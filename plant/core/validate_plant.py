#!/usr/bin/env python3
"""Validate libskysurfer_plant (shared library): C Truth (SksPlant) and C sensors (SksSensors).

  "$HOME/Library/Application Support/SkySurferHIL/venv/bin/python" plant/core/validate_plant.py \
      --cache ~/Library/Caches/Codex/SkySurferPhaseB/core_<timestamp>

Checks (results in <cache>/results/plant_validation.json; exit code 0 only when all PASS):
  self_test    the comparison helpers turn NaN / Inf into FAIL
  layout       ctypes structs match the C headers: sizeof and every field offset (compiled probe)
  truth        14 reference cases: every old TruthSnapshot field with the same meaning
  consistency  |F_gravity| = mass*g; specific force = (aero + thrust + ground) / mass
  rejects      non-zero initial rates, site_msl and wind are refused
  plant_state  two plants interleaved, sks_plant_copy mid-run: bit-identical
  geo          flat-earth LLA and wrapping against MATLAB flat2lla (plant/truth/flat2lla_test_vectors.json)
  wmm          C WMM against MATLAB wrldmagm (plant/sensors/wmm_test_vectors.json)
  ideal        noise off: every sensor output field equals its ideal value; GPS every 25 steps, held
  boundaries   GPS fixes stay legal near +-180 deg and the poles; courses stay in [0, 2*pi) / [0, 360)
  noise        noise on: per-channel standard deviation and mean match the configuration
  vibration    vibration on with throttle: standard deviation = sqrt(chip^2 + vibration^2)
  rng          same seed reproduces, another seed differs, sks_sensors_copy continues identically
"""
import argparse
import ctypes as C
import importlib.util
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

CORE = Path(__file__).resolve().parent
PLANT = CORE.parent
sys.path.insert(0, str(CORE))
import toolchain  # noqa: E402
TOL = 1e-9
MASS, G = None, None  # from the model: <cache>/results/core_build.json (set in main)
D3, D4 = C.c_double * 3, C.c_double * 4


class Initial(C.Structure):
    _fields_ = [('height_agl_m', C.c_double), ('velocity_body_m_s', D3), ('euler_rad', D3), ('rates_body_rad_s', D3),
                ('latitude_deg', C.c_double), ('longitude_deg', C.c_double), ('site_msl_m', C.c_double), ('seed', C.c_uint32)]


class Input(C.Structure):
    _fields_ = [('command', C.c_double * 5), ('wind_ned_m_s', D3)]


class Truth(C.Structure):
    _fields_ = [('time_s', C.c_double), ('position_ned_m', D3), ('latitude_deg', C.c_double), ('longitude_deg', C.c_double),
                ('altitude_msl_m', C.c_double), ('height_agl_m', C.c_double), ('velocity_ned_m_s', D3),
                ('velocity_body_m_s', D3), ('ground_speed_m_s', C.c_double), ('course_rad', C.c_double),
                ('quaternion_nb', D4), ('euler_rad', D3), ('rates_body_rad_s', D3), ('angular_accel_body_rad_s2', D3),
                ('specific_force_body_m_s2', D3), ('accel_ned_m_s2', D3), ('airspeed_true_m_s', C.c_double),
                ('alpha_rad', C.c_double), ('beta_rad', C.c_double), ('mach', C.c_double), ('dynamic_pressure_pa', C.c_double),
                ('air_density_kg_m3', C.c_double), ('static_pressure_pa', C.c_double), ('air_temperature_k', C.c_double),
                ('wind_ned_m_s', D3), ('surface_deflection_rad', D4), ('throttle_actual', C.c_double),
                ('force_aero_body_N', D3), ('moment_aero_body_Nm', D3), ('force_thrust_body_N', D3),
                ('moment_thrust_body_Nm', D3), ('force_ground_body_N', D3), ('force_gravity_body_N', D3),
                ('on_ground', C.c_uint32), ('aero_active', C.c_uint32), ('flags', C.c_uint32), ('reserved', C.c_uint32)]


