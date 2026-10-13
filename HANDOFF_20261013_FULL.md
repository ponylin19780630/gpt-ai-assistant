# 股票 LINE Bot 交接清冊（2026-10-13 08:51～17:14 台北）

> **適用對象**：接手 `stock-bot`（Cloud Run）中「三大法人」「排行榜」模組，以及 VIP1688 後續工作的人。
> **依據**：本對話中使用者回貼的 Cloud Shell 輸出與 Cloud Run 日誌、上傳的檔案與截圖、repo 分支 `claude/intelligent-wright-hbx2kb` 的原始碼與 commit。
> **原則**：只寫有證據的內容。推論或沒有驗證過的事項，一律標註「**未驗證**」。本檔不含任何密鑰值，也不含完整的 LINE ID。
> **時間**：日誌裡的時間是 UTC，本檔其他地方的時間都是台北時間（UTC+8）。

---

## 0. 一頁總結（接手者先讀這裡）

| 項目 | 現況（已實測證實） |
|---|---|
| 正式版 | Cloud Run `stock-bot` → **`stock-bot-r3h`** 100%（10/13 17:04 切換；使用者回貼的輸出確認；LINE 前台 PASS） |
| r3h 檔案 SHA | `app.py` = `c486dd1db5dd4baa…`；`insti_query_r1.py` = `275f0127264550ca…` |
| 回滾鏈（由新到舊） | `stock-bot-r3f` → `stock-bot-rk-r3b` → `stock-bot-insti-r3e` → `stock-bot-01296-xid`（tag `fix8-r1`，今天開工時的正式版） |
| 本日新增功能 | 三大法人同買／同賣卡片、排行榜個股卡都加上：**外本比、投本比（當日｜近 5 日累計｜趨勢）**，以及**權值股★（上市市值前 50）** |
| 上市＋上櫃 | 發行股數 1,988 檔（上市 1,095＋上櫃 893）全部可以計算；ETF 沒有官方發行股數，會標灰色「資料不足」並寫明原因 |
| 使用者決定 | 16:39：**放棄上櫃前 10 的★**（TPEx 收盤價 API 持續逾時） |
| 未完成或需注意 | 第 6 節共 12 項。最需要注意的是：**TPEx `tpex_mainboard_daily_close_quotes` 仍不穩定**（其他模組 TW_R4 已啟動熔斷）、**三大法人卡片接近大小上限**、VIP1688 舊待辦（金鑰輪換、FinMind 額度）**本日沒有處理** |
| 成本 | 第 7 節：沒有讀過帳單；依日誌推估，增加的運算很少。實際的成本是**今天部署 8 次**產生的建置費與映像檔儲存 |
| repo | 分支 `claude/intelligent-wright-hbx2kb`，本日 14 個 commit（`468508e` → `8841206`） |

**回滾指令**（可直接執行）：
```bash
# 回到上一版 r3f（上市前50＋上櫃前10 的★版，會有 TPEx 重試延遲）
gcloud run services update-traffic stock-bot --to-revisions stock-bot-r3f=100 --region asia-east1 --project affable-gist-379402
# 回到今天開工時的正式版（沒有本日任何新增功能）
gcloud run services update-traffic stock-bot --to-revisions stock-bot-01296-xid=100 --region asia-east1 --project affable-gist-379402
```

---

## 1. 環境與鐵律

