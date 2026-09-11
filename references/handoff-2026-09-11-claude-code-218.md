# Handoff｜Claude Code 執行 218 段分流（2026-09-11）

> **這份不是規則文件。** 它只定這一次執行的順序、輸入、停止條件與回報格式。
> 所有規則都在 canonical，本檔只指向，不複製。執行完成後本檔可歸檔。
>
> 為什麼改用 Claude Code：Cowork 的 workspace sandbox 因 Plan9 掛載失敗無法執行
> `dashboard_check.py`（見 `incident-2026-09-11-bash-plan9.md` §10.1 R2／R2b）。
> Claude Code 不受影響。這是環境問題，不是 218 段或 canonical 的問題。

---

## 0. 開工前必讀（依序）

```
references/daily-sop.md        §0 互斥鎖｜§4.3 v3 pipeline｜§4.3 ①b 五類分流｜§4.9 Listener Analysis
references/jessica-voice.md    三 Audit 分工表｜§0.3 Voice Evidence 位階｜§2.5 生成機制 v2｜
                               §2.6 Jessica-First＋§2.6.5 Generation-Origin＋§2.6.6 測試輸出不得作示範｜
                               §7.3 AI Wording Audit｜§7.4 Corpus Audit｜§7.5 狀態定義
references/jessica-voice-samples.md   樣本分級表｜S-001～S-005｜C-001／C-002
references/dashboard-spec.md   §0.2 產品／維運邊界｜§0.3 卡片可以沒有建議留言｜§8 schema｜§9 健檢
references/runbook-windows-deploy.md  §0 標準流程（Windows 端 push 用）
```

⛔ **不得沿用任何前一輪的 generated candidate 當示範**（交叉測試 A／B／C 含在內）。
它們在 `jessica-voice-samples.md` 分級表裡標為 GENERATED CANDIDATE，只是測試輸出。

---

## 1. 執行順序（鎖定，不得調換）

### Step 1｜先固定 canonical 基線

四份未 commit 的檔案：

```
references/jessica-voice.md
references/daily-sop.md
references/jessica-voice-samples.md
references/incident-2026-09-11-bash-plan9.md
（＋本次新增：references/dashboard-spec.md §0.2／§0.3、本檔）
```

```
diff review → python tools/dashboard_check.py（基準）→ python tools/secret_scan.py
→ commit → push（runbook §0.5 兩條鏈）→ remote verify（runbook §0.9）
```

目的：讓 Jessica-first 規則先成為可追溯基線，218 段的每一筆變更都能對到這個 commit。

### Step 2｜重新讀取 repo 中的 canonical

從 repo 讀，不從對話記憶讀。確認 `daily-sop.md §4.3` 的 pipeline 第一步是
`Conversation Intent`、生成步驟是「直接用 Jessica 口語生成第一版」，
Jessica Voice 那一關是 **Verification** 不是 Rewrite。讀到的不是這樣就停。

### Step 3｜218 段逐段分流

對象：`threads_wedding_ring_dashboard.html` 內每張卡片的
「💬 Jessica 可以怎麼回」（原「四、非推銷式留言草稿」）與「五、Threads 延伸貼文草稿」。

每段：

```
原始貼文＋留言原文
 → Conversation Intent（§2.5.2 七題）
 → Evidence Gate
 → Structure Gate
     ├─ 像人 → KEEP 或 LIGHT FIX
     └─ 不像人 → REBUILD：丟掉原文，從原始留言＋對應情境的真實語料（§2.6.3 依情境取樣）重新生成
 → 需要 Jessica 本人經驗／立場而系統沒有 → EVIDENCE BOUNDARY
 → 生得出來但無足夠 Voice Evidence → VOICE REVIEW
 → 其餘 Gate 依 §4.3 v3 順序
```

每段留下**生成起點紀錄**（情境類型＋引用的 S-／C- 編號＋Reply Depth），放在 HTML 註解或既有 P1 欄位，
不放進 Jessica 看得到的 UI。沒有紀錄不得標 PASS。

**EVIDENCE BOUNDARY／VOICE REVIEW 可以沒有建議留言。** 顯示方式依 `dashboard-spec.md §0.3`。

⛔ 不得中途每批 push。⛔ 不得每批停下來問。
⛔ 不得因為「218 段幾乎都有一個漂亮新留言」而覺得做得好——那是警訊，見 §4。

### Step 4｜Corpus-level Audit（218 段全部完成後才做）

依 `jessica-voice.md §7.4`：抽掉主題，統計整批是否大量出現
相同開場／長度／轉折／專業進場／安慰句／總結句／停止點／自報身分／問句結尾／語助詞配置，
以及「不是 A 是 B」「差別主要在」「FAQ／說明書腔」「AI 安慰」「微型結論」的跨主題頻率。

Corpus Audit FAIL → 回頭找**生成機制**的問題，⛔ 不整批洗詞。

### Step 5｜驗證與派送（一次）

```
python tools/dashboard_check.py           必須 exit 0
Copy index.html ← 主檔，再驗一次
diff review → secret gate → commit → push → remote verification（runbook §0.9）
```

---

## 2. 停止條件（只有這五種才停）

```
Evidence Boundary（整批性的，不是單段——單段 BOUNDARY 是正常結果）
Decision Boundary（需要產品決策）
canonical conflict（兩份規則互相矛盾）
專業正確性無法確認
validation／deployment failure
```

「重寫幅度大」「marker 很多」「一段要 REBUILD」都**不是**停止條件（`daily-sop.md` 防循環條款）。

---

## 3. 回報格式

```
五類數量     KEEP __｜LIGHT FIX __｜REBUILD __｜EVIDENCE BOUNDARY __｜VOICE REVIEW __   （合計 218）
Corpus Audit PASS / FAIL（FAIL 時列出是哪一種模板、出現幾次、跨幾個主題）
狀態         Automated Audit：PASS/FAIL｜Positive Validation：NOT TESTED（固定，Jessica 未看過）
驗證         dashboard_check exit｜secret_scan exit｜push exit｜remote hash
停止         若有，列停止條件與位置
```

---

## 4. 這次最值得看的三個數字

```
有多少原文其實 KEEP
有多少真的需要 REBUILD
有多少系統願意停在 EVIDENCE BOUNDARY／VOICE REVIEW
```

如果最後又變成 218 段幾乎都有一個漂亮的新留言，**那是 Jessica-first 又被執行成另一套生成模板的證據**，
不是成功。

---

## 5. 邊界（不得越）

- 系統／環境 Bug **不進 Dashboard**（`dashboard-spec.md §0.2`）。
- 不改 `:root`、既有 CSS、`github_push.sh`、`tools/deploy_verify.sh`。
- 不建立任何明碼 token 檔；不向使用者索取 token。
- 對外帳號一律 `@trumi_jewelryofficial`。
- 風險貼文不留言、不自薦、不批評同業。
- `incident-2026-09-11-bash-plan9.md` §11 維持 EXTERNAL ATTRIBUTION，不升格 CONFIRMED。
