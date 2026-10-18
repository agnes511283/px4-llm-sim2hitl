# plant：核心、C Truth 與 sensors

飛機的 6DOF 由 `model/FW_SkySurfer_HIL.slx` 轉碼成可重入的 C 核心（`core/`）；這裡另放用 C 寫的 Truth（由核心的狀態與力算出 `PlantTruth`）與 sensors（讀 Truth）。SITL（`sitl/` 的 `plant_sim` 模組）與 HITL（`hitl/aircraft/skysurfer/adapter.c`）用同一份；同一程序可跑多架，只用標準 C。只在 Ubuntu 24.04 x86-64 驗證過。

核心、C Truth、C sensors 都通過驗收。平常不用單獨跑這裡的程式：`./runbridge update-model --generate`（要 MATLAB）把產生的 C 存進 `model/generated/`，`./runbridge update-model` 再把它們和 `adapter.c` 編成模型 release，同時跑四道檢查（reuse-library 閘門、`validate_core.py`、`validate_plant.py`、`hitl/tests/validate_library.py`），全部 PASS 才發布。

| 位置 | 內容 |
|---|---|
| [include/plant_core.h](include/plant_core.h) | 核心 API 與 CoreSnapshot[72] 欄位索引（權威） |
| [include/skysurfer_plant.h](include/skysurfer_plant.h) | plant 介面：輸入、初值、`PlantTruth`；`Plant` 包一個核心並算 Truth |
| [include/plant_sensors.h](include/plant_sensors.h) | sensors 介面：設定（預設值）、輸出、`PlantSensors` |
| [include/plant_geo.h](include/plant_geo.h) | Truth 與 GPS 共用的平地經緯度換算與包角（同 MATLAB `flat2lla`） |
| [truth/plant_truth.c](truth/plant_truth.c) | C Truth |
| [truth/flat2lla_test_vectors.json](truth/flat2lla_test_vectors.json) | 生成：MATLAB `flat2lla` 的 88 個點（含 ±180° 與兩極），供驗收 |
| [sensors/plant_sensors.c](sensors/plant_sensors.c) | C sensors（PCG32 亂數、GPS 鎖存） |
| [sensors/plant_wmm.c](sensors/plant_wmm.c)、[sensors/plant_wmm.h](sensors/plant_wmm.h) | WMM 磁場（球諧函數到 12 階） |
| [sensors/plant_wmm_coeffs.c](sensors/plant_wmm_coeffs.c) | 生成：WMM2025 係數，不手改 |
| [sensors/gen_wmm_coeffs.py](sensors/gen_wmm_coeffs.py) | 產生上一列，來源是 MATLAB 內附的 `WMM2025.COF`。平常不用重跑；要重跑時明確給路徑 `<MATLAB>/toolbox/aero/aero/private/WMM2025.COF`（腳本的預設路徑是舊的 macOS 路徑），而且產生的檔案會記下來源路徑，所以內容會變 |
| [sensors/wmm_test_vectors.json](sensors/wmm_test_vectors.json) | 生成：MATLAB `wrldmagm` 的 660 個磁場值（含兩極、負高度、850 km、2029.99），供驗收 |
| [core/build_core.m](core/build_core.m) | 從已存檔的 SLX 在 cache 副本產生 Reusable function 的 C；開頭先過 reuse-library 閘門 |
| [core/reuse_policy_gate.m](core/reuse_policy_gate.m) | reuse-library 閘門：`.satk/reuse-libraries.json` 必須存在、`confirmed_none: true`、沒有列任何 library（builder 不支援自訂 library） |
| [core/plant_core.c](core/plant_core.c) | 生成碼外面的可重入包裝：每架自己的狀態、輸入、初值；狀態複製；讀連續狀態與 f(x, u)（配平用） |
| [core/toolchain.py](core/toolchain.py) | 編譯器、MATLAB、cache 位置（都可用環境變數指定） |
| [core/compile_core.py](core/compile_core.py) | 編成 `libskysurfer_core.so`（核心）與 `libskysurfer_plant.so`（核心＋Truth＋sensors）；手寫 C 以 `-Wall -Wextra -Werror` 檢查 |
| [core/validate_core.py](core/validate_core.py) | 核心驗收 |
| [core/validate_plant.py](core/validate_plant.py) | Truth 與 sensors 驗收 |
| [reference/record_reference.py](reference/record_reference.py) | 用目前的 active release 錄參考資料 |
| `reference/data/` | 參考資料（`reference.npz`）與來源身分（`manifest.json`） |

