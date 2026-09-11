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

# ---------- P1 schema（2026-09-11 新增）----------
# 規格正本：references/dashboard-spec.md §8、§9
#
# ⚠️ 這批驗證**只套用在遷移日之後收錄的卡片**（data-collected >= MIGRATION_DATE）。
# 既有 229 張舊卡沒有 P1 欄位，依 ia-migration-plan.md 決策 A 採 forward-only，
# 不回填。若對全部卡片套用，健檢會一次噴 229 個 FAIL，等於把閘門變成雜訊。
MIGRATION_DATE = "2026-09-12"

VALID_TOPICS = {"婚戒", "戒圍佩戴", "客製設計", "感情婚姻", "籌備婚禮", "新發現", "待分類"}
VALID_INTENTS = {"分享方法", "實際困擾", "求助", "不同觀點", "閒聊", "認同", "想知道後續"}
LISTENER_KEYS = ("他在說什麼", "建議怎麼接", "可以怎麼回")

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


def split_cards(s):
    """把 HTML 切成一張張 post-card 的原始片段。

    卡片在檔案裡是一整串（含換行），用下一個 post-card 的起點當切點即可，
    不需要完整 DOM 解析——這裡只要抓欄位，不需要知道巢狀結構。
    """
    starts = [m.start() for m in re.finditer(r'<div class="post-card"', s)]
    out = []
    for i, a in enumerate(starts):
        b = starts[i + 1] if i + 1 < len(starts) else len(s)
        out.append(s[a:b])
    return out


def attr(chunk, name):
    m = re.search(r'\b%s="([^"]*)"' % re.escape(name), chunk)
    return m.group(1) if m else None


def check_p1_schema(s):
    """P1 欄位驗證。規格：dashboard-spec.md §8／§9。

    只驗 data-collected >= MIGRATION_DATE 的卡片（forward-only，見檔頭說明）。
    舊卡缺欄位不算錯，那是預期狀態。
    """
    new_cards = []
    for chunk in split_cards(s):
        collected = attr(chunk, "data-collected")
        if collected and collected >= MIGRATION_DATE:
            new_cards.append(chunk)

    if not new_cards:
        notes.append("P1 schema：尚無遷移日（%s）之後的新卡，本節略過" % MIGRATION_DATE)
        return

    who = lambda c: (re.search(r'post-author"><a[^>]*>(@[^<]+)</a>', c) or [None, "?"])[1] \
        if re.search(r'post-author"><a[^>]*>(@[^<]+)</a>', c) else "?"

    bad = 0
    for c in new_cards:
        tag = who(c)

        # ① data-topic 合法（含「待分類」——證據不足時的正確答案，不是錯誤）
        topic = attr(c, "data-topic")
        if topic is None:
            errors.append("P1 %s 缺 data-topic" % tag); bad += 1
        elif topic not in VALID_TOPICS:
            errors.append("P1 %s data-topic 值不合法：%s" % (tag, topic)); bad += 1

        # ②③ 關鍵留言數量 1-5，且與 data-count 相符
        kc_box = re.search(r'<div class="key-comments"([^>]*)>(.*?)</div>\s*(?=<div class="listener-analysis")',
                           c, re.S)
        if not kc_box:
            errors.append("P1 %s 缺 .key-comments 區塊" % tag); bad += 1
        else:
            n_kc = len(re.findall(r'<div class="key-comment"', kc_box.group(2)))
            declared = attr(kc_box.group(1), "data-count")
            if not (1 <= n_kc <= 5):
                errors.append("P1 %s 關鍵留言 %d 則（必須 1-5；不得為 0，也不得硬湊超過 5）"
                              % (tag, n_kc)); bad += 1
            if declared is None or not declared.isdigit() or int(declared) != n_kc:
                errors.append("P1 %s data-count=%s 與實際 %d 則不符" % (tag, declared, n_kc)); bad += 1
            # ⑥ 少於 5 則要說明理由（WARN）——防止「湊不到就默默少寫」
            if n_kc < 5 and not attr(kc_box.group(1), "data-short-reason"):
                warns.append("P1 %s 只有 %d 則關鍵留言但未填 data-short-reason" % (tag, n_kc))

            # ④ 每則必帶合法 primary intent
            for m in re.finditer(r'<div class="key-comment"([^>]*)>', kc_box.group(2)):
                pi = attr(m.group(1), "data-intent-primary")
                if pi is None:
                    errors.append("P1 %s 有 .key-comment 缺 data-intent-primary" % tag); bad += 1
                elif pi not in VALID_INTENTS:
                    errors.append("P1 %s data-intent-primary 不合法：%s" % (tag, pi)); bad += 1
            # secondary signals 與 uncertainty 刻意不驗完整性：
            # 一則留言可以只有一種意圖，強制填會逼 AI 虛構（dashboard-spec §8.3）

        # ⑤ listener-analysis 三層齊全
        la = re.search(r'<div class="listener-analysis">(.*?)</div>\s*(?=<div class="convo-thread"|'
                       r'<div class="selection-evidence"|<div class="jessica-insight")', c, re.S)
        if not la:
            errors.append("P1 %s 缺 .listener-analysis" % tag); bad += 1
        else:
            missing = [k for k in LISTENER_KEYS if k not in la.group(1)]
            if missing:
                errors.append("P1 %s listener-analysis 缺：%s" % (tag, "、".join(missing))); bad += 1

        # ⑦ selection-evidence 的入選筆數要對得上
        se = re.search(r'<div class="selection-evidence">(.*?)</div>\s*(?=<div class="jessica-insight")',
                       c, re.S)
        if se and kc_box:
            picked = len(re.findall(r'data-picked="yes"', se.group(1)))
            n_kc = len(re.findall(r'<div class="key-comment"', kc_box.group(2)))
            if picked != n_kc:
                errors.append("P1 %s selection-evidence 入選 %d 筆，關鍵留言 %d 則，對不上"
                              % (tag, picked, n_kc)); bad += 1

        # ⑧ 有對話串就不能標 none
        if '<div class="convo-thread"' in c and attr(c, "data-convo") == "none":
            errors.append("P1 %s 有 .convo-thread 但 data-convo=none" % tag); bad += 1

    notes.append("P1 schema：檢查 %d 張新卡（遷移日 %s 起），%s"
                 % (len(new_cards), MIGRATION_DATE, "全部通過" if bad == 0 else "%d 項不合格" % bad))


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

    # ---------- 4.5 P1 schema（僅驗遷移日之後的新卡）----------
    check_p1_schema(s)

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
