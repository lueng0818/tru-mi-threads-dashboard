# Tru-Mi Threads 每日海巡 SOP（排程正本）

> 這份檔案是每日排程的**規格正本**。Cowork 排程的 prompt 只留「開跑指令」，
> 規則一律寫在這裡——改規則改這個檔，不用去動排程 UI，而且改動會進 git 有版本可回溯。
> 最後更新：2026-09-02

---

## 0. 開跑前護欄

**每週版優先於每日版。** 若同一天另有涵蓋相同儀表板或相同資料源的「每週版」排程被觸發
（或該支排程今天已跑過／正在跑），本任務**當日不執行**：輸出一行
「本日由每週版排程接手，每日版跳過」後結束，不爬取、不寫入 HTML、不推送 GitHub。
理由：同一份 HTML 被兩支排程同日先後覆寫會遺失卡片與統計。
判斷方式：開跑時先用 bash 取得今天日期與星期。使用者手動要求補跑時才可忽略。
※ 目前尚無每週版排程，本條為預留護欄。

**帳號與色彩基準（2026-07-25）**
- 對外帳號一律 `@trumi_jewelryofficial`（舊帳號 `@trumi_jewelry` 已停用）。
  新卡片與今日草稿結尾固定「完整故事看 IG @trumi_jewelryofficial」。
- 儀表板已對齊 Tru-Mi Design System v1.0。**不得**改動 `:root` 或既有 CSS、
  不得把亮底分析卡還原成綠底、不得引入舊金 `rgba(230,180,34)` ／舊綠 `rgba(8,77,44)`。
  A/B/C/D/風險 分級功能色（紅橘藍灰黑）是刻意保留的辨識系統，不可換成品牌綠。
  → 這三條由 `tools/dashboard_check.py` 自動驗，不必用眼睛檢查。

## 目標檔案

| 檔案 | 角色 |
|---|---|
| `threads_wedding_ring_dashboard.html` | 儀表板主檔（唯一編輯對象） |
| `index.html` | 同步備份，Step 6 由主檔完整複製產生，**不直接編輯** |
| `tools/dashboard_prep.py` | 開跑前情報包＋查重 |
| `tools/dashboard_check.py` | 收尾健檢閘門（exit 1 就禁止推送） |
| `github_push.sh` | 上傳（不得修改；`.github_token` 不得印出） |

---

## Step 1：爬取 Threads 婚戒貼文

工具：Kapture Browser Automation 開 https://www.threads.net
（不可用時改 Claude in Chrome 的 navigate／get_page_text／javascript_tool）。

關鍵字池（每次輪替 3-4 組）：
婚戒、結婚戒指、對戒、求婚戒指、婚戒推薦、婚戒預算、5萬婚戒、
婚戒實品落差、婚戒硌手、婚戒改圍、舊戒重製、媽媽戒指重做

**節流對策（實測有效）**：同一輪連續搜尋 2～3 個關鍵字後常只回傳 1 筆。
每次搜尋間隔 20～30 秒，並在頁面反覆 scroll 到底觸發載入；
改由 UI 切「最近」分頁也能恢復回傳量。

收錄標準（最近 24–48 小時）：
- 互動數（愛心＋留言＋轉發）> 50，**或**
- 帶有明確日期／預算／需求／焦慮訊號（互動數低也要收）
- 有情感或痛點內容，非純廣告

每篇記錄：作者帳號、貼文原始連結、全文、互動數、前 5 則留言（含留言者與讚數）。
只找得到主頁找不到單篇連結時，仍記錄帳號連結並標記「貼文不存在」。

## Step 2：去重（**用腳本，不要手動 grep 主檔**）

```bash
python tools/dashboard_prep.py                      # 現況＋插入錨點行號
python tools/dashboard_prep.py --check "@候選帳號" "貼文連結" ...
```

回 `DUP` 就跳過，回 `NEW` 才處理。查重同時比對帳號名與 Threads post id。

若全部都是 DUP：在 `panel-strategy` 今日草稿區加一行
「⚠️ 今日無新貼文，沿用昨日草稿。」→ 跳過 Step 3～5，仍執行 Step 6.5 後結束。

## Step 3：分類至四大戰略分頁

| panel | 收什麼 |
|---|---|
| `panel-comms` 🚨 溝通與翻車焦慮 | 服務冷暴力、設計師／業務不聽話、專櫃態度差、實品與照片落差、避雷爆料 |
| `panel-daily` 🌿 日常佩戴與體感 | 硌手勾衣打字卡手、戒圍變化、配戴習慣、職業限制、意外遺失 |
| `panel-budget` 💸 預算與審美拉扯 | 預算焦慮、男女審美衝突、長輩介入、品牌迷思、CP值與材質 |
| `panel-heritage` 💛 傳承與情感重塑 | 舊戒／舊金改造、長輩遺物、彌補遺憾、內圈刻字、跨世代故事、求婚驚喜 |

