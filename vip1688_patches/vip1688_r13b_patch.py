"""VIP1688 R13b: REPORT_8888 only, on top of R13 (production). 外本比/投本比 show 當日｜近5日累計: the previous trading days
are fetched in the background with insti_query_r1's own verified official fetch (listed + OTC) while the AI writes, then
cached per process; rows of older days never replace the newest-day rows used by the cards. No deploy, no LINE, no AI."""
import contextvars, datetime, difflib, glob, hashlib, json, os, subprocess, sys, traceback, types

HOME = os.path.expanduser("~")
SRC_SHA = "6c08021d1e4f1f1f6912e15d38635f2451a8ab11640095cda78d4a6692003d3b"
HELPER = '_VIP1688_R13_DAYROWS = {}\n_VIP1688_R13_PREV = {}\n\n\ndef _vip1688_r13b_capture_day():\n    """VIP1688_R13B: extend the R13 capture so every official day fetched by insti_query_r1 is also kept per trading\n    day (last 10 days); select_rows result unchanged."""\n    try:\n        import insti_query_r1 as _q\n        cur = _q.select_rows\n        if getattr(cur, "_vip1688_day", False):\n            return\n\n        def cap(rows):\n            out = cur(rows)\n            try:\n                ctx = _q._CONTEXT.get()\n                if ctx:\n                    _VIP1688_R13_DAYROWS[ctx[1]] = {str(r[1]).strip(): r for r in rows}\n                    for old in sorted(_VIP1688_R13_DAYROWS)[:-10]:\n                        _VIP1688_R13_DAYROWS.pop(old, None)\n                    newest = _VIP1688_R13_DAYROWS[max(_VIP1688_R13_DAYROWS)]\n                    if ctx[1] != max(_VIP1688_R13_DAYROWS):\n                        _VIP1688_R13_ROWS.clear()\n                        _VIP1688_R13_ROWS.update(newest)\n            except Exception:\n                pass\n            return out\n        cap._vip1688_cap = True\n        cap._vip1688_day = True\n        _q.select_rows = cap\n    except Exception as e:\n        print(f"[VIP1688_R13B_CAP_ERR] {type(e).__name__}: {str(e)[:160]}", flush=True)\n\n\n_vip1688_r13b_capture_day()\n\n\ndef _vip1688_r13b_backfill(n=5, budget=25):\n    """VIP1688_R13B: walk back from the latest official day with insti_query_r1\'s own verified fetch until n trading\n    days of listed+OTC rows are known (previous-day links memoised per process). Returns the days, newest first."""\n    import datetime as _dt\n    import time as _t\n    t0 = _t.time()\n    try:\n        import insti_query_r1 as _q\n        if not _VIP1688_R13_DAYROWS:\n            return []\n        deadline = _t.monotonic() + budget\n        cur = max(_VIP1688_R13_DAYROWS)\n        have = [cur]\n        while len(have) < n and _t.monotonic() < deadline:\n            prev = _VIP1688_R13_PREV.get(cur)\n            if prev is None or prev not in _VIP1688_R13_DAYROWS:\n                _q._fetch_latest(_dt.datetime.combine(cur - _dt.timedelta(days=1), _dt.time(18, 0), _q.TAIPEI), deadline)\n                older = [d for d in _VIP1688_R13_DAYROWS if d < cur]\n                if not older:\n                    break\n                prev = max(older)\n                _VIP1688_R13_PREV[cur] = prev\n            have.append(prev)\n            cur = prev\n        print(f"[VIP1688_R13B_BACKFILL] days={[str(d) for d in have]} ms={int((_t.time() - t0) * 1000)}", flush=True)\n        return have\n    except Exception as e:\n        print(f"[VIP1688_R13B_BACKFILL_ERR] {type(e).__name__}: {str(e)[:160]} ms={int((_t.time() - t0) * 1000)}", flush=True)\n        return []\n\n\ndef _vip1688_r13b_take_days():\n    """VIP1688_R13B: wait (max 15s) for the background backfill started by the fast path; keep the days for the cards."""\n    f = getattr(_VIP1688_R8_TLS, "r13_bf", None)\n    _VIP1688_R8_TLS.r13_bf = None\n    try:\n        days = f.result(timeout=15) if f is not None else []\n    except Exception:\n        days = []\n    _VIP1688_R8_TLS.r13_days = days or []\n    return days\n\n\ndef _vip1688_r13b_ratio_rows(sid, d):\n    """VIP1688_R13B: 外本比/投本比 rows, value = 當日｜近5日累計 (official net lots ÷ issued lots ×100%)."""\n    f = d.get("output_fields") if isinstance(d.get("output_fields"), dict) else {}\n    days = getattr(_VIP1688_R8_TLS, "r13_days", None) or []\n    lots = (_VIP1688_R13_SHARES.get("data") or {}).get(str(sid), 0) / 1000\n    rows = []\n    for label, key, idx in (("外本比 當日｜5日", "foreign_ratio", 3), ("投本比 當日｜5日", "trust_ratio", 4)):\n        day = _vip1688_r8_field(d, key) if f else ""\n        if not day:\n            rows.append(_vip1688_r8_row(label, "資料不足", _VIP1688_R8_NA))\n            continue\n        cum = ""\n        if lots > 0 and len(days) >= 2:\n            tot = sum((((_VIP1688_R13_DAYROWS.get(x) or {}).get(str(sid)) or (0, 0, 0, 0, 0, 0))[idx]) for x in days) / 1000\n            cum = f"{tot / lots * 100:+.3f}%" + ("" if len(days) >= 5 else f"({len(days)}日)")\n        rows.append(_vip1688_r8_row(label, f"{day}｜{cum or \'—\'}", _vip1688_r8_color(_vip1688_r8_num(day))))\n    return rows\n\n\n'
ANCHOR = "def _vip1688_r7_stock_line("
BF_OLD = '    print(f"[VIP1688_R13_FETCH] fast={len(fast)}/{len(syms)}'
BF_NEW = "    _VIP1688_R8_TLS.r13_bf = _vip1688_r9_start(_vip1688_r13b_backfill)  # VIP1688_R13B\n" + BF_OLD
TAKE_OLD = "    _r9 = _vip1688_r9_take()  # VIP1688_R9\n"
TAKE_NEW = TAKE_OLD + "    _vip1688_r13b_take_days()  # VIP1688_R13B\n"
ROWS_OLD = ('    for label, key in (("外資", "foreign_buy"), ("投信", "trust_buy"), ("外本比(當日)", "foreign_ratio"),\n'
            '                       ("投本比(當日)", "trust_ratio")):  # VIP1688_R13\n'
            '        v = _vip1688_r8_field(d, key)\n'
            '        rows.append(_vip1688_r8_row(label, v or "資料不足", _vip1688_r8_color(_vip1688_r8_num(v)) if v else _VIP1688_R8_NA))\n')
