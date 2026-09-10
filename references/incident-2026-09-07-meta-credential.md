# INCIDENT 2026-09-07-B｜SUSPECTED META CREDENTIAL EXPOSURE

```
Incident              : 2026-09-07-B
Classification        : SUSPECTED META SECRET
Observed strings      : 2 unique
String identity       : DISTINCT
Credential identity   : UNCONFIRMED
Asset identity        : UNCONFIRMED
Validity              : UNCONFIRMED
Human revocation gate : PASS（人工回報 attestation，2026-09-07）
Compromise            : NOT ESTABLISHED
File cleanup          : DONE（2026-09-07 14:25，tombstone 覆寫）
Count-only verify     : PASS（目標檔明碼命中 = 0）
Residual scan         : IN PROGRESS（全樹遞迴，見 §6）
Containment           : PENDING VERIFICATION
Related            : incident-2026-09-07-concurrency.md（GitHub credential，獨立事件）
Tru-Mi Deployment  : HOLD（本事件的暫時性控制，非因已證實入侵）
```

> **獨立於 GitHub credential incident。**
> GitHub 那件的既有結論不因本件回退；本件也不被那件的結案涵蓋。
> 兩者的資產、授權範圍、撤銷路徑都不同。

---

## 1. 發現經過

2026-09-07 第二輪憑證掃描時，於工作資料夾根目錄發現 `meta tmp pw.txt`。
第一輪漏掉的原因與補救見 §5。

## 2. 證據（安全 fingerprint，未輸出任何原值）

```
路徑    : Tru-Mi專區/meta tmp pw.txt
sha256  : 78546f09abfc693c6fc05effedecd77a98821c8a6a6e3733da916c94620dd9b6
大小    : 771 bytes / 4 行（其中 2 行有內容、2 行空白）
mtime   : 2026-07-14 14:33:37
```

逐行結構（長度／字元類別／Shannon entropy，count-only）：

| 行 | 長度 | 字元類別 | entropy | 以空白分隔的段數 |
|---|---|---|---|---|
| L1 | 469 | lower+upper+digit+punct | 5.90 | 2 |
| L2 | 0 | — | — | 0 |
| L3 | 0 | — | — | 0 |
| L4 | 296 | lower+upper+digit+punct | 5.86 | 2 |

偵測規則命中數（ruleset **v1**，count-only）：

| 規則 | 命中 | 說明 |
|---|---|---|
| `meta_user_or_page_token`（`EAA…`） | **2** | 兩個候選 token，不是一個 |
| `meta_app_secret_like`（32 hex） | **1** | ⚠️ 32 hex 也可能是 MD5／其他雜湊，**單獨不足以判定** |
| `meta_app_id_like`（15-17 位數字） | **2** | ⚠️ 同樣可能誤判 |
| `line_channel_token`（長 base64） | 2 | ⚠️ **極可能與上面的 2 個 `EAA` 是同一批字串**——EAA token 本身就是長 base64。**不得與 `meta_user_or_page_token` 相加**，否則會把 2 個候選誇大成 4 個 |
| github_pat／github_classic／slack／openai／google_api／aws_akid／jwt／bearer／url-userinfo／private_key | 0 | — |

命中總數 ≠ 憑證數量。規則之間會重疊，**跨規則相加是錯的**。

### 受控去重（完整字串 sha256，未輸出任何原值）

行數與規則命中數都不能拿來推算憑證數量，所以另外做了一次字串層去重：

| # | 行 | 長度 | sha256[:16] |
|---|---|---|---|
| 1 | L1 | 285 | `9ceefa2a5bf9044a` |
| 2 | L4 | 198 | `320b41eeadb4eeba` |

**unique = 2**（兩個 fingerprint 相異，不是同一把出現兩次）。

⚠️ **但「兩個相異字串」仍不等於「兩把不同資產的憑證」。** 可能是：
- 同一個 App 底下的不同 token（例如 user token 與 page token）
- 同一把 token 的新舊版本
- 分屬不同資產

長度差異（285 / 198）與此三種情形都相容，**結構分析無法再往下判**。
身分判定只能在 Meta 官方介面完成。

### ⚠️ 這些數字**不能**被讀成什麼