## Step 4：海巡八段式判讀

先讀 `references/patrol-playbook.md`（與 `references/platforms.md`）。
可存取 `tru-mi-marketing-ops:tru-mi-threads-patrol` 技能時亦可引用。

**八類**：1 無方向求推薦／2 預算明確求解／3 兩人審美衝突／4 品牌實品失望／
5 時程焦慮／6 日常佩戴問題／7 求婚驚喜兩難／8 舊戒傳承重製。
無法歸類標「非標準八類」並簡述。

**意圖分級**：A 高意圖｜B 問題意圖｜C 情緒共鳴｜D 低對頻｜
風險（避雷／點名／敏感家庭／協尋——不留言、不自薦、只觀察）。

每篇用繁中產出七項：
2. 消費者訊號
3. 判讀
4. 非推銷式留言草稿（**A/B/C 才寫**，2-4 句，不放連結、不自薦、不批評同業）
5. Threads 延伸貼文草稿（設計師第一人稱 100-200 字，結尾固定
   「完整故事看 IG @trumi_jewelryofficial」）
6. 跨平台延伸（IG／Reels／限動／LINE 官網；Reels 公式依焦慮類型交錯選，
   勿每篇都用「迷思破解 B」）
7. 漏斗更新
8. 追蹤動作

**語氣**：溫暖真實克制，用生活語言不用珠寶術語。
**禁用詞**：高CP值、物超所值、划算、優惠、限時。留言先回答問題，不先證明品牌厲害。

### 4.5 素材關卡（寫「五、延伸貼文草稿」前必跑）

依全域 CLAUDE.md 的 ALWAYS #1，任何 Tru-Mi 內容動筆前要過素材四格。
本排程的素材來源就是當日那則 Threads 原文，所以四格這樣填：

| 格 | 從哪裡來 |
|---|---|
| 矛盾 | 原貼文裡那個沒解決的張力（不是我們替他總結的） |
| 具體物件細節 | 原文出現的實體：桌數、克數、戒圍、價格、場地、職業⋯ |
| 第一人稱來源 | 設計師觀點只能寫 Jessica 真的做過／說過的事 |
| 去重 | `--check` 已保證帳號與貼文不重複；主題也要跟最近 7 天草稿不同（看 `--json` 的 track_recent） |

**四格填不滿就不要硬寫**：該篇 draft-body 寫
「素材不足，今日暫緩發文」，而不是用形容詞把字數撐滿。
（違反的後果見 CLAUDE.md NEVER #1：舊內容換句話說。）

### 4.6 交稿前去 AI 味終檢

今日草稿定稿前，用 `speak-human-tw` 的機械層清單自查：
中國用語、半形標點、emoji（品牌帳號 0）、破折號密度、對稱最高級句、抽象名詞化。
**機械層過關不等於沒問題**——再拿原始貼文逐句比對一次：
有沒有把作者的敘述改寫成引號內的他人原話？有沒有替作者發明立場或升華句？
有就砍掉，不補假事實。

---

## Step 5：更新儀表板 HTML

**插入位置**：對應 panel 的 `.posts-grid` 最前面
（行號由 `dashboard_prep.py` 的「插入錨點」給）。

**卡片規格**
- 開頭 div 必帶 `data-level`（A/B/C/D/RISK）
- 必帶 `data-keywords="關鍵字1 關鍵字2"`（省略會讓 JS 退回全文比對，搜尋品質變差）
- 必帶 `<div class="post-date">YYYY-MM-DD</div>`，**零位補齊**（`2026-03-10` 不是 `2026-3-10`）
- 建議帶 `data-collected="YYYY-MM-DD"`（今天的日期）——這是未來要做卡片汰舊的唯一依據
- 內文用「jessica-insight 八段抽屜」完整格式（📊二/🔍三/💬四/📝五/🔀六/🔧七/📌八）

**收尾 `</div>`**：每張卡片 jessica-insight 後依序恰好 3 個 `</div>`
（①關 jessica-insight ②關 comments-section ③關 post-card——第③最常漏）。
唯一例外是各 panel 的**最後一張卡片**，其後會多出 2 個
（關 `.posts-grid` 與 `.category-panel`），屬正確結構，不要「修正」。

**今日草稿**（`class="draft-card"`）：取今日互動數最高、A 或風險以外者的「五、延伸貼文草稿」。
全為風險／敏感／同業時，draft-body 寫
「今日新貼文皆屬觀察類，暫緩發文，沿用昨日草稿。」

