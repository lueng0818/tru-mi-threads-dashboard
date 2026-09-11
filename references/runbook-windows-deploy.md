# Runbook｜Windows 部署與同步

> 建立於 2026-09-11。
> **Git 認證原則的 canonical owner 是 `GITHUB-AUTH-STANDARD.md`，本檔只引用不複製。**
> 本檔負責：Windows 端的實際操作、故障排除、技術債。

---

## 0. 標準流程（照抄即可｜2026-09-11 實測通過）

> 這一節是**可直接複製貼上的完整流程**：取鎖 → 健檢 → 除錯 → 同步 → 驗證。
> 每一段都在 2026-09-11 實際跑過並成功。遇到問題先看 §0.5 對照表，不要自行發明修法。

### 0.1 開工：取鎖 ＋ 基準健檢

```powershell
cd "$env:USERPROFILE\Documents\Claude專區\Tru-Mi專區"

python tools\runlock.py acquire --task trumi_daily --note "<這次要做什麼>"
"lock exit = $LASTEXITCODE"      # 0=取得  4=CONCURRENCY_BLOCKED（停止，不要繞過）

python tools\dashboard_check.py
"check exit = $LASTEXITCODE"      # 動工前先確認基準是乾淨的
```

**記下 lock 的 instance id**，收尾 checkpoint／release 要用。

### 0.2 改完：本機驗證

```powershell
cd "$env:USERPROFILE\Documents\Claude專區\Tru-Mi專區"
python tools\dashboard_check.py
"check exit = $LASTEXITCODE"      # 必須 0，FAIL 就先修，禁止推送
```

改過 `tools/*.py` 時，額外跑 regression：

```powershell
python tools\test_secret_scan_regression.py
python tools\test_dispatch_regression.py
```

### 0.3 HTML 同步備份（健檢 PASS 後）

```powershell
Copy-Item threads_wedding_ring_dashboard.html index.html -Force
python tools\dashboard_check.py    # 再驗一次，確認主檔與 index 一致
```

### 0.4 認證預檢 ＋ 憑證掃描

```powershell
python tools\secret_scan.py
"scan exit = $LASTEXITCODE"

gh auth status
"auth exit = $LASTEXITCODE"
```

`secret_scan` 回 exit 1 **不一定是阻塞**。判斷方式：

| 命中類型 | 處置 |
|---|---|
| 僅「檔名命中提示規則」 | ✅ 放行（檔名含 token/credential 等字樣而已） |
| `SIGNAL_ONLY`（32 hex、15 位數字等） | ✅ 放行，確認是已知 fixture 或平台 ID |
| `HIGH_CONFIDENCE` 且為**新增**命中 | ⛔ 停止，走 credential incident |
| `HIGH_CONFIDENCE` 但為既有已知項（如 `.github_token`） | ⚠️ 確認該檔不在同步腳本的複製範圍內才放行，並持續列為待撤銷 |

`gh auth status` FAIL → 請使用者跑 `gh auth login`，**不得 fallback 到 token 檔**。

### 0.5 上傳：兩條鏈分開跑

```powershell
$gitBash = @(
  "$env:ProgramFiles\Git\bin\bash.exe",
  "${env:ProgramFiles(x86)}\Git\bin\bash.exe",
  "$env:LOCALAPPDATA\Programs\Git\bin\bash.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

& $gitBash github_push.sh          # HTML 鏈
"push exit = $LASTEXITCODE"

& $gitBash repo_sync_docs.sh       # 文件與工具鏈
"sync exit = $LASTEXITCODE"
```

### 0.6 除錯對照表（依實際訊息判，不要猜）

| 症狀 | 真正原因 | 處置 |
|---|---|---|
| `Windows 子系統 Linux 版 沒有已安裝的發佈` | `bash` 打到 WSL，腳本**沒被執行** | 用 `& $gitBash`，見 §1。**不是部署失敗** |
| `gh auth status` PASS 但 push 回「token 無效或無權限」 | git credential helper 失效（常見於重開機後） | `gh auth setup-git`，見 §2.1 |
| 腳本 push FAIL 但手動 push 成功 | 未查明（技術債 §5-5） | 見 §0.7 取得真正錯誤 |
| GitHub 擋下 push，指向某行 fixture | Push Protection 命中連續字串常值 | 見 §6，改 runtime 組裝。**不得 bypass** |
| `deploy_verify.sh` exit 1 且顯示「僅行尾不同」 | CRLF 環境問題 | 檢查 `core.autocrlf`，不是漏推 |
| `deploy_verify.sh` exit 2 | 讀不到遠端 | `UNKNOWN`，**不得記成已發布或未發布** |

