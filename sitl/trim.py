#!/usr/bin/env python3
"""Trim of the SkySurfer plant (steady level flight or steady coordinated turn) and the open-loop drop test.

  "$HOME/Library/Application Support/SkySurferHIL/venv/bin/python" sitl/trim.py
      [--airspeed 15 20 25] [--height 100] [--bank 0] [--drop 20] [--plant-lib PATH] [--json]

Default: level flight at 15, 20 and 25 m/s, 100 m, each followed by a 20 s drop test. Output: a table in
SI with kts / ft alongside (or one JSON line with --json).

Trim: the equilibrium of the plant core (plant/include/sks_core.h, sks_core_eval = f(x, u) on the same code
path as the simulation). Given airspeed V, height h, bank phi (heading 0, no wind), turn rate
psi_dot = g tan(phi) / V and body rates from the Euler kinematics (p = -psi_dot sin(theta),
q = psi_dot sin(phi) cos(theta), r = psi_dot cos(phi) cos(theta)). Unknowns (12): angle of attack,
sideslip, pitch, aileron (same command on both channels, as the HITL FC sends), elevator, rudder,
throttle and the five actuator states. The actuator states are eliminated inside the residual (each
actuator derivative is affine in its own state, so its rest value follows from two evaluations); the
remaining 7 unknowns solve body accelerations, angular accelerations and vertical velocity = 0 by damped
Newton iterations (finite-difference Jacobian, step limit, line search).

The surfaces pass a rate limiter (a hidden discrete state) after their servo, so every evaluation writes
the state and steps SETTLE times before taking f(x, u).

Drop test: start the plant at the trim state (rate limiters settled), hold the trim commands (nothing controls the aircraft) for
--drop seconds and report the drift. A correct trim drifts only through the slow modes (spiral, phugoid).

Commands are normalised like the HIL ABI controls[0..4]: elevator + = nose up, + on either aileron
channel rolls left. The plant library defaults to the one the SITL PX4 build links (SKS_PLANT_LIB in its
CMakeCache.txt); it must have core API 1.1 (sks_core_eval).
"""
import argparse
import ctypes as C
import json
import math
from pathlib import Path

import numpy as np

PX4_ROOT_CONFIG = Path.home() / 'Library' / 'Application Support' / 'SkySurferHIL' / 'px4_root'
G0 = 9.80665
DT = 0.004
NX = 21
SETTLE = 40  # steps for the surface rate limiters to reach the equilibrium deflection (2 deg per step)
D = C.c_double
# CoreSnapshot indices (plant/include/sks_core.h)
S_POS, S_VNED, S_EULER, S_AIRSPEED, S_SURF = 0, 13, 16, 52, 66


def default_plant_lib():
    cache = Path(PX4_ROOT_CONFIG.read_text().strip()) / 'build' / 'px4_sitl_default_skysurfer' / 'CMakeCache.txt'
    for line in cache.read_text().splitlines():
        if line.startswith('SKS_PLANT_LIB:'):
            return Path(line.split('=', 1)[1])
    raise RuntimeError('SKS_PLANT_LIB not found in ' + str(cache))


class _Initial(C.Structure):
    _fields_ = [('velocity_body_m_s', D * 3), ('height_m', D), ('euler_deg', D * 3)]


class Core:
    """The plant core through ctypes (sks_core.h, API 1.1)."""

    def __init__(self, path):
        self.lib = C.CDLL(str(path))
        self.lib.sks_core_size.restype = C.c_size_t
        self.lib.sks_core_api_version.restype = C.c_uint32
        if self.lib.sks_core_api_version() < 0x00010100:
            raise RuntimeError(f'{path}: core API {self.lib.sks_core_api_version():#x} has no sks_core_eval')
        self.path = Path(path)
        self.size = self.lib.sks_core_size()

    def new(self, height):
        core = C.create_string_buffer(self.size)
        ic = _Initial((D * 3)(10.0, 0.0, 0.0), height, (D * 3)(0.0, 0.0, 0.0))
        assert self.lib.sks_core_init(core, C.byref(ic)) == 0
        # The first step loads the integrators from the initial-condition input, which would overwrite a state
        # written by sks_core_eval; step once so that the template is past it.
        assert self.lib.sks_core_step(core, (D * 16)(), None) == 0
        return core

    def eval(self, template, x, controls, settle=SETTLE):
        """f(x, u) with the hidden discrete states settled: the surfaces pass a rate limiter after their
        servo transfer function, and the limiter keeps its previous output, so x is written and stepped
        `settle` times (continuous states reset to x each time) before the result is taken."""
        core = C.create_string_buffer(self.size)
        self.lib.sks_core_copy(core, template)
        xdot, snap = (D * NX)(), (D * 72)()
        u = (D * 16)(*(list(controls) + [0.0] * (16 - len(controls))))
        xs = (D * NX)(*x)
        for _ in range(settle):
            code = self.lib.sks_core_eval(core, xs, u, xdot, snap)
            if code:
                break
        return code, np.array(xdot[:]), np.array(snap[:]), core, u


