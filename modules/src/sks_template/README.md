# sks_template：把自己的算法放進 PX4 的一個例子

**這只是例子，讓人有個概念。** 真正要怎麼接，請 AI 在第 1 段先讀 PX4 原始碼，再和使用者討論方案（見 [AGENTS](../../../AGENTS.md) 第 1 段）。這裡示範的只是其中一種：在 OFFBOARD 模式裡，換掉固定翼控制鏈最上層的「導引」。

## 這個例子做什麼

- **接法**：模組編進韌體，自己發 OFFBOARD 訊號（`offboard_control_mode.velocity = true`），不需要外接任務電腦。PX4 進入 OFFBOARD 後，只把「導引」交給這個模組；高度與速度（`fw_lat_lon_control`）、姿態、角速度、控制分配都還是 PX4 原生的。
- **算法**（`SksTemplate::guidance()`，換成你的就改這一段）：進入 OFFBOARD 時記下當下的航向與高度；5 秒後航向目標 +30°，25 秒後高度目標 +10 m。側向加速度 = 地速 × 0.2 × 航向誤差（傾角限 20°），高度交給 PX4 的 TECS，空速用預設值。
- **出事時**：位置資料無效或太舊，就停發 OFFBOARD 訊號，PX4 自己的「OFFBOARD 失聯保護」接手（`COM_OF_LOSS_T`、`COM_OBL_RC_ACT`）。沒有這個模組在跑時，PX4 根本不讓你切進 OFFBOARD。

## 驗收（這個例子自己的標準）

`analysis/template_check.py` 讀飛控記錄（SITL、HITL 用同一支）：航向變化和 30° 差 ≤ 3°、高度變化和 10 m 差 ≤ 1.5 m、都要安定下來、最大傾角 ≤ 25°。SITL 的狀態是真值，HITL 是 FC 上 EKF 的估測，所以兩邊比的是表現，不要求逐點相同。

| | 結果 |
|---|---|
| SITL（2026-10-18） | PASS：航向 +29.3°（上升 10.5 s、安定 14.5 s）、高度 +9.66 m、最大傾角 16.8° |
| HITL | 見 README 的狀態表 |

觀察：空速在兩邊都比 PX4 的目標（15 m/s）高很多（SITL 約 27 m/s）。這不是範本造成的：PX4 參數 `FW_THR_TRIM=0.6`，而這個飛機模型在 15 m/s 平飛只需要約 0.115 的油門，原生模式的 HITL 盤旋也一樣偏快，屬於「模型與 PX4 參數不吻合」，另外處理。

## 照著做一個自己的模組

1. 複製 `modules/src/sks_template/` 成新名字，改掉檔名、類別名稱、`CMakeLists.txt` 的 `MODULE`／`MAIN`；在 `sitl/px4_external/src/` 照 `sks_template/` 加一個同樣的包裝，並列進那裡的 `CMakeLists.txt`。
2. 改 `guidance()`（或依第 1 段討論的接法，改成要換的那一層）。
3. SITL：照 `sitl/scenarios/template_offboard.json` 寫自己的情境，`sitl/build_sitl.py` → `sitl/run_sitl.py --scenario ...` → 自己的判定程式（照 `analysis/template_check.py`）。
4. 部署配方：照 `deploy/02_template/` 複製一份，`firmware/firmware.json` 的 `recipe.modules` 換成新模組，`sd/etc/extras.txt` 寫啟動指令，`hitl.json` 指定起飛後的動作（`hitl/commands/`）與判定程式。
5. `./runbridge deploy-test --release deploy/<新配方>` 先看計畫，再 `--flash`。
