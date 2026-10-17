#!/usr/bin/env python3
"""Step-response metrics of a stick-step scenario (ROADMAP batch 4g), shared by SITL and HITL.

  "$HOME/Library/Application Support/SkySurferHIL/venv/bin/python" analysis/response.py \
      --trace <run>/instance_0/trace.csv --scenario sitl/scenarios/stabilized_steps.json [--out metrics.json]

trace.csv columns (sitl/px4_external/src/sks_sim): t_s counted from the first plant step, attitude and body
rates from the plant truth, the sticks and the five controls. The step times of the scenario count from the
end of settle_s.

Per step (Stabilized):
  roll / pitch steps: the attitude setpoint is the roll / pitch stick in the trace times FW_MAN_R_MAX, and
  -stick * FW_MAN_P_MAX + FW_PSP_OFF (fw_att_control); the response is the roll / pitch angle.
  yaw steps: the yaw stick drives the rudder through the yaw-rate setpoint (MAN_YR_MAX); the response is the
  body yaw rate r, there is no attitude setpoint.
Metrics (angles in degrees, rates in deg/s):
  baseline = mean over the 1 s before the step, pre_slope_per_s = its linear trend (is the start stationary?);
  tail_mean = mean over the last 30 % of the step, tail_slope_per_s = its trend: a finite window, not a
  steady state; change = tail_mean - baseline;
  peak_change = largest |response - baseline| during the step (for yaw the main number: the rate peaks and
  then decays because of the directional stability);
  rise_time_s = 10 -> 90 % of change;
  settling_time_s = time after which the response stays within 5 % of |change| (min 0.2 deg or 0.6 deg/s)
  around tail_mean; settled = false (settling_time_s null) when it never does or the tail still drifts by
  more than that band;
  roll / pitch only: setpoint_before / setpoint_abs = absolute setpoints before and during the step,
  setpoint_change = their difference, change_error = change - setpoint_change (relative),
  abs_error = tail_mean - setpoint_abs (absolute), overshoot_pct = largest excursion past setpoint_abs in the
  step direction, in % of |setpoint_change| (0 when the response never crosses the setpoint).
Data quality: the time axis must be finite and strictly increasing; each window (and the step's stick over
baseline + step) needs finite samples, no gap above --max-gap and coverage of the whole window;
otherwise the step is valid = false with its problems listed, and the exit code is 2.

HITL (batch 4i): --hitl-log <flight log dir> instead of --trace converts <log>/host/wire.bin with
analysis/hitl_trace.py (step times measured from the sent sticks) and writes hitl_trace.csv and
hitl_scenario.json next to --out (required), then analyses those:
  python3 analysis/response.py --hitl-log <L> --scenario sitl/scenarios/stabilized_steps_hitl.json --out <dir>/metrics.json
"""
import argparse
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PARAMS = ROOT / 'deploy' / '00_native' / 'fc_params_20261013.params'


def read_param(path, name, default):
    for line in Path(path).read_text().splitlines():
        fields = line.strip().split('\t')
        if len(fields) == 5 and fields[2] == name:
            return float(fields[3])
    return default


def load_trace(path):
    rows = list(csv.DictReader(open(path)))
    return {k: np.array([float(r[k]) for r in rows]) for k in rows[0]}


def window_problems(t, y, lo, hi, max_gap, name):
    inside = (t >= lo) & (t < hi)
    ts, ys = t[inside], y[inside]
    if len(ts) < 3:
        return [f'{name}: {len(ts)} samples']
    problems = []
    if not np.isfinite(ys).all():
        problems.append(f'{name}: non-finite values')
    gaps = np.diff(np.concatenate(([lo], ts, [hi])))
    if gaps.max() > max_gap:
        problems.append(f'{name}: gap {gaps.max():.3f} s > {max_gap} s')
    return problems


def slope(t, y):
    return float(np.polyfit(t - t[0], y, 1)[0]) if len(t) >= 2 else math.nan


def step_metrics(t, y, start, end, max_gap, setpoint=None, band_min=0.2):
    """setpoint: (absolute setpoint before, during) for roll / pitch."""
    tail_start = start + 0.7 * (end - start)
    problems = (window_problems(t, y, start - 1.0, start, max_gap, 'baseline window')
                + window_problems(t, y, start, end, max_gap, 'step window')
                + window_problems(t, y, tail_start, end, max_gap, 'tail window'))
    metrics = {'valid': not problems, 'problems': problems}
    if problems:
        return metrics
    before = (t >= start - 1.0) & (t < start)
    during = (t >= start) & (t < end)
    td, yd = t[during] - start, y[during]
    tail = td >= tail_start - start
    baseline = float(y[before].mean())
    tail_mean = float(yd[tail].mean())
    change = tail_mean - baseline
    peak_index = int(np.argmax(np.abs(yd - baseline)))
    metrics.update({'baseline': baseline, 'pre_slope_per_s': slope(t[before], y[before]), 'tail_mean': tail_mean,
                    'tail_slope_per_s': slope(td[tail], yd[tail]), 'change': change,
                    'peak_change': float(yd[peak_index] - baseline), 'peak_time_s': float(td[peak_index])})
    if abs(change) > 1e-9:
        frac = (yd - baseline) / change
        t10 = td[np.argmax(frac >= 0.1)] if np.any(frac >= 0.1) else math.nan
        t90 = td[np.argmax(frac >= 0.9)] if np.any(frac >= 0.9) else math.nan
        metrics['rise_time_s'] = float(t90 - t10)
        band = max(0.05 * abs(change), band_min)
        outside = np.nonzero(np.abs(yd - tail_mean) > band)[0]
        drifting = abs(metrics['tail_slope_per_s']) * (end - tail_start) > band
        if len(outside) and outside[-1] == len(yd) - 1 or drifting:
            metrics.update(settled=False, settling_time_s=None)
        else:
            metrics.update(settled=True, settling_time_s=float(td[outside[-1] + 1]) if len(outside) else 0.0)
    if setpoint is not None:
        sp_before, sp_abs = setpoint
        change_sp = sp_abs - sp_before
        sign = 1.0 if change_sp >= 0 else -1.0
        past = sign * (yd - sp_abs)
        metrics.update({'setpoint_before': sp_before, 'setpoint_abs': sp_abs, 'setpoint_change': change_sp,
                        'change_error': change - change_sp, 'abs_error': tail_mean - sp_abs,
                        'overshoot_pct': float(max(0.0, past.max()) / abs(change_sp) * 100) if change_sp else None})
    return metrics


