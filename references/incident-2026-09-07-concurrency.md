# INCIDENT 2026-09-07｜CONCURRENCY — duplicate writer on Tru-Mi dashboard

```
Concurrency protection : IMPLEMENTED / TESTED
Parallel execution     : CONFIRMED
Concurrency root cause : CONFIRMED — HUMAN_SCHEDULER_OVERLAP
Credential control     : CLEANUP_INCOMPLETE
Validation gate        : IMPLEMENTED / TESTED
Dispatch control       : IMPLEMENTED / TESTED（10/10 regression）
G5 integrity           : PASS（2026-09-07 已核可修復）
Dashboard health       : PASS / 0 WARN
Dashboard canonical    : CONFIRMED_LOCAL_CANONICAL（224 cards）
Deployment             : HOLD
Remote                 : OUT_OF_SYNC（remote = 09-06 內容，已證實）
```

撰寫：2026-09-07｜關聯：`references/daily-sop.md` Canonical Rule ⑤⑥

---

## 1. 事件

`tru-mi-daily-threads-update` 於 09:41:38 開始執行。開跑時：

```
threads_wedding_ring_dashboard.html   224 張卡   去重池 222 帳號 / 215 貼文
dashboard_prep.py --check @satine_0720  →  NEW
```

判讀進行中，**主檔於 09:54:27 被另一個 writer 覆寫**，index.html 於 09:54:33 同步：

```
09:54 後   225 張卡   去重池 223 帳號 / 216 貼文
新增：@satine_0720 卡片（data-collected="2026-09-07"，Tru-Mi 八段式格式）
另加：今日草稿、當日追蹤列、留言行銷紀錄列
```

新增內容的格式、口徑、命名慣例都與本流程一致，判定為**同型 writer**，
不是外部程式誤寫。本次執行依 Step 0 護欄停止寫入，未造成資料遺失。

## 2. 排查過程與被推翻的假設

| # | 假設 | 結果 |
|---|---|---|
| H1 | 每週版排程接手（SOP Step 0 情境） | ❌ **推翻**。`threads-home-deco-daily` 確實是每週一排程且今天有跑，但它屬 ChannelDeco 品牌，目標是 `chanel deco/index.html`，不是本檔 |
| H2 | 同一任務被建立兩份 | ❌ **推翻**。`list_scheduled_tasks` 只有一支指向本儀表板 |
| H3 | 前一實例未結束就被再次啟動 | ⚠️ **最相符，但未證實**（見下） |
| H4 | 使用者在另一個 session 手動補跑 | ⚠️ **可能，無法從容器端排除** |

**H3 的證據**：三支排程的 `lastRunAt` 全部是 `2026-09-07T01:41:38Z`（彼此相差
不到 1 秒），而 `tru-mi-daily-threads-update` 的 cron 是 `0 9 * * *`＋jitter 577s，
排定觸發時間應為 `01:09:37Z`。同秒批次觸發的樣態像是**應用程式喚醒後的補跑**。
若 09:09 那次已經觸發並仍在執行，09:41 的補跑就會產生第二個 instance。

**為什麼無法證實**：`lastRunAt` 只保留最後一次觸發時間，09:09 那次（若存在）已被覆蓋。
容器端也看不到 Windows 主機上的 process。

⚠️ **這一條不要寫成已確認的結論。** 現有證據支持它，但沒有證明它。

### 2026-09-07 補充查核：排程層在哪一層

`Get-ScheduledTask | Where TaskName -like "*tru-mi*"` 在 Windows 上**零回傳**。
→ 這三支**不是** Windows Task Scheduler 任務，而是 **Claude 桌面版（Cowork）的應用層排程**。
`list_scheduled_tasks` 由 `scheduled-tasks` MCP 提供，任務定義在
`C:\Users\Tilandky Ho\Documents\Claude\Scheduled\<taskId>\SKILL.md`。

⛔ **不要再拿 Windows Task Scheduler 的 event log 當本事故的根因證據**，那一層根本沒有這些任務。

應用層 run history 可用 `session_info` 查。實際查核結果：

| session_id | 標題 | 日期 | 事實 |
|---|---|---|---|
| `local_74a5a165…` | Tru mi daily threads update | 09-07 | 本次執行。09:41:38 起跑，偵測到覆寫後停止寫入 |
| `local_52ac5aef…` | Tru mi daily threads update | **09-07** | **就是 09:54:27 的 writer**。完成完整一輪，收錄 @satine_0720，回報 225 卡、health PASS |
| `local_f0f78524…` | Tru mi daily threads update | 09-06 | 前一日，非本事故 |

