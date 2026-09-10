#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tru-Mi 派送前驗證閘門（G1–G6）

Canonical Rule ⑥：**No validation, no dispatch.**
產生內容的那一步，不得自行宣告該內容已通過驗證。驗證與執行必須是
兩個可獨立稽核的階段——所以這支腳本刻意不會產生任何內容，
它只讀既有事實，然後打分。它也不會修改 queue 的 dispatch_status，
那是 dispatch.py 的事。

用法：
    python tools/validation_gate.py                    # 驗整個 queue
    python tools/validation_gate.py --job <dispatch_id>
    python tools/validation_gate.py --json
    python tools/validation_gate.py --write            # 把結果寫回 queue 的 validation 欄

exit code：
    0  全部 PASS
    1  有 FAIL（BLOCKED）
    2  有 WARN 但無 FAIL（REVIEW_REQUIRED）

六道閘門：
    G1 Concurrency        沒有其他 instance 正在寫同一份資料
    G2 Source freshness   permalink 格式合法、有紀錄過的存活查核、非過期
    G3 Duplicate          dashboard / queue / 歷史紀錄均未重複
    G4 Content policy     風險類、敏感家庭、醫療、攻擊性內容不自動派送
    G5 Artifact integrity health check PASS、主檔與 index 一致
    G6 Deployment         需要網站最新資料的動作，必須 DEPLOY_VERIFIED
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta

TPE = timezone(timedelta(hours=8))
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(BASE, "tools")
DATA = os.path.join(BASE, "data")
QUEUE = os.path.join(DATA, "dispatch_queue.json")
LOG = os.path.join(DATA, "dispatch_log.jsonl")
MAIN = os.path.join(BASE, "threads_wedding_ring_dashboard.html")
MIRROR = os.path.join(BASE, "index.html")

# G2：來源超過這個天數就不該再拿去做即時互動
SOURCE_MAX_AGE_DAYS = 7

# G4：出現這些訊號一律不自動派送（對應 SOP 的風險類與 L3）
POLICY_BLOCK = [
    "產後憂鬱", "憂鬱", "自殺", "輕生", "家暴", "離婚", "外遇", "婆媳",
    "協尋", "詐騙", "避雷", "求償", "訴訟", "提告", "病危", "罹癌",
]
POLICY_REVIEW = [
    "醫療", "診斷", "手術", "藥物", "懷孕", "流產", "分手", "債務", "負債",
]

STATE_PASS = "PASS"
STATE_WARN = "WARN"
STATE_FAIL = "FAIL"


def now():
    return datetime.now(TPE)


def iso():
    return now().isoformat(timespec="seconds")


def load_queue():
    if not os.path.exists(QUEUE):
        return {"version": 1, "jobs": []}
    with open(QUEUE, encoding="utf-8") as f:
        return json.load(f)


def save_queue(q):
    os.makedirs(DATA, exist_ok=True)
    with open(QUEUE, "w", encoding="utf-8") as f:
        json.dump(q, f, ensure_ascii=False, indent=1)


def dashboard_text():
    if not os.path.exists(MAIN):
        return ""
    with open(MAIN, encoding="utf-8", errors="ignore") as f:
        return f.read()