- **「3 行」不等於三把憑證。** 實際是 4 行、2 行有內容，內含至少 2 個 token 候選。
- **前綴命中不等於憑證有效。** `EAA` 是強線索，但只憑前綴無法證明它是可用的 Meta access token。
- **「未曾撤銷」是錯的寫法。** 正確狀態是 **目前沒有撤銷證據**（`REVOCATION_UNCONFIRMED`），
  不是「已驗證仍然有效」。兩者的差別在於前者不需要證據、後者需要。
- **檔名叫 `pw` 不代表整份都是 token。** 內容可能混有 App Secret、密碼或其他平台憑證，
  需分別判定、分別處置。
- **entropy 高不等於是秘密**，低也不等於安全。這裡只用它描述結構，不用它下結論。

## 3. 處置順序（先授權能力，後檔案殘留）

### 步驟 1 — 於 Meta 官方介面確認並撤銷（資產擁有者在 Windows 端操作）

先確認憑證所屬：**哪個 App、屬於使用者／粉絲專頁／System User、授權範圍為何**。
Meta access token 可能代表使用者、應用程式或粉絲專頁，撤銷路徑依類型而異。

- 一般 App：Meta for Developers → 應用程式管理
- 商業資產或 System User：Meta Business Settings → 由管理者檢查

⛔ **在確認 token 類型之前，不要重設整個 IG／FB 帳號或刪除應用程式**——
會造成不必要的服務中斷。
⛔ **不要只產生新 token 就假設舊的已失效。** 多數情況下舊 token 仍然有效，
必須明確撤銷授權或輪替憑證。

### 步驟 2 — 保留證據後消毒檔案

記錄：檔案 hash、非敏感 fingerprint、命中數、位置、處置時間（§2 已備妥）。
確認沒有必要的獨有設定（例如 App ID 這類非機密但有用的值需要另存）後，
將秘密值覆寫為 metadata tombstone，或經核准刪除。

⛔ **不得**把原值貼進聊天、終端輸出或任何報告。

### 步驟 3 — 驗證與獨立結案

`containment complete` 需要四項證據齊備：

```
① 舊授權確認失效（在 Meta 介面驗證，不是靠「有沒有報錯」推測）
② 目標檔明碼命中 = 0
③ 相關依賴已更新，或確認無任何流程使用該憑證
④ 記錄本次掃描的 ruleset 版本、掃描範圍與排除項目
```

## 4. 需要回報的最小資訊

| 欄位 | 回報內容 |
|---|---|
| 憑證類型 | User／Page／System User／App，或仍無法確認 |
| 撤銷結果 | 已撤銷／已輪替且舊憑證失效／無法確認 |
| 完成時間 | 日期與時間（含時區） |

兩個候選若屬**不同資產或不同授權，請分別回報**；若在 Meta 介面確認是同一把，
只需回報去重結果。

⛔ **不要**把 token、App Secret、完整授權 URL 或含秘密的截圖貼進對話。

## 5. 掃描規則的教訓（升格為偵測規則，但不等於完整覆蓋）

第一輪漏掉本檔的原因：
- 檔名比對只找 `token|secret|credential|pem|key` —— 它叫 `pw`
- 內容比對只找 `password`／`pw`／`@`／`http` —— 沒找 `EAA`

修正：平台前綴清單已寫進 `tools/secret_scan.py` 的 ruleset。**但這不是覆蓋率保證。**

- `EAA`、`sk-` 這類短前綴**既可能誤判、也可能漏掉**其他格式
- 完整偵測應結合：格式、上下文、entropy、已知供應商 detector、以及安全的驗證方式
- **掃描結果必須標明 ruleset 版本、掃描範圍與排除項目**
- ⛔ **不得因 pattern count = 0 就宣稱「沒有任何秘密」**——
  那只證明「這個版本的規則在這個範圍內沒有命中」，兩者不是同一件事

### 擴充 ruleset 的門檻（`tools/test_secret_scan_regression.py`，18/18 通過）

**只加一條前綴就宣稱「覆蓋更完整」是沒有證據的說法。** 每新增一條規則，必須同時新增：

```
① positive fixture — 該格式應被抓到
② negative fixture — 不該被這條規則抓到的相似字串
③ 已知易誤判者，把誤判樣本放進 negative，並在 RULES 標註風險
沒有 fixture 的規則不算完成（S3 會擋）
```

