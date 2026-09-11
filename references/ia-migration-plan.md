# Threads Dashboard — IA 重整與遷移計畫

> 建立於 2026-09-11。
> 產品規格與 UI 驗收在 `dashboard-spec.md`，語氣規則在 `jessica-voice.md`。
> **本檔只寫 IA 與 migration，不收 Git、部署、verifier 等實作細節**
> （那些歸 `runbook-windows-deploy.md`）。
> 發布相關只寫一句：**須通過既有 Definition of Done。**

---

## 1. 問題

隨著 Jessica Voice、留言分析、Conversation Loop、Evidence Gate 等規則加入，
頁面資訊量已超出可用範圍。

**現況盤點（2026-09-11）**

```
固定列（永遠可見、無法收合）
├─ header          ├─ summary-bar（5 格）   ├─ output-bar（4 格）
├─ daily-brief（8 條）  ├─ tabs（8 個）      ├─ level-bar（5 個）
└─ keyword-bar（15 顆）
                    合計 41 個可點元素
```

然後預設落在「待辦回應」分頁。**Jessica 要回一則留言，得先滑過 41 個東西。**

| 分頁 | 量體 |
|---|---|
| `panel-todo` / `panel-week` / `panel-search` | 動態 |
| `panel-comms` 35 卡｜`panel-daily` 61｜`panel-budget` 84｜`panel-heritage` 49 | 229 卡 |
| `panel-strategy` | **約 1,100 行、12 個 section** |

`panel-strategy` 12 個 section：今日草稿推薦｜留言行銷紀錄｜產出效益追蹤｜四大戰略抽屜｜
爆款原因解析｜受眾痛點地圖｜適合的主題與互動方向｜設計師視角範本庫｜視覺調性升級｜
突圍策略｜高效產出工作流｜顧客體驗峰終定律

**單卡內部**（×229）：貼文原文 → 統計 → 熱門留言 → 觀察備註 → 市場訊號 → 原始連結 →
jessica-insight 八段抽屜

---

## 2. Mapping：現有區塊 → 新節點

**一筆資料都不刪，只改可見層級。**

| 現有區塊 | 新節點 | 處置 |
|---|---|---|
| `daily-brief` 8 條 | 今天 | **拆分**：行動項留 L1，爬取狀況／安全事項移「為什麼」 |
| `output-bar` | 今天（收合） | 折疊 |
| `summary-bar` | 延伸閱讀 › 資料概況 | 降級 |
| `panel-todo` | 今天 › 待回覆 | 保留為主入口 |
| strategy › 今日草稿推薦 | 今天 › 今天發什麼 | 提升到 L1 |
| strategy › 留言行銷紀錄 | 今天 › 今日互動紀錄（收合） | 折疊 |
| strategy › 產出效益追蹤 | 延伸閱讀 › 成效回填 | 降級 |
| `tabs` 四大焦慮分頁 | 找題目 | 見決策 B |
| `keyword-bar` 15 chip | 找題目 › 快速篩選 | 移入 |
| `level-bar` | 找題目 › 篩選（收合） | 折疊 |
| `panel-search` | 頂部常駐搜尋 | 改造，分「直接答案／延伸閱讀」 |
| 卡片 › 熱門留言 | 議題樹 › N 則值得看的留言 | **需補資料，見決策 A** |
| 卡片 › 💬四 留言草稿 | 議題樹 › Jessica 可以怎麼回 | **需補前兩層** |
| 卡片 › 📊二 消費者訊號 | 為什麼 › Listener Analysis | 降到 L3 |
| 卡片 › 🔍三 判讀 | 為什麼 › 建議理由 | 降到 L3 |
| 卡片 › 📝五 延伸貼文草稿 | 議題樹 › 可以延伸 | 保留 |
| 卡片 › 🔀六／🔧七／📌八 | 延伸閱讀 | 降到 L5 |
| strategy › 爆款解析／痛點地圖／主題方向 | 為什麼 | 降級 |
| strategy › 範本庫／視覺調性／突圍策略／工作流／峰終定律 | 延伸閱讀 | 降到 L5 |
| — | Jessica 怎麼說（Voice 案例庫） | **新建**，引用 `jessica-voice-samples.md` |

### 2.1 四類處置

**✅ L1 保留**　今天發什麼｜今天值得互動｜有後續｜可延伸題目｜四個主入口
**🔽 折疊 L2**　output-bar｜level-bar｜留言行銷紀錄｜四大分頁卡片列表
**📦 降 L3–L5**　summary-bar｜八段抽屜的二三六七八｜strategy 的 9 個策略 section｜效益追蹤
**🆕 新建**　議題小樹導覽層｜關鍵留言的意圖標籤與摘要｜三層決策樹｜Voice 案例庫

---

## 3. 三項決策（已定案）

### 決策 A｜forward-only + on-demand enrichment

不批次回填 229 張舊卡。新資料從新版排程開始產生。

