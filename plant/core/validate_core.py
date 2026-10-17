#!/usr/bin/env python3
"""Validate libskysurfer_core.dylib against the recorded plant reference and its own contracts.

  "$HOME/Library/Application Support/SkySurferHIL/venv/bin/python" plant/core/validate_core.py \
      --cache ~/Library/Caches/Codex/SkySurferPhaseB/core_<timestamp>

Checks (results in <cache>/results/core_validation.json, exit code 0 only when all PASS):
  reference   the 14 cases of plant/reference (same initial conditions and controls) against
              plant/reference/data/reference.npz: every Truth field the core also outputs; every
              case must run to the end with finite values
  instances   two instances stepped interleaved give bit-identical results to separate runs
              (bit equality compares the raw bytes, so +0.0 and -0.0 differ)
  copy        sks_core_copy mid-run, both copies continue bit-identically to an uninterrupted run
  reinit      re-initialising an instance reproduces the first run bit-identically
  state_eval  API >= 1.1: sks_core_get_state then sks_core_eval with the next controls gives the same
              snapshot and next state as sks_core_step, bit for bit; a different state written by
              sks_core_eval is the one the output and the integration use; xdot is finite; and xdot is the
              right derivative, checked against signals the same step outputs under their own names
              (independent of the xdot vector): position rate = NED velocity, body velocity rate = body
              acceleration, body rate rate = angular acceleration, quaternion rate = 0.5 * Omega(p, q, r) q
              from x, and each of the five controls moves exactly its own actuator state derivative
              (controls[0..4] -> x[15], x[14], x[16], x[17], x[13]); the actuator and gust derivatives
              also agree with the state change of one ordinary sks_core_step (library-internal
              integration, not the returned vector) within 20 % (+1e-9); at two operating points (the
              rudder doublet and the banked heading case, mid-run)
"""
import argparse
import ctypes as C
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

CORE = Path(__file__).resolve().parent
PLANT = CORE.parent
TOLERANCE = 1e-9  # absolute, after scaling by max(1, |reference|)

# CoreSnapshot index -> reference raw index (docs/MODEL_INTERFACE.md section 6).
PAIRS = {
    'position_ned': ([0, 1, 2], [22, 23, 24]),
    'quaternion': ([6, 7, 8, 9], [6, 7, 8, 9]),
    'rates_body': ([10, 11, 12], [28, 29, 30]),
    'velocity_ned': ([13, 14, 15], [15, 16, 17]),
    'roll_pitch': ([16, 17], [12, 11]),
    'angular_accel': ([19, 20, 21], [5, 13, 14]),
    # raw 27 AirSpeed_m_s is the true airspeed in references recorded from plant-based releases
    # (2026-10-16 onwards); the old export put the body x air velocity there (MODEL_REVIEW P8).
    'airspeed': ([52], [27]),
    'alpha_beta_deg': ([53, 54], [25, 26]),
    'mach': ([55], [36]),
    'actuators': ([67, 66, 68, 70, 69], [0, 1, 2, 3, 4]),  # raw order: R, L, elevator, throttle, rudder
}


class Initial(C.Structure):
    _fields_ = [('velocity_body_m_s', C.c_double * 3), ('height_m', C.c_double), ('euler_deg', C.c_double * 3)]


class Core:
    def __init__(self, path):
        self.lib = C.CDLL(str(path))
        self.lib.sks_core_size.restype = C.c_size_t
        self.lib.sks_core_api_version.restype = C.c_uint32
        self.lib.sks_core_init.argtypes = [C.c_void_p, C.POINTER(Initial)]
        self.lib.sks_core_step.argtypes = [C.c_void_p, C.POINTER(C.c_double), C.POINTER(C.c_double)]
        self.lib.sks_core_copy.argtypes = [C.c_void_p, C.c_void_p]
        self.lib.sks_core_get_state.argtypes = [C.c_void_p, C.POINTER(C.c_double)]
        self.lib.sks_core_eval.argtypes = [C.c_void_p] + [C.POINTER(C.c_double)] * 4
        self.size = self.lib.sks_core_size()

    def new(self):
        return C.create_string_buffer(self.size)

    def init(self, instance, case):
        ic = Initial()
        ic.velocity_body_m_s[:] = case['velocity']
        ic.height_m = case['height']
        ic.euler_deg[:] = case['euler']
        self.check(self.lib.sks_core_init(instance, C.byref(ic)))

    def step(self, instance, controls):
        u = (C.c_double * 16)(*controls)
        y = (C.c_double * 72)()
        self.check(self.lib.sks_core_step(instance, u, y))
        return np.frombuffer(y, dtype=np.float64).copy()

    @staticmethod
    def check(code):
        if code:
            raise RuntimeError(f'sks_core returned {code}')