def sha(path):
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def dispatched_ids():
    """
    log 是 append-only，所以判斷依據是**同一個 id 的最後一筆結果**，
    不是「有沒有出現過 DISPATCHED」。VOIDED 會撤銷先前的 DISPATCHED。

    ⚠️ 這裡的語意必須與 `dispatch.py::already_dispatched` 完全一致。
    2026-09-07 就是因為兩邊不一致踩過一次：dispatch.py 認得 VOIDED，
    這裡不認得，於是一筆已撤銷的工作在 dispatcher 眼中是 PENDING、
    在 validator 眼中卻是 DUPLICATE——兩邊各自看起來都合理，最難查。
    日後改動任一邊，必須同步改另一邊，並補回歸測試。
    """
    last = {}
    if os.path.exists(LOG):
        with open(LOG, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("dispatch_id"):
                    last[rec["dispatch_id"]] = rec.get("result")
    return {k for k, v in last.items() if v == "DISPATCHED"}


# ── 六道閘門 ────────────────────────────────────────────────

def g1_concurrency():
    """沒有其他 instance 正在寫同一份資料。"""
    r = subprocess.run([sys.executable, os.path.join(TOOLS, "runlock.py"), "status"],
                       capture_output=True, text=True)
    out = (r.stdout or "").strip()
    first = out.splitlines()[0] if out else ""
    if first.startswith("LOCKED"):
        # 有人持鎖。若持鎖者就是自己（環境變數），視為正常。
        me = os.environ.get("TRUMI_INSTANCE_ID")
        if me and me in out:
            return STATE_PASS, "鎖由本 instance 持有（%s）" % me
        return STATE_FAIL, "CONCURRENCY_BLOCKED：鎖被其他 instance 持有\n%s" % out
    if first.startswith("CORRUPT"):
        return STATE_FAIL, "CONCURRENCY_BLOCKED：鎖檔損毀，需人工確認"
    if first.startswith("STALE"):
        return STATE_WARN, "鎖已 stale，代表上一輪沒有正常收尾，請確認原因"
    if "WARN 鎖期間來源檔已被改動" in out:
        return STATE_FAIL, "CONCURRENCY_BLOCKED：偵測到鎖外 writer"
    return STATE_PASS, "無其他 instance 持鎖"


def g2_source_freshness(job):
    src = job.get("source") or {}
    pl = (src.get("permalink") or "").strip()
    if not pl:
        return STATE_FAIL, "SOURCE_INVALID：缺 permalink"
    if not re.fullmatch(r"[A-Za-z0-9_\-]{6,}", pl):
        return STATE_FAIL, "SOURCE_INVALID：permalink 格式不合法（%s）" % pl
    if not (src.get("account") or "").startswith("@"):
        return STATE_FAIL, "SOURCE_INVALID：缺帳號或格式不對"
    seen = src.get("verified_at")
    if not seen:
        return STATE_WARN, "來源未記錄查核時間，無法確認貼文仍存在"
    try:
        d = datetime.fromisoformat(seen)
    except ValueError:
        return STATE_WARN, "verified_at 格式無法解析：%s" % seen
    age = (now() - d).days
    if age > SOURCE_MAX_AGE_DAYS:
        return STATE_FAIL, "SOURCE_INVALID：來源查核已過 %s 天（上限 %s）" % (age, SOURCE_MAX_AGE_DAYS)
    return STATE_PASS, "來源 %s 天前查核，permalink 格式合法" % age


def g3_duplicate(job, queue, html, done):
    did = job.get("dispatch_id")
    if did in done:
        return STATE_FAIL, "DUPLICATE_SKIP：dispatch_id 已派送過"
    pl = (job.get("source") or {}).get("permalink", "")
    acct = (job.get("source") or {}).get("account", "")
    if pl and pl in html:
        return STATE_FAIL, "DUPLICATE_SKIP：permalink 已存在於 dashboard"
    if acct and ('>%s</a>' % acct) in html:
        return STATE_FAIL, "DUPLICATE_SKIP：帳號已收錄於 dashboard"
    same = [j for j in queue.get("jobs", [])
            if j is not job and j.get("dispatch_id") == did]
    if same:
        return STATE_FAIL, "DUPLICATE_SKIP：queue 內有同 dispatch_id 的重複項"
    return STATE_PASS, "dashboard／queue／歷史紀錄皆無重複"


def g4_content_policy(job):
    level = (job.get("intent") or "").upper()
    blob = " ".join(str(v) for v in [
        job.get("summary", ""), job.get("note", ""),
        (job.get("source") or {}).get("excerpt", ""),
    ])
    hits_block = [k for k in POLICY_BLOCK if k in blob]
    hits_review = [k for k in POLICY_REVIEW if k in blob]

    if level in ("RISK", "風險"):
        return STATE_FAIL, "MANUAL_ONLY：風險類一律不自動派送（OBSERVE_ONLY）"
    if hits_block:
        return STATE_FAIL, "MANUAL_ONLY：命中敏感訊號 %s" % "、".join(hits_block)
    if hits_review:
        return STATE_WARN, "REVIEW_REQUIRED：出現需人工判斷的訊號 %s" % "、".join(hits_review)
    if job.get("dispatch_level") == "L3":
        return STATE_FAIL, "MANUAL_ONLY：本項標為 L3，禁止自動派送"
    if job.get("dispatch_level") == "L2":
        return STATE_WARN, "REVIEW_REQUIRED：L2 需人工 APPROVE 後才可派送"
    return STATE_PASS, "無風險／敏感訊號，L1 可自動派送"


def g5_artifact_integrity():
    r = subprocess.run([sys.executable, os.path.join(TOOLS, "dashboard_check.py")],
                       capture_output=True, text=True)
    if r.returncode != 0:
        tail = (r.stdout or "").strip().splitlines()[-3:]
        return STATE_FAIL, "CONTENT_INVALID：health check FAIL\n  " + "\n  ".join(tail)
    a, b = sha(MAIN), sha(MIRROR)
    if a is None or b is None:
        return STATE_FAIL, "CONTENT_INVALID：主檔或 index.html 不存在"
    if a != b:
        return STATE_FAIL, "CONTENT_INVALID：主檔與 index.html 不一致（%s vs %s）" % (a, b)
    warn = [l for l in (r.stdout or "").splitlines() if l.strip().startswith("WARN")]
    if warn:
        return STATE_WARN, "health check PASS 但有 WARN：\n  " + "\n  ".join(w.strip() for w in warn)
    return STATE_PASS, "health check PASS，主檔與 index 一致（%s）" % a


def g6_deployment(job):
    if not job.get("requires_deploy"):
        return STATE_PASS, "本項不依賴網站最新資料，跳過部署前置"
    script = os.path.join(TOOLS, "deploy_verify.sh")
    if not os.path.exists(script):
        return STATE_FAIL, "DEPLOY_WAITING：找不到 deploy_verify.sh"
    r = subprocess.run(["bash", script], capture_output=True, text=True)
    if r.returncode == 0:
        return STATE_PASS, "DEPLOY_VERIFIED"
    if r.returncode == 2:
        return STATE_FAIL, "DEPLOY_WAITING：讀不到遠端，狀態 UNKNOWN（不得視為已發布）"
    return STATE_FAIL, "DEPLOY_WAITING：遠端與本機不一致（OUT_OF_SYNC）"


GATES_JOB = [
    ("G2 Source freshness", g2_source_freshness),
    ("G4 Content policy", g4_content_policy),
    ("G6 Deployment", g6_deployment),
]


def validate_job(job, queue, html, done, shared):
    results = []
    results.append(("G1 Concurrency",) + shared["g1"])
    results.append(("G2 Source freshness",) + g2_source_freshness(job))
    results.append(("G3 Duplicate",) + g3_duplicate(job, queue, html, done))
    results.append(("G4 Content policy",) + g4_content_policy(job))
    results.append(("G5 Artifact integrity",) + shared["g5"])
    results.append(("G6 Deployment",) + g6_deployment(job))

    states = [r[1] for r in results]
    overall = STATE_FAIL if STATE_FAIL in states else (STATE_WARN if STATE_WARN in states else STATE_PASS)
    return overall, results


def main():
    ap = argparse.ArgumentParser(description="Tru-Mi 派送前驗證閘門 G1-G6")
    ap.add_argument("--job", help="只驗這個 dispatch_id")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write", action="store_true", help="把結果寫回 queue 的 validation 欄")
    a = ap.parse_args()

    queue = load_queue()
    jobs = queue.get("jobs", [])
    if a.job:
        jobs = [j for j in jobs if j.get("dispatch_id") == a.job]
        if not jobs:
            print("找不到 dispatch_id：%s" % a.job)
            return 1

    html = dashboard_text()
    done = dispatched_ids()
    shared = {"g1": g1_concurrency(), "g5": g5_artifact_integrity()}

    report = {"validated_at": iso(), "jobs": []}
    worst = STATE_PASS

    if not jobs:
        # 沒有待驗工作時，仍要回報環境層閘門，這樣「今天沒東西派」也是有證據的
        print("Tru-Mi 驗證閘門｜%s" % iso())
        print("  queue 內無待驗工作，僅回報環境層閘門：")
        for name, key in (("G1 Concurrency", "g1"), ("G5 Artifact integrity", "g5")):
            st, msg = shared[key]
            print("  [%s] %-22s %s" % (st, name, msg))
            if st == STATE_FAIL:
                worst = STATE_FAIL
            elif st == STATE_WARN and worst == STATE_PASS:
                worst = STATE_WARN
        print("\n總結：%s" % worst)
        return {STATE_PASS: 0, STATE_FAIL: 1, STATE_WARN: 2}[worst]

    for job in jobs:
        overall, results = validate_job(job, queue, html, done, shared)
        report["jobs"].append({
            "dispatch_id": job.get("dispatch_id"),
            "status": overall,
            "gates": [{"gate": g, "status": s, "detail": m} for g, s, m in results],
        })
        if a.write:
            job["validation"] = {
                "status": overall,
                "validated_at": iso(),
                "validator": "tools/validation_gate.py",
                "gates": {g: s for g, s, _ in results},
            }
            # 驗證器只寫 validation，不碰 dispatch_status（責任分離）
        if overall == STATE_FAIL:
            worst = STATE_FAIL
        elif overall == STATE_WARN and worst == STATE_PASS:
            worst = STATE_WARN

    if a.write:
        save_queue(queue)

    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print("Tru-Mi 驗證閘門｜%s" % iso())
        for jr in report["jobs"]:
            print("\n▸ %s → %s" % (jr["dispatch_id"], jr["status"]))
            for g in jr["gates"]:
                print("  [%s] %-22s %s" % (g["status"], g["gate"], g["detail"]))
        print("\n總結：%s（%s）" % (
            worst,
            {STATE_PASS: "可進 DISPATCH_QUEUE",
             STATE_WARN: "REVIEW_REQUIRED，不自動派送",
             STATE_FAIL: "BLOCKED，不派送"}[worst]))

    return {STATE_PASS: 0, STATE_FAIL: 1, STATE_WARN: 2}[worst]


if __name__ == "__main__":
    sys.exit(main())