**效益追蹤欄**：`#trackBody` 最前面插一列當日草稿
（Threads｜主題｜@靈感帳號；四個效益欄 time/likes1hr/auth/reach 填「待回填」
帶 `col-fill`＋`contenteditable`，備註「—」）。固定 8 欄。
`.output-bar` 與加總由 `trumi_track_v1` JS 自動運算，不要手改數字。

**留言行銷紀錄**：讀 `https://www.threads.com/@trumi_jewelryofficial/replies`
與 `https://www.threads.com/@trumi_jessica/replies`，把當日／本週**實際送出**的留言
登錄到 `#commentLogBody`（日期｜平台｜帳號｜留言對象｜留言類型｜意圖等級｜成效｜備註，固定 8 欄）。
零留言時保留零產出列，並在「今日提醒重點」加一條警訊。
⚠️ 這一欄記錄的是**已送出**的留言，不是備妥的草稿——兩者不可混寫。

**計數**：各分頁 tab `<span class="count">N</span>` ＝ 該 panel post-card 數；
同步更新 summary-bar。→ 這兩項由健檢腳本自動核對，改錯會 FAIL。

**固定結構（不得移除，損毀須還原）**：
`.level-bar`（data-level 自動計數）、`.output-bar`＋`.track-table/#trackBody`（trumi_track_v1）、
`.keyword-bar`＋`#panel-search`（filterKeyword/cardMatchesKw 只比對貼文原文＋留言、排除分析模板）、
`#commentLogBody` 留言行銷紀錄表。

### Step 5.9：健檢閘門（**沒過就不准往下走**）

```bash
python tools/dashboard_check.py
```

驗：div 平衡與巢狀、post-card 無巢狀、各 panel 卡片深度一致、
data-level 齊全且合法、`#trackBody`／`#commentLogBody` 每列 8 欄、
分頁計數與 summary-bar 對得上、禁用色碼、停用帳號、`:root` 未被改動、
重複 permalink、主檔／備份是否一致。

exit 0 = PASS 才可進 Step 6；exit 1 = FAIL，先修好，**禁止推送**。

## Step 6：同步備份

健檢 PASS 後，把 `threads_wedding_ring_dashboard.html` 完整複製至 `index.html`。

## Step 6.5：上傳 GitHub

```bash
bash github_push.sh
```

`OK`＝成功／無變動；`SKIP`＝token 未設定（註明，不視為錯誤）；
`FAIL`＝失敗（註明原因，**不重試超過 1 次**）。
嚴禁印出 token；不要修改 `github_push.sh` 與 `.github_token`。
GitHub Pages CDN 約 10 分鐘快取屬正常。

## Step 7：輸出摘要

```
✅ Tru-Mi 每日更新完成｜YYYY-MM-DD
新增貼文：N 則（分佈：溝通N / 日常N / 預算N / 傳承N）
意圖分級：A級N｜B級N｜C級N｜D級N｜風險N
今日草稿靈感：@帳號
本週留言行銷：官方N則｜個人N則（實際送出）
健檢：PASS
檔案已同步至 index.html
GitHub：[已推送 ✅ / 無變動 / 略過 / 失敗＋原因]
```

回報紀律（全域 CLAUDE.md）：`✅ 做完了`／`⚠️ 有疑慮`／`❓ 資訊不夠`／`⛔ 卡住了` 四選一。
爬取失敗、健檢 FAIL、留言零產出，都要如實寫進摘要，不可用「應該沒問題」帶過。

---

## 品牌核心價值與口徑

**差異化資產**：1:1 蠟模試戴、同一師傅從諮詢到交件、無門市無業績壓力、
內弧圓角＋1.8mm 厚度底線、免費鑽戒租借、舊金改造原料自帶、內圈刻字。

**價格帶（假設值，不可稱已驗證）**：入門簡約對戒 NT$38,000-48,000｜
主力故事訂製 NT$58,000-88,000｜高階專屬訂製 NT$108,000 起｜舊戒改造測試帶 NT$20,000-45,000。

LINE：@303nksbt｜IG：@trumi_jewelryofficial｜一般工期 15-18 個工作天。
語氣：溫柔、理性、有同理心，不說教，不誇大。

## 注意事項

- Threads 需登入才可瀏覽 → 截圖告知，不強制登入。
- 爬取失敗記錄錯誤於摘要，不中斷排程，仍執行 Step 6.5 檢查未推送變更。
- 風險貼文一律不留言、不自薦、不批評同業，只記錄觀察。
- 所有新增內容用繁體中文。
- 每次只更新內容（新增卡片、統計、今日草稿、當日追蹤列、留言行銷紀錄）。
