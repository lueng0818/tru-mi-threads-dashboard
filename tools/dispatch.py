#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tru-Mi 派送器（Dispatcher）

Producer → Validator → Queue → **Dispatcher** → Verifier 五段式的第四段。

這支腳本只做一件事：從 queue 取出「已驗證、可派送」的工作。
它刻意不具備下列能力，這是設計而不是缺漏：
  ⛔ 不得自行修改 job["validation"]（驗證結果只能由 validation_gate.py 寫）
  ⛔ 不得產生內容（那是 Producer 的事）
  ⛔ 不得在 validation 不是 PASS 時執行任何 action

冪等性（idempotency）：
  dispatch_id = 日期 + 平台 + 帳號 + permalink + action
  同一個 dispatch_id 無論排程重跑幾次，都只會成功一次。
  已派送紀錄寫在 data/dispatch_log.jsonl，append-only，不覆寫。
  這一條直接吃掉「同日兩個 instance」造成的重複寫入。

用法：
    python tools/dispatch.py --dry-run          # 預設，只說會做什麼
    python tools/dispatch.py --execute          # 真的派送 L1
    python tools/dispatch.py --approve <id>     # 人工核准一則 L2
    python tools/dispatch.py --list

exit code：
    0  正常結束（含「沒有可派送的工作」）
    1  有工作被 BLOCKED
    3  queue 或 log 檔異常
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta

TPE = timezone(timedelta(hours=8))
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
QUEUE = os.path.join(DATA, "dispatch_queue.json")
LOG = os.path.join(DATA, "dispatch_log.jsonl")

AUTO_LEVELS = {"L1"}
APPROVAL_LEVELS = {"L2"}
FORBIDDEN_LEVELS = {"L3"}


def iso():
    return datetime.now(TPE).isoformat(timespec="seconds")


def load_queue():
    if not os.path.exists(QUEUE):
        return None
    with open(QUEUE, encoding="utf-8") as f:
        return json.load(f)


def save_queue(q):
    with open(QUEUE, "w", encoding="utf-8") as f:
        json.dump(q, f, ensure_ascii=False, indent=1)


