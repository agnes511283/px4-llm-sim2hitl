#!/bin/zsh
set -euo pipefail
runtime_dir=${0:A:h}
# Same venv as runbridge.command.
[[ $OSTYPE == darwin* ]] && venv_default="$HOME/Library/Application Support/SkySurferHIL/venv" || venv_default="${XDG_DATA_HOME:-$HOME/.local/share}/SkySurferHIL/venv"
export UV_PROJECT_ENVIRONMENT=${UV_PROJECT_ENVIRONMENT:-$venv_default}
py=${FW_HIL_PYTHON:-$UV_PROJECT_ENVIRONMENT/bin/python}
[[ -x "$py" ]] || { print -u2 "找不到 HIL runtime Python：$py\n請在專案根目錄執行 ./runbridge.command --setup"; exit 4; }
exec "$py" -B "$runtime_dir/update.py" "$@"
