# Tru-Mi Threads 每日海巡 SOP（排程正本）

> 這份檔案是每日排程的**規格正本**。Cowork 排程的 prompt 只留「開跑指令」，
> 規則一律寫在這裡——改規則改這個檔，不用去動排程 UI，而且改動會進 git 有版本可回溯。
> 最新更新：2026-09-11 下午（建立 6 份 canonical 文件並完成 relocation：
>   4.8.6 語料 → `jessica-voice-samples.md`；Step 6.5 Windows 操作 → `runbook-windows-deploy.md`；
>   Step 5 `data-keywords` JS 行為 → `dashboard-spec.md`。**本輪只搬移，未改寫規則語意。**
>   §4.4／§4.7／§4.8／§4.9 全部保留在本檔。）
>
> 前次更新：2026-09-11（新增 **4.9 Listener Analysis（本章最上位：先聽懂再回話）**、
>   **4.8 Conversation Loop**（唯一有完整行為鏈證據的一節）；
>   並降級 4.8.1 原本「不要急著把話講完＝上位原則」的過度概括；
>   4.4.0 依真實樣本把留言拆成社群互動／海巡兩型；
>   新增 4.4／4.7 是兩個模組不共用生成邏輯的界線；
>   更正 Step 5 對 `data-keywords` 的錯誤描述——它是 OR 加分不是 fallback）
>
> **本章優先序（衝突時由上往下）**：`4.9 聽懂對方` → `4.8 互動策略` → `4.4 留言語氣` → `4.7 發文語氣`
> 前次更新：2026-09-10（Step 6.5 補上 Windows `bash` 指向 WSL 的失敗模式與正確呼叫方式）
> 再前次：2026-09-07（CONCURRENCY INCIDENT 後導入互斥鎖與五段式派送架構）

---

## Canonical control references

> **2026-09-07 改為指標。** 本節原本內嵌四條 Canonical Rules 的完整條文，
> 與跨專案正本形成**兩份正本**——同一規則維護兩處，未來一定會分叉。
> 已發生過一次 prompt drift，這是防呆，不是預防性設計。

```text
Canonical control references:

- Human Verification / Dispatch:
  000_Agent/knowledge/HUMAN-VERIFICATION-DISPATCH-STANDARD.md

- Execution Boundary:
  000_Agent/knowledge/EXECUTION-BOUNDARY-STANDARD.md

- Credential placement / audit output safety:
  chanel deco/GITHUB-AUTH-STANDARD.md

若本 SOP 與上述 canonical standard 衝突，
以 canonical standard 為準。
本 SOP 不複製或重新定義其狀態機與授權語意。
```

**專案內 canonical ownership（2026-09-11 建立）**

| 檔案 | 唯一負責 |
|---|---|
| `references/daily-sop.md` | 每日 Step 0–8、何時套用哪個規則（**本檔**） |
| `references/brand-voice.md` | 品牌手冊正本來源、**語域分層**（品牌層／Threads 互動層）、跨語域條文 |
| `references/jessica-voice.md` | **Threads 互動層**的 Voice 規則、Rule Generalization Gate、四條品質 Gate |
| `references/jessica-voice-samples.md` | 真實語料、上下文、來源、外部確認、AI 寫偏反例 |
| `references/dashboard-spec.md` | Dashboard 產品規格、schema、`data-*`、JS 行為、UI 驗收 |
| `references/ia-migration-plan.md` | IA 重整與 P0–P5 migration |
| `references/runbook-windows-deploy.md` | Windows 部署操作、故障排除、技術債 |
| `references/incident-2026-09-11-bash-plan9.md` | 2026-09-11 環境事故 |

**一份規則只能有一個 owner。** 本檔引用，不複製。

正確的分層是：

```text
Canonical Standard
        ↓
Project SOP mapping     ← 本檔只寫這一層
        ↓
Scheduled Prompt
        ↓
Runtime execution
```

**不是**：`Canonical Standard ↘ 完整複製 A ↘ 完整複製 B ↘ 完整複製 C`。
後者正是 drift 的來源。

---

## 本流程的 mapping（Tru-Mi 專屬，不重新定義語意）

```text
Validation PASS
→ CONTENT_COMPLETE

容器 runtime
→ 不具 Windows deploy authority

Windows deployment
→ 依 Execution Boundary Standard

DEPLOY_READY
→ 不等於 DEPLOY_PUSHED

remote artifact hash verified
→ DEPLOY_VERIFIED
```

具體對應到本專案的檔案與工具：

| canonical 概念 | Tru-Mi 的實體 |
|---|---|
| Content Pipeline 的完成閘門 | `tools/dashboard_check.py` exit 0 ＋ Step 6 本機同步 |
| Deployment Pipeline（Windows-only） | `github_push.sh`（容器內回 `DEPLOYMENT_NOT_AVAILABLE_IN_THIS_RUNTIME`，exit 3） |
| Deployment Evidence Gate | `tools/deploy_verify.sh`（0=VERIFIED／1=遠端落後／2=UNKNOWN） |
| 本專案的 artifact | `threads_wedding_ring_dashboard.html`＋`index.html` |
| 具名失敗狀態 | 見 Execution Boundary Standard 第三節；本專案不另定義 |

---

## 0. 開跑前護欄 — 互斥鎖（2026-09-07 改寫）

**第一個動作，先取鎖，不要先開瀏覽器。**

```bash
INSTANCE_ID=$(python tools/runlock.py acquire --task trumi_daily --note "cowork daily")
echo "exit=$?"        # 0 = 取得；4 = CONCURRENCY_BLOCKED
export TRUMI_INSTANCE_ID="$INSTANCE_ID"
```

| exit | 意思 | 該做什麼 |
|---|---|---|
| 0 | 取得鎖 | 往下跑，過程中每隔一段時間 `runlock.py heartbeat --instance "$TRUMI_INSTANCE_ID"` |
| 4 | `CONCURRENCY_BLOCKED` | **立刻結束**：不 discovery、不寫入 HTML、不派送。摘要只回報鎖的持有者與狀態 |

### ⛔ 沒有「手動補跑」例外（2026-09-07 事故的直接根因）

舊 Step 0 寫過「使用者手動要求補跑時才可忽略」。**這句話已刪除，不得復原。**

2026-09-07 的覆寫就是它造成的：使用者在既有 session 說「更新貼文」，
那個 session 正確引用了這條例外、放行、開始跑，同時排程又獨立啟動了另一個 instance。
那個 session **完全照規則走**——規則本身就是洞。

「手動要求」影響的是**今天該不該跑**；它不影響**能不能同時有兩個 writer**。
這是兩個不同的問題，舊規則把它們混成一個。

→ **手動補跑一樣要先取鎖。取不到就是 `CONCURRENCY_BLOCKED`，跟排程執行一視同仁。**
使用者要求補跑而鎖被佔住時，正確回應是告訴他誰在跑、跑多久了，
讓他決定要等、還是確認對方已死後 `release --force`——而不是繞過鎖。

**每完成一次授權寫入且驗證 PASS 之後，checkpoint 一次**（Step 08 health_check 之後）：

```bash
python tools/runlock.py checkpoint \
  --instance "$TRUMI_INSTANCE_ID" \
  --validated "dashboard_check:PASS exit0" \
  --expect "threads_wedding_ring_dashboard.html=<sha256前16碼>" \
  --expect "index.html=<sha256前16碼>" \
  --note "這次寫了什麼"
```