def analyse(trace, scenario, params, max_gap=0.05):
    t = trace['t_s']
    settle = scenario.get('settle_s', 0.0)
    r_max = read_param(params, 'FW_MAN_R_MAX', 45.0)
    p_max = read_param(params, 'FW_MAN_P_MAX', 30.0)
    psp_off = read_param(params, 'FW_PSP_OFF', 0.0)

    def stick(name, lo, hi):
        inside = (t >= lo) & (t < hi)
        return float(np.median(trace[name][inside])) if inside.any() else math.nan

    # The time axis itself: finite and strictly increasing, or no window can be trusted.
    time_problems = [] if np.isfinite(t).all() and (np.diff(t) > 0).all() else ['time: not finite or not strictly increasing']
    results = []
    for step in scenario.get('steps', []):
        start, end = settle + step['start_s'], settle + step['end_s']
        for axis in ('roll', 'pitch', 'yaw'):
            if not step.get(axis, 0.0):
                continue
            # The stick that defines the step (and the setpoints) must be complete over baseline + step.
            problems = time_problems + window_problems(t, trace['stick_' + axis], start - 1.0, end, max_gap,
                                                        'stick window')
            if problems:
                results.append({'axis': axis, 'stick': step[axis], 'start_s': start, 'end_s': end,
                                'valid': False, 'problems': problems})
                continue
            if axis == 'roll':
                sp = tuple(stick('stick_roll', lo, hi) * r_max for lo, hi in ((start - 1.0, start), (start, end)))
                m = step_metrics(t, np.degrees(trace['roll_rad']), start, end, max_gap, sp)
            elif axis == 'pitch':
                sp = tuple(-stick('stick_pitch', lo, hi) * p_max + psp_off for lo, hi in ((start - 1.0, start), (start, end)))
                m = step_metrics(t, np.degrees(trace['pitch_rad']), start, end, max_gap, sp)
            else:
                m = step_metrics(t, np.degrees(trace['r_rad_s']), start, end, max_gap, None, band_min=0.6)
            results.append({'axis': axis, 'stick': step[axis], 'start_s': start, 'end_s': end,
                            'response': 'yaw rate r [deg/s]' if axis == 'yaw' else f'{axis} angle [deg]', **m})
    return results


def no_nan(value):
    """JSON without NaN: a metric that could not be computed is null."""
    if isinstance(value, dict):
        return {k: no_nan(v) for k, v in value.items()}
    if isinstance(value, list):
        return [no_nan(v) for v in value]
    return None if isinstance(value, float) and not math.isfinite(value) else value


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--trace', type=Path)
    source.add_argument('--hitl-log', type=Path, help='HITL flight log directory (converted from host/wire.bin)')
    parser.add_argument('--scenario', type=Path, required=True)
    parser.add_argument('--params', type=Path, default=DEFAULT_PARAMS)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--max-gap', type=float, default=0.05, help='largest allowed sample gap in a window, s')
    args = parser.parse_args()
    scenario = json.loads(args.scenario.read_text())
    report = {}
    if args.hitl_log:
        if not args.out:
            parser.error('--hitl-log needs --out (the converted trace is written next to it)')
        sys.dont_write_bytecode = True  # no __pycache__ in the Dropbox project
        import hitl_trace
        trace, scenario, conversion = hitl_trace.convert(args.hitl_log, scenario)
        args.trace = args.out.parent / 'hitl_trace.csv'
        hitl_trace.write_csv(trace, args.trace)
        (args.out.parent / 'hitl_scenario.json').write_text(json.dumps(scenario, indent=2))
        report['hitl_conversion'] = conversion
    results = analyse(load_trace(args.trace), scenario, args.params, args.max_gap)
    text = json.dumps(no_nan({'trace': str(args.trace), 'scenario': str(args.scenario), **report, 'steps': results}),
                      indent=2, allow_nan=False)
    if args.out:
        args.out.write_text(text)
    print(text)
    return 0 if all(r['valid'] for r in results) else 2


if __name__ == '__main__':
    sys.exit(main())
