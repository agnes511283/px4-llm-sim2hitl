# 起飛後動作腳本

自動飛手（`hitl/autotakeoff/`）起飛、爬到目標高度並穩定後，照這裡選定的腳本送模式與操桿。指令見[根目錄 README](../../README.md)，runtime 的規則（停止、恢復）見 [hitl README](../README.md)。

## 怎麼選用

| 指令 | 跑哪個腳本 |
|---|---|
| `./runbridge takeoff --after SCRIPT` | `hitl/commands/SCRIPT.py`（只寫名字，不加 `.py`）；不給 `--after` 就不跑任何腳本 |
| `./runbridge test-takeoff-hold`、`./runbridge hitl-run` | `--after SCRIPT`；不給時是 `after_takeoff_loiter` |
| `./runbridge deploy-test --release deploy/<配方> --flash`（或 `--reuse`） | 配方 `hitl.json` 的 `"after"`；沒有就是 `after_takeoff_loiter`。例：`deploy/02_template` 用 `template_offboard` |

- QGC 的模式選單切不到這架固定翼的 Offboard；要手動試 OFFBOARD 時用 `./runbridge takeoff --altitude 100 --after template_offboard`（FC 要是 `02_template` 的韌體）。
- `takeoff` 回傳只代表飛手已啟動，不代表起飛完成；進度看 `./runbridge status` 的 `pilot`。
- `test-takeoff-hold` 是完整有界的一趟：先重開 PX4 → 起飛 → 腳本 → 確認 AUTO_LOITER 後盤旋至少 60 s 且至少一圈（高度在進入盤旋時的 ±15 m 內）→ 停模型 → `recover`。`hitl-run` 用 `hitl/flight_test.json` 的預設值跑同一趟，前後再收身分、參數與飛控記錄。
- **給 `test-takeoff-hold`、`hitl-run`、配方 `hitl.json` 用的腳本要 `ON_FINISH = 'loiter'`**：盤旋判定從腳本完成、PX4 在 AUTO_LOITER 時才開始。

## 現有腳本

| 腳本 | 做什麼 | `ON_FINISH` |
|---|---|---|
| `after_takeoff_template.py` | 空模板，不送任何命令 | `hold` |
| `after_takeoff_loiter.py` | 切 AUTO_LOITER（main 4／sub 3） | `loiter` |
| `template_offboard.py` | 範例模組 `sks_template` 用：AUTO_LOITER → 10 s → OFFBOARD 60 s（模組導引：15 s 後轉 30°、35 s 後爬 10 m）→ AUTO_LOITER。沒有模組送 offboard 訊號時 PX4 拒絕，這一步失敗 | `loiter` |
| `stabilized_steps.py` | Stabilized 巡航中送 roll／pitch／yaw 桿量階躍，最後切 AUTO_LOITER。序列在載入時讀 `sitl/scenarios/stabilized_steps_hitl.json`，和 SITL 預演同一份（基準桿量、穩定時間、階躍）；情境的桿量是 `manual_control_setpoint` 值（油門 −1..1），必須落在 1/1000 格點上。分析見 [analysis README](../../analysis/README.md)（`response.py --hitl-log`） | `loiter` |

## 寫一個新腳本

複製 `after_takeoff_template.py`，填 `build_sequence()`，明確設 `ON_FINISH`：

```python
from commands.sequence import Mode, Sticks, Wait

ON_FINISH = 'loiter'

def build_sequence():
    return [Mode(4, 3, timeout=8.)]  # 依序列出動作
```

| 動作 | 意義 |
|---|---|
| `Wait(seconds)` | 等待；維持上一筆桿量，照常持續送出 |
| `Mode(main_mode, sub_mode=0, timeout=5)` | 送 PX4 custom main／sub mode 請求（每秒重送），heartbeat 讀回相同模式才進下一步；逾時就失敗並放手 |
| `Sticks(pitch, roll, throttle, seconds, yaw=0)` | 持續這組桿量指定秒數 |

- `Sticks` 是 MAVLink MANUAL_CONTROL 的 x／y／z／r 正規化值：pitch、roll、yaw 為 −1..1，throttle 為 0..1，送出時換成 −1000..1000／0..1000。它們不是姿態角或舵面角；負 pitch（負 x）是抬頭；各模式怎麼解讀操桿由飛控決定。要改用「幾度」當介面，得另外定義各模式的換算並驗證。
- `Mode` 允許 main mode 1–8、sub mode 0–255。這裡用到的：4／3 = AUTO_LOITER、6 = OFFBOARD、7 = STABILIZED。OFFBOARD 只有在有來源送 offboard 訊號時 PX4 才會進（例如 `modules/` 的模組 `sks_template`）；訊號停了 PX4 走自己的 offboard 失聯保護。實際支援哪些模式與進入條件依韌體而定，要在 HITL 確認。
- `ON_FINISH`：
  - `'hold'`：結束時 PX4 必須在 Stabilized，否則失敗並放手；roll、yaw 桿歸中，自動飛手回到原本的高度保持。
  - `'loiter'`：結束時 PX4 必須在 AUTO_LOITER（4／3）；飛手繼續送中立的 MANUAL_CONTROL 與 heartbeat（照舊滿足 RC 失聯設定），導航由 PX4 負責。會一直持續到明確停止，不會自己停模型；PX4 離開 AUTO_LOITER 就放手。
  - `'release'`：停止送桿，交回原本的人工輸入；不自動 disarm。
- 載入時就檢查（起飛前），不合法就拒絕起飛。離線先試載入（專案根目錄）：

  ```sh
  "$PY" -B -c "import sys; sys.path.insert(0, 'hitl'); from commands.sequence import load_script; s = load_script('SCRIPT'); print(s.finish, s.actions)"
  ```

  改了 `sequence.py` 或飛手時跑 `hitl/tests/test_command_scripts.py`（含在離線測試裡）。

## 執行規則

- 腳本在爬升完成並穩定後才開始，只跑一次：Stabilized、高度在目標 ±5 m、CAS 在轉動空速（預設 12 m/s）到 30 m/s、|roll| ≤ 5°、|爬升率| ≤ 1.5 m/s、pitch −15°～20°，連續 3 s。60 s 內沒達到，或爬升逾時，就失敗並放手（`--after-stable-seconds`、`--after-timeout` 可改）。
- 腳本和自動飛手共用同一條連線、遙測與送桿迴圈，逐 tick 推進，一個 tick 最多前進一步，不補發堆積的動作。腳本裡不要開 socket、直接送 MAVLink、sleep 或呼叫外部程序。
- 停止後續動作並放手的情況：`./runbridge stop-takeoff`、Ctrl+C、QGC 搖桿被動到（人接手）、遙測失聯、disarm、PX4 切到序列沒要求的模式。
- 狀態：`./runbridge status` 的 `pilot.after_state`（disabled、waiting、running、complete、failed、cancelled）、`pilot.after_step`（目前步驟，從 0 起算）、`pilot.after_reason`（中止原因）。
- 飛手的路由、session、log 選項由 owner 決定，`takeoff` 不能覆寫。只有起飛後腳本；沒有起飛前或解鎖後的 hook。
