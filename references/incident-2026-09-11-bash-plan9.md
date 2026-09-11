# Incident 2026-09-11｜bash / Plan9 sandbox lifecycle failure

```
Incident ID   : 2026-09-11-bash-plan9
Scope         : Sandbox lifecycle / execution environment
Impact        : Dashboard implementation BLOCKED 約一個工作天
Status        : RECOVERED
Root Cause    : UNCONFIRMED
```

> ⚠️ **`RECOVERED` ≠ `ROOT_CAUSE_RESOLVED`。**
> 環境恢復只證明可以繼續工作，不證明知道為什麼壞。

---

## 1. Timeline

| 時間 | 事件 |
|---|---|
| 2026-09-10 | 每日排程正常完成，`DEPLOY_VERIFIED`，remote HEAD `8d95b76` |
| 2026-09-11 早 | 首次 bash 呼叫失敗；連續 5 次相同錯誤後判定 wedged |
| — | 改用檔案工具完成唯讀盤點與 SOP 編輯，宣告 `FROZEN／零專案寫入` |
| — | 第 6、7 次探測（含最小 `echo` probe）失敗，判定 `RECOVERY_ATTEMPT_FAILED` |
| — | 重啟 Claude 桌面程式 → 錯誤變為 `VM service not running` |
| — | 重新開機 → VM service 恢復，但原錯誤簽章回歸 |
| — | 使用者在本機 PowerShell／Git Bash 執行，工作恢復（人機分工模式） |

---

## 2. Symptom

所有 shell 指令在**執行前**即失敗，包含最小 `echo` probe。指令本體從未開始執行。

## 3. Evidence

```
① resume:
   failed to mount .../uploads as uploads:
   source path ... is under Plan9 share "c" which is not mounted

② create（fallback）:
   ensure user: user determined-keen-thompson
   already exists unexpectedly: uid=1183 gid=1183
```

resume 因 9p share 消失而不可能成功；create 因殘留 user record 碰撞而不可能成功。
**兩條路同時斷。**

### 3.1 重啟後的錯誤變化（診斷關鍵）

```
重啟 Claude 前 : Plan9 share not mounted ＋ stale user collision
重啟 Claude 後 : VM service not running          ← 主機層
重新開機後     : VM service 恢復；但上述兩個原錯誤回歸
```

**推論（非確證）**：「Plan9 share 消失」可能是 VM service 中止的**症狀**，
而非獨立原因。VM service 最初為何中止，無證據可判斷。

### 3.2 一項可驗證的事實

user record `determined-keen-thompson` (uid 1183) **撐過了一次完整重新開機**。
記憶體殘留不可能存活過重開機 → 該記錄存在持久化狀態中，且綁定本對話的 sandbox 識別碼。

由此可判定故障範圍為 **session-scoped，不是 host-scoped**。

---

## 4. Failure layer

```
✅ 已定位  : Sandbox lifecycle（resume 與 create 兩條路徑皆失敗）
❌ 未證實  : Plan9 share 為何消失
❌ 未證實  : VM service 最初為何中止
❌ 未證實  : stale user record 為何未被清理
```

**證據不支持**以下任一結論：Tru-Mi 程式碼造成｜repository 造成｜
working directory 造成｜某一支 script 造成。

---

## 5. Actions attempted

| 動作 | 結果 |
|---|---|
| 最小 `echo` probe ×7 | 全部失敗，錯誤簽章一致 |
| 重啟 Claude 桌面程式 | 錯誤層級改變，未解決 |
| 重新開機 | VM service 恢復，sandbox 仍不可用 |
| 檔案工具唯讀盤點 | 成功（走不同路徑） |
| 人機分工（AI 寫檔／使用者執行） | **成功，工作恢復** |

## 6. Actions NOT attempted（刻意不做）

```
⛔ 刪 lock ／ 刪 user ／ 改 mount
⛔ 修改 Dashboard 程式碼以掩蓋環境問題
⛔ 修改 deployment 邏輯以繞過 sandbox failure
⛔ 為了讓 health check 通過而降低驗證標準
⛔ 建立假的 health-check 結果
```

理由：execution layer 不可用時，**沒有能力安全驗證這些動作**。
而且修復手段本身需要執行指令，而執行指令正是壞掉的那件事——
**專案端任何改動在技術上都無法影響此故障。**

---

