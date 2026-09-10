#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tru-Mi 每日流程互斥鎖（Canonical Rule ⑤：Mutual Exclusion）

2026-09-07 CONCURRENCY INCIDENT 的修正。當日主檔在一支流程執行到一半時
被另一個 writer 於 09:54:27 覆寫。舊 Step 0 只靠「開跑時看一眼日期／星期」，
那是偵測不是互斥——衝突發生在開跑之後，開跑時看不到。

本模組把 Step 0 升級成真正的鎖：
    取得 lock → 記 instance_id / pid / start_time / fingerprint
              → 執行 → 寫入 → health check → 釋放 lock

用法：
    python tools/runlock.py acquire --task trumi_daily
        exit 0  已取得鎖，可以往下跑（stdout 印 instance_id，請保留）
        exit 4  CONCURRENCY_BLOCKED，鎖被別人持有 → 不 discovery、不寫入、不派送

    python tools/runlock.py status
    python tools/runlock.py release --instance <instance_id>
    python tools/runlock.py release --force        # 只在確認 owner 已死時使用

設計取捨：
- 鎖檔放在工作資料夾內的 runtime/，跟著雲端同步，跨 runtime 可見。
  這正是需要的——衝突的兩個 writer 可能根本不在同一台機器上。
- 因為跨 runtime，**不能**用 os.kill(pid, 0) 判斷 owner 是否存活：
  容器的 pid 對 Windows 沒有意義。改用「心跳 + TTL」：
  持有者每次呼叫 heartbeat 更新 heartbeat_at；超過 TTL 沒心跳才算 stale。
- **鎖用「檔案裡的 state 欄位」表示，不是用「檔案存不存在」表示。**
  這個工作資料夾是雲端掛載磁碟，os.remove 會回 Operation not permitted
  （實測 2026-09-07），所以任何 delete-to-unlock 的設計在這裡都跑不起來。
  released 是寫進去的，不是刪出來的。
- 首次建檔用 O_CREAT|O_EXCL；之後是 read-modify-write，不是原子操作，
  因此取鎖後會 re-read 確認贏家（write-then-verify），擋掉現實中的 race。
  這裡要擋的是相隔數十秒到數分鐘的兩個 instance，不是微秒級競爭。
