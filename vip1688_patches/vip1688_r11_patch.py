"""VIP1688 R11: REPORT_8888 only, on top of R10. Fix: the report cache replays the short summary text, and the card
renderer took the carousel from a thread-local that was never cleared, so a cache hit could show a stale carousel (other
thread / older run) or none. Now each carousel is stored under a unique id written into the report text (memory + the
app's disk cache, 24h); the renderer looks it up by that id and always clears the thread-local. No deploy, no LINE, no AI."""
import datetime, difflib, glob, hashlib, json, os, subprocess, sys, traceback, types

HOME = os.path.expanduser("~")
SRC_SHA = "fbcd3b2401e1f8a5217a7f3a1b057777825caca307004f49f87fc9b09e769553"
HELPER = '_VIP1688_R11_STORE = {}\n\n\ndef _vip1688_r11_remember(text, carousel):\n    """VIP1688_R11: keep the carousel under a unique id carried in the report text, so a report-cache hit replays\n    exactly these cards (never a stale carousel left on a reused worker thread)."""\n    import uuid as _u\n    rid = _u.uuid4().hex[:12]\n    _VIP1688_R11_STORE[rid] = carousel\n    while len(_VIP1688_R11_STORE) > 16:\n        _VIP1688_R11_STORE.pop(next(iter(_VIP1688_R11_STORE)))\n    try:\n        c = globals().get("cache")\n        if c is not None and hasattr(c, "set"):\n            c.set(f"vip1688_r11::{rid}", carousel, expire=86400)\n    except Exception as e:\n        print(f"[VIP1688_R11_STORE_ERR] {type(e).__name__}: {str(e)[:160]}", flush=True)\n    print(f"[VIP1688_R11_STORE] id={rid}", flush=True)\n    return f"{text}\\n🆔 VIP1688-{rid}"\n\n\ndef _vip1688_r11_take(content):\n    """VIP1688_R11: carousel for this exact report text (fresh run or cache hit); None -> original builder."""\n    import re as _re\n    _VIP1688_R8_TLS.payload = None\n    m = _re.search(r"VIP1688-([0-9a-f]{12})", str(content or ""))\n    if not m:\n        print("[VIP1688_R11_TAKE] miss reason=no_id", flush=True)\n        return None\n    rid, src = m.group(1), "mem"\n    c = _VIP1688_R11_STORE.get(rid)\n    if c is None:\n        src = "disk"\n        try:\n            cc = globals().get("cache")\n            c = cc.get(f"vip1688_r11::{rid}") if (cc is not None and hasattr(cc, "get")) else None\n        except Exception:\n            c = None\n    if not isinstance(c, dict) or not c.get("contents"):\n        print(f"[VIP1688_R11_TAKE] miss reason=not_stored id={rid}", flush=True)\n        return None\n    print(f"[VIP1688_R11_TAKE] hit src={src} id={rid} bubbles={len(c[\'contents\'])}", flush=True)\n    return FlexSendMessage(alt_text="💎 含金量最高發財1688精華報（左右滑動查看完整內容）", contents=c)\n\n\n'
ANCHOR = "def _vip1688_r7_stock_line("
RET_OLD = ('        return f"💎【含金量最高發財1688精華報】\\n📅 資料日 {date_note} 收盤｜{period_note}\\n'
           '👉 完整內容請左右滑動 {len(carousel[\'contents\'])} 張卡片"\n')
RET_NEW = ('        return _vip1688_r11_remember(f"💎【含金量最高發財1688精華報】\\n📅 資料日 {date_note} 收盤｜{period_note}\\n'
           '👉 完整內容請左右滑動 {len(carousel[\'contents\'])} 張卡片", carousel)  # VIP1688_R11\n')
TAKE_OLD = "    _r8 = _vip1688_r8_take()  # VIP1688_R8\n"
TAKE_NEW = "    _r8 = _vip1688_r11_take(content)  # VIP1688_R11\n"
EDITS = [("anchor", ANCHOR, HELPER + ANCHOR), ("stash_return", RET_OLD, RET_NEW), ("take", TAKE_OLD, TAKE_NEW)]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def need(cond, msg, **dbg):
    if not cond:
        raise RuntimeError(f"{msg} | debug={dbg}")


def find_src():
    hits = [d for d in sorted(glob.glob(os.path.join(HOME, "vip1688_r10_2026*", "source")))
            if os.path.isfile(os.path.join(d, "app.py")) and sha(open(os.path.join(d, "app.py"), "rb").read()) == SRC_SHA]
    need(hits, "R10 candidate with expected SHA not found", searched=glob.glob(os.path.join(HOME, "vip1688_r10_*")))
    return hits[-1]


def patch(t):
    need("_vip1688_r11_" not in t, "R11 already applied")
    for name, old, new in EDITS:
        need(t.count(old) == 1, f"{name} count != 1", count=t.count(old))
        t = t.replace(old, new)
    return t


