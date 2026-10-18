# aircraft/avl：SkySurfer 氣動表的來源幾何

`model/m_05.mat`、`model/m_1.mat`（Mach 0.05、0.10 的 AVL 氣動表，`model/import_aerostates_avl.m` 讀取）由這裡的幾何算出。重心、力矩參考點、中性點與 MAC 的意思和換算見 [plant README「重心與氣動作用點」](../../plant/README.md)。這個資料夾不在 `model/` 裡，改這裡不影響模型版本；`model/` 底下任何檔案變動都要重新產碼。

| 檔案 | 內容 |
|---|---|
| `SkySurfer_wing2410_NDU.avl` | 產生現用氣動表的幾何：原作者幾何（SHA-256 `54a6eb4f…`）＋兩個相容性修改（左翼剖面改成 y 遞增；垂直尾翼翼尖弦長 0 → 1e-4 m）＋使用者 2026-10-15 量測的升降舵（鉸鏈舵，弦長 0.035 m，每側 y = 0–0.165 m）與方向舵（弦長 0.025 m）。副翼沿用原作者幾何（約 30 % 弦長，沒有量測） |
| `sky_mass_20251130.mass` | 原作者的質量檔：1.3 kg、重心 AVL x = 0.05 m、慣量 0.023／0.029／0.05 kg·m²（模型用的是 Ixx × 2、Iyy × 3） |
| `build_avl_mat.m` | 把 AVL 的計算結果（AVL MCP 的 `result.json`）轉成 importer 讀的 MAT（每個 α 一個 93×6 cell：第 1 欄標籤，第 2–6 欄為 β −10、−5、0、5、10） |

`.avl` 檔頭寫的 `Xref` 是 0；算表時另外指定 0.05（等於質量檔的重心）。直接用 AVL 重算時，記得把 `Xref` 設成 0.05，否則力矩參考點和模型的 `XREF_m` 對不上。

## 重新產生氣動表（換飛機或改幾何時）

1. 用 AVL（驗證時是 3.52，經 [AVL MCP](https://github.com/rhyne1012/avl-mcp)）對 `.avl` 跑 60 個工況：Mach 0.05、0.10 × α −10、−5、0、5、10、15 × β −10、−5、0、5、10；角速度與舵面為 0；參考值 Sref 0.238、Cref 0.2、Bref 1.41、`Xref` = 質量檔的重心、Yref 0、Zref 0；輸出 total、stability、body。
2. MATLAB（在專案根目錄）：

```matlab
addpath('aircraft/avl');
build_avl_mat('<job>/result.json', 'model/m_05.mat', 'model/m_05.mat', 'm05');
build_avl_mat('<job>/result.json', 'model/m_1.mat',  'model/m_1.mat',  'm1');
```

   第二個參數是讀列標籤用的模板（現用 MAT 即可）。舵面依名稱對應：d01 aileronR、d02 aileronL、d03 elevator、d04 rudder（和 Simulink 接線相同），不依 AVL 的宣告順序。
3. `model/FW_SkySurfer_InitialFunction.m` 的 `XREF_m` 要對應算表用的 `Xref`（換算見 plant README），`cbar`、`b`、`S` 照參考值；然後照 AGENTS 第 5 段「飛機模型」那一列。

## 重現檢查（2026-10-15）

用原作者幾何（只做那兩個相容性修改）以同樣設定重算，和原本的 MAT 比：最大絕對差 6e-5（原 MAT 只有 5–6 位有效數字）。這只證明近似重現，不證明原 MAT 的確切產生過程；重算結果差很多時，不要直接替換 MAT。

## 另一份：VSP 氣動表（備用，現在沒用）

模型裡還有一份 OpenVSP（VSPAERO）算的氣動表 `model/Skysurfer.mat`，由 `model/import_aerostates_vsp.m` 讀；`model/FW_SkySurfer_InitialFunction.m` 的 `useAVL_VSP` 設成 1 才會用。現在是 0（用 AVL），這包所有的檢查、SITL、HITL 都是 AVL。VSP 那份：

- 沒有幾何檔，也沒記當初的參考值（翼面積、參考弦長、力矩參考點），不能重算，也不能確認力矩參考點和 AVL 相同；
- 不知道有沒有用 2026-10-15 量測的升降舵、方向舵尺寸（那次只修了 AVL）；
- 數字和 AVL 接近：中性點都在參考點後面約 0.41 個參考弦長；升力斜率 5.24／rad，比 AVL 的 4.62 多約 13 %；範圍 α −10～15°、β −10、0、10°；另加的阻力修正 `CD_fix_VSP` 0.065（AVL 是 `CD_fix_AVL` 0.075）。

找到 VSP 幾何時放進 `aircraft/vsp/`，可以和 AVL 互相比對。要拿掉這份屬於模型改動（`model/` 有變動就要重新產碼）。
