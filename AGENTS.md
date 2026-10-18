# px4-llm-sim2hitl：給 AI 的工作規則

專案是什麼、流程、環境準備與指令見 [README](README.md)。本檔只寫 AI 怎麼工作。

## 1. 和使用者合作

- **講白話**。技術細節由 AI 自己查、自己處理；只有需要使用者做決定時才說，一次一件。講太細就失去這套專案的意義。
- 照 README 的流程分段走。**每段結束時問「下一步 1／2／3」**，段內不逐項詢問權限。
- 遇到 runtime 的安全檢查擋下、原因不明的 FAIL、或需要人手（重插 USB、斷電、拆槳）時，停下來說明，不自行繞過或重試。

### 第 1 段「需求與規格」：最重要，先和人把整個工作流程談完

AI 先查好現況、提出建議，只跟人確認**目標、選擇與成功條件**：

1. **先聽**：想做什麼、要飛什麼情境、怎樣算成功。
2. **1.1 飛機模型與配平**：是哪一架飛機、和 SkySurfer 差在哪裡（外型、重量、重心、慣量、氣動、舵面配置）。舵面配置不同時（例如飛翼、V 尾），現在固定的五路輸入（左副翼、右副翼、升降舵、方向舵、油門）要跟著改。改完：重新產碼、四道檢查、配平與放手測試（`sitl/trim.py`）。刻意改了模型後，「對錄製參考資料的比對」本來就會不同（它只報告、不擋）；確認同次 Simulink 對照通過後，再重錄參考資料。
3. **1.2 算法、部署與驗收**：
   - **先讀鎖定版本的 PX4 原始碼，再和使用者討論接法**：依使用者要開發的東西，整理 PX4 現在的控制鏈（固定翼大致是：導引／模式管理 → 高度與速度 → 姿態 → 角速度 → 控制分配）、模式與相關模組，找出這次可行的方案；每個方案用白話說明要不要改 PX4 原始碼、能不能切回原生、失效保護誰負責、Flash 空間、SITL 要模擬哪些部分。可能的例子：OFFBOARD（交出去幾層由旗標決定，模組也能在韌體內自己發 OFFBOARD 訊號，不一定要外接任務電腦）、用專案的 patch 機制修改或拿掉原生模組、PX4 的外部模式。**這些只是例子，不是只有這幾種**；方案由使用者選，AI 依原始碼查證可行後才開始。`modules/src/guidance_template` 是其中一種接法的範例，只用來讓人有概念；
   - 預想 SITL 與 HITL 會碰到的問題：SITL 用真值、不經 EKF；HITL 編進客製韌體、用 FC 上 EKF 的估測；和現有飛行模式怎麼共存；Flash 空間（原生韌體已用約 98 %）；
   - 談好：用哪塊飛控、HITL 是否已設好；新算法何時接手、怎麼退出、失效時怎麼回到原生；用什麼動作證明它真的有作用；
   - **「怎麼部署」是第 3 段一條龍的前提**；
   - 寫成模組 README 的一頁規格：目標、接法、SITL 與 HITL 各自的驗收指標。兩邊估測來源不同，比的是表現與差距，不要求逐點相同。

不替使用者預先決定客製方式；把要想的問題提出來，依 PX4 原始碼給建議。

**建議先做「最小打通」**：開發位置確定後（例如只做導引），先不寫正式算法，而是架好開發框架，用一個極簡的版本（例如把 PX4 原本的導引換成一個很簡單的測試）走完 SITL → 編韌體 → 燒錄 → HITL 一次，並記錄下來。之後每次修改都交給自動化（第 2 段的指令與第 3 段的 `deploy-test`），不必每次重新摸索接法，可以省下很多 token。把這個建議告訴使用者，由使用者決定要不要做。

**建議人隨著開發慢慢建立自己的自動化**：同一件事手動做了兩三次（例如一段飛行動作、一種判定、一串檢查），就建議把它變成專案裡的指令或腳本，放在現有的位置（起飛後動作放 `hitl/commands/`、判定放 `analysis/`、配方的 `hitl.json` 指定要跑哪些），之後一個指令跑完、AI 只讀結果。越用越省 token，也越不容易出錯。只在真的重複時才建議，不預先做；由人決定要不要做。

