# Shared-library HIL runtime

載入已驗證的模型 library，以 4 ms 步進執行，並透過 USB MAVLink 與 PX4 做 HIL。本文是環境、能力限制與測試入口；CLI 語意見[操作說明](../hil_bridge/docs/HIL_操作說明.md)，wire 與恢復契約見 [BEHAVIOR_CONTRACT](../hil_bridge/docs/BEHAVIOR_CONTRACT.md)，建置見 [BUILD_AND_RELEASE](../docs/BUILD_AND_RELEASE.md)。

## 環境

| 項目 | macOS（本機） | Linux（Ubuntu，只連飛控） | Windows |
|---|---|---|---|
| 入口 | 根目錄 `runbridge.command` | 同一支 `runbridge.command`（需要 zsh：`sudo apt install zsh`） | 根目錄 `runbridge.cmd` |
| Python | uv 管理的 CPython 3.12，venv 在 `~/Library/Application Support/SkySurferHIL/venv` | `~/.local/share/SkySurferHIL/venv` | `%LOCALAPPDATA%\SkySurferHIL\venv\Scripts\python.exe`（尚未實測） |
| 覆寫 | `FW_HIL_PYTHON` | `FW_HIL_PYTHON` | `FW_HIL_PYTHON` |
| 套件 | 根目錄 `pyproject.toml`／`uv.lock`：PySide6 6.8.3、pyserial 3.5、pymavlink 2.4.49、numpy 2.0.2 | 同左 | 同左 |
| 建立環境 | `./runbridge.command --setup`（需要 `brew install uv`） | `./runbridge.command --setup`（需要 uv） | `runbridge.cmd --setup`（需要 `winget install astral-sh.uv`） |
| native release | `releases/skysurfer/macos-arm64/` | `releases/skysurfer/linux-x64/`：**FC-only**（只有 worker、沒有模型；`update_model.command --fc-only`） | 尚未實作，updater 會拒絕 |
| FC 序列埠 | `/dev/cu.usbmodem*` | `/dev/ttyACM*`（使用者要在 `dialout` 群組） | COM |

- `./runbridge.command --check-python` 只檢查環境，不會安裝任何東西。找不到 Python 時退出碼 4。
- 新機器安裝步驟見 [runbook：新機器安裝](../docs/runbooks/new_machine_setup.md)。venv、建置 cache、IPC、log 都留在本機，不放 Dropbox、不在機器間複製。
- 兩個 dylib 只依賴 macOS 系統庫；runtime 不需要 MATLAB。
- **Linux FC-only**：模型 library 要 MATLAB 產生的程式碼，Linux 上沒有，所以 Linux release 只有 worker（`native/macos/worker.c`、`io.c` 是 POSIX 共用碼，時鐘與排程分 macOS／Linux 兩段；Linux 用 `CLOCK_MONOTONIC` 與 SCHED_FIFO，沒有權限時 status 的 `scheduler` 會顯示失敗碼）。owner 照常連 FC：`status`、`param-readback`、`param-plan`、`fetch-log`、`sd-list`、`sd-get`、`recover`；status 的 `fc_only: true`，`missing_conditions` 有「model release (FC-only on this platform)」，所以 `model-start`、`takeoff`、`test-takeoff-hold`、`hitl-run` 都會被拒絕。沒有確認視窗（2026-10-17）：`param-deploy`、`sd-put`、`sd-rm` 在 Linux 也照常執行。
- 公開 header：`interface/hil_model_api.h`；ABI 65537，natural alignment；Initial／Input／Output／Info 為 120／176／680／280 bytes。

本機狀態目錄：`~/Library/Caches/Codex/SkySurferPhaseB/runtime/<project-path-hash>/`（Linux：`~/.cache/SkySurferPhaseB/runtime/<project-path-hash>/`）