### 1.1 環境（已證實）
- GCP 專案 `affable-gist-379402`，區域 `asia-east1`，Cloud Run 服務 `stock-bot`。
- 操作全部在使用者的 Cloud Shell 進行（HOME `/home/chloe828525`，空間 4.8G，使用率 95%，剩約 276M）。
- Claude 的沙箱**連不到** TWSE／TPEx（代理伺服器回 403，10/13 實測）。所有真實資料都由使用者在 Cloud Shell 執行指令後回貼。
- repo：`ponylin19780630/gpt-ai-assistant`。`main` 是 2023 年的 ChatGPT bot，和股票系統無關；股票系統的補丁與日誌都在分支 `claude/intelligent-wright-hbx2kb`。
- **正式版的原始碼不在 repo 裡**。要取得時，從 revision 的 annotation `run.googleapis.com/build-source-location` 讀出 GCS 上的 zip。這個值是 JSON 格式：`{"stock-bot-1":"gs://run-sources-…/….zip#…"}`，必須用正則抽出 `gs://` 開頭的網址，並且用 **zip** 解壓，不是 tar.gz。
- 觸發測試的端點：`POST /internal/run_task`，標頭 `X-Internal-Task-Secret`（值為 INTERNAL_TASK_SECRET，沒設定時用 CRON_SECRET）。body 為 `{user_id, prompt:"", mode}`：
  - 三大法人：`mode="INSTI_SYNC_R1"`（app.py 第 11721 行 → `insti_query_r1.send_report`），同步執行約 1～60 秒。
  - 排行榜：`mode="RANKING_PICK"`，加上 `flex_title:"🏆 排行榜精選"`。**同步執行超過 40 秒**，所以 curl 要放到背景，或把逾時設為 400 秒以上。
- 推送對象：只推送給 Secret Manager 裡的 `ADMIN_LINE_ID`，用 regex `^Ubccb[0-9a-f]{28}$` 把關，密鑰不印出。

### 1.2 使用者鐵律（已存入記憶 `/preferences.md`）
1. 所有上市、上櫃股票都要可查詢；缺資料要寫明原因，不能悄悄消失。
2. 先讀真實數據，核對來源、日期、單位後才推理；不造假、不幻想、不敷衍。
3. 同一問題兩次除錯失敗，就改做除錯版，把錯誤完整印出。
4. 重點用顏色標記：紅＝漲或偏多、綠＝跌或偏空、黃＝中性、灰＝資料不足；嚴禁重複文字與重複數值；美編排版列為驗收條件。
5. 要回貼的內容用 **[開始]／[結束]** 標記（由指令自動印出）；需要分析的檔案直接給 `cloudshell download`。
6. 部署並驗證通過後，附上自動清理；Cloud Shell 只能「先盤點，再刪已核實的重複或臨時候選」，絕不碰正式程式。
7. 每次修改選把握最高、步驟最少、程式碼最少的做法；回覆一律用繁體中文。
8. 切換正式流量前要使用者同意。本日的作法是：使用者**執行**包含切換的指令，就視為同意；指令裡都附自動回滾。

---

## 2. 時間軸：對話、上傳檔案、圖表

