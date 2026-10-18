# SkySurfer

固定翼 SkySurfer 的飛控開發套件：MATLAB/Simulink 飛機模型 → 轉成 C → SITL（精簡 PX4）→ 客製 PX4 韌體 → 實體飛控 HITL。用 AI 開發時，AI 的工作規則在 [AGENTS.md](AGENTS.md)。

> 狀態：從舊專案 `FW_SkySurfer` 搬家中（見最後一節）。

## 流程

1. **需求與規格**：先談清楚要做什麼、怎樣算成功。
   - 1.1 飛機模型與配平（換飛機或改模型時）
   - 1.2 算法、部署與驗收
2. **SITL（電腦模擬）**：反覆模擬，結果存成 `trace.csv`＋ULog（MATLAB 可直接讀）。
3. **HITL（自動編譯、燒錄、測試）**
   - 3.1 手動 HITL（`./runbridge`＋QGC）
   - 3.2 出場檢查：QGC 關掉 HITL 後確認舵面有輸出（尚未完成）

## 環境準備（第一次）

只在 **Ubuntu 24.04 x86-64** 驗證過。下面每一項都寫了「為什麼要」與「這台 Ubuntu 的做法」；做法只是例子，換平台或版本時，**請 AI 先查該項的官方文件**確認正確做法再裝。

