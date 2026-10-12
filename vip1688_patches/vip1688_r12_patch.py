"""VIP1688 R12 (debug / compare only): REPORT_8888 only, on top of R11. While the existing 5-stock fetch runs, a parallel
fast path pulls FinMind daily K + institutional rows and, after the old results are in, logs old card value vs each
candidate formula per field. The report itself is unchanged. No deploy, no LINE, no AI."""
import datetime, difflib, glob, hashlib, json, os, subprocess, sys, traceback, types

HOME = os.path.expanduser("~")
SRC_SHA = "c37e482599b42e430c2e8b9de7d174cd65b403199799d57619263143c7965a13"
HELPER = 'def _vip1688_r12_fast(syms):\n    """VIP1688_R12 (compare only): fetch FinMind daily K + institutional rows for the DNA stocks (listed or OTC)."""\n    import concurrent.futures as _cf\n    import datetime as _dt\n    import os as _os\n    import time as _t\n    t0 = _t.time()\n    keys = sorted(k for k in _os.environ if "FINMIND" in k.upper())\n    tok = next((_os.environ[k] for k in keys if _os.environ.get(k)), "")\n    print(f"[VIP1688_R12_ENV] finmind_env={keys} token={\'yes\' if tok else \'no\'}", flush=True)\n    today = _dt.date.today()\n\n    def q(ds, sid, days):\n        import requests as _rq\n        r = _rq.get("https://api.finmindtrade.com/api/v4/data", timeout=15,\n                    params={"dataset": ds, "data_id": sid, "start_date": (today - _dt.timedelta(days=days)).isoformat()},\n                    headers={"Authorization": f"Bearer {tok}"} if tok else {})\n        j = r.json()\n        if j.get("status") != 200:\n            raise RuntimeError(f"{ds} status={j.get(\'status\')} msg={str(j.get(\'msg\'))[:80]}")\n        return j.get("data") or []\n\n    def one(sid):\n        t1 = _t.time()\n        return {"px": q("TaiwanStockPrice", sid, 400), "ch": q("TaiwanStockInstitutionalInvestorsBuySell", sid, 20),\n                "ms": int((_t.time() - t1) * 1000)}\n    out = {}\n    with _cf.ThreadPoolExecutor(max_workers=5) as ex:\n        fs = {str(s): ex.submit(one, str(s)) for s in syms}\n        for s, f in fs.items():\n            try:\n                out[s] = f.result(timeout=40)\n            except Exception as e:\n                out[s] = {"err": f"{type(e).__name__}: {str(e)[:120]}"}\n    print(f"[VIP1688_R12_FAST] ms={int((_t.time() - t0) * 1000)} "\n          + " ".join(f"{s}={v.get(\'ms\', \'ERR\')}" for s, v in out.items()), flush=True)\n    return out\n\n\ndef _vip1688_r12_calc(px, ch):\n    """VIP1688_R12: candidate formulas (the core has several variants; the compare run shows which one the card uses)."""\n    import pandas as _pd\n    df = _pd.DataFrame(px).sort_values("date").reset_index(drop=True)\n    num = lambda k: _pd.to_numeric(df[k], errors="coerce")\n    c, h, l = num("close"), num("max"), num("min")\n    last = lambda s: None if _pd.isna(s.iloc[-1]) else round(float(s.iloc[-1]), 2)\n    o = {"date": str(df["date"].iloc[-1]), "rows": len(df), "price": last(c), "change": last(num("spread")),\n         "volume": round(float(num("Trading_Volume").iloc[-1]) / 1000, 2)}\n    for n in (5, 20, 60):\n        o[f"MA{n}"] = last(c.rolling(n).mean())\n    d = c.diff()\n    up, dn = d.clip(lower=0), -d.clip(upper=0)\n    o["RSI_wilder"] = last(100 - 100 / (1 + up.ewm(com=13, adjust=False).mean() / dn.ewm(com=13, adjust=False).mean()))\n    o["RSI_sma"] = last(100 - 100 / (1 + up.rolling(14).mean() / dn.rolling(14).mean()))\n    dif = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()\n    sig = dif.ewm(span=9, adjust=False).mean()\n    o["MACD_dif"], o["MACD_hist"], o["MACD_sig"] = last(dif), last(dif - sig), last(sig)\n    for n in (9, 14):\n        rsv = (c - l.rolling(n).min()) / (h.rolling(n).max() - l.rolling(n).min() + 1e-9) * 100\n        k = rsv.ewm(com=2, adjust=False).mean()\n        o[f"K{n}"], o[f"D{n}"] = last(k), last(k.ewm(com=2, adjust=False).mean())\n    cd = _pd.DataFrame(ch)\n    if len(cd):\n        cd = cd[cd["date"] == cd["date"].max()]\n        net = {str(r["name"]): (float(r["buy"]) - float(r["sell"])) / 1000 for _, r in cd.iterrows()}\n        o["chip_date"] = str(cd["date"].iloc[0])\n        o["foreign"] = round(net.get("Foreign_Investor", 0.0), 2)\n        o["foreign_all"] = round(net.get("Foreign_Investor", 0.0) + net.get("Foreign_Dealer_Self", 0.0), 2)\n        o["trust"] = round(net.get("Investment_Trust", 0.0), 2)\n    return o\n\n\n_VIP1688_R12_MAP = {"price": ("price",), "change": ("change",), "volume": ("volume",), "MA5": ("MA5",), "MA20": ("MA20",),\n                    "MA60": ("MA60",), "RSI": ("RSI_wilder", "RSI_sma"), "MACD": ("MACD_dif", "MACD_hist", "MACD_sig"),\n                    "KD_K": ("K9", "K14"), "KD_D": ("D9", "D14"), "foreign_buy": ("foreign", "foreign_all"),\n                    "trust_buy": ("trust",)}\n\n\ndef _vip1688_r12_compare(fut, syms, results):\n    """VIP1688_R12: log old (card) value vs every candidate per field; \'*\' marks a match. Report output is unchanged."""\n    try:\n        fast = fut.result(timeout=60) if fut is not None else {}\n        ok = tot = 0\n        for s, r in zip(syms, results):\n            s = str(s)\n            d = r[1] if (isinstance(r, (list, tuple)) and len(r) > 1 and r[0]) else None\n            f = fast.get(s) or {}\n            if not isinstance(d, dict) or "px" not in f:\n                print(f"[VIP1688_R12_CMP] sid={s} skip old={\'ok\' if isinstance(d, dict) else \'none\'} new={f.get(\'err\', \'none\')}", flush=True)\n                continue\n            n = _vip1688_r12_calc(f["px"], f["ch"])\n            print(f"[VIP1688_R12_CMP] sid={s} date={n[\'date\']} rows={n[\'rows\']} chip_date={n.get(\'chip_date\')}", flush=True)\n            for fld, cands in _VIP1688_R12_MAP.items():\n                ov = _vip1688_r8_num(_vip1688_r8_field(d, fld))\n                parts, hit = [], False\n                for cn in cands:\n                    nv = n.get(cn)\n                    m = ov is not None and nv is not None and abs(nv - ov) <= max(0.011, abs(ov) * 0.0005)\n                    hit = hit or m\n                    parts.append(f"{cn}={nv}{\'*\' if m else \'\'}")\n                tot += 1\n                ok += hit\n                print(f"[VIP1688_R12_CMP] sid={s} f={fld} old={ov} " + " ".join(parts), flush=True)\n        print(f"[VIP1688_R12_SUMMARY] matched={ok}/{tot}", flush=True)\n    except Exception as e:\n        print(f"[VIP1688_R12_ERR] {type(e).__name__}: {str(e)[:200]}", flush=True)\n\n\n'
ANCHOR = "def _vip1688_r7_stock_line("
PRE_OLD = "        _vip1688_r8_prewarm_etf(dna_symbols[:1])  # VIP1688_R8\n"
PRE_NEW = "        _r12_fut = _vip1688_r9_start(_vip1688_r12_fast, list(dna_symbols[:5]))  # VIP1688_R12\n" + PRE_OLD
RES_OLD = ("            _8888_results = list(_ex8b.map(_fetch_8888_stock, dna_symbols[:5]))\n"
           "        for idx, (py_s, d) in enumerate(_8888_results):\n")