理由：fingerprint 是取鎖當下拍的，分不出「我自己剛剛合法寫的」和「別人偷偷寫的」。
不 checkpoint 的話 release 每次都會報 drift，久了就會被當雜訊忽略——**那等於把警報關掉**。

**但 checkpoint 自己是一條 trust boundary**，所以它不是「把現在的磁碟狀態當新基準」。
語意是**接受本次已驗證的合法變更**：

```
before_hash → authorized mutation → expected_after_hash → validation PASS
           → checkpoint(expected_after_hash)
```

四個條件缺一不可，任一不符即拒絕：

```
caller == current lock owner        （--instance，不接受匿名）
AND lock state == HELD
AND post-write validation == PASS   （--validated 提供證據）
AND 磁碟實際 hash == --expect 的 hash（逐檔比對）
```

若磁碟內容 ≠ 預期 hash，代表這段期間有第三方寫入 → 回 exit 4，**不吸收這次 drift**。
⛔ **不得為了讓 checkpoint 過而改用「重新掃描現況」**——那會把未授權修改一起洗白，
等於用一個修正把原本要防的東西放進來。

收尾（無論成功失敗）：

```bash
python tools/runlock.py release --instance "$TRUMI_INSTANCE_ID"
```

release 會拿取鎖當下的 fingerprint 跟現在比對。若期間來源檔被改動，
它會印 `WARN 鎖期間來源檔被改動（可能有鎖外 writer）`——**這是必須寫進摘要的事件**，
代表有 writer 沒有走鎖，鎖本身沒有涵蓋到它。

實作備註：這個工作資料夾是雲端掛載磁碟，`os.remove` 會回 `Operation not permitted`
（2026-09-07 實測）。所以鎖是**用檔案裡的 `state` 欄位**表示，不是用檔案存不存在表示；
released 是寫進去的，不是刪出來的。任何 delete-to-unlock 的改法在這裡都會壞掉。

### 排程清單（2026-09-07 查核，避免再次誤判）

| taskId | 排程 | 目標 artifact | 與本流程的關係 |
|---|---|---|---|
| `tru-mi-daily-threads-update` | 每日 09:00 | `threads_wedding_ring_dashboard.html` | **就是本流程** |
| `threads-home-deco-daily` | 每週一 09:09 | `chanel deco/index.html` | ChannelDeco 專案，**不同品牌不同檔案**，不衝突 |
| `threads-home-deco-daily-a-sweep` | 週二～日 09:00 | `chanel deco/index.html` | 同上，不衝突 |

⚠️ **不要再把 `threads-home-deco-daily` 當成「本儀表板的每週版」。** 它的名字裡有
`threads` 和 `daily`，很容易讓人誤判成同一條線；它其實是居家裝修品牌，寫的是另一份檔案。
本儀表板目前**沒有**每週版排程。若日後真的新增，優先權規則寫在這裡，並且一樣走同一把鎖。

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
| `tools/deploy_verify.sh` | **Deployment Evidence Gate**：比對本機與 GitHub remote |
| `github_push.sh` | 上傳（**Windows-only**；容器內不執行，嚴禁印出 token） |
| `repo_sync_docs.sh` | 規格文件同步（**Windows-only**；容器內不執行） |

> 兩支 deploy 腳本可以改「runtime 偵測與回報語意」，
> 但**不得**為了讓容器能 push 而加裝憑證、token 檔或硬編 `gh` 路徑（見 Execution Boundary Standard Rule ①②）。

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

### 1.9 Discovery degraded-mode trigger

> **規則本體見 `000_Agent/knowledge/EXECUTION-BOUNDARY-STANDARD.md` 第四節。**
> 本節只寫 Tru-Mi 的 surface 對照，不重述觸發條件、重試策略與狀態記法。

節流對策（上一節）處理的是「回傳量變少」。**endpoint 整個掛掉是另一回事**，
不該用擴大關鍵字去解——那時瓶頸已是 endpoint availability，不是 query coverage。

本專案的三個獨立 discovery surface：

| # | Surface | Tru-Mi 探測點 |
|---|---|---|
| A | Search | `/search?q=婚戒` |
| B | Hashtag | `/tag/婚戒` |
| C | Profile Replies | `/@trumi_jewelryofficial/replies` |

首頁基準點：`https://www.threads.net/`（用來區分平台端異常與登入失效）。

DEGRADED 當日的本專案收尾：跳過 Step 3～5 的卡片作業，
依 Step 2 的無新貼文路徑在 `panel-strategy` 加註失敗原因與實際重試過程，
仍執行 Step 5.9 之後的完整收尾。

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
4. 非推銷式留言草稿（**A/B/C 才寫**，不放連結、不自薦、不批評同業。
   語氣與長度規則見 **4.4 Jessica 回覆語氣**，不再沿用「2-4 句公關式回覆」的舊寫法）
5. Threads 延伸貼文草稿（設計師第一人稱 100-200 字，結尾固定
   「完整故事看 IG @trumi_jewelryofficial」）
6. 跨平台延伸（IG／Reels／限動／LINE 官網；Reels 公式依焦慮類型交錯選，
   勿每篇都用「迷思破解 B」）
7. 漏斗更新
8. 追蹤動作

**禁用詞**：高CP值、物超所值、划算、優惠、限時。留言先回答問題，不先證明品牌厲害。

### 4.3 文字產出流程（2026-09-11 定版｜留言與延伸貼文都適用）

```
生文
 → human write 檢查      通用 AI 痕跡
 → 大眾語氣檢查          這句中文成不成立
 → Jessica 語氣檢查      逐句比對語氣資料庫（最大幅度重寫）
 → 大眾語氣複檢          ⭐ 改寫可能生出新的不通順
 → 正式確認
```

**順序不可對調。** 「四、非推銷式留言草稿」與「五、Threads 延伸貼文草稿」
兩者都要走完整流程。

三個檢查層問的是**三個不同的問題**，不可互相取代：

```
human write    有沒有 AI 痕跡？          通用 AI 標記掃描
大眾語氣       這句中文「成不成立」？     比對真人語料＋中文語感
Jessica 語氣   這是不是「她」會說的話？   逐句比對 jessica-voice-samples.md
```

#### 為什麼是這個順序（2026-09-11 定版，兩次調整）

**① `human write` 不放最後** —— 它是**通用**工具，不認識 Jessica。
放最後會把她的特徵當成問題砍掉：`！！` 連用、`欸／呢／唷`、句尾 emoji，
在通用標準裡都像「過度口語」。**通用工具不該對一個人的聲音下最後判斷。**

**② `Jessica 語氣` 放倒數第二，後面接複檢** ——
它負責最大幅度的重寫（句型、結構、斷行），而**跑最後的那一關，
它自己的產出沒有人檢查**。
2026-09-11 實例：最後三個錯誤（`保固保鬆掉`、`比款式更決定`、`多半`）
全部是在 Jessica 改寫階段自己產生的，連續被退三次。

**③ 複檢只跑大眾語氣，不重跑 human write** ——
避免最後一步又把她的語氣特徵洗掉。

#### ① 生文
依 §4.9 Listener Analysis 判斷對方需要什麼，再依 §4.4／§4.7 產出初稿。

#### ② human write 檢查（`speak-human-tw`）
通用 AI 痕跡：破折號密度、中國用語、半形標點、emoji 數量、
「不是 A 而是 B」句型、罐頭收尾、對話殘留。

#### ③ 大眾語氣檢查
見下方 §「大眾語氣檢查」的四項。