**建議人把這包本地化**：這包是給大家用的通用套件。拿它開始自己的專案時（例如 fork 一份），建議人把它改成自己的：自己的飛機（模型、`hitl/aircraft/<飛機>/`、名稱）、自己機器的路徑與設定（環境變數 `SIM2HITL_*` 或設定檔）、自己的飛控與配方、自己的驗收標準與自動化腳本，並寫進專案文件。之後的 AI 讀文件就知道，不必每次重新查，省 token。由人決定要不要做、做到哪裡。

**建議使用者用 ULog 看結果**：SITL、HITL、實機都產生 ULog，AI 用 Python 自動判定，人用 MATLAB 畫圖檢查；好處與工具見 [analysis README](analysis/README.md) 的「ULog 工具包」，向使用者說明後由他決定。

**PX4 v1.17.0 的記憶卡讀取問題（要告訴使用者）**：在 Pixhawk 6C（STM32H7）上，v1.17.0 用的 NuttX 在 SD 卡 DMA 讀取完成後沒有清除快取，曾讓自建韌體下載的飛控記錄出現 32 bytes 一段的錯誤（MAVLink 檢查碼正確，看起來像好的）。NuttX 官方修正 82d1285 不在 v1.17.0 裡，專案保存在 `px4/patches/`。自建韌體的配方都要套它（`deploy/01_sdfix` 是範例）；`hitl-run` 會把同一份記錄下載兩次比對、再做嚴格解析，用來抓這類錯誤。原生 `00_native` 至今沒有出現過，但沒有證明不受影響。升級 PX4 版本時，先查新版是否已經包含這個修正。

## 2. 接手時先查平台

- 只在 Ubuntu 24.04 x86-64 驗證過。換平台時，照 README「環境準備」逐項查官方文件，確認做法再裝。
- 路徑與工具不寫死：MATLAB、編譯器、暫存位置見 `plant/core/toolchain.py`（可用環境變數指定），PX4 原始碼樹見 `px4/check_px4_tree.py`。
- 檢查：`./runbridge --check-python`、`python3 px4/check_px4_tree.py`、`./runbridge preflight`。
- **第一次在這台機器用 AI：把權限一次設好，之後人只要口頭同意**（不要每次刷機都請人做技術步驟）：
  - 即時排程權限：照 README「環境準備」的長期設定，重開機（或完全登出）一次才生效。生效前只能臨時給：請人執行 `sudo prlimit --pid <AI 程序的 PID> --rtprio=10:10`，再用 `ulimit -r` 確認。
  - AI 工具的允許清單：碰飛控的 `runbridge takeoff`（解鎖起飛）與 `runbridge deploy-test`（刷機、參數、開機檔、HITL）會被 AI 工具的自動權限檢查擋下；AI 不能自己改權限設定（也會被擋），請人加一次。Claude Code 是在 `~/.claude/settings.json` 的 `permissions.allow` 加 `Bash(<專案絕對路徑>/runbridge takeoff *)` 與 `Bash(<專案絕對路徑>/runbridge deploy-test *)`；AI 執行時也用同樣的絕對路徑開頭，不包在 `cd … &&` 或 `timeout` 裡，規則才對得上。
  - 設好之後，人說「刷」「飛」就好；AI 每次寫入 FC 前仍先說一聲，第 3 節的安全檢查照舊。

## 3. 安全底線（不可繞過）

- **寫入對象與內容要確定**：寫參數、開機檔、燒錄前確認 FC 身分、未解鎖；寫入後讀回。不確定是否成功就停，不繼續到解鎖。
- **恢復與單一 owner 不能繞過**：不刪恢復記號（`recovery.json`）、寫參數交易記號（`param_deploy.json`）、`owner.lock`、`host.json`；不用重開程式或換資料夾繞過未完成的恢復。runtime 的狀態資料夾跟著程式所在的路徑，換資料夾或換電腦前，先在原處恢復並關閉 owner。
- **只做隔離實體動力的 HITL**：HITL 時螺旋槳已拆或電調不供電，第一次使用前請人確認。3.2 出場檢查完成前，自動流程不關 HITL（`SYS_HITL`）、不測實體致動器。
- 不用 `rm -rf` 大量刪除。
- 遠端操作時，現場沒人能重插 USB 或斷電：刷機或恢復卡在需要人手時就停下來等。

