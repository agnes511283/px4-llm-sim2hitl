"""HITL wire.bin -> trace.csv in the SITL column layout (ROADMAP batch 4i); used by response.py --hitl-log.

The runtime logs no plant truth, so the trace comes from the MAVLink traffic in <log>/host/wire.bin
(docs/ARCHITECTURE.md, HITL logs; all channel stamps are native ns):
  channel 1 (FC RX): ATTITUDE (EKF2 attitude, filtered body rates; 100 Hz), LOCAL_POSITION_NED (height = -z),
                     VFR_HUD (calibrated airspeed), HIL_ACTUATOR_CONTROLS (controls[0..4]).
  channel 4 (written to the FC): MANUAL_CONTROL, the sticks actually sent.
Rows are on the ATTITUDE samples; sticks and controls are the latest value, airspeed and height interpolated
(NaN before the first or after the last sample of a source, never back-filled); the report gives each
source's largest gap after the sequence start.
Columns as sitl/px4_external/src/sks_sim trace.csv, except: attitude and rates are PX4's estimate (SITL:
plant truth), tas_m_s holds CAS (about 0.5 % below TAS at 100 m) and height_m is EKF2 height over its origin.

The step times are measured, not assumed: the pilot's command sequence advances on 50 Hz ticks, so each
action can run up to a tick long. The sequence start is the first MANUAL_CONTROL equal to the scenario's
base sticks; each step is the first sample equal to base + step and ends on the return to base. The sent
sticks must equal the scenario to the 1/1000 MAVLink resolution, otherwise the conversion fails. The
returned scenario carries the measured times (t_s = 0 at the sequence start, settle_s unchanged).
"""
import struct
from pathlib import Path

import numpy as np

# MAVLink message id -> (CRC extra, unpack format of the full payload, minimum payload length)
MESSAGES = {
    30: (39, '<Iffffff'),  # ATTITUDE
    32: (185, '<Iffffff'),  # LOCAL_POSITION_NED
    69: (243, '<hhhh'),  # MANUAL_CONTROL: x, y, z, r first on the wire
    74: (20, '<ffffhH'),  # VFR_HUD
    93: (47, '<QQ16fB'),  # HIL_ACTUATOR_CONTROLS
}
COLUMNS = ['t_s', 'roll_rad', 'pitch_rad', 'yaw_rad', 'p_rad_s', 'q_rad_s', 'r_rad_s', 'tas_m_s', 'height_m',
           'stick_roll', 'stick_pitch', 'stick_yaw', 'stick_throttle', 'ail_l', 'ail_r', 'elev', 'rud', 'thr']


def crc_x25(data, crc=0xFFFF):
    for byte in data:
        tmp = byte ^ (crc & 0xFF)
        tmp = (tmp ^ (tmp << 4)) & 0xFF
        crc = ((crc >> 8) ^ (tmp << 8) ^ (tmp << 3) ^ (tmp >> 4)) & 0xFFFF
    return crc


def read_records(path):
    data = Path(path).read_bytes()
    i = 0
    while i + 13 <= len(data):
        stamp, channel, n = struct.unpack_from('<QBI', data, i)
        yield stamp, channel, data[i + 13:i + 13 + n]
        i += 13 + n


def parse_stream(records):
    """CRC-checked MAVLink v1/v2 packets of one byte stream (packets may span records) -> (stamp, id, fields)."""
    buf, stamps, out = bytearray(), [], []
    for stamp, chunk in records:
        buf += chunk
        stamps += [stamp] * len(chunk)
        j = 0
        while True:
            while j < len(buf) and buf[j] not in (0xFD, 0xFE):
                j += 1
            if j >= len(buf):
                break
            v2 = buf[j] == 0xFD
            header = 10 if v2 else 6
            if j + header > len(buf):
                break
            length = buf[j + 1]
            msgid = (buf[j + 7] | buf[j + 8] << 8 | buf[j + 9] << 16) if v2 else buf[j + 5]
            total = header + length + 2 + (13 if v2 and buf[j + 2] & 1 else 0)
            if j + total > len(buf):
                break
            if msgid in MESSAGES:
                extra, fmt = MESSAGES[msgid]
                crc = crc_x25(bytes(buf[j + 1:j + header + length]) + bytes([extra]))
                if crc != struct.unpack_from('<H', buf, j + header + length)[0]:
                    j += 1
                    continue
                payload = bytes(buf[j + header:j + header + length]).ljust(struct.calcsize(fmt), b'\0')
                out.append((stamps[j + total - 1], msgid, struct.unpack_from(fmt, payload)))
            j += total
        del buf[:j]
        del stamps[:j]
    return out


def counts(sticks):
    """manual_control_setpoint units -> MANUAL_CONTROL x, y, z, r counts (PX4 mavlink_receiver)."""
    values = (sticks['pitch'] * 1000, sticks['roll'] * 1000, (sticks['throttle'] + 1) * 500, sticks['yaw'] * 1000)
    result = tuple(round(v) for v in values)
    if any(abs(r - v) > 1e-6 for r, v in zip(result, values)):
        raise ValueError(f'scenario sticks {sticks} are not on the 1/1000 MANUAL_CONTROL grid')
    return result