#### ④ Jessica 語氣檢查（**比對語氣資料庫**）

> ⚠️ **這一關指的是逐句比對 `references/jessica-voice-samples.md` 的真實樣本，
> 不是套用 `jessica-voice.md` 的規則。**
> 規則是我對樣本的詮釋，會漂移；樣本是正本。衝突時以樣本為準。

```
逐句問：這個句型，在 S-001～S-005 裡找得到對應嗎？

找得到              → ✅ 標註對應哪一筆
找不到但是白話       → ⚠️ 標記「無樣本對應」，交人工判斷，不得自行放行
找不到又是「寫出來的」 → ⛔ 砍掉重寫
```

**交付時要附對應表**，列出每個句型對應哪一筆樣本、哪些無對應。
沒有對應表就不算跑過這一關——2026-09-11 的三次退件，
前兩次都是「宣稱通過」但沒有逐句對應。

`jessica-voice.md` 可當**查詢捷徑**（§4.2 動作句／§7.0 結構／§4.2.2 禁用詞），
但 ⛔ **不得因為「規則沒有禁止」就放行**——禁用清單只收錄已經犯過的錯，
必然不完整（`多半` 就是第四個被抓到、而清單原本沒列的詞）。

#### ⑤ 大眾語氣複檢

只重跑 §③ 的四項，**不重跑 human write**。
理由：Jessica 改寫階段最容易生出新的不通順，而通用工具在最後一步
會洗掉她的語氣特徵。

**⛔ 防循環條款（2026-09-11 修正）**

```
Jessica 語氣檢查允許大幅重寫。

大幅重寫後：
→ 只重新執行「大眾語氣複檢」
→ 不重新進入 Jessica 語氣檢查
→ 避免 Jessica 改寫 → 大眾修正 → Jessica 再改的無限循環

大眾語氣複檢發現不自然時：
→ 只做最小必要修正
→ 不因純文字順暢度重新啟動整套流程
```

**只有下列五種情況才停止並要求確認：**

```
1. 修正會改變原始事實
2. 修正會改變專業判斷或必要專業資訊
3. Evidence Gate 無法判定
4. 現有 Jessica Voice 證據不足，必須替 Jessica 創造新的說話方式
5. 出現既有 canonical 無法處理的新規則衝突
```

**⛔ 以下情況不得因「改很多」而停止：**

```
拆除 AI 模板｜移除情緒鏡頭｜移除金句與對仗｜調整句型與文章結構
改成 Jessica 已有證據支持的說法｜保留原專業內容只重寫敘事外殼
```

> **重寫幅度 ≠ 決策風險。**
> 是否需要停下來，以「**是否跨越既有證據與決策邊界**」判斷，不以改動大小判斷。
>
> 這條 2026-09-11 修過一次：初版寫成「實質改變就停下來問」，
> 那會讓 229 張卡的盤點碰到每篇大改都卡住，形成另一種流程阻塞。

#### ⚠️ 兩條防模板規則（2026-09-11 新增，都是實際犯過才補的）

**A. marker 不是禁詞**

```
其實／倒是／通常／多半／破折號  ← 這些是 marker，不是禁詞

marker 的作用：把這一則送進檢查
不是：全域字元替換

該詞在當句確實有語意功能且自然 → 保留
沒有溝通功能、純粹是承接慣性     → 刪掉
```

破折號同理，依 Human Write canonical 逐則判斷，**不得做全域取代**。

**三個統計必須分開，不可互相代表**：

```
marker 命中數  ≠  待檢則數  ≠  實際修改則數
```

**B. 不得把修正變成新模板**

`§4.7.2`「Threads 是對話串的開頭」的意思是**留下互動空間**，
**不等於每篇都要用問句結尾**。

> 2026-09-11 實例：P1 六則重寫時，全部收在問句，其中兩則的問句形狀
> 幾乎一樣。這是把「AI 金句模板」換成「AI 問句模板」，問題沒有解決，只是換了外衣。

```
結尾依每篇內容判斷：
自然陳述 ／ 留白 ／ 問句  都可以

⛔ 同一批產出若結尾形狀高度一致，即使每則單看都合格，也算模板化
```

**通則**：任何修正手法如果在一批產出中重複出現，就要回頭檢查它是不是變成新模板。

#### ⑥ 正式確認

前四關全部 PASS 才可標記為正式可用版本：

```
Human Write PASS
大眾語氣 PASS
Jessica Voice PASS
大眾語氣複檢 PASS
Evidence / Fact 沒有因改寫遭破壞
```

未通過不得進入正式發布／回覆版本。

#### ③ 大眾通用語氣檢查（2026-09-11 新增）

> **為什麼需要獨立一層**：2026-09-11 連續三次漏判**全部通過了 Jessica 語氣檢查**，
> 因為它們「像她的風格」——短句、動作導向、不自誇。
> 但它們**不是中文**。Jessica 檢查比對的是 5 筆樣本，樣本裡沒有、
> 看起來又不突兀的說法就會放行。這一層補那個洞。

逐句問：**一般人會不會這樣說？這句中文成不成立？**

| 檢查 | 實際漏判案例 |
|---|---|
| **搭配詞成不成立** | ❌「保固大多只**保鬆掉**變形」——`保固` 是名詞，再拿 `保` 當動詞形成 `保固保⋯` 疊字；`保鬆掉` 是把動詞當名詞用 |
| **語法有沒有硬凹** | ❌「戴不住**這件事它**保不到」——為了讓主語對齊硬塞，念出來就卡 |
| **是不是發明的說法** | ❌「儀式感不用**靠石頭撐**」——語料庫 grep 零同類表達 |
| **動詞名詞化** | ❌「降低摩擦與**拔的疼痛感**」——改「比較不痛」 |

**比對語料**：儀表板的 229 則 `.post-content` ＋ 全部 `.comment-text`
（方法見 `jessica-voice.md` §4.1）。

**最實用的一招：把句子唸出來。** 念到卡住的地方就是問題所在。
這三次漏判全部念一次就聽得出來。

#### ④ human write 檢查（`speak-human-tw`）
殘留的通用 AI 痕跡：破折號密度、中國用語、半形標點、emoji 數量、
「不是 A 而是 B」句型、罐頭收尾。**這一關是補掃，不是主檢查。**

#### ⑤ 正式確認
人工過目後才寫入儀表板。**AI 不得自行判定通過。**

---

⚠️ **這套流程是 2026-09-11 才補齊的，而且是被實際漏判逼出來的。**
同一段文字連續改了三次都沒過，前兩次都在換用詞，第三次才發現根因是句型。
漏判紀錄見 `jessica-voice-samples.md` N-005、N-006。

**在此之前寫入儀表板的 229 張卡，其留言與延伸貼文都沒有走過這套流程。**
既有內容的處理範圍見 `references/ia-migration-plan.md`。

### 4.4 Jessica 回覆語氣（2026-09-11 新增，取代舊的「語氣：溫暖真實克制」一行）

> 舊規則只寫了「溫暖真實克制、用生活語言」，結果產出的留言雖然沒有廣告味，
> 卻普遍**過於工整**——起承轉合完整、每句都在給結論，讀起來像一份寫得很好的公關回覆，
> 而不像 Jessica 本人在 Threads 上跟人講話。這一節就是修這件事。

**核心指令**

```
Jessica 用自己的口氣，像跟朋友聊天一樣回覆對方；
在聊天過程中，自然讓人感受到 Tru-Mi 對人的故事、感情、婚戒與設計的看法。
```