ROWS_NEW = ('    for label, key in (("外資", "foreign_buy"), ("投信", "trust_buy")):\n'
            '        v = _vip1688_r8_field(d, key)\n'
            '        rows.append(_vip1688_r8_row(label, v or "資料不足", _vip1688_r8_color(_vip1688_r8_num(v)) if v else _VIP1688_R8_NA))\n'
            '    rows += _vip1688_r13b_ratio_rows(sid, d)  # VIP1688_R13B\n')
EDITS = [("anchor", ANCHOR, HELPER + ANCHOR), ("backfill", BF_OLD, BF_NEW), ("take", TAKE_OLD, TAKE_NEW), ("rows", ROWS_OLD, ROWS_NEW)]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def need(cond, msg, **dbg):
    if not cond:
        raise RuntimeError(f"{msg} | debug={dbg}")


def find_src():
    hits = [d for d in sorted(glob.glob(os.path.join(HOME, "vip1688_r13_2026*", "source")))
            if os.path.isfile(os.path.join(d, "app.py")) and sha(open(os.path.join(d, "app.py"), "rb").read()) == SRC_SHA]
    need(hits, "R13 candidate with expected SHA not found", searched=glob.glob(os.path.join(HOME, "vip1688_r13_*")))
    return hits[-1]


def patch(t):
    need("_vip1688_r13b_" not in t, "R13b already applied")
    for name, old, new in EDITS:
        need(t.count(old) == 1, f"{name} count != 1", count=t.count(old))
        t = t.replace(old, new)
    return t


