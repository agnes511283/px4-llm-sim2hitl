# plant 核心、C Truth 與 sensors（開發中）

plant 的 6DOF 由 `FW_SkySurfer_HIL.slx` 轉碼成可重入的核心（`core/`）；本資料夾另放用 C 重寫的 Truth（由核心的狀態與力算出 `SksTruth`）與 sensors（讀 Truth）。完成後供 SITL 與 HITL 共用，同一程序可跑多架，只用標準 C，macOS 與 Windows 用同一份原始碼。模型審查見 [MODEL_REVIEW](../docs/MODEL_REVIEW.md)。

**目前狀態**：核心、C Truth、C sensors 都通過驗收。HIL library 由 `hil_runtime/update.py` 把它們與 `hil_runtime/aircraft/skysurfer/adapter.c` 編成 release（見 [MODEL_INTERFACE](../docs/MODEL_INTERFACE.md)、[BUILD_AND_RELEASE](../docs/BUILD_AND_RELEASE.md)）；發布時同時跑這裡的驗收腳本。整體計畫見 [ROADMAP](../docs/ROADMAP.md)。

| 位置 | 內容 |
|---|---|
| [include/sks_core.h](include/sks_core.h) | 核心 API 與 CoreSnapshot[72] 欄位索引（權威） |
| [include/skysurfer_plant.h](include/skysurfer_plant.h) | plant 介面：輸入、初值、`SksTruth`；`SksPlant` 包裝一個核心並計算 Truth |
| [include/sks_sensors.h](include/sks_sensors.h) | sensors 介面：設定（預設值）、輸出、`SksSensors` |
| [truth/sks_plant.c](truth/sks_plant.c) | C Truth 實作 |
| [sensors/sks_sensors.c](sensors/sks_sensors.c) | C sensors 實作（PCG32 亂數、GPS 鎖存） |
| [sensors/sks_wmm.c](sensors/sks_wmm.c)、[sensors/sks_wmm.h](sensors/sks_wmm.h) | WMM 磁場計算（球諧函數到 12 階） |
| [sensors/sks_wmm_coeffs.c](sensors/sks_wmm_coeffs.c) | 生成：WMM2025 係數（由 `gen_wmm_coeffs.py` 從 MATLAB 內附的 `WMM2025.COF` 產生，不手改） |
| [sensors/gen_wmm_coeffs.py](sensors/gen_wmm_coeffs.py) | 產生上一列 |
| [sensors/wmm_test_vectors.json](sensors/wmm_test_vectors.json) | 生成：MATLAB `wrldmagm` 的 660 個磁場值（含兩極、負高度、850 km、2029.99），供驗收 |
| [include/sks_geo.h](include/sks_geo.h) | Truth 與 GPS 共用的平地經緯度換算與包角（同 MATLAB `flat2lla`） |
| [truth/flat2lla_test_vectors.json](truth/flat2lla_test_vectors.json) | 生成：MATLAB `flat2lla` 的 88 個點（含 ±180° 與兩極），供驗收 |
| [core/build_core.m](core/build_core.m) | 從已存檔的 SLX 在 cache 副本產生 Reusable function 的 C；開頭先過 reuse-library 閘門 |
| [core/reuse_policy_gate.m](core/reuse_policy_gate.m) | reuse-library 閘門：`.satk/reuse-libraries.json` 必須存在、`confirmed_none: true`、沒有列任何 library（[MODEL_INTERFACE](../docs/MODEL_INTERFACE.md) 第 1 節） |
| [core/sks_core.c](core/sks_core.c) | 生成碼外面的可重入包裝：每架自己的狀態、輸入、初值；狀態複製；讀連續狀態與 f(x, u)（配平用） |
| [core/compile_core.py](core/compile_core.py) | 編譯成 `libskysurfer_core.dylib`（核心）與 `libskysurfer_plant.dylib`（核心＋Truth＋sensors）；手寫 C 以 `-Wall -Wextra -Werror` 檢查 |
| [core/validate_core.py](core/validate_core.py) | 核心驗收：對參考資料、多架、複製、重新初始化、狀態存取與 f(x, u) |
| [core/validate_plant.py](core/validate_plant.py) | Truth 與 sensors 驗收 |
| [reference/record_reference.py](reference/record_reference.py) | 用目前 active release 錄製參考資料 |
| `reference/data/` | 參考資料（`reference.npz`）與來源身分（`manifest.json`） |

## 核心

