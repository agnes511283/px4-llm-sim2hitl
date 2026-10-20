"""Manual HITL (3.1) with the QGC joystick in one go, for a desktop launcher (hitl/qgc_session.sh).

  python -B hitl/qgc_session.py [--altitude 100] [--scenario hitl/scenarios/<x>.json] [--no-takeoff] [--no-qgc]
                                [--no-log] [--keep-owner]

owner (started if not running) -> checks: verified FC, unarmed, SYS_HITL=1, nothing pending (a pending recovery
gets one standard recover) -> QGC (only when its settings keep USB auto-connect off) -> model on the ground ->
automatic takeoff (unless --no-takeoff or 'm' at the prompt) -> you fly with the QGC joystick; a status line
shows height, airspeed and mode -> Enter, Ctrl-C or closing the window ends it: model-stop ->
recover --hil-force-disarm (the runtime forces only after a refused normal disarm) -> status check -> this
flight's records (unless --no-log; the same checks as hitl-run: the FC log is newer than the newest one before the
flight, downloaded twice and identical, strict parse) in <cache>/manual_flights/ -> owner shutdown (unless
--keep-owner). Anything that is not ready stops here with the reason; nothing is bypassed. A human flight is an
observation, not a test: nothing is judged PASS or FAIL.
"""
import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
RUNBRIDGE = str(PROJECT / 'runbridge')
sys.path.insert(0, str(PROJECT / 'hitl'))
from host.ipc import request  # noqa: E402
QGC_INI = Path.home() / '.config' / 'QGroundControl' / 'QGroundControl.ini'
MODES = {1: 'Manual', 2: 'Altitude', 3: 'Position', 4: 'Auto (Hold/Return/...)', 5: 'Acro', 6: 'Offboard',
         7: 'Stabilized'}


def runbridge(*args, timeout=120):
    """(exit code, result): the last JSON line of the output, an operation's own result taken out of it."""
    result = subprocess.run([RUNBRIDGE, *args], cwd=PROJECT, capture_output=True, text=True, timeout=timeout)
    line = next((x for x in reversed(result.stdout.strip().splitlines()) if x.startswith('{')), None)
    try:
        value = json.loads(line) if line else None
    except ValueError:
        value = None
    if isinstance(value, dict) and isinstance(value.get('operation'), dict) and 'result' in value['operation']:
        value = value['operation']['result'] or {}
    return result.returncode, value


def status():
    """The owner's status over its local IPC, in this process: polling through a new runbridge process every
    few seconds is a CPU burst that can make the 4 ms loop late on a machine without real-time scheduling."""
    try:
        response = request(PROJECT / 'hitl', 'status', None, timeout_s=10)
    except Exception:  # noqa: BLE001 - no owner yet, or it is restarting
        return None
    return response.get('result') if response.get('status') == 'complete' else None


def start_owner():
    log = Path(os.environ.get('SIM2HITL_CACHE') or Path.home() / '.cache' / 'px4-llm-sim2hitl') / 'manual'
    log.mkdir(parents=True, exist_ok=True)
    stream = open(log / f'qgc_session_owner_{time.strftime("%Y%m%d_%H%M%S")}.log', 'a')
    subprocess.Popen([RUNBRIDGE, 'bridge'], cwd=PROJECT, stdout=stream, stderr=subprocess.STDOUT,
                     stdin=subprocess.DEVNULL, start_new_session=True)
    end = time.monotonic() + 90
    while time.monotonic() < end:
        s = status()
        if s and (s.get('fc') or {}).get('state') == 'verified':
            return s
        time.sleep(1)
    raise SystemExit('owner 90 秒內沒有連上 FC：確認 USB 有接、QGC 沒有佔用序列埠（log 在 ' + str(log) + '）')


def qgc_problem():
    """Why QGC must not be started (it would take the FC's serial port), or None."""
    text = QGC_INI.read_text() if QGC_INI.is_file() else ''
    if 'autoConnectPixhawk=false' not in text:
        return (f'QGC 的 USB 自動連線沒有關（{QGC_INI} 的 [AutoConnect] 要有 autoConnectPixhawk=false，'
                '做法見根目錄 README「環境準備」的 QGC），它會和 owner 搶 FC 的序列埠')
    return None