def quaternion(phi, theta, psi):
    cr, sr, cp, sp, cy, sy = (math.cos(phi / 2), math.sin(phi / 2), math.cos(theta / 2), math.sin(theta / 2),
                              math.cos(psi / 2), math.sin(psi / 2))
    return [cr * cp * cy + sr * sp * sy, sr * cp * cy - cr * sp * sy, cr * sp * cy + sr * cp * sy,
            cr * cp * sy - sr * sp * cy]


def state(z, actuators, airspeed, height, bank):
    alpha, beta, theta = z[0], z[1], z[2]
    psi_dot = G0 * math.tan(bank) / airspeed
    x = [0.0, 0.0, -height]
    x += [airspeed * math.cos(alpha) * math.cos(beta), airspeed * math.sin(beta), airspeed * math.sin(alpha) * math.cos(beta)]
    x += quaternion(bank, theta, 0.0)
    x += [-psi_dot * math.sin(theta), psi_dot * math.sin(bank) * math.cos(theta), psi_dot * math.cos(bank) * math.cos(theta)]
    x += list(actuators) + [0.0, 0.0, 0.0]
    return x


def controls(z):
    aileron, elevator, rudder, throttle = z[3], z[4], z[5], z[6]
    return [aileron, aileron, elevator, rudder, throttle]


def residual(core, template, z, airspeed, height, bank):
    """Residual for the 7 unknowns; the actuator states are set to their rest values for the commands
    (each actuator derivative is affine in its own state: two evaluations give the root)."""
    u = controls(z)
    code0, xdot0, _, _, _ = core.eval(template, state(z, [0.0] * 5, airspeed, height, bank), u)
    code1, xdot1, _, _, _ = core.eval(template, state(z, [1.0] * 5, airspeed, height, bank), u)
    if code0 or code1:
        raise RuntimeError(f'sks_core_eval returned {code0 or code1}')
    slope = xdot1[13:18] - xdot0[13:18]
    actuators = -xdot0[13:18] / slope
    code, xdot, snap, _, _ = core.eval(template, state(z, actuators, airspeed, height, bank), u)
    if code != 0:
        raise RuntimeError(f'sks_core_eval returned {code}')
    f = np.concatenate([xdot[3:6], xdot[10:13] * 10.0, [snap[S_VNED + 2]]])
    return f, snap, actuators, float(np.max(np.abs(xdot[13:18])))


def trim(core, airspeed, height=100.0, bank_deg=0.0, iterations=100):
    """Unknowns z = [alpha, beta, theta, aileron, elevator, rudder, throttle]; damped Newton with line search."""
    bank = math.radians(bank_deg)
    template = core.new(height)
    z = np.array([math.radians(3.0), 0.0, math.radians(3.0), 0.0, 0.3, 0.0, 0.2])
    lower = np.array([-0.3, -0.3, -1.2, -1.0, -1.0, -1.0, 0.0])
    upper = np.array([0.3, 0.3, 1.2, 1.0, 1.0, 1.0, 1.0])
    step = 1e-7
    f, snap, actuators, act_res = residual(core, template, z, airspeed, height, bank)
    for _ in range(iterations):
        if np.max(np.abs(f)) < 1e-11:
            break
        jac = np.column_stack([(residual(core, template, z + np.eye(7)[k] * step, airspeed, height, bank)[0] - f) / step
                               for k in range(7)])
        dz = np.linalg.lstsq(jac, -f, rcond=None)[0]
        dz *= min(1.0, 0.2 / max(1e-12, np.max(np.abs(dz))))  # at most 0.2 (rad or command) per iteration
        scale, norm = 1.0, np.linalg.norm(f)
        while scale > 1e-4:
            candidate = np.clip(z + scale * dz, lower, upper)
            fc, sc, ac, ar = residual(core, template, candidate, airspeed, height, bank)
            if np.linalg.norm(fc) < norm:
                z, f, snap, actuators, act_res = candidate, fc, sc, ac, ar
                break
            scale *= 0.5
        else:
            break
    u = controls(z)
    psi_dot = G0 * math.tan(bank) / airspeed
    radius = airspeed ** 2 / (G0 * math.tan(bank)) if bank else math.inf
    residual_max = max(float(np.max(np.abs(f))), act_res)
    return {
        'airspeed_m_s': airspeed, 'airspeed_kts': airspeed / 0.514444, 'height_m': height, 'height_ft': height / 0.3048,
        'bank_deg': bank_deg, 'turn_rate_deg_s': math.degrees(psi_dot), 'turn_radius_m': radius,
        'turn_radius_ft': radius / 0.3048, 'load_factor': 1.0 / math.cos(bank),
        'alpha_deg': math.degrees(z[0]), 'beta_deg': math.degrees(z[1]), 'pitch_deg': math.degrees(z[2]),
        'aileron': float(u[0]), 'elevator': float(u[2]), 'rudder': float(u[3]), 'throttle': float(u[4]),
        'surface_deg': {'aileron_left': snap[S_SURF], 'aileron_right': snap[S_SURF + 1], 'elevator': snap[S_SURF + 2],
                        'rudder': snap[S_SURF + 3]},
        'residual_max': residual_max, 'converged': bool(residual_max < 1e-8),
        'state': state(z, actuators, airspeed, height, bank), 'controls': [float(v) for v in u],
    }