優先順序，不可對調：

```
先像 Jessica，再像 Tru-Mi
先像聊天，再像內容
先讓人知道 Jessica 怎麼想，再考慮品牌曝光
```

Jessica 的核心能力是「**把人的故事轉譯成可以被戴在身上的設計**」。
這項能力可以自然出現在合適的議題中，但**禁止每則留言都硬帶回婚戒**。

> ⚠️ **本節（4.4）與 4.7 是兩個模組，不共用生成邏輯。**
> 「四、留言」是**下一句建議器**——判斷 Jessica 現在最自然的下一句是什麼。
> 「五、延伸貼文」是**專業內容產出器**——把互動累積出來的題目轉成她的觀點。
> 兩者若共用同一套 prompt，留言就會被寫成小型文案，越寫越完整、越像 AI。
> 詳見 **4.8 Conversation Loop**。

#### 4.4.0 留言有兩種，長度差一個量級（2026-09-11 依真實樣本校準）

初版只訂了一種長度（「2-4 句」），並用海巡的長度去要求所有留言。**那是錯的。**

| 型別 | 對象 | 真實樣本 | 長度 | 目的 |
|---|---|---|---|---|
| **社群互動** | 回自己貼文下的留言者 | 「肥皂洗手是好方法欸！」 | **5-15 字** | 接住對方，把話留在場上 |
| **海巡留言** | 陌生人的貼文 | 「婚戒設計師路過⋯⋯」那則 | **80-100 字** | 先自我定位，再給觀點 |

⛔ **不得因為內容太短就自動補專業知識、品牌資訊或 CTA。**
「肥皂洗手是好方法欸！」沒有 Tru-Mi、沒有婚戒、沒有專業知識、沒有導購，
但它是**正確的品牌行為**——願意像朋友一樣聊，本身就在累積 Jessica 這個人的品牌感。

#### 4.4.1 產生順序（禁止倒過來）

```
原 Threads 在聊什麼
  ↓ Jessica 對這件事有沒有真實可成立的觀察
  ↓ Jessica 如果跟朋友聊天會怎麼接這句話
  ↓ 有沒有適合加入設計師視角
  ↓ 有沒有自然帶出品牌價值的機會
  ↓ 最後才判斷是否值得延伸到婚戒／客製設計
```

⛔ **不得倒過來**：「我要曝光 Tru-Mi」→ 找角度塞婚戒 → 寫一個看似自然的留言。
倒過來寫出來的東西，第 7 項檢查一定過不了。

#### 4.4.2 議題距離決定品牌濃度（不是每則都一樣濃）

| 距離 | 範圍 | 品牌濃度 | 標記 |
|---|---|---|---|
| **A 直接相關** | 婚戒／求婚／戒指／客製珠寶／挑戒指 | 可明確加入設計師觀察與婚戒設計思考，但**仍先回應對方，再談自己的經驗** | 💍 設計師視角 |
| **B 間接相關** | 感情／伴侶／結婚／共同生活／紀念日／送禮 | 可加入對關係、故事、紀念方式的觀察，**不必硬提戒指** | 🤍 關係／故事視角 |
| **C 弱相關** | 日常生活／熱門話題／一般聊天 | 以「Jessica 這個人」參與即可；除非存在自然連結，**不要提 Tru-Mi、珠寶、婚戒** | 👤 Jessica 視角 |

**品牌存在感不等於品牌名稱出現率。** 回覆不需要刻意提到「Tru-Mi」。

應該透過 Jessica 的觀察與回應，自然呈現：重視每個人的故事｜願意先聽而不是急著給答案｜
注意關係裡的小細節｜能把抽象的感情與象徵轉譯成具體設計｜有專業判斷但不賣弄術語｜
溫暖有審美但不刻意煽情｜故事優先於規格｜陪伴與理解優先於銷售。

#### 4.4.3 寫法

**要短、自然、有明確觀點**，讓 Jessica 一眼判斷要不要用、可以直接微調成自己的話。
不必每次完整鋪陳起承轉合——儀表板是**協助** Jessica 回覆，不是代替她扮演一個虛構人格。

可以用自然口語：「我也會耶」「其實我覺得⋯⋯」「看到這個我第一個想到的是⋯⋯」
「這個真的很有感」「我反而會好奇⋯⋯」「結果最後反而是⋯⋯」「你們會這樣嗎？」
「我做設計的時候也常遇到這種狀況」。
但**不要為了模仿口語而大量塞語助詞**——那會變成另一種假。

⛔ 禁止產生：官方客服語氣｜品牌小編語氣｜廣告文案｜過度完整工整的公關式回覆｜
心靈雞湯｜文青式感性金句｜為了品牌曝光硬轉婚戒｜
「每一段愛情都值得⋯⋯」這類泛用珠寶品牌句型。

#### 4.4.4 素材不足時不得捏造

缺少 Jessica 本人的真實經驗、感受或立場時，**不得自行產生**類似
「之前有一對客人也是這樣⋯⋯」的內容，除非知識庫／素材庫真的有那個案例。

資料不足時，該欄位寫：

```
這題適合 Jessica 補一個自己的經驗再回。
```

而不是生成假的品牌故事。（同 4.5 素材四格、CLAUDE.md NEVER #1 的精神。）

#### 4.4.5 Brand Voice Gate（每則留言草稿定稿前逐項檢查）

| # | 檢查 | 核心 |
|---|---|---|
| 1 | Jessica 平常真的講得出口嗎？ | ✅ 核心 |
| 2 | 像朋友聊天，還是像品牌小編？ | ✅ 核心 |
| 3 | 有沒有自己的觀察／反應，而不是泛泛附和？ | ✅ 核心 |
| 4 | 如果帶到品牌，轉折是否自然？ | |
| 5 | 有沒有為了曝光而硬塞婚戒？ | ✅ 核心 |
| 6 | 有沒有捏造 Jessica、客戶或 Tru-Mi 未經確認的經驗？ | ✅ 核心 |
| 7 | 拿掉品牌名稱後，這句話本身還值得回嗎？ | ✅ 核心 |

**任一核心項目不通過就重新生成**，不要在原句上修修補補——
公關腔通常是結構問題，不是用詞問題。

#### 4.4.6 不被本節覆蓋的既有規則

本節只改語氣與生成順序，下列規則**維持不變**：
不放外部連結｜不放 hashtag｜不用價格吸引互動｜不使用稀缺性｜不硬銷｜
CTA 與互動優先採自然問句｜真實資訊優先於品牌感｜不因為需要產生內容而自行補造素材｜
未經另一當事人同意的私人故事不擴大使用｜風險類不留言不自薦只觀察｜
D 級不寫留言草稿。

「五、Threads 延伸貼文草稿」的語氣規則見 **4.7**（2026-09-11 修訂，取代本節原本
「延伸貼文不套用品牌語氣」的寫法——那條界線畫錯了，見 4.7 開頭說明）。

### 4.7 Threads 延伸貼文草稿的品牌語氣（2026-09-11 新增）

> **這一節是在修 4.4.6 的一個錯誤。** 4.4 初版把「品牌口吻」與「朋友聊天感」綁成一組，
> 然後因為發文不是聊天，就把延伸貼文整個排除在品牌語氣之外。
> 那是把兩件事混為一談：**聊天感是情境限定的，品牌口吻不是。**
> 結果就是留言變得像 Jessica，發文還是像品牌文案——同一個人在同一個平台上有兩種人格。

**拆開來看**：

