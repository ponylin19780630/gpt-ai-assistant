"""VIP1688 R13: REPORT_8888 only, on top of R11. Fast path for the 5 DNA stocks, formulas verified against the original
path in R12c/R12d (Yahoo daily K + official cross-checked 三大法人 rows; listed and OTC); any stock it cannot build falls
back to the original fetch (ETF prewarm only then). Stock cards add 外本比/投本比 (當日). No deploy, no LINE, no AI."""
import datetime, difflib, glob, hashlib, json, os, subprocess, sys, traceback, types

HOME = os.path.expanduser("~")
SRC_SHA = "c37e482599b42e430c2e8b9de7d174cd65b403199799d57619263143c7965a13"
HELPER = '_VIP1688_R13_ROWS = {}\n_VIP1688_R13_SHARES = {"day": None, "data": {}}\n\n\ndef _vip1688_r13_capture_install():\n    """VIP1688_R13: keep a copy of the official, cross-checked per-stock 三大法人 rows (listed + OTC) that insti_query_r1\n    passes to select_rows; its result is returned unchanged."""\n    try:\n        import insti_query_r1 as _q\n        if getattr(_q.select_rows, "_vip1688_cap", False):\n            return\n        orig = _q.select_rows\n\n        def cap(rows):\n            out = orig(rows)\n            try:\n                _VIP1688_R13_ROWS.clear()\n                _VIP1688_R13_ROWS.update({str(r[1]).strip(): r for r in rows})\n            except Exception:\n                pass\n            return out\n        cap._vip1688_cap = True\n        _q.select_rows = cap\n    except Exception as e:\n        print(f"[VIP1688_R13_CAP_ERR] {type(e).__name__}: {str(e)[:160]}", flush=True)\n\n\n_vip1688_r13_capture_install()\n\n\ndef _vip1688_r13_shares():\n    """VIP1688_R13: issued shares per code from official company basic data (TWSE t187ap03_L + TPEx mopsfin_t187ap03_O),\n    cached per Taipei day."""\n    import datetime as _dt\n    day = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=8))).date()\n    if _VIP1688_R13_SHARES["day"] == day and _VIP1688_R13_SHARES["data"]:\n        return _VIP1688_R13_SHARES["data"]\n    out = {}\n    for url, ck, sk in (("https://openapi.twse.com.tw/v1/opendata/t187ap03_L", "公司代號", "已發行普通股數或TDR原股發行股數"),\n                        ("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O", "SecuritiesCompanyCode", "IssueShares")):\n        try:\n            for r in _vip1688_r9_json(url, 15) or []:\n                k = {str(a).strip(): v for a, v in r.items()} if isinstance(r, dict) else {}\n                try:\n                    v = float(str(k.get(sk, "")).replace(",", ""))\n                except ValueError:\n                    continue\n                if v > 0:\n                    out[str(k.get(ck, "")).strip()] = v\n        except Exception as e:\n            print(f"[VIP1688_R13_SHARES_ERR] {url.rsplit(\'/\', 1)[-1]} {type(e).__name__}: {str(e)[:100]}", flush=True)\n    if out:\n        _VIP1688_R13_SHARES.update(day=day, data=out)\n    return out\n\n\ndef _vip1688_r13_yahoo(sid):\n    """VIP1688_R13: Yahoo daily K for one code (.TW, then .TWO)."""\n    import requests as _rq\n    last = None\n    for suf in (".TW", ".TWO"):\n        r = _rq.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sid}{suf}", params={"range": "2y", "interval": "1d"},\n                    headers={"User-Agent": "Mozilla/5.0"}, timeout=10)\n        last = r.status_code\n        try:\n            res = ((r.json().get("chart") or {}).get("result") or [None])[0]\n        except Exception:\n            res = None\n        if res and res.get("timestamp"):\n            return res\n    raise RuntimeError(f"yahoo no data last_status={last}")\n\n\ndef _vip1688_r13_ratios(sid, fields, shares):\n    """VIP1688_R13: 外本比/投本比 (當日) = official foreign / trust net lots ÷ issued lots × 100%."""\n    row = _VIP1688_R13_ROWS.get(str(sid))\n    lots = (shares or {}).get(str(sid), 0) / 1000\n    if row and lots > 0:\n        fields["foreign_ratio"] = {"value": f"{row[3] / 1000 / lots * 100:+.3f}%"}\n        fields["trust_ratio"] = {"value": f"{row[4] / 1000 / lots * 100:+.3f}%"}\n\n\ndef _vip1688_r13_build(sid, res, shares, now=None):\n    """VIP1688_R13: card fields in the original output_fields shape. Verified against the original path (R12c/R12d):\n    price/change/volume = latest bar; MA5/20/60 SMA, RSI Wilder 14, MACD = DIF(12,26), KD 14 (com=2) on completed bars\n    (today\'s bar is excluded until 14:30 Taipei); foreign/trust = official rows, lots truncated."""\n    import datetime as _dt\n    import pandas as _pd\n    row = _VIP1688_R13_ROWS.get(str(sid))\n    if not row:\n        return None, "no_insti_row"\n    tz = _dt.timezone(_dt.timedelta(hours=8))\n    now = now or _dt.datetime.now(tz)\n    q = (res.get("indicators") or {}).get("quote", [{}])[0]\n    df = _pd.DataFrame({"date": [_dt.datetime.fromtimestamp(t, tz).date() for t in res["timestamp"]],\n                        "high": q.get("high"), "low": q.get("low"), "close": q.get("close"), "volume": q.get("volume")}\n                       ).dropna(subset=["close"]).drop_duplicates("date", keep="last").reset_index(drop=True)\n    if len(df) < 62:\n        return None, f"rows={len(df)}"\n    live = df["date"].iloc[-1] == now.date() and (now.hour, now.minute) < (14, 30)\n    ind = df.iloc[:-1] if live else df\n    c, h, l = (_pd.to_numeric(ind[k], errors="coerce") for k in ("close", "high", "low"))\n    r2 = lambda x: f"{float(x):.2f}".rstrip("0").rstrip(".") if x == x else "N/A"\n    d = c.diff()\n    up, dn = d.clip(lower=0), -d.clip(upper=0)\n    rsi = 100 - 100 / (1 + up.ewm(com=13, adjust=False).mean() / dn.ewm(com=13, adjust=False).mean())\n    dif = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()\n    rsv = (c - l.rolling(14).min()) / (h.rolling(14).max() - l.rolling(14).min() + 1e-9) * 100\n    k = rsv.ewm(com=2, adjust=False).mean()\n    cl = _pd.to_numeric(df["close"], errors="coerce")\n    f = {"price": r2(cl.iloc[-1]), "change": r2(cl.iloc[-1] - cl.iloc[-2]),\n         "volume": f"{int(round(float(df[\'volume\'].iloc[-1] or 0) / 1000)):,}張",\n         "MA5": r2(c.rolling(5).mean().iloc[-1]), "MA20": r2(c.rolling(20).mean().iloc[-1]), "MA60": r2(c.rolling(60).mean().iloc[-1]),\n         "RSI": r2(rsi.iloc[-1]), "MACD": r2(dif.iloc[-1]), "KD_K": r2(k.iloc[-1]), "KD_D": r2(k.ewm(com=2, adjust=False).mean().iloc[-1]),\n         "foreign_buy": f"{int(row[3] / 1000):+,}張", "trust_buy": f"{int(row[4] / 1000):+,}張"}\n    fields = {key: {"value": v} for key, v in f.items()}\n    _vip1688_r13_ratios(sid, fields, shares)\n    return {"symbol": str(sid), "name": str(row[2]).strip(), "output_fields": fields, "source": "VIP1688_R13_FAST",\n            "indicator_upto": str(ind["date"].iloc[-1])}, "ok"\n\n\ndef _vip1688_r13_fetch(syms, old_fetch, insti_fut=None):\n    """VIP1688_R13: fast path for the 5 DNA stocks (listed or OTC); any stock it cannot fully build falls back to the\n    original fetch (with the ETF prewarm only in that case). Returns [(code, d) | (None, None)] like the original."""\n    import concurrent.futures as _cf\n    import time as _t\n    t0 = _t.time()\n    syms = [str(s).strip() for s in (syms or [])]\n    try:\n        if insti_fut is not None:\n            insti_fut.result(timeout=40)\n    except Exception as e:\n        print(f"[VIP1688_R13_INSTI_WAIT] {type(e).__name__}: {str(e)[:120]}", flush=True)\n    fast, why = {}, {}\n    with _cf.ThreadPoolExecutor(max_workers=6) as ex:\n        sf = ex.submit(_vip1688_r13_shares)\n        fs = {s: ex.submit(_vip1688_r13_yahoo, s) for s in syms}\n        try:\n            shares = sf.result(timeout=20)\n        except Exception:\n            shares = {}\n        for s in syms:\n            try:\n                d, why[s] = _vip1688_r13_build(s, fs[s].result(timeout=20), shares)\n                if d is not None:\n                    fast[s] = d\n            except Exception as e:\n                why[s] = f"{type(e).__name__}: {str(e)[:80]}"\n    t1 = _t.time()\n    back = [s for s in syms if s not in fast]\n    olds = {}\n    if back:\n        _vip1688_r8_prewarm_etf(back[:1])\n        with _cf.ThreadPoolExecutor(max_workers=8) as ex:\n            olds = dict(zip(back, ex.map(old_fetch, back)))\n    out = []\n    for s in syms:\n        if s in fast:\n            out.append((s, fast[s]))\n            continue\n        r = olds.get(s) or (None, None)\n        if r[0] and isinstance(r[1], dict) and isinstance(r[1].get("output_fields"), dict):\n            _vip1688_r13_ratios(s, r[1]["output_fields"], shares)\n        out.append(r)\n    print(f"[VIP1688_R13_FETCH] fast={len(fast)}/{len(syms)} fast_ms={int((t1 - t0) * 1000)} total_ms={int((_t.time() - t0) * 1000)} "\n          f"rows={len(_VIP1688_R13_ROWS)} shares={len(shares)} "\n          + " ".join(f"{s}={\'fast:\' + fast[s][\'indicator_upto\'] if s in fast else \'fallback:\' + str(why.get(s))}" for s in syms), flush=True)\n    return out\n\n\n'
ANCHOR = "def _vip1688_r7_stock_line("
FETCH_OLD = ("        _vip1688_r8_prewarm_etf(dna_symbols[:1])  # VIP1688_R8\n"
             "        with _TPE8888(max_workers=8) as _ex8b:  # ✅ P3優化：8888 DNA並行 5→8\n"
             "            _8888_results = list(_ex8b.map(_fetch_8888_stock, dna_symbols[:5]))\n")
