"""The wind of a run: one description for SITL (sitl/run_sitl.py) and HITL (hitl/aircraft/<aircraft>/scenario.py).

Scenario / scene field "wind" (all keys optional; nothing given = still air, as before):

  "wind": {
    "steady_ned_m_s": [n, e, d],       steady wind: NED velocity of the air (direction it blows TO), m/s
    "start": {"mode": "after_airborne" | "at_time" | "from_start",   default after_airborne
              "height_m": 5, "time_s": 0, "ramp_s": 5},
    "gust":  {"start_s": 0, "length_m": [120, 120, 80], "magnitude_m_s": [0, 0, 0]},
    "shear": {"speed_6m_m_s": 0, "from_deg": 0},
    "turbulence": {"speed_6m_m_s": 0, "from_deg": <shear from_deg>, "seed": [23341, 23342, 23343, 23344]}
  }

How the model uses it (plant/README.md "Wind"): two modes of the source model. Steady wind only, or shear
(mean wind growing with height, given at 6 m) + discrete gust + Dryden turbulence; any non-zero gust, shear or
turbulence selects the second and the steady wind is then not used. The wind starts when the start condition
is met; steady speed, shear speed and turbulence ramp up over ramp_s; the gust starts start_s after the start.

parse() returns (config, reminders): config has the HilWindConfig field names (hil_model_api.h); reminders are
plain sentences for the human (risks and model limits). Remind, don't block: only malformed input raises.
"""
import math

START_MODES = {'after_airborne': 0, 'at_time': 1, 'from_start': 2}
DEFAULT_SEED = [23341, 23342, 23343, 23344]
KEYS = {'steady_ned_m_s', 'start', 'gust', 'shear', 'turbulence'}
SUB_KEYS = {'start': {'mode', 'height_m', 'time_s', 'ramp_s'}, 'gust': {'start_s', 'length_m', 'magnitude_m_s'},
            'shear': {'speed_6m_m_s', 'from_deg'}, 'turbulence': {'speed_6m_m_s', 'from_deg', 'seed'}}


def _number(value, name, lo=-math.inf, hi=math.inf):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lo <= value <= hi:
        raise ValueError(f'wind {name} must be a finite number in [{lo}, {hi}]')
    return float(value)


def _vector(value, name, lo=-math.inf, hi=math.inf):
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(f'wind {name} must be a list of 3 numbers')
    return [_number(v, name, lo, hi) for v in value]


def default_config():
    return {'steady_ned_m_s': [0.0, 0.0, 0.0], 'start_mode': 0, 'start_height_m': 5.0, 'start_time_s': 0.0,
            'ramp_s': 5.0, 'gust_start_s': 0.0, 'gust_length_m': [120.0, 120.0, 80.0], 'gust_magnitude_m_s': [0.0, 0.0, 0.0],
            'shear_speed_6m_m_s': 0.0, 'shear_from_deg': 0.0, 'turbulence_speed_6m_m_s': 0.0, 'turbulence_from_deg': 0.0,
            'turbulence_seed': list(DEFAULT_SEED)}


