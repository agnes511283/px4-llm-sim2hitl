"""ULog replay through PX4's own fixed-wing controllers (ROADMAP batch 4h); run by run_sitl.py --replay.

  python3 sitl/run_sitl.py --replay <flight.ulg> --out <dir> [--speed 5]

PX4's generic `replay` module (src/modules/replay) publishes the logged messages at their logged times and
sets the lockstep clock; uORB publisher rules (orb_publisher.rules, only compiled into px4_sitl_replay:
`python3 sitl/build_sitl.py --replay`) restrict it to the controller INPUTS below, so the logged outputs are
not republished. fw_att_control, fw_rate_control and control_allocator recompute the outputs from those
inputs with the parameters of the log (`replay tryapplyparams`), and PX4's logger records them (and the
replayed inputs) in <out>/log/. analysis/replay_compare.py then matches each recomputed output sample with
the logged one. No sensors, EKF2, commander or plant run: this checks the controllers alone.

--speed is PX4_SIM_SPEED_FACTOR: the self-test gave the same result at 5x as at 1x and a slightly larger
median difference at 10x (sitl/README.md). The PX4 tree is only read; everything is written under --out.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'px4'))
from check_px4_tree import px4_root  # noqa: E402
# Upstream topics the three controllers subscribe to (ORB_IDs in their sources), minus their own outputs.
INPUTS = ['vehicle_attitude', 'vehicle_angular_velocity', 'manual_control_setpoint', 'vehicle_control_mode',
          'vehicle_status', 'vehicle_land_detected', 'airspeed_validated', 'vehicle_local_position',
          'actuator_armed', 'battery_status', 'autotune_attitude_control_status', 'failure_detector_status',
          'flaps_setpoint', 'spoilers_setpoint', 'landing_gear_wheel', 'fixed_wing_runway_control']
MODULES = ['control_allocator start', 'fw_rate_control start', 'fw_att_control start']


# uORB reads ./orb_publisher.rules when PX4 starts (before the startup script), so it is written first.
RULES = 'restrict_topics: ' + ', '.join(INPUTS) + '\nmodule: replay\nignore_others: true\n'


def startup_script():
    return '\n'.join([
        '#!/bin/sh', 'set +e', '. px4-alias.sh',
        'n=0; until px4-ver --instance $px4_instance all >/dev/null 2>&1 || [ $n -ge 200 ]; do sleep 0.05; n=$((n+1)); done',
        'param select parameters.bson',
        'replay tryapplyparams',  # the log's parameters, before the modules read them
        *MODULES,
        'logger start -f -t -b 1000 -p vehicle_angular_velocity',
        'replay start',
    ]) + '\n'


def run(ulog, out, speed=5.0, timeout_margin=120.0):
    """Replay ulog; returns a report dict (the replayed ULog path, wall time, exit)."""
    sys.path.insert(0, str(ROOT / 'analysis'))
    import ulog as ulog_reader
    log = ulog_reader.read(ulog)
    stamps = [int(a['timestamp'][-1]) for a in log.topics.values() if len(a)]
    span_s = (max(stamps) - log.start_us) * 1e-6
    tree = px4_root()
    bindir = tree / 'build' / 'px4_sitl_replay' / 'bin'
    if not (bindir / 'px4').is_file():
        raise SystemExit('px4_sitl_replay not built: python3 sitl/build_sitl.py --replay')
    work = Path(out).resolve()
    work.mkdir(parents=True, exist_ok=True)
    (work / 'orb_publisher.rules').write_text(RULES)
    script = work / 'replay_rcS'
    script.write_text(startup_script())
    env = dict(os.environ, PATH=f'{bindir}:{os.environ.get("PATH", "")}', replay=str(Path(ulog).resolve()),
               PX4_SIM_SPEED_FACTOR=str(speed))
    env.pop('replay_mode', None)  # generic mode (replay_mode=ekf2 is the EKF2-only mode)
    start = time.monotonic()
    with open(work / 'px4.log', 'w') as px4_log:
        proc = subprocess.Popen([str(bindir / 'px4'), '-d', '-s', str(script), '-w', str(work)],
                                stdout=px4_log, stderr=subprocess.STDOUT, env=env)
        deadline = start + span_s / speed + timeout_margin
        # The replay module exits when the log is done; PX4 keeps running, so poll the module and shut down.
        time.sleep(min(10.0, span_s / speed / 2))
        while time.monotonic() < deadline and proc.poll() is None:
            status = subprocess.run([str(bindir / 'px4-replay'), '--instance', '0', 'status'], env=env, cwd=work,
                                    capture_output=True, text=True)
            if 'not running' in (status.stdout + status.stderr) or status.returncode != 0:
                break
            time.sleep(1.0)
        timed_out = time.monotonic() >= deadline
        time.sleep(2.0)  # let the logger flush its last buffer
        subprocess.run([str(bindir / 'px4-shutdown'), '--instance', '0'], env=env, cwd=work, capture_output=True)
        try:
            code = proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
            code = proc.wait()
    logs = sorted((work / 'log').rglob('*.ulg'))
    return {'ulog': str(ulog), 'replayed_ulog': str(logs[-1]) if logs else None, 'log_span_s': span_s,
            'speed': speed, 'wall_s': time.monotonic() - start, 'timed_out': timed_out, 'exit': code,
            'inputs': INPUTS, 'modules': MODULES}


if __name__ == '__main__':
    print(json.dumps(run(sys.argv[1], sys.argv[2])))