| 台北時間 | 事件 | 證據（檔案或輸出） |
|---|---|---|
| 08:51 | 使用者要求在三大法人模組加上外本比、投本比與趨勢分析 | — |
| 08:55 | 在 repo 分支找到股票系統，讀 `VIP1688_HANDOFF_20261012.md`（記載的正式版是 R13b） | repo |
| 09:26 | 上傳 `insti_src_20261013.txt`（1,101 行）：`insti_query_r1.py` 全文（SHA `28185d59`）＋ app.py 引用處 | 上傳檔 |
| 09:30 | 在沙箱還原 insti_query_r1.py，**SHA 完全吻合**；寫 R3 補丁（commit `468508e`），本機測試通過 | 本機測試 |
| 09:31 | 使用者追加：1688 優化、鐵律 1～8、「yes MR.lin」 | 已寫入記憶 |
| 09:32 | R3 真資料乾跑：`ORIGINAL_UNCHANGED True`，上櫃單位確認是「股」，同買 carousel 30,052 bytes；**發現友達 5 日 −6.110% 看起來異常** | attachment（R3 乾跑） |
| 09:33 | 使用者：「忽略：定位 VIP1688 精華報的實際入口」 | — |
| 09:38 | 友達逐日數字是 −2,628 萬、−5,945 萬、−7,619 萬、−8,705 萬、−21,214 萬股 → **官方資料屬實**。同時發現**探針標籤有錯**（3044 被誤標為最大值）。空間盤點：105 個含 app.py 的目錄 | attachment（A／B 盤點） |
| 09:40 | R3b（`6319cf2`）：極小值改顯示 `±<0.001%`；dupscan（`ab73fb8`） | commit |
| 09:52 | R3b 部署到 tag `insti-r3b`；**發現正式流量其實在 `stock-bot-01296-xid`（fix8-r1），不是 R13b**；dupscan 找到 5 份內容完全相同的目錄（共 18.1M） | attachment |
| 09:57 | fix8 原始碼比對失敗（JSON 格式、zip 檔）；5 份重複目錄已刪除（Home 剩餘從 257M 增加到 276M） | `fix8_check_20261013.txt` |
| 10:15 | R3c：fix8 和 r13b 只差 3 個檔案（`app.py`、`fundamental_entry_r19.py`、`us_analysis_entry_r1.py`），insti 三個檔相同；部署 `insti-r3c` 並推播給管理者 | `insti_r3c_20261013.txt`＋**截圖 2 張** |
| 10:16 | 截圖驗收：**整列依 5 日累計上色，負值也顯示紅色，違反顏色規則** → R3d（`52576b5`）改為逐值上色 | — |
| 10:35 | R3d 部署並推播：同買 carousel 44,995 bytes；前台 PASS；使用者新增需求：權值股★ | `insti_r3d_20261013.txt`＋**截圖 2 張** |
| 10:36 | 使用者選擇★定義：上市前 50＋上櫃前 10 | AskUserQuestion |
| 10:48 | R3e（`66aae38`）部署並推播：★ 上市 50、上櫃 10；carousel 47,197 bytes；前台 PASS | `insti_r3e_20261013.txt` |
| 10:52 | 切換到 `insti-r3e`：正式網址 `PUSH_OK`；刪除 revision insti-r3b、r3c、r3d。使用者新任務：排行榜也要加 | `insti_r3e_switch_20261013.txt` |
| 11:18 | 排行榜原始碼索引：入口在 app.py 第 24045 行，mode RANKING_PICK 在第 12813 行，76 個 rank 相關函式（v27～rk17） | `ranking_src_20261013.txt`（426KB） |
| 11:29 | 第二次擷取**輸出是空的**（擷取程式只掃描最外層函式，沒掃到 try 區塊裡的） | `ranking_card_20261013.txt` |
| 11:56 | 確認 `_v9663_stock_bubble` 最後被重新指定為 `_v967914rk14_bubble`（第 124854 行）；rk17b 在推送前用模組層級的名稱畫卡 | `ranking_card2_20261013.txt` |
| 11:58 | RK_R3（`2c0521c`） | commit |
| 12:19 | 部署 `rk-r3`：乾跑 2330★ 等正確；正式環境 **stars=50（上櫃收盤價失敗）**；`curl` 40 秒逾時（排行榜是同步執行，不是錯誤） | `rk_r3_20261013.txt`＋**截圖 1 張** |
| 12:20 | RK_R3b（`744170a`）：每張卡加「法人MM/DD｜」；★名單不完整時重抓並在總覽卡如實說明 | commit |
| 12:33 | 部署 `rk-r3b`：rk-r3 的失敗原因是 TPEx `ChunkedEncodingError`；rk17b 共 4 則（多方 5＋4、空方 4＋4），沒有丟卡；★ 60 檔 | `rk_r3b_20261013.txt`＋**截圖 2 張** |
| 12:33～16:13 | 使用者執行了切換到 rk-r3b 的指令。**第一次執行的輸出沒有回貼**；16:13 那次回貼顯示「切換前」就已經是 rk-r3b 100% | `rk_switch_20261013.txt` |
| 16:15 | 正式環境日誌：**`shares=1095`（上櫃發行股數失敗）、`stars=50`、`ms=45898`**；找出設計缺陷：發行股數只抓到一部分也會快取一整天 | 同上 |
| 16:18 | R3f（`086da48`）：每個資料源重試 2 次；任一市場失敗就不快取；原因如實顯示 | commit |
| 16:38 | R3f 部署、兩個模組都 `PUSH_OK`、切換上線；**TPEx 收盤價在兩分鐘內失敗 8 次**（Read timed out） | `r3f_20261013.txt` |
| 16:39 | R3g（`ee88a65`，加上 dailyQuotes 備援）已準備好，**還沒執行**時，使用者決定「上櫃前10不做！放棄」 | — |
| 16:41 | R3h（`20456d1`）：★只標上市前 50，完全不呼叫 TPEx 收盤價 API | commit |
| 17:04 | R3h 部署、兩個模組都 `PUSH_OK`、切換上線；乾跑 5.8 秒（r3f 時是 64.7 秒）；前台 PASS | `r3h_20261013.txt` |
| 17:10 | 狀態確認：正式版 r3h 100%；暫存已清；日誌出現 `TW_R4_HTTP tpex_breaker_open`（其他模組） | 回貼內容 |