class Config(C.Structure):
    _fields_ = [('dt_s', C.c_double), ('gps_decimation', C.c_uint32), ('noise_enabled', C.c_uint32),
                ('accel_noise_density', D3), ('gyro_noise_density', D3), ('mag_noise_ut', D3), ('baro_noise_pa', C.c_double),
                ('diff_pressure_noise_pa', C.c_double), ('gps_horizontal_noise_m', C.c_double),
                ('gps_vertical_noise_m', C.c_double), ('gps_velocity_noise_m_s', D3), ('wmm_decimal_year', C.c_double),
                ('vibration_enabled', C.c_uint32), ('reserved', C.c_uint32), ('vibration_accel_m_s2', D3),
                ('vibration_gyro_rad_s', D3)]


class Output(C.Structure):
    _fields_ = [('time_s', C.c_double), ('accel_m_s2', D3), ('gyro_rad_s', D3), ('magnetic_ut', D3),
                ('absolute_pressure_pa', C.c_double), ('differential_pressure_pa', C.c_double), ('temperature_k', C.c_double),
                ('gps_lla_msl', D3), ('gps_velocity_ned_m_s', D3), ('gps_ground_speed_m_s', C.c_double),
                ('gps_course_deg', C.c_double), ('gps_sample_time_s', C.c_double), ('imu_updated', C.c_uint32),
                ('gps_updated', C.c_uint32)]


STRUCTS = {'SksInitialConditions': Initial, 'SksPlantInput': Input, 'SksTruth': Truth,
           'SksSensorConfig': Config, 'SksSensorOutput': Output}


def compile_and_run(source):
    """Compile a small C program against plant/include and return its stdout."""
    with tempfile.TemporaryDirectory() as tmp:
        src, exe = Path(tmp) / 'probe.c', Path(tmp) / 'probe'
        src.write_text(source)
        subprocess.run(toolchain.cc() + ['-std=c99', '-I', str(PLANT / 'include'), str(src), '-o', str(exe), '-lm'],
                       check=True)
        return subprocess.check_output([str(exe)], text=True)


def check_layout():
    lines = []
    for n, cls in STRUCTS.items():
        lines.append(f'printf("{n} sizeof %zu\\n", sizeof({n}));')
        for f in cls._fields_:
            lines.append(f'printf("{n} {f[0]} %zu\\n", offsetof({n}, {f[0]}));')
    out = compile_and_run('#include <stddef.h>\n#include <stdio.h>\n#include "sks_sensors.h"\nint main(void){' +
                          ''.join(lines) + 'return 0;}')
    c = {(a, b): int(v) for a, b, v in (line.split() for line in out.splitlines())}
    mismatches = []
    for n, cls in STRUCTS.items():
        if c[(n, 'sizeof')] != C.sizeof(cls):
            mismatches.append(f'{n} sizeof {c[(n, "sizeof")]} != {C.sizeof(cls)}')
        for f in cls._fields_:
            if c[(n, f[0])] != getattr(cls, f[0]).offset:
                mismatches.append(f'{n}.{f[0]} {c[(n, f[0])]} != {getattr(cls, f[0]).offset}')
    fields = sum(len(cls._fields_) for cls in STRUCTS.values())
    return {'status': 'PASS' if not mismatches else 'FAIL', 'structs': len(STRUCTS), 'fields': fields,
            'mismatches': mismatches}


class Lib:
    def __init__(self, path):
        lib = self.lib = C.CDLL(str(path))
        for name in ('sks_plant_size', 'sks_sensors_size'):
            getattr(lib, name).restype = C.c_size_t
        lib.sks_plant_init.argtypes = [C.c_void_p, C.POINTER(Initial)]
        lib.sks_plant_step.argtypes = [C.c_void_p, C.POINTER(Input), C.POINTER(Truth)]
        lib.sks_plant_copy.argtypes = [C.c_void_p, C.c_void_p]
        lib.sks_sensors_default_config.argtypes = [C.POINTER(Config)]
        lib.sks_sensors_init.argtypes = [C.c_void_p, C.POINTER(Config), C.c_uint32]
        lib.sks_sensors_step.argtypes = [C.c_void_p, C.POINTER(Truth), C.POINTER(Output)]
        lib.sks_sensors_copy.argtypes = [C.c_void_p, C.c_void_p]
        lib.sks_sensors_magnetic_field_ned.argtypes = [C.POINTER(Config), C.c_double, C.c_double, C.c_double, C.POINTER(C.c_double)]
        lib.sks_wmm_field_ned.argtypes = [C.c_double] * 4 + [C.POINTER(C.c_double)]

    def plant(self):
        return C.create_string_buffer(self.lib.sks_plant_size())

    def sensors(self):
        return C.create_string_buffer(self.lib.sks_sensors_size())

    def config(self, **overrides):
        c = Config()
        self.lib.sks_sensors_default_config(C.byref(c))
        for k, v in overrides.items():
            setattr(c, k, v)
        return c


