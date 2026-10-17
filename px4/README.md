# PX4 版本鎖定與原始碼樹位置

本資料夾記錄專案使用的 PX4 版本，以及找到本機 PX4 原始碼樹的方法。**PX4 原始碼樹本身不放在專案裡**：它約 1.8 GB、4.7 萬個檔案，放進 Dropbox 會拖慢同步，git 也容易因衝突副本損壞。

| 檔案 | 內容 |
|---|---|
| [px4_lock.json](px4_lock.json) | 版本權威：repository、tag、commit、HITL 韌體版本、本機路徑設定位置 |
| [check_px4_tree.py](check_px4_tree.py) | 核對本機原始碼樹是否等於 lock（commit、乾淨、submodule） |

目前鎖定 **v1.17.0**（commit `d6f12ad1c4f70ad3230afd7d86e971421e02fef4`），與 HITL 飛控（Pixhawk 6C，`px4_fmu-v6c`）上的韌體同版本。SITL、客製韌體與 HITL 必須使用同一個鎖定版本；要換版本時照 [PX4 版本更新 runbook](../docs/runbooks/px4_upgrade.md) 走，不要只改其中一處。

## 本機原始碼樹在哪裡

位置因機器而異，依序從這三處取得：

1. 指令參數 `--path`
2. 環境變數 `SKYSURFER_PX4_ROOT`
3. 本機設定檔：macOS `~/Library/Application Support/SkySurferHIL/px4_root`，Windows `%LOCALAPPDATA%\SkySurferHIL\px4_root`（只有一行路徑，不隨 Dropbox 同步）

```bash
python3 px4/check_px4_tree.py
```

| 結果 | 意思 | LLM 該做什麼 |
|---|---|---|
| `PASS`（exit 0） | 原始碼樹等於 lock | 可以使用 |
| `FAIL`（exit 1） | commit 不同、有未提交修改或 submodule 不符 | 停下回報，不要自行 checkout、reset 或清理 |
| `UNKNOWN_LOCATION`（exit 2） | 這台機器還沒設定位置，或路徑不存在（外接碟未掛載） | **問使用者 PX4 原始碼樹在哪裡**；取得路徑後執行下一個指令 |

```bash
python3 px4/check_px4_tree.py --path <使用者給的路徑> --remember
```

`--remember` 只在核對 PASS 後寫入本機設定檔。

## 規則

- 換到新電腦時，先問使用者 PX4 原始碼樹放在哪裡。不要猜路徑，不要自行 clone 或下載；使用者要求下載時，下載到使用者指定的 Dropbox 外位置，並用上面的指令核對。
- 不直接修改 PX4 原始碼樹。客製程式以 out-of-tree 模組（PX4 的 `EXTERNAL_MODULES_LOCATION`）放在專案裡；必須改 PX4 原有檔案時，以 patch 檔保存在專案，套用前後都要能用 `check_px4_tree.py` 說明原始碼樹狀態。
- 原始碼樹裡的 `build/` 是 git 忽略的產物，不影響核對結果。它的來源身分另外看執行檔內嵌的版本：`strings build/px4_sitl_default/bin/px4` 要有 lock 的 commit 與 `v1.17.0`，且沒有 `-dirty`；對不上才重編（C 級）。
