"""VIP1688 R8c: REPORT_8888 only, on top of R8b. (1) institutions from the production insti_query_r1.get_snapshot
(listed+OTC, all-three same-direction top 5, run in background, old source only as fallback); (2) overview adds DNA x5 and
large-cap leader/laggard rows; (3) 9 cards (large caps and institutions split) with capped notes for even card height.
No deploy, no LINE, no AI."""
import ast, datetime, difflib, glob, hashlib, json, os, subprocess, sys, traceback, types

HOME = os.path.expanduser("~")
SRC_SHA = "86a706604e1d9db35b9707da05f41af61e320398304ffa2cbab9c041b5ec6b56"
NEW_BUILD = 'def _vip1688_r8c_insti_start():\n    """VIP1688_R8C: start the production three-institution snapshot (listed+OTC) in the background."""\n    try:\n        import concurrent.futures as _cf\n        from insti_query_r1 import get_snapshot as _gs\n        ex = _cf.ThreadPoolExecutor(max_workers=1)\n        fut = ex.submit(_gs)\n        ex.shutdown(wait=False)\n        return fut\n    except Exception as e:\n        print(f"[VIP1688_R8C_INSTI_START_ERR] {type(e).__name__}: {str(e)[:160]}", flush=True)\n        return None\n\n\ndef _vip1688_r8c_insti_collect(fut, timeout=60):\n    """VIP1688_R8C: top-5 same-direction buy/sell from the snapshot; on failure fall back to the old source."""\n    import time as _t\n    t0 = _t.time()\n    try:\n        if fut is None:\n            raise RuntimeError("no snapshot future")\n        snap = fut.result(timeout=timeout)\n        q = {}\n        for key, quote in (getattr(snap, "quotes", ()) or ()):\n            try:\n                q[key] = float(quote.percent)\n            except Exception:\n                pass\n\n        def conv(rows):\n            out = []\n            for r in list(rows or ())[:5]:\n                market, code, name, f, t, dl = r\n                out.append({"code": code, "name": name, "market": market, "net": f + t + dl, "foreign": f,\n                            "trust": t, "dealer": dl, "pct": q.get((market, code)), "day": snap.day.isoformat()})\n            return out\n        b, s = conv(snap.buy), conv(snap.sell)\n        print(f"[VIP1688_R8C_INSTI] day={snap.day} buy={len(snap.buy)} sell={len(snap.sell)} "\n              f"wait_ms={int((_t.time() - t0) * 1000)}", flush=True)\n        return b, s\n    except Exception as e:\n        print(f"[VIP1688_R8C_INSTI_ERR] {type(e).__name__}: {str(e)[:160]} wait_ms={int((_t.time() - t0) * 1000)}", flush=True)\n        try:\n            fb = globals().get("get_institutional_top5")\n            return fb() if callable(fb) else ([], [])\n        except Exception:\n            return [], []\n\n\ndef _vip1688_r8_build(dna_symbols, results, tw_top10, inst_buy, inst_sell, giants, ai_text, date_note, period_note):\n    """VIP1688_R8C: 9 cards — overview, 5 DNA, large caps, institutions, US + strategy."""\n    import json as _j\n    import re as _re\n    ch = _vip1688_r8_chapters(ai_text)\n    ai1 = (ch.get(1) or "").splitlines()\n    syms = list(dna_symbols or [])[:5]\n    pairs = [(syms[i] if i < len(syms) else "", (r[1] if r and r[0] else None)) for i, r in enumerate(list(results or [])[:5])]\n    tw = [s for s in (tw_top10 or []) if isinstance(s, dict)]\n    tw_has = [s for s in tw if _vip1688_r8_num(s.get("pct")) not in (None, 0)]\n    up = sum(1 for s in tw_has if _vip1688_r8_num(s.get("pct")) > 0)\n    g = giants if isinstance(giants, dict) else {}\n    gup = sum(1 for v in g.values() if isinstance(v, dict) and (_vip1688_r8_num(v.get("change_pct")) or 0) > 0)\n    gdn = sum(1 for v in g.values() if isinstance(v, dict) and (_vip1688_r8_num(v.get("change_pct")) or 0) < 0)\n    m = _re.search(r"大盤多空判斷[：:]\\s*([^\\s，。]{1,4})", str(ai_text or ""))\n    mkt = m.group(1) if m else ""\n    mkt_c = _VIP1688_R8_UP if "多" in mkt else (_VIP1688_R8_DN if "空" in mkt else (_VIP1688_R8_NEU if mkt else _VIP1688_R8_NA))\n\n    def _items(items):\n        return [it for it in (items or [])[:5] if isinstance(it, dict) and (it.get("code") or it.get("stock_id"))]\n    buy, sell = _items(inst_buy), _items(inst_sell)\n    iday = (buy or sell or [{}])[0].get("day") or ""\n\n    def _pct_of(d):\n        p, c = _vip1688_r8_num(_vip1688_r8_field(d, "price")), _vip1688_r8_num(_vip1688_r8_field(d, "change"))\n        return c / (p - c) * 100 if (p is not None and c is not None and p - c > 0) else None\n\n    def _name(d):\n        return _re.split(r"[\\s|｜(（📈📉]", str(d.get("name") or "").strip())[0]\n    rows1 = [\n        _vip1688_r8_row("大盤判斷", mkt or "資料不足", mkt_c),\n        _vip1688_r8_row("權值股", f"{up}漲 / {len(tw_has) - up}跌" if tw_has else "資料不足",\n                        _vip1688_r8_color(up - (len(tw_has) - up)) if tw_has else _VIP1688_R8_NA),\n        _vip1688_r8_row("美股7巨頭", f"{gup}漲 / {gdn}跌" if (gup + gdn) else "資料不足",\n                        _vip1688_r8_color(gup - gdn) if (gup + gdn) else _VIP1688_R8_NA),\n        _vip1688_r8_row("法人同買第1", f"{buy[0].get(\'name\', \'\')}({buy[0].get(\'code\', \'\')})" if buy else "資料不足",\n                        _VIP1688_R8_UP if buy else _VIP1688_R8_NA),\n    ]\n    if tw_has:\n        hi = max(tw_has, key=lambda s: _vip1688_r8_num(s.get("pct")))\n        lo = min(tw_has, key=lambda s: _vip1688_r8_num(s.get("pct")))\n        rows1.append(_vip1688_r8_row(f"權值領漲 {hi.get(\'name\', \'\')}", f"{_vip1688_r8_num(hi.get(\'pct\')):+.2f}%",\n                                     _vip1688_r8_color(_vip1688_r8_num(hi.get("pct")))))\n        rows1.append(_vip1688_r8_row(f"權值領跌 {lo.get(\'name\', \'\')}", f"{_vip1688_r8_num(lo.get(\'pct\')):+.2f}%",\n                                     _vip1688_r8_color(_vip1688_r8_num(lo.get("pct")))))\n    rows1.append({"type": "separator", "margin": "md"})\n    for sid, d in pairs:\n        if isinstance(d, dict):\n            pc = _pct_of(d)\n            rows1.append(_vip1688_r8_row(f"DNA {sid} {_name(d)}", f"{pc:+.2f}%" if pc is not None else "資料不足",\n                                         _vip1688_r8_color(pc)))\n        else:\n            rows1.append(_vip1688_r8_row(f"DNA {sid}", "資料取得失敗", _VIP1688_R8_NA))\n    b = [_vip1688_r8_bubble("💎 發財1688精華報", f"資料日 {date_note} 收盤" + ("｜休市" if "休市" in str(period_note) else ""),\n                            rows1, "👉 左右滑動：DNA 個股 ×5｜權值｜法人｜美股與策略")]\n    b += [_vip1688_r8_stock_bubble(sid, d, ai1) for sid, d in pairs]\n    rows7 = [_vip1688_r8_row(f"{s.get(\'name\', \'\')}({s.get(\'code\', \'\')})", f"{_vip1688_r8_num(s.get(\'pct\')):+.2f}%",\n                             _vip1688_r8_color(_vip1688_r8_num(s.get("pct")))) for s in tw_has[:10]]\n    if not rows7:\n        rows7 = [_vip1688_r8_row("權值股漲跌", f"{date_note} 收盤資料未取得", _VIP1688_R8_NA)]\n    b.append(_vip1688_r8_bubble("📊 台灣10大權值股", f"資料日 {date_note} 收盤", rows7, ch.get(2) or "AI 判讀：資料不足"))\n\n    def _irows(items, label, color):\n        if not items:\n            return [_vip1688_r8_row(label, "資料不足", _VIP1688_R8_NA)]\n        rows = [_vip1688_r8_txt(label, "sm", color, True, margin="md")]\n        for it in items:\n            lots = int(round((_vip1688_r8_num(it.get("net")) or 0) / 1000))\n            pc = _vip1688_r8_num(it.get("pct"))\n            rows.append(_vip1688_r8_row(f"{it.get(\'name\', \'\')}({it.get(\'code\', it.get(\'stock_id\', \'\'))})",\n                                        f"{lots:+,}張" + (f"  {pc:+.2f}%" if pc is not None else ""), color))\n        return rows\n    rows_i = _irows(buy, "三大法人同步買超 TOP5", _VIP1688_R8_UP) + _irows(sell, "三大法人同步賣超 TOP5", _VIP1688_R8_DN)\n    b.append(_vip1688_r8_bubble("🏦 三大法人籌碼", f"法人資料日 {iday}（上市＋上櫃）" if iday else "法人資料：來源無資料",\n                                rows_i, ch.get(3) or "AI 判讀：資料不足"))\n    rows8 = []\n    for nm, v in list(g.items())[:7]:\n        if isinstance(v, dict):\n            cp = _vip1688_r8_num(v.get("change_pct"))\n            rows8.append(_vip1688_r8_row(str(nm), (f"${v.get(\'price\')}  " if v.get("price") not in (None, "") else "")\n                                         + (f"{cp:+.2f}%" if cp is not None else "資料不足"), _vip1688_r8_color(cp)))\n    us_note = "\\n\\n".join(x for x in (ch.get(4), ch.get(5)) if x)[:480]\n    b.append(_vip1688_r8_bubble("🇺🇸 美股與台指策略", "美股為其最近交易日收盤", rows8, us_note or "AI 判讀：資料不足",\n                                footer="⚠️ 投資有風險，本報告僅供參考，請獨立判斷"))\n    carousel = {"type": "carousel", "contents": b}\n    size = len(_j.dumps(carousel, ensure_ascii=False).encode("utf-8"))\n    if len(b) > 12 or size > 45000:\n        raise ValueError(f"carousel too large bubbles={len(b)} bytes={size}")\n    return carousel, size\n\n\n'
CAP_OLD, CAP_NEW = '"\\n".join(v)[:420] for k, v in out.items() if v}', '"\\n".join(v)[:300] for k, v in out.items() if v}'
BRANCH_MARK = "        # 速度優化：tw_top10 / giants / TWSE ALL 三者並行抓取（安全版）"
INST_OLD = "        inst_buy, inst_sell = get_institutional_top5()\n"
INST_NEW = "        inst_buy, inst_sell = [], []\n        _r8c_insti_fut = _vip1688_r8c_insti_start()  # VIP1688_R8C\n"
DATA_MARK = "        data_str = json.dumps({\n"
COLLECT = "        inst_buy, inst_sell = _vip1688_r8c_insti_collect(_r8c_insti_fut)  # VIP1688_R8C\n"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def need(cond, msg, **dbg):
    if not cond:
        raise RuntimeError(f"{msg} | debug={dbg}")