上傳的截圖共 7 張：R3c 2 張、R3d 2 張、rk-r3 1 張、rk-r3b 2 張（R3e 和 R3h 由使用者口頭確認 PASS，沒有截圖）。

---

## 3. 版本清單與 SHA

### 3.1 Cloud Run revision（本日建立的）
| revision | 基底 | 內容 | 狀態 |
|---|---|---|---|
| stock-bot-insti-r3b | R13b（**不是正式版**） | R3＋極小值顯示 | 已刪除 |
| stock-bot-insti-r3c | fix8 | R3b，改以正式版為基底 | 已刪除 |
| stock-bot-insti-r3d | fix8 | 逐值上色 | 已刪除 |
| **stock-bot-insti-r3e** | fix8 | ★ 上市前 50＋上櫃前 10 | 保留（回滾點），tag 已移除 |
| stock-bot-rk-r3 | insti-r3e | 排行榜 RK_R3 | 已刪除 |
| **stock-bot-rk-r3b** | insti-r3e | 排行榜加法人日期、★如實說明 | 保留（回滾點），tag 已移除 |
| **stock-bot-r3f** | rk-r3b | 重試、不快取部分失敗、原因如實 | 保留（回滾點），tag 已移除 |
| **stock-bot-r3h** | r3f | ★只標上市前 50，不呼叫 TPEx 收盤價 | **正式版 100%** |

### 3.2 檔案 SHA（前 16 碼）
| 版本 | app.py | insti_query_r1.py |
|---|---|---|
| fix8-r1（開工時的正式版） | f7340c7905ed68e5 | 28185d5967406ce8 |
| r13b（日誌記載，但不是正式版） | 0f0dc47572b6293d | 28185d5967406ce8 |
| insti-r3e | f7340c7905ed68e5 | 3da9b6fe4649d648 |
| rk-r3b | a3b5214daba69a1f | 3da9b6fe4649d648 |
| r3f | 47e54b77f4f1fa97 | ae1786b8ebaa819c |
| **r3h** | **c486dd1db5dd4baa** | **275f0127264550ca** |

### 3.3 repo 補丁檔（`vip1688_patches/`）
| 檔案 | 用途 |
|---|---|
| `insti_r3_patch.py` | 從原版 insti（28185d59）產生 R3 系列；支援 `--src`、`--cand`、`--app-sha`、`--no-net`；含真資料探針 |
| `rk_r3_patch.py` | 排行榜 RK_R3 段（只附加在 app.py 檔尾）；含探針 |
| `r3f_delta.py` | rk-r3b → r3f 差異部署（換 insti 全檔＋改 app.py 一行） |
| `r3g_delta.py` | **沒有執行**（dailyQuotes 備援；使用者放棄上櫃★） |
| `r3h_delta.py` | r3f → r3h 差異部署（換 insti 全檔＋整段替換 RK_R3） |
| `dupscan_20261013.py` | 重複目錄唯讀盤點（app.py 同 SHA 才比對整個目錄內容；保護正式與回滾原始碼） |

---

## 4. 功能規格與程式架構

### 4.1 公式與顯示（r3h 現況）
- 外本比／投本比 ＝ 外資／投信買賣超（股）÷ 官方發行股數（股）× 100%，取到小數 3 位。
  - 非零但絕對值小於 0.0005% 顯示 `±<0.001%`；恰好為零顯示 `0.000%`。
- 每列格式：`外本比 當日｜N日 累計｜趨勢`。N 為實際取得的交易日數，最多 5。
  - 趨勢：連買／連賣 k 日（k 等於 N 時加「+」）、轉買／轉賣、當日未進出。