## 核心

- **來源邊界**：SLX 根層是 `Controls[16]` → `Actuator_Mapping` → `UAV` → `CoreSnapshot[72]`。CoreSnapshot 在 `UAV/UAV` 內以 Vector Concatenate 組成，欄位與單位見 `plant_core.h`。
- **builder 只改 cache 副本**：加 Thil 的 ZOH（輸出取 t_k）；把 SETTING1 的 7 個初值常數改由根層 `InitialConditions[7]` 輸入，風速、風向與風的模式改由根層 `Wind[4]` 輸入，因為 Reusable 生成碼的模型參數是共用的全域結構，放在輸入裡才會每架各一份；亂流以參考強度 W20 = 1 m/s 產碼，輸出乘上 `Wind[3]`（見下面「風」）。其餘氣動表、質量等參數各架共用（同一架飛機）。
- **連續狀態與 f(x, u)**（API 1.1）：37 個連續狀態（位置、機體速度、四元數、角速度、5 個致動器、16 個 Dryden 亂流濾波器、3 個陣風距離；順序與致動器對應見 `plant_core.h`）。`plant_core_get_state()` 讀出；`plant_core_eval()` 寫入狀態 x、套用命令、跑一個正常步，回傳該步 ode4 第一階的 f(t_k, x) 與 x 的 snapshot，和模擬是同一段程式。注意：(1) 新初始化的核心第一步會從初值輸入重新載入積分器，所以先步進一次再寫狀態；(2) 舵面在伺服之後有 rate limiter（記住前一次輸出），單次求值舵面最多動 2°，求平衡時同一狀態要寫入並步進數十次讓 limiter 到位（`sitl/trim.py`）。eval 之後核心已前進一步，所以在副本上做。
- **呼叫規則**：每架配置 `plant_core_size()` 位元組；`plant_core_step()` 先回報 t_k，再積分一步。同一程序可交錯跑多架，但一次一個呼叫，不在多執行緒同時呼叫。複製狀態一律用 `plant_core_copy()`（內部指標要重新指向新位置）。
- **單位**：照來源，SI；欄位名稱有 `_deg` 的是度。

## 手動建置與驗收

平常由 `update-model` 跑（見上）。不用 MATLAB MCP 時，第一段在 MATLAB 裡做（目前資料夾是專案根目錄、SLX 已存檔）：

```matlab
addpath('plant/core'); cache = build_core();
```

再 `./runbridge update-model --generate --cache <cache>`。要單獨重跑某一項檢查時，用 `./runbridge update-model` 印出的建置 cache（`~/.cache/px4-llm-sim2hitl/build_<時間>/`）；`PY` 是 venv 的 python（AGENTS 第 5 節）：

```bash
"$PY" -B plant/core/compile_core.py --cache <cache>
"$PY" -B plant/core/validate_core.py --cache <cache>
"$PY" -B plant/core/validate_plant.py --cache <cache>
```

結果在 `<cache>/results/core_validation.json`、`plant_validation.json`，發布時也封進 release。

