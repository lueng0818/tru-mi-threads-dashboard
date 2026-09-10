#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
派送控制的回歸測試。

    python tools/test_dispatch_regression.py

在 tempdir 裡跑，**不會碰到真的 queue 或 log**。

R1 是 2026-09-07 真實踩到的坑：`--void` 清了 dispatched_at 與 approved_with_warn，
卻漏了 approved_at，結果出現「狀態是 PENDING_VALIDATION，metadata 卻還留著核准時間」
的 semantic drift。狀態欄位與旁證欄位不一致，比單純狀態錯更難查——因為兩邊各自看
起來都合理。所以這裡不是斷言「approved_at 被清掉」，而是斷言**整組相關欄位都被清掉**，
日後新增任何核准／派送欄位，忘了加進清除清單就會在這裡被抓到。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
DISPATCH = os.path.join(TOOLS, "dispatch.py")

# 一旦 job 回到 PENDING_VALIDATION，這些欄位都不該還留著
FORBIDDEN_AFTER_VOID = ["approved_at", "approved_with_warn", "dispatched_at"]

PASS, FAIL = "\033[32mPASS\033[0m", "\033[31mFAIL\033[0m"
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print("  [%s] %s%s" % (PASS if cond else FAIL, name, ("  — " + detail) if detail else ""))


def make_queue(path, **over):
    job = {
        "dispatch_id": "TEST_job_1",
        "source": {"platform": "threads", "account": "@tester",
                   "permalink": "AbcDef123", "verified_at": "2026-09-07T10:00:00+08:00"},
        "intent": "C", "panel": "panel-daily", "action": "dashboard_ingest",
        "dispatch_level": "L1", "summary": "測試用", "note": "",
        "requires_deploy": False,
        "validation": {"status": "PASS", "validated_at": "2026-09-07T10:01:00+08:00",
                       "validator": "test"},
        "dispatch_status": "READY",
    }
    job.update(over)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"version": 1, "jobs": [job]}, f, ensure_ascii=False, indent=1)


def run(tmp, *args):
    env = dict(os.environ)
    r = subprocess.run([sys.executable, DISPATCH, *args],
                       capture_output=True, text=True, cwd=tmp, env=env)
    return r


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["jobs"][0]