- 字色：標籤用中性灰；每個數值依自己的正負上色（紅正、綠負、黃 0、灰缺）；趨勢字依當日方向上色。
  - 深色底：#FF7A7A／#5FD38D／#F5C518／#9A9A9A。淺色底：#B3261E／#1B6B3A／#7A5C00／#5F5F5F。
- ★權值股：上市市值前 50 ＝ 官方發行股數 × `STOCK_DAY_ALL` 收盤價，台北同日快取。上櫃不標★。
- 資料來源：
  - 法人：`insti_sync_source_r1.fetch_twse`／`fetch_tpex`，日期與三大法人合計逐筆核對。
  - 發行股數：TWSE `t187ap03_L` 欄位「已發行普通股數或TDR原股發行股數」；TPEx `mopsfin_t187ap03_O` 欄位 `IssueShares`（已實測：2330 是 25,932,370,067 股、6488 是 478,113,725 股）。

### 4.2 三大法人（insti_query_r1.py，R3h）
```
send_report → get_snapshot()（原邏輯，5 分鐘快取）
           → build_messages = _r3_base_build（原卡）＋ _r3_inject：
               _r3_history：當日（同買/同賣列）＋往前 4 個交易日全市場（_r3_day_rows，快取 10 天）
               _r3_shares：發行股數（重試 2 次；任一市場失敗就不快取，並記錄 fail）
               _r3_star_set：STOCK_DAY_ALL × 上市發行股數 → 前 50
               每張卡追加兩列 span；★加在標題後；carousel 超過 50,000 或單張超過 29,000 bytes → 移除新增列（INSTI_R3_SIZE_DROP）
               摘要追加定義、累計區間、★說明、缺資料的代號與原因
```

### 4.3 排行榜（app.py 檔尾 `# ===== RK_R3` 段）
```
RANKING_PICK → build_ranking_pick_report（原邏輯不動）→ push
  → rk17b 在 line_bot_api.push/reply 時重新組 carousel：
       _v9663_summary_bubble = _rkr3_summary_bubble（原卡＋圖例：法人資料日、★定義）
       _v9663_stock_bubble   = _rkr3_stock_bubble  （原卡＋兩列；第一列前面加「法人MM/DD｜」；★）
  → _rkr3_data()：get_snapshot＋_r3_history＋當日全市場 _r3_day_rows＋_r3_shares＋_r3_star_set
       快取：資料完整（當日＋★50＋發行股數無失敗）10 分鐘，否則 2 分鐘；失敗只標灰色「資料不足（原因）」
```
- 個股資料 `x["code"]` 是股票代號，`x["direction"]` 是多空方向。rk17b 會把卡片切成每則 ≤45KB、≤12 張，**最多 5 則訊息**。

---

## 5. 標準部署流程與關鍵指令

### 5.1 流程（本日每一版都照此執行）
```
1. curl 從 GitHub（固定 commit）下載補丁 → sha256sum -c 驗證
2. 從「當下正式 revision」的 build-source-location 取 zip，解壓到 /tmp（不占 Home）
3. 補丁腳本：檢查基底 SHA → 用 cp -al 建立候選目錄 → os.replace 寫入新檔（確認 nlink=1，不會改到基底）→ 編譯檢查
4. 真資料乾跑（不推播）：檢查 ORIGINAL_UNCHANGED／INSTI_R3_OK／STAR／SIZE
5. gcloud run deploy --source <cand> --no-traffic --tag <t> --revision-suffix <t>
6. 從 revision 的環境變數取得 ADMIN_LINE_ID 與密鑰 → regex 把關 → 只推給管理者（三大法人同步執行；排行榜放背景）
7. 每 30 秒讀一次日誌，最多 16 次，直到看到 INSTI_R1_PUSH_OK＋RK17B_PUSH＋PUSH_OK(RANKING_PICK)
8. 通過才 update-traffic 100%，否則不切換或自動回滾；成功才移除 tag 並清理 /tmp 與家目錄暫存
9. 所有輸出用 {…} | tee 存檔，前後自動印出 [開始]／[結束]，再用 cloudshell download 下載
```

