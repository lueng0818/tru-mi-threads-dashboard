#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tru-Mi 每日排程的開跑前情報包（取代 Step 2 手動 grep 1.1MB HTML）

用法：
    python tools/dashboard_prep.py             # 人看的摘要
    python tools/dashboard_prep.py --json      # 給程式吃的 JSON
    python tools/dashboard_prep.py --check "@someone"   # 單筆查重，回 NEW / DUP

輸出：已收錄帳號清單、已收錄貼文連結清單、各分頁計數、
      最近 7 天追蹤列、留言行銷最後一筆日期、四個插入錨點的行號。
"""
import sys
import os
import re
import json

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(BASE, "threads_wedding_ring_dashboard.html")
PANELS = ["panel-comms", "panel-daily", "panel-budget", "panel-heritage"]


def load():
    s = open(MAIN, encoding="utf-8").read()
    authors = sorted(set(re.findall(r'class="post-author"><a[^>]*>(@[^<]+)</a>', s)))
    links = sorted(set(re.findall(r'class="post-link"[^>]*href="([^"]+)"', s)))
    # permalink 尾碼（Threads 的 post id），比整條網址更耐比對
    slugs = sorted({m.split("/post/")[-1].strip("/") for m in links if "/post/" in m})

    marks = sorted([(m.group(1), m.start()) for m in re.finditer(r'id="(panel-[a-z]+)"', s)],
                   key=lambda t: t[1])
    counts, anchors = {}, {}
    for i, (name, pos) in enumerate(marks):
        end = marks[i + 1][1] if i + 1 < len(marks) else len(s)
        counts[name] = s[pos:end].count('class="post-card')
        if name in PANELS:
            g = s.find('<div class="posts-grid">', pos, end)
            anchors[name] = s.count("\n", 0, g) + 1 if g != -1 else None

    tb = re.search(r'id="trackBody"(.*?)</tbody>', s, re.S)
    track = []
    if tb:
        for r in re.findall(r"<tr\b.*?</tr>", tb.group(1), re.S)[:7]:
            cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).strip()
                     for c in re.findall(r"<td\b[^>]*>(.*?)</td>", r, re.S)]
            track.append(cells)

    cb = re.search(r'id="commentLogBody"(.*?)</tbody>', s, re.S)
    comments = []
    if cb:
        for r in re.findall(r"<tr\b.*?</tr>", cb.group(1), re.S):
            cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).strip()
                     for c in re.findall(r"<td\b[^>]*>(.*?)</td>", r, re.S)]
            comments.append(cells)

    return {
        "file_mb": round(os.path.getsize(MAIN) / 1048576.0, 2),
        "lines": s.count("\n") + 1,
        "cards_total": sum(counts.get(p, 0) for p in PANELS),
        "counts": {p: counts.get(p, 0) for p in PANELS},
        "posts_grid_line": anchors,
        "authors": authors,
        "post_slugs": slugs,
        "track_recent": track,
        "comment_log": comments,
    }


def is_dup(d, needle):
    """帳號或 permalink 都可以丟進來；比對帳號名與 Threads post id。"""
    key = needle.strip().lower().rstrip("/")
    if "/post/" in key:
        key = key.split("/post/")[-1]
    else:
        key = key.split("/")[-1]
    key = key.lstrip("@")
    if key in {a.lower().lstrip("@") for a in d["authors"]}:
        return "帳號已收錄"
    if key in {x.lower() for x in d["post_slugs"]}:
        return "貼文已收錄"
    return None


def main():
    d = load()

    # 查重：可一次丟多個帳號或連結，這是每日 Step 2 的正式入口
    if "--check" in sys.argv:
        args = sys.argv[sys.argv.index("--check") + 1:]
        if not args:
            print("用法：--check @帳號 [貼文連結 ...]")
            return 2
        for a in args:
            why = is_dup(d, a)
            print(("DUP  %s（%s，跳過）" % (a, why)) if why else ("NEW  %s（可處理）" % a))
        return 0
    if "--authors" in sys.argv:
        print(" ".join(d["authors"]))
        return 0
    if "--slugs" in sys.argv:
        print(" ".join(d["post_slugs"]))
        return 0
    if "--json" in sys.argv:
        print(json.dumps(d, ensure_ascii=False, indent=1))
        return 0

    print("Tru-Mi 儀表板現況（%.2f MB / %d 行 / %d 張卡）" % (d["file_mb"], d["lines"], d["cards_total"]))
    print("  溝通%d 日常%d 預算%d 傳承%d"
          % (d["counts"]["panel-comms"], d["counts"]["panel-daily"],
             d["counts"]["panel-budget"], d["counts"]["panel-heritage"]))
    print("  插入錨點（.posts-grid 起始行）：%s"
          % "  ".join("%s=%s" % (k.replace("panel-", ""), v) for k, v in d["posts_grid_line"].items()))
    print("  去重池：帳號 %d 個、貼文 id %d 筆"
          % (len(d["authors"]), len(d["post_slugs"])))
    print("  （查重請用 --check @帳號 貼文連結…；要完整清單用 --authors / --slugs）")
    print("")
    print("最近 7 列效益追蹤：")
    for r in d["track_recent"]:
        print("  " + " | ".join(r))
    print("")
    print("留言行銷紀錄（%d 列）：" % len(d["comment_log"]))
    for r in d["comment_log"]:
        print("  " + " | ".join(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