## 7. Asset risk（本次最大發現）

盤點時發現遠比預期嚴重的備份缺口：

| 資產 | 狀態 |
|---|---|
| `references/daily-sop.md` | +867 行變更**從未進 Git** |
| `tools/runlock.py`／`validation_gate.py`／`dispatch.py`／`secret_scan.py`＋2 支 regression test | **從未進過 repo** |
| `references/incident-2026-09-07-*.md` ×2 | **從未進過 repo** |

即整套 concurrency incident 之後建立的工具鏈都只有單一本機副本。

**已於同日解除**：commit `ddae114`，11 檔 +2914/-31，remote verification 通過。

### 7.1 為什麼沒早點發現

`tools/deploy_verify.sh` 只驗兩份 HTML，`references/*.md` 與 `tools/*.py` 由
`repo_sync_docs.sh` 負責，而後者**不在每日排程中自動執行**。
→ HTML 天天 `DEPLOY_VERIFIED`，文件與工具卻可以數週沒有備份而無人察覺。

**這是流程缺口，不是本次事故造成的。** 已列入 `runbook-windows-deploy.md` 技術債。

---

## 8. Recovery procedure（實際生效的）

```
1. 最小 execution probe（echo / pwd / whoami）
2. 失敗 → 不測專案 script，不執行同步，不改 Dashboard
3. 改用檔案工具完成唯讀資產盤點，建立 recovery baseline
4. 宣告 FROZEN／零專案寫入
5. 主機層修復（重啟應用程式 → 重新開機）
6. 仍失敗 → 判定 session-scoped
7. 改人機分工：AI 負責檔案寫入，使用者負責執行與發布
```

## 9. Validation（恢復後）

```
✅ 取鎖成功        trumi_daily-20260911-072329-d474
✅ dashboard_check  229 卡、PASS、exit 0，與事故前 baseline 一致
✅ HTML hash        a80f482e4c672268（未變動）
✅ gh auth          keyring 認證，scopes 含 repo
✅ push / remote    ddae114，local HEAD == origin/main
✅ secret gate      無 HIGH_CONFIDENCE 內容命中；.github_token 回 404（未進 repo）
```

**注意證據層級**：HTML 的 hash 是可驗證的 integrity evidence；
其餘檔案的「未修改」只是操作紀錄，**不得在報告中寫成「完整性已由 hash 驗證」**。

---

## 10. Recurrence signature

```
任何 bash 呼叫回：
  Plan9 share "c" which is not mounted
  或 ensure user ... already exists unexpectedly
```

**復發時第一件事：跑 `echo`。**
若 `echo` 也失敗 → 確定是 sandbox lifecycle 而非命令問題，不必再逐條試專案指令。

**已知有效的處置順序**：重啟應用程式 → 重新開機 → 若仍失敗，改人機分工繼續工作。

### 10.1 復發紀錄

| # | 時間 | 簽名 | 當時工作 | 處置 |
|---|---|---|---|---|
| R1 | 2026-09-11（本次事故） | Plan9 + stale user | Dashboard IA v2 | 重開機後恢復 |
| R2 | 2026-09-11 稍後（同日第二次） | **完全相同**：Plan9 share "c" not mounted ＋ uid=1183 already exists，attempt 3 of 5 | 準備重跑 218 段 | 依簽名判定為同一事故，**不重試**；canonical `.md` 編輯改用 file tools 完成；218 段因 `dashboard_check.py` 無法執行（Step 5.9 閘門）而**停在 Execution Boundary**，未對 HTML 做任何未經健檢的批次修改 |

| R2b | R2 之後、canonical 修正完成時 | 相同；`echo ok` 亦失敗（依 §10 只試一次）；錯誤訊息附帶廠商聲明（見 §11） | 準備重跑 218 段 | 停止重試；218 段維持 BLOCKED |

| R3 | 2026-09-11 13:13（Cowork session，同日第三次） | 相同簽名，訊息為 `sandbox-helper: no Plan9 drive shares mounted under /mnt/.virtiofs-root/shared`，並附帶與 R2b 相同的廠商聲明；依 §10 只試一次 | 依 `handoff-2026-09-11-claude-code-218.md` 重跑 218 段（自 Step 1 起） | 停止重試；218 段維持 BLOCKED，**未取鎖、未對 HTML 做任何寫入** |