def bit_equal(a, b):
    """Bit-for-bit equality of two float arrays (np.array_equal treats +0.0 and -0.0 as equal)."""
    a, b = np.ascontiguousarray(a, dtype=np.float64), np.ascontiguousarray(b, dtype=np.float64)
    return a.shape == b.shape and a.tobytes() == b.tobytes()


def load_reference_module():
    spec = importlib.util.spec_from_file_location('record_reference', PLANT / 'reference' / 'record_reference.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(core, case, controls, instance=None):
    instance = instance or core.new()
    core.init(instance, case)
    return np.array([core.step(instance, u) for u in controls])


# controls[0..4] (left aileron, right aileron, elevator, rudder, throttle) -> actuator state in x (sks_core.h:
# x[13..17] = throttle, right aileron, left aileron, elevator, rudder).
ACTUATOR_STATE = {0: 15, 1: 14, 2: 16, 3: 17, 4: 13}
GUST_STATES = (18, 19, 20)
DT_S = 0.004  # SKS_CORE_DT_S


def derivative_oracle(core, src, x, controls, xdot, y):
    """xdot of sks_core_eval against the step's named output signals (sks_core.h snapshot layout)."""
    def close(a, b):
        return float(np.max(np.abs(np.asarray(a) - np.asarray(b)) / (1.0 + np.abs(np.asarray(b)))))

    xs = np.array(x[:])
    q, (p, qr, r) = xs[6:10], xs[10:13]
    omega = np.array([[0, -p, -qr, -r], [p, 0, r, -qr], [qr, -r, 0, p], [r, qr, -p, 0]])
    errors = {'position_vs_velocity_ned': close(xdot[0:3], y[13:16]),
              'velocity_body_vs_accel_body': close(xdot[3:6], y[22:25]),
              'rates_vs_angular_accel': close(xdot[10:13], y[19:22]),
              'quaternion_vs_kinematics': close(xdot[6:10], 0.5 * omega @ q)}
    def step_rate(u):
        # The library's own integration of one ordinary step: (x_next - x) / dt, independent of xdot.
        dst = core.new()
        core.check(core.lib.sks_core_copy(dst, src))
        core.step(dst, u)
        nxt = (C.c_double * 21)()
        core.check(core.lib.sks_core_get_state(dst, nxt))
        return (np.array(nxt[:]) - xs) / DT_S

    def rate_error(value, rate):
        return float(abs(value - rate) / (abs(rate) + 1e-9 / 0.2))

    base_rate = step_rate(list(controls))
    rate_errors = {'gust_vs_step': max(rate_error(xdot[k], base_rate[k]) for k in GUST_STATES)}
    # Each control alone, from the same state (eval advances its instance: fresh copies).
    moved, actuator_errors = {}, []
    for control, state in ACTUATOR_STATE.items():
        u = list(controls)
        u[control] += -0.1 if u[control] > 0.5 else 0.1
        dst = core.new()
        core.check(core.lib.sks_core_copy(dst, src))
        out, snap = (C.c_double * 21)(), (C.c_double * 72)()
        core.check(core.lib.sks_core_eval(dst, x, (C.c_double * 16)(*u), out, snap))
        changed = [k for k in range(13, 18) if np.array(out[:])[k] != xdot[k]]
        moved[str(control)] = changed
        actuator_errors.append(rate_error(out[state], step_rate(u)[state]))
    rate_errors['actuator_vs_step'] = max(actuator_errors)
    mapping = all(moved[str(c)] == [s] for c, s in ACTUATOR_STATE.items())
    ok = all(e <= 1e-9 for e in errors.values()) and mapping and all(e <= 0.2 for e in rate_errors.values())
    return {'status': 'PASS' if ok else 'FAIL', 'max_relative_error': errors, 'tolerance': 1e-9,
            'step_increment_relative_error': rate_errors, 'step_increment_tolerance': 0.2,
            'actuator_mapping_ok': mapping, 'actuator_states_moved': moved}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--cache', type=Path, required=True)
    args = parser.parse_args()
    library = args.cache / 'native' / 'libskysurfer_core.dylib'
    core = Core(library)
    ref = load_reference_module()
    data = np.load(PLANT / 'reference' / 'data' / 'reference.npz')
    manifest = json.loads((PLANT / 'reference' / 'data' / 'manifest.json').read_text())
    result = {'library': str(library), 'api_version': hex(core.lib.sks_core_api_version()), 'instance_bytes': core.size,
              'reference_build_id': manifest['model_build_id'], 'tolerance': TOLERANCE, 'cases': {}}
    snapshots, worst, all_finite = {}, 0.0, True
    for case in ref.CASES:
        name = case['name']
        controls = data[name + '__controls']
        raw = data[name + '__raw']
        y = run(core, case, controls)
        snapshots[name] = y
        errors = {}
        for group, (ci, ri) in PAIRS.items():
            scale = np.maximum(1.0, np.abs(raw[:, ri]))
            errors[group] = float(np.max(np.abs(y[:, ci] - raw[:, ri]) / scale))
        # The old Truth yaw is wrapped into [0, 2*pi); the core yaw is the 6DOF atan2 principal value [-pi, pi].
        errors['yaw_wrapped'] = float(np.max(np.abs(np.mod(y[:, 18], 2 * np.pi) - raw[:, 10]) / np.maximum(1.0, np.abs(raw[:, 10]))))
        # Internal consistency: true airspeed is the norm of the air-relative body velocity.
        errors['airspeed_norm'] = float(np.max(np.abs(y[:, 52] - np.linalg.norm(y[:, 56:59], axis=1)) / np.maximum(1.0, y[:, 52])))
        worst = max(worst, max(errors.values()))
        finite = bool(np.isfinite(y).all()) and len(y) == len(controls)
        all_finite = all_finite and finite
        result['cases'][name] = {'samples': len(y), 'finite': finite, 'max_scaled_error': errors}
    ok = worst <= TOLERANCE and all_finite
    result['reference'] = {'status': 'PASS' if ok else 'FAIL', 'worst_scaled_error': worst, 'all_finite': all_finite}

    # Two instances interleaved step by step.
    a_case, b_case = ref.CASES[4], ref.CASES[12]  # elevator doublet, banked heading
    a_u, b_u = data[a_case['name'] + '__controls'], data[b_case['name'] + '__controls']
    ia, ib = core.new(), core.new()
    core.init(ia, a_case)
    core.init(ib, b_case)
    n = min(len(a_u), len(b_u))
    ya, yb = [], []
    for k in range(n):
        ya.append(core.step(ia, a_u[k]))
        yb.append(core.step(ib, b_u[k]))
    same = bit_equal(np.array(ya), snapshots[a_case['name']][:n]) and bit_equal(np.array(yb), snapshots[b_case['name']][:n])
    result['instances'] = {'status': 'PASS' if same else 'FAIL', 'cases': [a_case['name'], b_case['name']], 'steps': n}

    # Copy mid-run: both continue identically to the uninterrupted run.
    c_case = ref.CASES[7]  # rudder doublet
    c_u = data[c_case['name'] + '__controls']
    split = len(c_u) // 2
    src = core.new()
    core.init(src, c_case)
    first = [core.step(src, c_u[k]) for k in range(split)]
    dst = core.new()
    core.check(core.lib.sks_core_copy(dst, src))
    rest_src = [core.step(src, c_u[k]) for k in range(split, len(c_u))]
    rest_dst = [core.step(dst, c_u[k]) for k in range(split, len(c_u))]
    full = snapshots[c_case['name']]
    same = bit_equal(np.array(first + rest_src), full) and bit_equal(np.array(rest_dst), full[split:])
    result['copy'] = {'status': 'PASS' if same else 'FAIL', 'case': c_case['name'], 'split_step': split}

    # Re-initialise the same instance.
    again = run(core, a_case, a_u, instance=ia)
    result['reinit'] = {'status': 'PASS' if bit_equal(again, snapshots[a_case['name']]) else 'FAIL', 'case': a_case['name']}

    # State access and f(x, u) (API 1.1): eval from the state read back equals a normal step.
    nx = 21
    src = core.new()
    core.init(src, c_case)
    for k in range(split):
        core.step(src, c_u[k])
    x = (C.c_double * nx)()
    core.check(core.lib.sks_core_get_state(src, x))
    stepped, evaluated, moved = core.new(), core.new(), core.new()
    for dst in (stepped, evaluated, moved):
        core.check(core.lib.sks_core_copy(dst, src))
    u = (C.c_double * 16)(*c_u[split])
    y_step, y_eval, y_moved = (C.c_double * 72)(), (C.c_double * 72)(), (C.c_double * 72)()
    xdot, xdot_moved = (C.c_double * nx)(), (C.c_double * nx)()
    core.check(core.lib.sks_core_step(stepped, u, y_step))
    core.check(core.lib.sks_core_eval(evaluated, x, u, xdot, y_eval))
    x_moved = (C.c_double * nx)(*x)
    x_moved[3] += 1.0  # body u + 1 m/s
    core.check(core.lib.sks_core_eval(moved, x_moved, u, xdot_moved, y_moved))
    next_step, next_eval = (C.c_double * nx)(), (C.c_double * nx)()
    core.check(core.lib.sks_core_get_state(stepped, next_step))
    core.check(core.lib.sks_core_get_state(evaluated, next_eval))
    same = bytes(y_step) == bytes(y_eval) and bytes(next_step) == bytes(next_eval)
    applied = y_moved[3] == x_moved[3] and y_moved[3] != y_eval[3]
    finite = bool(np.isfinite(np.array(xdot[:])).all() and np.isfinite(np.array(xdot_moved[:])).all())
    version = core.lib.sks_core_api_version()
    oracle = derivative_oracle(core, src, x, c_u[split], np.array(xdot[:]), np.array(y_eval[:]))
    # A second operating point with non-zero rates and bank: the banked heading case, mid-run.
    d_case = ref.CASES[12]
    d_u = data[d_case['name'] + '__controls']
    d_src = core.new()
    core.init(d_src, d_case)
    for k in range(len(d_u) // 2):
        core.step(d_src, d_u[k])
    d_x, d_xdot, d_y = (C.c_double * nx)(), (C.c_double * nx)(), (C.c_double * 72)()
    core.check(core.lib.sks_core_get_state(d_src, d_x))
    d_eval = core.new()
    core.check(core.lib.sks_core_copy(d_eval, d_src))
    core.check(core.lib.sks_core_eval(d_eval, d_x, (C.c_double * 16)(*d_u[len(d_u) // 2]), d_xdot, d_y))
    oracle_2 = derivative_oracle(core, d_src, d_x, d_u[len(d_u) // 2], np.array(d_xdot[:]), np.array(d_y[:]))
    oracle_2['case'] = d_case['name']
    result['state_eval'] = {'status': 'PASS' if same and applied and finite and version >= 0x00010100
                            and oracle['status'] == 'PASS' and oracle_2['status'] == 'PASS' else 'FAIL',
                            'derivative_oracle_2': oracle_2,
                            'api_version': f'{version:#010x}', 'eval_equals_step': same, 'written_state_used': applied,
                            'finite': finite, 'derivative_oracle': oracle, 'case': c_case['name'], 'step': split}

    checks = ['reference', 'instances', 'copy', 'reinit', 'state_eval']
    result['status'] = 'PASS' if all(result[c]['status'] == 'PASS' for c in checks) else 'FAIL'
    (args.cache / 'results' / 'core_validation.json').write_text(json.dumps(result, indent=2))
    np.savez_compressed(args.cache / 'results' / 'core_snapshots.npz', **snapshots)
    print(json.dumps({c: result[c] for c in checks} | {'status': result['status']}, indent=2))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