FETCH_NEW = "        _8888_results = _vip1688_r13_fetch(dna_symbols[:5], _fetch_8888_stock, _r8c_insti_fut)  # VIP1688_R13\n"
ROWS_OLD = '    for label, key in (("外資", "foreign_buy"), ("投信", "trust_buy")):\n'
ROWS_NEW = ('    for label, key in (("外資", "foreign_buy"), ("投信", "trust_buy"), ("外本比(當日)", "foreign_ratio"),\n'
            '                       ("投本比(當日)", "trust_ratio")):  # VIP1688_R13\n')
EDITS = [("anchor", ANCHOR, HELPER + ANCHOR), ("fetch", FETCH_OLD, FETCH_NEW), ("rows", ROWS_OLD, ROWS_NEW)]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def need(cond, msg, **dbg):
    if not cond:
        raise RuntimeError(f"{msg} | debug={dbg}")


def find_src():
    hits = [d for d in sorted(glob.glob(os.path.join(HOME, "vip1688_r11_2026*", "source")))
            if os.path.isfile(os.path.join(d, "app.py")) and sha(open(os.path.join(d, "app.py"), "rb").read()) == SRC_SHA]
    need(hits, "R11 candidate with expected SHA not found", searched=glob.glob(os.path.join(HOME, "vip1688_r11_*")))
    return hits[-1]