目前 14 條規則：9 條有 fixture，5 條**列名豁免並附理由**
（`meta_app_secret_like`／`meta_app_id_like`／`line_channel_token`／
`openai_key`／`bearer_header`——都是結構上無法與一般字串區分的規則，
它們只作為人工複核線索，不單獨構成判定）。

測試裡全部使用合成字串，不含任何真實憑證。
**S4 鎖的是最重要的一條性質：掃描結果永遠不得包含命中的字串本身。**
掃描器一旦把秘密印進報告或 log，它就從防護變成外洩管道。

---

## 6. Containment 執行紀錄（2026-09-07）

### 人工 gate — PASS（attestation）

使用者回報已於 Meta 官方介面完成處置。**記為人工 attestation，不再要求提供 token
或重複撤銷操作。** 但下列欄位仍為 UNCONFIRMED，因為 Agent 端沒有獨立證據：
credential identity／asset identity／validity。

⚠️ **處置證據鏈仍有一段缺口**：fingerprint 層已把候選拆成 A／B 兩筆，
但目前的人工回報是整體 PASS，沒有逐一對應到 A、B。
若日後需要稽核「哪一把在何時被如何處置」，這一段接不起來。
補完只需下表四格，不需要任何 token 值：

| 候選 | fingerprint | 憑證類型／資產 | 撤銷結果 | 完成時間 |
|---|---|---|---|---|
| A | `9ceefa2a5bf9044a`（L1, len 285） | 待填 | 待填 | 待填 |
| B | `320b41eeadb4eeba`（L4, len 198） | 待填 | 待填 | 待填 |

**兩者若最終證實屬同一資產，仍分別記錄 A／B 的處置結果**，
這樣 fingerprint → 處置證據的鏈才不會斷。

### 檔案消毒 — DONE

```
執行時間 : 2026-09-07 14:25（+08:00）
方式     : tombstone 覆寫（非刪除）
前置斷言 : 消毒前 sha256 與事件檔記錄相符才動手，不符即中止
消毒前   : 78546f09abfc693c… / 771 bytes / 4 行
消毒後   : 2cc8aaa16d59a9ad… / 1221 bytes / 20 行
```

為什麼是覆寫不是刪除：工作資料夾是雲端掛載磁碟，`os.remove` 回
`Operation not permitted`（與 runlock 遇到的是同一個限制）。
tombstone 內含 fingerprint 與處置說明，**不含任何秘密值**，且不觸發任何偵測規則。
要真正移除檔案需在 Windows 端執行 `Remove-Item`。

### Count-only 驗證 — PASS

```
meta tmp pw.txt : sha256 2cc8aaa16d59a9ad  1221 bytes
                  pattern 命中 = 0（僅檔名命中提示規則 → 🟡）
```

### Same-class residual scan — IN PROGRESS

```
ruleset : v1 (2026-09-07)
範圍    : 工作資料夾遞迴全樹
排除    : .git / node_modules / __pycache__ / .tmp / .codex_tmp /
          .playwright-cli / venv / .venv；二進位副檔名；單檔上限 2MB
狀態    : 執行中（雲端掛載磁碟 I/O 極慢，已逾 12 分鐘）
```

⛔ **這一項未完成前不得標記 `CONTAINMENT_COMPLETE`。**
根目錄 76 檔的掃描已完成（僅 `.github_token` 仍有 HIGH_CONFIDENCE 命中，屬事件 A），
但**根目錄乾淨不等於全樹乾淨**——這正是第一輪漏掉本檔的同型錯誤。

### 結案條件（尚未滿足）

```
① 舊授權確認失效        → 人工 attestation PASS（Agent 端無獨立證據）
② 目標檔明碼命中 = 0     → ✅ PASS
③ 相關依賴已更新／確認不使用 → 待確認
④ same-class residual scan 完成 → 執行中
⑤ residual review（人工複核掃描結果） → 未進行
```

⚠️ `incident closed` 不等於 `count = 0`。還取決於 ④⑤ 是否完成。

---

## 附：三個檔案的判定狀態

| 檔案 | 判定 | 下一步 |
|---|---|---|
| `.github_token` | `REVOKED SECRET / FILE RESIDUAL`（依既有證據） | 受控清理 |
| `token.txt` | `NO KNOWN SECRET PATTERN / TOMBSTONE` | 可保留或另案刪除 |
| `meta tmp pw.txt` | **`SUSPECTED META SECRET / REVOCATION_UNCONFIRMED`** | **優先確認授權與 containment** |
