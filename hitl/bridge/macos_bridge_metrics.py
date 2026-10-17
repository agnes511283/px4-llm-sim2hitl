"""Bounded-window forwarding and pacing measurements; no console or file I/O."""
from collections import deque
import math


class TransferTiming:
    """Packet-weighted last-second mean/min/max; amortized O(1) updates."""
    def __init__(self):
        self.samples = deque()
        self.minima = deque()
        self.maxima = deque()
        self.total = 0.0
        self.count = 0

    def _expire(self, now):
        while self.samples and self.samples[0][0] <= now-1:
            stamp, delay, count = self.samples.popleft()
            self.total -= delay*count
            self.count -= count
            if self.minima and self.minima[0] == (stamp, delay):
                self.minima.popleft()
            if self.maxima and self.maxima[0] == (stamp, delay):
                self.maxima.popleft()
        if not self.count:
            self.total = 0.0

    def observe(self, now, delay, packets=1):
        self._expire(now)
        if packets <= 0:
            return
        delay = max(0.0, delay)
        self.samples.append((now, delay, packets))
        self.total += delay*packets
        self.count += packets
        while self.minima and self.minima[-1][1] >= delay:
            self.minima.pop()
        self.minima.append((now, delay))
        while self.maxima and self.maxima[-1][1] <= delay:
            self.maxima.pop()
        self.maxima.append((now, delay))

    def snapshot(self, now):
        self._expire(now)
        if not self.count:
            return None, None, None
        return 1000*self.total/self.count, 1000*self.minima[0][1], 1000*self.maxima[0][1]


class EventRate:
    """Events in the last `window` seconds, reported per second."""
    def __init__(self, window=1.0):
        self.window = window
        self.events = deque()
        self.count = 0
        self.total = 0

    def add(self, now, count=1):
        if count > 0:
            self.events.append((now, count))
            self.count += count
            self.total += count

    def rate(self, now):
        while self.events and self.events[0][0] <= now-self.window:
            self.count -= self.events.popleft()[1]
        return self.count/self.window


class MessageRates:
    """Per-message received and forwarded rates for one direction."""
    def __init__(self, names):
        self.names = dict(names)
        self.received = {msgid: EventRate() for msgid in self.names}
        self.forwarded = {msgid: EventRate() for msgid in self.names}

    def receive(self, now, msgids):
        for msgid in msgids:
            if msgid in self.received:
                self.received[msgid].add(now)

    def forward(self, now, msgids):
        for msgid in msgids:
            if msgid in self.forwarded:
                self.forwarded[msgid].add(now)

    def snapshot(self, now):
        return {name: dict(received_hz=self.received[msgid].rate(now),
                           forwarded_hz=self.forwarded[msgid].rate(now),
                           received=self.received[msgid].total,
                           forwarded=self.forwarded[msgid].total)
                for msgid, name in self.names.items()}


class PacingMonitor:
    """Real-time factor from HIL_SENSOR time_usec against local arrival time.

    RTF = (delta time_usec / 1e6) / delta monotonic arrival time, over the
    last `window` seconds (live value) and `long_window` seconds. Samples
    come from one source and one run: a different source or a timestamp that
    goes backwards starts a new generation and clears the windows. A repeated
    timestamp is counted but is not progress. `lag_ms` is the arrival time
    elapsed in this generation minus the simulated time elapsed.
    """
    def __init__(self, window=1.0, long_window=10.0, stale_after=1.0, min_span=0.5):
        self.window = window
        self.long_window = long_window
        self.stale_after = stale_after
        self.min_span = min_span
        self.short = deque()
        self.long = deque()
        self.intervals = deque()
        self.generations = 0
        self.resets = dict(source=0, backwards=0)
        self.duplicates = 0
        self.source = None
        self.first = None
        self.last = None

    def observe(self, now, time_usec, source=None):
        if self.last is not None and source != self.source:
            self._restart('source')
        elif self.last is not None and time_usec < self.last[1]:
            self._restart('backwards')
        elif self.last is not None and time_usec == self.last[1]:
            self.duplicates += 1
            return
        if self.last is None:
            self.generations += 1
            self.source = source
            self.first = (now, time_usec)
        else:
            self.intervals.append((now, now-self.last[0]))
        self.last = (now, time_usec)
        self.short.append(self.last)
        self.long.append(self.last)
        self._expire(now)

    def _restart(self, reason):
        self.resets[reason] += 1
        self.short.clear()
        self.long.clear()
        self.intervals.clear()
        self.last = None
        self.first = None

    def _expire(self, now):
        for samples, window in ((self.short, self.window), (self.long, self.long_window),
                                (self.intervals, self.window)):
            while samples and samples[0][0] <= now-window:
                samples.popleft()

    def _rtf(self, samples, window):
        if len(samples) < 2 or samples[-1][0]-samples[0][0] < min(self.min_span, window/2):
            return None
        return (samples[-1][1]-samples[0][1])/1e6/(samples[-1][0]-samples[0][0])

    def snapshot(self, now):
        self._expire(now)
        result = dict(state='waiting', rtf=None, rtf_long=None, lag_ms=None,
                      gap_max_ms=None, gap_std_ms=None, generations=self.generations,
                      resets_source=self.resets['source'], resets_backwards=self.resets['backwards'],
                      duplicates=self.duplicates, last_age_s=None)
        if self.last is None:
            return result
        age = now-self.last[0]
        result['last_age_s'] = age
        result['lag_ms'] = 1000*((self.last[0]-self.first[0])-(self.last[1]-self.first[1])/1e6)
        if age > self.stale_after:
            result['state'] = 'stale'
            return result
        result['rtf'] = self._rtf(self.short, self.window)
        result['rtf_long'] = self._rtf(self.long, self.long_window)
        gaps = [gap for _, gap in self.intervals]
        if gaps:
            mean = sum(gaps)/len(gaps)
            result['gap_max_ms'] = 1000*max(gaps)
            result['gap_std_ms'] = 1000*math.sqrt(sum((g-mean)**2 for g in gaps)/len(gaps))
        result['state'] = 'ok' if result['rtf'] is not None else 'waiting'
        return result


