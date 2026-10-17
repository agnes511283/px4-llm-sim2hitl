"""Stabilized roll/pitch/yaw stick steps after takeoff, then AUTO_LOITER (ROADMAP batch 4i).

The sequence comes from sitl/scenarios/stabilized_steps_hitl.json, read when the script is loaded, so the
HITL flight and its SITL preview use the same base sticks, settle time and steps. The pilot already flies
Stabilized in cruise; the base sticks hold the 15 m/s level trim of the SITL reference for settle_s, then
each step is added to them. Scenario sticks are manual_control_setpoint values (throttle -1..1) and must lie
on the 1/1000 MANUAL_CONTROL grid. analysis/response.py --hitl-log measures the sent step times afterwards.
"""
import json
from pathlib import Path

from commands.sequence import Mode, Sticks

ON_FINISH = 'loiter'
SCENARIO = Path(__file__).resolve().parents[2] / 'sitl' / 'scenarios' / 'stabilized_steps_hitl.json'


def sticks(values, seconds):
    for name, value in values.items():
        scaled = (value + 1) * 500 if name == 'throttle' else value * 1000
        if abs(scaled - round(scaled)) > 1e-6:
            raise ValueError(f'{name} stick {value} is not on the 1/1000 MANUAL_CONTROL grid')
    return Sticks(pitch=values['pitch'], roll=values['roll'], throttle=(values['throttle'] + 1) / 2,
                  seconds=seconds, yaw=values['yaw'])


def build_sequence():
    scenario = json.loads(SCENARIO.read_text())
    if scenario['mode'] != 'stabilized':
        raise ValueError('stabilized_steps needs a Stabilized scenario')
    if 'base' in scenario or 'base_sticks' not in scenario:
        # run_sitl.py adds "base" to the trim-derived sticks; HITL has no trim, so only absolute sticks are flown.
        raise ValueError('the HITL scenario must give absolute base_sticks and no "base" offsets')
    base = {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0, 'throttle': -1.0, **scenario['base_sticks']}
    settle = scenario['settle_s']
    actions, t = [], 0.0
    for step in sorted(scenario['steps'], key=lambda s: s['start_s']):
        start, end = settle + step['start_s'], settle + step['end_s']
        if not t < start < end:
            raise ValueError('scenario steps must be ordered, non-overlapping and after the start')
        actions.append(sticks(base, start - t))
        actions.append(sticks({k: base[k] + step.get(k, 0.0) for k in base}, end - start))
        t = end
    total = settle + scenario['duration_s']
    if total > t:
        actions.append(sticks(base, total - t))
    return actions + [Mode(4, 3, timeout=8.)]