舊卡只有兩種情況補算：
1. Jessica 主動開啟並點「補算這則」
2. 舊卡重新進入「今天值得看／待回覆／可延伸」等 active workflow

**理由**：新增的三種資料都是為了改善 Jessica 接下來的操作，不是補漂亮的歷史資料。

### 決策 B｜雙軸並存

```
焦慮軸（既有）：溝通與翻車／日常佩戴／預算審美／傳承情感
  → 回答「客人在卡什麼？」，保留為資料判讀與策略層

題材軸（新增）：婚戒／戒圍佩戴／客製設計／感情婚姻／籌備婚禮／新發現
  → 回答「Jessica 現在想找什麼內容？」，作為 UI 主導覽
```

**不重新分類 229 張卡。** 優先用既有 metadata／`data-keywords` 建立動態 mapping；
證據不足時允許 `待分類`，**不得硬分類**。

### 決策 C｜Selection 留痕

UI 名稱用「**N 則關鍵留言**」，不用「前五大」——選的是代表性與互動價值，不是排行榜。

L4 Evidence 保存候選／入選／未入選／理由／代表的需求觀點／使用的訊號。
Jessica 日常不顯示，只有點「為什麼挑這些留言？」才展開。

**「N 則」不是硬性湊滿**——只有 2–3 則真正有代表性就顯示 2–3 則。

---

## 3.5 Persona 覆蓋檢查（2026-09-11 新增）

來源：Tru-Mi 品牌策略完整手冊（Slides，正本；mapping 見 `references/brand-voice.md`）

```text
品牌手冊定義：
- Alex｜婚戒
- Emily｜寶寶禮
- Chloe｜離婚／重新開始
- Robert｜傳承

目前 Dashboard：
- Chloe 情境：現有 229 張卡未觀察到明確覆蓋
- Robert 情境：需盤點既有「傳承情感」卡片後才能判定覆蓋程度

狀態：
→ 內容／探索覆蓋待驗證
→ 不等同市場需求已驗證
→ 不等同低競爭或高客單已被外部證據確認
→ 不為補齊 Persona 而人工製造卡片
```

### 3.5.1 Evidence Gate 提醒

品牌手冊把 Chloe／Robert 標為差異化方向、並附帶「市場幾乎沒有對手深耕」
「客單最高」等判斷。**那是品牌自身的策略主張，不是外部市場證據。**

```
可以說：品牌手冊把離婚重生與傳承定義為差異化方向
不得說：這兩個場景是已驗證的市場缺口／低競爭／高客單
```

要主張後者需外部查證，證據另存。詳見 `brand-voice.md` §6。

> 這條是接 2026-09-11 的實際教訓——Jessica 的一句觀察曾被擴寫成
> 「高需求、低競爭、完全沒有品牌承接」（`jessica-voice-samples.md` N-002）。
> **品牌手冊是內部文件，它的市場判斷同樣適用這條 Gate。**

### 3.5.2 可以做的下一步（不製造資料）

```
① 盤點既有 panel-heritage 的 49 張卡，判定 Robert 情境實際覆蓋多少
② discovery 關鍵字池目前沒有離婚重生相關字，可評估是否加入
   （加了如果撈不到，那本身就是有意義的觀察，不是失敗）
③ 兩者都只做「觀察覆蓋率」，不回頭補卡片
```

---

## 4. 六階段

| Phase | 內容 | 可獨立回滾 |
|---|---|---|
| **P0** 前置 | 建 `backup/`、題材軸 mapping 表、效能 baseline | — |
| **P1** Schema | 新卡帶新欄位；`dashboard_check.py` 擴充（**僅驗新卡**） | ✅ |
| **P2** 議題小樹 | 卡片內部改成 L1–L5 漸進展開 | ✅ |
| **P3** 首頁 IA | 四個主入口＋頂部搜尋；strategy 12 section 降級 | ✅ |
| **P4** On-demand | 舊卡「補算這則」 | ✅ |
| **P5** Capacity Governance | 見 §6 | ✅ |

**依賴關係**

```
P0 ─┬─→ P1 Schema ─→ P2 議題小樹 ─→ P3 首頁 IA
    └─→ 題材軸 mapping ─────────────┘
                                    ↓
                          P4 On-demand ─→ P5
```

- P1 必須先於 P2：沒有資料就沒有樹可展開
- P3 最後：首頁改動最顯眼，前面沒穩就改會讓她每天用的東西壞掉
- **P1 建議先跑一週**（每天 1–2 張新卡自然累積）再進 P2

每階段之間的檢查點：**須通過既有 Definition of Done**，再加 Jessica 實測一天。

---

## 5. Active Conversation 追蹤

### 5.1 判定

**進入 active（三項全中）**：Jessica 已送出留言｜最後活動 ≤ 7 天｜未標記結束

**停止 polling（時間類，可自動）**

