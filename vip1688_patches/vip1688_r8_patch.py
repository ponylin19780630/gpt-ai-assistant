"""VIP1688 R8: REPORT_8888 only. 8-card carousel (overview, 5 DNA stocks with full technical fields, market+institutions,
US+strategy), colors red=up green=down yellow=neutral gray=missing; ETF master prewarmed once before the 5 parallel
fetches (root cause of the ~120s cold stall); AI chapter 1 one line per stock. Base = R7. No deploy, no LINE, no AI."""
import ast, datetime, difflib, hashlib, json, os, subprocess, sys, traceback

HOME = os.path.expanduser("~")
SRC = os.path.join(HOME, "vip1688_r7_20261011_150340", "source")
SRC_SHA = "fbe3e25415c8acde39d69ec6e7158370bf57ba870564ee0bc93132c90d9aaca5"
HELPER = 'import threading as _vip1688_r8_threading\n_VIP1688_R8_TLS = _vip1688_r8_threading.local()\n_VIP1688_R8_UP, _VIP1688_R8_DN, _VIP1688_R8_NEU, _VIP1688_R8_NA = "#E74C3C", "#27AE60", "#C9A227", "#9E9E9E"\n\n\ndef _vip1688_r8_num(v):\n    try:\n        x = float(str(v).replace(",", "").replace("+", "").replace("%", "").replace("張", "").strip())\n        return x if x == x else None\n    except Exception:\n        return None\n\n\ndef _vip1688_r8_color(x):\n    if x is None:\n        return _VIP1688_R8_NA\n    return _VIP1688_R8_UP if x > 0 else (_VIP1688_R8_DN if x < 0 else _VIP1688_R8_NEU)\n\n\ndef _vip1688_r8_fmt(x):\n    return f"{x:,.2f}".rstrip("0").rstrip(".")\n\n\ndef _vip1688_r8_txt(s, size="sm", color="#333333", bold=False, wrap=True, **kw):\n    s = str(s if s not in (None, "") else "—")\n    d = {"type": "text", "text": s[:1200], "size": size, "color": color, "wrap": wrap}\n    if bold:\n        d["weight"] = "bold"\n    d.update(kw)\n    return d\n\n\ndef _vip1688_r8_row(label, value, color="#222222"):\n    return {"type": "box", "layout": "horizontal", "margin": "sm", "contents": [\n        _vip1688_r8_txt(label, "sm", "#777777", flex=4),\n        _vip1688_r8_txt(value, "sm", color, True, flex=6, align="end")]}\n\n\ndef _vip1688_r8_bubble(title, subtitle, rows, notes, sub_color="#DDDDDD", footer=None):\n    body = list(rows) or [_vip1688_r8_txt("資料不足", color=_VIP1688_R8_NA)]\n    if notes:\n        body.append({"type": "separator", "margin": "md"})\n        body.append(_vip1688_r8_txt(notes, "sm", "#333333", margin="md"))\n    b = {"type": "bubble", "size": "mega",\n         "header": {"type": "box", "layout": "vertical", "backgroundColor": "#1A1A2E", "paddingAll": "12px", "contents": [\n             _vip1688_r8_txt(title, "md", "#F5C518", True), _vip1688_r8_txt(subtitle, "xs", sub_color, margin="xs")]},\n         "body": {"type": "box", "layout": "vertical", "paddingAll": "12px", "contents": body}}\n    if footer:\n        b["footer"] = {"type": "box", "layout": "vertical", "backgroundColor": "#1A1A2E", "paddingAll": "8px",\n                       "contents": [_vip1688_r8_txt(footer, "xxs", "#AAAAAA", align="center")]}\n    return b\n\n\ndef _vip1688_r8_chapters(ai_text):\n    import re as _re\n    out, cur = {}, None\n    for line in str(ai_text or "").splitlines():\n        m = _re.search(r"第([一二三四五])章", line)\n        if m and "═" in line:\n            cur = "一二三四五".index(m.group(1)) + 1\n            out[cur] = []\n            continue\n        if cur and line.strip():\n            out[cur].append(line.strip())\n    return {k: "\\n".join(v)[:900] for k, v in out.items() if v}\n\n\ndef _vip1688_r8_field(d, key):\n    f = d.get("output_fields") if isinstance(d.get("output_fields"), dict) else {}\n    m = f.get(key) if isinstance(f.get(key), dict) else {}\n    s = str(m.get("value", "") or "").strip()\n    return "" if s in ("N/A", "--", "None", "nan") else s\n\n\ndef _vip1688_r8_stock_bubble(sid, d, ai_lines):\n    sid = str(sid or "").strip()\n    if not isinstance(d, dict):\n        return _vip1688_r8_bubble(f"{sid}", "資料取得失敗", [], "本檔資料取得失敗，未列入解讀。", _VIP1688_R8_NA)\n    name = str(d.get("name") or "").strip()\n    p, c = _vip1688_r8_num(_vip1688_r8_field(d, "price")), _vip1688_r8_num(_vip1688_r8_field(d, "change"))\n    if p is None:\n        sub, sub_c = "收盤資料不足", _VIP1688_R8_NA\n    else:\n        sub, sub_c = f"收 {_vip1688_r8_fmt(p)}", _vip1688_r8_color(c)\n        if c is not None and c != 0 and p - c > 0:\n            sub += f"  {\'▲\' if c > 0 else \'▼\'}{_vip1688_r8_fmt(abs(c))}（{c / (p - c) * 100:+.2f}%）"\n        elif c == 0:\n            sub += "  平盤"\n    rows = []\n    for label, key in (("成交量", "volume"), ("MA5", "MA5"), ("MA20", "MA20"), ("MA60", "MA60"), ("RSI", "RSI"), ("MACD", "MACD")):\n        v = _vip1688_r8_field(d, key)\n        rows.append(_vip1688_r8_row(label, v or "資料不足", "#222222" if v else _VIP1688_R8_NA))\n    k, dd = _vip1688_r8_field(d, "KD_K"), _vip1688_r8_field(d, "KD_D")\n    rows.append(_vip1688_r8_row("KD (K/D)", f"{k} / {dd}" if k and dd else "資料不足", "#222222" if k and dd else _VIP1688_R8_NA))\n    for label, key in (("外資", "foreign_buy"), ("投信", "trust_buy"), ("自營", "dealer_buy")):\n        v = _vip1688_r8_field(d, key)\n        rows.append(_vip1688_r8_row(label, v or "資料不足", _vip1688_r8_color(_vip1688_r8_num(v)) if v else _VIP1688_R8_NA))\n    mine = [l for l in ai_lines if sid and sid in l]\n    return _vip1688_r8_bubble(f"{sid} {name}".strip(), sub, rows, "🤖 " + ("\\n".join(mine)[:500] if mine else "AI 判讀：資料不足"), sub_c)\n\n\ndef _vip1688_r8_build(dna_symbols, results, tw_top10, inst_buy, inst_sell, giants, ai_text, date_note, period_note):\n    import json as _j\n    import re as _re\n    ch = _vip1688_r8_chapters(ai_text)\n    ai1 = (ch.get(1) or "").splitlines()\n    syms = list(dna_symbols or [])[:5]\n    pairs = [(syms[i] if i < len(syms) else "", (r[1] if r and r[0] else None)) for i, r in enumerate(list(results or [])[:5])]\n    tw = [s for s in (tw_top10 or []) if isinstance(s, dict)]\n    tw_has = [s for s in tw if _vip1688_r8_num(s.get("pct")) not in (None, 0)]\n    up = sum(1 for s in tw_has if _vip1688_r8_num(s.get("pct")) > 0)\n    g = giants if isinstance(giants, dict) else {}\n    gup = sum(1 for v in g.values() if isinstance(v, dict) and (_vip1688_r8_num(v.get("change_pct")) or 0) > 0)\n    gdn = sum(1 for v in g.values() if isinstance(v, dict) and (_vip1688_r8_num(v.get("change_pct")) or 0) < 0)\n    m = _re.search(r"大盤多空判斷[：:]\\s*([^\\s，。]{1,4})", str(ai_text or ""))\n    mkt = m.group(1) if m else ""\n    mkt_c = _VIP1688_R8_UP if "多" in mkt else (_VIP1688_R8_DN if "空" in mkt else (_VIP1688_R8_NEU if mkt else _VIP1688_R8_NA))\n    dna_up = sum(1 for _, d in pairs if isinstance(d, dict) and (_vip1688_r8_num(_vip1688_r8_field(d, "change")) or 0) > 0)\n    dna_ok = sum(1 for _, d in pairs if isinstance(d, dict))\n    def _net(items):\n        out = []\n        for it in (items or [])[:5]:\n            if isinstance(it, dict):\n                code = it.get("stock_id") or it.get("code") or it.get("symbol")\n                n = _vip1688_r8_num(it.get("net"))\n                if code and n:\n                    out.append((str(code), n))\n        return out\n    buy, sell = _net(inst_buy), _net(inst_sell)\n    rows1 = [\n        _vip1688_r8_row("大盤判斷", mkt or "資料不足", mkt_c),\n        _vip1688_r8_row("權值股", f"{up}漲 / {len(tw_has) - up}跌" if tw_has else "資料不足",\n                        _vip1688_r8_color(up - (len(tw_has) - up)) if tw_has else _VIP1688_R8_NA),\n        _vip1688_r8_row("美股7巨頭", f"{gup}漲 / {gdn}跌" if (gup + gdn) else "資料不足",\n                        _vip1688_r8_color(gup - gdn) if (gup + gdn) else _VIP1688_R8_NA),\n        _vip1688_r8_row("外資買超第1", buy[0][0] if buy else "資料不足", _VIP1688_R8_UP if buy else _VIP1688_R8_NA),\n        _vip1688_r8_row("DNA 候選", f"{dna_ok} 檔（{dna_up} 漲）" if dna_ok else "資料不足", "#222222" if dna_ok else _VIP1688_R8_NA),\n    ]\n    b = [_vip1688_r8_bubble("💎 發財1688精華報", f"資料日 {date_note} 收盤｜{period_note}", rows1,\n                            "👉 左右滑動：DNA 個股 ×5｜大盤與法人｜美股與策略")]\n    b += [_vip1688_r8_stock_bubble(sid, d, ai1) for sid, d in pairs]\n    rows7 = [_vip1688_r8_row(f"{s.get(\'name\', \'\')}({s.get(\'code\', \'\')})", f"{_vip1688_r8_num(s.get(\'pct\')):+.2f}%",\n                             _vip1688_r8_color(_vip1688_r8_num(s.get("pct")))) for s in tw_has[:10]]\n    if not rows7:\n        rows7 = [_vip1688_r8_row("權值股漲跌", f"{date_note} 收盤資料未取得", _VIP1688_R8_NA)]\n    rows7.append(_vip1688_r8_row("外資買超", "、".join(c for c, _ in buy) or "資料不足", _VIP1688_R8_UP if buy else _VIP1688_R8_NA))\n    rows7.append(_vip1688_r8_row("外資賣超", "、".join(c for c, _ in sell) or "資料不足", _VIP1688_R8_DN if sell else _VIP1688_R8_NA))\n    b.append(_vip1688_r8_bubble("📊 大盤與法人", f"資料日 {date_note} 收盤", rows7,\n                                "\\n\\n".join(x for x in (ch.get(2), ch.get(3)) if x) or "AI 判讀：資料不足"))\n    rows8 = []\n    for nm, v in list(g.items())[:7]:\n        if isinstance(v, dict):\n            cp = _vip1688_r8_num(v.get("change_pct"))\n            rows8.append(_vip1688_r8_row(str(nm), (f"${v.get(\'price\')}  " if v.get("price") not in (None, "") else "")\n                                         + (f"{cp:+.2f}%" if cp is not None else "資料不足"), _vip1688_r8_color(cp)))\n    b.append(_vip1688_r8_bubble("🇺🇸 美股與台指策略", "美股為其最近交易日收盤", rows8,\n                                "\\n\\n".join(x for x in (ch.get(4), ch.get(5)) if x) or "AI 判讀：資料不足",\n                                footer="⚠️ 投資有風險，本報告僅供參考，請獨立判斷"))\n    carousel = {"type": "carousel", "contents": b}\n    size = len(_j.dumps(carousel, ensure_ascii=False).encode("utf-8"))\n    if len(b) > 12 or size > 45000:\n        raise ValueError(f"carousel too large bubbles={len(b)} bytes={size}")\n    return carousel, size\n\n\ndef _vip1688_r8_stash(final_response, dna_symbols, results, tw_top10, inst_buy, inst_sell, giants, ai_text, date_note, period_note):\n    """VIP1688_R8: build the 8-card carousel; keep it for build_report1688_flex on this thread. Any error -> old text path."""\n    _VIP1688_R8_TLS.payload = None\n    try:\n        carousel, size = _vip1688_r8_build(dna_symbols, results, tw_top10, inst_buy, inst_sell, giants, ai_text, date_note, period_note)\n        _VIP1688_R8_TLS.payload = carousel\n        print(f"[VIP1688_R8_STASH] bubbles={len(carousel[\'contents\'])} bytes={size}", flush=True)\n        return f"💎【含金量最高發財1688精華報】\\n📅 資料日 {date_note} 收盤｜{period_note}\\n👉 完整內容請左右滑動 {len(carousel[\'contents\'])} 張卡片"\n    except Exception as e:\n        print(f"[VIP1688_R8_STASH_ERR] {type(e).__name__}: {str(e)[:200]}", flush=True)\n        return final_response\n\n\ndef _vip1688_r8_take():\n    c = getattr(_VIP1688_R8_TLS, "payload", None)\n    if c is None:\n        return None\n    print(f"[VIP1688_R8_RENDER] bubbles={len(c[\'contents\'])}", flush=True)\n    return FlexSendMessage(alt_text="💎 含金量最高發財1688精華報（左右滑動查看完整內容）", contents=c)\n\n\ndef _vip1688_r8_prewarm_etf(symbols):\n    """VIP1688_R8: build the shared ETF master once before 5 parallel fetches (avoid 5x duplicate ISIN parsing)."""\n    import time as _t\n    t0 = _t.time()\n    try:\n        fn = globals().get("is_probable_etf_symbol")\n        if callable(fn) and symbols:\n            fn(str(list(symbols)[0]))\n        print(f"[VIP1688_R8_ETF_PREWARM] ms={int((_t.time() - t0) * 1000)}", flush=True)\n    except Exception as e:\n        print(f"[VIP1688_R8_ETF_PREWARM_ERR] {type(e).__name__}: {str(e)[:160]}", flush=True)\n\n\n'
ANCHOR = "def _vip1688_r7_stock_line("
POOL = "        with _TPE8888(max_workers=8) as _ex8b:"
PREWARM = "        _vip1688_r8_prewarm_etf(dna_symbols[:1])  # VIP1688_R8\n"
R7B = "        # VIP1688_R7B: data-only prompt"
FINAL_END = "            + ai_interpretation\n            + LEGAL_WARNING\n        )\n"
STASH = ("        final_response = _vip1688_r8_stash(final_response, dna_symbols, _8888_results, tw_top10, inst_buy, "
         "inst_sell, giants, ai_interpretation, date_note, period_note)  # VIP1688_R8\n")