## 4. 不變量

- **唯一 plant 來源**：`model/` 的 `.slx`＋初始化＋氣動 MAT／importer＋preload。轉出的 C（`model/generated/`）是建置產物，不手改；改模型後重新產碼。
- **單一 owner**：同時只有一個程序持有模型與序列埠；其他指令經本機 IPC 和它溝通。
- **通道**：`controls[0..4]` = 左副翼／右副翼／升降舵／方向舵／油門。
- **4 ms 迴圈不呼叫 Python 或 LLM**；runtime 是最終安全判斷者，不要為了讓操作成功而放寬它的前置條件。
- **停模型 ≠ PX4 已恢復**：送過感測器資料後，待恢復狀態會持久化，要 `recover` 完成才算恢復。
- 實體 HITL 不准在空中起始。
- 發布模型 release 只是離線證據，不會自動開始 HIL、解鎖、切模式或重開 FC。

## 5. 改了什麼，要跑什麼

| 改了 | 要跑 |
|---|---|
| 飛機模型（`model/`） | `./runbridge update-model --generate`（MATLAB）→ `./runbridge update-model` → 配平；刻意改了模型就照第 1.1 段重錄參考資料 |
| `plant/` 的 C、`hitl/` 的 `native/`、`interface/`、`aircraft/`、`update.py` | `./runbridge update-model`（四道檢查）→ 離線測試 |
| `hitl/host/` 等 runtime 程式 | 離線測試；影響時序時加跑 600 s 負載 |
| `sitl/`、`modules/` | `sitl/build_sitl.py` → `sitl/run_sitl.py` → `analysis/response.py` |
| 韌體、參數、開機檔（`deploy/<配方>/`、`modules/`、`px4/patches/`） | 第 3 段：`./runbridge deploy-test --release deploy/<配方>` 先看計畫（只讀），再由人選 `--flash`（必要時先編韌體、燒錄）或 `--reuse`（沿用 FC 上的韌體）；只編韌體：`./runbridge build-firmware --release deploy/<配方>` |

離線測試與負載（`PY` = venv 的 python，例如 `~/.local/share/px4-llm-sim2hitl/venv/bin/python`）：

```sh
for f in hitl/tests/test_*.py deploy/test_*.py; do echo "== $f"; "$PY" -B "$f" 2>&1 | tail -1; done
"$PY" -B hitl/tests/run_load.py <新的空資料夾> --duration 600
```

## 6. 在哪裡

| 資料夾 | 內容 |
|---|---|
| `model/` | 飛機模型來源；`generated/` 是轉好的 C 與 Simulink 參考結果 |
| `plant/` | plant 核心包裝、C 真值、C 感測器、各自的檢查程式、錄製的參考資料 |
| `sitl/` | 精簡 PX4 的 plant 模組 `plant_sim`、情境、配平、ULog 重播 |
| `modules/` | 自己的 PX4 模組（同一份原始碼編進 SITL 與韌體；`guidance_template` 是範例，見它的 README「照著做一個自己的模組」）。韌體只編配方 `recipe.modules` 列的模組；SITL 要在 `sitl/px4_external/src/` 加包裝並列進那裡的 `CMakeLists.txt` |
| `hitl/` | runtime（owner、worker、`hitl-run`）、起飛與起飛後動作腳本、`flight_test.json`（預設飛行與判定）、模型 release |
| `deploy/` | 部署配方：`00_native`（原生韌體＋參數，可隨時刷回）、`01_sdfix`（原生＋記憶卡修正 patch，交接時 FC 上是它）、`02_template`（01＋範例模組 `guidance_template`＋開機檔＋`hitl.json` 指定的起飛後動作與判定）；自建配方的 `firmware/firmware.json` 的 `recipe` 寫要套的 patch 與 `modules/` 的模組，`px4/build_firmware.py` 在 PX4 原始碼樹旁的建置樹編譯（原樹不動），patch 以固定作者與日期 commit，FC 回報的 NuttX hash 因此可預期、可核對 |
| `px4/` | PX4 版本鎖、原始碼樹核對、修正 patch |
| `analysis/` | 響應指標、ULog 讀檔與嚴格解析、重播比對 |
