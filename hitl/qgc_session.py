"""Manual HITL (3.1) with the QGC joystick in one go, for a desktop launcher (hitl/qgc_session.sh).

  python -B hitl/qgc_session.py [--altitude 100] [--no-takeoff] [--no-qgc] [--keep-owner]

owner (started if not running) -> checks: verified FC, unarmed, SYS_HITL=1, nothing pending (a pending recovery
gets one standard recover) -> QGC (only when its settings keep USB auto-connect off) -> model on the ground ->
automatic takeoff (unless --no-takeoff or 'm' at the prompt) -> you fly with the QGC joystick; a status line
shows height, airspeed and mode -> Enter, Ctrl-C or closing the window ends it: model-stop ->
recover --hil-force-disarm (the runtime forces only after a refused normal disarm) -> status check -> owner
shutdown (unless --keep-owner). Anything that is not ready stops here with the reason; nothing is bypassed.
"""
import argparse
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
QGC_INI = Path.home() / '.config' / 'QGroundControl' / 'QGroundControl.ini'
MODES = {1: 'Manual', 2: 'Altitude', 3: 'Position', 4: 'Auto (Hold/Return/...)', 5: 'Acro', 6: 'Offboard',
         7: 'Stabilized'}


def runbridge(*args, timeout=120):
    """(exit code, last JSON line of the output or None)."""
    result = subprocess.run([RUNBRIDGE, *args], cwd=PROJECT, capture_output=True, text=True, timeout=timeout)
    line = next((x for x in reversed(result.stdout.strip().splitlines()) if x.startswith('{')), None)
    try:
        return result.returncode, json.loads(line) if line else None
    except ValueError:
        return result.returncode, None


def status():
    code, value = runbridge('status', timeout=20)
    return value if code == 0 else None


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


def show_status(stop):
    while not stop.wait(2):
        s = status()
        if s:
            print('\r' + line(s) + ' ' * 4, end='', flush=True)


def finish(keep_owner):
    print('\n\n結束：停模型 → 恢復 → 檢查')
    runbridge('model-stop', timeout=60)
    code, value = runbridge('recover', '--hil-force-disarm', timeout=120)
    s = status() or {}
    fc = s.get('fc') or {}
    ok = code == 0 and not s.get('recovery_required') and fc.get('armed') is False and fc.get('SYS_HITL') == 1
    print('恢復完成：未解鎖、SYS_HITL=1、沒有待恢復' if ok else
          f'恢復沒有完成，先不要關 owner：{json.dumps(value, ensure_ascii=False)[:300]}（照 hitl/README 的恢復規則處理）')
    if ok and not keep_owner:
        runbridge('shutdown', timeout=60)
        print('owner 已關閉')
    return 0 if ok else 3


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--altitude', type=float, default=100)
    parser.add_argument('--no-takeoff', action='store_true', help='do not take off automatically')
    parser.add_argument('--no-qgc', action='store_true', help='do not start QGC (open it yourself)')
    parser.add_argument('--keep-owner', action='store_true', help='leave the owner running at the end')
    args = parser.parse_args()
    # Closing the window (SIGHUP) or SIGTERM ends the session the same way as Ctrl-C. Without a window the
    # output of the cleanup goes to a log file, so printing cannot stop the recovery halfway.
    def hangup(signum, frame):
        log = Path(os.environ.get('SIM2HITL_CACHE') or Path.home() / '.cache' / 'px4-llm-sim2hitl') / 'manual'
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

    try:
        print('== 3/4 模型在地面開始跑')
        code, value = runbridge('model-start', timeout=60)
        if code:
            print('模型沒有啟動：' + json.dumps(value, ensure_ascii=False)[:300])
            return 3
        takeoff = not args.no_takeoff
        if takeoff:
            answer = input(f'按 Enter 自動起飛到 {args.altitude:g} m；輸入 m 再按 Enter = 不自動起飛，自己用搖桿從地面起飛：')
            takeoff = answer.strip().lower() != 'm'
        if takeoff:
            code, value = runbridge('takeoff', '--altitude', f'{args.altitude:g}', timeout=60)
            if code:
                print('自動起飛沒有開始：' + json.dumps(value, ensure_ascii=False)[:300])
                return finish(args.keep_owner) or 3
            print('自動起飛中：平飛後動 QGC 的搖桿就會接手（超過約 15 %），模式選 Position 最好飛')
        else:
            print('自己起飛：模式切 Stabilized → 用 QGC 的 Arm 解鎖 → 油門推過一半 → 空速約 12 m/s 拉桿')
        print('== 4/4 飛行中：飛完回到這個視窗按 Enter 結束（Ctrl-C 或關視窗也會正常結束）\n')
        stop = threading.Event()
        threading.Thread(target=show_status, args=(stop,), daemon=True).start()
        try:
            input()
        finally:
            stop.set()
    except (KeyboardInterrupt, EOFError):
        pass
    return finish(args.keep_owner)


if __name__ == '__main__':
    sys.exit(main())