RES_NEW = ("            _8888_results = list(_ex8b.map(_fetch_8888_stock, dna_symbols[:5]))\n"
           "        _vip1688_r9_start(_vip1688_r12_compare, _r12_fut, list(dna_symbols[:5]), list(_8888_results))  # VIP1688_R12\n"
           "        for idx, (py_s, d) in enumerate(_8888_results):\n")
EDITS = [("anchor", ANCHOR, HELPER + ANCHOR), ("start", PRE_OLD, PRE_NEW), ("compare", RES_OLD, RES_NEW)]


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
    need("_vip1688_r12_" not in t, "R12 already applied")
    for name, old, new in EDITS:
        need(t.count(old) == 1, f"{name} count != 1", count=t.count(old))
        t = t.replace(old, new)
    return t


def behaviour(t, logs):
    s = t.index("import threading as _vip1688_r8_threading")
    e = t.index(ANCHOR)
    ns = {"FlexSendMessage": lambda **k: k}
    exec(compile(t[s:e], "r12", "exec"), ns)
    r = {}
    import pandas as pd
    closes = [100 + (i % 7) * 1.5 + i * 0.3 for i in range(120)]
    px = [{"date": f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}", "close": cl, "max": cl + 1, "min": cl - 1, "spread": 0.3,
           "Trading_Volume": 1629000} for i, cl in enumerate(closes)]
    ch = [{"date": "2026-10-08", "name": "Foreign_Investor", "buy": 500000, "sell": 253000},
          {"date": "2026-10-08", "name": "Foreign_Dealer_Self", "buy": 1000, "sell": 0},
          {"date": "2026-10-08", "name": "Investment_Trust", "buy": 0, "sell": 53000},
          {"date": "2026-10-07", "name": "Investment_Trust", "buy": 999000, "sell": 0}]
    n = ns["_vip1688_r12_calc"](px, ch)
    c = pd.Series(closes)
    r["ma_ok"] = n["MA5"] == round(float(c.rolling(5).mean().iloc[-1]), 2) and n["MA60"] == round(float(c.rolling(60).mean().iloc[-1]), 2)
    r["volume_lots"] = n["volume"] == 1629.0 and n["price"] == round(closes[-1], 2)
    r["chips_latest_day"] = n["foreign"] == 247.0 and n["foreign_all"] == 248.0 and n["trust"] == -53.0 and n["chip_date"] == "2026-10-08"
    r["variants_present"] = all(k in n for k in ("RSI_wilder", "RSI_sma", "MACD_dif", "MACD_hist", "K9", "K14", "D9", "D14"))
    old = {"name": "健策", "output_fields": {k: {"value": str(v)} for k, v in (
        ("price", n["price"]), ("change", n["change"]), ("volume", "1,629張"), ("MA5", n["MA5"]), ("MA20", n["MA20"]),
        ("MA60", n["MA60"]), ("RSI", n["RSI_sma"]), ("MACD", n["MACD_dif"]), ("KD_K", n["K14"]), ("KD_D", n["D14"]),
        ("foreign_buy", "+247張"), ("trust_buy", "-53張"))}}
    fut = types.SimpleNamespace(result=lambda timeout=None: {"3653": {"px": px, "ch": ch, "ms": 5}, "6515": {"err": "X"}})
    ns["_vip1688_r12_compare"](fut, ["3653", "6515", "3533"], [("3653", old), ("6515", old), (None, None)])
    out = "\n".join(logs)
    r["compare_marks"] = ("f=RSI old=" in out and "RSI_sma=" in out and "f=KD_K" in out and "K14=" in out
                          and "[VIP1688_R12_SUMMARY] matched=12/12" in out)
    r["compare_skips_bad"] = "sid=6515 skip old=ok new=X" in out
    ns["_vip1688_r12_compare"](types.SimpleNamespace(result=lambda timeout=None: 1 / 0), ["1"], [])
    r["compare_never_raises"] = "[VIP1688_R12_ERR] ZeroDivisionError" in "\n".join(logs)
    i, j = t.index("_r12_fut = _vip1688_r9_start(_vip1688_r12_fast"), t.index("_vip1688_r9_start(_vip1688_r12_compare")
    r["wiring"] = i < t.index("_8888_results = list(_ex8b.map") < j < t.index("for idx, (py_s, d) in enumerate(_8888_results)")
    return r


def main():
    out = {"status": "STOP", "revision": "VIP1688_R12", "deployed": False, "line_sent": False, "ai_called": False}
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
        diff = [l for l in difflib.unified_diff(old.splitlines(), new.splitlines(), "r11", "r12", n=0, lineterm="")
                if l[:1] in "+-" and l[:3] not in ("+++", "---")]
        removed = [l[1:] for l in diff if l.startswith("-")]
        need(len(removed) == 0, "unexpected removed lines", removed=removed[:4])
        dst = os.path.join(HOME, "vip1688_r12_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        os.mkdir(dst)
        subprocess.run(["cp", "-al", src, os.path.join(dst, "source")], check=True)
        target = os.path.join(dst, "source", "app.py")
        tmp = target + ".r12tmp"
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
    print("R12_RESULT " + json.dumps(out, ensure_ascii=False))
    return 0 if out["status"] == "candidate_ready" else 2


if __name__ == "__main__":
    sys.exit(main())
