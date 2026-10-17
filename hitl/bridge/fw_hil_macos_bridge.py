#!/usr/bin/env python3
"""PX4 macOS HIL: terminal-only USB/UDP bridge with persistent reconnect.

For the Normal-mode Simulink model with Simulation Pacing and DSP UDP blocks.
CRC-valid HIL_ACTUATOR_CONTROLS (ID93) frames go to Simulink first, one frame
per datagram at their received length (no padding). Simulink datagrams are
reduced to their CRC-valid frames and, like QGC datagrams, written to serial
at once after a passive autopilot-heartbeat probe, with no queue, rate limit,
source or age check. A write
that stalls for 100 ms reconnects. The dashboard shows per-message rates and
the real-time factor observed from HIL_SENSOR time_usec. No joystick, MATLAB
startup or MAVLink commands are generated here. QGC commands are forwarded
only when QGC sends them.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
import math
from pathlib import Path
import select
import signal
import socket
import sys
import shutil
import subprocess
import time

from macos_bridge_console import BridgeDashboard, DeviceSelection, vehicle_label
from macos_bridge_metrics import (BacklogHint, MessageRates, PacingMonitor,
                                  TransferTiming, WriteStats)

os.environ.setdefault('MAVLINK20', '1')
try:
    import serial
    from serial.tools import list_ports
    from pymavlink import mavutil
except ImportError as exc:
    raise SystemExit(f'Missing {exc.name}; run runbridge.command to check Python and offer local setup') from exc

try:
    from fastcrc.crc16 import mcrf4xx
except ImportError:
    from pymavlink.generator.mavcrc import x25crc

    def mcrf4xx(data: bytes) -> int:
        return x25crc(data).crc


SERIAL_READ_SIZE = 4096
# Waited only under backpressure; an unfinished write then reconnects (Windows parity).
SERIAL_WRITE_TIMEOUT_S = 0.1
HEARTBEAT_PROBE_TIMEOUT_S = 5.0
HEARTBEAT_PROBE_COOLDOWN_S = 10.0
# select() wakes on arrival; the timeout only paces reconnect, status and stop checks.
SELECT_TIMEOUT_S = 0.02
REPORT_PERIOD_S = 0.1
ACTUATOR_MSG_ID = 93
HIL_SENSOR_MSG_ID = 107
MANUAL_CONTROL_MSG_ID = 69
AGENT_MANUAL_HOLD_S = 0.2
# The model's UDP Receive block holds 128 bytes; a longer datagram is truncated
# and its partial frame can swallow the next one. ID93 frames are at most 106.
ACTUATOR_DATAGRAM_LIMIT = 128
# Messages whose rates the dashboard reports, per direction.
SIMULATOR_MSG_NAMES = ((HIL_SENSOR_MSG_ID, 'HIL_SENSOR'), (113, 'HIL_GPS'), (0, 'HEARTBEAT'))
ACTUATOR_MSG_NAMES = ((ACTUATOR_MSG_ID, 'HIL_ACTUATOR_CONTROLS'),)
# Only these low-rate messages are decoded, for the dashboard.
DASHBOARD_MSG_IDS = frozenset((0, 77, 253))  # HEARTBEAT, COMMAND_ACK, STATUSTEXT
CRC_EXTRA = {msgid: bytes((message.crc_extra,))
             for msgid, message in mavutil.mavlink.mavlink_map.items()}
AUTOPILOT_USB_VIDS = frozenset((0x26AC, 0x2DAE, 0x3162, 0x3185))


def is_likely_pixhawk(port: object) -> bool:
    if getattr(port, 'vid', None) in AUTOPILOT_USB_VIDS:
        return True
    attributes = (
        getattr(port, "device", ""),
        getattr(port, "description", ""),
        getattr(port, "manufacturer", ""),
        getattr(port, "product", ""),
        getattr(port, "hwid", ""),
    )
    identity = " ".join(str(value or "") for value in attributes).lower()
    keywords = (
        "pixhawk",
        "px4",
        "autopilot",
        "cubeorange",
        "cubepilot",
        "holybro",
    )
    return any(keyword in identity for keyword in keywords)


# USB serial nodes: macOS callout devices (any /dev/cu.* listed with USB metadata), Linux CDC-ACM and USB-serial.
if sys.platform == 'darwin':
    USB_SERIAL_PREFIXES = ('/dev/cu.usbmodem', '/dev/cu.usbserial')
    DEVICE_PREFIXES = ('/dev/cu.',)
else:
    USB_SERIAL_PREFIXES = DEVICE_PREFIXES = ('/dev/ttyACM', '/dev/ttyUSB')


def is_usb_serial(port):
    hwid = str(getattr(port, 'hwid', '') or '').upper()
    path = str(getattr(port, 'device', '') or '')
    if 'Bluetooth' in path or hwid.startswith('BTHENUM'):
        return False
    return (getattr(port, 'vid', None) is not None or hwid.startswith('USB')
            or path.startswith(USB_SERIAL_PREFIXES))


def make_mavlink_parser() -> mavutil.mavlink.MAVLink:
    parser = mavutil.mavlink.MAVLink(None)
    parser.robust_parsing = True
    return parser


@dataclass(frozen=True)
class Device:
    path: str
    identity: str
    label: str
    priority: int = 1


def device_identity(port):
    """Serial numbers such as 0 are placeholders; prefer USB location instead."""
    serial_number = str(getattr(port, 'serial_number', '') or '').strip()
    base = f"usb:{getattr(port, 'vid', None)}:{getattr(port, 'pid', None)}"
    if (serial_number.lower() not in {'', 'unknown', 'none', 'n/a'}
            and serial_number.replace('-', '').strip('0')):
        return f'{base}:serial:{serial_number}'
    location = getattr(port, 'location', None)
    if location:
        return f'{base}:location:{location}'
    return 'path:' + port.device


def is_autopilot_heartbeat(message):
    if message.get_type() != 'HEARTBEAT' or message.get_srcSystem() == 0:
        return False
    # A component ID alone does not identify an autopilot. Use heartbeat fields.
    non_vehicle_types = {
        getattr(mavutil.mavlink, name) for name in (
            'MAV_TYPE_GCS', 'MAV_TYPE_ONBOARD_CONTROLLER', 'MAV_TYPE_GIMBAL',
            'MAV_TYPE_CAMERA', 'MAV_TYPE_ADSB', 'MAV_TYPE_ANTENNA_TRACKER')
        if hasattr(mavutil.mavlink, name)
    }
    return (message.autopilot in mavutil.mavlink.enums['MAV_AUTOPILOT']
            and message.autopilot != mavutil.mavlink.MAV_AUTOPILOT_INVALID
            and message.type in mavutil.mavlink.enums['MAV_TYPE']
            and message.type not in non_vehicle_types)


def heartbeat_label(message):
    autopilot = mavutil.mavlink.enums['MAV_AUTOPILOT'][message.autopilot].name
    vehicle = mavutil.mavlink.enums['MAV_TYPE'][message.type].name
    return f'{autopilot}; {vehicle}; System ID={message.get_srcSystem()}, Component ID={message.get_srcComponent()}'


def reconnection_choices(found, preferred):
    """Re-selection is explicit when a device without a real serial changes port."""
    if preferred is None:
        return found if len(found) > 1 else []
    matches = [d for d in found if d.identity == preferred.identity]
    if len(matches) > 1:
        return matches
    if not matches and (':location:' in preferred.identity or preferred.identity.startswith('path:')):
        return found
    return []


def usb_callout_paths():
    """Rescan /dev on every discovery attempt, including late USB attachment."""
    root = Path('/dev')
    return sorted({str(path) for prefix in USB_SERIAL_PREFIXES
                   for path in root.glob(prefix[len('/dev/'):] + '*')})


def devices():
    """Enumerate USB serial devices (macOS callout or Linux ACM/USB nodes); retain USB identity across renumbering."""
    result = []
    for port in list_ports.comports():
        if not is_usb_serial(port) or not port.device.startswith(DEVICE_PREFIXES):
            continue
        identity = device_identity(port)
        result.append(Device(port.device, identity, port.description or port.device,
                             0 if is_likely_pixhawk(port) else 1))
    listed = {item.path for item in result}
    for path in usb_callout_paths():
        if path not in listed:
            result.append(Device(path, 'path:' + path, path))
    return sorted(result, key=lambda item: (item.priority, item.path))


def choose_device(found, preferred=None, requested='auto'):
    if preferred is not None:
        matches = [d for d in found if d.identity == preferred.identity]
        if not matches and preferred.identity.startswith('path:'):
            # IOKit metadata may appear after /dev created the USB callout node.
            matches = [d for d in found if d.path == preferred.path]
        return matches[0] if len(matches) == 1 else None
    if requested != 'auto':
        match = next((d for d in found if os.path.realpath(d.path) == os.path.realpath(requested)), None)
        if match:
            return match
        return Device(requested, 'path:' + requested, requested) if Path(requested).exists() else None
    return found[0] if len(found) == 1 else None


def serial_owner(path):
    """Check both Darwin names (or the one Linux node) for the same device before opening it."""
    paths = [path]
    if path.startswith('/dev/cu.'):
        paths.append('/dev/tty.' + path[len('/dev/cu.'):])
    try:
        lsof = '/usr/sbin/lsof' if Path('/usr/sbin/lsof').exists() else shutil.which('lsof') or 'lsof'
        result = subprocess.run([lsof, '-t', '--', *paths],
                                capture_output=True, text=True, timeout=2, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OSError(f'Cannot check serial port owner: {exc}') from exc
    owners = [line for line in result.stdout.splitlines()
              if line.isdigit() and int(line) != os.getpid()]
    return ','.join(sorted(set(owners))) or None


def udp_socket(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Deliberately exclusive: a second bridge must not steal incoming UDP.
        sock.bind(('127.0.0.1', port))
        sock.setblocking(False)
        return sock
    except BaseException:
        sock.close()
        raise


def scan_frames(data):
    """Locate complete CRC-valid MAVLink v1/v2 frames without decoding payloads.

    Returns (frames, end, bad): frames holds (msgid, start, stop) slices, end is
    the start of a trailing partial frame, and bad counts CRC failures. A CRC
    failure resynchronizes one byte later. Unknown IDs cannot be CRC-checked, so
    they are skipped only when the next frame start is where their length says.
    """
    frames = []
    bad = 0
    size = len(data)
    index = 0
    while index < size:
        stx = data[index]
        if stx == 0xFD:
            if size - index < 10:
                break
            length = data[index+1]
            msgid = data[index+7] | data[index+8] << 8 | data[index+9] << 16
            crc_at = index + 10 + length
            stop = crc_at + (15 if data[index+2] & 1 else 2)
        elif stx == 0xFE:
            if size - index < 6:
                break
            length = data[index+1]
            msgid = data[index+5]
            crc_at = index + 6 + length
            stop = crc_at + 2
        else:
            v2 = data.find(b'\xfd', index)
            v1 = data.find(b'\xfe', index)
            candidates = [found for found in (v1, v2) if found >= 0]
            index = min(candidates) if candidates else size
            continue
        if stop > size:
            break
        extra = CRC_EXTRA.get(msgid)
        if extra is None:
            index = stop if stop == size or data[stop] in (0xFD, 0xFE) else index + 1
            continue
        if mcrf4xx(bytes(data[index+1:crc_at]) + extra) != data[crc_at] | data[crc_at+1] << 8:
            bad += 1
            index += 1
            continue
        frames.append((msgid, index, stop))
        index = stop
    return frames, index, bad


def count_frames(data):
    return len(scan_frames(bytes(data))[0])


def simulator_payload(raw):
    """Keep only CRC-valid frames of a Simulink datagram, bytes unchanged.

    Trailing zero fill and unknown message IDs are dropped. Returns
    (payload, frames, bad) where frames holds (msgid, start, stop) slices of
    payload.
    """
    found, _, bad = scan_frames(raw)
    if len(found) == 1:
        msgid, start, stop = found[0]
        return raw[start:stop], [(msgid, 0, stop-start)], bad
    frames = []
    offset = 0
    for msgid, start, stop in found:
        frames.append((msgid, offset, offset+stop-start))
        offset += stop-start
    return b''.join(raw[start:stop] for _, start, stop in found), frames, bad


def frame_origin(data, start):
    """(sysid, compid, payload start, payload length) of the frame at start."""
    if data[start] == 0xFD:
        return data[start+5], data[start+6], start+10, data[start+1]
    return data[start+3], data[start+4], start+6, data[start+1]


def hil_sensor_time_usec(data, start):
    """HIL_SENSOR time_usec: the first little-endian uint64 of the payload.

    MAVLink 2 trims trailing zero bytes, so a short payload is zero-extended.
    Returns (time_usec, sysid, compid).
    """
    sysid, compid, offset, length = frame_origin(data, start)
    field = bytes(data[offset:offset+min(length, 8)]).ljust(8, b'\0')
    return int.from_bytes(field, 'little'), sysid, compid


def actuator_datagram(frame):
    """One received ID93 frame per datagram, unchanged and unpadded."""
    frame = bytes(frame)
    if len(frame) > ACTUATOR_DATAGRAM_LIMIT:
        raise ValueError(f'Actuator frame exceeds {ACTUATOR_DATAGRAM_LIMIT} bytes')
    return frame


def write_serial(port, payload, timeout=SERIAL_WRITE_TIMEOUT_S, stats=None):
    """Write now; wait for tty space only under backpressure, at most timeout.

    pyserial keeps the fd nonblocking, and its write_timeout=0 path retries
    EAGAIN in a busy loop. Writing the fd directly costs one syscall when the
    buffer has room. Returns bytes written; fewer than len(payload) is a stall.
    stats (WriteStats) records whether the first attempt was incomplete and
    how long this call waited for tty space.
    """
    fd = port.fileno()
    view = memoryview(payload)
    written = 0
    deadline = None
    started = None
    while written < len(view):
        try:
            written += os.write(fd, view[written:])
            continue
        except BlockingIOError:
            pass
        now = time.perf_counter()
        if deadline is None:
            started = now
            deadline = now + timeout
        if now >= deadline or not select.select([], [fd], [], deadline-now)[1]:
            break
    if stats is not None:
        now = time.perf_counter()
        stats.observe(now, 0.0 if started is None else now-started, started is not None)
    return written


class HeartbeatProbe:
    """Read-only MAVLink detection; discard bytes preceding an autopilot heartbeat."""

    def __init__(self):
        self.buffer = b''
        self.decoder = make_mavlink_parser()
        self.bad_data = 0

    def feed(self, raw):
        data = self.buffer + raw
        frames, end, bad = scan_frames(data)
        self.bad_data += bad
        for msgid, start, stop in frames:
            if msgid != 0:
                continue
            try:
                message = self.decoder.parse_char(data[start:stop])
            except mavutil.mavlink.MAVError:
                continue
            if message is not None and is_autopilot_heartbeat(message):
                self.buffer = b''
                return data[start:]
        self.buffer = data[end:]
        return None


def split_manual_control(raw):
    """Separate CRC-valid joystick frames, preserving every other byte."""
    found = [(start, stop) for msgid, start, stop in scan_frames(raw)[0]
             if msgid == MANUAL_CONTROL_MSG_ID]
    if not found:
        return raw, b''
    rest = []
    index = 0
    for start, stop in found:
        rest.append(raw[index:start])
        index = stop
    rest.append(raw[index:])
    return b''.join(rest), b''.join(raw[start:stop] for start, stop in found)


class SerialRouter:
    """Verify the controller, then route its bytes, actuator frames first."""

    def __init__(self, sim_out, sim_destination, qgc, qgc_destination, display, state, rates=None,
                 agent=None, agent_destination=None):
        self._sim_out = sim_out
        self._sim_destination = sim_destination
        self._qgc = qgc
        self._qgc_destination = qgc_destination
        self._agent = agent
        self._agent_destination = agent_destination
        self._display = display
        self._state = state
        self.timing = TransferTiming()
        self.rates = rates or MessageRates(ACTUATOR_MSG_NAMES)
        self.actuator_messages = 0
        self.actuator_send_errors = 0
        self.bad_data = 0
        self.reset()

    def reset(self):
        """A new serial session never joins a partial frame from the previous one."""
        self._buffer = b''
        self._decoder = make_mavlink_parser()
        self._last_armed = self._last_custom_mode = None
        self._last_status_text = ''
        self._probe = HeartbeatProbe()
        self._probe_bad_data = 0
        self._state.update(armed=None, last_heartbeat=None, last_control=None,
                           controller='Unverified', source=None, verified=False)

    def __call__(self, received_at, raw):
        probing = not self._state['verified']
        if probing:
            payload = self._probe.feed(raw)
            self.bad_data += self._probe.bad_data - self._probe_bad_data
            self._probe_bad_data = self._probe.bad_data
            if payload is None:
                return 0
            raw = payload
            self._state['verified'] = True
        data = self._buffer + raw if self._buffer else raw
        frames, end, bad = scan_frames(data)
        for msgid, start, stop in frames:
            if msgid == ACTUATOR_MSG_ID:
                self.rates.receive(received_at, (msgid,))
                try:
                    self._sim_out.sendto(actuator_datagram(data[start:stop]),
                                         self._sim_destination)
                except (OSError, ValueError):
                    self.actuator_send_errors += 1
                    continue
                self.actuator_messages += 1
                sent = time.perf_counter()
                self.rates.forward(sent, (msgid,))
                self._state['last_control'] = sent
        try:
            self._qgc.sendto(raw, self._qgc_destination)
        except OSError:
            pass
        if self._agent is not None:
            try:
                self._agent.sendto(raw, self._agent_destination)
            except OSError:
                pass
        for msgid, start, stop in frames:
            if msgid in DASHBOARD_MSG_IDS:
                self._observe(data[start:stop])
        self._buffer = data[end:]
        self.bad_data += 0 if probing else bad  # probe already counted this read's CRC failures
        if frames:
            completed = time.perf_counter()
            self.timing.observe(completed, completed-received_at, len(frames))
        return len(frames)

    def _observe(self, frame):
        try:
            message = self._decoder.parse_char(frame)
        except mavutil.mavlink.MAVError:
            return
        if message is None:
            return
        kind = message.get_type()
        if kind == 'HEARTBEAT':
            if not is_autopilot_heartbeat(message):
                return
            first = self._state.get('last_heartbeat') is None
            self._state['last_heartbeat'] = time.perf_counter()
            firmware = mavutil.mavlink.enums['MAV_AUTOPILOT'][message.autopilot].name
            vehicle = mavutil.mavlink.enums['MAV_TYPE'][message.type].name
            self._state['controller'] = (firmware.replace('MAV_AUTOPILOT_', '') + ' / '
                                         + vehicle_label(vehicle.replace('MAV_TYPE_', '')))
            if first:
                self._display.event('Heartbeat verified: ' + self._state['controller'])
            self._state['source'] = (message.get_srcSystem(), message.get_srcComponent())
            armed = bool(message.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
            custom_mode = int(message.custom_mode)
            self._state['armed'] = armed
            if armed != self._last_armed:
                self._display.event('Flight controller armed' if armed else 'Flight controller disarmed')
            if self._last_custom_mode is not None and custom_mode != self._last_custom_mode:
                self._display.event(f'Flight controller mode changed: {custom_mode}')
            self._last_armed = armed
            self._last_custom_mode = custom_mode
        elif kind == 'STATUSTEXT':
            text = str(message.text).rstrip('\0')
            if text and text != self._last_status_text:
                self._display.event('Flight controller message: '+text)
                self._last_status_text = text
        elif kind == 'COMMAND_ACK':
            self._display.event(f'Command acknowledgement: {message.command}, result: {message.result}')


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', default='auto', help='macOS /dev/cu.* port; default auto-detect and wait')
    parser.add_argument('--list-serial', '--check', action='store_true', help='List USB candidates without opening them; heartbeat identity is not yet verified')
    parser.add_argument('--baud', type=int, default=115200)
    parser.add_argument('--sim-in-port', type=int, default=14580)
    parser.add_argument('--sim-out-port', type=int, default=14572)
    parser.add_argument('--sim-destination-port', type=int, default=14571)
    parser.add_argument('--qgc-local-port', type=int, default=14575)
    parser.add_argument('--qgc-destination-port', type=int, default=14550)
    parser.add_argument('--agent-local-port', type=int, default=14576,
                        help='Local script endpoint; received datagrams are written to the flight controller')
    parser.add_argument('--agent-destination-port', type=int, default=14560,
                        help='Flight-controller bytes are always copied to this localhost port')
    parser.add_argument('--retry-seconds', type=float, default=2.0)
    parser.add_argument('--probe-seconds', type=float, default=HEARTBEAT_PROBE_TIMEOUT_S,
                        help='Passive autopilot heartbeat timeout before releasing a port (default 5 s)')
    parser.add_argument('--plain', action='store_true', help='Use a one-line English summary every second')
    parser.add_argument('--duration', type=float, default=0, help='Stop after N seconds; 0 runs until Ctrl+C')
    parser.add_argument('--stop-file', type=Path, help='Stop cleanly when this initially absent file appears')
    args = parser.parse_args()
    if (not all(math.isfinite(x) for x in (args.retry_seconds, args.probe_seconds, args.duration))
            or args.retry_seconds <= 0 or args.probe_seconds <= 0 or args.baud <= 0 or args.duration < 0):
        parser.error('retry-seconds/probe-seconds/baud must be positive; duration finite and nonnegative')
    for name in ['sim_in_port', 'sim_out_port', 'sim_destination_port', 'qgc_local_port', 'qgc_destination_port',
                 'agent_local_port', 'agent_destination_port']:
        if not 1 <= getattr(args, name) <= 65535:
            parser.error(f'{name} must be in 1..65535')
    if len({args.sim_in_port, args.sim_out_port, args.qgc_local_port, args.agent_local_port}) != 4:
        parser.error('Local UDP ports must be different')
    if args.stop_file and args.stop_file.exists():
        parser.error('stop-file already exists; use a new path')
    return args


def main():
    args = arguments()
    if args.list_serial:
        for device in devices():
            kind = 'known autopilot candidate' if device.priority == 0 else 'USB serial candidate'
            print(f'{kind} (heartbeat not verified): {device.path}: {device.label} [{device.identity}]')
        return 0
    opened = []
    try:
        for port in [args.sim_in_port, args.sim_out_port, args.qgc_local_port, args.agent_local_port]:
            opened.append(udp_socket(port))
    except OSError as exc:
        for sock in opened:
            sock.close()
        print(f'UDP port unavailable: {exc}. Stop the other HIL bridge first.', file=sys.stderr)
        return 2
    sim_in, sim_out, qgc, agent = opened
    agent_destination = ('127.0.0.1', args.agent_destination_port)
    agent_manual_until = 0.0
    agent_manual = False
    sim_destination = ('127.0.0.1', args.sim_destination_port)
    qgc_destination = ('127.0.0.1', args.qgc_destination_port)
    running = True

    def stop(_signum, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    controller = preferred = None
    active_device = None
    probe_deadline = 0.0
    rejected = {}
    next_retry = 0.0
    tx_timing = TransferTiming()
    next_report = time.perf_counter()
    last_notice = None
    manual_choice = None
    counters = dict(serial_rx_bytes=0, serial_rx_packets=0, serial_tx_bytes=0, serial_tx_packets=0,
                    sim_messages=0, qgc_rx_datagrams=0, connections=0, discarded_disconnected=0,
                    sim_bad_data=0, agent_rx_datagrams=0, qgc_manual_diverted=0)
    display = BridgeDashboard(plain=args.plain)
    selection = DeviceSelection(display)
    state = dict(opened=False, port='Automatic')
    router = SerialRouter(sim_out, sim_destination, qgc, qgc_destination, display, state,
                          agent=agent, agent_destination=agent_destination)
    sim_rates = MessageRates(SIMULATOR_MSG_NAMES)
    pacing = PacingMonitor()
    backlog = BacklogHint()
    write_stats = WriteStats()
    reported = dict(backlog=False, restarts=0, sensor='waiting')

    def notice(message):
        nonlocal last_notice
        if message != last_notice:
            display.event(message)
            last_notice = message

    def disconnect(reason):
        nonlocal controller, next_retry, active_device
        if controller is not None:
            controller.close()
        controller = None
        active_device = None
        state.update(opened=False)
        router.reset()
        next_retry = time.perf_counter() + args.retry_seconds
        notice(f'Disconnected - Waiting to reconnect: {reason}')

    def send(payload, received, frames=None):
        """Write on arrival; a failed or unfinished write drops it and reconnects.

        frames: (msgid, start, stop) slices of a Simulink payload, counted per
        message once completely written; None for QGC data.
        """
        if controller is None or not state.get('verified'):
            counters['discarded_disconnected'] += 1
            return False
        try:
            written = write_serial(controller, payload, stats=write_stats)
        except OSError as exc:
            write_stats.errors += 1
            disconnect(exc)
            return False
        completed = time.perf_counter()
        complete = written == len(payload)
        if frames is None:
            packets = count_frames(payload if complete else payload[:written])
        else:
            done = [msgid for msgid, _, stop in frames if stop <= written]
            sim_rates.forward(completed, done)
            packets = len(done)
        counters['serial_tx_bytes'] += written
        counters['serial_tx_packets'] += packets
        tx_timing.observe(completed, completed-received, packets)
        if not complete:
            write_stats.timeouts += 1
            disconnect(f'serial write incomplete: {written}/{len(payload)} bytes '
                       f'within {SERIAL_WRITE_TIMEOUT_S*1000:.0f} ms')
        return complete

    def publish(now):
        ra, rn, rx = router.timing.snapshot(now)
        ta, tn, tx = tx_timing.snapshot(now)
        messages = sim_rates.snapshot(now)
        messages.update(router.rates.snapshot(now))
        sensor = pacing.snapshot(now)
        hint = backlog.update(now, messages['HIL_ACTUATOR_CONTROLS']['forwarded_hz'],
                              messages['HIL_SENSOR']['received_hz'], sensor['state'])
        if hint['backlog'] != reported['backlog']:
            display.event('Possible actuator backlog: ' + hint['backlog_reason'] if hint['backlog']
                          else 'Actuator backlog condition cleared')
        restarts = sensor['resets_source'] + sensor['resets_backwards']
        if restarts != reported['restarts']:
            display.event('HIL_SENSOR time restarted (new source or time_usec went backwards)')
        if sensor['state'] != reported['sensor'] and 'ok' in (sensor['state'], reported['sensor']):
            display.event('HIL_SENSOR stream ' + ('observed' if sensor['state'] == 'ok' else sensor['state']))
        reported.update(backlog=hint['backlog'], restarts=restarts, sensor=sensor['state'])
        display.update(dict(state, **counters, **write_stats.snapshot(now), **hint,
            sample_time=now, messages=messages,
            pacing=sensor,
            actuator_messages=router.actuator_messages,
            actuator_send_errors=router.actuator_send_errors,
            bad_data=router.bad_data+counters['sim_bad_data'],
            rx_avg_ms=ra, rx_min_ms=rn, rx_max_ms=rx,
            tx_avg_ms=ta, tx_min_ms=tn, tx_max_ms=tx))

    display.start()
    notice(f'Sensor UDP {args.sim_in_port}; actuator {args.sim_out_port} -> {args.sim_destination_port}; QGC {args.qgc_local_port} -> {args.qgc_destination_port}')
    notice(f'Agent UDP {args.agent_local_port} -> {args.agent_destination_port}')
    deadline = time.perf_counter()+args.duration if args.duration else float('inf')
    try:
        while running and time.perf_counter() < deadline:
            now = time.perf_counter()
            if controller is None and now >= next_retry:
                # Fresh IOKit and /dev discovery each retry, never a startup-only list.
                rejected = {key: until for key, until in rejected.items() if until > now}
                found = [device for device in devices() if device.identity not in rejected]
                pinned = preferred if preferred and (args.serial == 'auto' or not preferred.identity.startswith('path:')) else None
                chosen = manual_choice or choose_device(found, pinned, args.serial)
                if chosen is not None and chosen.identity in rejected:
                    chosen = None
                manual_choice = None
                if chosen is None:
                    ambiguous = reconnection_choices(found, preferred)
                    selection.set_choices(ambiguous if args.serial == 'auto' else ())
                    notice('Waiting for a flight controller or device selection')
                else:
                    selection.set_choices(())
                    try:
                        owner = serial_owner(chosen.path)
                        if owner:
                            raise OSError(f'serial port is already used by PID {owner}')
                        controller = serial.Serial(chosen.path, args.baud, timeout=0,
                                                   write_timeout=0, exclusive=True)
                    except (OSError, serial.SerialException) as exc:
                        if controller is not None:
                            controller.close()
                        controller = None
                        state['opened'] = False
                        notice(f'Waiting for connection: {chosen.path}: {exc}')
                    else:
                        active_device = chosen
                        probe_deadline = time.perf_counter() + args.probe_seconds
                        router.reset()
                        state.update(opened=True, port=chosen.path)
                        notice(f'Serial port opened: {chosen.path}')
                        notice(f'Probing {chosen.path}: waiting up to {args.probe_seconds:g} s for an autopilot heartbeat; forwarding paused')
                        if ':location:' in chosen.identity or chosen.identity.startswith('path:'):
                            notice('USB identity uses its current location; select again if the USB location changes')
                next_retry = time.perf_counter() + args.retry_seconds
            readers = [sim_in, qgc, agent]
            if controller is not None:
                readers.append(controller)
            stdin = selection.reader()
            if stdin is not None:
                readers.append(stdin)
            try:
                readable, _, _ = select.select(readers, [], [], SELECT_TIMEOUT_S)
            except (OSError, ValueError) as exc:
                disconnect(exc)
                continue
            if stdin is not None and stdin in readable:
                manual_choice = selection.read()
                if manual_choice is not None:
                    next_retry = 0
            if controller is not None and controller in readable:
                try:
                    raw = os.read(controller.fileno(), SERIAL_READ_SIZE)
                except BlockingIOError:
                    raw = None
                except OSError as exc:
                    disconnect(exc)
                    raw = None
                else:
                    if not raw:
                        disconnect('serial device closed')
                if raw:
                    was_verified = state.get('verified', False)
                    counters['serial_rx_bytes'] += len(raw)
                    counters['serial_rx_packets'] += router(time.perf_counter(), raw)
                    if not was_verified and state['verified']:
                        preferred = active_device
                        counters['connections'] += 1
                        notice(f'Bridge ready: {state["port"]}')
            if controller is not None and not state.get('verified') and time.perf_counter() >= probe_deadline:
                rejected[active_device.identity] = time.perf_counter() + HEARTBEAT_PROBE_COOLDOWN_S
                disconnect(f'No valid autopilot heartbeat on {active_device.path} within {args.probe_seconds:g} s; port released (retry after {HEARTBEAT_PROBE_COOLDOWN_S:g} s)')
            for sock in (sim_in, agent, qgc):
                if sock not in readable:
                    continue
                for _ in range(64):
                    try:
                        raw, sender = sock.recvfrom(4096)
                    except (BlockingIOError, ConnectionError):
                        break
                    received = time.perf_counter()
                    if sock is agent:
                        counters['agent_rx_datagrams'] += 1
                        if any(msgid == MANUAL_CONTROL_MSG_ID for msgid, _, _ in scan_frames(raw)[0]):
                            agent_manual_until = received + AGENT_MANUAL_HOLD_S
                            if not agent_manual:
                                agent_manual = True
                                notice('Agent MANUAL_CONTROL active: QGC joystick diverted to the agent port')
                        send(raw, received)
                        continue
                    if sock is qgc:
                        counters['qgc_rx_datagrams'] += 1
                        if received < agent_manual_until:
                            raw, manual = split_manual_control(raw)
                            if manual:
                                counters['qgc_manual_diverted'] += 1
                                try:
                                    agent.sendto(manual, agent_destination)
                                except OSError:
                                    pass
                            if not raw:
                                continue
                        send(raw, received)
                        continue
                    payload, frames, bad = simulator_payload(raw)
                    counters['sim_bad_data'] += bad
                    if not frames:
                        continue
                    sim_rates.receive(received, [msgid for msgid, _, _ in frames])
                    for msgid, start, _ in frames:
                        if msgid == HIL_SENSOR_MSG_ID:
                            stamp, sysid, compid = hil_sensor_time_usec(payload, start)
                            pacing.observe(received, stamp, (sender[1], sysid, compid))
                    if send(payload, received, frames):
                        counters['sim_messages'] += len(frames)
            now = time.perf_counter()
            if agent_manual and now >= agent_manual_until:
                agent_manual = False
                notice('Agent MANUAL_CONTROL stopped: QGC joystick restored')
            if now >= next_report:
                if args.stop_file and args.stop_file.exists():
                    break
                publish(now)
                next_report = now + REPORT_PERIOD_S
    finally:
        selection.close()
        if controller is not None:
            controller.close()
        for sock in opened:
            sock.close()
        state.update(stopped=True, opened=False, armed=None)
        publish(time.perf_counter())
        display.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