| | 留言（四） | 延伸貼文（五） |
|---|---|---|
| Tru-Mi 品牌口吻 | ✅ 適用 | ✅ **同樣適用** |
| 朋友聊天感（接話、問回去） | ✅ 適用 | ✅ **同樣適用**（2026-09-11 修正，見 4.7.2） |
| 長度與格式 | 短、可不完整 | 第一人稱 100-200 字＋固定結尾 |
| 對象 | 一個具體的人 | 一群還不認識 Jessica 的人 |

#### 4.7.1 品牌口吻在發文裡怎麼落地

4.4.2 那八條品牌特質**原封不動適用**：重視每個人的故事｜願意先聽而不是急著給答案｜
注意關係裡的小細節｜把抽象的感情與象徵轉譯成具體設計｜有專業判斷但不賣弄術語｜
溫暖有審美但不刻意煽情｜**故事優先於規格**｜陪伴與理解優先於銷售。

發文特有的三條落地方式：

1. **從一個具體的人開始，不從一個道理開始。**
   ✅「今天看到一則貼文，她說⋯⋯」　❌「很多人以為婚戒就是⋯⋯」
   後者是文案的開場，前者是 Jessica 的開場。
2. **專業判斷要掛在使用情境上，不要單獨陳列規格。**
   ✅「太薄的戒圈久了會壓手，人就會把它摘下來放著，所以我一定做到 1.8mm」
   ❌「我們堅持 1.8mm 厚度底線與內弧圓角設計」
   同一個事實，後者是型錄，前者是理由。
3. **結尾收在一個判斷，不收在一個金句。**
   ✅「先想清楚哪一隻要陪你過日子，預算怎麼分就會自己浮出來」
   ❌「每一對戒指，都值得被好好對待」

#### 4.7.2 聊天感同樣適用（2026-09-11 修正）

> 初版寫「發文不做反問收尾，那是留言的 CTA，用在發文會變成假互動」。**這是錯的，已刪除。**
> 那條規則把 Threads 當成 IG 貼文或部落格在管——**Threads 的貼文本質就是對話串的開頭，
> 不是廣播**。在 Threads 上發一則沒有人可以接話的文，才是真的不自然。

所以 4.4.3 的聊天感規則**在延伸貼文裡照樣適用**，包含：

- 自然口語與轉折：「我看了有點在意」「說實話我自己也⋯⋯」「後來才發現」「結果最後反而是⋯⋯」
- **反問收尾可用**：「你們會這樣嗎？」「你平常會⋯⋯嗎？」
  這在 Threads 不是假互動，是把貼文留成一個開口。
- 不必每次都把話講完、講滿，可以停在還沒想清楚的地方

唯一保留的差別只有**對象**：留言是回一個具體的人，發文是對一群還不認識 Jessica 的人開場，
所以第一句要能讓不知道前情的人接得上（見 4.7.1 第 1 條）。
除此之外，**不要因為它是「發文」就把語氣調正式**。

仍然禁止的是**假的互動感**，不是互動本身：
不要用「留言告訴我」「+1 讓我知道」這種為了衝互動而問的問題——
問句要是 Jessica 真的好奇的事，不是為了觸發演算法。

#### 4.7.3 發文的 Voice Gate（在 4.4.5 七項之外另加三項）

| # | 檢查 |
|---|---|
| 8 | 第一句是從一個具體的人／情境開始，還是從一個道理開始？ |
| 9 | 有沒有出現型錄句（規格單獨陳列、沒有掛使用情境）？ |
| 10 | 結尾是判斷還是金句？出現「值得」「都應該」「每一段」就重寫 |

第 4.4.5 的七項**同樣要過**，其中第 6 項（不得捏造 Jessica／客戶／品牌未經確認的經驗）
在發文裡更嚴格——留言講錯只有一個人看到，發文講錯是對外宣稱。

#### 4.7.4 不變的部分

第一人稱、100-200 字、結尾固定「完整故事看 IG @trumi_jewelryofficial」、
素材四格（4.5）、去 AI 味終檢（4.6）、禁用詞、不放連結、不放 hashtag——全部維持。
本節只改語氣，不改格式與素材紀律。

---

## 4.8 Conversation Loop（2026-09-11 新增｜依 09-06～09-07 真實互動校準）

> **這一節的地位跟前面幾節不同。** 4.4／4.7 是從規則推論出來的，
> 4.8 是**有完整行為鏈證據**的：真實發文 → 網友留言 → Jessica 回覆 → 網友追問 →
> 行銷顧問即時指導 → Jessica 採用。所以它**優先於 4.4 的任何語氣描述**。

### Evidence（本節的全部依據，不得憑推論擴充）

```
網友：  用乳液
Jessica：好方法呢！！
網友：  有成功嗎？
Bevis： 不用，就是繼續跟他聊～ / 你試試看之類的
Jessica：肥皂洗手是好方法欸！
Bevis： 可以唷！/ 真的就把它當作朋友聊天就好
```

### 4.8.1 Conversation Loop 優先於 Answer Completion

Threads 回覆的成功標準**不是「有沒有完整回答」**。

網友問「有成功嗎？」時，AI 的直覺是去找答案、把結果交代完。
Bevis 的實際指導是相反的：不用回答，繼續聊。

> ⚠️ **2026-09-11 降級修正。** 本節初版把這條寫成「Threads interaction 的上位原則」，
> 那是**從單一情境升格出來的過度概括**——Bevis 那句指導成立，是因為當時對方只是在閒聊追問，
> 不是真的需要一個答案。把它擴大成「Threads 一律不要直接回答」會直接傷到真正在求助的人。
>
> **真正的上位原則是 4.9 Listener Analysis：先聽懂對方 → 判斷他此刻需要什麼
> → 再決定是接住、問、聊，還是回答。**
> 「不要急著把話講完」的正確意思是**「不要提供超過對方此刻需要的內容」**，
> 而不是「不要回答問題」。對方真的在問問題時，就該回答。

生成回覆前先問四題：

```
1. 對方現在丟了什麼球？
2. Jessica 需要回答嗎？
3. 還是只需要接住這句？
4. 回完之後，對方還有沒有自然繼續聊的空間？
```

⛔ **不要因為 AI 知道答案，就自動把資訊補完。**

### 4.8.2 「朋友聊天」是對話策略，不是語氣修飾

**禁止**把「正式文字改成口語文字」就判定符合 Jessica Voice。

錯的流程：`正式文案 → 改口語`
對的流程：`對方丟了什麼球 → Jessica 最自然會接哪一球 → 接完要不要停`

**允許最佳建議只有一句。** 例：「肥皂洗手是好方法欸！」

### 4.8.3 品牌露出不是每則留言的必要條件

社群互動留言可以完全不提 Tru-Mi、不提婚戒、不自稱設計師、不給專業知識、
不導購、不加 CTA。**只要 Jessica 真實地參與對話，就成立。**

```
品牌口吻 ≠ 每則留言都必須出現品牌資訊
```

Brand Voice 的判斷要包含「Jessica 如何跟人互動」，
**不能只檢查品牌關鍵字或專業資訊有沒有出現**。

### 4.8.4 對話狀態 A–E（先判狀態，再生成）

| 狀態 | 情境 | Jessica 該做什麼 |
|---|---|---|
| **A 開話題** | 主動丟事件或問題 | 先聽大家說，不預先給答案 |
| **B 接球** | 對方提供經驗或方法 | **優先短回應，不重述、不總結** |
| **C 續聊** | 對方再追問或補充 | 判斷值不值得把球留在場上，**不急著結案** |
| **D 專業補充** | 情境累積足夠 | 這時才加入真正有價值的設計師判斷 |
| **E 內容延伸** | 留言區產生足夠真實問題 | 才判斷值不值得形成後續 Threads 題材 |