DOC_END = "    大盤判斷、台指期方向，組成快覽儀表板\n    \"\"\"\n    import re as _re\n"
TAKE = "    _r8 = _vip1688_r8_take()  # VIP1688_R8\n    if _r8 is not None:\n        return _r8\n"
P1_OLD, P1_NEW = "逐檔一句技術判讀（只用dna_stocks欄位），附支持與反證。", "逐檔各一行，行首寫股票代號與冒號（例：3653：），2～3句技術判讀，只引用dna_stocks欄位數值，附支持與反證。"
P2_OLD, P2_NEW = "每章最多6行", "第一章每檔一行，其餘每章最多8行"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def need(cond, msg, **dbg):
    if not cond:
        raise RuntimeError(f"{msg} | debug={dbg}")


def patch(t):
    need("_vip1688_r8_" not in t, "R8 already applied")
    for name, s in (("anchor", ANCHOR), ("pool", POOL), ("r7b", R7B), ("doc_end", DOC_END), ("p1", P1_OLD), ("p2", P2_OLD)):
        need(t.count(s) == 1, f"{name} count != 1", count=t.count(s))
    i = t.index(R7B)
    j = t.find(FINAL_END, i)
    need(0 < j - i < 6000, "final_response end not found after 1688 prompt", dist=j - i)
    j += len(FINAL_END)
    t = t[:j] + STASH + t[j:]
    t = t.replace(POOL, PREWARM + POOL).replace(DOC_END, DOC_END + TAKE)
    t = t.replace(P1_OLD, P1_NEW).replace(P2_OLD, P2_NEW)
    return t.replace(ANCHOR, HELPER + ANCHOR)