def start_qgc():
    if subprocess.run(['pgrep', '-f', 'QGroundControl'], capture_output=True).returncode == 0:
        print('QGC 已經開著')
        return
    candidates = [os.environ.get('SIM2HITL_QGC')] + sorted(str(p) for p in (Path.home() / 'Applications').glob('QGroundControl*.AppImage'))
    exe = next((c for c in candidates if c and Path(c).is_file()), None)
    if not exe:
        print('找不到 QGC（設 SIM2HITL_QGC 指到 AppImage），請自己打開 QGC')
        return
    subprocess.Popen([exe], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    print('已打開 QGC：等它經 UDP 連上飛機')


def line(s):
    fc, tele = s.get('fc') or {}, s.get('telemetry') or {}
    height = ((tele.get('LOCAL_POSITION_NED') or {}).get('values') or {}).get('height_local_m')
    speed = ((tele.get('VFR_HUD') or {}).get('values') or {}).get('airspeed_m_s')
    mode = MODES.get(((fc.get('custom_mode') or 0) >> 16) & 0xFF, '?')
    pilot = 'running' if (s.get('pilot') or {}).get('running') else 'off'
    fmt = lambda v, unit: f'{round(v, 1) + 0.0:6.1f} {unit}' if isinstance(v, (int, float)) else f'{"-":>6} {unit}'  # no -0.0
    return (f'高度 {fmt(height, "m")}  空速 {fmt(speed, "m/s")}  模式 {mode:<11} '
            f'{"已解鎖" if fc.get("armed") else "未解鎖"}  自動飛手 {pilot}  晚到 {s.get("misses")}')


def cache():
    return Path(os.environ.get('SIM2HITL_CACHE') or Path.home() / '.cache' / 'px4-llm-sim2hitl')


def newest_log():
    """The id of the FC's newest log, or None when the list cannot be read."""
    code, value = runbridge('fetch-log', '--list', timeout=120)
    ids = [e.get('id') for e in ((value or {}).get('entries') or []) if isinstance(e.get('id'), int)]
    return max(ids) if code == 0 and ids else None


def keep_records(record):
    """This flight's FC log (only if newer than the newest before the flight), twice, plus the owner's logs."""
    out = cache() / 'manual_flights' / record['name']
    out.mkdir(parents=True, exist_ok=True)
    newest = newest_log()
    if record['log_before'] is None or newest is None or newest <= record['log_before']:
        record['fc_log'] = f'not kept: no FC log newer than {record["log_before"]} (newest {newest})'
    else:
        got = []
        for copy in ('a', 'b'):
            code, value = runbridge('fetch-log', '--log-id', str(newest), '--out', str(out / copy), timeout=900)
            got.append(value if code == 0 and value else {})
        paths = [g.get('path') for g in got]
        same = all(paths) and len({hashlib.sha256(Path(x).read_bytes()).hexdigest() for x in paths}) == 1
        strict = json.loads(subprocess.run([sys.executable, '-B', str(PROJECT / 'analysis' / 'ulog_strict.py'),
                                            paths[0]], capture_output=True, text=True).stdout or '{}') if same else {}
        record['fc_log'] = {'id': newest, 'path': paths[0], 'downloaded_twice_identical': same,
                            'strict_ok': bool(strict.get(paths[0], {}).get('ok')) if same else None}
    (out / 'session.json').write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n')
    print(f'這趟的紀錄：{out}/session.json（飛控記錄、owner 的 wire／timing 位置；分析工具見 analysis/README）')


def show_status(stop):
    while not stop.wait(3):
        s = status()
        if s:
            print('\r' + line(s) + ' ' * 4, end='', flush=True)


def finish(keep_owner, record=None):
    print('\n\n結束：停模型 → 恢復 → 檢查')
    runbridge('model-stop', timeout=60)
    code, value = runbridge('recover', '--hil-force-disarm', timeout=120)
    s = status() or {}
    fc = s.get('fc') or {}
    ok = code == 0 and not s.get('recovery_required') and fc.get('armed') is False and fc.get('SYS_HITL') == 1
    print('恢復完成：未解鎖、SYS_HITL=1、沒有待恢復' if ok else
          f'恢復沒有完成，先不要關 owner：{json.dumps(value, ensure_ascii=False)[:300]}（照 hitl/README 的恢復規則處理）')
    if ok and record is not None:
        record.update(ended_local=time.strftime('%Y-%m-%d %H:%M:%S'), recovery='complete')
        print('留下這趟的紀錄（飛控記錄下載兩次核對，約 1 分鐘）')
        keep_records(record)
    if ok and not keep_owner:
        runbridge('shutdown', timeout=60)
        print('owner 已關閉')
    return 0 if ok else 3


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--altitude', type=float, default=100)
    parser.add_argument('--no-takeoff', action='store_true', help='do not take off automatically')
    parser.add_argument('--scenario', type=Path, help='start scenario for model-start (default: ground)')
    parser.add_argument('--no-qgc', action='store_true', help='do not start QGC (open it yourself)')
    parser.add_argument('--no-log', action='store_true', help='do not keep this flight\'s FC log')
    parser.add_argument('--keep-owner', action='store_true', help='leave the owner running at the end')
    args = parser.parse_args()
    # Closing the window (SIGHUP) or SIGTERM ends the session the same way as Ctrl-C. Without a window the
    # output of the cleanup goes to a log file, so printing cannot stop the recovery halfway.
    def hangup(signum, frame):
        log = cache() / 'manual'
        log.mkdir(parents=True, exist_ok=True)
        sys.stdout = sys.stderr = open(log / f'qgc_session_closed_{time.strftime("%Y%m%d_%H%M%S")}.log', 'a')
        raise KeyboardInterrupt

    signal.signal(signal.SIGHUP, hangup)
    signal.signal(signal.SIGTERM, hangup)

    print('== 1/4 owner 與 FC')
    s = status() or start_owner()
    if s.get('model') == 'running':
        print('上次的模型還在跑，先停模型並恢復')
        if finish(keep_owner=True):
            return 3
        s = status()
    if s.get('recovery_required'):
        print('有待恢復，先做一次標準恢復')
        runbridge('recover', timeout=120)
        s = status()
    fc = s.get('fc') or {}
    if not s.get('ready_to_start_model'):
        print('還不能啟動模型：' + '; '.join(s.get('missing_conditions') or ['原因不明，看 ./runbridge status']))
        return 3
    print(f'FC 已驗證、{"未解鎖" if fc.get("armed") is False else "解鎖狀態不明"}、SYS_HITL={fc.get("SYS_HITL")}')

    print('== 2/4 QGC')
    problem = qgc_problem()
    if problem:
        print('不打開 QGC：' + problem)
        return 3
    if not args.no_qgc:
        start_qgc()
    print('虛擬搖桿：QGC 左上 Q → Application Settings → General → Fly View → 勾 Virtual Joystick')

    record = None if args.no_log else {
        'name': 'flight_' + time.strftime('%Y%m%d_%H%M%S'), 'kind': 'manual HITL (QGC joystick), observation only',
        'started_local': time.strftime('%Y-%m-%d %H:%M:%S'), 'scenario': str(args.scenario or 'hitl/scenarios/ground.json'),
        'fc': {k: (s.get('fc') or {}).get(k) for k in ('identity', 'SYS_HITL')}, 'build_id': s.get('build_id'),
        'owner_log_dir': s.get('log_dir'), 'log_before': newest_log()}
    try:
        print('== 3/4 模型在地面開始跑')
        start = ['model-start'] + (['--scenario', str(args.scenario.resolve())] if args.scenario else [])
        code, value = runbridge(*start, timeout=60)
        if code:
            print('模型沒有啟動：' + json.dumps(value, ensure_ascii=False)[:300])
            return 3
        takeoff = not args.no_takeoff
        if takeoff:
            answer = input(f'按 Enter 自動起飛到 {args.altitude:g} m；輸入 m 再按 Enter = 不自動起飛，自己用搖桿從地面起飛：')
            takeoff = answer.strip().lower() != 'm'
        if record is not None:
            record['automatic_takeoff'] = takeoff
        if takeoff:
            code, value = runbridge('takeoff', '--altitude', f'{args.altitude:g}', timeout=60)
            if code:
                print('自動起飛沒有開始：' + json.dumps(value, ensure_ascii=False)[:300])
                return finish(args.keep_owner, record) or 3
            print('自動起飛中：平飛後動 QGC 的搖桿就會接手（超過約 15 %），模式選 Position 最好飛')
        else:
            print('自己起飛：模式切 Stabilized → 用 QGC 的 Arm 解鎖 → 油門推過一半 → 空速約 12 m/s 拉桿')
        print('== 4/4 飛行中：飛完回到這個視窗按 Enter 結束（Ctrl-C 或關視窗也會正常結束）\n')
        stop = threading.Event()
        shown = threading.Thread(target=show_status, args=(stop,), daemon=True)
        shown.start()
        try:
            input()
        finally:
            stop.set()
            shown.join(timeout=12)
    except (KeyboardInterrupt, EOFError):
        pass
    return finish(args.keep_owner, record)


if __name__ == '__main__':
    sys.exit(main())