### 0.7 取得腳本吞掉的真正錯誤

兩支腳本都用 `2>/dev/null` 吞掉 push 的 stderr，失敗訊息是它自己推斷的。要看 git 真正說什麼：

```powershell
$tmp = Join-Path $env:TEMP "trumi-authprobe"
Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
git clone --depth 1 https://github.com/lueng0818/tru-mi-threads-dashboard.git $tmp
cd $tmp
git remote -v
git config --get credential.https://github.com.helper
git commit --allow-empty -m "auth probe"
git push origin main
"push exit = $LASTEXITCODE"
cd "$env:USERPROFILE\Documents\Claude專區\Tru-Mi專區"
```

錯誤訊息對應：`could not read Username` → helper 沒接上｜`403` → 權限｜
`protected branch` → 分支保護｜`repository not found` → repo 名稱或可見性

### 0.8 緊急手動同步（一次性，非標準做法）

僅在 `repo_sync_docs.sh` 失敗且資產有遺失風險時使用。
**優點是多了腳本沒有的 commit 前 diff 審查**。

```powershell
cd "$env:USERPROFILE\Documents\Claude專區\Tru-Mi專區"
$src = $PWD.Path
$tmp = Join-Path $env:TEMP "trumi-docsync"
Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
git clone --depth 1 https://github.com/lueng0818/tru-mi-threads-dashboard.git $tmp

New-Item -ItemType Directory -Force -Path "$tmp\references","$tmp\tools" | Out-Null
Copy-Item "$src\references\*.md"  "$tmp\references\" -Force
Copy-Item "$src\references\*.txt" "$tmp\references\" -Force -ErrorAction SilentlyContinue
Copy-Item "$src\tools\*.py"       "$tmp\tools\"      -Force
Copy-Item "$src\SKILL.md"         "$tmp\SKILL.md"    -Force

cd $tmp
git add -A
git status --short          # ← 停下來看：有沒有憑證檔？有沒有意外刪檔？
git diff --cached --stat
```

**diff 確認乾淨後**（分支狀態須為 `ahead N` 且無 `behind`）：

```powershell
git fetch origin; git status -sb
git -c user.name="Tru-Mi Bot" -c user.email="lueng1314@gmail.com" commit -m "<描述這次保全什麼>"
git push origin main
git log -1 --pretty='%H'; git rev-parse origin/main   # 兩者必須相同
```

被 Push Protection 擋下時：**修來源 → 複製進 `$tmp` → `git add -A` → `git commit --amend --no-edit` → push**。
⛔ 不產生第二個修正 commit，⛔ 不使用 unblock／bypass。

### 0.9 Remote Verification（必做，`push exit 0` 不等於已發布）

```powershell
# HTML 鏈
& $gitBash tools/deploy_verify.sh
"verify exit = $LASTEXITCODE"     # 0=DEPLOY_VERIFIED  1=遠端落後  2=UNKNOWN

# 文件鏈（目前只能人工，見 §5-1）
gh api repos/lueng0818/tru-mi-threads-dashboard/contents/references/daily-sop.md --jq '.size'
gh api repos/lueng0818/tru-mi-threads-dashboard/contents/tools/runlock.py --jq '.name'
gh api repos/lueng0818/tru-mi-threads-dashboard/contents/.github_token --jq '.name' 2>&1 | Select-Object -First 1
```

前兩者回數值與檔名；**第三者必須回 404 / Not Found**。

### 0.10 收尾：checkpoint ＋ release

```powershell
cd "$env:USERPROFILE\Documents\Claude專區\Tru-Mi專區"
$h1 = (Get-FileHash threads_wedding_ring_dashboard.html -Algorithm SHA256).Hash.ToLower().Substring(0,16)
$h2 = (Get-FileHash index.html -Algorithm SHA256).Hash.ToLower().Substring(0,16)

python tools\runlock.py checkpoint --instance "<instance_id>" `
  --validated "dashboard_check:PASS exit0" `
  --expect "threads_wedding_ring_dashboard.html=$h1" `
  --expect "index.html=$h2" `
  --note "<這次寫了什麼>"

python tools\runlock.py release --instance "<instance_id>"
```

release 印出 `WARN 鎖期間來源檔被改動` 時，**必須寫進摘要**——代表有 writer 沒走鎖。

### 0.11 完成判定

```
✅ 可以說「已發布」的條件（缺一不可）
   dashboard_check exit 0
 ＋ 主檔與 index.html hash 相同
 ＋ push exit 0
 ＋ deploy_verify exit 0（HTML）
 ＋ 文件鏈 remote 查詢回傳預期內容
 ＋ .github_token 查詢回 404
 ＋ lock 已 release
```