class BacklogHint:
    """Flag a possible actuator backlog in the model's UDP receive queue.

    The model reads one datagram per step. HIL_SENSOR arrives once per step,
    so its rate is the model's consumption rate. The hint is raised when the
    forwarded ID93 rate exceeds it by more than max(min_excess_hz,
    min_excess_ratio * sensor rate) for `hold` seconds, or when ID93 keeps
    arriving while HIL_SENSOR is stale; it clears after `clear` seconds
    without that condition. It reports the rate difference only; it does not
    estimate queue depth.
    """
    def __init__(self, min_excess_hz=5.0, min_excess_ratio=0.02, hold=3.0, clear=2.0):
        self.min_excess_hz = min_excess_hz
        self.min_excess_ratio = min_excess_ratio
        self.hold = hold
        self.clear = clear
        self.since = None
        self.quiet_since = None
        self.active = False
        self.reason = None
        self.raised = 0

    def update(self, now, actuator_hz, sensor_hz, sensor_state):
        excess = actuator_hz-sensor_hz
        if sensor_state == 'stale' and actuator_hz > 0:
            condition, reason = True, 'ID93 arriving while HIL_SENSOR is stale'
        elif sensor_state == 'ok' and excess > max(self.min_excess_hz, self.min_excess_ratio*sensor_hz):
            condition, reason = True, f'ID93 {excess:+.1f} Hz above model step rate'
        else:
            condition, reason = False, None
        if condition:
            self.quiet_since = None
            self.since = now if self.since is None else self.since
            if not self.active and now-self.since >= self.hold:
                self.active = True
                self.raised += 1
            if self.active:
                self.reason = reason
        else:
            self.since = None
            if self.active:
                self.quiet_since = now if self.quiet_since is None else self.quiet_since
                if now-self.quiet_since >= self.clear:
                    self.active = False
                    self.reason = None
                    self.quiet_since = None
        return dict(backlog=self.active, backlog_reason=self.reason, backlog_raised=self.raised,
                    actuator_excess_hz=excess)


class WriteStats:
    """Serial write backpressure: incomplete first attempts, waits and failures."""
    def __init__(self):
        self.writes = 0
        self.incomplete = 0
        self.wait_total_s = 0.0
        self.wait_max_s = 0.0
        self.timeouts = 0
        self.errors = 0
        self.recent = deque()

    def observe(self, now, waited, incomplete):
        self.writes += 1
        if incomplete:
            self.incomplete += 1
            self.wait_total_s += waited
            self.wait_max_s = max(self.wait_max_s, waited)
            self.recent.append((now, waited))

    def snapshot(self, now):
        while self.recent and self.recent[0][0] <= now-1:
            self.recent.popleft()
        return dict(serial_writes=self.writes, write_incomplete=self.incomplete,
                    write_wait_total_ms=1000*self.wait_total_s, write_wait_max_ms=1000*self.wait_max_s,
                    write_wait_recent_max_ms=1000*max((w for _, w in self.recent), default=0.0),
                    write_failures=self.timeouts+self.errors, write_timeouts=self.timeouts,
                    write_errors=self.errors)