- **核心**（阻擋）：14 個參考 case 都跑完且值有限；兩架交錯、狀態複製後續跑、重新初始化都和單獨執行逐位元相同；`plant_core_eval` 對讀回的狀態與正常步逐位元相同，寫入不同狀態時輸出確實改用它。
- **對參考資料的比對**（只報告、不阻擋）：14 個 case 中核心也有輸出的欄位與 `reference/data` 一致，容差 1e-9（相對於 max(1, |值|)）；yaw 包到 [0, 2π) 後比。它回答「這次建置算出的和錄下來的一樣嗎」；刻意改了模型就本來會不同。
- **plant**（13 項，除了 Truth 對參考資料的比對只報告，其他都阻擋）：
  - 自我檢查：比對工具遇到 NaN／Inf 一律判 FAIL。
  - 版面：5 個公開 struct 的大小與 77 個欄位位置，C 與 ctypes 一致。
  - Truth：14 個參考 case 中與舊 Truth 同義的欄位一致，容差 1e-9（只報告）。
  - 一致性：重力 |F_gravity| = m·g、比力兩種算法一致；不支援的輸入（非零初始角速度、site_msl、非有限值的風、陣風長度 0）被拒絕。
  - 風：從 t = 0 吹定常風時，Truth 的風等於輸入的風（1e-6 m/s），空速和無風時不同。
  - 多架與狀態：兩架交錯、狀態複製都逐位元相同。
  - 經緯度：與 MATLAB `flat2lla` 的 88 個點一致（1e-9°）；正好在極點且東向位移 > 1 m 的 10 個點只檢查範圍。
  - WMM：與 MATLAB `wrldmagm` 的 660 個值一致（< 1e-3 nT）。
  - 感測器：無雜訊時每個輸出欄位都等於理想值；GPS 每 25 步更新、其間保持；有雜訊時各通道標準差與設定差 5% 以內（GPS 8%）；震動選項；同種子重現、不同種子不同、狀態複製後續跑相同。
  - 邊界：GPS 在 ±180° 經度與兩極附近加雜訊後仍在合法範圍；航跡角不會等於 2π（360°）。

## C Truth

`plant_step()` 把核心的 CoreSnapshot 換算成 `PlantTruth`：

- 經緯度：與來源 `Flat Earth to LLA`／MATLAB `flat2lla` 相同的公式與包角（WGS84、ψ = 0、參考高度 0；`plant_geo.h`）。正好在極點時經度沒有定義（平地模型的奇異點），只保證輸出在合法範圍。MSL 高度 = 離地高度（site_msl = 0）。
- 地速是水平速度；航跡角在 [0, 2π)。
- 比力（理想加速度計）= Ab − Vb×ω − F_gravity/m，與來源 `Measurement/acc` 相同；另以（氣動＋推力＋地面）/m 核對。質量來自模型（`model/FW_SkySurfer_InitialFunction.m` 的 `Mass0`，建置時以 `-DPLANT_MASS_KG` 傳入），g = 9.80665 寫在 `plant_truth.c`；驗收每一步核對 |F_gravity| = m·g。
- α、β、舵角轉成弧度；動壓 = ½ρV²；`airspeed_true_m_s` 是真空速。
- `flags`（氣動作用時）：bit 0 是 α 或 β 超出氣動表，bit 1 是 Mach 超出氣動表（超出時表會外插）。
- 風：`PlantTruth.wind_ned_m_s` 是實際作用的風（地速 − 機體轉到 NED 的空氣相對速度），有風時才填。
- 只支援初始角速度為零、site_msl = 0；其他值回傳 `PLANT_ERR_INPUT`。

## C sensors

`plant_sensors_step()` 讀 `PlantTruth`，輸出和 HIL ABI 相同單位的感測器值。預設值由 `plant_sensors_default_config()` 提供，都可以改：

| 感測器 | 模型 | 預設雜訊（每筆標準差） | 來源 |
|---|---|---|---|
| accel | 比力＋白雜訊 | 65／65／70 µg/√Hz → 7.1e-3／7.1e-3／7.7e-3 m/s² | ICM-42688-P datasheet |
| gyro | 機體角速度＋白雜訊 | 2.8 mdps/√Hz → 5.5e-4 rad/s | 同上 |
| 磁力計 | WMM2025（日期固定 2026.0）轉到機體軸＋白雜訊 | 2／2／3 µT | PX4 `sensor_mag_sim` |
| 氣壓 | 核心的 ISA 靜壓＋白雜訊 | 2.7 Pa | MS5611 OSR 1024（PX4 driver 設定） |
| 差壓 | ±½ρu²（u 為相對空氣的機體 x 速度，同 PX4 `sensor_airspeed_sim`） | 0 | 使用者決定（PX4 `sensor_airspeed_sim` 為 1 Pa） |
| GPS | 每 25 步（10 Hz）一筆，其間保持；位置、NED 速度＋白雜訊 | 水平 0.2 m、垂直 0.5 m；速度 0.06／0.077／0.158 m/s | PX4 `sensor_gps_sim` |
| 震動（選項，預設關） | throttle > 0 時加在 accel、gyro | 0.5／1.7／1.4 m/s²；0.14／0.07／0.03 rad/s | PX4 SIH（Bulka & Nahon 2018） |