**確認：同日確實有兩個同任務 session 並行。** 這一點不再是推測。

**但第二個 session 是怎麼被啟動的，仍未確定。** 一條反向線索：
`local_52ac5aef` 的回報裡寫「遠端 HEAD 7f066df 仍是**你剛才推的** 09-06 內容」——
排程執行不會知道使用者「剛才」推了什麼，除非那個 session 裡有人對它說過話。
所以它可能是**使用者在既有 session 內續跑／手動補跑**，而不是排程重複觸發。

### 根因確認（2026-09-07，讀完 `local_52ac5aef` 全文後）

**`ROOT_CAUSE : HUMAN_SCHEDULER_OVERLAP` — 已確認，非推測。**

該 session 有**多個 user turn**，是一段持續進行的人工對話（處理 09-06 日報爭議、
指導 `gh auth` 與 Git Bash、修 `deploy_verify.sh` 的 autocrlf bug、
執行 `github_push.sh`）。使用者接著說「更新貼文」，該 session 就開始跑當日流程。

決定性證據是那個 session 自己寫下的一句話：

> 「儀表板最新停在 09-06，今天還沒跑。今天是**週一**（每週版 home-deco 的執行日），
> 但那支寫的是另一份儀表板，且 SOP Step 0 明訂『使用者手動要求補跑時才可忽略』——
> **你這句就是手動要求，所以放行。**」

所以事件序列是：

```
（稍早）  使用者在 local_52ac5aef 內持續互動，完成 09-06 內容的 push
09:41:38  排程獨立啟動 local_74a5a165（本次執行）
（同時）  local_52ac5aef 依「手動補跑」條款放行，開始跑當日流程
09:54:27  local_52ac5aef 寫入主檔       ← 覆寫發生在此
09:54:33  local_52ac5aef 同步 index.html
```

排除掉的假設：
- ❌ scheduler 於 09:09 重複觸發 —— 不需要這個假設就能解釋全部現象
- ❌ wake-up catch-up 為根因 —— 它可能是 09:41 那次觸發的機制，但**不是覆寫的原因**

### ⚠️ 舊 Step 0 的真正漏洞：手動補跑條款

舊護欄寫著「**使用者手動要求補跑時才可忽略**」。這句話讓人工觸發的執行
**完全跳過整個 Step 0**，包括任何併發檢查。那個 session 是**照規則走的**，
它引用了條款、說明了理由、然後正確地放行——規則本身就是洞。

→ 修正：新 Step 0 已移除該例外。**手動補跑一樣要取鎖，沒有例外。**
手動的正當性影響的是「今天該不該跑」，不影響「能不能同時有兩個 writer」——
這是兩個不同的問題，舊規則把它們混成一個。

新鎖若當時存在，`local_52ac5aef` 在取鎖階段就會回 `CONCURRENCY_BLOCKED`
（或反過來，本次執行被擋），不會走到寫入。

## 3. 為什麼舊的 Step 0 擋不住

舊護欄是「開跑時用 bash 取得今天日期與星期」。這是**偵測**，不是互斥：

```
09:41:38  本 instance 開跑，檢查護欄 → 通過（當時檔案是乾淨的）
09:54:27  另一個 writer 寫入          ← 護欄早就檢查完了，看不到
```

衝突發生在開跑之後。任何「開跑時看一眼」的機制，結構上都無法涵蓋這段時間。
這次是靠比對 mtime 才發現，屬於運氣，不是設計。

## 4. 已落地的修正

| 修正 | 檔案 | 擋住什麼 |
|---|---|---|
| 互斥鎖（心跳＋TTL＋fingerprint drift） | `tools/runlock.py` | 第二個 instance 連 discovery 都不會開始 |
| 六道驗證閘門 G1–G6 | `tools/validation_gate.py` | G1 併發、G4 風險內容、G5 產物完整性、G6 部署前置 |
| 派送佇列＋冪等 dispatcher | `tools/dispatch.py`、`data/dispatch_queue.json` | 同一 `dispatch_id` 只成功一次；即使鎖失效也不會寫兩張同樣的卡 |
| Canonical Rule ⑤⑥ | `references/daily-sop.md` | 互斥、以及「No validation, no dispatch」 |
| 排程清單查核表 | `references/daily-sop.md` Step 0 | 避免再把 ChannelDeco 排程誤判成本流程的每週版 |
| 回歸測試 13 項 | `tools/test_dispatch_regression.py` | 派送控制的行為不會被日後改壞（在 tempdir 跑，不碰真 queue） |
| `runlock.py checkpoint` | `tools/runlock.py` | 授權寫入後重新取 fingerprint 基準 |

