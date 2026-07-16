# ChatGPT Work + Claude Repo Workflow

適用 repo:
- `lueng0818/tru-mi-threads-dashboard`

本地來源檔:
- `C:\Users\Tilandky Ho\Documents\Claude專區\Tru-Mi專區\index.html`

線上網址:
- `https://lueng0818.github.io/tru-mi-threads-dashboard/`

## 目標

讓 ChatGPT Work 與 Claude 可以共同維護同一個 dashboard repo，但不互相覆蓋、也不只更新到本地或 GitHub repo 而忘記確認 live 頁面。

## 角色分工

### ChatGPT Work

適合負責:
- Threads 海巡分析
- 貼文等級判讀
- 八段式內容草稿
- Jessica 觀察
- 內容策略整理
- 排程 prompt 規則更新

輸出要求:
- 明確指出要更新哪一張卡、哪個區塊、哪個等級
- 若改動 dashboard 結構，必須說明是新增元件、替換元件，還是只補資料
- 若要推版，必須要求最終驗證 raw GitHub 與 live Pages

### Claude

適合負責:
- 本地檔案編修
- HTML/JS/CSS 結構修正
- 去重與版本整合
- Git 推送
- raw GitHub 驗證
- live GitHub Pages 驗證
- 排程落地到 Codex automation

輸出要求:
- 不能只說「已推送」
- 必須同時檢查:
  - repo `main`
  - `raw.githubusercontent.com`
  - GitHub Pages live URL

## 單一來源原則

每次更新都以這份本地檔案作為 source of truth:

- `C:\Users\Tilandky Ho\Documents\Claude專區\Tru-Mi專區\index.html`

不要直接把舊 clone 裡的 `index.html` 當成主來源覆回來。
先確認本地工作檔是否仍包含目前有效結構，例如:

- `海巡分級中心`
- `gradeChipGrid`
- `renderGradeHub`
- `複製回覆`

## 更新流程

1. 先讀本地 `index.html`
2. 確認目前結構仍是 ABCD grading dashboard 版本
3. 再做本週貼文或結構更新
4. 本地驗證以下標記仍存在:
   - `海巡分級中心`
   - `gradeChipGrid`
   - `renderGradeHub`
   - `複製回覆`
5. 推送到 `lueng0818/tru-mi-threads-dashboard`
6. 驗證 raw GitHub:
   - `https://raw.githubusercontent.com/lueng0818/tru-mi-threads-dashboard/main/index.html`
7. 驗證 live Pages:
   - `https://lueng0818.github.io/tru-mi-threads-dashboard/`
8. 只有在 live 頁面也驗證成功後，才能回報「已更新完成」

## 驗證標準

### 本地檢查

至少確認:
- 頁面有 `海巡分級中心`
- 頁面有 A/B/C/D 分級卡
- 可看到 `複製回覆`
- `index.html` 只有一組有效的 `<script> ... </script>` 收尾
- 沒有舊殘留內容跑在 `</html>` 後面

### Raw GitHub 檢查

至少確認:
- raw 檔包含 `海巡分級中心`
- raw 檔包含 `renderGradeHub`

### Live Pages 檢查

至少確認:
- live 頁面包含 `海巡分級中心`
- live 頁面包含 `複製回覆`
- live 頁面不是舊版 archive 結構

## 如果 Pages 沒更新

若 raw 已更新、live 仍未更新:

1. 等待數分鐘再查一次
2. 若仍未更新，可再推一次極小變更觸發 Pages redeploy
3. 若還是不變，回報:
   - repo `main` 已更新
   - live Pages 仍 stale
   - 不能宣稱已完全完成

## 避免互相覆蓋的規則

- ChatGPT Work 若只是提出內容草稿，不要直接把不完整 HTML 當完成版
- Claude 推送前，要先確認本地 `index.html` 沒被其他流程覆寫成舊版
- 若遠端 `main` 被其他版本覆蓋，先比對本地 source-of-truth 再重推
- 若要重建 automation，需同步更新 prompt 裡的 repo 驗證規則

## Commit 建議

內容更新:
- `Daily dashboard update YYYY-MM-DD`
- `Update weekly Threads cards`

結構更新:
- `Add ABCD grading control center`
- `Fix dashboard HTML tail`
- `Preserve grading dashboard structure`

部署補救:
- `Republish ABCD grading dashboard`
- `Trigger Pages redeploy`

## 每次完成後要記錄

至少記錄:
- 更新了哪些卡片或區塊
- 是否推到 repo
- raw 是否成功
- live Pages 是否成功
- 若失敗，失敗在 repo、raw、還是 live

## 建議共管方式

最穩定的協作方式是:

- ChatGPT Work 負責內容決策與貼文分析
- Claude 負責本地落版、驗證、推送、部署確認

也就是:
- ChatGPT Work 負責「寫什麼」
- Claude 負責「怎麼落地且真的上線」
