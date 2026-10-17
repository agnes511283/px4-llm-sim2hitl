"""Independent macOS HIL dashboard; output stays off the routing thread."""
from __future__ import annotations

from collections import deque
import os
import sys
import threading
import time
import unicodedata


def clean(text):
    """Device-provided text must never inject terminal control sequences."""
    return "".join(c if not unicodedata.category(c).startswith("C") else " "
                   for c in str(text))


def cell_width(text):
    return sum(0 if unicodedata.combining(c) else
               2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in text)


def fit(text, columns):
    text = clean(text)
    result, width = [], 0
    for c in text:
        size = cell_width(c)
        if width + size > columns:
            break
        result.append(c)
        width += size
    return "".join(result) + " " * max(0, columns-width)


def age_text(timestamp, now):
    if timestamp is None:
        return "Not received"
    age = max(0.0, now-timestamp)
    return f"{age*1000:.0f} ms" if age < 1 else f"{age:.1f} s"


class RateMeter:
    def __init__(self):
        self.previous = None
        self.peaks = {"rx": 1024.0, "tx": 1024.0}

    def sample(self, snapshot):
        now = snapshot.get("sample_time", time.perf_counter())
        values = {name: snapshot.get(key, 0) for name, key in (
            ("rx", "serial_rx_bytes"), ("tx", "serial_tx_bytes"),
            ("rx_packets", "serial_rx_packets"), ("tx_packets", "serial_tx_packets"))}
        rates = dict.fromkeys(values, 0.0)
        if self.previous is not None:
            old_time, old_values = self.previous
            elapsed = now-old_time
            if elapsed > 0:
                rates = {name: max(0, value-old_values[name])/elapsed for name, value in values.items()}
        self.previous = now, values
        for name in self.peaks:
            self.peaks[name] = max(1024.0, self.peaks[name], rates[name])
        return rates

    def bar(self, name, value, width=16):
        count = min(width, int(width*max(0, value)/self.peaks[name] + .5))
        if value > 0:
            count = max(1, count)
        return "#"*count + "-"*(width-count)


class ConsoleSurface:
    """ANSI terminal surface; restore cursor and alternate screen on exit."""
    def __init__(self, stream, plain=False):
        self.stream = stream
        self.vt = False
        self.active = False
        self._size = (0, 0)
        if plain or not stream.isatty():
            return
        if os.environ.get("TERM", "") not in ("", "dumb"):
            self.vt = True


    def size(self):
        try:
            return os.get_terminal_size(self.stream.fileno())
        except (OSError, ValueError, AttributeError):
            return (80, 30)

    def draw(self, lines, colors=None):
        if not self.vt:
            return
        size = self.size()
        prefix = ""
        if not self.active:
            prefix = "\x1b[?1049h\x1b[?25l"
            self.active = True
        if size != self._size:
            prefix += "\x1b[2J"
            self._size = size
        # Paint complete rows without clearing the screen on every refresh.
        pieces = [prefix, "\x1b[H"]
        for i, line in enumerate(lines[:max(1, size[1]-1)], 1):
            color = (colors or {}).get(i-1, "0")
            pieces.append(f"\x1b[{i};1H\x1b[{color}m{fit(line, max(1, size[0]-1))}\x1b[0m\x1b[K")
        pieces.append("\x1b[J")
        self.stream.write("".join(pieces))
        self.stream.flush()

    def close(self):
        try:
            if self.active:
                self.stream.write("\x1b[0m\x1b[?25h\x1b[?1049l")
                self.stream.flush()
        finally:
            self.active = False



def vehicle_label(name):
    """English names for reported MAV_TYPE values, including multirotors."""
    labels = {
        'GENERIC': 'Generic', 'FIXED_WING': 'Fixed-wing',
        'QUADROTOR': 'Quadrotor', 'HEXAROTOR': 'Hexarotor', 'OCTOROTOR': 'Octorotor',
        'TRICOPTER': 'Tricopter', 'COAXIAL': 'Coaxial', 'HELICOPTER': 'Helicopter',
        'DECAROTOR': 'Decarotor', 'DODECAROTOR': 'Dodecarotor',
        'VTOL_DUOROTOR': 'Vertical takeoff and landing / Duorotor',
        'VTOL_QUADROTOR': 'Vertical takeoff and landing / Quadrotor',
        'VTOL_TILTROTOR': 'Vertical takeoff and landing / Tiltrotor',
        'VTOL_TAILSITTER': 'Vertical takeoff and landing / Tailsitter',
        'VTOL_TILTWING': 'Vertical takeoff and landing / Tiltwing',
        'GROUND_ROVER': 'Ground rover', 'SURFACE_BOAT': 'Surface boat',
        'SUBMARINE': 'Submarine',
    }
    return labels.get(name, clean(name.replace('_', ' ').title()))


