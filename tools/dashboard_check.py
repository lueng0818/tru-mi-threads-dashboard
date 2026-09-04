#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tru-Mi 儀表板健檢（把每日排程 prompt 裡的散文規則變成可執行的閘門）

用法：
    python tools/dashboard_check.py            # 檢查主檔
    python tools/dashboard_check.py --strict   # 把 WARN 也視為失敗

結束碼：0 = PASS（可進入 Step 6 同步／推送）；1 = FAIL（禁止推送）
"""
import sys
import os
import re
import json
import hashlib

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(BASE, "threads_wedding_ring_dashboard.html")
MIRROR = os.path.join(BASE, "index.html")
BASELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".css_baseline.json")

PANELS = ["panel-comms", "panel-daily", "panel-budget", "panel-heritage"]
TAB_KEY = {"comms": "panel-comms", "daily": "panel-daily",
           "budget": "panel-budget", "heritage": "panel-heritage"}
VALID_LEVELS = {"A", "B", "C", "D", "RISK"}

errors, warns, notes = [], [], []


def blank_out(s, tag):
    """把 <script>/<style> 內容換成等長空白，保留 offset 不變。"""
    def rep(m):
        return m.group(1) + (" " * len(m.group(2))) + m.group(3)
    return re.sub(r"(<" + tag + r"\b[^>]*>)(.*?)(</" + tag + r">)", rep, s, flags=re.S | re.I)


def scan_divs(s):
    """回傳 [(kind, pos, attrs, depth)]；kind: open / close。"""
    out, stack = [], []
    for m in re.finditer(r"<div\b([^>]*)>|</div>", s):
        if m.group(0).startswith("</"):
            if not stack:
                errors.append("多餘的 </div>，位置 offset=%d" % m.start())
                continue
            op = stack.pop()
            out.append(("close", m.start(), op[1], len(stack)))
        else:
            stack.append((m.start(), m.group(1)))
            out.append(("open", m.start(), m.group(1), len(stack) - 1))
    for pos, attrs in stack:
        errors.append("未關閉的 <div%s>，位置 offset=%d" % (attrs[:60], pos))
    return out


def main():
    strict = "--strict" in sys.argv
    if not os.path.exists(MAIN):
        print("FAIL: 找不到主檔 %s" % MAIN)
        return 1
    s = open(MAIN, encoding="utf-8").read()
    clean = blank_out(blank_out(s, "script"), "style")

    # ---------- 1. div 平衡與巢狀 ----------
    ev = scan_divs(clean)
    if s.count("<div") != s.count("</div>"):
        errors.append("全檔 <div> (%d) 與 </div> (%d) 不平衡"
                      % (s.count("<div"), s.count("</div>")))

    card_stack = []
    for kind, pos, attrs, depth in ev:
        is_card = "post-card" in attrs
        if kind == "open" and is_card:
            if card_stack:
                errors.append("post-card 巢狀：offset=%d 的卡片開在另一張卡片內" % pos)
            card_stack.append((pos, depth))
        elif kind == "close" and is_card and card_stack:
            card_stack.pop()

    # ---------- 2. 每個 panel 內卡片深度一致 ----------
    marks = sorted([(x.group(1), x.start()) for x in re.finditer(r'id="(panel-[a-z]+)"', clean)],
                   key=lambda t: t[1])
    for p in PANELS:
        hit = [pos for name, pos in marks if name == p]
        if not hit:
            errors.append("找不到 %s" % p)
            continue
        start = hit[0]
        after = [pos for _, pos in marks if pos > start]
        end = after[0] if after else len(clean)
        depths = {d for k, pos, a, d in ev
                  if k == "open" and "post-card" in a and start <= pos < end}
        if len(depths) > 1:
            errors.append("%s 內 post-card 深度不一致：%s（有卡片少關或多關 </div>）"
                          % (p, sorted(depths)))

    # ---------- 3. 卡片數 vs 分頁計數 vs summary-bar ----------
    counts = {}
    for i, (name, pos) in enumerate(marks):
        end = marks[i + 1][1] if i + 1 < len(marks) else len(clean)
        counts[name] = clean[pos:end].count('class="post-card')
    total = sum(counts.get(p, 0) for p in PANELS)

    for key, pid in TAB_KEY.items():
        m = re.search(r"switchTab\('" + key + r"'[^>]*>[^<]*<span class=\"count\"[^>]*>(\d+)</span>", s)
        if not m:
            warns.append("讀不到 %s 分頁的 count（結構可能被改過）" % key)
        elif int(m.group(1)) != counts.get(pid, -1):
            errors.append("分頁計數不符：%s 標示 %s，實際 %d 張卡"
                          % (key, m.group(1), counts.get(pid, -1)))

    m = re.search(r'<div class="summary-bar">.*?<div class="num">(\d+)</div>', s, re.S)
    if not m:
        warns.append("讀不到 summary-bar 的蒐集貼文數")
    elif int(m.group(1)) != total:
        errors.append("summary-bar 標示 %s，實際卡片總數 %d" % (m.group(1), total))

    # ---------- 4. data-level ----------
    n_cards = s.count('class="post-card')
    cards = re.findall(r'<div class="post-card"([^>]*)>', s)
    if len(cards) != n_cards:
        warns.append("post-card 開頭標籤格式不一致（%d/%d 可解析）" % (len(cards), n_cards))
    for a in cards:
        lv = re.search(r'data-level="([^"]*)"', a)
        if not lv:
            errors.append("有 post-card 缺 data-level：%s" % a[:80])
        elif lv.group(1) not in VALID_LEVELS:
            errors.append("data-level 值不合法：%s" % lv.group(1))
    kw = len(re.findall(r"data-keywords=", s))
    notes.append("data-keywords 覆蓋率 %d/%d（%.0f%%）" % (kw, n_cards, 100.0 * kw / max(n_cards, 1)))

    # ---------- 5. 表格欄數固定 8 ----------
    for tid in ("trackBody", "commentLogBody"):
        m = re.search(r'id="' + tid + r'"(.*?)</tbody>', s, re.S)
        if not m:
            errors.append("找不到 #%s" % tid)
            continue
        rows = re.findall(r"<tr\b.*?</tr>", m.group(1), re.S)
        for i, r in enumerate(rows):
            n = len(re.findall(r"<td\b", r))
            if n != 8:
                errors.append("#%s 第 %d 列有 %d 個 <td>（應為 8）" % (tid, i + 1, n))
        notes.append("#%s 共 %d 列" % (tid, len(rows)))

    # ---------- 6. 品牌護欄 ----------
    for bad, why in [("230,180,34", "舊金色"), ("8,77,44", "舊綠色")]:
        if bad in s:
            errors.append("出現禁用色碼 %s（%s），共 %d 處" % (bad, why, s.count(bad)))
    old_acct = re.findall(r"@trumi_jewelry(?![_a-z])", s)
    if old_acct:
        errors.append("出現已停用帳號 @trumi_jewelry，共 %d 處" % len(old_acct))

    # ---------- 7. :root 指紋（擋 CSS 漂移）----------
    m = re.search(r":root\s*\{(.*?)\}", s, re.S)
    if m:
        fp = hashlib.sha256(re.sub(r"\s+", "", m.group(1)).encode("utf-8")).hexdigest()[:16]
        if os.path.exists(BASELINE):
            old = json.load(open(BASELINE, encoding="utf-8")).get("root_fp")
            if old != fp:
                errors.append(":root 品牌色票被改動（baseline %s → 現在 %s）" % (old, fp))
        else:
            with open(BASELINE, "w", encoding="utf-8") as f:
                json.dump({"root_fp": fp}, f)
            notes.append("已建立 :root 指紋 baseline（%s）" % fp)
    else:
        warns.append("找不到 :root 區塊")

    # ---------- 8. 重複貼文 ----------
    # 註：重複連結是內容瑕疵（多半是貼錯 permalink），不影響頁面結構，
    # 所以列為 WARN 不擋推送；要當成硬錯誤請加 --strict。
    links = re.findall(r'class="post-link"[^>]*href="([^"]+)"', s)
    dup = sorted({x for x in links if links.count(x) > 1})
    if dup:
        warns.append("重複的 post-link（可能有卡片貼錯連結）：%s" % ", ".join(dup[:5]))
    authors = re.findall(r'class="post-author"><a[^>]*>(@[^<]+)</a>', s)
    rep = sorted({a for a in authors if authors.count(a) > 2})
    if rep:
        notes.append("同一帳號出現 3 次以上：%s" % ", ".join(rep[:8]))

    # ---------- 9. 主檔／備份一致 ----------
    if os.path.exists(MIRROR):
        a = hashlib.sha256(open(MAIN, "rb").read()).hexdigest()
        b = hashlib.sha256(open(MIRROR, "rb").read()).hexdigest()
        if a != b:
            warns.append("index.html 與主檔不一致（Step 6 尚未同步就會是這樣）")
    else:
        warns.append("找不到 index.html")

    # ---------- 輸出 ----------
    print("Tru-Mi 儀表板健檢")
    print("  檔案 %.2f MB / %d 行 / %d 張卡"
          % (os.path.getsize(MAIN) / 1048576.0, s.count("\n") + 1, n_cards))
    print("  分佈 溝通%d 日常%d 預算%d 傳承%d"
          % (counts.get("panel-comms", 0), counts.get("panel-daily", 0),
             counts.get("panel-budget", 0), counts.get("panel-heritage", 0)))
    for n in notes:
        print("  · %s" % n)
    for w in warns:
        print("  WARN %s" % w)
    for e in errors:
        print("  FAIL %s" % e)
    ok = not errors and not (strict and warns)
    print("")
    print("PASS：可進入 Step 6 同步與推送" if ok else "FAIL：先修好再同步，禁止推送")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
