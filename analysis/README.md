# analysis：判定與指標

SITL 與 HITL 共用的分析程式（[ROADMAP](../docs/ROADMAP.md) 批次 4g）。

| 檔案 | 用途 |
|---|---|
| [response.py](response.py) | 搖桿階躍情境的響應指標（定義見程式開頭的說明）：基準與其斜率、尾窗平均與其斜率、變化量、峰值、上升時間（10→90 %）、安定時間（5 % 帶；未安定為 null）、roll／pitch 的絕對設定值與 `change_error`（相對）、`abs_error`（絕對）、越過絕對設定值的超越量；資料不完整就 `valid=false`、exit 2 |
| [hitl_trace.py](hitl_trace.py) | HITL 的 `host/wire.bin` 轉成 SITL 欄位的 trace（`response.py --hitl-log` 呼叫） |
| [ulog.py](ulog.py) | ULog 讀檔（只用 numpy）：各主題的 structured array、info（`ver_hw`、`ver_sw`）、參數、dropout、log 訊息；`intervals()` 算記錄間隔 |
| [replay_compare.py](replay_compare.py) | ULog 重播的輸出比對與輸入記錄品質（`sitl/run_sitl.py --replay` 呼叫；做法見 [sitl README](../sitl/README.md)） |

```sh
python3 analysis/response.py \
    --trace <run>/instance_0/trace.csv --scenario sitl/scenarios/stabilized_steps.json --out metrics.json
```

- 輸入是 `trace.csv`（plant 真值、搖桿、五路 controls，[sitl README](../sitl/README.md)）與情境檔；設定值換算用 `deploy/00_native/` 的 `FW_MAN_R_MAX`、`FW_MAN_P_MAX`。
- roll／pitch 階躍看姿態角；設定值由 trace 裡的搖桿算（所以 SITL 與 HITL 同一套），另讀 `FW_PSP_OFF`。yaw 搖桿在 Stabilized 是經由偏航角速度設定值驅動方向舵，看機體偏航角速度 r，主要看峰值；之後因方向穩定性衰減，沒有超越量，`settled` 也剛好在漂移門檻附近，不拿來驗收。
- 「尾窗平均」是階躍最後 30 % 的平均，不一定是穩態；`tail_slope_per_s` 大或 `settled=false` 時，`abs_error` 只代表窗口結束時還差多少。
- 資料品質：時間軸要有限且嚴格遞增；每個窗口（階躍前 1 s、階躍、尾窗，以及那一軸的搖桿在階躍前 1 s 到階躍結束）都要有限值、相鄰樣本間隔 ≤ `--max-gap`（預設 0.05 s）且涵蓋整個窗口；不合格的階躍 `valid=false` 並列出 `problems`，exit 2。JSON 不寫 NaN（算不出的值是 null）。
- SITL 重跑結果不逐位元相同（PX4 work queue 先後不固定），比對兩次結果時用容差；參考情境 3 次重跑的指標差異見 VALIDATION。
- **HITL**（批次 4i）：runtime 不記 plant 真值，所以從 `<log>/host/wire.bin` 的 MAVLink 轉 trace：

  ```sh
  python3 analysis/response.py --hitl-log <飛行 log 目錄> --scenario sitl/scenarios/stabilized_steps_hitl.json --out <目錄>/metrics.json
  ```

  - 會在 `--out` 旁邊寫 `hitl_trace.csv`、`hitl_scenario.json`（實測的階躍時間），再算指標；輸出另含 `hitl_conversion`（各階躍與名目時間的差、樣本數、序列期間各來源的最大間隔）。
  - 來源：FC 回傳的 `ATTITUDE`（100 Hz，**EKF2 姿態與濾波後角速度**；SITL 是 plant 真值）、`LOCAL_POSITION_NED`（高度 = −z，EKF2 原點以上）、`VFR_HUD`（**CAS**，100 m 時比 TAS 低約 0.5 %）、`HIL_ACTUATOR_CONTROLS`（controls[0..4]）；搖桿用實際寫給 FC 的 `MANUAL_CONTROL`。每個封包都驗 CRC，跨 record 的封包會接起來。
  - 階躍時間用量的：飛手序列以 50 Hz tick 推進，每個動作最多晚一個 tick。序列起點是第一個等於情境基準桿量的 MANUAL_CONTROL；送出的桿量必須和情境一致到 1/1000，不一致就報錯，不會默默對錯時間。
