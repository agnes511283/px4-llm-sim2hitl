# 起飛後飛控命令腳本

此處是 native managed pilot 使用的起飛後序列。啟動、起飛與停止見 [HIL 操作說明](../docs/HIL_操作說明.md)，整體責任見 [ARCHITECTURE](../../docs/ARCHITECTURE.md)。

用根入口 `./runbridge.command takeoff --after SCRIPT` 明確選擇本資料夾內的 `SCRIPT.py`。
提供`after_takeoff_template.py`空模板，以及`after_takeoff_loiter.py`：成功達高後切AUTO_LOITER並維持中立manual-input可用性。
`stabilized_steps.py`：在 Stabilized 巡航中送 roll／pitch／yaw 搖桿階躍，結束切 AUTO_LOITER（ROADMAP 批次 4i）；序列在載入時讀 `sitl/scenarios/stabilized_steps_hitl.json`，和 SITL 預演用同一份情境（基準桿量、settle、階躍）。情境的桿量是 `manual_control_setpoint` 值（油門 -1..1），必須落在 MANUAL_CONTROL 的 1/1000 格點上。飛完用 `analysis/response.py --hitl-log` 分析（[analysis README](../../analysis/README.md)）。
腳本不會由人類雙擊 runbridge 或普通 takeoff 自動選用。

複製模板、填入 `build_sequence()`，並明確設定 `ON_FINISH`：

```python
from commands.sequence import Mode, Sticks, Wait

ON_FINISH = 'hold'

def build_sequence():
    return []  # 在此填入已定義的測試順序
```

| 動作 | 介面與意義 |
|---|---|
| 等待 | `Wait(seconds)`；維持上一筆桿量，持續正常送出 |
| 模式 | `Mode(main_mode, sub_mode=0, timeout=5)`；送模式請求，等 heartbeat 讀回主／子模式才進下一步 |
| 操桿 | `Sticks(pitch, roll, throttle, seconds, yaw=0)`；持續該桿量指定時間 |

`Sticks` 是 MAVLink MANUAL_CONTROL 的 x／y／z／r 正規化輸入：pitch、roll、yaw 為 -1..1，
throttle 為 0..1；會轉成 -1000..1000／0..1000。它們不是姿態角度或舵面角度。
現有起飛程式以負 x 表達抬頭；不同模式如何解讀操桿仍由飛控決定。
若日後要用「roll／pitch 幾度」作為腳本介面，需要另外定義各模式的換算，再驗證。

`Mode` 使用現有 PX4 custom main／sub mode 欄位，允許 main mode 1、2、3、4、5、7、8，
目前不提供 main mode 6 的後續命令。飛控拒絕、模式未讀回或等待逾時會停止序列並放手。
實際支援的模式／子模式與進入條件需要針對所用飛控韌體做 HIL 確認。

`ON_FINISH = 'hold'`：結束時必須已回到 Stabilized，roll／yaw 桿歸中，恢復原高度保持。
`ON_FINISH = 'loiter'`：結束時要求PX4 main=4/sub=3；保留飛手迴圈與中立MANUAL_CONTROL/heartbeat，以符合既有RC-loss設定，導航由PX4負責。

`ON_FINISH = 'release'`：結束後停止送桿，把控制交回原有人工輸入途徑；不自動 disarm。
空模板使用 `hold`，不送任何模式命令。

命令腳本與起飛程式共用一個 agent 連線、遙測與送桿迴圈，序列逐 tick 推進。
不要在模組或 `build_sequence()` 開 socket、直接送 MAVLink、sleep、等待或呼叫外部程序。
腳本在起飛前載入及檢查，但命令只在成功起飛與連續穩定條件滿足後執行一次。
一個 tick 最多推進一個步驟，不補發堆積的動作。

`stop-takeoff`、Ctrl+C、人類搖桿接手、遙測失聯與 disarm 都會停止後續動作。
序列執行期間如果飛控切到序列未要求的模式，也會放手。
native 根入口 `status --json` 中的 `pilot.after_state` 為 disabled、waiting、running、complete、failed 或 cancelled，
`pilot.after_step` 是目前的零起算步驟索引，`pilot.after_reason` 記錄中止原因。

native owner 擁有 managed pilot 的路由／session／log 設定，使用者不能透過 takeoff 覆寫保留參數。每個專案只有一個 owner；多套 HIL 的埠與環境隔離需另定範圍。

完整有界起飛／Hold／停止模型／disarm／reboot用根入口`test-takeoff-hold`。Hold預設60 s並要求完成至少一圈；每趟模型接入前先重開PX4。`takeoff --after after_takeoff_loiter`本身會持續保活至明確停止；不自動停止模型。


## 預留情境目錄

runtime 沒有 before_takeoff／after_arm hook，也沒有手持搬動／助跑／手拋功能。增加現有起飛後命令仍使用本目錄與 sequence.py，不另開 MAVLink owner。