IMU 的 noise density 換成每筆標準差：σ = density·√(1/(2·dt))。沒有 bias、比例誤差與延遲。亂數是每架各自的 PCG32，種子由 `plant_sensors_init()` 給；同種子同輸入必得同輸出。`noise_enabled = 0` 只供測試：PX4 會把完全不變的感測器判為卡住。

## 地面

模型的地面是很簡化的一塊（`UAV/UAV/Ground Model`，參數在 `model/FW_SkySurfer_InitialFunction.m` 的 `uavData.contact`）。看起飛、落地的結果或換飛機前要知道：

- **只有一個接觸點，就在重心**：沒有輪子、起落架、機腹的位置。地面是一整片平地，就在模型位置的高度 0（場景的離地高度 `height_agl_m` 從這裡量），沒有地形。
- **往上推的力**：重心低於地面時才有，像很硬的彈簧加阻尼（自然頻率 20 Hz、臨界阻尼），只推不拉。靜止時約陷下 0.6 mm。
- **摩擦**：係數 0.2，各方向都一樣（沒有「輪子往前好滾、側向難滑」的分別），北、東兩個方向各自算，速度很小時用 tanh 平滑（`vd` = 0.02 m/s）。像一個在地上滑的雪橇：推力要大過約 0.2 × 重量才會開始動（SkySurfer 1.3 kg，約 2.6 N）。
- **地面不產生力矩**：力作用在重心，所以地面不會把飛機扶正，也不會擋住機頭或機尾。地上的姿態只會被氣動力矩改變，而氣動的力與力矩在空速 5 m/s 以下都是 0。結果是：
  - 靜止時姿態就是場景給的值（`hitl/scenarios/ground.json` 的 pitch 0.8633°）；
  - 起飛時一拉升降舵機頭就能抬，不會擦到機尾；
  - 地上遇到側風會側傾甚至翻倒（10 m/s 約側傾 68°，見下一節），滑跑方向也沒有鼻輪或尾輪控制。
- **落地或撞地沒有另外處理**：只是被彈簧擋住；模型和 runtime 都不判定墜毀，要看記錄自己判斷。
- SITL 的情境從空中開始，用不到地面；HITL 一律從地面靜止開始，所以地面主要影響 HITL 的起飛（[autotakeoff README](../hitl/autotakeoff/README.md)）。
- 換飛機時：接觸點、彈簧、摩擦都是照 SkySurfer 這種小飛機定的。有起落架、要看機尾擦地或地面滑行轉向時，這個地面不夠，要改模型（第 1.1 段）。
- 原始模型裡被註解掉的 `6DoF/Ground` 是 Simulink 的「Ground」方塊（只給一個 0 訊號），和這個地面無關。

## 風

**模型裡的風**（`model/FW_SkySurfer_HIL.slx` 的 `UAV/UAV/Environment/Wind`，Aerospace Blockset 方塊）有兩種模式，二選一，不疊加：

| 模式 | 內容 | 平均風從哪來 |
|---|---|---|
| 1 定常風 | Horizontal Wind Model：固定風速、風向 | 就是這個定常風 |
| 2 低空風 | Wind Shear Model（風切）＋Discrete Wind Gust（陣風，1−cos 形狀）＋Dryden 亂流（MIL-F-8785C，連續 +q −r） | 風切模型：給 6 m（20 ft）高的風速與風向，越高越大；**模式 1 的定常風不加進來** |