HEARTBEAT_STALE_S = 3.0


def heartbeat_stale(snapshot, now):
    heartbeat = snapshot.get('last_heartbeat')
    return heartbeat is not None and now-heartbeat > HEARTBEAT_STALE_S


def armed_label(snapshot, now=None):
    """Arming state from the latest verified heartbeat of the open serial port."""
    if not snapshot.get('opened'):
        return 'Unknown'
    armed = snapshot.get('armed')
    if armed is None or snapshot.get('last_heartbeat') is None:
        return 'Waiting for heartbeat'
    label = 'Armed' if armed else 'Disarmed'
    if now is not None and heartbeat_stale(snapshot, now):
        label += ' (last heartbeat, stale)'
    return label


def status_text(snapshot, now):
    """Serial open/closed, heartbeat OK/stale/missing and reconnection, separately."""
    if snapshot.get('stopped'):
        return 'Stopped', '37'
    connections = snapshot.get('connections', 0)
    if snapshot.get('opened'):
        prefix = 'Reconnected' if connections > 1 else 'Connected'
        heartbeat = snapshot.get('last_heartbeat')
        if heartbeat is None:
            port = 'Serial reopened' if connections > 1 else 'Serial open'
            return port + ' - Waiting for heartbeat', '33'
        if heartbeat_stale(snapshot, now):
            return f'{prefix} - Heartbeat stale ({now-heartbeat:.1f} s)', '33'
        return prefix + ' - Heartbeat OK', '32'
    if connections:
        return 'Disconnected - Waiting to reconnect', '31'
    return 'Waiting for flight controller connection', '33'


def rate_pair(snapshot, name):
    """Received/forwarded messages per second over the last second."""
    item = (snapshot.get('messages') or {}).get(name)
    if not item:
        return '--/--'
    return f"{item['received_hz']:.1f}/{item['forwarded_hz']:.1f}"


def number(value, digits, unit='', signed=False):
    if value is None:
        return '--'
    return f"{value:{'+' if signed else ''}.{digits}f}{unit}"


def pacing_summary(snapshot):
    """RTF text and dashboard color for the HIL_SENSOR time_usec observation."""
    pacing = snapshot.get('pacing') or {}
    state = pacing.get('state', 'waiting')
    if state == 'stale':
        return f"stale {number(pacing.get('last_age_s'), 1, ' s')}", '33'
    if state != 'ok':
        return 'waiting', '33'
    return number(pacing.get('rtf'), 3), '36'


def backlog_text(snapshot):
    return 'POSSIBLE' if snapshot.get('backlog') else 'none'


def pacing_fields(snapshot):
    pacing = snapshot.get('pacing') or {}
    rtf, _ = pacing_summary(snapshot)
    return ([f'RTF (observed): {rtf}',
             f"10 s: {number(pacing.get('rtf_long'), 3)}",
             f"Lag: {number(pacing.get('lag_ms'), 0, ' ms', True)}",
             f'Backlog: {backlog_text(snapshot)}'],
            ['Sim->FC rx/fwd Hz:', f"Sensor {rate_pair(snapshot, 'HIL_SENSOR')}",
             f"GPS {rate_pair(snapshot, 'HIL_GPS')}",
             f"Heartbeat {rate_pair(snapshot, 'HEARTBEAT')}"],
            ['FC->Sim rx/fwd Hz:', f"ID93 {rate_pair(snapshot, 'HIL_ACTUATOR_CONTROLS')}",
             f"Sensor gap max {number(pacing.get('gap_max_ms'), 1, ' ms')}",
             f"std {number(pacing.get('gap_std_ms'), 2, ' ms')}"])


def write_fields(snapshot):
    return [f"Write failures: {snapshot.get('write_failures', 0)} "
            f"(timeout {snapshot.get('write_timeouts', 0)}, error {snapshot.get('write_errors', 0)})",
            f"Incomplete writes: {snapshot.get('write_incomplete', 0)}, "
            f"max wait {snapshot.get('write_wait_max_ms', 0.0):.1f} ms"]


def timing_parts(snapshot, direction):
    parts = []
    for key, label in (('avg', 'Average'), ('min', 'Minimum'), ('max', 'Maximum')):
        value = snapshot.get(direction+'_'+key+'_ms')
        number = '--' if value is None else f'{value:.2f}'
        parts.append(f'{label} delay: {number} ms')
    return parts


def timing_text(snapshot, direction):
    return '   '.join(timing_parts(snapshot, direction))


def wrap_fields(fields, width, indent='  '):
    """Keep each full field together when wrapping a narrow console."""
    lines, line = [], indent
    for field in fields:
        candidate = line + ('   ' if line != indent else '') + field
        if line != indent and cell_width(candidate) > width:
            lines.append(line)
            line = indent + field
        else:
            line = candidate
    if line != indent:
        lines.append(line)
    return lines


