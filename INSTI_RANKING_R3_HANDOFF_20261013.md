# 三大法人＋排行榜：外本比／投本比／權值股★ 交接日誌（2026-10-13）

> 依據：本日 Cloud Shell 回貼的實際輸出與 Cloud Run 日誌。只寫有證據的內容。

## 1. 現況

| 項目 | 狀態 |
|---|---|
| 正式版 | Cloud Run `stock-bot` → **`stock-bot-r3h`** 100%（2026-10-13 09:04 UTC 切換，前台 LINE PASS） |
| 回滾點 | `stock-bot-r3f` → `stock-bot-rk-r3b` → `stock-bot-insti-r3e` → `stock-bot-01296-xid`（tag `fix8-r1`，本日任務前的正式版） |
| 回滾指令 | `gcloud run services update-traffic stock-bot --to-revisions stock-bot-r3f=100 --region asia-east1 --project affable-gist-379402` |
| 補丁 | `vip1688_patches/insti_r3_patch.py`（產生 insti_query_r1.py）、`rk_r3_patch.py`（排行榜段）、`r3f_delta.py`、`r3h_delta.py` |
| 檔案 SHA | r3h：app.py `c486dd1db5dd4baa`、insti_query_r1.py `275f0127264550ca` |

注意：本日開始時日誌記載的正式版是 R13b，但實際 100% 流量在 `fix8-r1`（10/12 10:57 UTC 由其他作業切換）。之後所有修改都以「當下正式版的原始碼」（從 revision 的 build-source-location 下載）為基底，沒有覆蓋 fix8 的修改。

## 2. 功能定義

- **外本比／投本比** ＝ 外資／投信買賣超股數 ÷ 官方發行股數 × 100%，取到小數 3 位。極小的非零值顯示 `±<0.001%`，恰好為零顯示 `0.000%`。
- **格式**：`當日｜近N日累計｜趨勢`。N 為實際取得的交易日數，最多 5。趨勢有：連買／連賣N日（全部同向時加「+」）、轉買／轉賣、當日未進出。
- **顏色**：每個數值依自己的正負上色（紅＝正／買、綠＝負／賣、黃＝0、灰＝缺資料）；標籤為中性灰。
- **★權值股** ＝ 上市市值前 50（官方發行股數 × STOCK_DAY_ALL 收盤價），台北同日快取。**上櫃不標★**（使用者 16:39 決定放棄上櫃前 10）。
- **資料來源**：
  - 法人：insti_sync_source_r1 的官方 T86／TPEx，日期與合計逐筆核對。
  - 發行股數：TWSE `t187ap03_L`＋TPEx `mopsfin_t187ap03_O`（單位：股，已用 2330、6488 實測驗證）。
  - 收盤價：TWSE `STOCK_DAY_ALL`。
- **資料不足的原因會如實顯示**：
  - 無發行股數 → 「官方無發行股數，如ETF」。
  - 發行股數來源失敗 → 「上櫃官方發行股數來源暫缺，或為ETF」，而且不快取，下次重抓。

## 3. 模組接法

- **三大法人**（mode `INSTI_SYNC_R1`，app.py 約 11721 行 → `insti_query_r1.send_report`）：用 `build_messages` 包一層，每張卡尾端追加兩列；原卡內容逐字不變（用 `ORIGINAL_UNCHANGED` 檢查）。卡片大小超過上限時，只移除新增列。
- **排行榜**（mode `RANKING_PICK`）：在 app.py 檔尾的 `RK_R3` 段把 `_v9663_stock_bubble`、`_v9663_summary_bubble` 各包一層。rk17b 在推送前用模組層級的名稱逐檔畫卡，所以新增欄位會生效。
  - 每張卡第一列加上「法人MM/DD｜」。
  - ★加在含有該股代號的第一個文字節點後面。
  - 總覽卡加一行圖例。
  - 快取：資料完整時 10 分鐘，不完整時 2 分鐘。
- 1688 精華報只用 `get_snapshot`／`select_rows`，本次沒有改動這兩個函式。

## 4. 已知限制與觀察

1. TPEx `tpex_mainboard_daily_close_quotes` 在 10/13 16:15～16:37 持續逾時或斷線（ChunkedEncodingError、Read timed out）→ 因此放棄上櫃★，R3h 已完全不呼叫這支 API。
2. 冷啟動時，新增欄位需要抓 4 個前交易日的全市場法人資料、發行股數和收盤價（排行榜約 9～24 秒）；之後走快取（2～6 秒）。
3. 卡片大小：三大法人同買 carousel 47,197／50,000 bytes，餘裕不多。超過上限時會自動移除新增列並記錄 `INSTI_R3_SIZE_DROP`。
4. Cloud Shell HOME 使用率 95%（剩約 276M）。只刪了 5 份經過「整個目錄內容逐檔比對」確認完全相同的重複目錄，其餘不同版本沒有動。

## 5. 監控日誌關鍵字

`INSTI_R3_OK`、`INSTI_R3_SHARES(_ERR)`、`INSTI_R3_HTTP_RETRY`、`INSTI_R3_STAR`、`INSTI_R3_SIZE_DROP`、`RK_R3_DATA(_ERR)`、`RK_R3_BUBBLE_ERR`、`V967914RK17B_PUSH`、`INSTI_R1_PUSH_OK`、`PUSH_OK`