**為什麼要有 checkpoint**：fingerprint 是取鎖當下拍的，它分不出「我自己剛剛合法寫的」
和「別人偷偷寫的」——兩者看起來都只是 mtime 變了。不 checkpoint 的話，
release 每次都會報 drift，久了就會被當成雜訊忽略，**那等於把警報關掉**。
所以每完成一次授權寫入就 checkpoint 一次；之後 release 若還報 drift，就是真的鎖外 writer。

**回歸測試涵蓋**（2026-09-07 全數通過 13/13）：
R1 void 後不得殘留 approval／dispatch／execution 欄位（真實踩到的坑）｜
R2 冪等：重複 execute 只產生 1 筆 DISPATCHED｜R3 No validation, no dispatch｜
R4 L3 核准也不行｜R5 FAIL 不可用 `--accept-warn` 繞過｜R6 void 必須留理由｜
**R7 validator 與 dispatcher 對 VOIDED 的認定必須一致（第二個真實踩到的坑）**。

**R7 的來歷** — 這是一個獨立的次要事故，已結案：

```
Root cause: DUPLICATE_STATE_SEMANTIC_DRIFT

dispatch.py                : 以同一 id 的最後有效狀態判定
validation_gate.py（修正前）: 只要歷史曾出現 DISPATCHED 即判定重複

Failure: VOIDED 後 dispatcher = PENDING，但 validator = DUPLICATE
Symptom: G3 在無外部變化下莫名 FAIL
Status : RESOLVED（13/13 regression，修復後 G3 PASS）
```

**兩邊各自看起來都合理，這種不一致最難查。** 已統一語意並鎖進 R7 的三個斷言：
日後改動任一邊，另一邊沒跟上就會被抓到。

理想上兩邊應共用單一狀態投影函式；目前以「同一份 canonical 規格＋共用回歸測試」約束，
已足以擋住回歸，不為此再重構一次。

⚠️ 本項**不因 2026-09-07-B（Meta 憑證）事件回退**——兩者無因果關係。

R1 的斷言刻意寫成「整組欄位都要清掉」而不是只檢查 `approved_at`：
日後新增任何核准／派送欄位，忘了加進清除清單就會在這裡被抓到。
會出現這個 bug 是因為狀態欄位與旁證欄位不一致——
「狀態是 PENDING_VALIDATION，metadata 卻還留著核准時間」，
兩邊各自看起來都合理，所以比單純狀態錯更難查。這類 semantic drift 要靠測試擋。

**實作限制（重要）**：本工作資料夾是雲端掛載磁碟，`os.remove` 回
`Operation not permitted`（2026-09-07 實測，ChannelDeco SKILL 也記錄過同一現象）。
因此鎖用**檔案內的 `state` 欄位**表示，不是用檔案存不存在表示。
任何把它改成 delete-to-unlock 的「簡化」都會讓鎖直接壞掉。

## 5. 驗收結果（2026-09-07 實測）

```
第二個 instance 取鎖              → CONCURRENCY_BLOCKED, exit 4      ✅
非持有者釋放鎖                    → FAIL, exit 1                     ✅
released 後可再次取得              → exit 0                           ✅
未驗證就派送                      → BLOCKED（No validation, no dispatch）✅
風險類（@ch_1001mm 產後憂鬱）      → G4 FAIL / MANUAL_ONLY            ✅
L3 即使人工核准                    → REFUSED                          ✅
WARN 未經確認核准                  → REVIEW_REQUIRED                  ✅
重複 execute                      → DUPLICATE，log 恆為 1 筆          ✅
--void 撤銷                       → 補寫 VOIDED，歷史不改寫           ✅
```

## 6. 未結案項目

1. **根因仍未證實**。需要在 Windows 端確認 09:09 是否有一次觸發。
   在確認之前，維持「不讓任何自動寫入任務修改同一份 HTML」。