def parse(wind, ground_start=True):
    """wind: the "wind" object (or None). ground_start: the run starts on the ground (HITL always does)."""
    config, reminders = default_config(), []
    if wind is None:
        return config, reminders
    if not isinstance(wind, dict):
        raise ValueError('wind must be an object')
    unknown = set(wind) - KEYS
    if unknown:
        raise ValueError('unknown wind fields: ' + ', '.join(sorted(unknown)))
    for key, allowed in SUB_KEYS.items():
        part = wind.get(key, {})
        if not isinstance(part, dict) or set(part) - allowed:
            raise ValueError(f'wind {key} must be an object with fields {sorted(allowed)}')
    if 'steady_ned_m_s' in wind:
        config['steady_ned_m_s'] = _vector(wind['steady_ned_m_s'], 'steady_ned_m_s', -100, 100)
    start = wind.get('start', {})
    mode = start.get('mode', 'after_airborne')
    if mode not in START_MODES:
        raise ValueError('wind start mode must be one of ' + ', '.join(START_MODES))
    config['start_mode'] = START_MODES[mode]
    config['start_height_m'] = _number(start.get('height_m', 5.0), 'start height_m', 0, 10000)
    config['start_time_s'] = _number(start.get('time_s', 0.0), 'start time_s', 0)
    config['ramp_s'] = _number(start.get('ramp_s', 5.0), 'start ramp_s', 0, 600)
    gust = wind.get('gust', {})
    config['gust_start_s'] = _number(gust.get('start_s', 0.0), 'gust start_s', 0)
    if 'length_m' in gust:
        config['gust_length_m'] = _vector(gust['length_m'], 'gust length_m', 1e-3, 1e5)
    if 'magnitude_m_s' in gust:
        config['gust_magnitude_m_s'] = _vector(gust['magnitude_m_s'], 'gust magnitude_m_s', -50, 50)
    shear = wind.get('shear', {})
    config['shear_speed_6m_m_s'] = _number(shear.get('speed_6m_m_s', 0.0), 'shear speed_6m_m_s', 0, 50)
    config['shear_from_deg'] = _number(shear.get('from_deg', 0.0), 'shear from_deg', -360, 360)
    turbulence = wind.get('turbulence', {})
    config['turbulence_speed_6m_m_s'] = _number(turbulence.get('speed_6m_m_s', 0.0), 'turbulence speed_6m_m_s', 0, 50)
    config['turbulence_from_deg'] = _number(turbulence.get('from_deg', config['shear_from_deg']), 'turbulence from_deg', -360, 360)
    seed = turbulence.get('seed', DEFAULT_SEED)
    if (not isinstance(seed, list) or len(seed) != 4 or
            any(isinstance(s, bool) or not isinstance(s, int) or not 0 <= s < 2 ** 31 for s in seed)):
        raise ValueError('wind turbulence seed must be 4 integers in [0, 2^31)')
    config['turbulence_seed'] = list(seed)

    steady = config['steady_ned_m_s']
    low_altitude = (any(config['gust_magnitude_m_s']) or config['shear_speed_6m_m_s'] > 0 or
                    config['turbulence_speed_6m_m_s'] > 0)
    if steady[2] != 0:
        reminders.append('The vertical part of the steady wind is ignored: the model has a horizontal steady wind only.')
    if low_altitude and any(steady):
        reminders.append('The steady wind is not used: with shear, gust or turbulence the model takes its mean wind '
                         'from the shear model (speed at 6 m, growing with height).')
    if ground_start and config['start_mode'] != 0 and (low_altitude or any(steady[:2])):
        reminders.append('The wind may start while the aircraft is still on the ground: a crosswind turns and tips it '
                         'over (about 68 deg of roll at 10 m/s in a test), and PX4 sees airspeed on the ground '
                         '(preflight checks, EKF). The default start is after_airborne.')
    if any(config['gust_magnitude_m_s']):
        reminders.append('The discrete gust rises (1 - cos) over its length and then stays at its magnitude for the rest '
                         'of the run; a vertical gust is a lasting up- or downdraft.')
    if config['turbulence_speed_6m_m_s'] > 0:
        reminders.append('Turbulence is the Dryden model scaled from its reference W20 = 1 m/s: exact below 1000 ft '
                         '(305 m), not above. For other heights or the exact intensity, regenerate the core with the '
                         'wanted W20 (plant/README.md "Wind").')
    if config['start_mode'] == 0 and not ground_start and config['start_height_m'] > 0:
        reminders.append('This run starts in the air: "after_airborne" starts the wind at the first step '
                         '(ramp_s still applies).')
    return config, reminders


def sitl_line(config):
    """The plant_sim scenario line (PlantSim::load_scenario)."""
    c = config
    values = (c['steady_ned_m_s'] + [c['start_mode'], c['start_height_m'], c['start_time_s'], c['ramp_s'], c['gust_start_s']]
              + c['gust_length_m'] + c['gust_magnitude_m_s']
              + [c['shear_speed_6m_m_s'], c['shear_from_deg'], c['turbulence_speed_6m_m_s'], c['turbulence_from_deg']]
              + c['turbulence_seed'])
    return 'wind ' + ' '.join(f'{v:.12g}' for v in values)