def patch(t):
    need("_vip1688_r13_" not in t and "_vip1688_r12" not in t, "R12/R13 already applied")
    for name, old, new in EDITS:
        need(t.count(old) == 1, f"{name} count != 1", count=t.count(old))
        t = t.replace(old, new)
    return t


def behaviour(t, logs):
    import pandas as pd
    s = t.index("import threading as _vip1688_r8_threading")
    e = t.index(ANCHOR)
    fake = types.ModuleType("insti_query_r1")
    fake.select_rows = lambda rows: (["B"], ["S"])
    old_mod = sys.modules.get("insti_query_r1")
    sys.modules["insti_query_r1"] = fake
    try:
        ns = {"FlexSendMessage": lambda **k: k}
        exec(compile(t[s:e], "r13", "exec"), ns)
        fake.select_rows([("上市", "2340", "台亞", 5006880, -53000, 0), ("上櫃", "6515", "穎崴", 1000, 2000, 0)])
    finally:
        if old_mod is None:
            sys.modules.pop("insti_query_r1", None)
        else:
            sys.modules["insti_query_r1"] = old_mod
    r = {"capture": set(ns["_VIP1688_R13_ROWS"]) == {"2340", "6515"}}
    tz = datetime.timezone(datetime.timedelta(hours=8))
    base = datetime.datetime(2026, 5, 1, 9, 0, tzinfo=tz)
    n = 120
    closes = [50 + (i % 7) * 0.5 + i * 0.05 for i in range(n)]
    ts = [int((base + datetime.timedelta(days=i)).timestamp()) for i in range(n)]
    res = {"timestamp": ts, "indicators": {"quote": [{"high": [x + 1 for x in closes], "low": [x - 1 for x in closes],
                                                       "close": closes, "volume": [50833000] * n}]}}
    last_day = (base + datetime.timedelta(days=n - 1))
    shares = {"2340": 438623000.0}
    d_live, why = ns["_vip1688_r13_build"]("2340", res, shares, now=last_day.replace(hour=10))
    d_done, _ = ns["_vip1688_r13_build"]("2340", res, shares, now=last_day.replace(hour=15))
    c = pd.Series(closes)
    f = d_live["output_fields"]
    v = lambda dd, k: dd["output_fields"][k]["value"]
    fmt = lambda x: f"{float(x):.2f}".rstrip("0").rstrip(".")
    r["live_excludes_today"] = (v(d_live, "MA5") == fmt(c.iloc[:-1].rolling(5).mean().iloc[-1]) and d_live["indicator_upto"] != str(last_day.date())
                                and v(d_live, "price") == fmt(closes[-1]))
    r["closed_includes_today"] = v(d_done, "MA5") == fmt(c.rolling(5).mean().iloc[-1]) and d_done["indicator_upto"] == str(last_day.date())
    d = c.iloc[:-1].diff()
    up, dn = d.clip(lower=0), -d.clip(upper=0)
    rsi = 100 - 100 / (1 + up.ewm(com=13, adjust=False).mean() / dn.ewm(com=13, adjust=False).mean())
    r["rsi_wilder"] = v(d_live, "RSI") == fmt(rsi.iloc[-1])
    r["chips_truncated"] = v(d_live, "foreign_buy") == "+5,006張" and v(d_live, "trust_buy") == "-53張" and v(d_live, "volume") == "50,833張"
    r["ratios"] = v(d_live, "foreign_ratio") == f"{5006.88 / 438623 * 100:+.3f}%" and v(d_live, "trust_ratio") == f"{-53 / 438623 * 100:+.3f}%"
    r["name_from_official"] = d_live["name"] == "台亞"
    r["no_row_none"] = ns["_vip1688_r13_build"]("9999", res, shares)[0] is None
    short = {"timestamp": ts[:30], "indicators": {"quote": [{"high": closes[:30], "low": closes[:30], "close": closes[:30], "volume": [1] * 30}]}}
    r["short_history_none"] = ns["_vip1688_r13_build"]("2340", short, shares)[0] is None
    calls = []
    ns["_vip1688_r13_yahoo"] = lambda sid: res if sid == "2340" else (_ for _ in ()).throw(RuntimeError("yahoo no data"))
    ns["_vip1688_r13_shares"] = lambda: shares
    ns["_vip1688_r8_prewarm_etf"] = lambda syms: calls.append(("prewarm", list(syms)))
    oldd = {"name": "穎崴", "output_fields": {"price": {"value": "5615"}}}
    out = ns["_vip1688_r13_fetch"](["2340", "6515", "3533"], lambda sid: calls.append(("old", sid)) or ((sid, oldd) if sid == "6515" else (None, None)))
    r["fallback_only_failed"] = ([x for x in calls if x[0] == "old"] == [("old", "6515"), ("old", "3533")]
                                 and calls[0] == ("prewarm", ["6515"]) and out[0][0] == "2340" and out[1] == ("6515", oldd) and out[2] == (None, None))
    calls.clear()
    out2 = ns["_vip1688_r13_fetch"](["2340"], lambda sid: calls.append(("old", sid)))
    r["no_prewarm_when_all_fast"] = calls == [] and out2[0][1]["source"] == "VIP1688_R13_FAST"
    r["fetch_logged"] = any("[VIP1688_R13_FETCH] fast=1/3" in x and "6515=fallback:yahoo" not in x for x in logs)
    b = ns["_vip1688_r8_stock_bubble"]("2340", d_live, [])
    js = json.dumps(b, ensure_ascii=False)
    r["card_ratio_rows"] = "外本比(當日)" in js and "投本比(當日)" in js and v(d_live, "foreign_ratio") in js
    r["wiring"] = (t.count("_vip1688_r13_fetch(dna_symbols[:5], _fetch_8888_stock, _r8c_insti_fut)") == 1
                   and t.index("_r8c_insti_fut = _vip1688_r8c_insti_start()") < t.index("_8888_results = _vip1688_r13_fetch(")
                   < t.index("for idx, (py_s, d) in enumerate(_8888_results)"))
    return r


def main():
    out = {"status": "STOP", "revision": "VIP1688_R13", "deployed": False, "line_sent": False, "ai_called": False}
    dst = None
    try:
        src = find_src()
        app = os.path.join(src, "app.py")
        old = open(app, "rb").read().decode("utf-8")
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
        diff = [l for l in difflib.unified_diff(old.splitlines(), new.splitlines(), "r11", "r13", n=0, lineterm="")
                if l[:1] in "+-" and l[:3] not in ("+++", "---")]
        removed = [l[1:] for l in diff if l.startswith("-")]
        need(len(removed) == 4, "unexpected removed line count", removed=removed[:6])
        dst = os.path.join(HOME, "vip1688_r13_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        os.mkdir(dst)
        subprocess.run(["cp", "-al", src, os.path.join(dst, "source")], check=True)
        target = os.path.join(dst, "source", "app.py")
        tmp = target + ".r13tmp"
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
    print("R13_RESULT " + json.dumps(out, ensure_ascii=False))
    return 0 if out["status"] == "candidate_ready" else 2


if __name__ == "__main__":
    sys.exit(main())