2. **憑證清理：兩個檔要分開記，不可混成同一事件。**

   | 檔案 | 事實 | 狀態 |
   |---|---|---|
   | `.github_token` | 93 bytes，命中 PAT pattern，mtime **2026-08-07**（migration 前的殘留，非重建）。對應 PAT 使用者已撤銷 | `REVOKED SECRET / FILE RESIDUAL` |
   | `token.txt` | 8 行 397 bytes，mtime 2026-09-06 20:10。掃描 `github_pat_`／`ghp_`／`LINE`／`SECRET`／`Bearer`／`sk-` 等樣式**全部未命中** | `NO KNOWN SECRET PATTERN DETECTED`／`SANITIZED / TOMBSTONE CANDIDATE` |
   | `meta tmp pw.txt` | 771 bytes，命中 `EAA` 前綴 ×2 | **另案處理** → `incident-2026-09-07-meta-credential.md` |

   ⚠️ **`meta tmp pw.txt` 已升格為獨立資安事件（INCIDENT 2026-09-07-B）。**
   資產、授權範圍、撤銷路徑都與 GitHub 這件不同，不可混為一談：
   **本件（GitHub）的既有結論不因它回退，本件的結案也不涵蓋它。**
   詳見 `references/incident-2026-09-07-meta-credential.md`。

   掃描規則的教訓已升格進 `tools/secret_scan.py`（ruleset v1，count-only，
   輸出必帶版本／範圍／排除項目）。但**不得因 pattern count = 0 就宣稱沒有秘密**——
   那只證明「這個版本的規則在這個範圍內沒有命中」。

   ⛔ **不得把 `token.txt` 記成「曾含 PAT」——目前沒有這個證據。**
   整體狀態是 `CLEANUP_INCOMPLETE`，**不是** credential regression。
   Producer 追查：`github_push.sh`、`repo_sync_docs.sh`、`tools/*.py` 皆不引用任何 token 檔，
   唯一命中的是 SOP 裡的禁止規定本身。`github_push.sh` 走 gh CLI，乾淨。
   刪除由使用者手動執行（注意 PowerShell `Remove-Item` 曾被 function shadow，
   需用 `Microsoft.PowerShell.Management\Remove-Item`），刪後以 `Test-Path` 驗兩者皆為 `False`。

3. **G5 重複 permalink：已診斷，待核可後才動。**

   `@moose.19971024/post/DbF_0VkkyIp` 出現 2 次，兩張卡片比對結果：

   | | 起始行 | 帳號 | post-date | level | 互動 | 內文 |
   |---|---|---|---|---|---|---|
   | A | 2529 | @moose.19971024 | 2026-07-23 | B | ❤️ 54 | 相同 |
   | B | 2630 | @moose.19971024 | 2026-07-22 | C | ❤️ 32 | 相同 |

   判定：**同一貼文重複收錄**（不是兩則不同貼文共用 permalink）。
   同一則在 07-22、07-23 連兩天各收一次，讚數 32→54 是同一則的成長。

   ✅ **2026-09-07 經核可後已修復。** 這次動作的性質是
   **duplicate card removal，不是 link correction**——
   permalink 沒有貼錯，是同一則被收了兩次。
   ⛔ 事故報告與日後回顧不得把根因寫成「卡片貼錯連結」。

   實際變更（範圍嚴格限於核准的 5 項）：

   | 項目 | 前 | 後 |
   |---|---|---|
   | 移除 B 卡（行 2630-2648，19 行，div 平衡 42/42） | 有 | 無 |
   | 卡片總數 | 225 | 224 |
   | panel-budget 計數 | 83 | 82 |
   | summary-bar 蒐集貼文數 | 225 | 224 |
   | `DbF_0VkkyIp` 出現次數 | 2 | **1**（保留 2026-07-23 / B / ❤️54） |
   | health check | PASS＋1 WARN | **PASS，零 WARN** |
   | G5 Artifact integrity | WARN | **PASS** |

   刪除前跑了 5 道前置斷言（起始行標記、permalink、日期、互動數、div 平衡），
   任一不符即中止。主檔已同步至 `index.html`（G5 要求兩者一致，否則健檢必 FAIL）。
   未推送，Deployment 維持 HOLD。

4. **部署 `OUT_OF_SYNC` → 語意已收斂。**
   遠端 HEAD `7f066df` commit message 寫 2026-09-07，但依 `local_52ac5aef` 的回報，
   其內容是使用者當天手動推上去的 **09-06 版本**。所以「remote 有 09-07 commit」
   指的是推送日期，不是內容日期。
   在根因釐清、憑證清理完成、G5 回 PASS、且確認 225 卡版本為 canonical 之前，**HOLD**。