def main():
    tmp = tempfile.mkdtemp(prefix="trumi_dispatch_test_")
    try:
        # dispatch.py 用 BASE=tools 的上層當根目錄，所以在 tmp 裡複製同樣的結構
        os.makedirs(os.path.join(tmp, "tools"), exist_ok=True)
        os.makedirs(os.path.join(tmp, "data"), exist_ok=True)
        shutil.copy(DISPATCH, os.path.join(tmp, "tools", "dispatch.py"))
        qp = os.path.join(tmp, "data", "dispatch_queue.json")
        lp = os.path.join(tmp, "data", "dispatch_log.jsonl")
        local = [sys.executable, os.path.join(tmp, "tools", "dispatch.py")]

        def call(*args):
            return subprocess.run(local + list(args), capture_output=True, text=True)

        print("\nR1  void 後不得殘留任何核准／派送欄位（2026-09-07 regression）")
        make_queue(qp)
        call("--execute")
        j = load(qp)
        check("R1a 派送後狀態為 DISPATCHED", j.get("dispatch_status") == "DISPATCHED",
              "實際 %s" % j.get("dispatch_status"))
        call("--void", "TEST_job_1", "--reason", "regression test")
        j = load(qp)
        check("R1b void 後狀態回到 PENDING_VALIDATION",
              j.get("dispatch_status") == "PENDING_VALIDATION", "實際 %s" % j.get("dispatch_status"))
        leftovers = [k for k in FORBIDDEN_AFTER_VOID if k in j]
        check("R1c void 後無殘留欄位", not leftovers,
              ("殘留 %s" % leftovers) if leftovers else "approval／dispatch／execution 欄位皆已清除")
        check("R1d void 後 validation 重置為 PENDING",
              (j.get("validation") or {}).get("status") == "PENDING",
              "實際 %s" % (j.get("validation") or {}).get("status"))

        print("\nR2  冪等：重複 execute 不得產生第二筆 DISPATCHED")
        make_queue(qp)
        open(lp, "w").close()
        call("--execute"); call("--execute"); call("--execute")
        n = sum(1 for l in open(lp, encoding="utf-8") if l.strip()
                and json.loads(l).get("result") == "DISPATCHED")
        check("R2a log 僅 1 筆 DISPATCHED", n == 1, "實際 %d 筆" % n)

        print("\nR3  No validation, no dispatch")
        make_queue(qp, validation={"status": "PENDING", "validated_at": None, "validator": None})
        open(lp, "w").close()
        r = call("--execute")
        check("R3a validation!=PASS 一律不派送", "No validation, no dispatch" in r.stdout)
        check("R3b 未寫入 log", os.path.getsize(lp) == 0)

        print("\nR4  L3 禁止自動派送，核准也不行")
        make_queue(qp, dispatch_level="L3", action="observe_only")
        r = call("--approve", "TEST_job_1")
        check("R4a L3 核准被拒", "REFUSED" in r.stdout and r.returncode == 1)

        print("\nR5  FAIL 不可用核准繞過")
        make_queue(qp, dispatch_level="L2",
                   validation={"status": "FAIL", "validated_at": "x", "validator": "test"})
        r = call("--approve", "TEST_job_1", "--accept-warn")
        check("R5a FAIL 即使帶 --accept-warn 也被拒",
              "REFUSED" in r.stdout and "FAIL" in r.stdout)

        print("\nR6  void 必須留下理由")
        make_queue(qp)
        r = call("--void", "TEST_job_1")
        check("R6a 無 --reason 時拒絕撤銷", r.returncode == 3 and "必須帶 --reason" in r.stdout)

        print("\nR7  validator 與 dispatcher 對 VOIDED 的認定必須一致（2026-09-07 regression）")
        # 兩邊各自實作「這筆派送過了嗎」。dispatch.py 認得 VOIDED、
        # validation_gate.py 不認得，就會出現「dispatcher 說 PENDING、
        # validator 說 DUPLICATE」——兩邊各自看起來都合理，最難查。
        import importlib.util

        def load_mod(name, path):
            spec = importlib.util.spec_from_file_location(name, path)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            return m

        log = os.path.join(tmp, "data", "dispatch_log.jsonl")
        with open(log, "w", encoding="utf-8") as f:
            f.write(json.dumps({"dispatch_id": "X", "at": "t1", "result": "DISPATCHED"}) + "\n")
            f.write(json.dumps({"dispatch_id": "X", "at": "t2", "result": "VOIDED"}) + "\n")

        vg_src = os.path.join(TOOLS, "validation_gate.py")
        shutil.copy(vg_src, os.path.join(tmp, "tools", "validation_gate.py"))
        d_mod = load_mod("d_mod", os.path.join(tmp, "tools", "dispatch.py"))
        v_mod = load_mod("v_mod", os.path.join(tmp, "tools", "validation_gate.py"))

        recs = d_mod.log_records()
        disp_says = d_mod.already_dispatched("X", recs)
        val_says = "X" in v_mod.dispatched_ids()
        check("R7a dispatcher：VOIDED 後不算已派送", disp_says is False,
              "實際 %s" % disp_says)
        check("R7b validator：VOIDED 後不算已派送", val_says is False,
              "實際 %s" % val_says)
        check("R7c 兩邊語意一致", disp_says == val_says,
              "dispatcher=%s validator=%s" % (disp_says, val_says))

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    ok = sum(1 for _, c, _ in results if c)
    print("\n%d/%d 通過" % (ok, len(results)))
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
