"""One traceable automatic HITL run (hitl-run): identity and parameters before, the fixed test-takeoff-hold,
identity, parameters, FC log and data after, and manifest.json with a verdict that a flight PASS cannot
override (BEHAVIOR_CONTRACT 7e)."""

import contextlib
import hashlib
import importlib.util
import json
import os
import struct
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

from pymavlink.dialects.v20 import common as mav
from pymavlink.generator.mavcrc import x25crc

from .ipc import cache_root, request
from . import runtime_identity

DEFAULT_OUT = cache_root() / 'hitl_runs'
DEFAULT_RELEASE = 'deploy/00_native'
SCENARIO = 'takeoff_hold'
EXIT = {'PASS': 0, 'FAIL': 3, 'INCOMPLETE': 5, 'NOT_RUN': 2}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def combine(verdicts):
    """FAIL beats INCOMPLETE beats PASS: a flight PASS never hides missing or wrong evidence."""
    verdicts = list(verdicts)
    return 'FAIL' if 'FAIL' in verdicts else 'INCOMPLETE' if 'INCOMPLETE' in verdicts else 'PASS'


def checker(project):
    spec = importlib.util.spec_from_file_location('skysurfer_check_params', Path(project) / 'deploy/check_params.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HIL_SENSOR = 107
SENSOR_CHANNEL = 2  # wire.bin channel of the native writer's HIL_SENSOR / HIL_GPS (1: bytes read from the FC)


def frame_valid(frame, v2, length, msgid):
    """A MAVLink frame whose checksum (with the message's CRC_EXTRA) is right; an unknown message id is not."""
    entry = mav.mavlink_map.get(msgid)
    if entry is None:
        return False
    end = (10 if v2 else 6) + length
    crc = x25crc(bytes(frame[1:end]))
    crc.accumulate(bytes([entry.crc_extra]))
    return crc.crc == frame[end] | frame[end + 1] << 8


def wire_slice(path, start, end):
    """One run's part of an owner's wire.bin (records '<QBI' stamp, channel, length + bytes; the owner's serial
    traffic of its whole session): the whole records that start at or after byte `start` and end at or before
    byte `end` (test-takeoff-hold takes the file size right before model-start and right after model-stop's log
    barrier). Every channel-2 byte of these records must belong to a valid MAVLink frame (magic, length, checksum
    with CRC_EXTRA, known message id), with nothing left over. Returns (range of the records or None,
    HIL_SENSOR frames, bad), bad = places in the channel-2 bytes that are no valid frame (other bytes, a wrong
    checksum, an unknown id, a frame cut off at the end)."""
    data = Path(path).read_bytes()
    first, last, buf, i = None, None, bytearray(), 0
    while i + 13 <= len(data):
        _, channel, n = struct.unpack_from('<QBI', data, i)
        if i + 13 + n > len(data):
            break  # a record still being written
        if i >= start and i + 13 + n <= end:
            first = i if first is None else first
            last = i + 13 + n
            if channel == SENSOR_CHANNEL:
                buf += data[i + 13:i + 13 + n]
        i += 13 + n
    sensors, bad, j = 0, 0, 0
    while j < len(buf):
        if buf[j] not in (0xFD, 0xFE):
            bad += 1  # bytes that start no frame
            while j < len(buf) and buf[j] not in (0xFD, 0xFE):
                j += 1
            continue
        v2 = buf[j] == 0xFD
        if j + (10 if v2 else 6) > len(buf):
            bad += 1  # a header cut off at the end
            break
        total = (12 + buf[j + 1] + (13 if buf[j + 2] & 1 else 0)) if v2 else 8 + buf[j + 1]
        if j + total > len(buf):
            bad += 1  # a frame cut off at the end
            break
        msgid = (buf[j + 7] | buf[j + 8] << 8 | buf[j + 9] << 16) if v2 else buf[j + 5]
        if not frame_valid(buf[j:j + total], v2, buf[j + 1], msgid):
            bad += 1
            j += 1
            continue
        sensors += msgid == HIL_SENSOR
        j += total
    return (None if first is None else (first, last)), sensors, bad


def readback_values(path):
    return {p['name']: p for p in json.loads(Path(path).read_text())['parameters']}


def run_hitl(runtime, args):
    runtime = Path(runtime).resolve()
    project = runtime.parent
    policy = json.loads((project / 'agent_policy.json').read_text())
    fixed = policy['flight_test']
    flight = {'altitude': args.altitude, 'hold_seconds': args.hold_seconds, 'hold_timeout': args.hold_timeout,
              'flight_timeout': args.flight_timeout}
    flight = {k: (fixed[k] if v is None else v) for k, v in flight.items()}
    if not args.fake_fc and flight != {k: fixed[k] for k in flight}:
        # The fixed flight is what makes hitl-run tier B; any other flight is test-takeoff-hold (tier C).
        raise ValueError('hitl-run uses only the fixed flight parameters of agent_policy.json on a real FC')
    release = (Path(args.release) if args.release else project / DEFAULT_RELEASE).resolve()
    out = (Path(args.out) if args.out else DEFAULT_OUT).resolve()
    run = out / f'run_{time.strftime("%Y%m%d_%H%M%SZ", time.gmtime())}_{uuid.uuid4().hex[:8]}'
    run.mkdir(parents=True)
    started = time.monotonic()
    pilot_files = ['hil_runtime/scenarios/ground.json', 'hil_bridge/autotakeoff/FW_SkySurfer_HIL_AutoTakeoff.py',
                   'hil_bridge/commands/after_takeoff_loiter.py']
    manifest = {
        'schema_version': 1,
        'kind': 'hitl-run',
        'run': run.name,
        'created_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'scope': 'fake FC' if args.fake_fc else 'physical PX4 HIL',
        'verdict': None,
        'reasons': [],
        'parts': {},
        'scenario': {'name': SCENARIO, 'flight': flight, 'files': None},
    }
    parts = manifest['parts']

    def part(name, verdict, reasons=(), **details):
        parts[name] = dict({'verdict': verdict, 'reasons': list(reasons)}, **details)

    def call(action, arguments=None, timeout_s=45):
        response = request(runtime, action, arguments, fake_state_dir=args.fake_state_dir, timeout_s=timeout_s)
        with (run / 'operations.jsonl').open('a') as stream:
            stream.write(json.dumps({'time_s': time.monotonic() - started, 'action': action,
                                     'arguments': arguments, 'response': response}, allow_nan=False) + '\n')
        return response

    def status():
        response = call('status')
        if response.get('status') != 'complete':
            raise RuntimeError('owner status failed: ' + str(response.get('error') or response))
        return response['result']

    def readback(name):
        """(params json path or None, readback verdict, error)."""
        response = call('param-readback', {'out': str(run / name)}, timeout_s=600)
        if response.get('status') != 'complete':
            return None, None, str(response.get('error') or response.get('operation', {}).get('error'))
        result = response['operation']['result']
        return result['path'], result['verdict'], None

    def finish():
        if manifest['verdict'] is None:
            manifest['verdict'] = 'NOT_RUN' if 'flight' not in parts else combine(p['verdict'] for p in parts.values())
        manifest['reasons'] = [f'{name}: {reason}' for name, p in parts.items() for reason in p['reasons']]
        manifest['finished_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        manifest['wall_seconds'] = round(time.monotonic() - started, 2)
        # Every file of the run with its SHA-256; a file that cannot be read is listed with its error and the run
        # is not PASS (the manifest is still written).
        files, unreadable = [], []
        try:
            paths = sorted(p for p in run.rglob('*') if p.is_file() and p.name not in ['manifest.json', 'manifest.tmp'])
        except OSError as exc:
            paths, unreadable = [], [f'the run directory cannot be listed ({exc})']
        for path in paths:
            try:
                files.append({'path': path.relative_to(run).as_posix(), 'sha256': sha256(path),
                              'size': path.stat().st_size})
            except OSError as exc:
                files.append({'path': path.relative_to(run).as_posix(), 'error': str(exc)})
                unreadable.append(f'{path.relative_to(run).as_posix()} cannot be read ({exc})')
        manifest['files'] = files
        if unreadable:
            manifest['reasons'] += [f'manifest: {reason}' for reason in unreadable]
            if manifest['verdict'] == 'PASS':
                manifest['verdict'] = 'INCOMPLETE'
        temp = run / 'manifest.tmp'
        temp.write_text(json.dumps(manifest, indent=1, ensure_ascii=False, allow_nan=False) + '\n')
        os.replace(temp, run / 'manifest.json')
        print(json.dumps({'verdict': manifest['verdict'], 'reasons': manifest['reasons'][:10],
                          'manifest': str(run / 'manifest.json')}, ensure_ascii=False), flush=True)
        return EXIT[manifest['verdict']]

    stage = ['identity']  # the part being checked, for a manifest even when something unexpected stops the run
    try:
        # Before: the owner runs the code on disk and the active model; the FC is ready; parameters as released.
        # Everything read from disk is inside this protection too (a missing scenario file: NOT_RUN, a manifest).
        manifest['scenario']['files'] = [{'path': p, 'sha256': sha256(project / p)} for p in pilot_files]
        try:
            start = status()
        except Exception as exc:
            part('identity', 'FAIL', [f'no running owner ({exc}); start ./runbridge.command gui first'])
            return finish()
        disk_id = runtime_identity.source_id(runtime_identity.inventory(project))
        owner = start.get('runtime_identity') or {}
        from .release import platform_id, read_release

        _, active = read_release(runtime)
        active_sha = json.loads((runtime / 'active' / f'{platform_id()}.json').read_text()).get('manifest_sha256')
        manifest['runtime'] = {'source_id_owner': owner.get('source_id'), 'source_id_disk': disk_id,
                               'instance_id': start.get('instance_id'), 'build_id': start.get('build_id'),
                               'model_manifest_sha256': owner.get('model_manifest_sha256'),
                               'active_build_id': active.get('build_id'), 'active_manifest_sha256': active_sha,
                               'log_dir': start.get('log_dir')}
        reasons = []
        if owner.get('source_id') != disk_id:
            reasons.append(f'owner runs {owner.get("source_id")}, the code on disk is {disk_id}: restart the owner')
        if start.get('build_id') != active.get('build_id') or owner.get('model_manifest_sha256') != active_sha:
            reasons.append(f'owner model {start.get("build_id")} is not the active release {active.get("build_id")}')
        fc = start.get('fc') or {}
        if fc.get('state') != 'verified' or fc.get('armed') is not False or fc.get('SYS_HITL') != 1:
            reasons.append(f'FC not ready (state {fc.get("state")}, armed {fc.get("armed")}, SYS_HITL {fc.get("SYS_HITL")})')
        if start.get('model') == 'running' or (start.get('pilot') or {}).get('running'):
            reasons.append('a model or pilot is running')
        if bool(start.get('fake_fc')) != bool(args.fake_fc):
            reasons.append(f'owner fake_fc={start.get("fake_fc")} but hitl-run fake_fc={args.fake_fc}: a real FC only '
                           'takes the fixed flight, and --fake-fc must not reach it')
        if start.get('recovery_required') or start.get('param_deploy_pending'):
            reasons.append('recovery or a parameter deploy is pending')
        part('identity', 'FAIL' if reasons else 'PASS', reasons)
        if reasons:
            return finish()

        stage[0] = 'params_before'
        check = checker(project)
        checker_sha = sha256(project / 'deploy/check_params.py')
        firmware_info = json.loads((release / json.loads((release / 'params.json').read_text())['firmware']).read_text())
        manifest['firmware'] = {'release': str(release), 'file': firmware_info['outputs']['firmware']['file'],
                                'sha256': firmware_info['outputs']['firmware']['sha256'],
                                'git_hash': firmware_info['embedded']['git_hash'],
                                'board_id': firmware_info['embedded']['board_id'],
                                'flashed': {k: (firmware_info.get('flashed') or {}).get(k) for k in ['status', 'at_utc']}}
        params = manifest['params'] = {'release_params_sha256': sha256(release / 'params.json'),
                                       'check_params_sha256': checker_sha}
        before_path, before_verdict, error = readback('params_before')
        reasons = []
        if error or before_verdict != 'PASS':
            reasons.append(f'readback before the flight is not PASS ({error or before_verdict})')
        else:
            report = check.check(release, before_path)
            params['before'] = {'path': str(Path(before_path).relative_to(run)), 'sha256': sha256(before_path),
                                'check': report['verdict']}
            if report['verdict'] != 'PASS':
                problems = {k: v[:5] for k, v in report.items() if isinstance(v, list) and v and k != 'not_default'}
                reasons.append(f'parameters are not as released ({report["verdict"]}: {json.dumps(problems)[:600]}); '
                               'nothing flown and nothing written: deploying parameters is a separate tier C action')
            version = json.loads(Path(before_path).read_text()).get('autopilot_version') or {}
            manifest['fc'] = {k: version.get(k) for k in ['uid', 'board_version', 'git_hash_prefix', 'flight_sw_version']}
        part('params_before', 'FAIL' if reasons else 'PASS', reasons)
        if reasons:
            return finish()

        # The flight: the existing fixed test-takeoff-hold, judged by flight-summary.
        from .flight_test import run_test
        from .agent_tools import flight_summary

        stage[0] = 'flight'
        stopped = None
        try:
            with (run / 'flight_console.txt').open('w') as console, contextlib.redirect_stdout(console):
                run_test(runtime, SimpleNamespace(fake_fc=args.fake_fc, fake_state_dir=args.fake_state_dir,
                                                  fake_config=args.fake_config, port=args.port,
                                                  log_dir=run / 'flight', **flight))
        except Exception as exc:
            # The checks after the flight are read-only and still run (the owner refuses what is not safe).
            stopped = f'the flight test stopped ({type(exc).__name__}: {exc})'
        result, verdict, reasons = {}, 'INCOMPLETE', []
        try:
            result = json.loads((run / 'flight' / 'result.json').read_text())
            summary = flight_summary(run / 'flight')
            (run / 'flight_summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
            verdict, reasons = summary['verdict'], list(summary['failures'])
        except Exception as exc:
            reasons.append(f'flight evidence cannot be judged ({exc})')
        # A failure the flight test already recorded is evidence of a fault: missing evidence never hides it.
        known = [f'{k}={result.get(k)}' for k in ['status', 'flight', 'recovery'] if result.get(k) == 'FAIL']
        if known and verdict != 'FAIL':
            verdict = 'FAIL'
            reasons.insert(0, f'the flight test recorded {", ".join(known)}'
                              + (f' ({result["error"]})' if result.get('error') else ''))
        if stopped:
            reasons.append(stopped)
            verdict = 'FAIL' if verdict == 'FAIL' else 'INCOMPLETE'
        part('flight', verdict, reasons, result=result.get('status'), flight=result.get('flight'),
             recovery=result.get('recovery'), error=result.get('error'))

        # After: each part on its own, so one failure (e.g. an IPC timeout) leaves the others and the manifest.
        def identity_end():
            end = status()
            was = (start.get('instance_id'), start.get('build_id'), owner.get('source_id'), disk_id, checker_sha,
                   manifest['scenario']['files'])
            now = (end.get('instance_id'), end.get('build_id'), (end.get('runtime_identity') or {}).get('source_id'),
                   runtime_identity.source_id(runtime_identity.inventory(project)),
                   sha256(project / 'deploy/check_params.py'),
                   [{'path': f['path'], 'sha256': sha256(project / f['path'])} for f in manifest['scenario']['files']])
            names = ['instance', 'build', 'owner source_id', 'disk source_id', 'check_params.py', 'scenario files']
            reasons = [f'{n} changed during the run' for n, a, b in zip(names, was, now) if a != b]
            part('identity_end', 'FAIL' if reasons else 'PASS', reasons)

        def params_after():
            after_path, after_verdict, error = readback('params_after')
            if error or after_verdict != 'PASS':
                part('params_after', 'INCOMPLETE', [f'readback after the flight is not PASS ({error or after_verdict})'])
                return
            report = check.check(release, after_path)
            owned = set(json.loads((release / 'params.json').read_text())['fc_owned']['resolved_names'])
            before, after = readback_values(before_path), readback_values(after_path)
            changed = sorted(n for n in set(before) | set(after)
                             if (before.get(n) or {}).get('bits') != (after.get(n) or {}).get('bits'))
            other = [n for n in changed if n not in owned]
            uid_after = (json.loads(Path(after_path).read_text()).get('autopilot_version') or {}).get('uid')
            params['after'] = {'path': str(Path(after_path).relative_to(run)), 'sha256': sha256(after_path),
                               'check': report['verdict'], 'changed_fc_owned': [n for n in changed if n in owned],
                               'changed_other': other}
            reasons = []
            if report['verdict'] != 'PASS':
                reasons.append(f'parameters after the flight: check {report["verdict"]}')
            if other:
                reasons.append(f'parameters changed during the run that are not the FC\'s own: {other[:10]}')
            if uid_after != (manifest.get('fc') or {}).get('uid'):
                reasons.append(f'another FC after the flight (uid {uid_after})')
            verdict = ('FAIL' if other or uid_after != (manifest.get('fc') or {}).get('uid') or report['verdict'] == 'FAIL'
                       else 'INCOMPLETE' if report['verdict'] != 'PASS' else 'PASS')
            part('params_after', verdict, reasons)

        def fc_log():
            log = result.get('fc_log') or {}
            if not log or log.get('error') or not log.get('path'):
                part('fc_log', 'INCOMPLETE', [f'no FC log of this flight ({log.get("error") or "not downloaded"})'])
            elif log.get('id') is None or result.get('fc_log_before') is None or log['id'] <= result['fc_log_before']:
                # No newest log before the flight (the list failed or was empty): no baseline, so not provably
                # this flight's log either.
                part('fc_log', 'INCOMPLETE', [f'FC log {log.get("id")} is not newer than the newest before the '
                                              f'flight ({result.get("fc_log_before")}): not provably this flight\'s'])
            elif not Path(log['path']).is_file():
                part('fc_log', 'INCOMPLETE', [f'FC log file missing: {log["path"]}'])
            elif sha256(log['path']) != log.get('sha256'):
                part('fc_log', 'FAIL', ['FC log file differs from the downloaded one (SHA-256)'])
            else:
                part('fc_log', 'PASS', [], id=log.get('id'), before=result.get('fc_log_before'), sha256=log['sha256'],
                     size=log.get('size'))

        def data():
            # This run's raw data, kept with the manifest: the owner's timing rows of this run, and the records of
            # its wire.bin between model-start and model-stop, whose HIL_SENSOR frames must all be there and valid.
            host = result.get('host_log') or {}
            host_dir = Path(host['dir']) if host.get('dir') else None
            recovered, stopped = result.get('initial_recovery') or {}, result.get('after_model_stop') or {}
            steps = stopped.get('produced_steps')
            reasons, details = [], {}
            (run / 'host').mkdir(exist_ok=True)
            timing = host_dir / 'timing.csv' if host_dir else None
            t0, t1 = host.get('timing_start'), host.get('timing_end')
            if timing is None or not timing.is_file() or t0 is None or t1 is None or t1 <= t0:
                reasons.append('no timing rows of this run in the owner timing.csv')
            else:
                with timing.open('rb') as stream:
                    stream.seek(t0)
                    rows = stream.read(t1 - t0)
                (run / 'host' / 'timing.csv').write_bytes(rows)
                index = [int(r.split(b',')[0]) for r in rows.splitlines() if r[:1].isdigit()]
                details['timing'] = {'source': str(timing), 'range': [t0, t1], 'rows': len(index)}
                if not index or index != list(range(index[0], index[0] + len(index))) or len(index) != steps:
                    reasons.append(f'timing rows of this run are not {steps} consecutive steps ({len(index)} rows)')
            # The HIL_SENSOR packets this run sent: the native counters restart at every reconnection, so they are
            # compared within one connection generation, from after the test's initial reboot to the model stop.
            # Both counts must have been reported (status always lists them): a missing one is no evidence of 0.
            generations = [(x.get('fc') or {}).get('connection_generation') for x in (recovered, stopped)]
            counts = [(x.get('metrics') or {}).get('tx_HIL_SENSOR') if isinstance(x.get('metrics'), dict) else None
                      for x in (recovered, stopped)]
            counts = [c if isinstance(c, int) and not isinstance(c, bool) and c >= 0 else None for c in counts]
            expected = None if None in counts or None in generations or counts[1] < counts[0] else counts[1] - counts[0]
            wire = host_dir / 'wire.bin' if host_dir else None
            w0, w1 = host.get('wire_start'), host.get('wire_end')
            if generations[0] != generations[1] or None in generations:
                reasons.append(f'the FC connection changed during the run (generation {generations[0]} -> '
                               f'{generations[1]}): its HIL_SENSOR count cannot be checked')
            elif wire is None or not wire.is_file() or w0 is None or w1 is None or w1 <= w0 or not expected:
                reasons.append(f'no wire.bin range or no HIL_SENSOR count for this run (counts {counts})')
            else:
                span, found, bad = wire_slice(wire, w0, w1)
                details['wire'] = {'source': str(wire), 'requested': [w0, w1], 'range': list(span) if span else None,
                                   'sensor_packets': expected, 'found': found, 'bad_frames': bad}
                if span is not None:
                    with wire.open('rb') as stream:
                        stream.seek(span[0])
                        (run / 'host' / 'wire.bin').write_bytes(stream.read(span[1] - span[0]))
                if span is None or found != expected or bad:
                    reasons.append(f'wire.bin holds {found} valid of this run\'s {expected} HIL_SENSOR packets'
                                   + (f' and {bad} places that are no valid MAVLink frame' if bad else ''))
            part('data', 'INCOMPLETE' if reasons else 'PASS', reasons, **details)

        for stage[0], step in [('identity_end', identity_end), ('params_after', params_after), ('fc_log', fc_log),
                               ('data', data)]:
            try:
                step()
            except Exception as exc:
                part(stage[0], 'INCOMPLETE', [f'{stage[0]} could not be checked ({type(exc).__name__}: {exc})'])
    except Exception as exc:
        # Whatever stopped the run still leaves a manifest (before the flight: NOT_RUN; from the flight on:
        # that part INCOMPLETE).
        part(stage[0], 'INCOMPLETE' if stage[0] == 'flight' or 'flight' in parts else 'FAIL',
             [f'{stage[0]} stopped ({type(exc).__name__}: {exc})'])
    return finish()