### 5.2 常用唯讀指令
```bash
set +H; export CLOUDSDK_CORE_DISABLE_FILE_LOGGING=1 P=affable-gist-379402 R=asia-east1
# 目前正式版
gcloud run services describe stock-bot --region $R --project $P --format='value(status.traffic)' | tr ';' '\n' | grep "percent': 100"
# 正式版原始碼位置（JSON 中抽出 gs://）
gcloud run revisions describe stock-bot-r3h --region $R --project $P --format=json | python3 -c "import json,sys,re; a=json.load(sys.stdin)['metadata']['annotations']['run.googleapis.com/build-source-location']; print(re.search(r'gs://[^#\"]+', a).group(0))"
# 本日功能的日誌
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.revision_name="stock-bot-r3h" AND textPayload=~"INSTI_R3|RK_R3|RK17B_PUSH|PUSH_OK|TW_R4_HTTP|Traceback"' --project $P --freshness=1d --order=asc --limit 80 --format='value(timestamp,textPayload)'
# 誰在什麼時候切換流量
gcloud logging read 'protoPayload.serviceName="run.googleapis.com" AND protoPayload.methodName:("ReplaceService" OR "UpdateService")' --project $P --freshness=2d --limit 20 --format='value(timestamp,protoPayload.methodName)'
```

### 5.3 已踩過的坑（下次直接避開）
- 指令裡不使用 `!`，開頭加 `set +H`。
- build-source-location 是 JSON＋zip，不是網址＋tar.gz。
- 用 AST 擷取函式時要用 `ast.walk`，大多數覆寫都包在 `try:` 區塊裡面。
- 排行榜的 run_task 是同步執行，`curl -m 40` 一定逾時；要放背景。
- 不要依賴交接日誌記載的「正式版」，**部署前一律先讀流量**（本日實際遇到：日誌寫 R13b，實際是 fix8）。

---

## 6. 未完成事項與已知故障（逐項核實）

