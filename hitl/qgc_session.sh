#!/usr/bin/env bash
# Double-click entry for hitl/qgc_session.py (manual HITL with the QGC joystick); a desktop launcher runs it in a
# terminal window, which stays open at the end so the result can be read. Arguments go to qgc_session.py.
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
"$(./runbridge where python)" -B hitl/qgc_session.py "$@"
code=$?
echo
read -rp "按 Enter 關閉這個視窗（結束碼 $code）" _
exit "$code"