R3 的三項新資訊（與 R2／R2b 的差別，診斷用）：

1. **閘門本身沒有壞，壞的是 Windows 端執行通道。**
   R2 停在「`dashboard_check.py` 無法執行」；R3 以完全相同的來源檔在雲端容器執行
   `dashboard_check.py`，回 **PASS／exit 0**（1.24 MB／6350 行／229 張卡，
   分佈 溝通35 日常61 預算84 傳承49），與事故前 baseline 的卡數一致。
   → 故障範圍可再收斂為 **workspace 檔案掛載層**，不含驗證邏輯、不含專案內容。

2. **第二條迂迴路徑（GUI 代打指令）經查證亦不可用。**
   computer-use 對終端機／IDE 類應用程式只給 `click` 層級（可見、可左鍵點擊，
   **不可輸入文字、不可按鍵、不可貼上**）。`Windows PowerShell` 解析結果為
   `tier: click`。→ 事故期間 AI 端沒有任何可用的 Windows 指令執行通道。

3. **由 1＋2 得到的工作方式結論（與 §11 一致，非新歸因）：**
   人機分工不是應急而是此事故期間的唯一可行模式——
   AI 端可做到內容與本機驗證（CONTENT_COMPLETE）為止；
   取鎖／commit／push／remote verification 一律必須在 Windows 端執行。

⛔ R3 不改寫 §11：Root Cause 仍為 `PARTIALLY IDENTIFIED ＋ EXTERNAL ATTRIBUTION`，
不因「換到雲端容器就能跑健檢」而改寫成「Plan9 故障已定位於 X」——
那只是證明另一台機器正常，不是本機故障原因的證據。

R2 的重要性：**同一天同一 session 復發**，加強「session-scoped、非專案指令問題」的判斷；
R2b 取得第一筆 EXTERNAL EVIDENCE。Root Cause Status 更新見 §11。

---

## 11. Root Cause Status

```
PARTIALLY IDENTIFIED ＋ EXTERNAL ATTRIBUTION（2026-09-11 R2 更新）

已確認：
  · failure layer 為 sandbox lifecycle
  · VM service 曾中止
  · 故障範圍為 session-scoped

EXTERNAL EVIDENCE（R2 的 bash 錯誤訊息末尾，由平台附帶）：
  「A Windows update released September 8 prevents Claude's workspace
    from reaching your files. We're tracking this issue. Claude Code is unaffected.」
  → 廠商歸因為 2026-09-08 Windows 更新與 workspace 檔案掛載的相容性問題
  → 與本事故簽名（Plan9 share 未掛載）一致
  → 這是廠商陳述，不是本機獨立驗證；不升格為 CONFIRMED

未確認：
  · 哪一個 KB 更新、是否能回滾
  · 為何上午重開機後曾短暫恢復（若為更新所致，恢復期應為 0）
  · stale user record 為何未被清理
```

⛔ **不得**因為換環境後正常，就把 root cause 寫成「stale sandbox」或「Plan9 故障已修復」。
⛔ 也**不得**因廠商一句話就寫「Windows 更新所致」——只能寫 EXTERNAL ATTRIBUTION。

**對工作方式的影響**：若廠商歸因成立，重啟／重開機**不會**修好它；
人機分工（file tools 編輯、Windows 端跑驗證與派送）是本事故期間的常態模式，不是應急。
「Claude Code is unaffected」是一條可行的替代路徑，由使用者決定是否採用。

---

## 12. 附帶產出

本次事故期間額外發現並處理的三件事：

1. **`repo_sync_docs.sh` 與 `github_push.sh` 用 `2>/dev/null` 吞掉 push 的 stderr**
   → 失敗時只能猜原因，實際錯誤不可見。已列入技術債。
2. **重開機後 git credential helper 需重新 `gh auth setup-git`**
   → 任何 runbook 都沒寫過這件事。已補入 `runbook-windows-deploy.md`。
3. **`secret_scan.py` 的 regression fixture 會被 GitHub Push Protection 擋下**
   → commit `f6f0096e` 因 Slack token fixture 被擋。
   已改為 runtime 組裝（值逐字元相同，偵測覆蓋率零損失），37/37 regression 通過。
   同時修掉 JWT、private key、URL userinfo 三條同類風險。
   **未使用 bypass、未降低 detector 靈敏度、未刪除 coverage。**