def traffic_lines(snapshot, rates, meter, width):
    lines = []
    for direction, label in (('rx', 'Flight controller to computer'),
                             ('tx', 'Computer to flight controller')):
        if lines:
            lines.append('')
        lines.append(label)
        metrics = [f'{rates[direction]/1024:.2f} KiB/s',
                   f"{rates[direction+'_packets']:.1f} packets/second"]
        numbers = '    '.join(metrics)
        bar_width = min(16, width-cell_width(numbers)-8)
        if bar_width >= 4:
            lines.append('  ['+meter.bar(direction, rates[direction], bar_width)+']    '+numbers)
        else:
            lines += wrap_fields(metrics, width)
        lines += wrap_fields(timing_parts(snapshot, direction), width)
    return lines


def heartbeat_text(snapshot, now):
    timestamp = snapshot.get('last_heartbeat')
    return 'Not received' if timestamp is None else age_text(timestamp, now)+' ago'


def plain_text(snapshot, rates, now):
    status, _ = status_text(snapshot, now)
    source = snapshot.get('controller', 'Unverified')
    pacing = ' '.join(' '.join(fields) for fields in pacing_fields(snapshot))
    return (f"Connection: {status} | Flight controller: {source} / {snapshot.get('port', 'Automatic')} | "
            f"Arming status: {armed_label(snapshot, now)} | Last 1 second | "
            f"Flight controller to computer: {rates['rx']/1024:.2f} KiB/s {rates['rx_packets']:.1f} packets/second | "
            f"Local forwarding delay: {timing_text(snapshot, 'rx')} | "
            f"Computer to flight controller: {rates['tx']/1024:.2f} KiB/s {rates['tx_packets']:.1f} packets/second | "
            f"Local forwarding delay: {timing_text(snapshot, 'tx')} | "
            f"{pacing} | "
            f"Last heartbeat: {heartbeat_text(snapshot, now)} | "
            f"Connections: {snapshot.get('connections', 0)} | "
            f"Reconnections: {max(0, snapshot.get('connections', 0)-1)} | "
            f"Invalid data: {snapshot.get('bad_data', 0)} | "
            + ' | '.join(write_fields(snapshot)))


def panel_lines(snapshot, rates, meter, events, now, width=80, height=30):
    width = max(1, min(width-1, 100))
    rows = []

    def add(text='', color='37', decoration=False, detail=False):
        rows.append((text, color, decoration, detail))

    status, color = status_text(snapshot, now)
    identity = snapshot.get('controller', 'Unverified')
    ids = snapshot.get('source')
    source = f'{ids[0]} / {ids[1]}' if ids else 'Unverified'
    add('='*width, '36')
    add(' HIL Flight Controller Bridge', '36')
    add('='*width, '36')
    add(decoration=True)
    add('Connection        : '+status, color)
    add(f"Flight controller : {identity} / {snapshot.get('port', 'Automatic')}")
    add('System / Component: '+source)
    armed_color = '31' if snapshot.get('armed') is True and snapshot.get('opened') else '37'
    add('Arming status     : '+armed_label(snapshot, now), armed_color)
    add('Last heartbeat    : '+heartbeat_text(snapshot, now))
    add(decoration=True)
    heading = 'Traffic and local forwarding delay - Last 1 second'
    if cell_width(heading) <= width:
        add(heading)
    else:
        add('Traffic and local forwarding delay')
        add('Last 1 second')
    add('-'*width, '90', True)
    add(decoration=True)
    direction_color = '36'
    for line in traffic_lines(snapshot, rates, meter, width):
        if line == 'Computer to flight controller':
            direction_color = '35'
        is_rate = 'KiB/s' in line or 'packets/second' in line or line.endswith('to computer') or line.endswith('to flight controller')
        add(line, direction_color if is_rate else '37', not line, 'delay:' in line)
    add(decoration=True)
    _, pacing_color = pacing_summary(snapshot)
    first_row = True
    for fields in pacing_fields(snapshot):
        color = ('33' if snapshot.get('backlog') else pacing_color) if first_row else '37'
        for line in wrap_fields(fields, width, '' if first_row else '  '):
            add(line, color, detail=not first_row)
        first_row = False
    add(decoration=True)
    for line in wrap_fields([f"Connections: {snapshot.get('connections', 0)}",
                             f"Reconnections: {max(0, snapshot.get('connections', 0)-1)}",
                             f"Invalid data: {snapshot.get('bad_data', 0)}"], width, ''):
        add(line)
    for line in wrap_fields(write_fields(snapshot), width, ''):
        add(line)
    add(decoration=True)

    # Remove decoration, then detail rows, before sacrificing recent events.
    footer = [('Rate bars are relative to the highest rate in this session.', '90'),
              ('Delays measure forwarding inside this bridge only.', '90')]
    refresh, exit_hint = 'Refresh interval: 1 second', 'Press Ctrl+C to exit'
    if width >= len(refresh)+len(exit_hint)+2:
        footer.append((refresh+' '*(width-len(refresh)-len(exit_hint))+exit_hint, '37'))
    else:
        footer += [(refresh, '37'), (exit_hint, '37')]
    full_height = len(rows)+2+6+2+len(footer)
    decorated = full_height <= height-1
    if not decorated:
        rows = [row for row in rows if not row[2]]
    extra = 2 if decorated else 1

    def event_room():
        return max(0, min(6, height-1-len(rows)-len(footer)-extra-(2 if decorated else 0)))
    if event_room() < 2:
        rows = [row for row in rows if not row[3]]
    room = event_room()
    if room:
        add('Recent events - Latest 6')
        if decorated:
            add('-'*width, '90')
        shown = list(events)[-room:]
        for event in shown:
            add(event)
        for _ in range(room-len(shown)):
            add()
    if decorated:
        add()
        add('-'*width, '90')
    # Preserve the exit hint even if the user makes the console exceptionally small.
    rows = rows[:max(0, height-1-len(footer))]
    rows += [(line, color, False, False) for line, color in footer]
    lines = [fit(line, width).rstrip() for line, *_ in rows]
    colors = {i: row[1] for i, row in enumerate(rows)}
    return lines, colors