"""
import argparse
import hashlib
import json
import os
import secrets
import sys
import time
from datetime import datetime, timezone, timedelta

TPE = timezone(timedelta(hours=8))
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNTIME = os.path.join(BASE, "runtime")

DEFAULT_TTL = 45 * 60          # 45 分鐘沒心跳視為 stale
HEARTBEAT_HINT = 5 * 60        # 建議每 5 分鐘打一次心跳

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_BLOCKED = 4               # CONCURRENCY_BLOCKED


def now():
    return datetime.now(TPE)


def iso(dt=None):
    return (dt or now()).isoformat(timespec="seconds")


def lock_path(task):
    return os.path.join(RUNTIME, "%s.lock" % task)


def read_lock(task):
    p = lock_path(task)
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        # 壞掉的鎖檔本身就是異常訊號，不要當成「沒有鎖」
        return {"_corrupt": True, "path": p}
    d["_path"] = p
    d["_age_sec"] = int(time.time() - os.path.getmtime(p))
    return d


def is_held(d):
    return bool(d) and not d.get("_corrupt") and d.get("state") == "held"


def is_stale(d, ttl):
    return d.get("_age_sec", 0) > ttl


def write_lock(task, payload):
    """雲端掛載磁碟不允許 remove，所以一律用覆寫，不用刪除。"""
    p = lock_path(task)
    try:
        fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        return True
    except FileExistsError:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        return False


def acquire(task, ttl, owner_note):
    os.makedirs(RUNTIME, exist_ok=True)
    existing = read_lock(task)

    if existing and existing.get("_corrupt"):
        print("CONCURRENCY_BLOCKED: 鎖檔存在但無法解析 → %s" % lock_path(task))
        print("  → 人工確認沒有其他 instance 在跑之後，用 release --force 清除")
        return EXIT_BLOCKED

    if is_held(existing):
        if not is_stale(existing, existing.get("ttl_sec", ttl)):
            print("CONCURRENCY_BLOCKED: %s 已被其他 instance 持有" % task)
            print("  instance_id : %s" % existing.get("instance_id"))
            print("  started_at  : %s" % existing.get("started_at"))
            print("  last_beat   : %s 秒前（TTL %s 秒）"
                  % (existing.get("_age_sec"), existing.get("ttl_sec", ttl)))
            print("  runtime     : %s" % existing.get("runtime"))
            print("  → 不 discovery、不寫入 HTML、不派送；只回報狀態後結束")
            return EXIT_BLOCKED
        print("NOTE: 發現 stale lock（%s 秒無心跳 > TTL %s），接管中"
              % (existing.get("_age_sec"), existing.get("ttl_sec", ttl)))
        print("  前一持有者：%s / %s" % (existing.get("instance_id"), existing.get("started_at")))

    instance_id = "%s-%s-%s" % (task, now().strftime("%Y%m%d-%H%M%S"), secrets.token_hex(2))
    payload = {
        "state": "held",
        "instance_id": instance_id,
        "task": task,
        "pid": os.getpid(),
        "started_at": iso(),
        "heartbeat_at": iso(),
        "ttl_sec": ttl,
        "runtime": os.environ.get("HOSTNAME") or "unknown",
        "note": owner_note or "",
        "took_over_from": existing.get("instance_id") if is_held(existing) else None,
        "fingerprint": fingerprint(),
    }
    write_lock(task, payload)

    # write-then-verify：覆寫不是原子操作，回頭確認自己是不是贏家
    time.sleep(1.5)
    check = read_lock(task)
    if not check or check.get("instance_id") != instance_id:
        print("CONCURRENCY_BLOCKED: 取鎖後複驗失敗，鎖已被 %s 搶走"
              % (check or {}).get("instance_id"))
        return EXIT_BLOCKED

    print(instance_id)
    return EXIT_OK


def fingerprint():
    """記下取鎖當下來源檔的樣子，收尾時比對，可抓到『鎖外的 writer』。"""
    out = {}
    for name in ("threads_wedding_ring_dashboard.html", "index.html"):
        p = os.path.join(BASE, name)
        if os.path.exists(p):
            st = os.stat(p)
            out[name] = {"size": st.st_size, "mtime": int(st.st_mtime)}
    return out


def heartbeat(task, instance):
    d = read_lock(task)
    if not d or d.get("_corrupt"):
        print("FAIL: 沒有可更新的鎖")
        return EXIT_ERROR
    if instance and d.get("instance_id") != instance:
        print("FAIL: 鎖的持有者是 %s，不是 %s" % (d.get("instance_id"), instance))
        return EXIT_ERROR
    d.pop("_path", None)
    d.pop("_age_sec", None)
    d["heartbeat_at"] = iso()
    write_lock(task, d)
    print("OK: heartbeat %s" % d["heartbeat_at"])
    return EXIT_OK


def content_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def checkpoint(task, instance, note, expect, validated):
    """
    接受**本次已驗證的合法變更**，而不是「接受現在碰巧存在的內容」。

    為什麼需要 checkpoint：fingerprint 是取鎖當下拍的，它分不出「我自己剛剛合法寫的」
    和「別人偷偷寫的」——兩者看起來都只是 mtime 變了。不 checkpoint 的話 release
    每次都會報 drift，久了就會被當雜訊忽略，那等於把警報關掉。

    但 checkpoint 本身會形成新的 trust boundary（2026-09-07 指出）：
    若有其他 writer 在鎖持有期間改了檔，合法 holder 接著 checkpoint，
    就會把未授權修改一起洗白。所以它不是無條件的「重新掃描磁碟」。

    四個必要條件，缺一不可：
        caller == current lock owner
        AND lock state == HELD
        AND post-write validation == PASS   （--validated，由呼叫端提供證據）
        AND 實際 hash == 本次預期的 hash     （--expect file=hash，逐檔比對）

    語意：
        before_hash → authorized mutation → expected_after_hash → validation PASS
                   → checkpoint(expected_after_hash)
    若磁碟上的內容不等於 expected_after_hash，代表這段期間有第三方寫入，
    **拒絕 checkpoint**，讓 drift 留在那裡等人看，而不是靜靜吸收掉。
    """
    d = read_lock(task)
    if not is_held(d):
        print("REFUSED: 沒有持有中的鎖可 checkpoint（lock state != HELD）")
        return EXIT_ERROR
    if not instance:
        print("REFUSED: 必須以 --instance 指明呼叫者，checkpoint 不接受匿名呼叫")
        return EXIT_ERROR
    if d.get("instance_id") != instance:
        print("REFUSED: 持有者是 %s，不是 %s——非持有者不得 checkpoint"
              % (d.get("instance_id"), instance))
        return EXIT_ERROR
    if not validated:
        print("REFUSED: 缺 --validated，checkpoint 必須在寫後驗證 PASS 之後才能做")
        print("  → 正確順序：authorized write → dashboard_check/validation_gate PASS → checkpoint")
        return EXIT_ERROR
    if not expect:
        print("REFUSED: 缺 --expect，checkpoint 只接受本次預期的 hash，不接受掃描現況")
        print("  → 用法：--expect threads_wedding_ring_dashboard.html=<sha256前16碼> [--expect index.html=...]")
        return EXIT_ERROR

    mismatches, accepted = [], []
    for item in expect:
        if "=" not in item:
            print("REFUSED: --expect 格式應為 檔名=hash，收到 %r" % item)
            return EXIT_ERROR
        name, want = item.split("=", 1)
        p = os.path.join(BASE, name.strip())
        if not os.path.exists(p):
            mismatches.append("%s 不存在" % name)
            continue
        got = content_hash(p)
        if got != want.strip():
            mismatches.append("%s 實際 %s ≠ 預期 %s" % (name, got, want.strip()))
        else:
            accepted.append("%s %s" % (name, got))

    if mismatches:
        print("REFUSED: 磁碟內容與本次預期不符——這段期間可能有第三方寫入")
        for m in mismatches:
            print("  · " + m)
        print("  → 不吸收這次 drift。請先查清楚是誰寫的，不要用 checkpoint 洗白。")
        return EXIT_BLOCKED

    drift = compare_fingerprint(d.get("fingerprint") or {})
    d.pop("_path", None)
    d.pop("_age_sec", None)
    d["fingerprint"] = fingerprint()
    d["heartbeat_at"] = iso()
    d.setdefault("checkpoints", []).append({
        "at": iso(),
        "note": note or "",
        "validated": validated,
        "expected": expect,
        "drift_absorbed": drift,
    })
    write_lock(task, d)
    print("OK: 已接受本次已驗證的合法變更（%s）" % (note or "no note"))
    for line in accepted:
        print("  hash 相符：%s" % line)
    for line in drift:
        print("  納入本次授權寫入：%s" % line)
    return EXIT_OK


def release(task, instance, force):
    d = read_lock(task)
    if not d:
        print("OK: 本來就沒有鎖")
        return EXIT_OK
    if d.get("_corrupt"):
        if not force:
            print("FAIL: 鎖檔損毀，需要 --force")
            return EXIT_ERROR
        write_lock(task, {"state": "released", "released_at": iso(),
                          "note": "forced release of corrupt lock"})
        print("OK: 已強制標記為 released（損毀鎖檔）")
        return EXIT_OK
    if d.get("state") == "released":
        print("OK: 鎖已是 released 狀態")
        return EXIT_OK
    if not force and instance and d.get("instance_id") != instance:
        print("FAIL: 你不是持有者（持有者 %s），拒絕釋放" % d.get("instance_id"))
        print("  → 確認對方確實已結束後再用 --force")
        return EXIT_ERROR

    drift = compare_fingerprint(d.get("fingerprint") or {})
    d.pop("_path", None)
    d.pop("_age_sec", None)
    d["state"] = "released"
    d["released_at"] = iso()
    d["released_by"] = "force" if force else (instance or "owner")
    d["drift_on_release"] = drift
    write_lock(task, d)
    if drift:
        print("WARN: 釋放鎖，但偵測到鎖期間來源檔被改動（可能有鎖外 writer）")
        for line in drift:
            print("  · " + line)
        print("OK: 鎖已釋放（帶 WARN）")
    else:
        print("OK: 鎖已釋放")
    return EXIT_OK


def compare_fingerprint(old):
    """收尾比對。只回報差異，不判斷誰對——判斷交給人。"""
    drift = []
    for name, before in old.items():
        p = os.path.join(BASE, name)
        if not os.path.exists(p):
            drift.append("%s 在鎖期間消失" % name)
            continue
        st = os.stat(p)
        if int(st.st_mtime) != before.get("mtime") or st.st_size != before.get("size"):
            drift.append("%s size %s→%s, mtime %s→%s"
                         % (name, before.get("size"), st.st_size,
                            before.get("mtime"), int(st.st_mtime)))
    return drift


def status(task):
    d = read_lock(task)
    if not d:
        print("UNLOCKED: %s 目前沒有鎖" % task)
        return EXIT_OK
    if d.get("_corrupt"):
        print("CORRUPT: 鎖檔存在但無法解析 → %s" % d["path"])
        return EXIT_BLOCKED
    if d.get("state") == "released":
        print("UNLOCKED: %s（上一輪 %s 於 %s 釋放）"
              % (task, d.get("instance_id"), d.get("released_at")))
        if d.get("drift_on_release"):
            print("  上次釋放時帶 WARN：")
            for line in d["drift_on_release"]:
                print("    · " + line)
        return EXIT_OK
    stale = is_stale(d, d.get("ttl_sec", DEFAULT_TTL))
    print("%s: %s" % ("STALE" if stale else "LOCKED", task))
    for k in ("instance_id", "started_at", "heartbeat_at", "pid", "runtime", "note"):
        print("  %-12s %s" % (k, d.get(k)))
    print("  %-12s %s 秒前（TTL %s）" % ("last_beat", d.get("_age_sec"), d.get("ttl_sec")))
    drift = compare_fingerprint(d.get("fingerprint") or {})
    if drift:
        print("  WARN 鎖期間來源檔已被改動：")
        for line in drift:
            print("    · " + line)
    return EXIT_OK if not stale else EXIT_OK


def main():
    ap = argparse.ArgumentParser(description="Tru-Mi 每日流程互斥鎖")
    ap.add_argument("action",
                    choices=["acquire", "release", "status", "heartbeat", "checkpoint"])
    ap.add_argument("--task", default="trumi_daily")
    ap.add_argument("--instance", default=os.environ.get("TRUMI_INSTANCE_ID"))
    ap.add_argument("--ttl", type=int, default=DEFAULT_TTL)
    ap.add_argument("--note", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--expect", action="append", metavar="FILE=HASH",
                    help="checkpoint 專用：本次預期的檔案 hash（sha256 前 16 碼），可重複")
    ap.add_argument("--validated", metavar="EVIDENCE",
                    help="checkpoint 專用：寫後驗證 PASS 的證據，例如 dashboard_check:PASS")
    a = ap.parse_args()

    if a.action == "acquire":
        return acquire(a.task, a.ttl, a.note)
    if a.action == "release":
        return release(a.task, a.instance, a.force)
    if a.action == "heartbeat":
        return heartbeat(a.task, a.instance)
    if a.action == "checkpoint":
        return checkpoint(a.task, a.instance, a.note, a.expect, a.validated)
    return status(a.task)


if __name__ == "__main__":
    sys.exit(main())