def helper_tests():
    import json
    ns = {"FlexSendMessage": lambda **k: k}
    exec(HELPER, ns)
    def mk(n, p, c, v):
        return {"name": n, "output_fields": {"price": {"value": p}, "change": {"value": c}, "volume": {"value": v},
                "MA5": {"value": "7020.5"}, "MA20": {"value": "6650.1"}, "MA60": {"value": "N/A"}, "RSI": {"value": "67.19"},
                "MACD": {"value": "109.03"}, "KD_K": {"value": "90.79"}, "KD_D": {"value": "84.97"},
                "foreign_buy": {"value": "+549張"}, "trust_buy": {"value": "-444張"}, "dealer_buy": {"value": "N/A"}}}
    syms = ["3653", "3661", "6515", "3533", "8996"]
    res = [("x", mk("健策", "7165.0", "360.0", "1,629張")), ("x", mk("世芯-KY", "4345.0", "155.0", "4,923張")),
           ("x", mk("穎崴", "5615.0", "-95.0", "1,100張")), (None, None), ("x", mk("高力", "1710.0", "65.0", "1,086張"))]
    tw = [{"code": "2330", "name": "台積電", "pct": 0, "note": "更新中"}] * 10
    giants = {"AMZN": {"price": 262.43, "change_pct": 2.31}, "NVDA": {"price": 229.28, "change_pct": -1.95}, "MSFT": {"price": 535.07, "change_pct": 1.29}}
    ai = ("═══【第一章：DNA技術】═══\n3653：站上MA5與MA20，RSI 67.19 偏強；反證：KD 高檔。\n6515：收5615 低於MA20。\n"
          "═══【第二章：大盤解析】═══\n大盤多空判斷：中性\n權值股資料不足。\n═══【第三章：法人籌碼】═══\n資料不足\n"
          "═══【第四章：美股7巨頭】═══\n亞馬遜漲2.31%。\n═══【第五章：台指聯動與策略】═══\n期貨資料不足。")
    r = {}
    txt = ns["_vip1688_r8_stash"]("ORIG", syms, res, tw, [], [], giants, ai, "10/08", "休市")
    c = ns["_VIP1688_R8_TLS"].payload
    r["stash_ok"] = c is not None and "左右滑動 8 張" in txt
    r["eight_bubbles"] = len(c["contents"]) == 8
    def walk(n, bad):
        if isinstance(n, dict):
            if n.get("type") == "text" and not str(n.get("text", "")).strip(): bad.append(n)
            if n.get("type") == "box" and not n.get("contents"): bad.append(n)
            for v in n.values(): walk(v, bad)
        elif isinstance(n, list):
            for v in n: walk(v, bad)
        return bad
    r["no_empty_text_or_box"] = walk(c, []) == []
    size = len(json.dumps(c, ensure_ascii=False).encode()); r["size_under_45k"] = size < 45000
    s1 = json.dumps(c["contents"][1], ensure_ascii=False)
    r["stock_up_red"] = '"text": "收 7,165  ▲360（+5.29%）", "size": "xs", "color": "#E74C3C"' in s1
    s3 = json.dumps(c["contents"][3], ensure_ascii=False)
    r["stock_down_green"] = "#27AE60" in s3 and "▼95（-1.66%）" in s3
    r["failed_stock_listed"] = "資料取得失敗" in json.dumps(c["contents"][4], ensure_ascii=False)
    r["ai_line_mapped"] = "RSI 67.19 偏強" in s1
    r["missing_marked_gray"] = '"text": "資料不足", "size": "sm", "color": "#9E9E9E"' in s1
    s7 = json.dumps(c["contents"][6], ensure_ascii=False)
    r["holiday_tw_honest"] = "10/08 收盤資料未取得" in s7
    r["overview_mkt_neutral"] = "中性" in json.dumps(c["contents"][0], ensure_ascii=False)
    m = ns["_vip1688_r8_take"](); r["take_returns_flex"] = m["contents"] is c
    bad = ns["_vip1688_r8_stash"]("ORIG", syms, 5, tw, [], [], giants, ai, "10/08", "休市")
    r["broken_input_falls_back"] = bad == "ORIG" and ns["_VIP1688_R8_TLS"].payload is None and ns["_vip1688_r8_take"]() is None
    return r