class _Disk(dict):
    def set(self, k, v, expire=None):
        self[k] = v


def behaviour(t):
    s = t.index("import threading as _vip1688_r8_threading")
    e = t.index(ANCHOR)
    disk = _Disk()
    ns = {"FlexSendMessage": lambda **k: k, "cache": disk}
    exec(compile(t[s:e], "r11", "exec"), ns)
    r = {}
    mk = lambda n: {"name": n, "output_fields": {"price": {"value": "100"}, "change": {"value": "1"}}}
    res = [("3653", mk("健策"))]
    txt = ns["_vip1688_r8_stash"]("ORIG", ["3653"], res, [], [], [], {}, "", "10/08", "休市")
    rid = txt.rsplit("VIP1688-", 1)[-1]
    stored = ns["_VIP1688_R11_STORE"].get(rid)
    r["stash_text_has_id"] = len(rid) == 12 and txt.startswith("💎【含金量最高發財1688精華報】") and "張卡片\n🆔 VIP1688-" in txt and isinstance(stored, dict)
    r["disk_copy"] = disk.get(f"vip1688_r11::{rid}") is stored
    f1 = ns["_vip1688_r11_take"]("前綴\n" + txt + "\n後綴")
    r["fresh_take_same_cards"] = f1 is not None and f1["contents"] is stored and ns["_VIP1688_R8_TLS"].payload is None
    f2 = ns["_vip1688_r11_take"](txt)
    r["cache_hit_replays"] = f2 is not None and f2["contents"] is stored
    ns["_VIP1688_R11_STORE"].clear()
    f3 = ns["_vip1688_r11_take"](txt)
    r["disk_fallback"] = f3 is not None and f3["contents"] is stored
    ns["_VIP1688_R8_TLS"].payload = {"type": "carousel", "contents": [{"stale": 1}]}
    r["stale_tls_never_used"] = ns["_vip1688_r11_take"]("舊快取文字，沒有編號") is None and ns["_VIP1688_R8_TLS"].payload is None
    r["unknown_id_none"] = ns["_vip1688_r11_take"]("🆔 VIP1688-0123456789ab") is None
    for i in range(20):
        ns["_vip1688_r11_remember"]("x", {"contents": [i]})
    r["store_bounded"] = len(ns["_VIP1688_R11_STORE"]) == 16
    bad = ns["_vip1688_r8_stash"]("ORIG", ["3653"], 5, [], [], [], {}, "", "10/08", "")
    r["stash_failure_keeps_original"] = bad == "ORIG"
    r["renderer_wired"] = t.count("_vip1688_r11_take(content)  # VIP1688_R11") == 1 and "_vip1688_r8_take()  # VIP1688_R8" not in t
    return r


def main():
    out = {"status": "STOP", "revision": "VIP1688_R11", "deployed": False, "line_sent": False, "ai_called": False}
    dst = None
    try:
        src = find_src()
        app = os.path.join(src, "app.py")
        old = open(app, "rb").read().decode("utf-8")
        new = patch(old)
        compile(new, "app.py", "exec", dont_inherit=True)
        checks = behaviour(new)
        need(all(checks.values()), "behaviour check failed", checks=checks)
        diff = [l for l in difflib.unified_diff(old.splitlines(), new.splitlines(), "r10", "r11", n=0, lineterm="")
                if l[:1] in "+-" and l[:3] not in ("+++", "---")]
        removed = [l[1:] for l in diff if l.startswith("-")]
        need(len(removed) == 2, "unexpected removed line count", removed=removed[:4])
        dst = os.path.join(HOME, "vip1688_r11_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        os.mkdir(dst)
        subprocess.run(["cp", "-al", src, os.path.join(dst, "source")], check=True)
        target = os.path.join(dst, "source", "app.py")
        tmp = target + ".r11tmp"
        with open(tmp, "wb") as fh:
            fh.write(new.encode("utf-8"))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
        nb = open(target, "rb").read()
        need(nb == new.encode("utf-8"), "written app mismatch")
        need(sha(open(app, "rb").read()) == SRC_SHA, "SOURCE CHANGED - stop")
        need(os.stat(target).st_nlink == 1, "candidate app still hardlinked", nlink=os.stat(target).st_nlink)
        out.update(status="candidate_ready", base=src, candidate=os.path.join(dst, "source"), new_app_sha=sha(nb),
                   checks=checks, removed_lines=len(removed), added_lines=len(diff) - len(removed))
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
        out["traceback"] = traceback.format_exc()[-1500:]
        out["partial_candidate"] = dst
    print("R11_RESULT " + json.dumps(out, ensure_ascii=False))
    return 0 if out["status"] == "candidate_ready" else 2


if __name__ == "__main__":
    sys.exit(main())
