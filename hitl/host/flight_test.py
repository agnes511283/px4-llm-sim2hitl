"""Bounded takeoff -> PX4 Hold -> stopped-model HIL recovery via the sole owner."""

import json
import math
from pathlib import Path
import subprocess
import sys
import time

import numpy as np

from .ipc import request, state_path


def mode(status):
    value = status['fc'].get('custom_mode') or 0
    return ((value >> 16) & 255, (value >> 24) & 255)


def orbit_metrics(samples):
    """Fit the observed horizontal path, then measure travel around its centre."""
    if len(samples) < 20:
        return {'samples': len(samples), 'turns': 0.0}
    points = np.array([[s['north_m'], s['east_m']] for s in samples])
    origin = points.mean(axis=0)
    q = points - origin
    matrix = np.column_stack((2 * q, np.ones(len(q))))
    if np.linalg.matrix_rank(matrix) < 3:
        return {'samples': len(samples), 'turns': 0.0, 'reason': 'path is not a circle'}
    fit = np.linalg.lstsq(matrix, (q * q).sum(axis=1), rcond=None)[0]
    centre = origin + fit[:2]
    radii = np.linalg.norm(points - centre, axis=1)
    angles = np.unwrap(np.arctan2(points[:, 1] - centre[1], points[:, 0] - centre[0]))
    return {
        'samples': len(samples),
        'turns': float(abs(angles[-1] - angles[0]) / (2 * math.pi)),
        'radius_m': float(np.mean(radii)),
        'radius_std_m': float(np.std(radii)),
        'centre_north_m': float(centre[0]),
        'centre_east_m': float(centre[1]),
        'height_min_m': min(s['height_m'] for s in samples),
        'height_max_m': max(s['height_m'] for s in samples),
        'airspeed_min_m_s': min(s['airspeed_m_s'] for s in samples),
    }