| 檔案 | 內容 |
|---|---|
| `owner.lock`、`host.json` | owner lock 與 IPC 端點／token（0600）。IPC 每個請求、回覆各一行 JSON：請求上限 64 KiB；回覆上限 4 MiB。`status` 的 `operations` 只列摘要（`operations_summarized: true`；每個操作只留純量欄位與結果的純量欄位、字串最多 2,000 字、每個最多 8 KiB——以送出的 JSON 位元組計，非 ASCII 字元會被跳脫——太大時只留識別欄位與截短的 error，`result_summarized: true`），完整的操作用 `operation` 請求（`request_id`）取得：CLI 的 `request()` 與附掛視窗在操作結束時都這樣拿完整結果。owner 保留最近 32 個已結束的操作，還沒結束的一律保留；同時最多 16 個還沒結束，再多的請求直接拒絕（「Owner busy」），不認得的動作與超過 64 字的 `request_id` 也直接拒絕，所以 status 有上限。同一個 `request_id` 只會有一個操作：查重複與登記在同一把鎖裡做，同時送來兩次只執行一次，第二次回覆第一次的操作。沒有換行就結束的回覆是錯誤（`host/ipc.py` 的 `read_reply`，CLI 與附掛視窗共用） |
| `recovery.json` | recovery pending marker；只由 Core 寫入，不可手動刪改 |
| `logs-<時間>/` | 每次 owner 的 log（wire、timing、io_events、clock_sync、pilot、final_status） |

## 能力與限制

- **步進**：ode4、4 ms、輸出 t_k；單實例。Mac worker 使用 QoS user-interactive 與 Mach time-constraint（4 ms／1 ms／2 ms）；實際設定結果在 status 的 `scheduler`。這是 soft real-time。
- **時序 fault**：lateness ≥20 ms fault；最多補 4 個已逾期 step，不跳步、不大量重播 sensor。每一步都記錄在 `timing.csv`。
- **controls**：未收到時為 0，之後 hold-last；stale >100 ms 提醒、≥2 s fault；開始後 5 s 內沒有有效 controls 也 fault。
- **sensor 單位**：加速度 m/s²、gyro rad/s、mag µT、pressure Pa；GPS deg／MSL m、NED m/s、course deg。wire 縮放只做一次（見 BEHAVIOR_CONTRACT）。
- **GPS 品質設定**：來源 GPS accuracy 0.3／0.5 m → eph／epv 30／50 cm，fix=3、衛星數 10。這是模擬設定，不是實際衛星觀測。
- **場景**：支援 AGL、TAS、yaw、body velocity 或 TAS 模式、Euler、緯經度。來源固定 ground MSL=0、geoid=0、wind／rates=0、fixed seed，其他值拒絕。非零高度／速度只能離線驗證；實體 air-start 拒絕。預設場景 `scenarios/ground.json`。
- **發散 guard**：加速度 >1000 m/s²、gyro >100 rad/s、GPS 速度 >200 m/s 或非有限值時 fault；不裁切、不歸零、不改飛機來掩蓋發散。
- **原 SLX 的 UDP 路徑**（14580／14572／14571）不參與 runtime。

## 離線測試

全部使用 fake FC、隔離狀態目錄與隨機 loopback 埠，不碰實體 serial、QGC 路由或 recovery marker。

```sh
PY="$HOME/Library/Application Support/SkySurferHIL/venv/bin/python"
"$PY" -B hil_runtime/tests/test_runtime.py
"$PY" -B hil_runtime/tests/test_management_faults.py
"$PY" -B hil_runtime/tests/test_stability.py
"$PY" -B hil_runtime/tests/test_baro_compat.py
"$PY" -B hil_runtime/tests/test_reconnect.py
"$PY" -B hil_runtime/tests/test_runtime_identity.py
"$PY" -B hil_runtime/tests/test_gui_contract.py
"$PY" -B hil_runtime/tests/test_gui_session.py
"$PY" -B hil_runtime/tests/test_gui_language.py
"$PY" -B hil_runtime/tests/test_runbridge_fake.py
```

飛手與 commands 的共用回歸在 `hil_bridge/tests/`。完整清單與執行方式見 [runbook：離線回歸](../docs/runbooks/model_update_to_hil.md#離線回歸)。

- `FW_HIL_TEST_OUTPUT=<dir>` 可保存每個案例的 CLI、host／pilot console、wire、timing、FC events 與 final status。
- 600 s 負載：`tests/run_gui_load.py <新目錄>`，預設 thread peer；`--peer-mode process` 只用於診斷對照。門檻見 [GUI_SPEC](../docs/GUI_SPEC.md#負載驗收)。
- `tests/run_live_unarmed.py` 會連實體 PX4（未解鎖），屬於實體測試。
- `tests/validate_library.py` 由 updater 呼叫，驗證新建的 library。
