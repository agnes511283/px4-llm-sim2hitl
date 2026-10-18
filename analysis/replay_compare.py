"""Compare the controller outputs of a ULog with their replay (run_sitl.py --replay).

Outputs (fw_att_control, fw_rate_control, control_allocator) and the fields compared are in OUTPUTS. A
recomputed sample is paired with the logged one by timestamp_sample when the topic has it, otherwise by the
nearest timestamp after removing the replay offset (within PAIR_WINDOW_US; a FC log and its replay do not
share exact timestamps); the offset is the median of (replayed - logged) timestamp of
vehicle_angular_velocity paired by timestamp_sample.

Results are split by the logged PX4 mode (vehicle_status.nav_state at each sample). A mode is covered only
when it is in COVERED_MODES (its setpoint chain starts at the replayed inputs; in AUTO modes the attitude
setpoint comes from the position controllers, which the replay does not run) and every REQUIRED_INPUTS
topic has samples inside the mode's segments (REQUIRED_STATE: at or before the segment start). The report's
'modes' lists each mode's segments, missing inputs and covered flag; per output and mode, 'paired_fraction'
is the share of the logged samples that found a recomputed partner (unpaired samples are not compared). Per mode and field: paired samples, exact fraction, median / p99 /
max |difference| (a value NaN on one side only counts as infinite), and the samples above --tolerance with
their log times (s since the log start). No PASS/FAIL: the acceptance tolerance is agreed separately.

Input quality of the original log (what the replay could feed): per input topic the sample count, median
and largest interval, and the logger dropouts. A topic logged slower than the controllers run (e.g.
airspeed_validated at 200 ms in SDLOG_PROFILE 17) is held between samples by the replay.
"""
import numpy as np

OUTPUTS = {
    'vehicle_attitude_setpoint': ['q_d', 'thrust_body'],
    'vehicle_rates_setpoint': ['roll', 'pitch', 'yaw', 'thrust_body'],
    'vehicle_torque_setpoint': ['xyz'],
    'vehicle_thrust_setpoint': ['xyz'],
    'actuator_servos': ['control'],
    'actuator_motors': ['control'],
}
# vehicle_status.nav_state (PX4 v1.17): modes whose setpoint chain starts at the replayed inputs.
MODE_NAMES = {0: 'manual', 1: 'altctl', 2: 'posctl', 3: 'auto_mission', 4: 'auto_loiter', 5: 'auto_rtl',
              10: 'acro', 12: 'descend', 13: 'termination', 14: 'offboard', 15: 'stabilized', 17: 'auto_takeoff',
              18: 'auto_land'}
COVERED_MODES = {0, 10, 15}
# Upstream inputs a covered mode needs logged inside its own time segment; a segment without one of them is
# reported covered=false ('missing_inputs'): the replay then held an old value or never had one.
REQUIRED_INPUTS = ['vehicle_attitude', 'vehicle_angular_velocity', 'manual_control_setpoint', 'airspeed_validated']
# Published on change or at about 2 Hz: needed at or before the segment start.
REQUIRED_STATE = ['vehicle_control_mode', 'vehicle_status']
PAIR_WINDOW_US = 1000


def _pairs(a, b, offset):
    if 'timestamp_sample' in a.dtype.names:
        _, ia, ib = np.intersect1d(a['timestamp_sample'], b['timestamp_sample'], return_indices=True)
        return ia, ib
    ta = a['timestamp'].astype(np.int64)
    tb = b['timestamp'].astype(np.int64) - offset
    j = np.clip(np.searchsorted(tb, ta), 1, len(tb) - 1)
    nearest = np.where(np.abs(tb[j - 1] - ta) <= np.abs(tb[j] - ta), j - 1, j)
    ok = np.abs(tb[nearest] - ta) <= PAIR_WINDOW_US
    return np.nonzero(ok)[0], nearest[ok]


def _stats(d, t, tolerance):
    over = np.nonzero(d > tolerance)[0]
    return {'paired': int(len(d)),
            'exact_fraction': float((d == 0).mean()),
            'median': float(np.percentile(d, 50, method='higher')),
            'p99': float(np.percentile(d, 99, method='higher')),
            'max': float(d.max()),
            'over_tolerance': int(len(over)),
            'over_tolerance_at_s': [round(float(v), 3) for v in t[over][:20]]}


def jsonable(value):
    """Standard JSON: non-finite floats (an unmatched NaN/Inf difference is infinite) become strings."""
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, float) and not np.isfinite(value):
        return str(value).replace('inf', 'Infinity').replace('nan', 'NaN')
    return value


