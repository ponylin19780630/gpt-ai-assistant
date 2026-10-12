"""VIP1688 R12d (debug / compare only; R12c + previous-bar variants + truncated lots): REPORT_8888 only, on top of R11. FinMind hit its quota (402) in R12, so the
candidate fast path is: Yahoo daily K (.TW/.TWO) for price indicators, the official cross-checked 三大法人 rows that
insti_query_r1 already fetches (captured, result unchanged) for chips, and official company basic data for issued shares
(外本比/投本比). Logs old card value vs candidates per field. Report output unchanged. No deploy, no LINE, no AI."""
import datetime, difflib, glob, hashlib, json, os, subprocess, sys, traceback, types

HOME = os.path.expanduser("~")
SRC_SHA = "c37e482599b42e430c2e8b9de7d174cd65b403199799d57619263143c7965a13"
HELPER = '_VIP1688_R12C_ROWS = {}\n\n\ndef _vip1688_r12c_capture_install():\n    """VIP1688_R12C: keep a copy of the official, already cross-checked per-stock 三大法人 rows (listed + OTC) that\n    insti_query_r1 passes to select_rows; its result is returned unchanged."""\n    try:\n        import insti_query_r1 as _q\n        if getattr(_q.select_rows, "_vip1688_cap", False):\n            return\n        orig = _q.select_rows\n\n        def cap(rows):\n            out = orig(rows)\n            try:\n                _VIP1688_R12C_ROWS.clear()\n                _VIP1688_R12C_ROWS.update({str(r[1]).strip(): r for r in rows})\n            except Exception:\n                pass\n            return out\n        cap._vip1688_cap = True\n        _q.select_rows = cap\n    except Exception as e:\n        print(f"[VIP1688_R12C_CAP_ERR] {type(e).__name__}: {str(e)[:160]}", flush=True)\n\n\n_vip1688_r12c_capture_install()\n\n\ndef _vip1688_r12c_shares():\n    """VIP1688_R12C: issued shares per code from official company basic data (listed TWSE + OTC TPEx); logs field names."""\n    import re as _re\n    out = {}\n    for url in ("https://openapi.twse.com.tw/v1/opendata/t187ap03_L", "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"):\n        try:\n            rows = _vip1688_r9_json(url, 15)\n        except Exception as e:\n            print(f"[VIP1688_R12C_SHARES] {url.rsplit(\'/\', 1)[-1]} ERR {type(e).__name__}: {str(e)[:100]}", flush=True)\n            continue\n        rows = rows if isinstance(rows, list) else []\n        keys = [str(k).strip() for k in (rows[0].keys() if rows and isinstance(rows[0], dict) else [])]\n        ck = next((k for k in keys if _re.search(r"公司代號|CompanyCode", k)), None)\n        sk = next((k for k in keys if _re.search(r"已發行普通股數|IssuedShares|IssueShares", k)), None)\n        n = 0\n        for r in rows:\n            k = {str(a).strip(): v for a, v in r.items()} if isinstance(r, dict) else {}\n            try:\n                if ck and sk:\n                    v = float(str(k.get(sk, "")).replace(",", ""))\n                    if v > 0:\n                        out[str(k.get(ck, "")).strip()] = v\n                        n += 1\n            except ValueError:\n                pass\n        print(f"[VIP1688_R12C_SHARES] {url.rsplit(\'/\', 1)[-1]} rows={len(rows)} used={n} code_key={ck} shares_key={sk}"\n              + ("" if sk else f" keys={keys[:20]}"), flush=True)\n    return out\n\n\ndef _vip1688_r12c_fast(syms):\n    """VIP1688_R12C (compare only): Yahoo daily K (.TW, then .TWO) per DNA stock + official issued shares."""\n    import concurrent.futures as _cf\n    import time as _t\n    t0 = _t.time()\n\n    def one(sid):\n        import requests as _rq\n        t1, last = _t.time(), None\n        for suf in (".TW", ".TWO"):\n            r = _rq.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sid}{suf}", params={"range": "2y", "interval": "1d"},\n                        headers={"User-Agent": "Mozilla/5.0"}, timeout=10)\n            last = r.status_code\n            try:\n                res = ((r.json().get("chart") or {}).get("result") or [None])[0]\n            except Exception:\n                res = None\n            if res and res.get("timestamp"):\n                return {"suf": suf, "res": res, "ms": int((_t.time() - t1) * 1000)}\n        raise RuntimeError(f"yahoo no data last_status={last}")\n    out = {}\n    with _cf.ThreadPoolExecutor(max_workers=6) as ex:\n        sf = ex.submit(_vip1688_r12c_shares)\n        fs = {str(s): ex.submit(one, str(s)) for s in syms}\n        for s, f in fs.items():\n            try:\n                out[s] = f.result(timeout=30)\n            except Exception as e:\n                out[s] = {"err": f"{type(e).__name__}: {str(e)[:120]}"}\n        try:\n            shares = sf.result(timeout=30)\n        except Exception:\n            shares = {}\n    out["__shares__"] = shares\n    print(f"[VIP1688_R12C_FAST] ms={int((_t.time() - t0) * 1000)} "\n          + " ".join(f"{s}={v.get(\'suf\', \'\')}{v.get(\'ms\', \'ERR\')}" for s, v in out.items() if s != "__shares__"), flush=True)\n    return out\n\n\ndef _vip1688_r12c_calc(res):\n    """VIP1688_R12D: candidate formulas on Yahoo daily OHLCV (Taipei dates); suffix _p = same formula without the\n    latest bar (tests whether the card\'s indicators use history up to the previous trading day)."""\n    import datetime as _dt\n    import pandas as _pd\n    q = (res.get("indicators") or {}).get("quote", [{}])[0]\n    tz = _dt.timezone(_dt.timedelta(hours=8))\n    df = _pd.DataFrame({"date": [_dt.datetime.fromtimestamp(t, tz).date().isoformat() for t in res["timestamp"]],\n                        "open": q.get("open"), "high": q.get("high"), "low": q.get("low"), "close": q.get("close"),\n                        "volume": q.get("volume")}).dropna(subset=["close"]).drop_duplicates("date", keep="last").reset_index(drop=True)\n    last = lambda s: None if _pd.isna(s.iloc[-1]) else round(float(s.iloc[-1]), 2)\n    o = {"date": df["date"].iloc[-1], "prev_date": df["date"].iloc[-2] if len(df) > 1 else "", "rows": len(df)}\n\n    def ind(dd, sfx):\n        c, h, l = (_pd.to_numeric(dd[k], errors="coerce") for k in ("close", "high", "low"))\n        o["price" + sfx], o["change" + sfx] = last(c), last(c.diff())\n        o["volume" + sfx] = round(float(dd["volume"].iloc[-1] or 0) / 1000, 2)\n        for n in (5, 20, 60):\n            o[f"MA{n}{sfx}"] = last(c.rolling(n).mean())\n        d = c.diff()\n        up, dn = d.clip(lower=0), -d.clip(upper=0)\n        o["RSIw" + sfx] = last(100 - 100 / (1 + up.ewm(com=13, adjust=False).mean() / dn.ewm(com=13, adjust=False).mean()))\n        o["RSIs" + sfx] = last(100 - 100 / (1 + up.rolling(14).mean() / dn.rolling(14).mean()))\n        dif = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()\n        sig = dif.ewm(span=9, adjust=False).mean()\n        o["DIF" + sfx], o["OSC" + sfx], o["SIG" + sfx] = last(dif), last(dif - sig), last(sig)\n        for n in (9, 14):\n            rsv = (c - l.rolling(n).min()) / (h.rolling(n).max() - l.rolling(n).min() + 1e-9) * 100\n            k = rsv.ewm(com=2, adjust=False).mean()\n            o[f"K{n}{sfx}"], o[f"D{n}{sfx}"] = last(k), last(k.ewm(com=2, adjust=False).mean())\n    ind(df, "")\n    if len(df) > 61:\n        ind(df.iloc[:-1], "_p")\n    return o\n\n\n_VIP1688_R12C_BASE = {"price": ("price",), "change": ("change",), "volume": ("volume",), "MA5": ("MA5",), "MA20": ("MA20",),\n                      "MA60": ("MA60",), "RSI": ("RSIw", "RSIs"), "MACD": ("DIF", "OSC", "SIG"), "KD_K": ("K9", "K14"),\n                      "KD_D": ("D9", "D14")}\n_VIP1688_R12C_MAP = dict({k: v + tuple(x + "_p" for x in v) for k, v in _VIP1688_R12C_BASE.items()},\n                         foreign_buy=("foreign", "foreign_int"), trust_buy=("trust", "trust_int"))\n\n\ndef _vip1688_r12c_compare(fut, syms, results):\n    """VIP1688_R12C: log old card value vs each candidate per field (\'*\' = match); report output unchanged."""\n    try:\n        fast = fut.result(timeout=60) if fut is not None else {}\n        shares = fast.get("__shares__") or {}\n        print(f"[VIP1688_R12C_ROWS] official_insti_rows={len(_VIP1688_R12C_ROWS)} shares={len(shares)}", flush=True)\n        ok = tot = 0\n        for s, r in zip(syms, results):\n            s = str(s)\n            d = r[1] if (isinstance(r, (list, tuple)) and len(r) > 1 and r[0]) else None\n            f = fast.get(s) or {}\n            if not isinstance(d, dict) or "res" not in f:\n                print(f"[VIP1688_R12C_CMP] sid={s} skip old={\'ok\' if isinstance(d, dict) else \'none\'} new={f.get(\'err\', \'none\')}", flush=True)\n                continue\n            n = _vip1688_r12c_calc(f["res"])\n            row = _VIP1688_R12C_ROWS.get(s)\n            if row:\n                n["foreign"], n["trust"] = round(row[3] / 1000, 2), round(row[4] / 1000, 2)\n                n["foreign_int"], n["trust_int"] = float(int(row[3] / 1000)), float(int(row[4] / 1000))\n            lots = (shares.get(s) or 0) / 1000\n            print(f"[VIP1688_R12C_CMP] sid={s} src=yahoo{f[\'suf\']} date={n[\'date\']} prev={n[\'prev_date\']} rows={n[\'rows\']} "\n                  f"insti_row={\'yes\' if row else \'no\'}", flush=True)\n            if row and lots > 0:\n                print(f"[VIP1688_R12C_RATIO] sid={s} issued_lots={round(lots)} 外本比={n[\'foreign\'] / lots * 100:+.3f}% "\n                      f"投本比={n[\'trust\'] / lots * 100:+.3f}%", flush=True)\n            else:\n                print(f"[VIP1688_R12C_RATIO] sid={s} missing insti_row={\'yes\' if row else \'no\'} issued_lots={round(lots)}", flush=True)\n            for fld, cands in _VIP1688_R12C_MAP.items():\n                ov = _vip1688_r8_num(_vip1688_r8_field(d, fld))\n                parts, hit = [], False\n                for cn in cands:\n                    nv = n.get(cn)\n                    m = ov is not None and nv is not None and abs(nv - ov) <= max(0.011, abs(ov) * 0.0005)\n                    hit = hit or m\n                    parts.append(f"{cn}={nv}{\'*\' if m else \'\'}")\n                tot += 1\n                ok += hit\n                print(f"[VIP1688_R12C_CMP] sid={s} f={fld} old={ov} " + " ".join(parts), flush=True)\n        print(f"[VIP1688_R12C_SUMMARY] matched={ok}/{tot}", flush=True)\n    except Exception as e:\n        print(f"[VIP1688_R12C_ERR] {type(e).__name__}: {str(e)[:200]}", flush=True)\n\n\n'
ANCHOR = "def _vip1688_r7_stock_line("
PRE_OLD = "        _vip1688_r8_prewarm_etf(dna_symbols[:1])  # VIP1688_R8\n"
PRE_NEW = "        _r12_fut = _vip1688_r9_start(_vip1688_r12c_fast, list(dna_symbols[:5]))  # VIP1688_R12C\n" + PRE_OLD
RES_OLD = ("            _8888_results = list(_ex8b.map(_fetch_8888_stock, dna_symbols[:5]))\n"
           "        for idx, (py_s, d) in enumerate(_8888_results):\n")
