#!/usr/bin/env python3
"""Judge one OFFBOARD run of the sks_template example from its ULog (SITL and HITL alike).

  <SkySurfer venv python> -B analysis/template_check.py <flight.ulg> [--out metrics.json]

From entering OFFBOARD (vehicle_status.nav_state): the course should turn by COURSE_STEP after COURSE_AT and the
altitude rise by ALTITUDE_STEP after ALTITUDE_AT (modules/src/sks_template). Each step is measured from the steady
value in the second before it (the altitude from the TECS altitude setpoint then, the module's own target), and
the bank from the first step on, so the mode flown before OFFBOARD (in HITL a
banked loiter) does not count. Course = atan2(vy, vx) and
altitude = -z + ref_alt of vehicle_local_position (truth in SITL, the FC's EKF in HITL). Reported per step:
the change at the end of its window, rise time 10->90 %, overshoot, settling time into a 5 % band; plus the
largest bank and the airspeed range while in OFFBOARD. The pass limits below are the example's own (written in
modules/src/sks_template/README.md); a new module writes its own.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ulog  # noqa: E402

OFFBOARD = 14  # vehicle_status NAVIGATION_STATE_OFFBOARD
COURSE_STEP, COURSE_AT = 30.0, 15.0         # deg, s after entering OFFBOARD
ALTITUDE_STEP, ALTITUDE_AT = 10.0, 35.0     # m, s
LIMITS = {'course_change_error_deg': 3.0, 'altitude_change_error_m': 1.5, 'bank_max_deg': 25.0}


def step_metrics(t, y, start, end, size):
    """Response of y (already relative to its value at start) to a step of size at t = start, up to end."""
    w = (t >= start) & (t < end)
    tt, yy = t[w] - start, y[w]
    if len(tt) < 10:
        return {'valid': False}
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
              'course': step_metrics(t, course - before(course, COURSE_AT), COURSE_AT, ALTITUDE_AT, COURSE_STEP),
              'altitude': step_metrics(t, altitude - altitude_base, ALTITUDE_AT, duration, ALTITUDE_STEP),
              'altitude_base_m': altitude_base}
    att = log.topics[('vehicle_attitude', 0)]
    ta = (att['timestamp'].astype(np.int64) - entered) * 1e-6
    q = att['q'][(ta >= COURSE_AT) & (ta <= duration)]  # bank from the module's first step on
    roll = np.degrees(np.arctan2(2 * (q[:, 0] * q[:, 1] + q[:, 2] * q[:, 3]), 1 - 2 * (q[:, 1] ** 2 + q[:, 2] ** 2)))
    report['bank_max_deg'] = float(np.max(np.abs(roll))) if len(roll) else None
    air = log.topics.get(('airspeed_validated', 0))
    if air is not None:
        tv = (air['timestamp'].astype(np.int64) - entered) * 1e-6
        eas = air['calibrated_airspeed_m_s'][(tv >= 0) & (tv <= duration)]
        report['airspeed_m_s'] = [float(np.min(eas)), float(np.max(eas))] if len(eas) else None
    problems = []
    if duration < ALTITUDE_AT + 20:
        problems.append(f'OFFBOARD only {duration:.1f} s (needs {ALTITUDE_AT + 20:.0f} s)')
    for name, limit in [('course', LIMITS['course_change_error_deg']), ('altitude', LIMITS['altitude_change_error_m'])]:
        m = report[name]
        if not m['valid'] or abs(m['error']) > limit or m['settling_time_s'] is None:
            problems.append(f'{name} step: {m}')
    if report['bank_max_deg'] is None or report['bank_max_deg'] > LIMITS['bank_max_deg']:
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
    text = json.dumps(report, indent=2, default=lambda x: None if isinstance(x, float) and math.isnan(x) else x)
    if args.out:
        args.out.write_text(text)
    print(text)
    return 0 if report['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