def behaviour(t, logs):
    s = t.index("import threading as _vip1688_r8_threading")
    e = t.index(ANCHOR)
    tz = datetime.timezone(datetime.timedelta(hours=8))
    fake = types.ModuleType("insti_query_r1")
    fake.TAIPEI = tz
    fake._CONTEXT = contextvars.ContextVar("x", default=None)
    fake.select_rows = lambda rows: (["B"], ["S"])
    trading = [datetime.date(2026, 10, d) for d in (1, 2, 5, 6, 7, 8)]
    net = {d: (i + 1) * 1000 for i, d in enumerate(trading)}

    def fetch_latest(now, deadline):
        day = max(d for d in trading if d <= now.date())
        tok = fake._CONTEXT.set((deadline, day, []))
        try:
            fake.select_rows([("上市", "2340", "台亞", net[day], -net[day], 0)])
        finally:
            fake._CONTEXT.reset(tok)
    fake._fetch_latest = fetch_latest
    old_mod = sys.modules.get("insti_query_r1")
    sys.modules["insti_query_r1"] = fake
    r = {}
    try:
        ns = {"FlexSendMessage": lambda **k: k}
        exec(compile(t[s:e], "r13b", "exec"), ns)
        r["chained_wrappers"] = getattr(fake.select_rows, "_vip1688_day", False) and getattr(fake.select_rows, "_vip1688_cap", False)
        fetch_latest(datetime.datetime(2026, 10, 12, 10, tzinfo=tz), 0)
        r["newest_rows"] = ns["_VIP1688_R13_ROWS"]["2340"][3] == 6000
        days = ns["_vip1688_r13b_backfill"]()
        r["backfill_5_days"] = [str(d) for d in days] == ["2026-10-08", "2026-10-07", "2026-10-06", "2026-10-05", "2026-10-02"]
        r["old_days_do_not_replace_newest"] = ns["_VIP1688_R13_ROWS"]["2340"][3] == 6000
        calls = []
        fake._fetch_latest = lambda now, deadline: calls.append(now) or fetch_latest(now, deadline)
        r["memoised"] = len(ns["_vip1688_r13b_backfill"]()) == 5 and calls == []
    finally:
        if old_mod is None:
            sys.modules.pop("insti_query_r1", None)
        else:
            sys.modules["insti_query_r1"] = old_mod
    ns["_VIP1688_R13_SHARES"].update(day=None, data={"2340": 438623000.0})
    ns["_VIP1688_R8_TLS"].r13_bf = types.SimpleNamespace(result=lambda timeout=None: days)
    ns["_vip1688_r13b_take_days"]()
    d = {"name": "台亞", "output_fields": {"foreign_ratio": {"value": "+1.368%"}, "trust_ratio": {"value": "-1.368%"},
                                         "foreign_buy": {"value": "+6,000張"}}}
    rows = json.dumps(ns["_vip1688_r13b_ratio_rows"]("2340", d), ensure_ascii=False)
    tot = (6 + 5 + 4 + 3 + 2) * 1000 / 1000 / 438623 * 100
    r["five_day_values"] = f"+1.368%｜{tot:+.3f}%" in rows and f"-1.368%｜{-tot:+.3f}%" in rows and "#E74C3C" in rows and "#27AE60" in rows
    ns["_VIP1688_R8_TLS"].r13_days = days[:3]
    r["partial_days_labelled"] = "(3日)" in json.dumps(ns["_vip1688_r13b_ratio_rows"]("2340", d), ensure_ascii=False)
    r["missing_gray"] = "資料不足" in json.dumps(ns["_vip1688_r13b_ratio_rows"]("2340", {"output_fields": {}}), ensure_ascii=False)
    ns["_VIP1688_R8_TLS"].r13_bf = types.SimpleNamespace(result=lambda timeout=None: 1 / 0)
    r["take_never_raises"] = ns["_vip1688_r13b_take_days"]() == [] and ns["_VIP1688_R8_TLS"].r13_days == []
    b = json.dumps(ns["_vip1688_r8_stock_bubble"]("2340", d, []), ensure_ascii=False)
    r["card_rows"] = "外本比 當日｜5日" in b and "投本比 當日｜5日" in b and "外本比(當日)" not in b
    r["wiring"] = (t.index("_VIP1688_R8_TLS.r13_bf = _vip1688_r9_start(_vip1688_r13b_backfill)") < t.index('print(f"[VIP1688_R13_FETCH]')
                   and t.index("_vip1688_r13b_take_days()  # VIP1688_R13B") > t.index("_r9 = _vip1688_r9_take()"))
    return r


def main():
    out = {"status": "STOP", "revision": "VIP1688_R13B", "deployed": False, "line_sent": False, "ai_called": False}
    dst = None
    try:
        src = find_src()
        app = os.path.join(src, "app.py")
        old = open(app, "rb").read().decode("utf-8")
        need("vip1688_cache" not in old, "production source references vip1688_cache")
        new = patch(old)
        compile(new, "app.py", "exec", dont_inherit=True)
        logs = []
        import builtins
        real_print = builtins.print
        builtins.print = lambda *a, **k: logs.append(" ".join(str(x) for x in a))
        try:
            checks = behaviour(new, logs)
        finally:
            builtins.print = real_print
        need(all(checks.values()), "behaviour check failed", checks=checks, logs=logs[-6:])
        diff = [l for l in difflib.unified_diff(old.splitlines(), new.splitlines(), "r13", "r13b", n=0, lineterm="")
                if l[:1] in "+-" and l[:3] not in ("+++", "---")]
        removed = [l[1:] for l in diff if l.startswith("-")]
        need(len(removed) == 2, "unexpected removed line count", removed=removed[:6])
        dst = os.path.join(HOME, "vip1688_r13b_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        os.mkdir(dst)
        subprocess.run(["cp", "-al", src, os.path.join(dst, "source")], check=True)
        target = os.path.join(dst, "source", "app.py")
        tmp = target + ".r13btmp"
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
    print("R13B_RESULT " + json.dumps(out, ensure_ascii=False))
    return 0 if out["status"] == "candidate_ready" else 2


if __name__ == "__main__":
    sys.exit(main())
