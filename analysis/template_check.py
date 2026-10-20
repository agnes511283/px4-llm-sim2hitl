#!/usr/bin/env python3
"""Judge one OFFBOARD run of the guidance_template example from its ULog (SITL and HITL alike).

  <venv python> -B analysis/template_check.py <flight.ulg> [--out metrics.json]

From entering OFFBOARD (vehicle_status.nav_state): the course should turn by COURSE_STEP after COURSE_AT and the
altitude rise by ALTITUDE_STEP after ALTITUDE_AT (modules/src/guidance_template). Each step is measured from the steady
value in the second before it (the altitude from the TECS altitude setpoint then, the module's own target), and
the bank from the first step on, so the mode flown before OFFBOARD (in HITL a
banked loiter) does not count. Course = atan2(vy, vx) and
altitude = -z + ref_alt of vehicle_local_position (truth in SITL, the FC's EKF in HITL). Reported per step:
the change at the end of its window, rise time 10->90 %, overshoot, settling time into a 5 % band; plus the
largest bank and the airspeed range while in OFFBOARD. The pass limits below are the example's own (written in
modules/src/guidance_template/README.md); a new module writes its own.
Data that cannot be judged fails with its reason, so bad data never passes: a time axis that does not strictly
increase, and in each step window (from the second before the step, which gives its base value) and in the bank
window too few samples, a non-finite value, a gap above MAX_GAP_S (also at the window edges; the window checks of
analysis/response.py) or vehicle_local_position flagging the estimate invalid (v_xy_valid for the course, z_valid
for the altitude). The JSON report has null where a number could not be computed.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import response  # noqa: E402  window_problems, no_nan
import ulog  # noqa: E402

OFFBOARD = 14  # vehicle_status NAVIGATION_STATE_OFFBOARD
COURSE_STEP, COURSE_AT = 30.0, 15.0         # deg, s after entering OFFBOARD
ALTITUDE_STEP, ALTITUDE_AT = 10.0, 35.0     # m, s
LIMITS = {'course_change_error_deg': 3.0, 'altitude_change_error_m': 1.5, 'bank_max_deg': 25.0}
MAX_GAP_S = 0.5  # largest sample gap in a judged window (HITL logs vehicle_local_position at 10 Hz)


def step_metrics(t, y, start, end, size, valid):
    """Response of y (already relative to its value at start) to a step of size at t = start, up to end.
    valid: the estimate's validity flag per sample. Data that cannot be judged: valid = false with the problems."""
    lo = start - 1.0  # the second before the step gives the base value
    problems = response.window_problems(t, y, lo, end, MAX_GAP_S, 'window')
    if not valid[(t >= lo) & (t < end)].all():
        problems.append('window: estimate flagged invalid')
    w = (t >= start) & (t < end)
    tt, yy = t[w] - start, y[w]
    if len(tt) < 10:
        problems.append(f'{len(tt)} samples after the step')
    if problems:
        return {'valid': False, 'problems': problems}
    tail = yy[tt >= 0.8 * (end - start)]
    change = float(np.mean(tail))
    sign = 1.0 if size >= 0 else -1.0
    frac = sign * yy / size
    rise = None
    above10, above90 = np.nonzero(frac >= 0.1)[0], np.nonzero(frac >= 0.9)[0]
    if len(above10) and len(above90):
        rise = float(tt[above90[0]] - tt[above10[0]])
    outside = np.nonzero(np.abs(yy - size) > 0.05 * abs(size))[0]
    settle = float(tt[outside[-1] + 1]) if len(outside) and outside[-1] + 1 < len(tt) else (0.0 if not len(outside) else None)
    return {'valid': True, 'change': change, 'error': change - size, 'rise_time_s': rise,
            'overshoot_pct': max(0.0, float(np.max(frac)) - 1.0) * 100.0, 'settling_time_s': settle}