RES_NEW = ("            _8888_results = list(_ex8b.map(_fetch_8888_stock, dna_symbols[:5]))\n"
           "        _vip1688_r9_start(_vip1688_r12c_compare, _r12_fut, list(dna_symbols[:5]), list(_8888_results))  # VIP1688_R12C\n"
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
    need("_vip1688_r12c_" not in t and "_vip1688_r12_" not in t, "R12/R12c already applied")
    for name, old, new in EDITS:
        need(t.count(old) == 1, f"{name} count != 1", count=t.count(old))
        t = t.replace(old, new)
    return t


def behaviour(t, logs):
    s = t.index("import threading as _vip1688_r8_threading")
    e = t.index(ANCHOR)
    fake = types.ModuleType("insti_query_r1")
    fake.select_rows = lambda rows: (["B"], ["S"])
    old_mod = sys.modules.get("insti_query_r1")
    sys.modules["insti_query_r1"] = fake
    try:
        ns = {"FlexSendMessage": lambda **k: k}
        exec(compile(t[s:e], "r12c", "exec"), ns)
        r = {}
        out = fake.select_rows([("上市", "3653", "健策", 247000, -53000, 1000), ("上櫃", "6515", "穎崴", 1000, 2000, 0)])
        r["capture_keeps_result"] = out == (["B"], ["S"]) and set(ns["_VIP1688_R12C_ROWS"]) == {"3653", "6515"}
        ns["_vip1688_r12c_capture_install"]()
        r["capture_once"] = getattr(fake.select_rows, "_vip1688_cap", False)
    finally:
        if old_mod is None:
            sys.modules.pop("insti_query_r1", None)
        else:
            sys.modules["insti_query_r1"] = old_mod
    import pandas as pd
    closes = [100 + (i % 7) * 1.5 + i * 0.3 for i in range(120)]
    ts = [1700000000 + i * 86400 for i in range(120)]
    res = {"timestamp": ts, "indicators": {"quote": [{"open": closes, "high": [x + 1 for x in closes], "low": [x - 1 for x in closes],
                                                       "close": closes[:-1] + [None], "volume": [1629000] * 120}]}}
    n = ns["_vip1688_r12c_calc"](res)
    c = pd.Series(closes[:-1])
    r["calc_drops_null_last"] = n["rows"] == 119 and n["price"] == round(closes[-2], 2) and n["MA5"] == round(float(c.rolling(5).mean().iloc[-1]), 2)
    r["prev_variant"] = n["price_p"] == round(closes[-3], 2) and n["MA5_p"] == round(float(c.iloc[:-1].rolling(5).mean().iloc[-1]), 2)
    r["volume_lots"] = n["volume"] == 1629.0
    old = {"name": "健策", "output_fields": {k: {"value": str(v)} for k, v in (
        ("price", n["price"]), ("change", n["change"]), ("volume", "1,629張"), ("MA5", n["MA5"]), ("MA20", n["MA20"]),
        ("MA60", n["MA60_p"]), ("RSI", n["RSIw"]), ("MACD", n["OSC_p"]), ("KD_K", n["K9"]), ("KD_D", n["D14_p"]),
        ("foreign_buy", "+247張"), ("trust_buy", "-53張"))}}
    fut = types.SimpleNamespace(result=lambda timeout=None: {"3653": {"suf": ".TW", "res": res, "ms": 5}, "6515": {"err": "X"},
                                                             "__shares__": {"3653": 2000000.0}})
    ns["_vip1688_r12c_compare"](fut, ["3653", "6515"], [("3653", old), ("6515", old)])
    txt = "\n".join(logs)
    r["compare_all_match"] = "[VIP1688_R12C_SUMMARY] matched=12/12" in txt and "official_insti_rows=2 shares=1" in txt
    r["ratio_logged"] = "issued_lots=2000 外本比=+12.350% 投本比=-2.650%" in txt and "foreign_int=247.0*" in txt
    r["skip_logged"] = "sid=6515 skip old=ok new=X" in txt
    ns["_vip1688_r12c_compare"](types.SimpleNamespace(result=lambda timeout=None: 1 / 0), ["1"], [])
    r["never_raises"] = "[VIP1688_R12C_ERR] ZeroDivisionError" in "\n".join(logs)
    ns["_vip1688_r9_json"] = lambda url, timeout=15: ([{"公司代號": "3653", "已發行普通股數或TDR原股發行股數": "35,000,000"}]
                                                       if url.endswith("_L") else [{"SecuritiesCompanyCode": "6515", "Other": 1}])
    sh = ns["_vip1688_r12c_shares"]()
    r["shares_parse_and_log_keys"] = sh == {"3653": 35000000.0} and "keys=['SecuritiesCompanyCode', 'Other']" in "\n".join(logs)
    i, j = t.index("_r12_fut = _vip1688_r9_start(_vip1688_r12c_fast"), t.index("_vip1688_r9_start(_vip1688_r12c_compare")
    r["wiring"] = i < t.index("_8888_results = list(_ex8b.map") < j < t.index("for idx, (py_s, d) in enumerate(_8888_results)")
    return r


def main():
    out = {"status": "STOP", "revision": "VIP1688_R12D", "deployed": False, "line_sent": False, "ai_called": False}
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
        need(all(checks.values()), "behaviour check failed", checks=checks, logs=logs[-8:])
        diff = [l for l in difflib.unified_diff(old.splitlines(), new.splitlines(), "r11", "r12c", n=0, lineterm="")
                if l[:1] in "+-" and l[:3] not in ("+++", "---")]
        removed = [l[1:] for l in diff if l.startswith("-")]
        need(len(removed) == 0, "unexpected removed lines", removed=removed[:4])
        dst = os.path.join(HOME, "vip1688_r12d_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        os.mkdir(dst)
        subprocess.run(["cp", "-al", src, os.path.join(dst, "source")], check=True)
        target = os.path.join(dst, "source", "app.py")
        tmp = target + ".r12ctmp"
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
    print("R12D_RESULT " + json.dumps(out, ensure_ascii=False))
    return 0 if out["status"] == "candidate_ready" else 2


if __name__ == "__main__":
    sys.exit(main())