class BridgeDashboard:
    def __init__(self, plain=False, stream=None):
        self.stream = stream or sys.stdout
        self.plain = plain
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._snapshot = {"sample_time": time.perf_counter()}
        self._events = deque(maxlen=6)
        self._selection = ((), "", False)
        self._selection_version = 0
        self._thread = threading.Thread(target=self._run, name="BridgeDashboard", daemon=True)

    def start(self):
        self._thread.start()

    def update(self, snapshot):
        with self._lock:
            self._snapshot = dict(snapshot)

    def event(self, message):
        with self._lock:
            self._events.append(time.strftime("%H:%M:%S") + "  " + clean(message))

    def select(self, choices, response="", invalid=False):
        with self._lock:
            state = (tuple(choices), response, invalid)
            if state != self._selection:
                self._selection = state
                self._selection_version += 1
                self._wake.set()

    def close(self):
        self._stop.set()
        self._wake.set()
        self._thread.join(timeout=2.0)

    def _read(self):
        with self._lock:
            return (dict(self._snapshot), tuple(self._events),
                    self._selection, self._selection_version)

    def _run(self):
        surface = ConsoleSurface(self.stream, self.plain)
        meter = RateMeter()
        next_frame = time.perf_counter()
        last_selection = -1
        shown_events = ()
        try:
            while not self._stop.is_set():
                self._wake.clear()
                snapshot, events, selection, version = self._read()
                choices, response, invalid = selection
                now = time.perf_counter()
                if choices:
                    # Pause dashboard frames while the user selects a controller.
                    if version != last_selection:
                        lines = ["HIL - Select flight controller", "",
                                 "Multiple flight controllers or changed USB location"]
                        lines += [f"  {i}: {clean(item.label)}" for i, item in enumerate(choices, 1)]
                        lines += ["", "Type a number and press Enter to confirm; press Ctrl+C to exit",
                                  ("Invalid number; please try again" if invalid else ""),
                                  "Number: " + response]
                        if surface.vt:
                            surface.draw(lines, {0: "33"})
                        elif last_selection == -1 or choices != previous_choices:
                            self.stream.write("\n".join(lines) + "\n")
                            self.stream.flush()
                        last_selection = version
                    previous_choices = choices
                    # Keep rate baselines current; a paused menu is not a traffic burst.
                    meter.sample(snapshot)
                    next_frame = now
                elif now >= next_frame or last_selection != -1:
                    width, height = surface.size()
                    rates = meter.sample(snapshot)
                    if surface.vt:
                        lines, colors = panel_lines(snapshot, rates, meter, events, now, width, height)
                        surface.draw(lines, colors)
                    else:
                        added = " | ".join(item for item in events if item not in shown_events)
                        line = f"[{time.strftime('%H:%M:%S')}] HIL | " + plain_text(snapshot, rates, now)
                        self.stream.write(line + (" | "+added if added else "") + "\n")
                        self.stream.flush()
                        shown_events = events
                    next_frame = now + 1.0
                    last_selection = -1
                self._wake.wait(max(.02, min(1.0, next_frame-time.perf_counter())) if not choices else 1.0)
        except (OSError, UnicodeError):
            # A closed/unsupported output stream must not interrupt serial routing.
            pass
        finally:
            try:
                surface.close()
                self.stream.write("Bridge stopped; serial port and UDP sockets released.\n")
                self.stream.flush()
            except (OSError, UnicodeError):
                pass