- **來源邊界**：SLX 根層是 `Controls[16]` → `Actuator_Mapping` → `UAV` → `CoreSnapshot[72]`。CoreSnapshot 在 `UAV/UAV` 內以 Vector Concatenate 組成，欄位與單位見 `sks_core.h` 與 [MODEL_INTERFACE](../docs/MODEL_INTERFACE.md#7-plant-核心coresnapshot)。
- **builder 只改 cache 副本**：加 Thil 的 ZOH（輸出取 t_k）；把 SETTING1 的 7 個初值常數改由根層 `InitialConditions[7]` 輸入，因為 Reusable 生成碼的模型參數是共用的全域結構，初值放在輸入結構裡才會每架各自一份。其餘氣動表、質量等參數各架共用（同一架飛機）。
- **連續狀態與 f(x, u)**（API 1.1）：21 個連續狀態（位置、body 速度、四元數、角速度、5 個致動器、3 個陣風距離；順序與致動器對應見 `sks_core.h`）。`sks_core_get_state()` 讀出；`sks_core_eval()` 把狀態 x 寫入、套用命令、跑一個正常步，回傳該步 ode4 第一階的 f(t_k, x) 與 x 的 snapshot，和模擬是同一段程式（驗收：與 `sks_core_step` 逐位元相同）。注意兩點：(1) 新初始化的核心第一步會從初值輸入重新載入積分器，所以先步進一次再寫狀態；(2) 舵面在伺服之後有 rate limiter（記住前一次輸出），單次求值舵面最多動 2°，要求平衡時同一狀態寫入並步進數十次讓 limiter 到位（`sitl/trim.py`）。eval 之後核心已前進一步，所以在副本上做。
- **呼叫規則**：每架配置 `sks_core_size()` 位元組；`sks_core_step()` 先回報 t_k，再積分一步。同一程序可交錯跑多架，但一次一個呼叫，不在多執行緒同時呼叫。複製狀態一律用 `sks_core_copy()`（內部指標要重新指向新位置）。
- **單位**：照來源，SI；角度欄位名稱有 `_deg` 的是度。

建置與驗收（MATLAB 已開啟，SLX 已存檔）：

```matlab
addpath('plant/core'); cache = build_core();
```

```bash
python3 plant/core/compile_core.py --cache <cache>
"$HOME/Library/Application Support/SkySurferHIL/venv/bin/python" plant/core/validate_core.py --cache <cache>
"$HOME/Library/Application Support/SkySurferHIL/venv/bin/python" plant/core/validate_plant.py --cache <cache>
```

驗收（`<cache>/results/core_validation.json`）：14 個參考 case 中，核心也有輸出的欄位與參考資料一致（容差 1e-9，相對於 max(1, |值|)）；兩架交錯、狀態複製後續跑、重新初始化都要與單獨執行逐位元相同；`sks_core_eval` 對讀回的狀態與正常步逐位元相同，寫入不同狀態時輸出確實改用它。參考資料的 yaw 包到 [0, 2π)，比對時依此換算；`AirSpeed_m_s` 自 2026-10-16（plant 為基礎的 release）起是真空速，舊 export 錄的是相對空氣速度的 body x 分量（MODEL_REVIEW P8）。

## C Truth

`sks_plant_step()` 把核心的 CoreSnapshot 換算成 `SksTruth`：

- 經緯度：與來源 `Flat Earth to LLA`／MATLAB `flat2lla` 相同的公式與包角（WGS84、ψ = 0、參考高度 0；`sks_geo.h`）。正好在極點時經度沒有定義（平地模型的奇異點），只保證輸出在合法範圍。MSL 高度 = 離地高度（site_msl = 0）。
- 地速是水平速度；航跡角在 [0, 2π)。
- 比力（理想加速度計）= Ab − Vb×ω − F_gravity/m，與來源 `Measurement/acc` 相同；另以（氣動＋推力＋地面）/m 核對。質量 1.3 kg 與 g = 9.80665 寫在 `sks_plant.c`，驗收每一步核對 |F_gravity| = m·g，初始化腳本改了就會失敗。
- α、β、舵角轉成弧度；動壓 = ½ρV²。
- `flags`（氣動作用時）：bit 0 是 α 或 β 超出氣動表，bit 1 是 Mach 超出氣動表（表會外插，見 MODEL_REVIEW A4）。
- 只支援零風、初始角速度為零、site_msl = 0；其他值回傳 `SKS_ERR_INPUT`。

## C sensors

`sks_sensors_step()` 讀 `SksTruth`，輸出與 HIL ABI canonical 欄位相同單位的感測器值。預設值（ROADMAP 決定 15）由 `sks_sensors_default_config()` 提供，都可以改：

| 感測器 | 模型 | 預設雜訊（每筆標準差） | 來源 |
|---|---|---|---|
| accel | 比力＋白雜訊 | 65／65／70 µg/√Hz → 7.1e-3／7.1e-3／7.7e-3 m/s² | ICM-42688-P datasheet |
| gyro | 機體角速度＋白雜訊 | 2.8 mdps/√Hz → 5.5e-4 rad/s | 同上 |
| 磁力計 | WMM2025（日期固定 2026.0）轉到機體軸＋白雜訊 | 2／2／3 µT | PX4 `sensor_mag_sim` |
| 氣壓 | 核心的 ISA 靜壓＋白雜訊 | 2.7 Pa | MS5611 OSR 1024（PX4 driver 設定） |
| 差壓 | ±½ρu²（u 為相對空氣的機體 x 速度，同 PX4 `sensor_airspeed_sim`） | 0 | 使用者決定（PX4 `sensor_airspeed_sim` 為 0.01 hPa = 1 Pa） |
| GPS | 每 25 步（10 Hz）一筆，其間保持；位置、NED 速度＋白雜訊 | 水平 0.2 m、垂直 0.5 m；速度 0.06／0.077／0.158 m/s | PX4 `sensor_gps_sim` |
| 震動（選項，預設關） | throttle > 0 時加在 accel、gyro | 0.5／1.7／1.4 m/s²；0.14／0.07／0.03 rad/s | PX4 SIH（Bulka & Nahon 2018） |

IMU 的 noise density 換算成每筆標準差：σ = density·√(1/(2·dt))。沒有 bias、比例誤差與延遲。亂數是每架各自的 PCG32，種子由 `sks_sensors_init()` 給；同種子同輸入必得同輸出。`noise_enabled = 0` 只供測試：PX4 會把完全不變的感測器判為卡住。

驗收（`<cache>/results/plant_validation.json`，13 項）：
- 自我檢查：比對工具遇到 NaN／Inf 一律判 FAIL。
- 版面：5 個公開 struct 的大小與 77 個欄位位置，C 與 ctypes 一致。
- Truth：14 個參考 case 中與舊 Truth 同義的欄位（位置、經緯度、高度、NED 速度、高度變化率、四元數、roll／pitch、yaw（包角換算）、角速度、角加速度、比力、α、β、Mach）一致，容差 1e-9。
- 一致性：重力、比力兩種算法一致；不支援的輸入會被拒絕。
- 多架與狀態：兩架交錯、狀態複製都逐位元相同。
- 經緯度：與 MATLAB `flat2lla` 的 88 個點一致（1e-9°）；正好在極點且東向位移 > 1 m 的 10 個點只檢查範圍。
- WMM：與 MATLAB `wrldmagm` 的 660 個值一致（< 1e-3 nT）。
- 感測器：無雜訊時每個輸出欄位都等於理想值（含差壓、溫度、GPS 地速／航跡角／取樣時間、更新旗標）；GPS 每 25 步更新並在其間保持；有雜訊時，各通道標準差與設定差 5% 以內（GPS 8%）；震動選項；同種子重現、不同種子不同、狀態複製後續跑相同。
- 邊界：GPS 在 ±180° 經度與兩極附近加雜訊後仍在合法範圍；航跡角不會等於 2π（360°）。

## plant 介面重點

- **輸入**：`SksActuatorCommand` 五個正規化命令（左副翼、右副翼、elevator、rudder、throttle），意義等於 PX4 `HIL_ACTUATOR_CONTROLS` 經 `HIL_ACT_FUNC` 對應後的通道，也就是現行 ABI 的 `controls[0..4]`。每單位幾度、正負號在核心的 ACTUATOR 子系統。
- **Truth**：plant 每一步都填滿所有欄位（位置、速度、姿態、角速度、加速度、空速、α、β、大氣、舵角、力與力矩分解、接地旗標）。SITL 各 tier 要發布哪些欄位給 PX4，在 plant 外面決定，plant 不因專案而改。經緯度由 C Truth 以 WGS84 平地近似（與來源的 `Flat Earth to LLA` 相同）計算。
- **狀態**：`SksPlant` 不透明，用 `sks_plant_copy()` 複製，用於 trim、與參考逐層比對、RL 重設。
- **輸出時間點**：`sks_plant_step()` 回報積分前的 t_k，與現行 HIL ABI 相同。
- **sensors 分開**：IMU、氣壓、磁力計、空速、GPS 由 `SksSensors` 讀 Truth 產生，見上一節。

## 參考資料

`reference/record_reference.py` 載入 active release 的 `libskysurfer.dylib`，以固定初值與控制序列逐步執行，存下每一步的 58 個 raw 欄位（ActuatorSnapshot、TruthSnapshot、Sensors，欄位定義見 [MODEL_INTERFACE 第 6 節](../docs/MODEL_INTERFACE.md#6-raw_source58-欄位表)）。它只呼叫 model ABI，不開 serial、不連 PX4、不需要 MATLAB。

```bash
"$HOME/Library/Application Support/SkySurferHIL/venv/bin/python" plant/reference/record_reference.py
```

`manifest.json` 記錄 model build-id、library SHA-256、腳本 SHA-256、每個 case 的初值與控制、樣本數與是否被發散 guard 截斷。C Truth 與 sensors 以這份資料對照；active release 改變後，舊參考資料只能當參考，要重錄。

感測器欄位（raw 39–57）來自 C sensors（固定預設種子），只當比較對象；感測器的驗收在 `validate_plant.py`，adapter 的欄位對應與時序在 `hil_runtime/tests/validate_library.py`。