def wiring(t):
    tree = ast.parse(t)
    r = {}
    f = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "build_report1688_flex"]
    r["take_first_in_flex"] = len(f) == 1 and any(isinstance(x, ast.Assign) and "_vip1688_r8_take" in ast.unparse(x) for x in f[0].body[:4])
    r["prewarm_before_pool"] = t.index(PREWARM) + len(PREWARM) == t.index(POOL)
    r["stash_after_final"] = t.index(STASH) == t.index(FINAL_END, t.index(R7B)) + len(FINAL_END)
    r["prompt_updated"] = P1_NEW in t and P2_NEW in t and P1_OLD not in t
    r["helpers_module_level"] = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)} >= {
        "_vip1688_r8_stash", "_vip1688_r8_take", "_vip1688_r8_prewarm_etf", "_vip1688_r8_build"}
    return r


def main():
    out = {"status": "STOP", "revision": "VIP1688_R8", "deployed": False, "line_sent": False, "ai_called": False}
    dst = None
    try:
        app = os.path.join(SRC, "app.py")
        raw = open(app, "rb").read()
        need(sha(raw) == SRC_SHA, "source app SHA mismatch", got=sha(raw))
        old = raw.decode("utf-8")
        new = patch(old)
        compile(new, "app.py", "exec", dont_inherit=True)
        checks = helper_tests()
        checks.update(wiring(new))
        need(all(checks.values()), "behaviour check failed", checks=checks)
        diff = [l for l in difflib.unified_diff(old.splitlines(), new.splitlines(), "r7", "r8", n=0, lineterm="")
                if l[:1] in "+-" and l[:3] not in ("+++", "---")]
        removed = [l[1:] for l in diff if l.startswith("-")]
        need(all((P1_OLD in l) or (P2_OLD in l) for l in removed), "unexpected removed lines", removed=removed[:5])
        dst = os.path.join(HOME, "vip1688_r8_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        os.mkdir(dst)
        subprocess.run(["cp", "-al", SRC, os.path.join(dst, "source")], check=True)
        target = os.path.join(dst, "source", "app.py")
        tmp = target + ".r8tmp"
        with open(tmp, "wb") as fh:
            fh.write(new.encode("utf-8"))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
        nb = open(target, "rb").read()
        need(nb == new.encode("utf-8"), "written app mismatch")
        need(sha(open(app, "rb").read()) == SRC_SHA, "SOURCE CHANGED - stop")
        need(os.stat(target).st_nlink == 1, "candidate app still hardlinked", nlink=os.stat(target).st_nlink)
        out.update(status="candidate_ready", candidate=os.path.join(dst, "source"), new_app_sha=sha(nb),
                   checks=checks, removed_lines=len(removed), added_lines=len(diff) - len(removed))
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
        out["traceback"] = traceback.format_exc()[-1500:]
        out["partial_candidate"] = dst
    print("R8_RESULT " + json.dumps(out, ensure_ascii=False))
    return 0 if out["status"] == "candidate_ready" else 2


if __name__ == "__main__":
    sys.exit(main())