def initial_for(case, ref):
    ic = Initial()
    ic.height_agl_m = case['height']
    ic.velocity_body_m_s[:] = case['velocity']
    ic.euler_rad[:] = [math.radians(e) for e in case['euler']]
    ic.latitude_deg = case.get('lat', ref.LAT0)
    ic.longitude_deg = case.get('lon', ref.LON0)
    return ic


def run_plant(lib, ic, controls, plant=None):
    plant = plant or lib.plant()
    code = lib.lib.sks_plant_init(plant, C.byref(ic))
    assert code == 0, code
    truths = []
    for u in controls:
        inp, t = Input(), Truth()
        inp.command[:] = list(u[:5])
        code = lib.lib.sks_plant_step(plant, C.byref(inp), C.byref(t))
        assert code == 0, code
        truths.append(bytes(t))
    return truths


def as_array(truths, field):
    return np.array([np.ctypeslib.as_array(getattr(Truth.from_buffer_copy(b), field)) if
                     hasattr(getattr(Truth.from_buffer_copy(b), field), '_length_') else
                     [getattr(Truth.from_buffer_copy(b), field)] for b in truths], dtype=float)


def worst_abs(diff):
    """Largest absolute value; any NaN / Inf makes it infinite (a plain max() skips NaN)."""
    diff = np.asarray(diff, dtype=float)
    if diff.size == 0:
        return 0.0
    return float(np.max(np.abs(diff))) if np.isfinite(diff).all() else math.inf