def check(path):
    log = ulog.read(path)
    status, pos = log.topics[('vehicle_status', 0)], log.topics[('vehicle_local_position', 0)]
    on = np.nonzero(status['nav_state'] == OFFBOARD)[0]
    if not len(on):
        return {'verdict': 'FAIL', 'problems': ['never in OFFBOARD'], 'log': str(path)}
    entered = int(status['timestamp'][on[0]])
    after = status['timestamp'][on[0]:]
    left = np.nonzero(status['nav_state'][on[0]:] != OFFBOARD)[0]
    end = int(after[left[0]]) if len(left) else int(pos['timestamp'][-1])
    t = (pos['timestamp'].astype(np.int64) - entered) * 1e-6
    course = np.degrees(np.unwrap(np.arctan2(pos['vy'], pos['vx'])))
    altitude = -pos['z'] + pos['ref_alt']
    duration = (end - entered) * 1e-6

    def before(y, at):
        # The steady value in the second before a step: the entry from another mode (a banked loiter) has
        # settled by then, so only the module's own response is judged.
        window = (t >= at - 1.0) & (t < at)
        return float(np.mean(y[window])) if window.any() else float('nan')

    # Altitude from the module's own target before the step (TECS altitude setpoint): TECS may hold a small
    # offset from it, which is not the module's response.
    tecs = log.topics.get(('tecs_status', 0))
    altitude_base = before(altitude, ALTITUDE_AT)
    if tecs is not None:
        ts = (tecs['timestamp'].astype(np.int64) - entered) * 1e-6
        window = (ts >= ALTITUDE_AT - 1.0) & (ts < ALTITUDE_AT)
        if window.any():
            altitude_base = float(np.mean(tecs['altitude_sp'][window]))
    report = {'log': str(path), 'offboard_seconds': duration,
              'course': step_metrics(t, course - before(course, COURSE_AT), COURSE_AT, ALTITUDE_AT, COURSE_STEP,
                                     pos['v_xy_valid'].astype(bool)),
              'altitude': step_metrics(t, altitude - altitude_base, ALTITUDE_AT, duration, ALTITUDE_STEP,
                                       pos['z_valid'].astype(bool)),
              'altitude_base_m': altitude_base}
    att = log.topics[('vehicle_attitude', 0)]
    ta = (att['timestamp'].astype(np.int64) - entered) * 1e-6
    q = att['q']
    roll = np.degrees(np.arctan2(2 * (q[:, 0] * q[:, 1] + q[:, 2] * q[:, 3]), 1 - 2 * (q[:, 1] ** 2 + q[:, 2] ** 2)))
    bank = (ta >= COURSE_AT) & (ta <= duration)  # bank from the module's first step on
    bank_problems = response.window_problems(ta, roll, COURSE_AT, duration, MAX_GAP_S, 'bank window')
    report['bank_max_deg'] = None if bank_problems else float(np.max(np.abs(roll[bank])))
    air = log.topics.get(('airspeed_validated', 0))
    if air is not None:
        tv = (air['timestamp'].astype(np.int64) - entered) * 1e-6
        eas = air['calibrated_airspeed_m_s'][(tv >= 0) & (tv <= duration)]
        report['airspeed_m_s'] = [float(np.min(eas)), float(np.max(eas))] if len(eas) else None
    problems = []
    if not np.all(np.diff(pos['timestamp'].astype(np.int64)) > 0):
        problems.append('vehicle_local_position: the time axis does not strictly increase')
    if duration < ALTITUDE_AT + 20:
        problems.append(f'OFFBOARD only {duration:.1f} s (needs {ALTITUDE_AT + 20:.0f} s)')
    for name, limit in [('course', LIMITS['course_change_error_deg']), ('altitude', LIMITS['altitude_change_error_m'])]:
        m = report[name]
        if not m['valid']:
            problems.append(f'{name} step: data cannot be judged ({"; ".join(m["problems"])})')
        elif abs(m['error']) > limit or m['settling_time_s'] is None:
            problems.append(f'{name} step: {m}')
    if bank_problems:
        problems.append(f'bank: data cannot be judged ({"; ".join(bank_problems)})')
    elif report['bank_max_deg'] > LIMITS['bank_max_deg']:
        problems.append(f'bank {report["bank_max_deg"]} deg')
    report['limits'] = LIMITS
    report['problems'] = problems
    report['verdict'] = 'FAIL' if problems else 'PASS'
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('ulog', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    report = check(args.ulog)
    text = json.dumps(response.no_nan(report), indent=2, allow_nan=False)
    if args.out:
        args.out.write_text(text)
    print(text)
    return 0 if report['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
