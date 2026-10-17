"""Standard checks and summaries for LLM (or human) operators.

Both return plain JSON-compatible dicts so every agent judges the same way.
Neither opens the serial port nor sends anything to the FC.
"""

import csv
import glob
import json
import platform
import subprocess
from pathlib import Path

from .policy import policy
from .ipc import request, state_path


def _check(name, ok, detail):
    return {'name': name, 'ok': bool(ok), 'detail': detail}


def _holders(port):
    """Processes that have the serial device open (lsof), as 'name(pid)'."""
    try:
        out = subprocess.run(['lsof', '-Fpc', port], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    holders, pid = [], None
    for line in out.splitlines():
        if line.startswith('p'):
            pid = line[1:]
        elif line.startswith('c') and pid:
            holders.append(f'{line[1:]}({pid})')
    return holders


def preflight(runtime, port='auto', fake_state_dir=None):
    runtime = Path(runtime)
    checks = []
    if fake_state_dir is None:
        devices = sorted(glob.glob('/dev/cu.usbmodem*')) if platform.system() == 'Darwin' else []
        target = devices[0] if port == 'auto' and devices else port
        checks.append(_check('serial_device', target in devices, {'found': devices, 'port': target}))
        holders = _holders(target) if target in devices else []
        checks.append(
            _check(
                'serial_free',
                holders == [],
                {'holders': holders, 'hint': 'QGC must use UDP, not the USB serial'} if holders else {'holders': holders},
            )
        )
    state = state_path(runtime, fake_state_dir)
    owner = None
    if (state / 'host.json').exists():
        try:
            result = request(runtime, 'status', fake_state_dir=fake_state_dir, timeout_s=3)
            if result.get('status') == 'complete':
                owner = result['result']
        except (OSError, ValueError, RuntimeError):
            owner = None
    busy = bool(owner and (owner.get('model') == 'running' or owner.get('pilot', {}).get('running')))
    checks.append(
        _check(
            'no_active_run',
            not busy,
            {
                'owner': bool(owner),
                'model': owner.get('model') if owner else None,
                'pilot_running': owner.get('pilot', {}).get('running') if owner else None,
            },
        )
    )
    marker = state / 'recovery.json'
    pending = json.loads(marker.read_text()).get('pending', True) if marker.exists() else False
    # Pending is not a blocker for test-takeoff-hold (it recovers first), only information.
    checks.append(_check('recovery_marker', True, {'pending': pending}))
    from .release import read_release

    try:
        _, manifest = read_release(runtime)
        checks.append(_check('active_release', True, {'build_id': manifest['build_id']}))
    except (OSError, ValueError, KeyError) as exc:
        checks.append(_check('active_release', False, str(exc)))
    return {'ready': all(c['ok'] for c in checks), 'checks': checks}


def flight_summary(directory):
    """Judge a finished test-takeoff-hold directory against agent_policy.json."""
    directory = Path(directory)
    config = policy()
    criteria, baseline = config['pass_criteria'], config['baseline']
    result = json.loads((directory / 'result.json').read_text())
    # The test's own host writes <dir>/host; with an existing (GUI) owner the logs stay in the owner's
    # directory and only the byte range [timing_start, timing_end) of its timing.csv belongs to this test.
    host = result.get('host_log') or {}
    host_dir = Path(host['dir']) if host.get('dir') else directory / 'host'
    final_file = host_dir / 'final_status.json'
    if final_file.exists() and not host.get('shared_owner'):
        final, ending_source = json.loads(final_file.read_text()), 'final_status.json'
    else:
        # The owner is still running: its status right after the test's recover.
        final, ending_source = result.get('after_recovery') or {}, 'result.json after_recovery'
    last = result.get('last_flight_status') or {}
    metrics = last.get('metrics', {})
    orbit = result.get('orbit', {})
    lateness = []
    with (host_dir / 'timing.csv').open('rb') as stream:
        start, end = host.get('timing_start'), host.get('timing_end')
        if start is not None:
            stream.seek(start)
        text = stream.read(None if end is None or start is None else end - start).decode()
    steps = []
    for row in csv.reader(text.splitlines()):
        if len(row) > 2 and row[0].isdigit() and row[2].lstrip('-').isdigit():
            steps.append(int(row[0]))
            lateness.append(int(row[2]))
    lateness.sort()
    late_steps = sum(x >= 4_000_000 for x in lateness)
    flight = {
        'flight_seconds': result.get('flight_seconds'),
        'hold_seconds': result.get('hold_seconds'),
        'turns': orbit.get('turns'),
        'radius_m': orbit.get('radius_m'),
        'radius_std_m': orbit.get('radius_std_m'),
        'height_min_m': orbit.get('height_min_m'),
        'height_max_m': orbit.get('height_max_m'),
        'airspeed_min_m_s': orbit.get('airspeed_min_m_s'),
    }
    timing = {
        'steps': len(lateness),
        'late_steps': late_steps,
        'lateness_p99_us': lateness[int(0.99 * len(lateness))] / 1e3 if lateness else None,
        'lateness_max_us': lateness[-1] / 1e3 if lateness else None,
    }
    transport = {
        key: metrics.get(key)
        for key in [
            'serial_errors',
            'serial_max_write_ms',
            'native_sensor_replacements',
            'native_log_drops',
            'tx_HIL_SENSOR',
            'tx_HIL_GPS',
        ]
    }
    ending = {
        'recovery': final.get('recovery'),
        'recovery_required': final.get('recovery_required'),
        'armed': final.get('fc', {}).get('armed'),
        'SYS_HITL': final.get('fc', {}).get('SYS_HITL'),
        'force_disarm_used': final.get('recovery_details', {}).get('force_disarm_used'),
    }
    failures = []
    for key in ['status', 'flight', 'recovery']:
        if result.get(key) != 'PASS':
            failures.append(f'{key} = {result.get(key)}')
    if (flight['hold_seconds'] or 0) < criteria['hold_seconds_min']:
        failures.append('hold shorter than %s s' % criteria['hold_seconds_min'])
    if (flight['turns'] or 0) < criteria['turns_min']:
        failures.append('fewer than %s orbit' % criteria['turns_min'])
    # The timing evidence must be the whole run: consecutive step indices, as many as the model produced.
    expected = (result.get('after_model_stop') or {}).get('produced_steps')
    if not steps:
        failures.append('timing log empty')
    elif steps != list(range(steps[0], steps[0] + len(steps))):
        failures.append('timing log steps not consecutive')
    elif expected is not None and len(steps) != expected:
        failures.append(f'timing log has {len(steps)} steps, the model produced {expected}')
    if late_steps > criteria['late_steps_max']:
        failures.append(f'{late_steps} steps late by >= 4 ms')
    # The App Nap guard must have been taken with this run's model start (absent in older results).
    if ((result.get('after_model_stop') or {}).get('scheduler') or {}).get('activity_run_ok') is False:
        failures.append('App Nap guard not held during the run')
    if (transport['serial_errors'] or 0) > criteria['serial_errors_max']:
        failures.append('serial errors')
    if (transport['native_log_drops'] or 0) > criteria['log_drops_max']:
        failures.append('log drops')
    if ending['recovery_required'] is not False or ending['armed'] is not False or ending['SYS_HITL'] != 1:
        failures.append('PX4 not confirmed recovered (pending/armed/SYS_HITL)')
    compare = {}
    for key, source in [
        ('hold_seconds', flight),
        ('turns', flight),
        ('radius_m', flight),
        ('height_min_m', flight),
        ('height_max_m', flight),
        ('lateness_max_us', timing),
        ('serial_max_write_ms', transport),
    ]:
        value = source.get(key)
        compare[key] = {
            'now': value,
            'baseline': baseline.get(key),
            'delta': None if value is None or baseline.get(key) is None else round(value - baseline[key], 3),
        }
    return {
        'verdict': 'FAIL' if failures else 'PASS',
        'failures': failures,
        'directory': str(directory),
        'host_log': str(host_dir),
        'ending_source': ending_source,
        'build_id': last.get('build_id'),
        'runtime_source_id': last.get('runtime_identity', {}).get('source_id'),
        'flight': flight,
        'timing': timing,
        'transport': transport,
        'ending': ending,
        'baseline_compare': compare,
        'notes': [
            'force_disarm_used=true is expected: the pilot ends airborne and armed, so normal disarm is rejected (result 1).'
        ]
        if ending['force_disarm_used']
        else [],
    }