def scaled(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    return worst_abs((a - b) / np.maximum(1.0, np.abs(b)))


def check_self_test():
    cases = {'nan_abs': worst_abs([0.0, math.nan]), 'inf_abs': worst_abs([math.inf]),
             'nan_scaled': scaled([math.nan], [1.0]), 'nan_reference': scaled([1.0], [math.nan])}
    ok = all(v == math.inf for v in cases.values()) and worst_abs([]) == 0.0
    return {'status': 'PASS' if ok else 'FAIL', 'cases': {k: str(v) for k, v in cases.items()}}


def load_reference_module():
    spec = importlib.util.spec_from_file_location('record_reference', PLANT / 'reference' / 'record_reference.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_truth(lib, ref, data):
    pairs = {  # SksTruth field -> reference raw index, transform
        'position_ned_m': ([22, 23, 24], None), 'velocity_ned_m_s': ([15, 16, 17], None),
        'quaternion_nb': ([6, 7, 8, 9], None), 'rates_body_rad_s': ([28, 29, 30], None),
        'angular_accel_body_rad_s2': ([5, 13, 14], None), 'specific_force_body_m_s2': ([31, 32, 33], None),
        'latitude_deg': ([20], None), 'longitude_deg': ([21], None), 'height_agl_m': ([19], None),
        'alpha_rad': ([37], None), 'beta_rad': ([38], None), 'mach': ([36], None)}
    cases, worst, consistency, truths_by_case = {}, 0.0, {'gravity': 0.0, 'specific_force': 0.0}, {}
    for case in ref.CASES:
        name = case['name']
        controls, raw = data[name + '__controls'], data[name + '__raw']
        truths = run_plant(lib, initial_for(case, ref), controls)
        truths_by_case[name] = truths
        errors = {}
        for field, (ri, _) in pairs.items():
            errors[field] = scaled(as_array(truths, field), raw[:, ri])
        euler = as_array(truths, 'euler_rad')
        errors['roll_pitch'] = scaled(euler[:, :2], raw[:, [12, 11]])
        errors['yaw_wrapped'] = scaled(np.mod(euler[:, 2], 2 * np.pi)[:, None], raw[:, [10]])
        errors['altitude_rate'] = scaled(-as_array(truths, 'velocity_ned_m_s')[:, 2:3], raw[:, [18]])
        worst = max(worst, max(errors.values()))
        fg = as_array(truths, 'force_gravity_body_N')
        consistency['gravity'] = max(consistency['gravity'], float(np.max(np.abs(np.linalg.norm(fg, axis=1) - MASS * G))))
        f = (as_array(truths, 'force_aero_body_N') + as_array(truths, 'force_thrust_body_N') +
             as_array(truths, 'force_ground_body_N')) / MASS
        consistency['specific_force'] = max(consistency['specific_force'],
                                            float(np.max(np.abs(f - as_array(truths, 'specific_force_body_m_s2')))))
        cases[name] = {'samples': len(truths), 'max_scaled_error': errors}
    truth = {'status': 'PASS' if worst <= TOL else 'FAIL', 'worst_scaled_error': worst, 'cases': cases,
             'not_compared': 'AirSpeed_m_s (old: body x air velocity), G, GroundSpeed_m_s (old: 3D speed): MODEL_REVIEW P8'}
    ok = consistency['gravity'] <= 1e-12 and consistency['specific_force'] <= 1e-9
    return truth, {'status': 'PASS' if ok else 'FAIL', 'max_abs': consistency}, truths_by_case


def check_rejects(lib, ref):
    base = ref.CASES[3]
    results = {}
    for label, change in (('rates', lambda ic: ic.rates_body_rad_s.__setitem__(0, 0.1)),
                          ('site_msl', lambda ic: setattr(ic, 'site_msl_m', 10.0))):
        ic = initial_for(base, ref)
        change(ic)
        results[label] = lib.lib.sks_plant_init(lib.plant(), C.byref(ic))
    plant = lib.plant()
    lib.lib.sks_plant_init(plant, C.byref(initial_for(base, ref)))
    inp = Input()
    inp.wind_ned_m_s[0] = 1.0
    results['wind'] = lib.lib.sks_plant_step(plant, C.byref(inp), C.byref(Truth()))
    return {'status': 'PASS' if all(v == 4 for v in results.values()) else 'FAIL', 'codes': results}


def check_plant_state(lib, ref, data, truths_by_case):
    a, b = ref.CASES[4], ref.CASES[12]
    ua, ub = data[a['name'] + '__controls'], data[b['name'] + '__controls']
    pa, pb = lib.plant(), lib.plant()
    lib.lib.sks_plant_init(pa, C.byref(initial_for(a, ref)))
    lib.lib.sks_plant_init(pb, C.byref(initial_for(b, ref)))
    ya, yb = [], []
    for k in range(min(len(ua), len(ub))):
        for plant, u, out in ((pa, ua[k], ya), (pb, ub[k], yb)):
            inp, t = Input(), Truth()
            inp.command[:] = list(u[:5])
            lib.lib.sks_plant_step(plant, C.byref(inp), C.byref(t))
            out.append(bytes(t))
    inter = ya == truths_by_case[a['name']][:len(ya)] and yb == truths_by_case[b['name']][:len(yb)]
    c = ref.CASES[7]
    uc = data[c['name'] + '__controls']
    src = lib.plant()
    lib.lib.sks_plant_init(src, C.byref(initial_for(c, ref)))
    split, first = len(uc) // 2, []
    for k in range(split):
        inp, t = Input(), Truth()
        inp.command[:] = list(uc[k][:5])
        lib.lib.sks_plant_step(src, C.byref(inp), C.byref(t))
        first.append(bytes(t))
    dst = lib.plant()
    lib.lib.sks_plant_copy(dst, src)
    rest = {0: [], 1: []}
    for k in range(split, len(uc)):
        for i, plant in enumerate((src, dst)):
            inp, t = Input(), Truth()
            inp.command[:] = list(uc[k][:5])
            lib.lib.sks_plant_step(plant, C.byref(inp), C.byref(t))
            rest[i].append(bytes(t))
    full = truths_by_case[c['name']]
    copy_ok = first + rest[0] == full and rest[1] == full[split:]
    return {'status': 'PASS' if inter and copy_ok else 'FAIL', 'interleaved': inter, 'copy': copy_ok}


def check_wmm(lib):
    vectors = json.loads((PLANT / 'sensors' / 'wmm_test_vectors.json').read_text())['vectors']
    diffs = []
    for v in vectors:
        out = D3()
        lib.lib.sks_wmm_field_ned(v['latitude_deg'], v['longitude_deg'], v['height_m'], v['decimal_year'], out)
        diffs.append(np.array(out[:]) - np.array(v['field_ned_nt']))
    worst = worst_abs(diffs)
    return {'status': 'PASS' if worst <= 1e-3 else 'FAIL', 'vectors': len(vectors), 'max_abs_nt': worst}


def check_geo():
    vectors = json.loads((PLANT / 'truth' / 'flat2lla_test_vectors.json').read_text())['vectors']
    rows = ','.join(f'{{{v["north_m"]!r},{v["east_m"]!r},{v["lat0_deg"]!r},{v["lon0_deg"]!r}}}' for v in vectors)
    out = compile_and_run('#include <stdio.h>\n#include "sks_geo.h"\nstatic const double v[][4]={' + rows +
                          '};int main(void){for(size_t k=0;k<sizeof v/sizeof v[0];k++){double a,b;'
                          'sks_geo_flat_to_lla(v[k][0],v[k][1],v[k][2],v[k][3],&a,&b);printf("%.17g %.17g\\n",a,b);}'
                          'return 0;}')
    got = np.array([[float(x) for x in line.split()] for line in out.splitlines()])
    want = np.array([[v['lat_deg'], v['lon_deg']] for v in vectors])
    # Exactly at a pole cos(lat0) ~ 6e-17, so an east offset of more than a few metres moves the
    # longitude by more than double precision can represent (the flat-earth model is singular there):
    # MATLAB and C then give different arbitrary longitudes. Those points are checked for range only.
    singular = np.array([abs(v['lat0_deg']) == 90.0 and abs(v['east_m']) > 1.0 for v in vectors])
    worst = worst_abs(got[~singular] - want[~singular])
    lat_singular = worst_abs(got[singular, 0] - want[singular, 0])
    legal = bool(np.isfinite(got).all() and np.all(np.abs(got[:, 0]) <= 90.0) and np.all(np.abs(got[:, 1]) <= 180.0))
    ok = worst <= 1e-9 and lat_singular <= 1e-9 and legal
    return {'status': 'PASS' if ok else 'FAIL', 'vectors': len(vectors), 'compared': int((~singular).sum()),
            'max_abs_deg': worst, 'pole_singular_range_only': int(singular.sum()),
            'pole_singular_latitude_max_abs_deg': lat_singular, 'legal_ranges': legal}


def ned_to_body(q, v):
    w, x, y, z = q
    r = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
                  [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
                  [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])
    return r.T @ v


def run_sensors(lib, config, truths, seed=1, sensors=None):
    sensors = sensors or lib.sensors()
    assert lib.lib.sks_sensors_init(sensors, C.byref(config), seed) == 0
    outs = []
    for b in truths:
        t, o = Truth.from_buffer_copy(b), Output()
        assert lib.lib.sks_sensors_step(sensors, C.byref(t), C.byref(o)) == 0
        outs.append(bytes(o))
    return outs


def field(outs, name):
    rows = []
    for b in outs:
        v = getattr(Output.from_buffer_copy(b), name)
        rows.append(list(v) if hasattr(v, '_length_') else [v])
    return np.array(rows, dtype=float)


def check_ideal(lib, truths):
    cfg = lib.config(noise_enabled=0)
    outs = run_sensors(lib, cfg, truths)
    t = [Truth.from_buffer_copy(b) for b in truths]
    err = {}
    err['time'] = worst_abs(field(outs, 'time_s') - as_array(truths, 'time_s'))
    err['accel'] = worst_abs(field(outs, 'accel_m_s2') - as_array(truths, 'specific_force_body_m_s2'))
    err['gyro'] = worst_abs(field(outs, 'gyro_rad_s') - as_array(truths, 'rates_body_rad_s'))
    err['baro'] = worst_abs(field(outs, 'absolute_pressure_pa') - as_array(truths, 'static_pressure_pa'))
    err['temperature'] = worst_abs(field(outs, 'temperature_k') - as_array(truths, 'air_temperature_k'))
    u = (as_array(truths, 'airspeed_true_m_s') * np.cos(as_array(truths, 'alpha_rad')) *
         np.cos(as_array(truths, 'beta_rad')))
    err['diff_pressure'] = worst_abs(field(outs, 'differential_pressure_pa') -
                                     np.sign(u) * 0.5 * as_array(truths, 'air_density_kg_m3') * u * u)
    mag = []
    for x in t:
        b = D3()
        lib.lib.sks_sensors_magnetic_field_ned(C.byref(cfg), x.latitude_deg, x.longitude_deg, x.altitude_msl_m, b)
        mag.append(ned_to_body(list(x.quaternion_nb), np.array(b[:])))
    err['mag'] = worst_abs(field(outs, 'magnetic_ut') - np.array(mag))
    fixes = np.arange(len(outs)) // 25 * 25
    vel = as_array(truths, 'velocity_ned_m_s')[fixes]
    course = np.degrees(np.arctan2(vel[:, 1], vel[:, 0])) % 360.0
    err['gps_ground_speed'] = worst_abs(field(outs, 'gps_ground_speed_m_s')[:, 0] - np.hypot(vel[:, 0], vel[:, 1]))
    err['gps_course'] = worst_abs(field(outs, 'gps_course_deg')[:, 0] - course)
    err['gps_sample_time'] = worst_abs(field(outs, 'gps_sample_time_s')[:, 0] - as_array(truths, 'time_s')[fixes, 0])
    err['imu_updated'] = worst_abs(field(outs, 'imu_updated') - 1.0)
    every = [n for n, _ in Output._fields_]
    err['all_finite'] = 0.0 if all(np.isfinite(field(outs, n)).all() for n in every) else math.inf
    updated = field(outs, 'gps_updated')[:, 0]
    schedule = bool(np.array_equal(np.nonzero(updated)[0], np.arange(0, len(outs), 25)))
    lla, held = field(outs, 'gps_lla_msl'), True
    for k in range(len(outs)):
        fix = (k // 25) * 25
        expect = [t[fix].latitude_deg, t[fix].longitude_deg, t[fix].altitude_msl_m]
        held = held and np.array_equal(lla[k], expect) and np.array_equal(
            field(outs[k:k + 1], 'gps_velocity_ned_m_s')[0], list(t[fix].velocity_ned_m_s))
    ok = max(err.values()) <= 1e-12 and schedule and held
    return {'status': 'PASS' if ok else 'FAIL', 'max_abs': {k: str(v) if math.isinf(v) else v for k, v in err.items()},
            'gps_every_25_steps': schedule, 'gps_hold': held}


def check_boundaries(lib, ref):
    """GPT 2026-10-16 counterexamples: GPS fixes near +-180 deg / the poles, and course = 2*pi."""
    cfg, legal, details = lib.config(), True, {}
    for label, lat, lon in (('lon_+180', 10.0, 179.99999999), ('lon_-180', -10.0, -180.0), ('near_north_pole', 89.9999999, 30.0),
                            ('north_pole', 90.0, 0.0), ('south_pole', -90.0, 120.0)):
        t = Truth.from_buffer_copy(constant_truth())
        t.latitude_deg, t.longitude_deg = lat, lon
        outs = run_sensors(lib, cfg, [bytes(t)] * 5000, seed=5)
        fixes = field(outs, 'gps_lla_msl')[np.nonzero(field(outs, 'gps_updated')[:, 0])[0]]
        ok = bool(np.isfinite(fixes).all() and np.all(np.abs(fixes[:, 0]) <= 90.0) and np.all(np.abs(fixes[:, 1]) <= 180.0))
        details[label] = {'fixes': int(len(fixes)), 'legal': ok, 'lat_range': [float(fixes[:, 0].min()), float(fixes[:, 0].max())],
                          'lon_range': [float(fixes[:, 1].min()), float(fixes[:, 1].max())]}
        legal = legal and ok
    case = dict(ref.CASES[3], velocity=[20.0, -1e-15, 0.0], euler=[0.0, 0.0, 0.0])
    truths = run_plant(lib, initial_for(case, ref), np.zeros((50, 16)))
    course = as_array(truths, 'course_rad')[:, 0]
    truth_course = bool(np.all((course >= 0.0) & (course < 2 * np.pi)))
    t = Truth.from_buffer_copy(constant_truth())
    t.velocity_ned_m_s[:] = [20.0, -1e-15, 0.0]
    gps_course = field(run_sensors(lib, lib.config(noise_enabled=0), [bytes(t)] * 30), 'gps_course_deg')[:, 0]
    sensor_course = bool(np.all((gps_course >= 0.0) & (gps_course < 360.0)))
    ok = legal and truth_course and sensor_course
    return {'status': 'PASS' if ok else 'FAIL', 'gps': details, 'truth_course_in_range': truth_course,
            'truth_course_first': float(course[0]), 'gps_course_in_range': sensor_course}


def constant_truth(throttle=0.0):
    t = Truth()
    t.latitude_deg, t.longitude_deg, t.altitude_msl_m = 22.910275834988674, 120.31096929726908, 100.0
    t.quaternion_nb[:] = [1, 0, 0, 0]
    t.specific_force_body_m_s2[:] = [0, 0, -G]
    t.static_pressure_pa, t.air_density_kg_m3, t.air_temperature_k = 100129.0, 1.213, 287.5
    t.airspeed_true_m_s = 20.0
    t.velocity_ned_m_s[:] = [20.0, 0, 0]
    t.throttle_actual = throttle
    return bytes(t)


def sigma_check(values, ideal, sigma, n_sigma_mean=5.0, rel=0.05):
    d = values - ideal
    std, mean = d.std(axis=0), d.mean(axis=0)
    ok = bool(np.all(np.abs(std - sigma) <= rel * sigma) and np.all(np.abs(mean) <= n_sigma_mean * sigma / math.sqrt(len(d))))
    return ok, std.tolist(), mean.tolist()


def check_noise(lib, n=100000):
    cfg = lib.config()
    truths = [constant_truth()] * n
    outs = run_sensors(lib, cfg, truths, seed=7)
    t = Truth.from_buffer_copy(truths[0])
    root = math.sqrt(1 / (2 * cfg.dt_s))
    b = D3()
    lib.lib.sks_sensors_magnetic_field_ned(C.byref(cfg), t.latitude_deg, t.longitude_deg, t.altitude_msl_m, b)
    res = {}
    res['accel'] = sigma_check(field(outs, 'accel_m_s2'), np.array(t.specific_force_body_m_s2[:]),
                               np.array(cfg.accel_noise_density[:]) * root)
    res['gyro'] = sigma_check(field(outs, 'gyro_rad_s'), 0.0, np.array(cfg.gyro_noise_density[:]) * root)
    res['mag'] = sigma_check(field(outs, 'magnetic_ut'), np.array(b[:]), np.array(cfg.mag_noise_ut[:]))
    res['baro'] = sigma_check(field(outs, 'absolute_pressure_pa'), t.static_pressure_pa, np.array([cfg.baro_noise_pa]))
    fixes = np.nonzero(field(outs, 'gps_updated')[:, 0])[0]
    gps = field(outs, 'gps_lla_msl')[fixes]
    lat0 = math.radians(t.latitude_deg)
    e2 = (1 / 298.257223563) * (2 - 1 / 298.257223563)
    rn = 6378137.0 / math.sqrt(1 - e2 * math.sin(lat0) ** 2)
    rm = rn * (1 - e2) / (1 - e2 * math.sin(lat0) ** 2)
    meters = np.column_stack([np.radians(gps[:, 0] - t.latitude_deg) * rm,
                              np.radians(gps[:, 1] - t.longitude_deg) * rn * math.cos(lat0), gps[:, 2] - t.altitude_msl_m])
    res['gps_position'] = sigma_check(meters, 0.0, np.array([cfg.gps_horizontal_noise_m] * 2 + [cfg.gps_vertical_noise_m]), rel=0.08)
    res['gps_velocity'] = sigma_check(field(outs, 'gps_velocity_ned_m_s')[fixes], np.array(t.velocity_ned_m_s[:]),
                                      np.array(cfg.gps_velocity_noise_m_s[:]), rel=0.08)
    dp = field(outs, 'differential_pressure_pa')[:, 0]
    res['diff_pressure_no_noise'] = (bool(np.all(dp == dp[0]) and abs(dp[0] - 0.5 * t.air_density_kg_m3 * 400.0) < 1e-9), [], [])
    ok = all(v[0] for v in res.values())
    return {'status': 'PASS' if ok else 'FAIL', 'samples': n, 'gps_fixes': int(len(fixes)),
            'channels': {k: {'pass': v[0], 'std': v[1], 'mean': v[2]} for k, v in res.items()}}


def check_vibration(lib, n=60000):
    cfg = lib.config(vibration_enabled=1)
    root = math.sqrt(1 / (2 * cfg.dt_s))
    on = run_sensors(lib, cfg, [constant_truth(throttle=0.5)] * n, seed=3)
    off = run_sensors(lib, cfg, [constant_truth(throttle=0.0)] * n, seed=3)
    acc_sigma = np.sqrt((np.array(cfg.accel_noise_density[:]) * root) ** 2 + np.array(cfg.vibration_accel_m_s2[:]) ** 2)
    gyr_sigma = np.sqrt((np.array(cfg.gyro_noise_density[:]) * root) ** 2 + np.array(cfg.vibration_gyro_rad_s[:]) ** 2)
    a = sigma_check(field(on, 'accel_m_s2'), np.array([0, 0, -G]), acc_sigma)
    g = sigma_check(field(on, 'gyro_rad_s'), 0.0, gyr_sigma)
    quiet = sigma_check(field(off, 'gyro_rad_s'), 0.0, np.array(cfg.gyro_noise_density[:]) * root)
    ok = a[0] and g[0] and quiet[0]
    return {'status': 'PASS' if ok else 'FAIL', 'accel_std': a[1], 'gyro_std': g[1], 'gyro_std_without_throttle': quiet[1]}


def check_rng(lib, truths):
    cfg = lib.config()
    a, b, c = run_sensors(lib, cfg, truths, seed=11), run_sensors(lib, cfg, truths, seed=11), run_sensors(lib, cfg, truths, seed=12)
    split = len(truths) // 2
    src = lib.sensors()
    assert lib.lib.sks_sensors_init(src, C.byref(cfg), 11) == 0
    first = []
    for x in truths[:split]:
        o = Output()
        lib.lib.sks_sensors_step(src, C.byref(Truth.from_buffer_copy(x)), C.byref(o))
        first.append(bytes(o))
    dst = lib.sensors()
    lib.lib.sks_sensors_copy(dst, src)
    rest = {0: [], 1: []}
    for x in truths[split:]:
        for i, s in enumerate((src, dst)):
            o = Output()
            lib.lib.sks_sensors_step(s, C.byref(Truth.from_buffer_copy(x)), C.byref(o))
            rest[i].append(bytes(o))
    result = {'same_seed_identical': a == b, 'other_seed_differs': a != c,
              'copy_continues': first + rest[0] == a and rest[1] == a[split:]}
    return {'status': 'PASS' if all(result.values()) else 'FAIL', **result}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--cache', type=Path, required=True)
    args = parser.parse_args()
    global MASS, G
    MASS, G = toolchain.model_constants(args.cache)
    library = args.cache / 'native' / toolchain.lib('skysurfer_plant')
    lib = Lib(library)
    result = {'library': str(library), 'self_test': check_self_test(), 'layout': check_layout()}
    if result['layout']['status'] != 'PASS' or result['self_test']['status'] != 'PASS':
        print(json.dumps(result, indent=2))
        return 1
    ref = load_reference_module()
    data = np.load(PLANT / 'reference' / 'data' / 'reference.npz')
    result['reference_build_id'] = json.loads((PLANT / 'reference' / 'data' / 'manifest.json').read_text())['model_build_id']
    result['truth'], result['consistency'], truths_by_case = check_truth(lib, ref, data)
    result['rejects'] = check_rejects(lib, ref)
    result['plant_state'] = check_plant_state(lib, ref, data, truths_by_case)
    result['geo'] = check_geo()
    result['wmm'] = check_wmm(lib)
    flight = truths_by_case['air_rudder_doublet'] + truths_by_case['air_banked_heading']
    result['ideal'] = check_ideal(lib, flight)
    result['noise'] = check_noise(lib)
    result['vibration'] = check_vibration(lib)
    result['rng'] = check_rng(lib, flight)
    result['boundaries'] = check_boundaries(lib, ref)
    checks = ['self_test', 'layout', 'truth', 'consistency', 'rejects', 'plant_state', 'geo', 'wmm', 'ideal', 'noise',
              'vibration', 'rng', 'boundaries']
    result['status'] = 'PASS' if all(result[c]['status'] == 'PASS' for c in checks) else 'FAIL'
    (args.cache / 'results' / 'plant_validation.json').write_text(json.dumps(result, indent=2))
    print(json.dumps({c: result[c]['status'] for c in checks} | {'status': result['status']}, indent=2))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
