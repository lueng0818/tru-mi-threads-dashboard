#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
secret_scan ruleset 的回歸測試（fixture-based）

    python tools/test_secret_scan_regression.py

在 tempdir 產生合成 fixture，**不使用任何真實憑證**，也不讀工作資料夾裡的檔。

為什麼要有這個（2026-09-07 約定）：
擴充 ruleset 時，只加一條前綴就宣稱「覆蓋更完整」是沒有證據的說法。
每新增一條規則，必須同時新增：
  ① positive fixture — 該格式應被抓到
  ② negative fixture — 不該被這條規則抓到的相似字串
  ③ 若該規則已知易誤判，把誤判樣本放進 negative 並在 RULES 標註風險
沒有 fixture 的規則不算完成。

S4 鎖的是本工具最重要的性質：**任何情況下都不得回傳命中的字串本身**。
掃描器一旦把秘密印進報告或 log，它就從防護變成外洩管道。
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
PASS, FAIL = "\033[32mPASS\033[0m", "\033[31mFAIL\033[0m"
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print("  [%s] %s%s" % (PASS if cond else FAIL, name, ("  — " + detail) if detail else ""))


def load(path):
    spec = importlib.util.spec_from_file_location("ss", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _j(*parts):
    """把敏感格式拆成片段，runtime 才組起來。

    2026-09-11 新增。原因：GitHub Push Protection 掃的是**原始檔案文字**，
    只要出現「單一連續字串常值」符合已知 secret 格式就會擋下 push
    （commit f6f0096e 即因 slack_token fixture 被擋）。

    片段本身各自不命中任何 pattern，組合後才是完整的 positive fixture。
    組出來的值與拆分前**逐字元相同**，所以偵測覆蓋率與 S1/S2 結果都不變。

    ⛔ 不得改為降低 detector 靈敏度或刪除 fixture 來讓 push 過關——
       那是拿偵測能力換方便，方向相反。
    ⛔ 新增 fixture 時，若該格式屬於 GitHub 會掃的類型（Slack／OpenAI／
       Google／AWS／GitHub token／private key／JWT／URL userinfo 等），
       一律用本函式組裝，不要寫成一整串。
    """
    return "".join(parts)


# 全部為合成字串，非真實憑證。
# **每一條規則都要在這裡有 positive fixture，沒有豁免。**
# SIGNAL_ONLY 的規則一樣要測：fixture 驗的是 detector 會不會按設計命中某種結構，
# 不是證明該字串是真憑證。分類由 RULES 的 classification 欄承擔，不是靠不測。
POSITIVE = {
    "meta_user_or_page_token": "EAA" + "Zz09Test" * 6,
    "meta_app_secret_like":    "a1b2c3d4e5f60718293a4b5c6d7e8f90",          # 32 hex
    "meta_app_id_like":        "123456789012345",                          # 15 位數
    "github_pat":              "github_pat_" + "A1b2C3d4E5" * 3,
    "github_classic":          "ghp_" + "x9Y8z7W6v5" * 4,
    "slack_token":             _j("xox", "b-", "1111111111", "-2222222222", "-AbCdEfGhIjKlMnOp"),
    "openai_key":              "sk-" + "Aa0Bb1Cc2Dd3Ee4Ff5Gg",
    "google_api_key":          "AIza" + "B" * 35,
    "aws_access_key_id":       "AKIA" + "Q" * 16,
    "jwt":                     _j("eyJhbGciOiJIUzI1NiJ9", ".", "eyJzdWIiOiIxMjM0NX0", ".", "SflKxwRJSM"),
    "private_key_block":       _j("-----BEGIN ", "RSA ", "PRIVATE ", "KEY", "-----"),
    "bearer_header":           "Authorization: Bearer " + "T" * 40,
    "url_with_userinfo":       _j("https://", "someuser", ":", "somepass", "@example.com/x"),
    "line_channel_token":      "B" * 150,                                   # 長 base64
}

# 這些**不該**被對應規則抓到（含高誤判規則的已知邊界）
NEGATIVE = {
    "meta_user_or_page_token": ["EAAshort", "NOTEAA" + "x" * 40, "eaa" + "b" * 40],
    "github_pat":              ["github_pat_short", "github_patX" + "y" * 30],
    "aws_access_key_id":       ["AKIAlowercase123", "AKIA" + "Q" * 8],
    "google_api_key":          ["AIzaTooShort", "BIza" + "B" * 35],
    "meta_app_secret_like":    ["a1b2c3d4e5f60718", "G" * 32, "a1b2c3d4e5f60718293a4b5c6d7e8f9012"],
    "meta_app_id_like":        ["12345", "1234567890123456789012"],
    "openai_key":              ["sk-short", "xk-" + "A" * 30],
    "bearer_header":           ["Bearer short", "bearer"],
    "line_channel_token":      ["B" * 100, "short"],
}


def main():
    tmp = tempfile.mkdtemp(prefix="trumi_secretscan_test_")
    try:
        os.makedirs(os.path.join(tmp, "tools"), exist_ok=True)
        shutil.copy(os.path.join(TOOLS, "secret_scan.py"),
                    os.path.join(tmp, "tools", "secret_scan.py"))
        ss = load(os.path.join(tmp, "tools", "secret_scan.py"))
        rule_names = [r[0] for r in ss.RULES]

        print("\nS1  每條 positive fixture 都要被對應規則抓到")
        for rule, sample in POSITIVE.items():
            p = os.path.join(tmp, "fx_%s.txt" % rule)
            open(p, "w", encoding="utf-8").write(sample + "\n")
            hits = ss.scan_file(p).get("hits", {})
            check("S1 %s" % rule, hits.get(rule, 0) >= 1,
                  "命中 %s" % (list(hits) or "無"))

        print("\nS2  negative fixture 不得被該規則抓到")
        for rule, samples in NEGATIVE.items():
            p = os.path.join(tmp, "neg_%s.txt" % rule)
            open(p, "w", encoding="utf-8").write("\n".join(samples) + "\n")
            hits = ss.scan_file(p).get("hits", {})
            check("S2 %s" % rule, hits.get(rule, 0) == 0,
                  "誤判 %d 次" % hits.get(rule, 0))

        print("\nS3  每條規則都必須有 positive fixture — 沒有豁免")
        # 2026-09-07 修正：舊版允許 5 條規則永久沒有 positive fixture，
        # 等於把「沒 fixture 不算完成」偷偷改成「有理由就可以不測」。
        # 高誤判規則一樣要測 detector 行為，分類交給 RULES 的 classification 欄承擔。
        missing = [r for r in rule_names if r not in POSITIVE]
        check("S3a 每條規則都有 positive fixture", not missing,
              ("缺 fixture：%s" % missing) if missing else
              "%d/%d 條規則皆有 fixture" % (len(rule_names), len(rule_names)))
        signal_only = [r[0] for r in ss.RULES if r[3] == ss.SIGNAL]
        check("S3b 高誤判規則已標為 SIGNAL_ONLY 而非豁免測試",
              len(signal_only) > 0 and all(r in POSITIVE for r in signal_only),
              "SIGNAL_ONLY: %s（全部有 fixture）" % ", ".join(signal_only))
        check("S3c SIGNAL_ONLY 規則也有 negative 邊界",
              all(r in NEGATIVE for r in signal_only),
              "缺 negative：%s" % [r for r in signal_only if r not in NEGATIVE])

        print("\nS4  任何輸出路徑都不得包含命中的字串本身")
        cases = {
            "meta":     "EAA" + "LeakCanary1" * 5,
            "userinfo": _j("https://", "leakuser", ":", "leakpass123456", "@example.com/path"),
            "bearer":   "Authorization: Bearer " + "LeakBearerToken" * 3,
        }
        for label, secret in cases.items():
            p = os.path.join(tmp, "leak_%s.txt" % label)
            open(p, "w", encoding="utf-8").write("value=%s\n" % secret)
            blob = json.dumps(ss.scan_file(p), ensure_ascii=False)
            check("S4a[%s] scan_file 回傳不含原值" % label, secret not in blob)
            check("S4b[%s] 也不含長片段" % label, secret[:30] not in blob)

        # CLI-level negative control：函式層乾淨不代表 CLI／例外／formatter 乾淨。
        # 真正的性質是「任何情況下不得輸出命中字串」，所以要連 stdout/stderr 一起驗。
        import subprocess
        leakdir = os.path.join(tmp, "clidir")
        os.makedirs(leakdir, exist_ok=True)
        for label, secret in cases.items():
            open(os.path.join(leakdir, "c_%s.txt" % label), "w",
                 encoding="utf-8").write("value=%s\n" % secret)
        for extra in (["--shape"], ["--json"], []):
            r = subprocess.run(
                [sys.executable, os.path.join(tmp, "tools", "secret_scan.py"),
                 "--path", leakdir] + extra,
                capture_output=True, text=True)
            out = (r.stdout or "") + (r.stderr or "")
            leaked = [l for l, s in cases.items() if s in out or s[:30] in out]
            check("S4c CLI %-8s stdout/stderr 無外洩" % (extra or ["(default)"])[0],
                  not leaked, ("外洩 %s" % leaked) if leaked else "3 類 fixture 皆未出現")

        print("\nS5  報告必須帶版本／分類／誤判風險")
        check("S5a 有 ruleset 版本", bool(getattr(ss, "RULESET_VERSION", "")),
              ss.RULESET_VERSION)
        check("S5b 每條規則都帶誤判風險說明與 classification",
              all(len(r) == 4 and r[2] and r[3] in (ss.HIGH, ss.SIGNAL) for r in ss.RULES))

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    ok = sum(1 for _, c in results if c)
    print("\n%d/%d 通過" % (ok, len(results)))
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