⛔ 只做到 local validation 不算完成。
⛔ `push exit 0` 不算完成。
⛔ 規格已定案不能代替實作完成。

---

## 1. ⚠️ Windows 的 `bash` 不是 Git Bash

這台機器上 PATH 的 `bash` 指向 `wsl.exe`，而系統**沒有安裝任何 WSL 發佈**。
在 PowerShell 直接打 `bash github_push.sh`，得到的是
「Windows 子系統 Linux 版 沒有已安裝的發佈」——**腳本根本沒有被執行**。

這個失敗模式危險在於它**不回任何表定的 exit code**：不是 `OK`、不是 `FAIL`、
也不是 `DEPLOYMENT_NOT_AVAILABLE_IN_THIS_RUNTIME`。
若記成「推送失敗」會誤導，正確判讀是 **interpreter 選錯，不是部署失敗**。

### 標準呼叫方式

```powershell
cd "$env:USERPROFILE\Documents\Claude專區\Tru-Mi專區"

$gitBash = @(
  "$env:ProgramFiles\Git\bin\bash.exe",
  "${env:ProgramFiles(x86)}\Git\bin\bash.exe",
  "$env:LOCALAPPDATA\Programs\Git\bin\bash.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $gitBash) { "找不到 Git Bash，請先安裝 Git for Windows" }
else {
  & $gitBash github_push.sh
  "push exit = $LASTEXITCODE"
  & $gitBash tools/deploy_verify.sh
  "verify exit = $LASTEXITCODE"
}
```

⚠️ 這只是換 interpreter，**不是改腳本**。
`github_push.sh` 與 `tools/deploy_verify.sh` 的內容**不得修改**。

⛔ **不得**為了避開這件事而在 PowerShell 重寫一份 clone／commit／push 的等價實作——
那會變成第二份部署邏輯，是 drift 的來源。

> **一次性例外（2026-09-11）**：`repo_sync_docs.sh` 在 Git Bash 下 push 失敗但同樣操作
> 在 PowerShell 成功時，曾以手動等價步驟完成一次緊急資產保全。
> 那是 recovery 手段，**不是新的標準做法**。原因未查明，見 §5 技術債。

---

## 2. Git Auth Gate（R-8.5 preflight）

**Canonical owner：`GITHUB-AUTH-STANDARD.md`。** 以下只是操作面。

```
gh auth status
  PASS → 繼續
  FAIL → AUTH_REQUIRED，停止 publication，請使用者執行 gh auth login
         ⛔ 不得 fallback 到 .github_token
```

`gh auth status` 是 **preflight**；腳本內建的檢查是 **enforcement**。兩層都保留。

### 2.1 ⚠️ `gh auth status` 過 ≠ `git push` 會過

兩者驗的不是同一件事：

```
gh auth status   → gh 自己的 token（keyring）
git push         → 需要 credential helper 把 token 交給 git
```

**重新開機後 credential helper 可能失效**（2026-09-11 實測）。
此時 `gh auth status` 顯示正常，但 push 回「token 無效或無權限」。

修法（這是認證標準本來就指定的機制，不是建 token 檔）：

```powershell
gh auth setup-git
```

⚠️ `gh auth login` 設的是 git protocol，`gh auth setup-git` 設的才是 credential helper。
**push 要的是後者，不能跳。**

---

## 3. 兩條發布鏈是分開的

```
github_push.sh    → threads_wedding_ring_dashboard.html, index.html
repo_sync_docs.sh → references/*.md, references/*.txt, tools/*.py, SKILL.md
```

`tools/deploy_verify.sh` 的 `FILES` **只驗兩份 HTML**。

⛔ **HTML 的 `DEPLOY_VERIFIED` 不能用來宣稱 Markdown／工具也已備份。**
兩條證據鏈要分開看、分開驗。

### 3.1 Markdown remote verification（目前只能人工）

```powershell
gh api repos/lueng0818/tru-mi-threads-dashboard/contents/references/daily-sop.md --jq '.size'
gh api repos/lueng0818/tru-mi-threads-dashboard/contents/tools/runlock.py --jq '.name'
gh api repos/lueng0818/tru-mi-threads-dashboard/contents/.github_token --jq '.name' 2>&1 | Select-Object -First 1
```

前兩者應回數值與檔名；**第三者必須回 404 / Not Found。**

---

## 4. Definition of Done

```
修改
→ local validation（dashboard_check.py exit 0）
→ gh auth status（preflight）
→ sync
→ Git diff review
→ secret gate
→ commit
→ push
→ remote verification
→ Jessica 實測（需要時）
```

**任一 Gate FAIL → 停止，不得為了「自動更新」強行推送。**