- **風向一律是「風從哪裡吹來」**（0° = 從北方吹來）；`steady_ned_m_s` 則是空氣的 NED 速度（往哪裡吹），程式自己換算。只有水平風，垂直分量不用。
- **亂流**：原作者把 Dryden 方塊註解掉了，因為停在地面時空速 0，它的濾波器除以空速會變成無限大。2026-10-18 取消註解，空速輸入加 5 m/s 下限（與氣動開始作用的門檻相同，飛行中不起作用），雜訊間隔由 0.1 s 改成 `Thil`（0.004 s；0.1 s 時角速度擾動少約 8–10 %，且讓模型變成兩種速率）。預設強度仍是 0、模式 1，所以無風時結果和改之前逐位元相同。
- **亂流強度**：Dryden 的強度在編譯時算定，所以核心以參考強度 W20 = 1 m/s 產碼，輸出乘上想要的 W20（`Wind[3]`）。1000 ft（305 m）以下的強度和 W20 成正比，這樣是準的；以上不準。要更高或要精確，就把來源的 W20 設成想要的值重新產碼（`./runbridge update-model --generate`），這也是另一種做法。隨機種子固定，所以每次亂流相同、SITL 與 HITL 可比。
- **陣風、風切、亂流的參數**在產生的 C 裡是共用的全域值；`plant_truth.c` 每一步先套用這一架的設定再步進，所以同一個程式跑多架也各自獨立（一次一個呼叫）。
- **什麼時候開始吹**（`PlantWindConfig.start_mode`）：預設「離地後」（高度超過 5 m），另有「指定時間」與「一開始」。停在地上遇到側風，模型會轉向並翻倒（10 m/s 側風約側傾 68°），地上就有空速也會讓 PX4 的起飛前檢查和 EKF 出問題，所以預設離地後才吹。開始後定常風、風切、亂流在 `ramp_s`（預設 5 s）內線性加上；陣風在開始後 `gust_start_s` 才來。
- **陣風會一直維持**：Discrete Wind Gust 照 1−cos 形狀在陣風長度（飛過的距離）內增強到設定大小，之後保持不變，不會自己消失；垂直分量因此是持續的上升或下沉氣流。
- **怎麼設**：SITL 情境與 HITL 場景都用同一個 `"wind"` 物件，格式與提醒在 [wind.py](wind.py)；例子 `sitl/scenarios/wind_steady.json`、`wind_low_altitude.json`。
- **驗收**：`build_core.m` 的 wind 對照（全部風都開）原始模型與核心副本逐位元相同；HIL 函式庫的 wind case 和 Simulink 一致（`hitl/tests/validate_library.py`）；Truth 的風等於輸入。

## plant 介面重點

- **輸入**：`PlantActuatorCommand` 五個正規化命令（左副翼、右副翼、升降舵、方向舵、油門），等於 PX4 `HIL_ACTUATOR_CONTROLS` 經 `HIL_ACT_FUNC` 對應後的通道，也就是 HIL ABI 的 `controls[0..4]`。每單位幾度、正負號在核心的 ACTUATOR 子系統。
- **Truth**：每一步都填滿所有欄位（位置、速度、姿態、角速度、加速度、空速、α、β、大氣、舵角、力與力矩分解、接地旗標）。SITL 要發布哪些欄位給 PX4，在 plant 外面決定，plant 不因專案而改。
- **狀態**：`Plant` 不透明，用 `plant_copy()` 複製，用於配平、與參考逐層比對、RL 重設。
- **輸出時間點**：`plant_step()` 回報積分前的 t_k，與 HIL ABI 相同。
- **sensors 分開**：IMU、氣壓、磁力計、空速、GPS 由 `PlantSensors` 讀 Truth 產生，見上一節。

## 參考資料

`reference/record_reference.py` 載入 active release 的 `libskysurfer.so`，以固定初值與控制序列逐步執行，存下每一步的 58 個 raw 欄位（名稱在 `hitl/poc/source_columns.json`，位置與單位在 `hitl/aircraft/skysurfer/adapter.c` 的 `fill_raw()`）。它只呼叫模型 ABI，不開序列埠、不連 PX4、不需要 MATLAB。

```bash
"$PY" -B plant/reference/record_reference.py
```

`manifest.json` 記錄是哪個 release 錄的（`model_build_id`）、library 與腳本的 SHA-256、每個 case 的初值與控制、樣本數與是否被發散保護截斷。刻意改了模型後，先確認 `update-model` 的 Simulink 對照（`validate_library.py`）通過，再用新的 active release 重錄。

感測器欄位（raw 39–57）來自 C sensors（固定預設種子），只當比較對象；感測器本身的驗收在 `validate_plant.py`，adapter 的欄位對應與時序在 `hitl/tests/validate_library.py`。