| 項目 | 為什麼要 | Ubuntu 24.04 的做法（例子） | 怎麼確認 |
|---|---|---|---|
| Python 環境 | runtime、測試、SITL、分析 | 安裝 [uv](https://docs.astral.sh/uv/)，再 `./runbridge --setup`（venv 在 `~/.local/share/SkySurfer/venv`） | `./runbridge --check-python` |
| MATLAB | 只有改飛機模型（第 1.1 段產碼）才需要：R2026b＋Simulink＋Simulink Coder＋Embedded Coder＋Aerospace Blockset。不需要 Java | MathWorks 安裝程式；建議接上 MATLAB MCP，讓 AI 能直接操作 | `matlab` 在 PATH，或設 `SKYSURFER_MATLAB_ROOT` |
| C 編譯器 | plant 與 HIL 函式庫 | 系統內建 gcc（`CC` 可指定別的） | `cc --version` |
| PX4 原始碼與工具鏈 | SITL 與編韌體；版本鎖在 [px4/px4_lock.json](px4/px4_lock.json) | 下載鎖定的 tag 到專案外，`python3 px4/check_px4_tree.py --path <樹> --remember`；工具鏈用 PX4 官方腳本 `bash <樹>/Tools/setup/ubuntu.sh --no-sim-tools`（不裝 Gazebo；會用 sudo）。官方說明：PX4 文件 “Ubuntu Development Environment” | `python3 px4/check_px4_tree.py` 為 PASS |
| **即時排程權限** | 4 ms 迴圈的 worker 執行緒要用即時排程（Linux：SCHED_FIFO，優先權 2）。沒有權限也能跑，但時間餘裕變小：這台 600 s 負載最慢晚到 3.7 ms（門檻 4 ms），有權限時 0.47 ms | 桌面程式由 systemd 使用者服務啟動，`/etc/security/limits.d` 管不到；改用 systemd，兩個檔都要：`/etc/systemd/system/user@<UID>.service.d/rtprio.conf` 寫入 `[Service]` 與 `LimitRTPRIO=10`（使用者管理程式本身的上限），以及 `/etc/systemd/user.conf.d/rtprio.conf` 寫入 `[Manager]` 與 `DefaultLimitRTPRIO=10`（它啟動桌面程式時套用的值；只設第一個，實測重開機後桌面程式仍是 0），`sudo systemctl daemon-reload`，再重新登入。暫時只給一個程序：`sudo prlimit --pid <PID> --rtprio=10:10`。官方說明：systemd.exec(5) 的 `LimitRTPRIO=`、sched(7) | `ulimit -r` ≥ 2；`./runbridge status` 的 `scheduler.time_constraint_result` 為 0 |
| 序列埠 | 連 Pixhawk（USB CDC-ACM） | 使用者加入 `dialout` 群組；停用 ModemManager（它會試探新插上的序列埠）：`sudo systemctl disable --now ModemManager` | `ls -l /dev/ttyACM*`、`groups` |
| QGC | 人看飛控、手動操作（3.1） | 官方 GitHub 發布的 AppImage（這台：v5.1.5，`~/Applications/`，核對官方公布的 SHA-256）；系統套件照 QGC 官方 Linux 說明（這台補裝 `libfuse2t64 gstreamer1.0-plugins-bad gstreamer1.0-libav libxcb-cursor0`）。**關掉 USB 自動連線**，只用 UDP 14550 連 runtime，否則會和 owner 搶飛控序列埠：設定檔 `~/.config/QGroundControl/QGroundControl.ini` 的 `[AutoConnect]` 把 `autoConnectPixhawk`、`autoConnectSiKRadio`、`autoConnectRTKGPS`、`autoConnectLibrePilot`、`autoConnectZeroConf` 設 `false`、`autoConnectUDP=true`（QGC 第一次啟動建好設定檔、關閉後再改；或在 QGC 的 Application Settings → Comm Links 取消勾選） | QGC 開著時 `lsof -p <QGC PID>` 只見 UDP 14550、不見 `/dev/ttyACM*` |

## 常用指令

```sh
./runbridge --help                    # 所有動作
./runbridge update-model --generate   # 第一段：MATLAB 產碼 → model/generated（要 MATLAB）
./runbridge update-model              # 第二段：編譯、四道檢查、發布模型 release（不需要 MATLAB 連線）
./runbridge bridge                    # 開 owner（持有模型與序列埠）；QGC 用 UDP 連
./runbridge status                    # owner 狀態
./runbridge deploy-test --release deploy/<配方>           # 第 3 段：只看計畫（FC 上現在是什麼、會做什麼）
./runbridge deploy-test --release deploy/<配方> --flash   # 必要時編韌體 → 燒錄 → 參數 → 開機檔 → hitl-run
./runbridge deploy-test --release deploy/<配方> --reuse   # FC 已經是這個配方的韌體：參數 → 開機檔 → hitl-run
```

## 搬家狀態（2026-10-18，Ubuntu 24.04）

| 項目 | 結果 |
|---|---|
| 模型 release `skysurfer-f53eee94…` | 四道檢查 PASS；對 macOS 錄的參考資料，除了靜止時沒有定義的攻角／側滑角，差 ≤ 6.2e-15 |
| 離線測試 | 15 個檔、186 項 OK（2026-10-18，範本加入後） |
| 600 s 負載（不開視窗） | PASS；有即時權限時最慢晚到 0.47 ms |
| SITL | 編譯 PASS；參考情境 `stabilized_steps` 的指標和 macOS 紀錄相同；速度：1000 次（每次模擬 60 s）實測 140.8 s，加大批次約 55 s；範本 `sks_template` PASS |
| ULog 與 MATLAB | SITL 與 HITL 的 ULog 都能用 MATLAB `ulogreader` 畫（`analysis/matlab/sks_ulog_plot.m`，不需要 Java），也能轉 CSV（`analysis/ulog_export.py`） |
| HITL（實體 FC） | 00_native 基準 `hitl-run` PASS（2026-10-17 UTC）：盤旋 60 s、2.78 圈；23,039 步 0 次晚到、最慢 0.79 ms；USB 寫入最慢 0.26 ms；FC 量到感測器 250.009 Hz |
| 第 3 段一條龍 | `deploy/01_sdfix`（原生＋記憶卡修正）用 `deploy-test` 燒錄並跑完：FC 回報 NuttX `8d3ed2a2…`（可預期的那個）；寫參數 0 個；`hitl-run` 七部分全 PASS，盤旋 60.13 s、2.78 圈，23,104 步 0 次晚到、最慢 0.19 ms；飛控記錄（10.9 MB）下載兩次相同、嚴格解析 PASS |
| 乾淨目錄試跑 | 從 git 拉到新資料夾、不連 MATLAB、不靠舊 cache：`update-model` 建出**相同的 build-id**、四道檢查 PASS、配平相同 |
| 收尾 | 把討論定案的計畫（`~/Documents/Codex/2026-10-18/skysurfer_architecture_v3/PLAN.md`）的核心精神放進專案；整套跑通後再做一次乾淨目錄試跑；上 GitHub |