⛔ **不要預設每次都從 A 直接跳到 D。** 那正是 AI 最容易犯的錯：
一看到有專業可講就立刻講完。

### 4.8.5 「不要替對話結案」檢查

回覆產生後再問一次：

```
這句是在接話，還是在替這段對話做總結？
```

一般社群互動場合若出現以下任一項，**回頭重判是否過度完成**：

完整答案｜三點建議｜知識補充｜品牌結論｜感謝＋總結｜CTA

### 4.8.6 Jessica Voice Reference（真實語料）

> **2026-09-11 relocation：語料本體已移出本檔。**
> 理由：真實樣本會持續增加，留在 SOP 會讓每次新增樣本都變更 SOP。
> 這一輪只搬移，未改寫任何內容。

| 要什麼 | 去哪裡 |
|---|---|
| 真實原句、情境、日期、外部確認、AI 寫偏反例 | **`references/jessica-voice-samples.md`** |
| 從樣本歸納出的穩定 Voice Rule、Rule Generalization Gate | **`references/jessica-voice.md`** |

⚠️ **樣本不因新增就自動升格為規則**，升格須通過
`jessica-voice.md` §0 Rule Generalization Gate。

⚠️ 真實樣本**不是要求機械模仿**。不得規定每句都要用
「欸／呢／唷／～～～／！！／emoji」。要學的是**互動節奏與自然程度**，
不是複製表面語助詞——照抄語助詞會產生另一種假。

### 4.8.7 發文策略：「先聊、後整理」（選項，非強制）

「戒指拔不出來」這個案例顯示一種已被實際使用、且適合 Jessica 的模式：

```
真實事件 → Jessica 開話題 → 網友分享方法／經驗
        → Jessica 短回覆 → 持續互動
        → 再由 Jessica 補充事後建議／設計師觀點
```

而**不是**：`我有專業知識 → 寫成完整教學 → 發布 → CTA`。

這跟 Tru-Mi「先聽故事，再進入設計」的品牌邏輯高度一致。
遇到適合的題目時可以建議「**先開話題，不急著一次寫完整**」，
但**只能是內容策略選項，不得強迫所有 Threads 都採此模式**。

### 4.8.8 最終驗收原則

儀表板不該問：

```
❌ 怎樣讓 Jessica 的留言更完整？
✅ Jessica 現在最自然的下一句是什麼？
```

**如果答案只有 6 個字，就只給 6 個字。**
但「最自然的下一句」是 **4.9 聽懂之後**才知道的事，不是先射箭再畫靶。

---

## 4.9 Listener Analysis｜先分析「人」，再產生「話」（本章最上位）

> **這一節優先於 4.4、4.7、4.8 的所有規則。**
> 4.8 給的是互動策略，但策略選錯對象就會傷人：
> 把求助的人當成閒聊、把閒聊的人當成客戶，兩種都是沒在聽。

```
「像朋友聊天」是輸出方式
「理解留言者」才是回覆生成的前置工作
```

**先聽懂，再回話。** 朋友聊天不是隨口講一句很口語的話，
而是**有在聽對方說什麼，才知道下一句該怎麼接**。

### 4.9.1 每則留言先做 Listener Analysis（系統內部，不一定輸出）

```
1. 他表面上說了什麼？
2. 他真正想表達的重點是什麼？
3. 他現在比較像是在：
   分享經驗／提供方法／求助／詢問專業問題／表達擔心害怕／
   認同 Jessica／提出不同看法／開玩笑閒聊／想知道後續／其他
4. 他現在最需要的是什麼？
   被聽見／被理解／Jessica 接著聊／一個答案／專業資訊／
   澄清／安心／進一步詢問他的情況
5. 上面哪一部分只是推測？
```

⛔ **不得把推測當成留言者的真實意圖。**
資訊不足時只能寫「可能是在⋯⋯」，**不能腦補對方的心理**。

### 4.9.2 再決定回應策略（分析完才選）

| 策略 | 什麼時候用 | Jessica 做什麼 |
|---|---|---|
| **A 接住** | 對方只是在分享經驗 | 不要教他，先回應他的分享 |
| **B 傾聽／追問** | 對方透露了值得了解的情況 | 問一個**真的有助於理解他**的問題 |
| **C 共聊** | 對方在聊天、提供方法、分享生活 | 像朋友接話，不必轉專業 |
| **D 回答** | 對方真的提出需要答案的問題 | **回答他真正問的事**，不要為了互動而不回答 |
| **E 專業補充** | 需求確實需要珠寶設計師判斷 | 才加入專業 |
| **F 先確認** | 資訊不足，直接答可能會答錯 | 先問清楚，不自行假設 |

### 4.9.3 不要把每個留言者都當成潛在客戶

分析需求是為了**更好地理解與互動**，不是判斷「怎麼把他轉成婚戒客戶」。

```
❌ 留言 → 潛在客戶 → 導向 Tru-Mi
✅ 留言 → 理解這個人現在在說什麼 → Jessica 真實回應
        → 關係自然延續 → 有需求時才進一步提供資訊
```

### 4.9.4 儀表板顯示格式（三層，不要寫成心理分析報告）

每則留言**不要**只顯示「建議 Jessica 回覆：XXXX」，改成：

```
【他在說什麼】   一句話整理留言者目前真正的重點
【建議怎麼接】   接住／追問／共聊／回答／專業補充／先確認
【Jessica 可以怎麼回】  給 1 個最自然的下一句
```

前兩層的目的只是讓 Jessica 一眼知道「AI 為什麼建議我這樣回」，**不是要她讀報告**。

### 4.9.5 範例

**留言：「肥皂或是乳液🥺」**

❌ 錯誤分析：「對方需要戒指卡住的專業解決方案。」——留言內容支撐不了這個結論。

```
【他在說什麼】 在分享自己知道的處理方法，也是在參與 Jessica 的話題
【建議怎麼接】 接住／共聊
【Jessica 可以怎麼回】 肥皂洗手是好方法欸！
```
不需要額外補珠寶知識。

**留言：「我的也是一直卡在關節，每次拔都超痛，有時候手還會腫起來🥲」**

❌ 不能只套一句「真的很驚險欸！」——他不是在提供方法，是在講自己長期的實際困擾。

```
【他在說什麼】 自己的戒指也常卡關節，已經造成疼痛與腫脹
【建議怎麼接】 先傾聽／了解情況，不急著導向 Tru-Mi
【Jessica 可以怎麼回】 依 Jessica 真實語氣產生一句自然追問
```
若牽涉戒圍調整、身體狀況或其他專業判斷，**要有足夠資訊後再回答，不自行診斷**。

### 4.9.6 生成流程（定版）

```
留言原文
  ↓ 理解對方說了什麼
  ↓ 區分「明確資訊」與「AI 推測」
  ↓ 判斷對方此刻的需求
  ↓ 選擇互動策略（4.9.2 A-F）
  ↓ 套 Jessica Voice Reference（4.8.6）
  ↓ 判斷是否需要設計師專業
  ↓ 產生「最自然的下一句」
  ↓ 檢查：過度回答？過度推銷？過度腦補？
```