def log_records():
    recs = []
    if os.path.exists(LOG):
        with open(LOG, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        recs.append(json.loads(line))
                    except Exception:
                        pass
    return recs


def last_result(did, recs):
    """log 是 append-only，所以看的是同一個 id 的最後一筆結果，不是有沒有出現過。"""
    hits = [r for r in recs if r.get("dispatch_id") == did]
    return hits[-1] if hits else None


def already_dispatched(did, recs):
    """VOIDED 會撤銷先前的 DISPATCHED——用補寫一筆的方式更正，不改寫歷史。"""
    last = last_result(did, recs)
    return bool(last) and last.get("result") == "DISPATCHED"


def write_log(rec):
    os.makedirs(DATA, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def execute(job, dry):
    """
    實際派送。目前支援的 action 都是「準備給人執行」的低風險動作，
    刻意不含任何對外送出（留言、發文、私訊）——那些必須留在 L2 人工核准後
    由人送出。要新增對外送出的 action，必須同時新增對應的 L2 核准路徑，
    不可直接掛在 L1 底下。
    """
    action = job.get("action")
    if action == "dashboard_ingest":
        if dry:
            return "DRY_RUN", "會把 %s 以 %s 級卡片寫入 %s" % (
                job["source"]["account"], job.get("intent"), job.get("panel"))
        # 實際寫卡片仍由每日流程的 safe_write 階段執行；dispatcher 只負責
        # 標記這筆已核可進入寫入階段，避免兩個 instance 各寫一次。
        return "DISPATCHED", "已核可寫入 %s（由 safe_write 階段落地）" % job.get("panel")
    if action == "observe_only":
        return "BLOCKED", "OBSERVE_ONLY：本項不派送，只保留觀察紀錄"
    if action == "prepare_comment":
        if dry:
            return "DRY_RUN", "會產生留言候選，等待人工 APPROVE"
        return "PREPARED", "留言候選已備妥，等待人工 APPROVE 後由人送出"
    return "BLOCKED", "未知的 action：%s" % action


def main():
    ap = argparse.ArgumentParser(description="Tru-Mi 派送器")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", default=True)
    g.add_argument("--execute", action="store_true")
    ap.add_argument("--approve", metavar="DISPATCH_ID", help="人工核准一則 L2")
    ap.add_argument("--accept-warn", action="store_true",
                    help="核准時接受 WARN（僅 WARN，FAIL 一律不可繞過）")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--void", metavar="DISPATCH_ID",
                    help="撤銷一筆先前的派送（補寫 VOIDED，不改寫歷史）")
    ap.add_argument("--reason", default="", help="搭配 --void 說明原因")
    a = ap.parse_args()
    dry = not a.execute

    q = load_queue()
    if q is None:
        print("FAIL: 找不到 %s" % QUEUE)
        return 3
    jobs = q.get("jobs", [])
    recs = log_records()

    if a.list:
        print("Tru-Mi 派送佇列（%d 筆）" % len(jobs))
        for j in jobs:
            print("  %-12s %-6s %-22s %s"
                  % (j.get("dispatch_status"), j.get("dispatch_level"),
                     (j.get("validation") or {}).get("status"), j.get("dispatch_id")))
        return 0

    if a.void:
        if not a.reason:
            print("FAIL: --void 必須帶 --reason，撤銷要留下理由")
            return 3
        write_log({"dispatch_id": a.void, "at": iso(), "result": "VOIDED",
                   "reason": a.reason, "voided_by": "manual"})
        for j in jobs:
            if j.get("dispatch_id") == a.void:
                j["dispatch_status"] = "PENDING_VALIDATION"
                for stale in ("dispatched_at", "approved_with_warn", "approved_at"):
                    j.pop(stale, None)
                j["validation"] = {"status": "PENDING", "validated_at": None, "validator": None}
        save_queue(q)
        print("OK: %s 已撤銷，回到 PENDING_VALIDATION（原紀錄保留，另補一筆 VOIDED）" % a.void)
        return 0

    if a.approve:
        hit = [j for j in jobs if j.get("dispatch_id") == a.approve]
        if not hit:
            print("FAIL: 找不到 %s" % a.approve)
            return 3
        job = hit[0]
        if job.get("dispatch_level") in FORBIDDEN_LEVELS:
            print("REFUSED: %s 是 L3，禁止自動派送，核准也不行" % a.approve)
            return 1
        vstat = (job.get("validation") or {}).get("status")
        if vstat == "FAIL":
            print("REFUSED: validation=FAIL，不得核准。FAIL 只能修好再驗，不能用核准繞過。")
            return 1
        if vstat == "WARN" and not a.accept_warn:
            print("REVIEW_REQUIRED: validation=WARN，需人工確認後加 --accept-warn 才可核准")
            for g, s in ((job.get("validation") or {}).get("gates") or {}).items():
                if s == "WARN":
                    print("  · %s = WARN" % g)
            return 1
        if vstat not in ("PASS", "WARN"):
            print("REFUSED: validation=%s（需 PASS 或經確認的 WARN）" % vstat)
            print("  → No validation, no dispatch。請先跑 validation_gate.py --write")
            return 1
        job["dispatch_status"] = "READY"
        job["approved_with_warn"] = (vstat == "WARN")
        job["approved_at"] = iso()
        save_queue(q)
        print("OK: %s 已核准，dispatch_status → READY" % a.approve)
        return 0

    print("Tru-Mi 派送器｜%s｜模式：%s" % (iso(), "DRY-RUN" if dry else "EXECUTE"))
    blocked = 0
    acted = 0

    for job in jobs:
        did = job.get("dispatch_id")
        lvl = job.get("dispatch_level")
        vs = (job.get("validation") or {}).get("status")

        # 冪等性最優先：已派送過的一律短路，不再重跑後面的判斷。
        # 這是「同日兩個 instance」不會寫兩次的關鍵，必須在 validation 之前。
        if already_dispatched(did, recs):
            print("  [DUPLICATE] %s\n             已派送過（%s），冪等跳過"
                  % (did, (last_result(did, recs) or {}).get("at")))
            if not dry and job.get("dispatch_status") != "DISPATCHED":
                job["dispatch_status"] = "DISPATCHED"
            continue
        if lvl in FORBIDDEN_LEVELS:
            print("  [BLOCKED ] %s\n             L3 OBSERVE_ONLY，禁止自動派送" % did)
            blocked += 1
            continue
        if vs == "WARN" and job.get("approved_with_warn") and job.get("dispatch_status") == "READY":
            pass  # 人工已就 WARN 明確核准
        elif vs != "PASS":
            label = "REVIEW_REQUIRED" if vs == "WARN" else "BLOCKED"
            print("  [%-9s] %s\n             validation=%s（需 PASS）→ No validation, no dispatch"
                  % (label, did, vs))
            blocked += 1
            continue
        if job.get("dispatch_status") != "READY":
            note = "L2 需人工 --approve" if lvl in APPROVAL_LEVELS else ""
            print("  [SKIP    ] %s\n             dispatch_status=%s（需 READY）%s"
                  % (did, job.get("dispatch_status"), note))
            continue
        result, detail = execute(job, dry)
        print("  [%-9s] %s\n             %s" % (result, did, detail))
        if result == "BLOCKED":
            blocked += 1
            continue
        acted += 1
        if not dry:
            job["dispatch_status"] = result
            job["dispatched_at"] = iso()
            write_log({
                "dispatch_id": did,
                "at": iso(),
                "result": result,
                "level": lvl,
                "action": job.get("action"),
                "validation_at": (job.get("validation") or {}).get("validated_at"),
                "detail": detail,
            })

    if not dry:
        save_queue(q)

    print("\n總結：處理 %d 筆，BLOCKED %d 筆%s"
          % (acted, blocked, "（DRY-RUN，未實際寫入）" if dry else ""))
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
