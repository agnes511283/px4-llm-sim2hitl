#!/usr/bin/env python3
"""Record reference trajectories from the active model release for the C plant port.

Loads the active release's model library through the existing ctypes ABI (hitl/host/abi.py),
runs fixed cases step by step and stores every step's 58 raw fields. Only the model ABI is called:
no serial port, no PX4, no MATLAB.

  <HIL venv python> -B plant/reference/record_reference.py

Outputs plant/reference/data/reference.npz and manifest.json (source identity, cases, sample counts).
"""
import argparse
import ctypes as C
import datetime
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / 'hitl'
sys.path.insert(0, str(RUNTIME))
from host.abi import Initial, Input, Model, Output, header  # noqa: E402
from host.release import read_release  # noqa: E402

DT = 0.004
LAT0, LON0 = 22.910275834988674, 120.31096929726908
THETA_GROUND = 0.8633
# controls[] index: 0 left aileron, 1 right aileron, 2 elevator, 3 rudder, 4 throttle
AIL_L, AIL_R, ELE, RUD, THR = range(5)


def tas_body(tas, alpha_deg, beta_deg=0.0):
    a, b = math.radians(alpha_deg), math.radians(beta_deg)
    return [tas * math.cos(a) * math.cos(b), tas * math.sin(b), tas * math.sin(a) * math.cos(b)]


def doublet(channel, amplitude, start=0.3, width=0.3):
    return [(start, start + width, channel, amplitude), (start + width, start + 2 * width, channel, -amplitude)]


AIR = dict(height=100.0, velocity=[20.0, 0.0, 0.0], euler=[0.0, THETA_GROUND, 0.0])
CASES = [
    dict(name='ground_idle', height=0.0, velocity=[0, 0, 0], euler=[0, THETA_GROUND, 0], duration=5.0, pulses=[],
         purpose='ground contact settling with zero command'),
    dict(name='ground_throttle', height=0.0, velocity=[0, 0, 0], euler=[0, THETA_GROUND, 0], duration=6.0,
         pulses=[(0.5, 6.0, THR, 0.45)], purpose='ground roll: thrust lag, friction, possible lift-off'),
    dict(name='ground_lateral_slide', height=0.0, velocity=[3.0, 1.0, 0], euler=[0, THETA_GROUND, 0], duration=3.0,
         pulses=[], purpose='friction direction on a sliding aircraft'),
    dict(name='air_free', **AIR, duration=2.0, pulses=[], purpose='natural response, no command'),
    dict(name='air_elevator_doublet', **AIR, duration=2.0, pulses=doublet(ELE, 0.2), purpose='pitch axis'),
    dict(name='air_left_aileron_pulse', **AIR, duration=1.5, pulses=[(0.3, 0.5, AIL_L, 0.3)],
         purpose='left aileron channel alone: sign and scale'),
    dict(name='air_right_aileron_pulse', **AIR, duration=1.5, pulses=[(0.3, 0.5, AIL_R, 0.3)],
         purpose='right aileron channel alone: sign and scale'),
    dict(name='air_rudder_doublet', **AIR, duration=2.0, pulses=doublet(RUD, 0.3), purpose='yaw axis'),
    dict(name='air_throttle_step', **AIR, duration=2.0, pulses=[(0.3, 2.0, THR, 0.6)], purpose='thrust and its lag'),
    dict(name='air_slow_high_alpha', height=100.0, velocity=tas_body(15.0, 6.0), euler=[0, 6.0, 0], duration=2.0,
         pulses=[], purpose='low speed, higher alpha'),
    dict(name='air_fast', height=100.0, velocity=tas_body(28.0, 1.0), euler=[0, 1.0, 0], duration=2.0, pulses=[],
         purpose='high speed'),
    dict(name='air_sideslip', height=100.0, velocity=tas_body(20.0, 2.0, 5.0), euler=[0, 2.0, 0], duration=1.5,
         pulses=[], purpose='beta and lateral coefficients'),
    dict(name='air_banked_heading', height=200.0, velocity=[20.0, 0, 0], euler=[30.0, 5.0, 120.0], duration=2.0,
         pulses=[], purpose='Euler/quaternion/NED frame conventions'),
    dict(name='air_other_location', height=500.0, velocity=[20.0, 0, 0], euler=[0, THETA_GROUND, 45.0], duration=1.5,
         pulses=[], lat=45.0, lon=-120.0, purpose='latitude/longitude dependence (gravity, sensors, GPS)'),
]