def find_src():
    hits = [d for d in sorted(glob.glob(os.path.join(HOME, "vip1688_r8b_*", "source")))
            if os.path.isfile(os.path.join(d, "app.py")) and sha(open(os.path.join(d, "app.py"), "rb").read()) == SRC_SHA]
    need(hits, "R8b candidate with expected SHA not found", searched=glob.glob(os.path.join(HOME, "vip1688_r8b_*")))
    return hits[-1]


def patch(t):
    need("_vip1688_r8c_" not in t, "R8c already applied")
    need(t.count(CAP_OLD) == 1 and t.count(BRANCH_MARK) == 1, "cap/branch marker count != 1",
         cap=t.count(CAP_OLD), mark=t.count(BRANCH_MARK))
    s, e = t.index("def _vip1688_r8_build("), t.index("def _vip1688_r8_stash(")
    need(t.count("def _vip1688_r8_build(") == 1 and 0 < e - s < 8000, "build region invalid", dist=e - s)
    t = t[:s] + NEW_BUILD + t[e:]
    t = t.replace(CAP_OLD, CAP_NEW)
    m = t.index(BRANCH_MARK)
    i = t.find(INST_OLD, m)
    need(0 < i - m < 3000, "inst call not found after branch marker", dist=i - m)
    t = t[:i] + INST_NEW + t[i + len(INST_OLD):]
    j = t.find(DATA_MARK, i)
    need(0 < j - i < 12000, "data_str not found after inst call", dist=j - i)
    return t[:j] + COLLECT + t[j:]