```
① 連續 3 天無新回覆
② 距 Jessica 最後一則 > 14 天
③ Jessica 手動標記「聊完了」
```

**只能降頻並觸發重新判斷（不得自動結案）**

```
④ 對方說「謝謝」
⑤ 達到固定往返輪數
```

⚠️「謝謝～那如果我的關節比較大怎麼辦？」有道謝，但對話顯然沒結束。
**判斷人正在做什麼，不能只靠關鍵字和輪數**（見 `jessica-voice.md` §7 Gate ①）。

### 5.2 Request budget 三分流

```
優先級
1. 有新回覆、待 Jessica 接球的既有對話
2. active-but-no-new-reply
3. discovery
```

**節流時優先減少 discovery 關鍵字組數**，不得為了 discovery 犧牲待接球的對話。

⚠️ 第 1 類的判定必須是「**有新回覆，且該回覆之後 Jessica 未再發言**」——
不能只看「有新回覆」，否則她剛回完也會被算成待接球。

⚠️ 不是所有 active conversation 都優先。「昨天留過言但對方沒新回覆」不值得犧牲 discovery 重抓。

### 5.3 請求量控制

每日追蹤上限 5 則，超過依 `data-convo-last` 由新到舊取前 5。間隔沿用 discovery 的 20–30 秒。

---

## 6. P5 = Capacity Governance（不是時間汰舊）

**不採固定 90／180／270 天門檻。** 卡片舊不等於沒價值——婚戒、戒圍、預算、家族情感
這些題材很多不是時效內容。

先建立 baseline：

```
□ HTML file size          □ DOM node count
□ TTI（首次可互動時間）     □ 展開一張卡的反應延遲
□ filterKeyword 掃 229 卡的耗時   ← 最可能先撞牆（每次全量 clone DOM）
□ dashboard_check.py runtime
□ 新 schema 實際平均增量（KB/卡）
```

達到事先設定的效能警戒值後，才依證據設計 archive。
排序依據應綜合：**低價值＋低活躍＋長期未使用**，日期只是其中一個訊號。

**P5 不是 P1 的 blocking dependency。** P1 每天只有 1–2 張新卡，
沒有必要為了一年後的推估容量，在第一階段引入破壞性的 archive migration。

### 6.1 容量推估（僅供 baseline 參考，不作為決策依據）

每張新卡增加約 2.9–4.4 KB（關鍵留言 ~1.4｜三層決策 ~0.6｜Evidence ~0.9｜thread ~1.5）。
每天 1–2 卡 ≈ +2.2 MB/年。現況 1.23 MB。

**這是推估不是實測**，實際值以 baseline 為準。

---

## 7. Rollback / Validation

### 7.1 Rollback

工作資料夾**不是 git repo**（推送由 Windows 端另行 clone），沒有 `git revert` 可用。

```
每階段動工前：backup/YYYY-MM-DD-P{N}-before.html
回滾：複製回主檔 → dashboard_check.py → 同步 index.html → 依 Definition of Done 發布
第二道保險：GitHub 每日 commit
```

**P5 汰舊是唯一不可輕易回滾的**，動工前須另留完整快照，且 `archive.html` 與主檔同時備份。

### 7.2 Validation 三層

**第一層 自動**　`dashboard_check.py` exit 0，且**舊卡內容 byte-identical**
（除新增的 `data-topic`）。這條要寫成腳本比對，不能靠眼睛。

**第二層 UX 情境層數檢核**

| # | 情境 | 目標 |
|---|---|---|
| 1 | 今天發什麼 | ≤ 2 層 |
| 2 | 回自己的留言 | ≤ 2 層 |
| 3 | 去海巡 | ≤ 2 層 |
| 4 | 想知道 AI 為什麼這樣建議 | 3 層 |
| 5 | 研究完整 SOP | 5 層 |
| 6 | 快速知道留言區在討論什麼 | 2 層看到關鍵留言＋分類 |

**第三層 Jessica 實測**　見 `dashboard-spec.md` §10.1。**不通過就回滾**，不管前兩層多漂亮。

### 7.3 一條容易悄悄失效的回歸檢查

**`.key-comment` 數量分布。** 如果新卡幾乎都剛好 5 則，代表「不硬湊」沒有被真正執行，
而是被湊出來了。

---

## 8. 本檔不處理的事

| 項目 | Canonical owner |
|---|---|
| Git 認證原則、禁止 PAT fallback | `GITHUB-AUTH-STANDARD.md` |
| Windows 部署操作、Git Bash、verifier 缺口 | `runbook-windows-deploy.md` |
| L3 定義 | `daily-sop.md` Step 6.9 |
| 語氣規則 | `jessica-voice.md` |
| 環境事故 | `incident-2026-09-11-bash-plan9.md` |

**發布只寫一句：須通過既有 Definition of Done。**
不在此保存 Git 實作細節，避免本檔慢慢變成第二份部署手冊。