---

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
- 必帶 `data-keywords="關鍵字1 關鍵字2"`
  → 目的是**補召回**不是防退化；`cardMatchesKw()` 的實作行為與有效補法
  見 **`references/dashboard-spec.md` §8.4**（2026-09-11 relocation，內容未改寫）。
  重點一句：**不要為了衝覆蓋率補與原文重複的詞，那對搜尋結果零影響。**
- 必帶 `<div class="post-date">YYYY-MM-DD</div>`，**零位補齊**（`2026-03-10` 不是 `2026-3-10`）
- **必帶** `data-collected="YYYY-MM-DD"`（今天的日期）——卡片汰舊的唯一依據，
  也是 P1 schema 驗證的開關（`dashboard_check.py` 靠它判斷要不要驗新欄位）
- 內文用「jessica-insight 八段抽屜」完整格式（📊二/🔍三/💬四/📝五/🔀六/🔧七/📌八）

#### P1 schema — 2026-09-12 起的新卡必帶（2026-09-11 新增）

> 規格正本：`references/dashboard-spec.md` §8。
> **只適用新卡**，既有 229 張舊卡採 forward-only 不回填
> （`ia-migration-plan.md` 決策 A）。

**卡片屬性再加三個**

```html
data-topic="婚戒|戒圍佩戴|客製設計|感情婚姻|籌備婚禮|新發現|待分類"
data-convo="active|inactive|none"
data-convo-last="YYYY-MM-DD"     <!-- 有對話才需要 -->
```

⛔ 證據不足時 `data-topic` 一律填 **`待分類`**。硬分類比留空更糟。

**`comments-section` 內新增三個區塊，順序固定**

```html
<div class="key-comments" data-count="3" data-short-reason="僅 3 則具代表性">
  <div class="key-comment"
       data-intent-primary="分享方法"
       data-intent-signals="自身經驗 想知道後續">
    <div class="kc-text">留言原文</div>
    <div class="kc-sum">一句摘要</div>
    <div class="kc-next">Jessica 可以怎麼回</div>
  </div>
</div>

<div class="listener-analysis">
  <b>他在說什麼</b>：一句話<br>
  <b>建議怎麼接</b>：接住／追問／共聊／回答／專業補充／先確認<br>
  <b>可以怎麼回</b>：最自然的下一句
</div>

<div class="convo-thread">…有對話往返才需要…</div>

<div class="selection-evidence">
  <div data-picked="yes">#12｜高互動＋不同方法｜代表「處理方式」</div>
  <div data-picked="no">#03｜高讚但與 #12 高度重複</div>
</div>
```

**健檢會擋的八件事**（`dashboard_check.py` §4.5）

| # | 驗什麼 | 級別 |
|---|---|---|
| 1 | `data-topic` 存在且值合法 | FAIL |
| 2 | `.key-comment` 數量 **1–5**（0 不行，>5 也不行） | FAIL |
| 3 | `data-count` 與實際則數相符 | FAIL |
| 4 | 每則帶合法 `data-intent-primary` | FAIL |
| 5 | `.listener-analysis` 三層齊全 | FAIL |
| 6 | 少於 5 則時必須填 `data-short-reason` | WARN |
| 7 | `selection-evidence` 的 `data-picked="yes"` 筆數 == `data-count` | FAIL |
| 8 | 有 `.convo-thread` 時 `data-convo` 不得為 `none` | FAIL |

⚠️ **第 2 與第 6 條是一組**：關鍵留言**不是固定五則**。
只有 2–3 則真正有代表性就寫 2–3 則，但要在 `data-short-reason` 說明為什麼。
⛔ 不得為了填滿而補低價值、重複或無關的留言（`dashboard-spec.md` §3.3）。

⚠️ `data-intent-signals` 與 `data-intent-uncertainty` **刻意不驗完整性**——
一則留言可以只有一種意圖，強制填會逼 AI 虛構。

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

健檢 PASS ＋ 本機同步完成 = **`CONTENT_COMPLETE`**。容器端的職責到此為止。

## Step 6.5：推送（**Windows-only，容器不執行**）

### ⚠️ Windows 端的實際呼叫方式 → 見 Runbook

> **2026-09-11 relocation：操作細節已移出本檔，內容未改寫。**
> Canonical owner：**`references/runbook-windows-deploy.md`**

必須知道的一句：**Windows 上 PATH 的 `bash` 指向 `wsl.exe`，不是 Git Bash。**
直接打 `bash github_push.sh` 會讓腳本**根本沒有被執行**，而且
**不回任何表定的 exit code**——不是 `OK`、不是 `FAIL`、也不是
`DEPLOYMENT_NOT_AVAILABLE_IN_THIS_RUNTIME`。
記成「推送失敗」會誤導，正確判讀是 **interpreter 選錯，不是部署失敗**。

| 要什麼 | 去哪裡 |
|---|---|
| `& $gitBash` 標準呼叫段、LF/CRLF 判讀、Auth Gate 操作 | `runbook-windows-deploy.md` §1–§2 |
| Git 認證原則、禁止 PAT fallback | `GITHUB-AUTH-STANDARD.md`（canonical） |
| 技術債（Markdown verifier 缺口、`2>/dev/null` 吞錯誤等） | `runbook-windows-deploy.md` §5 |

⚠️ 換 interpreter **不是改腳本**。`github_push.sh` 與 `tools/deploy_verify.sh`
不得修改（Execution Boundary Standard Rule ①②）。
也**不要**在 PowerShell 重寫等價實作——那會變成第二份部署邏輯，正是本 SOP 在防的 drift。

⚠️ `DEPLOY_READY.json` 的 `deploy_command` 仍是 `bash github_push.sh`
（欄位形狀依派送 schema 固定）。**未來的 Windows watcher 不得照字面執行它**，
須由 payload adapter 轉換。

認證走 `gh auth setup-git` 設定的 credential helper，從系統 keyring 提供。
**嚴禁印出 token；不得改回明碼 token 檔**（Execution Boundary Standard Rule ②）。

回傳語意：

| 回傳 | exit | 意思 | 狀態 |
|---|---|---|---|
| `OK` | 0 | 推送成功或內容無變動 | `DEPLOY_PUSHED` |
| `FAIL` | 1 | 推送失敗（註明原因，**不重試超過 1 次**） | `DEPLOY_WAITING` |
| `DEPLOYMENT_NOT_AVAILABLE_IN_THIS_RUNTIME` | 3 | 當前 runtime 無部署工具鏈 | `DEPLOY_BLOCKED` |

exit 3 **不是** `SKIP`。它代表依現行架構此環境必然無法推送，
不是「這次剛好略過、下次可能會好」。收到 exit 3 時**不要**嘗試安裝 `gh`、
不要硬編路徑、不要建立 token——那些都違反 Execution Boundary Standard Rule ①②。
正確處理是回報 `DEPLOY_BLOCKED` 並指出需由 Windows Deployment Pipeline 接手。

## Step 6.9：驗證閘門與派送（2026-09-07 新增）

架構是五段式，每一段都可以獨立稽核：

```
Producer → Validator → Queue → Dispatcher → Verifier
```

**分析結果 ≠ 派送指令。** 判讀完成只代表 `CLASSIFIED`，不代表可以送出去。

### 派送佇列

`data/dispatch_queue.json`。每筆工作至少要有 `dispatch_id`、`source`、`intent`、
`action`、`dispatch_level`、`validation`、`dispatch_status`。

```
dispatch_id = 日期_平台_帳號_permalink_action
```