def behaviour(t):
    s = t.index("import threading as _vip1688_r8_threading")
    e = t.index("def _vip1688_r7_stock_line(")
    ns = {"FlexSendMessage": lambda **k: k, "get_institutional_top5": lambda: (["OLD_B"], ["OLD_S"])}
    exec(compile(t[s:e], "r8c", "exec"), ns)
    r = {}
    Q = types.SimpleNamespace
    snap = Q(day=datetime.date(2026, 10, 8), buy=(("上市", "2330", "台積電", 1200000, 300000, 50000),) * 6,
             sell=(("上櫃", "6488", "環球晶", -900000, -100000, -2000),), tw_count=1300, tp_count=900,
             quotes=((("上市", "2330"), Q(percent=1.5)),))

    class F:
        def __init__(self, v, err=None):
            self.v, self.err = v, err

        def result(self, timeout=None):
            if self.err:
                raise self.err
            return self.v
    b, sl = ns["_vip1688_r8c_insti_collect"](F(snap))
    r["insti_top5_only"] = len(b) == 5 and len(sl) == 1
    r["insti_fields"] = b[0]["net"] == 1550000 and b[0]["pct"] == 1.5 and b[0]["day"] == "2026-10-08" and sl[0]["pct"] is None
    r["insti_timeout_falls_back"] = ns["_vip1688_r8c_insti_collect"](F(None, TimeoutError("x"))) == (["OLD_B"], ["OLD_S"])
    r["insti_none_falls_back"] = ns["_vip1688_r8c_insti_collect"](None) == (["OLD_B"], ["OLD_S"])
    r["insti_start_safe_without_module"] = ns["_vip1688_r8c_insti_start"]() is None or hasattr(ns["_vip1688_r8c_insti_start"](), "result")
    mk = lambda n, p, c: {"name": n + " 📈 +1", "output_fields": {"price": {"value": p}, "change": {"value": c}, "volume": {"value": "1張"}}}
    res = [("x", mk("健策", "7165", "360")), ("x", mk("穎崴", "5615", "-95")), (None, None), ("x", mk("A", "100", "1")), ("x", mk("B", "50", "-1"))]
    tw = [{"code": "2330", "name": "台積電", "pct": -1.35}, {"code": "1301", "name": "台塑", "pct": 7.82}, {"code": "2412", "name": "中華電", "pct": 0.69}]
    ai = "═══【第二章：大盤解析】═══\n大盤多空判斷：偏空\n" + "長" * 900 + "\n═══【第三章：法人籌碼】═══\n同買集中電子\n═══【第四章：美股】═══\n" + "美" * 900
    c, size = ns["_vip1688_r8_build"](["3653", "6515", "3533", "1", "2"], res, tw, b, sl, {"NVDA": {"price": 229, "change_pct": -1.95}}, ai, "10/08", "休市")
    J = lambda x: json.dumps(x, ensure_ascii=False)
    r["nine_cards"] = len(c["contents"]) == 9 and size < 45000
    ov = J(c["contents"][0])
    r["overview_dna_rows"] = "DNA 3653 健策" in ov and "+5.29%" in ov and "DNA 3533" in ov and "資料取得失敗" in ov
    r["overview_leaders"] = "權值領漲 台塑" in ov and "+7.82%" in ov and "權值領跌 台積電" in ov and "-1.35%" in ov
    r["overview_insti_first"] = "台積電(2330)" in ov and "偏空" in ov
    ins = J(c["contents"][7])
    r["insti_card"] = "三大法人同步買超 TOP5" in ins and "+1,550張  +1.50%" in ins and "環球晶(6488)" in ins and "-1,002張" in ins and "法人資料日 2026-10-08" in ins
    r["insti_empty_honest"] = "資料不足" in J(ns["_vip1688_r8_build"]([], [], [], [], [], {}, "", "10/08", "")[0]["contents"][-2])
    r["notes_capped"] = all(len(x["body"]["contents"][-1].get("text", "")) <= 490 for x in c["contents"][6:])
    r["no_empty_text"] = '"text": ""' not in J(c)
    m = t.index(BRANCH_MARK)
    r["wiring_order"] = m < t.index(INST_NEW) < t.index(COLLECT) < t.find(DATA_MARK, t.index(COLLECT))
    r["old_inst_call_removed_in_branch"] = INST_OLD not in t[m:m + 3000]
    return r


def main():
    out = {"status": "STOP", "revision": "VIP1688_R8C", "deployed": False, "line_sent": False, "ai_called": False}
    dst = None
    try:
        src = find_src()
        app = os.path.join(src, "app.py")
        old = open(app, "rb").read().decode("utf-8")
        new = patch(old)
        compile(new, "app.py", "exec", dont_inherit=True)
        checks = behaviour(new)
        need(all(checks.values()), "behaviour check failed", checks=checks)
        diff = [l for l in difflib.unified_diff(old.splitlines(), new.splitlines(), "r8b", "r8c", n=0, lineterm="")
                if l[:1] in "+-" and l[:3] not in ("+++", "---")]
        removed = [l[1:] for l in diff if l.startswith("-")]
        dst = os.path.join(HOME, "vip1688_r8c_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        os.mkdir(dst)
        subprocess.run(["cp", "-al", src, os.path.join(dst, "source")], check=True)
        target = os.path.join(dst, "source", "app.py")
        tmp = target + ".r8ctmp"
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
    print("R8C_RESULT " + json.dumps(out, ensure_ascii=False))
    return 0 if out["status"] == "candidate_ready" else 2


if __name__ == "__main__":
    sys.exit(main())