| # | 項目 | 證據 | 影響 | 狀態與建議 |
|---|---|---|---|---|
| 1 | **TPEx `tpex_mainboard_daily_close_quotes` 不穩定** | 12:17 有 1 次 ChunkedEncodingError；16:15～16:37 失敗 8 次（Read timed out 或 Chunked）；17:04 日誌出現 `[TW_R4_HTTP] act=tpex_breaker_open_10min_mkt` | R3h 已不使用；**其他模組（TW_R4 所屬，是 fix 系列的既有核心）仍在呼叫，熔斷已啟動**，該模組的上櫃行情可能缺值 | **未處理**（不在本日範圍）。建議在台北 09:00～13:30 和 17:00 後各量一次 HTTP 狀態與耗時，判斷是時段性還是持續性 |
| 2 | 三大法人有 10 檔沒有發行股數 | r3h 第一次推播 `cards=60 miss=10`；乾跑時 `FAIL []` | 卡片標灰色「資料不足」 | **未逐檔驗證**是否全部是 ETF。代號列在 LINE 摘要中，看一下即可確認 |
| 3 | 三大法人卡片接近大小上限 | 同買 carousel 47,197／50,000 bytes | 若某天超過上限，新增的兩列會被整組移除（會有 `INSTI_R3_SIZE_DROP` 日誌），原卡照常 | 監控 `INSTI_R3_SIZE_DROP`；若出現，可以把字型或標籤縮短 |
| 4 | 冷啟動延遲 | insti 首次 `ms=8258`；排行榜 `RK_R3_DATA ms` 介於 2,094～23,810（R3h 之前有 TPEx 重試時曾到 45,898） | 首次報告會慢幾秒到二十幾秒 | 已有快取（insti 前幾日資料 10 天、發行股數同日、★同日；排行榜 10 分鐘） |
| 5 | **流程治理：正式版曾被其他作業切換** | 10/12 10:57 UTC 流量被切到 fix8-r1，交接日誌沒有記錄 | 很容易用錯基底 | 本日的流程一律先讀正式流量、從 revision 下載原始碼。**建議所有作業都寫入交接日誌** |
| 6 | VIP1688 前一份交接（10/12）的 17 項待辦 | 見 `VIP1688_HANDOFF_20261012.md` 第 6 節 | 包括金鑰輪換（#1）、FinMind 額度耗盡（#3）、核心資料源失效（#4）、Home 空間（#17） | **本日沒有處理** |
| 7 | VIP1688 優化策略 A～D（草案） | 本日 09:31 提出；09:33 使用者要求略過「定位入口」 | — | **沒有實作**。其中 A（1688 的 R13B 和三大法人 R3 各自回補 5 日法人資料、重複抓取）仍然存在：fix8／r3h 裡 `VIP1688_R13B` 標記 10 處，和 `_R3_DAYS` 是兩份獨立的快取 |
| 8 | fix8 與 r13b 的差異 | 3 個檔案：`app.py`、`fundamental_entry_r19.py`、`us_analysis_entry_r1.py` | fix8 的修改內容本日**沒有審閱** | 接手者若要動 1688、基本面或美股，先用 diff 讀懂 fix8 |
| 9 | 排行榜的「不得出現資料不足」規則 | 記憶 `/areas/ranking-module.md` | 本日只在**新增列**標「資料不足」（ETF 或來源失敗），排行榜名單和策略欄位沒有改 | 需要使用者確認這樣的解讀是否可以接受（**未確認**） |
| 10 | Cloud Shell Home 使用率 95%（剩 276M） | `df` | 空間不足會讓部署或腳本失敗 | 本日只刪了 5 份逐檔比對確認完全相同的目錄（18.1M）。其他大目錄（`.local` 637M、`fundamental_r20_runtime` 491M、`stock-bot-deploy` 487M）是不同版本或執行環境，**需要使用者決定** |
| 11 | 舊的 tag 和 revision 數量多 | 17:04 的最終狀態列出約 130 個 tag（v967914、surge、dna、fundamental、tw/us-analysis、rk…） | revision 數量有上限；舊映像檔持續占用儲存 | 建議先列清單給使用者確認再清理；**不要刪 fix8-r1、insti-r3e、rk-r3b、r3f** |
| 12 | R3g 備援（dailyQuotes）沒有使用 | 使用者 16:39 決定放棄 | 上櫃不標★ | 若日後要恢復，`r3g_delta.py` 的基底是 r3f，需要重新以 r3h 為基底製作 |

---

## 7. 成本風險核實（現行正式版 r3h）

> **限制：沒有讀過 Billing 帳單資料**。以下是依日誌推估的方向，不是金額。

| 項目 | 依據 | 判斷 |
|---|---|---|
| Cloud Run 運算 | 每次報告增加：insti 5.8～8.3 秒（首次）／排行榜 2.1～23.8 秒（首次），之後走快取；r3h 去掉了 TPEx 重試（r3f 時乾跑要 64.7 秒） | 小幅增加；r3h 比 r3f 少 |
| 外部 API | TWSE／TPEx OpenAPI 與 T86／TPEx 法人報表都免費；每份報告首次最多約 12 次官方呼叫，之後走快取 | 不會增加金額；風險是限流 |
| 記憶體 | `_R3_DAYS` 最多 10 天 × 約 2,240 檔 ×（外資、投信）；發行股數 1,988 筆；排行榜快取 1 份 | 可以忽略 |
| Cloud Build／Artifact Registry | 本日部署 **8 次**（insti-r3b、r3c、r3d、r3e、rk-r3、rk-r3b、r3f、r3h），每次有建置費用，並產生一份映像檔 | **一次性費用已經發生；映像檔儲存會持續累積** |
| revision | 本日刪除 4 個（insti-r3b、r3c、r3d、rk-r3），保留 4 個 | 沒有流量時不收運算費用 |
| Cloud Logging | 每份報告新增約 5～10 行 INSTI_R3／RK_R3 日誌 | 少量 |