def run_test(runtime, args):
    runtime = Path(runtime).resolve()
    for name in ('altitude', 'hold_seconds', 'hold_timeout', 'flight_timeout'):
        value = getattr(args, name)
        if not math.isfinite(value) or value <= 0:
            raise ValueError(name + ' must be finite and positive')
    if not 20 <= args.altitude <= 500 or args.hold_timeout < args.hold_seconds:
        raise ValueError('Altitude must be 20..500 m; hold-timeout must cover hold-seconds')
    from .policy import flight_test_overrides

    # Non-standard values run (consent is given in the conversation) and are recorded in the report.
    overrides = flight_test_overrides(args)
    out = args.log_dir or state_path(runtime, args.fake_state_dir) / (
        'takeoff-hold-' + time.strftime('%Y%m%d_%H%M%S')
    )
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if (out / 'result.json').exists():
        raise ValueError('Use a new output directory; an earlier result already exists')
    report = {
        'schema_version': 1,
        'status': 'RUNNING',
        'flight': 'NOT_RUN',
        'recovery': 'NOT_RUN',
        'scope': 'fake management only' if args.fake_fc else 'physical PX4 HIL takeoff and Hold',
        'target_altitude_local_m': args.altitude,
        'nonstandard_parameters': {k: {'requested': v[0], 'standard': v[1]} for k, v in overrides.items()},
        'hold_min_seconds': args.hold_seconds,
        'hold_timeout_s': args.hold_timeout,
        'flight_timeout_s': args.flight_timeout,
        'force_disarm_policy': 'stopped HIL only, after explicit normal-disarm rejection',
        'output': str(out),
    }
    owned_host = None
    console = None
    started = False
    host_available = False
    samples = []
    started_at = time.monotonic()

    def call(action, arguments=None):
        response = request(
            runtime,
            action,
            arguments,
            fake_state_dir=args.fake_state_dir,
            timeout_s=1800 if action == 'fetch-log' else 90 if action == 'recover' else 45,
        )
        with (out / 'operations.jsonl').open('a') as stream:
            stream.write(
                json.dumps(
                    {
                        'time_s': time.monotonic() - started_at,
                        'action': action,
                        'response': response,
                    }
                )
                + '\n'
            )
        if response['status'] != 'complete':
            raise RuntimeError(
                response.get('error') or response.get('operation', {}).get('error') or str(response)
            )
        return response.get('result', response)

    def observe():
        status = call('status')
        with (out / 'status.jsonl').open('a') as stream:
            stream.write(
                json.dumps(
                    {'time_s': time.monotonic() - started_at, 'status': status}, allow_nan=False
                )
                + '\n'
            )
        return status

    try:
        try:
            initial = call('status')
        except (OSError, RuntimeError):
            command = [
                sys.executable,
                '-B',
                str(runtime / 'main.py'),
                'bridge',
                '--headless',
                '--port',
                args.port,
                '--log-dir',
                str(out / 'host'),
            ]
            if args.fake_fc:
                command += ['--fake-fc']
                if args.fake_state_dir:
                    command += ['--fake-state-dir', str(args.fake_state_dir)]
                if args.fake_config:
                    command += ['--fake-config', str(args.fake_config)]
            console = (out / 'host_console.log').open('w')
            owned_host = subprocess.Popen(command, stdout=console, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 12
            while True:
                if owned_host.poll() is not None:
                    raise RuntimeError(
                        'Host startup failed: ' + (out / 'host_console.log').read_text()
                    )
                try:
                    initial = call('status')
                    break
                except (OSError, RuntimeError):
                    if time.monotonic() >= deadline:
                        raise RuntimeError('HIL host startup timed out')
                    time.sleep(0.1)
        host_available = True
        if bool(initial.get('fake_fc')) != bool(args.fake_fc):
            # The owner says what it drives: --fake-fc never reaches a real FC (it skips the dialog above).
            raise RuntimeError(f'owner fake_fc={initial.get("fake_fc")} but this test was started with '
                               f'fake_fc={args.fake_fc}; refused before any flight command')
        # Where this test's host logs are: our own host writes <out>/host; an existing (GUI) owner keeps its own
        # log directory for the whole session, so flight-summary reads only this test's part of timing.csv.
        host_dir = Path(initial.get('log_dir') or out / 'host')
        report['host_log'] = {'dir': str(host_dir), 'shared_owner': owned_host is None}

        def timing_size():
            file = host_dir / 'timing.csv'
            return file.stat().st_size if file.exists() else 0

        def wire_size():
            # This run's records of the owner's wire.bin lie between these sizes (hitl-run checks them): the
            # native counters restart at every reconnection, so a count cannot place a run in the session file.
            file = host_dir / 'wire.bin'
            return file.stat().st_size if file.exists() else 0

        if initial.get('unarmed_only'):
            raise RuntimeError('Existing owner is restricted to unarmed validation')
        if initial['model'] == 'running' or initial.get('pilot', {}).get('running'):
            raise RuntimeError(
                'Another model/pilot run is active; test does not take ownership of it'
            )
        deadline = time.monotonic() + 45
        while True:
            status = observe()
            if (
                status['fc']['state'] == 'verified'
                and status['fc']['SYS_HITL'] == 1
                and status['fc']['identity'] == [1, 1]
                and status['fc']['heartbeat_age_s'] is not None
                and status['fc']['heartbeat_age_s'] <= 3
            ):
                break
            if time.monotonic() >= deadline:
                raise RuntimeError('Fresh fixed-wing PX4 1/1 with SYS_HITL=1 not available')
            time.sleep(0.1)
        call(
            'read-parameters',
            {
                'names': [
                    'SYS_AUTOSTART',
                    'NAV_LOITER_RAD',
                    'NAV_MIN_LTR_ALT',
                    'FW_AIRSPD_MIN',
                    'FW_AIRSPD_TRIM',
                    'CA_SV_CS0_TYPE',
                    'CA_SV_CS1_TYPE',
                    'CA_SV_CS2_TYPE',
                    'CA_SV_CS3_TYPE',
                ]
            },
        )
        time.sleep(0.5)
        report['before'] = observe()
        # Every HIL test begins with a PX4 reboot, even after a clean prior recovery.
        call('recover', {'hil_force_disarm': True})
        report['initial_recovery'] = observe()
        # The FC's newest log before this flight: the log fetched afterwards must be a newer one (this flight's).
        try:
            listed = call('fetch-log', {'list': True})
            report['fc_log_before'] = (listed.get('operation', {}).get('result') or {}).get('newest_id')
        except Exception as exc:
            report['fc_log_before'] = None
            report['fc_log_list_error'] = str(exc)
        report['host_log']['timing_start'] = timing_size()
        report['host_log']['wire_start'] = wire_size()
        call('model-start', {'scene': json.loads((runtime / 'scenarios/ground.json').read_text())})
        started = True
        call(
            'takeoff',
            {
                'argv': [
                    '--altitude',
                    str(args.altitude),
                    '--after',
                    'after_takeoff_loiter',
                    '--record',
                ]
            },
        )
        flight_start = time.monotonic()
        hold_start = None
        while True:
            status = observe()
            now = time.monotonic()
            if status['model'] != 'running':
                raise RuntimeError(status['last_error'] or 'Model stopped during flight')
            if status['fc']['heartbeat_age_s'] is None or status['fc']['heartbeat_age_s'] > 3:
                raise RuntimeError('FC heartbeat stale')
            if mode(status) == (10, 0):
                raise RuntimeError('PX4 termination during flight')
            pilot = status.get('pilot', {})
            if pilot.get('phase') == 'failed':
                raise RuntimeError(status['last_error'] or pilot.get('reason', 'Pilot failed'))
            if now - flight_start > args.flight_timeout:
                raise RuntimeError('Whole flight timeout')
            handed_over = (
                mode(status) == (4, 3)
                and pilot.get('after_state') == 'complete'
                and pilot.get('running')
                and pilot.get('state') == 'loiter'
            )
            if handed_over:
                if hold_start is None:
                    hold_start = now
                    report['hold_entry'] = status
                    print(
                        'PX4 AUTO_LOITER confirmed; observing the orbit',
                        file=sys.stderr,
                        flush=True,
                    )
                if not status['fc']['armed']:
                    raise RuntimeError('PX4 disarmed during Hold')
                needed = ('LOCAL_POSITION_NED', 'ATTITUDE', 'VFR_HUD')
                if any(
                    k not in status['telemetry'] or status['telemetry'][k]['stale'] for k in needed
                ):
                    raise RuntimeError('Hold telemetry stale')
                position = status['telemetry']['LOCAL_POSITION_NED']['values']
                airspeed = status['telemetry']['VFR_HUD']['values']['airspeed_m_s']
                sample = dict(
                    time_s=now - hold_start,
                    north_m=position['north_m'],
                    east_m=position['east_m'],
                    height_m=position['height_local_m'],
                    airspeed_m_s=airspeed,
                )
                if not all(v is not None and math.isfinite(v) for v in sample.values()):
                    raise RuntimeError('Non-finite Hold telemetry')
                samples.append(sample)
                metrics = orbit_metrics(samples)
                if now - hold_start >= args.hold_seconds and metrics['turns'] >= 1.0:
                    report['orbit'] = metrics
                    if (
                        max(
                            abs(metrics['height_min_m'] - args.altitude),
                            abs(metrics['height_max_m'] - args.altitude),
                        )
                        > 15
                    ):
                        raise RuntimeError('Hold height left the target +/-15 m acceptance band')
                    report['flight'] = 'PASS'
                    report['flight_seconds'] = now - flight_start
                    report['hold_seconds'] = now - hold_start
                    report['last_flight_status'] = status
                    break
                if now - hold_start >= args.hold_timeout:
                    report['orbit'] = metrics
                    raise RuntimeError(
                        'Hold orbit observation timed out before completing a circle'
                    )
            elif hold_start is not None:
                raise RuntimeError('PX4 left AUTO_LOITER after handover')
            elif not pilot.get('running') and pilot.get('phase') == 'ended':
                raise RuntimeError('Pilot ended without confirmed AUTO_LOITER handover')
            time.sleep(0.2)
    except KeyboardInterrupt:
        report['flight'] = 'FAIL'
        report['error'] = 'User interrupted test'
    except Exception as exc:
        report['flight'] = 'FAIL'
        report['error'] = str(exc)
    finally:
        if started and host_available:
            try:
                try:
                    call('model-stop')
                except Exception as exc:
                    report['model_stop_error'] = str(exc)
                stopped = time.monotonic()
                report['after_model_stop'] = observe()
                # model-stop returns after the owner's log barrier (Core.flush_logs): timing.csv is complete.
                report['host_log']['timing_end'] = timing_size()
                report['host_log']['wire_end'] = wire_size()
                if (
                    report['after_model_stop']['model'] == 'running'
                    or report['after_model_stop']['pilot']['running']
                ):
                    raise RuntimeError(
                        'Model or pilot remains active; recovery cannot force-disarm'
                    )
                deadline = stopped + 10
                report['termination_observed'] = False
                while time.monotonic() < deadline:
                    status = observe()
                    if mode(status) == (10, 0):
                        report['termination_observed'] = True
                        report['termination'] = status
                        break
                    if status['fc']['armed'] is False:
                        break
                    time.sleep(0.2)
                call('recover', {'hil_force_disarm': True})
                report['after_recovery'] = observe()
                report['recovery'] = (
                    'PASS' if report['after_recovery']['ready_after_recovery'] else 'FAIL'
                )
                # The FC ULog of this flight (newest log; SDLOG_MODE 0 logs from arm to disarm). Evidence
                # only: a failed download is reported but does not change the test verdict.
                try:
                    response = call('fetch-log', {'out': str(out / 'fc_log')})
                    report['fc_log'] = (response.get('operation', {}).get('result')
                                        if response.get('status') == 'complete'
                                        else {'error': response.get('operation', {}).get('error')
                                              or response.get('error')})
                    before = report.get('fc_log_before')
                    if 'id' in report['fc_log'] and (before is None or report['fc_log']['id'] <= before):
                        # Not provably this flight's log (no newer log than before the flight).
                        report['fc_log']['error'] = (f'fetched log {report["fc_log"]["id"]} is not newer than '
                                                     f'the newest log before the flight ({before})')
                except Exception as exc:
                    report['fc_log'] = {'error': str(exc)}
            except Exception as exc:
                report['recovery'] = 'FAIL'
                report['recovery_error'] = str(exc)
        if owned_host is not None:
            if owned_host.poll() is None:
                try:
                    call('shutdown', {'force': True})
                except Exception as exc:
                    report['host_shutdown_error'] = str(exc)
                try:
                    owned_host.wait(timeout=12)
                except subprocess.TimeoutExpired:
                    owned_host.terminate()
                    owned_host.wait(timeout=5)
            report['host_exit_code'] = owned_host.poll()
        if console:
            console.close()
        (out / 'hold_samples.json').write_text(json.dumps(samples, indent=2))
        report['wall_seconds'] = time.monotonic() - started_at
        report['status'] = (
            'PASS' if report['flight'] == 'PASS' and report['recovery'] == 'PASS' else 'FAIL'
        )
        (out / 'result.json').write_text(json.dumps(report, indent=2, allow_nan=False))
        print(
            json.dumps(
                {
                    k: report.get(k)
                    for k in ('status', 'flight', 'recovery', 'error', 'recovery_error', 'output')
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    return 0 if report['status'] == 'PASS' else 3