def controls_for(case):
    n = int(round(case['duration'] / DT))
    u = np.zeros((n, 16))
    t = np.arange(n) * DT
    for start, end, channel, value in case['pulses']:
        u[(t >= start - 1e-9) & (t < end - 1e-9), channel] = value
    return t, u


def run_case(model, case):
    initial = header(Initial)
    initial.height_m = case['height']
    initial.body_velocity_m_s[:] = case['velocity']
    initial.euler_deg[:] = case['euler']
    initial.latitude_deg = case.get('lat', LAT0)
    initial.longitude_deg = case.get('lon', LON0)
    model.check(model.lib.hil_model_reset(C.byref(initial)))
    t, u = controls_for(case)
    inp, out = header(Input), header(Output)
    raw, fault = [], None
    for k in range(len(t)):
        inp.step_index = k
        inp.input_sequence = k
        inp.actuator_valid = inp.actuator_new = 1
        inp.fc_armed = 1
        inp.controls[:] = u[k]
        code = model.lib.hil_model_step(C.byref(inp), C.byref(out))
        if code:
            buffer = C.create_string_buffer(256)
            model.lib.hil_model_get_last_error(buffer, 256)
            fault = {'step': k, 'time_s': k * DT, 'code': code, 'message': buffer.value.decode()}
            break
        raw.append(list(out.raw_source))
    n = len(raw)
    return t[:n], u[:n], np.array(raw).reshape(n, 58), fault


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--out', type=Path, default=Path(__file__).resolve().parent / 'data')
    args = parser.parse_args()
    release, manifest = read_release(RUNTIME)
    library = release / manifest['library']
    model = Model(library)
    columns = json.loads((RUNTIME / 'poc' / 'source_columns.json').read_text())
    arrays, cases = {}, []
    for case in CASES:
        t, u, raw, fault = run_case(model, case)
        name = case['name']
        arrays[name + '__time_s'] = t
        arrays[name + '__controls'] = u
        arrays[name + '__raw'] = raw
        record = {k: v for k, v in case.items() if k != 'pulses'}
        record['pulses'] = [dict(start_s=a, end_s=b, channel=c, value=v) for a, b, c, v in case['pulses']]
        record.update(samples=len(t), requested_samples=int(round(case['duration'] / DT)), fault=fault,
                      finite=bool(np.isfinite(raw).all()))
        cases.append(record)
        print(f"{name}: {len(t)} samples{' (stopped: ' + fault['message'] + ')' if fault else ''}", flush=True)
    model.lib.hil_model_terminate()
    args.out.mkdir(parents=True, exist_ok=True)
    npz = args.out / 'reference.npz'
    np.savez_compressed(npz, **arrays)
    info = {
        'schema_version': 1,
        'generated_at': datetime.datetime.now().astimezone().isoformat(timespec='seconds'),
        'model_build_id': manifest['build_id'],
        'release_manifest_sha256': sha256(release / 'manifest.json'),
        'library_sha256': sha256(library),
        'script_sha256': sha256(__file__),
        'dt_s': DT,
        'output_phase': 't_k, sampled before the ode4 update (same as the HIL ABI)',
        'controls_index': ['aileron_left', 'aileron_right', 'elevator', 'rudder', 'throttle', 'unused 5..15'],
        'raw_columns': columns[1:],
        'raw_note': 'Source units per docs/MODEL_INTERFACE.md section 6 (mag gauss, pressure hPa, GPS e7/mm/cm/s).',
        'npz_keys': '<case>__time_s, <case>__controls (N x 16), <case>__raw (N x 58)',
        'reference_npz_sha256': sha256(npz),
        'cases': cases,
    }
    (args.out / 'manifest.json').write_text(json.dumps(info, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'wrote {npz} and manifest.json for {manifest["build_id"]}')


if __name__ == '__main__':
    main()