同一個 `dispatch_id` 無論排程重跑幾次都只會成功一次（冪等），紀錄在
`data/dispatch_log.jsonl`（append-only）。**這一條直接吃掉「同日兩個 instance」
造成的重複寫入**——即使護欄失效，也不會寫兩張同樣的卡。

要更正一筆錯誤派送，用 `dispatch.py --void <id> --reason "..."` 補寫一筆 `VOIDED`，
**不要去改 log 既有的行**。`already_dispatched` 看的是同一個 id 的最後一筆結果。

### 六道閘門（`tools/validation_gate.py`）

| Gate | 驗什麼 | 不通過 |
|---|---|---|
| G1 Concurrency | 沒有其他 instance 正在寫同一份資料 | `CONCURRENCY_BLOCKED` |
| G2 Source freshness | permalink 格式合法、有查核時間、未超過 7 天 | `SOURCE_INVALID` |
| G3 Duplicate | dashboard／queue／歷史紀錄均未重複 | `DUPLICATE_SKIP` |
| G4 Content policy | 風險類／敏感家庭／醫療／攻擊性不自動派送 | `MANUAL_ONLY` |
| G5 Artifact integrity | health check PASS、主檔與 index 一致 | `CONTENT_INVALID` |
| G6 Deployment | 依賴網站最新資料者須 `DEPLOY_VERIFIED` | `DEPLOY_WAITING` |

```
PASS → 可進 DISPATCH_QUEUE
WARN → REVIEW_REQUIRED，不自動派送（人工確認後 --approve --accept-warn）
FAIL → BLOCKED，不派送。FAIL 只能修好再驗，不可用核准繞過
```

### 派送分級

| 級 | 內容 | 流程 |
|---|---|---|
| **L1 可全自動** | dashboard 新增合格卡片、更新統計、local sync、health check、deploy verify、建待辦 | `PASS → AUTO_DISPATCH` |
| **L2 半自動** | 留言候選、Threads 回覆建議、追蹤建議、中等敏感度品牌互動 | `PASS → PREPARED → 人工 APPROVE → DISPATCH` |
| **L3 禁止自動** | 風險類、敏感家庭、醫療、攻擊性 | `OBSERVE_ONLY`，不留言、不自薦、不導購 |

⚠️ **任何「對外送出」的動作（留言、發文、私訊）一律不得掛在 L1 底下。**
要新增這類 action，必須同時新增對應的 L2 人工核准路徑。

## Step 7：Deployment Evidence Gate

```bash
bash tools/deploy_verify.sh        # 容器內；Windows 上請用 Step 6.5 的 & $gitBash 寫法
```

不做認證、不推送，只用匿名讀取比對，輸出三種 evidence：
local artifact hash／remote HEAD／target file hash comparison。

| exit | 結果 | 狀態 |
|---|---|---|
| 0 | 遠端＝本機 | **`DEPLOY_VERIFIED`** ← 只有這裡才叫「發布完成」 |
| 1 | 遠端落後 | `DEPLOY_WAITING` 或 `DEPLOY_BLOCKED` |
| 2 | 讀不到遠端 | `UNKNOWN`（不得記成已發布，也不得記成未發布） |

`github_push.sh` 回 `OK` **不等於**已發布——它只證明推送動作的 exit code。
GitHub Pages CDN 約 10 分鐘快取屬正常，本 gate 驗的是 git remote，
Pages 實際部署完成是再下一層（暫不納入，先把 remote verification 做穩）。

## 每日流程總覽（2026-09-07 定版）

任何一項出錯，都不得直接跳到「完成」。

```
01 acquire_lock          取不到 → CONCURRENCY_BLOCKED，結束
02 discovery             三 surface 全失敗 → DEGRADED（見 1.9）
03 classify              四大分頁 ＋ 八段式判讀
04 dedupe                dashboard_prep.py --check
05 risk_gate             風險／敏感 → L3 OBSERVE_ONLY，不進 L1
06 prepare_changes       素材四格（4.5）＋ 去 AI 味終檢（4.6）
07 safe_write            寫卡片、草稿、追蹤列、留言紀錄、計數
08 health_check          FAIL → CONTENT_INVALID，不建 queue
09 local_sync            主檔 → index.html
10 build_dispatch_queue  把可派送工作寫進 data/dispatch_queue.json
11 validation_gate       G1-G6；WARN → REVIEW_REQUIRED，queue 留著但不派
12 dispatch_L1_jobs      只派 validation=PASS 且 dispatch_status=READY
13 deployment_status     容器不 push；回 DEPLOY_BLOCKED／DEPLOY_WAITING
14 deploy_verify         tools/deploy_verify.sh
15 delivery_verify       確認派送出去的東西真的到位
16 write_run_report      摘要
17 release_lock          比對 fingerprint，drift 要寫進摘要
```

對應關係：

```
health_check FAIL   → CONTENT_INVALID  → 不建 queue
validation WARN     → REVIEW_REQUIRED  → queue 留著但不派
deployment 不一致    → CONTENT_COMPLETE + DEPLOY_WAITING → 不得寫 DEPLOY_VERIFIED
lock 取不到          → CONCURRENCY_BLOCKED → 什麼都不做，只回報
```

## Step 8：輸出摘要

```
[✅/⚠️/❓/⛔] Tru-Mi 每日處理｜YYYY-MM-DD
Lock            : [ACQUIRED <instance_id> / CONCURRENCY_BLOCKED（附持有者）]
Discovery       : [OK / DEGRADED（附三 surface 探測結果）]
Intent analysis : [完成 N 則 / SKIP — insufficient reliable input]
Comment audit   : [官方N則｜個人N則（實際送出）/ UNKNOWN]
Strategy panel  : [UPDATED / 無變動]
Health check    : [PASS / FAIL＋原因]
Local sync      : [PASS / FAIL]
Validation      : [PASS N／WARN N／FAIL N]
Dispatch        : [DISPATCHED N（L1）／PREPARED N（L2 待核准）／OBSERVE_ONLY N（L3）]
─────────────────────────
Content         : CONTENT_COMPLETE
Git push        : [DEPLOY_PUSHED / DEPLOY_WAITING / DEPLOY_BLOCKED＋原因]
Deployment      : [DEPLOY_VERIFIED / OUT_OF_SYNC / UNKNOWN]
Lock released   : [OK / OK＋WARN（鎖期間偵測到鎖外 writer）]
```

**不得**在 `Deployment` 未達 `DEPLOY_VERIFIED` 時，於摘要開頭寫「每日更新完成」
（Execution Boundary Standard Rule ③）。內容處理完成與正式發布完成是兩件事，摘要必須讓人一眼看出差別。
否則連續 10 天推送壞掉，每天都會回報「更新完成」，但網站 10 天沒動。

回報紀律（全域 CLAUDE.md）：`✅ 做完了`／`⚠️ 有疑慮`／`❓ 資訊不夠`／`⛔ 卡住了` 四選一。
爬取失敗、健檢 FAIL、留言零產出、部署未驗證，都要如實寫進摘要，
不可用「應該沒問題」帶過。

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
- 爬取失敗記錄錯誤於摘要，不中斷排程，仍執行 Step 7 的 Deployment Evidence Gate。
- 三個 discovery surface 全失敗即進 DEGRADED（見 1.9），不要用擴大關鍵字硬撐。
- 風險貼文一律不留言、不自薦、不批評同業，只記錄觀察。
- 所有新增內容用繁體中文。
- 每次只更新內容（新增卡片、統計、今日草稿、當日追蹤列、留言行銷紀錄）。