**結論**：在可觀測的範圍內，r3h 沒有讓運算或 AI 成本明顯上升的證據（本日沒有新增 AI 呼叫）。實際存在的成本是 8 次建置與映像檔儲存，**需要用帳單資料驗證**：
```bash
gcloud artifacts docker images list asia-east1-docker.pkg.dev/affable-gist-379402/cloud-run-source-deploy --include-tags --format='value(package,createTime)' 2>&1 | tail -20
gcloud run revisions list --service stock-bot --region asia-east1 --project affable-gist-379402 --format='value(name)' | wc -l
```

---

## 8. 待辦清單（接手者依序處理）

1. 看 LINE 三大法人摘要，確認那 10 檔「資料不足」是否都是 ETF（第 6 節 #2）。
2. 量測 TPEx `tpex_mainboard_daily_close_quotes` 在不同時段的可用性，影響 TW_R4 所屬模組（#1）。
3. 監控日誌關鍵字：`INSTI_R3_SIZE_DROP`、`INSTI_R3_SHARES_ERR`、`INSTI_R3_HTTP_RETRY`、`RK_R3_DATA_ERR`、`RK_R3_BUBBLE_ERR`、`TW_R4_HTTP`。
4. 1688 前一份交接的待辦：先處理**金鑰輪換**與 **FinMind 額度**，這兩項都需要使用者同意（#6）。
5. 清理舊 tag、revision 和映像檔：先列清單，等使用者確認後再刪（#11）。
6. Home 空間：只處理經過核實的重複或臨時候選（#10）。
7. 1688 策略 A（法人 5 日回補合併成一份快取）：要使用者同意才做（#7）。

---

## 9. 本日工作成果自評（實事求是）

**做到的：**
- 三大法人、排行榜都加上外本比、投本比與趨勢，以及權值股★，**正式上線**，前台 PASS 共 4 次（R3d、R3e、rk-r3b、r3h）。
- 上市＋上櫃都可以計算（1,988 檔）；缺資料的個股標灰色並寫明原因。
- 原卡內容逐字不變，每一版都用 `ORIGINAL_UNCHANGED` 實測驗證；排行榜的選股、策略、按鈕都沒有動。
- 每一版的流程都相同：先鎖定基底 SHA、用硬連結建候選目錄、真資料乾跑、部署到 0% 流量、只推給管理者、驗證通過才切換並附回滾、最後清理暫存。
- 抓出並修正一個設計缺陷：發行股數只抓到一部分也會快取一整天（R3f）。
- 依使用者決定放棄上櫃★，報告速度從 64.7 秒降到 5.8 秒（r3f → r3h）。

**錯誤與教訓（按嚴重度）：**
1. **一開始用錯基底**：相信交接日誌記載的 R13b，R3 和 R3b 都做在錯的基底上。到 09:52 部署後讀流量才發現正式版是 fix8（還沒切換，沒有造成損害）。教訓：部署前一律先讀正式流量。
2. **R3 的發行股數快取設計缺陷**：只抓到一部分也快取一整天，上線後 16:15 才從正式環境日誌發現。期間上櫃股可能被誤標成「如ETF」。
3. **顏色規則第一版違規**：整列依 5 日累計上色，負值也顯示紅色，靠截圖驗收才發現（R3d 修正）。
4. **把話說得太滿**：說「不再呼叫 TPEx 收盤價 API」，其實只有 R3h 自己的程式不呼叫，TW_R4 仍在呼叫（17:10 更正）。
5. **擷取或探針程式寫錯，多花回合**：探針把最大比值標錯代號；fix8 比對用了 tar.gz、也沒解析 JSON；擷取函式只掃最外層，輸出空檔；第一版比對指令裡留了一段多餘的 heredoc。
6. **排行榜測試的 curl 設 40 秒**，造成誤判為逾時。
7. 第一次切換 rk-r3b 的輸出沒有拿到，我沒有在當下要求補看。
8. 每段任務都要求「1 小時內完成」，實際從 08:51 到 17:04 才完成全部（中間有使用者新增需求與等待時間），**沒有達到時限**。

**限制：**沒有讀過帳單資料；沙箱連不到官方 API，所有真實資料都靠使用者回貼；VIP1688 優化與前一份交接的待辦本日都沒有處理。