def compare(original, replayed, tolerance=1e-3, inputs=()):
    """original, replayed: analysis.ulog.ULog. Returns a JSON-able report."""
    av = original.topics[('vehicle_angular_velocity', 0)]
    bv = replayed.topics[('vehicle_angular_velocity', 0)]
    _, ia, ib = np.intersect1d(av['timestamp_sample'], bv['timestamp_sample'], return_indices=True)
    offset = int(np.median(bv['timestamp'][ib].astype(np.int64) - av['timestamp'][ia].astype(np.int64)))
    status = original.topics.get(('vehicle_status', 0))
    report = {'identity': {k: {'original': original.info.get(k), 'replayed': replayed.info.get(k)}
                           for k in ('ver_hw', 'ver_sw', 'sys_name')},
              'replay_offset_us': offset, 'tolerance': tolerance, 'covered_modes': sorted(MODE_NAMES[m] for m in COVERED_MODES),
              'outputs': {}, 'inputs': {},
              'dropouts': {'count': len(original.dropouts), 'total_ms': int(sum(d for _, d in original.dropouts))},
              'modes': {}}
    end_us = max(int(v['timestamp'][-1]) for v in original.topics.values() if len(v))
    if status is not None and len(status):
        st = status['timestamp'].astype(np.int64)
        nav = status['nav_state'].astype(int)

        def mode_at(stamps):
            return nav[np.clip(np.searchsorted(st, stamps, side='right') - 1, 0, len(nav) - 1)]

        change = [0] + [i for i in range(1, len(nav)) if nav[i] != nav[i - 1]]
        segments = [(int(nav[i]), int(st[i]), int(st[change[k + 1]]) if k + 1 < len(change) else end_us)
                    for k, i in enumerate(change)]
    else:
        def mode_at(stamps):
            return np.full(len(stamps), -1)

        segments = [(-1, original.start_us, end_us)]
    for mode, lo, hi in segments:
        label = MODE_NAMES.get(mode, str(mode))
        info = report['modes'].setdefault(label, {'segments_s': [], 'missing_inputs': []})
        info['segments_s'].append([round((lo - original.start_us) * 1e-6, 3), round((hi - original.start_us) * 1e-6, 3)])
        for topic in REQUIRED_INPUTS + REQUIRED_STATE:
            log = original.topics.get((topic, 0))
            stamps = log['timestamp'].astype(np.int64) if log is not None else np.array([], dtype=np.int64)
            present = ((stamps >= lo) & (stamps < hi)).any() if topic in REQUIRED_INPUTS else (stamps < hi).any()
            if not present and topic not in info['missing_inputs']:
                info['missing_inputs'].append(topic)
    for label, info in report['modes'].items():
        mode = next((m for m, n in MODE_NAMES.items() if n == label), None)
        info['covered'] = mode in COVERED_MODES and not info['missing_inputs']
    for topic, fields in OUTPUTS.items():
        key = (topic, 0)
        if key not in original.topics or key not in replayed.topics:
            report['outputs'][topic] = {'missing': [n for n, log in (('original', original), ('replayed', replayed))
                                                    if key not in log.topics]}
            continue
        a, b = original.topics[key], replayed.topics[key]
        ia, ib = _pairs(a, b, offset)
        stamps = a['timestamp'][ia].astype(np.int64)
        t = (stamps - original.start_us) * 1e-6
        modes = mode_at(a['timestamp'][ia].astype(np.int64))
        logged_modes = mode_at(a['timestamp'].astype(np.int64))
        result = {'logged': int(len(a)), 'recomputed': int(len(b)), 'paired': int(len(ia)), 'modes': {}}
        for name in fields:
            x = np.asarray(a[name][ia], dtype=float).reshape(len(ia), -1)
            y = np.asarray(b[name][ib], dtype=float).reshape(len(ib), -1)
            used = ~(np.isnan(x).all(0) & np.isnan(y).all(0))  # unused array slots: NaN in both, every sample
            x, y = x[:, used], y[:, used]
            d = np.where(np.isnan(x) & np.isnan(y), 0.0, np.abs(x - y))
            d = np.where(np.isnan(d), np.inf, d).max(1) if d.size else np.zeros(len(ia))
            for mode in np.unique(modes):
                m = modes == mode
                label = MODE_NAMES.get(int(mode), str(int(mode)))
                entry = result['modes'].setdefault(label, {
                    'covered': report['modes'].get(label, {}).get('covered', False),
                    'paired_fraction': float(m.sum() / max(1, (logged_modes == mode).sum())), 'fields': {}})
                entry['fields'][name] = _stats(d[m], t[m], tolerance)
        report['outputs'][topic] = result
    for topic in inputs:
        key = (topic, 0)
        if key in original.topics and len(original.topics[key]) > 1:
            dt = np.diff(original.topics[key]['timestamp'].astype(np.int64)) / 1000.0
            report['inputs'][topic] = {'samples': int(len(dt) + 1), 'median_ms': float(np.median(dt)),
                                       'max_ms': float(dt.max())}
        else:
            report['inputs'][topic] = {'samples': 0 if key not in original.topics else 1}
    return report