def drop(core, trim_result, seconds=20.0):
    """Hold the trim commands from the trim state; report the drift after `seconds`."""
    template = core.new(trim_result['height_m'])
    code, _, first, live, u = core.eval(template, trim_result['state'], trim_result['controls'])
    assert code == 0, code
    snap = (D * 72)()
    rows = [first]
    for _ in range(int(round(seconds / DT)) - 1):
        if core.lib.sks_core_step(live, u, snap) != 0:
            break
        rows.append(np.array(snap[:]))
    rows = np.array(rows)
    heading = np.unwrap(rows[:, S_EULER + 2])
    t = np.arange(len(rows)) * DT
    return {
        'seconds': float(t[-1] + DT),
        'airspeed_change_m_s': float(rows[-1, S_AIRSPEED] - rows[0, S_AIRSPEED]),
        'height_change_m': float(-(rows[-1, S_POS + 2] - rows[0, S_POS + 2])),
        'pitch_change_deg': math.degrees(rows[-1, S_EULER + 1] - rows[0, S_EULER + 1]),
        'roll_change_deg': math.degrees(rows[-1, S_EULER] - rows[0, S_EULER]),
        'turn_rate_deg_s': math.degrees((heading[-1] - heading[0]) / t[-1]) if t[-1] > 0 else 0.0,
        'max_abs': {'airspeed_m_s': float(np.max(np.abs(rows[:, S_AIRSPEED] - rows[0, S_AIRSPEED]))),
                    'height_m': float(np.max(np.abs(rows[:, S_POS + 2] - rows[0, S_POS + 2]))),
                    'pitch_deg': math.degrees(np.max(np.abs(rows[:, S_EULER + 1] - rows[0, S_EULER + 1]))),
                    'roll_deg': math.degrees(np.max(np.abs(rows[:, S_EULER] - rows[0, S_EULER])))},
    }


def table(results):
    lines = ['airspeed            height          bank   alpha  pitch   beta  elevator aileron  rudder throttle'
             ' | drop: dV m/s    dh m  dpitch   droll turn deg/s']
    for r in results:
        d = r.get('drop')
        row = (f"{r['airspeed_m_s']:5.1f} m/s {r['airspeed_kts']:5.1f} kts {r['height_m']:5.0f} m {r['height_ft']:4.0f} ft "
               f"{r['bank_deg']:5.1f} {r['alpha_deg']:6.2f} {r['pitch_deg']:6.2f} {r['beta_deg']:6.2f}  "
               f"{r['elevator']:7.4f} {r['aileron']:7.4f} {r['rudder']:7.4f}  {r['throttle']:7.4f}")
        if d:
            row += (f" | {d['airspeed_change_m_s']:+7.3f} {d['height_change_m']:+7.2f} {d['pitch_change_deg']:+7.2f} "
                    f"{d['roll_change_deg']:+7.2f} {d['turn_rate_deg_s']:+8.2f}")
        lines.append(row + ('' if r['converged'] else '   NOT CONVERGED'))
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--airspeed', type=float, nargs='+', default=[15.0, 20.0, 25.0])
    parser.add_argument('--height', type=float, default=100.0)
    parser.add_argument('--bank', type=float, default=0.0, help='deg; non-zero = steady coordinated turn')
    parser.add_argument('--drop', type=float, default=20.0, help='open-loop seconds from the trim (0 = none)')
    parser.add_argument('--plant-lib', type=Path)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    core = Core(args.plant_lib or default_plant_lib())
    results = []
    for airspeed in args.airspeed:
        r = trim(core, airspeed, args.height, args.bank)
        if args.drop > 0:
            r['drop'] = drop(core, r, args.drop)
        results.append(r)
    if args.json:
        print(json.dumps({'plant_lib': str(core.path), 'trims': results}))
    else:
        print(f'plant library: {core.path}')
        print(table(results))


if __name__ == '__main__':
    main()
