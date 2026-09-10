#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
明碼憑證掃描（count-only，永不輸出原值）

    python tools/secret_scan.py                      # 掃工作資料夾根目錄
    python tools/secret_scan.py --path <dir> --recursive
    python tools/secret_scan.py --json

⛔ 這支工具**不證明「沒有秘密」**。
   count = 0 只代表「ruleset v1 在本次宣告的範圍內沒有命中」。
   這兩件事不是同一件事，報告時不得互相替換。

為什麼要有版本與範圍宣告（2026-09-07 教訓）：
  第一輪掃描漏掉 `meta tmp pw.txt`，因為檔名只比對了
  token|secret|credential|pem|key（它叫 pw），內容只比對了
  password|pw|@|http（沒比 EAA）。當時的結論寫成「沒有其他 token 檔」，
  但實際上只證明了「那組關鍵字沒命中」。
  → 所以每次輸出都必須帶 ruleset 版本、掃描範圍、排除項目。

短前綴（EAA、sk- 等）既可能誤判也可能漏抓。完整偵測應結合格式、上下文、
entropy 與已知供應商 detector；本工具只是其中一層，不是全部。
"""
import argparse
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter
from datetime import datetime

RULESET_VERSION = "v1 (2026-09-07)"

# (規則名, pattern, 誤判風險說明, classification)
#
# classification 的意義（2026-09-07 定義）：
#   HIGH_CONFIDENCE — 格式夠特殊，命中即值得當成憑證候選處理
#   SIGNAL_ONLY     — 結構上無法與一般字串區分，**不得單獨升格成 secret confirmed**，
#                     只能作為人工複核的線索，或與其他規則的上下文合併判讀
#
# ⚠️ SIGNAL_ONLY 不等於「不用測」。fixture 驗的是 **detector 的行為**
#    （這個 pattern 會不會按設計命中某種結構），不是證明該字串是真憑證。
#    所以每一條規則都必須有 positive fixture，沒有例外。
HIGH = "HIGH_CONFIDENCE"
SIGNAL = "SIGNAL_ONLY"

RULES = [
    ("meta_user_or_page_token", r'\bEAA[A-Za-z0-9]{20,}', "高信度；但前綴命中 ≠ 憑證有效", HIGH),
    ("meta_app_secret_like",    r'\b[0-9a-f]{32}\b',      "⚠️ 32 hex 也可能是 MD5／雜湊，單獨不足以判定", SIGNAL),
    ("meta_app_id_like",        r'\b\d{15,17}\b',         "⚠️ 可能是任何長數字，需搭配上下文", SIGNAL),
    ("github_pat",              r'\bgithub_pat_[A-Za-z0-9_]{20,}', "高信度", HIGH),
    ("github_classic",          r'\bgh[pousr]_[A-Za-z0-9]{30,}',   "高信度", HIGH),
    ("slack_token",             r'\bxox[baprs]-[A-Za-z0-9-]{10,}', "高信度", HIGH),
    ("openai_key",              r'\bsk-[A-Za-z0-9_-]{20,}',        "⚠️ sk- 前綴短，可能誤判", SIGNAL),
    ("google_api_key",          r'\bAIza[0-9A-Za-z_-]{35}',        "高信度", HIGH),
    ("aws_access_key_id",       r'\bAKIA[0-9A-Z]{16}\b',           "高信度", HIGH),
    ("jwt",                     r'\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.', "中；JWT 未必是秘密", HIGH),
    ("private_key_block",       r'-----BEGIN [A-Z ]*PRIVATE KEY-----',            "高信度", HIGH),
    ("bearer_header",           r'(?i)\bbearer\s+\S{20,}',         "中；只是 header 形式，非特定供應商格式", SIGNAL),
    ("url_with_userinfo",       r'https?://[^/\s:@]+:[^/\s@]+@',   "高信度", HIGH),
    ("line_channel_token",      r'\b[A-Za-z0-9+/]{140,}=*\b',      "⚠️ 極易誤判長 base64，僅供人工複核", SIGNAL),
]

# 檔名層規則：不要只找 token/secret，2026-09-07 就是這樣漏掉 `pw` 的
NAME_HINTS = re.compile(
    r'(token|secret|credential|passwd|password|\bpw\b|apikey|api_key|'
    r'\.env|\.pem$|\.key$|\.p12$|\.pfx$|auth|login)', re.I)

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".tmp", ".codex_tmp",
             ".playwright-cli", "venv", ".venv"}
SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".mov", ".zip",
            ".pdf", ".docx", ".xlsx", ".pptx", ".xmind", ".ico", ".woff", ".woff2"}
MAX_BYTES = 2 * 1024 * 1024


def entropy(s):
    if not s:
        return 0.0
    n = len(s)
    return round(-sum((c / n) * math.log2(c / n) for c in Counter(s).values()), 2)


def charclass(s):
    cls = []
    if re.search(r'[a-z]', s): cls.append("lower")
    if re.search(r'[A-Z]', s): cls.append("upper")
    if re.search(r'[0-9]', s): cls.append("digit")
    if re.search(r'[^\w]', s): cls.append("punct")
    if re.search(r'[^\x00-\x7f]', s): cls.append("non-ascii")
    return "+".join(cls) or "empty"


def scan_file(path):
    """回傳 count-only 結果。**任何情況下都不回傳命中的字串本身。**"""
    try:
        raw = open(path, "rb").read(MAX_BYTES)
    except OSError as e:
        return {"path": path, "error": str(e)}
    txt = raw.decode("utf-8", errors="replace")
    hits = {}
    for name, pat, _risk, _cls in RULES:
        n = len(re.findall(pat, txt))
        if n:
            hits[name] = n
    lines = txt.splitlines()
    return {
        "path": path,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "lines": len(lines),
        "mtime": datetime.fromtimestamp(os.path.getmtime(path)).isoformat(timespec="seconds"),
        "name_hint": bool(NAME_HINTS.search(os.path.basename(path))),
        "hits": hits,
        "line_shape": [
            {"line": i + 1, "len": len(l.strip()),
             "charclass": charclass(l.strip()), "entropy": entropy(l.strip())}
            for i, l in enumerate(lines) if l.strip()
        ][:20],
    }


def main():
    ap = argparse.ArgumentParser(description="明碼憑證掃描（count-only）")
    ap.add_argument("--path", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--recursive", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--shape", action="store_true", help="對有命中的檔案附逐行結構")
    a = ap.parse_args()

    targets, excluded = [], []
    if a.recursive:
        for root, dirs, files in os.walk(a.path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for fn in files:
                p = os.path.join(root, fn)
                if os.path.splitext(fn)[1].lower() in SKIP_EXT:
                    excluded.append(p); continue
                targets.append(p)
    else:
        for fn in sorted(os.listdir(a.path)):
            p = os.path.join(a.path, fn)
            if not os.path.isfile(p):
                continue
            if os.path.splitext(fn)[1].lower() in SKIP_EXT:
                excluded.append(p); continue
            targets.append(p)

    results = [scan_file(p) for p in targets]
    flagged = [r for r in results if r.get("hits") or r.get("name_hint")]

    report = {
        "ruleset_version": RULESET_VERSION,
        "scanned_at": datetime.now().isoformat(timespec="seconds"),
        "scope": {"path": a.path, "recursive": a.recursive,
                  "files_scanned": len(targets),
                  "files_excluded_by_extension": len(excluded),
                  "skipped_dirs": sorted(SKIP_DIRS),
                  "max_bytes_per_file": MAX_BYTES},
        "flagged": flagged,
        "disclaimer": "count = 0 只代表本 ruleset 在本範圍內未命中，不等於「沒有任何秘密」。",
        "classification_note": "SIGNAL_ONLY 規則不得單獨升格成 secret confirmed，只作人工複核線索。",
    }

    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 1 if any(r.get("hits") for r in flagged) else 0

    print("明碼憑證掃描｜ruleset %s" % RULESET_VERSION)
    print("  範圍   : %s（recursive=%s）" % (a.path, a.recursive))
    print("  已掃描 : %d 檔｜依副檔名排除 %d 檔｜跳過目錄 %s"
          % (len(targets), len(excluded), ", ".join(sorted(SKIP_DIRS))))
    print()
    if not flagged:
        print("  本次無命中。")
    for r in flagged:
        tag = "🔴" if r.get("hits") else "🟡"
        print("%s %s" % (tag, os.path.relpath(r["path"], a.path)))
        print("   sha256 %s  %d bytes / %d 行  mtime %s"
              % (r["sha256"][:16], r["bytes"], r["lines"], r["mtime"]))
        if r.get("name_hint"):
            print("   檔名命中提示規則")
        for k, v in (r.get("hits") or {}).items():
            risk = next(x[2] for x in RULES if x[0] == k)
            cls = next(x[3] for x in RULES if x[0] == k)
            mark = "🔴" if cls == HIGH else "🟡"
            print("   %s 命中 %-24s ×%d  [%s]  %s" % (mark, k, v, cls, risk))
        if a.shape and r.get("hits"):
            for ls in r["line_shape"]:
                print("     L%-3d len=%-5d %-28s entropy=%s"
                      % (ls["line"], ls["len"], ls["charclass"], ls["entropy"]))
        print()
    print("⛔ count = 0 只代表 %s 在上述範圍內未命中，**不等於「沒有任何秘密」**。"
          % RULESET_VERSION)
    return 1 if any(r.get("hits") for r in flagged) else 0


if __name__ == "__main__":
    sys.exit(main())