def convert(log_dir, scenario):
    """-> (trace dict of numpy arrays, scenario with measured step times, report)."""
    log_dir = Path(log_dir)
    wire = log_dir / 'host' / 'wire.bin' if (log_dir / 'host' / 'wire.bin').is_file() else log_dir / 'wire.bin'
    records = list(read_records(wire))
    rx = parse_stream((s, d) for s, c, d in records if c == 1)
    tx = parse_stream((s, d) for s, c, d in records if c == 4)
    if 'base' in scenario or 'base_sticks' not in scenario:
        raise ValueError('a HITL scenario gives absolute base_sticks and no "base" offsets (as stabilized_steps.py)')
    base = {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0, 'throttle': -1.0, **scenario['base_sticks']}
    base_counts = counts(base)

    sent = [(s, f[:4]) for s, m, f in tx if m == 69]
    starts = [k for k, (s, c) in enumerate(sent) if c == base_counts]
    if not starts:
        raise ValueError(f'no MANUAL_CONTROL equal to the base sticks {base_counts} in {wire}')
    k = starts[0]
    t0 = sent[k][0]
    settle = scenario.get('settle_s', 0.0)
    steps, offsets = [], []
    for step in scenario.get('steps', []):
        target = counts({a: base[a] + step.get(a, 0.0) for a in base})
        while k < len(sent) and sent[k][1] != target:
            if sent[k][1] != base_counts:
                raise ValueError(f'unexpected sticks {sent[k][1]} at {(sent[k][0] - t0) * 1e-9:.2f} s before step {step}')
            k += 1
        if k >= len(sent):
            raise ValueError(f'step {step} not found in the sent sticks')
        start = (sent[k][0] - t0) * 1e-9
        while k < len(sent) and sent[k][1] == target:
            k += 1
        if k >= len(sent) or sent[k][1] != base_counts:
            raise ValueError(f'step {step} does not return to the base sticks')
        end = (sent[k][0] - t0) * 1e-9
        steps.append({**step, 'start_s': start - settle, 'end_s': end - settle})
        offsets.append({'start_s': start - settle - step['start_s'], 'end_s': end - settle - step['end_s']})

    def series(msgid, pick):
        rows = [(s, pick(f)) for s, m, f in rx if m == msgid]
        if not rows:
            raise ValueError(f'no MAVLink message {msgid} from the FC in {wire}')
        return (np.array([(s - t0) * 1e-9 for s, _ in rows]), np.array([v for _, v in rows], dtype=float))

    t, att = series(30, lambda f: f[1:7])
    tl, height = series(32, lambda f: -f[3])
    tv, cas = series(74, lambda f: f[0])
    ta, controls = series(93, lambda f: f[2:7])
    ts = np.array([(s - t0) * 1e-9 for s, _ in sent])
    stick_counts = np.array([c for _, c in sent], dtype=float)

    def latest(tx_, values):
        # NaN before the first sample: no back-filling with a later value.
        index = np.searchsorted(tx_, t, side='right') - 1
        held = values[np.clip(index, 0, len(values) - 1)].astype(float)
        held[index < 0] = np.nan
        return held

    def between(tx_, values):
        # Linear between samples, NaN outside them (no end-point extension).
        return np.interp(t, tx_, values, left=np.nan, right=np.nan)

    sticks = latest(ts, stick_counts)
    ctrl = latest(ta, controls)
    trace = {'t_s': t, 'roll_rad': att[:, 0], 'pitch_rad': att[:, 1], 'yaw_rad': att[:, 2], 'p_rad_s': att[:, 3],
             'q_rad_s': att[:, 4], 'r_rad_s': att[:, 5], 'tas_m_s': between(tv, cas),
             'height_m': between(tl, height), 'stick_roll': sticks[:, 1] / 1000, 'stick_pitch': sticks[:, 0] / 1000,
             'stick_yaw': sticks[:, 3] / 1000, 'stick_throttle': sticks[:, 2] / 500 - 1,
             'ail_l': ctrl[:, 0], 'ail_r': ctrl[:, 1], 'elev': ctrl[:, 2], 'rud': ctrl[:, 3], 'thr': ctrl[:, 4]}
    keep = t >= 0
    trace = {name: values[keep] for name, values in trace.items()}
    measured = {**scenario, 'steps': steps, 'measured_from': str(wire)}
    # Gaps over the sequence only (start to the last step's end + the scenario's remaining duration); the log
    # goes on through model stop and recover, where the FC streams pause.
    span = settle + max([s['end_s'] for s in steps] + [scenario.get('duration_s', 0.0)])

    def max_gap(times):
        times = times[(times >= 0) & (times <= span)]
        return float(np.diff(times).max()) if len(times) > 1 else None

    # Rows are on ATTITUDE; the other sources are held or interpolated, so their own gaps are reported too.
    # response.py rejects windows with gaps or non-finite values (--max-gap).
    report = {'wire': str(wire), 'sequence_start_ns': t0, 'step_offsets_s': offsets,
              'attitude_samples': int(keep.sum()), 'sticks_sent': len(sent),
              'max_gap_s': {'ATTITUDE': max_gap(t), 'LOCAL_POSITION_NED': max_gap(tl), 'VFR_HUD': max_gap(tv),
                            'HIL_ACTUATOR_CONTROLS': max_gap(ta), 'MANUAL_CONTROL': max_gap(ts)}}
    return trace, measured, report


def write_csv(trace, path):
    with open(path, 'w') as stream:
        stream.write(','.join(COLUMNS) + '\n')
        for row in zip(*(trace[c] for c in COLUMNS)):
            stream.write(f'{row[0]:.4f},' + ','.join(f'{v:.7g}' for v in row[1:]) + '\n')