人工邊界只剩兩處：**首次／失效時的 `gh auth login`**，以及 **Jessica 的功能實測與內容決策**。

### 4.1 LF/CRLF 警告不是錯誤

`LF will be replaced by CRLF` 是 Git for Windows 的常態提示。
**以 `deploy_verify.sh` 的 hash 逐檔比對結果為準**
（2026-09-10 實測：有此提示但 hash 相符）。

`deploy_verify.sh` 本身已用 `-c core.autocrlf=false -c core.eol=lf` clone，
比對的是 repo 儲存的 blob，不是被平台翻譯過的工作副本。

---

## 5. 技術債

| # | 項目 | 影響 | 狀態 |
|---|---|---|---|
| 1 | **Markdown 沒有 remote verifier** | `references/*.md` 是否成功備份只能人工查。不得用 HTML 的 `DEPLOY_VERIFIED` 代替 | 待辦。修法：另建只驗 Markdown 的 verifier，**不得改 `deploy_verify.sh`** |
| 2 | **`repo_sync_docs.sh` 未在每日排程中執行** | HTML 天天驗證，文件與工具可數週無備份而無人察覺。2026-09-11 發現 867 行 SOP ＋ 6 支工具 ＋ 2 份事故紀錄從未進 repo | 待辦 |
| 3 | **兩支腳本用 `2>/dev/null` 吞掉 push 的 stderr** | 失敗時只能猜原因，「token 無效或無權限」是腳本自己推斷的，不是 git 說的 | 待辦。腳本在禁改清單內，需獨立決策 |
| 4 | **`repo_sync_docs.sh` 無 commit 前 diff 斷點** | clone→copy→commit→push 一氣呵成，無法在 commit 前審 diff，與 Definition of Done 衝突 | 待辦 |
| 5 | **`repo_sync_docs.sh` 在 Git Bash 下 push 失敗，同操作在 PowerShell 成功** | 原因未查明。2026-09-11 曾以手動等價步驟繞過一次 | 待查 |
| 6 | **`secret_scan.py` fixture 的雙向衝突** | 完整靜態 fixture 會被 GitHub Push Protection 擋；但 fixture 又必須存在才有 coverage | **已處理**：改 runtime 組裝，見 §6 |

---

## 6. GitHub Push Protection 與 secret fixture

**2026-09-11 事件**：commit `f6f0096e` 被擋，原因是
`tools/test_secret_scan_regression.py:55` 的 Slack API Token positive fixture。

**關鍵理解**：GitHub 掃的是**原始檔案文字**。
只要出現「單一連續字串常值」符合已知 secret 格式就會擋。
已用 `+` 拆開的（`"AIza" + "B" * 35`）不會被擋。

**處置**（未使用 bypass、未降低 detector 靈敏度、未刪除 coverage）：

```python
def _j(*parts):
    return "".join(parts)

"slack_token": _j("xox", "b-", "1111111111", "-2222222222", "-AbCdEfGhIjKlMnOp")
```

組出來的值與拆分前**逐字元相同**，S1/S2 結果不變，37/37 regression 通過。
同批修掉 JWT、private key header、URL userinfo 三條同類風險。

### 6.1 新增 fixture 時的規則

若該格式屬於 GitHub 會掃的類型（Slack／OpenAI／Google／AWS／GitHub token／
private key／JWT／URL userinfo 等），**一律用 `_j()` 組裝，不要寫成一整串。**

⛔ 不得用 bypass、不得降低 detector 靈敏度、不得刪除 regression coverage 來讓 push 過關。

---

## 7. 憑證現況（SECURITY ACTION）

```
.github_token   sha256 91094b0353cc2124   93B / 1 行   mtime 2026-08-07
                🔴 命中 github_pat  HIGH_CONFIDENCE
                撤銷狀態：尚未撤銷
```

**系統已不依賴它**：`gh auth status` 顯示走 keyring 的 `gho_` OAuth token。
**且它不在任何同步腳本的複製範圍內**（已靜態分析確認），remote 查詢回 404。

→ 剩下的只有**撤銷與清除**：請到 GitHub 設定撤銷該 PAT 再刪檔。

同目錄另有 `token.txt`（8 行）與 `meta tmp pw.txt`（20 行），
僅檔名命中提示規則、內容未命中憑證格式，建議一併改名。

⛔ 不得建立 `.github_token`／`token.txt` 等明碼檔，不得把 PAT 寫進腳本、`.git/config`、
remote URL 或任何純文字檔，不得向使用者索取 token 字串。
回報憑證問題時只講「命中筆數、檔案類型、行號、憑證類型、是否已撤銷」，**不輸出憑證原值**。
