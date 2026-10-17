# 00_native：原生 PX4 基準

原生 PX4 v1.17.0（[px4_lock.json](../../px4/px4_lock.json)，不改程式）加上 FC 參數，是 SITL 與 HITL 比對的基準，也是第一次接手的 LLM 確認整套流程能跑通的參考（[ROADMAP](../../docs/ROADMAP.md) 決定 17）。

## 參數

| 檔案 | 內容 | 來源 |
|---|---|---|
| [fc_params_20261013.params](fc_params_20261013.params) | QGC 匯出的 FC 全部參數（1,208 個），原樣保存、不手改 | FC 在 2026-10-13 21:35 的狀態：PX4 v1.17.0（`d6f12ad1`）、`SYS_AUTOSTART=2100`（Generic Standard Plane）、`SYS_HITL=0`；SHA-256 `ec3cd0d049eba223ce9aeba609f1368552f7938f5294875a3337dda99ce9b38b` |
| [hitl_overrides.params](hitl_overrides.params) | 在上一個檔上加的 HITL 設定：`SYS_HITL=1`、`HIL_ACT_FUNC1..5 = 201, 202, 203, 204, 101`、`HIL_ACT_REV=2`（右副翼反向）、`SDLOG_PROFILE=17`（預設＋高頻記錄，給 ULog 重播；只影響記錄） | `SDLOG_PROFILE` 由使用者 2026-10-16 決定（批次 4h），FC 上已是 17（ULog 參數確認）；`HIL_ACT_FUNC1..5`、`HIL_ACT_REV` 也由 ULog 讀回確認（VALIDATION「FC 基準」）。通道對應由 model ABI 的通道（controls[0..4] = 左副翼、右副翼、elevator、rudder、throttle，[MODEL_INTERFACE](../../docs/MODEL_INTERFACE.md) 第 2 節）與 2100 的舵面配置推得；反向由 HITL wire log 推得：飛行中 controls[0] 與 controls[1] 每一筆都相同，而 plant 兩個副翼通道都是「正值 → 左滾」 |

- **完整參數** = `fc_params_20261013.params` 再套 `hitl_overrides.params`。
- **SITL**：輸出走 `pwm_out_sim` 的 `PWM_MAIN` 群組，不是 `HIL_ACT`；SITL 用 `PWM_MAIN_FUNC1..5` 設成同一組 function 值。
- **增益**：抽查的姿態與角速度增益 9 個（`FW_R_TC`、`FW_P_TC`、`FW_RR_P/I/FF`、`FW_PR_P/I/FF`、`FW_YR_P`）與原始碼的預設值相同（決定 14：不調 PX4 參數）；其餘參數未逐項對照預設值。
- **排除**：感測器校正（`CAL_*`）、硬體相關的參數只屬於實體 FC，SITL 不套用。

## 與 FC 現況的關係

- 2026-10-16 用 FC 的 ULog 參數（1,143 個）比對過：`HIL_ACT_FUNC1..5`、`HIL_ACT_REV=2`、`SDLOG_PROFILE=17` 與本資料夾相同；不同的只有實體感測器校正（`CAL_ACC3_*`、`CAL_MAG1_*`）與飛行計數器（`COM_FLIGHT_UUID`、`LND_FLIGHT_T_*`），控制參數沒有差異（VALIDATION「FC 基準」）。核對方法：飛一趟後讀 ULog 的參數（`analysis/ulog.py`），逐項比對；有差異就更新本資料夾並記入 CHANGELOG。
- 目前的基準取自 FC。正式流程反過來：本資料夾的參數檔是唯一來源，部署時由專案寫到 FC（ROADMAP 批次 5）；FC 上不手動改參數。
- **部署參數** [params.json](params.json)（ROADMAP 決定 18）：這是 **HITL 配方**（`SYS_HITL=1`）。只記跟韌體預設不同的：`airframe`＝機架 2100 腳本開機時設的值、`boot`＝STM32H7 板子架構預設（`EKF2_MULTI_IMU`、`SENS_IMU_MODE`、`MC_AT_EN`、`UAVCAN_ENABLE`）與 `rcS` 在 HITL 時設的 `GPS_1_CONFIG=0`（兩者都只核對、不寫）、`verify_only`＝`SYS_AUTOSTART`、`set`＝專案要寫的 11 個（HITL 8 個＋`MAV_1_CONFIG`、`MAV_1_FLOW_CTRL`、`SENS_EN_THERMAL`：FC 上原有、沒有開機腳本設，來源不明，照決定 14 保留）、`fc_owned`＝這台 FC 與其安裝的參數（校正、空速管型號、操作者遙控器的 RC 校正與通道對應、板子安裝、電源模組、裝置 ID、計數器、學到的磁偏角）：值不寫不比，但要讀到；規則解析出的 499 個名字存在檔內。其他參數一律應等於 `firmware/parameters.json.xz` 的預設值。檢查：`python3 deploy/check_params.py --readback <param-readback 的 params_*.json>`（PASS 0、FAIL 3、INCOMPLETE 5；含身分：board 56、git 前 10 碼、參數名單與韌體檔的 SHA）；`not_default` 只是報告，不是寫入清單。寫到 FC：`./runbridge.command param-plan --out DIR` 先看要寫什麼，`./runbridge.command param-deploy --out DIR`（C 級，確認視窗）只寫 `set` 的差異，有寫入就等存檔後重開 FC 讀回，失敗只改回自己寫的值（[BEHAVIOR_CONTRACT](../../hil_bridge/docs/BEHAVIOR_CONTRACT.md) 7d）。換 PX4 版本：`--compare-firmware 舊.json.xz 新.json.xz` 列出新增、刪除、預設值或型別或重開機標記改變、我們管的、被 fc_owned 規則新吞進的；新版的開機腳本也要一起看。實機飛行（`SYS_HITL=0`）要另一份配方：`rcS` 的 HITL 分支是用 `param set` 關掉 GPS，回到實機時不會自動恢復。上面兩個 `.params` 是取得基準時的原始資料，SITL 仍用它們。

## 韌體

專案自建的 HITL 韌體在 [firmware/](firmware/)，整個資料夾複製到別台電腦時韌體跟著走，不必重建也能刷：

| 檔案 | 內容 |
|---|---|
| [firmware.json](firmware/firmware.json) | 配方與身分：board、PX4 tag／commit、Docker image（tag 與 digest）、toolchain、建置指令、產物 SHA-256、內嵌的 board_id／git hash、flash 用量、是否已刷 |
| [px4_fmu-v6c_default.px4](firmware/px4_fmu-v6c_default.px4) | 建置產物原樣保存（內含 `.bin` image、`parameters.xml`、`airframes.xml`）；SHA-256 記在 `firmware.json` |
| [parameters.json.xz](firmware/parameters.json.xz) | 建置產物原樣保存：這個韌體定義的全部參數（2,038 個，含名稱、型別、預設值、是否要重開機） |

- **建置**：在 PX4 官方 Docker image 裡跑 `make px4_fmu-v6c_default`（指令在 `firmware.json`）。image 用 digest 鎖定，就是 v1.17.0 原始碼樹自己 CI 用的那個；有 arm64 與 amd64 版，任何有 Docker 的電腦都能建。原始碼樹照舊放 Dropbox 外，建置前後都要 `python3 px4/check_px4_tree.py` PASS；產物寫到原始碼樹的 `build/px4_fmu-v6c_default`（和 SITL 的 build 目錄分開）。
- **掛載**：用 `--mount type=bind,src=<PX4_ROOT>,dst=/src`。Docker Desktop 29.8.2 上 `-v <路徑>:<路徑>:rw` 會把容器裡的掛載點弄錯，容器看到空資料夾。
- **重建**：`.px4` 的檔頭有 `build_time`，每次重建的 SHA-256 都不同；兩次建置的位元組是否相同還沒驗證（NOT_RUN）。
- **flash 用量** 97.97 %（1,926,128／1,966,080 bytes）：加客製模組時可能要從 board 設定拿掉用不到的模組。
- **參數名單的用途**：PX4 的 `PARAM_REQUEST_LIST` 只送「有在用」的參數（`param_count_used()`），沒在用的參數仍可用名字讀寫。完整讀回 = 清單＋依本名單用名字補讀（`./runbridge.command param-readback`，[BEHAVIOR_CONTRACT](../../hil_bridge/docs/BEHAVIOR_CONTRACT.md) 7c）。QGC 匯出的 1,208 個與 ULog 多出的 14 個都在名單內。名單的 `rebootRequired` 有 PX4 產生器的 bug：12 個（`ADSB_*` 6 個、`IMU_GYRO_*`／`IMU_DGYRO_CUTOFF` 6 個）XML 是 false、JSON 是 true，所以「要重開機」的 270 個是保守集合（XML 為 258 個）。
- **FC 上的韌體**：2026-10-16 已刷入本資料夾的 `.px4`（`firmware.json` 的 `flashed`；uploader 核對 board 56、Verify 100 %）。FC 只回報 git hash 前 5 bytes 與板型，比不到檔案 SHA，所以「FC 上跑的是這個檔」靠刷機紀錄＋刷後讀回（`git_hash_prefix`、board、SIH 參數出現）。之前的韌體檔沒有追溯（沒有 SIH 相關參數，組態與自建版不同）。
- **FC 硬體**：Pixhawk 6C（`px4_fmu-v6c`）。IMU0 是 BMI055（`CAL_ACC0_ID`／`CAL_GYRO0_ID` 的 devtype 0x41／0x42），另有 ICM-42688-P。ULog 的 `ver_hw` 是 `PX4_FMU_V6C`（子型號 `V6C000001`）、`ver_sw` 是 `d6f12ad1…`。
- **SITL**：本機原始碼樹的 `build/px4_sitl_default_skysurfer`（加了 `sks_sim`，[sitl README](../../sitl/README.md)），同一個 commit；原本的 `build/px4_sitl_default` 執行檔內嵌 commit `d6f12ad1c4f70ad3230afd7d86e971421e02fef4`、tag `v1.17.0`，無 dirty 標記（[px4 README](../../px4/README.md)）。
