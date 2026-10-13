"""VIP1688 R9: REPORT_8888 only, on top of R8d. (1) TX near-month vs TAIEX close, change, % and basis on the US/strategy card
(official TAIFEX + TWSE open data, fetched in background with the institution snapshot, also given to the AI chapter 5);
(2) 72h news + official material info (listed TWSE + OTC TPEx) under each DNA stock card, fetched during the AI call.
No deploy, no LINE, no AI."""
import datetime, difflib, glob, hashlib, json, os, subprocess, sys, traceback, types, email.utils

HOME = os.path.expanduser("~")
SRC_SHA = "6d6f2bfa67c407089e809e04771e78f371e18755e931f874a2f669ab55266ea2"
HELPER = 'def _vip1688_r9_start(fn, *a):\n    """VIP1688_R9: run fn in a background thread; returns a future (None on failure)."""\n    try:\n        import concurrent.futures as _cf\n        ex = _cf.ThreadPoolExecutor(max_workers=1)\n        fut = ex.submit(fn, *a)\n        ex.shutdown(wait=False)\n        return fut\n    except Exception as e:\n        print(f"[VIP1688_R9_START_ERR] {type(e).__name__}: {str(e)[:160]}", flush=True)\n        return None\n\n\ndef _vip1688_r9_json(url, timeout=15):\n    import json as _j\n    import requests as _rq\n    r = _rq.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})\n    r.raise_for_status()\n    return _j.loads(r.content.decode("utf-8-sig"))\n\n\ndef _vip1688_r9_tx():\n    """VIP1688_R9: TX near-month regular session (TAIFEX) vs TAIEX (TWSE); basis only when both are the same trading day."""\n    import json as _j\n    import time as _t\n    t0, n = _t.time(), _vip1688_r8_num\n    tx = [r for r in _vip1688_r9_json("https://openapi.taifex.com.tw/v1/DailyMarketReportFut")\n          if isinstance(r, dict) and str(r.get("Contract", "")).strip() == "TX"\n          and str(r.get("TradingSession", "")).strip() == "一般" and str(r.get("ContractMonth(Week)", "")).strip().isdigit()]\n    near = min(tx, key=lambda r: str(r.get("ContractMonth(Week)")).strip())\n    idx = [r for r in _vip1688_r9_json("https://openapi.twse.com.tw/v1/exchangeReport/MI_INDEX")\n           if isinstance(r, dict) and str(r.get("指數", "")).strip() == "發行量加權股價指數"][0]\n    roc = str(idx.get("日期", "")).strip()\n    sign = -1 if str(idx.get("漲跌", "")).strip() == "-" else 1\n    ic, ip = n(idx.get("漲跌點數")), n(idx.get("漲跌百分比"))\n    out = {"期貨日": str(near.get("Date", "")).strip(), "月份": str(near.get("ContractMonth(Week)", "")).strip(),\n           "台指期收盤": n(near.get("Last")), "台指期漲跌": n(near.get("Change")), "台指期漲跌幅%": n(near.get("%")),\n           "現貨日": f"{int(roc[:-4]) + 1911}{roc[-4:]}" if len(roc) >= 7 and roc.isdigit() else "",\n           "加權指數收盤": n(idx.get("收盤指數")), "加權指數漲跌": None if ic is None else sign * abs(ic),\n           "加權指數漲跌幅%": None if ip is None else sign * abs(ip)}\n    f, s = out["台指期收盤"], out["加權指數收盤"]\n    out["期現價差"] = round(f - s, 2) if (f is not None and s is not None and out["期貨日"] == out["現貨日"]) else None\n    print(f"[VIP1688_R9_TX] {_j.dumps(out, ensure_ascii=False)} ms={int((_t.time() - t0) * 1000)}", flush=True)\n    return out\n\n\ndef _vip1688_r9_material():\n    """VIP1688_R9: material announcements, listed (TWSE) + OTC (TPEx): code -> [(MM/DD, subject)]."""\n    import re as _re\n    out = {}\n    for url in ("https://openapi.twse.com.tw/v1/opendata/t187ap04_L", "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap04_O"):\n        try:\n            rows = _vip1688_r9_json(url, 10)\n        except Exception as e:\n            print(f"[VIP1688_R9_MATERIAL_ERR] {url.rsplit(\'/\', 1)[-1]} {type(e).__name__}: {str(e)[:120]}", flush=True)\n            continue\n        cnt = 0\n        for r in rows if isinstance(rows, list) else []:\n            if not isinstance(r, dict):\n                continue\n            k = {str(x).strip(): v for x, v in r.items()}\n            code = next((str(v).strip() for x, v in k.items() if _re.search(r"公司代號|CompanyCode", x)), "")\n            subj = next((str(v) for x, v in k.items() if _re.search(r"主旨|Subject", x)), "")\n            day = next((str(v).strip() for x, v in k.items() if _re.search(r"發言日期|SpokesmanDate|AnnouncementDate", x)), "")\n            if code and subj.strip():\n                cnt += 1\n                out.setdefault(code, []).append((f"{day[-4:-2]}/{day[-2:]}" if len(day) >= 7 else "", _re.sub(r"\\s+", "", subj)))\n        print(f"[VIP1688_R9_MATERIAL] {url.rsplit(\'/\', 1)[-1]} rows={len(rows) if isinstance(rows, list) else 0} used={cnt}", flush=True)\n    return out\n\n\ndef _vip1688_r9_gnews(q, now, limit=3):\n    """VIP1688_R9: Google News RSS titles for q published within the last 72 hours: [(datetime, title)]."""\n    import email.utils as _eu\n    import html as _h\n    import re as _re\n    import urllib.parse as _up\n    import requests as _rq\n    url = "https://news.google.com/rss/search?q=" + _up.quote(q + " when:3d") + "&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"\n    t = _rq.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"}).text\n    out = []\n    for it in _re.findall(r"<item>(.*?)</item>", t, _re.S):\n        ti, pd = _re.search(r"<title>(.*?)</title>", it, _re.S), _re.search(r"<pubDate>(.*?)</pubDate>", it, _re.S)\n        try:\n            dt = _eu.parsedate_to_datetime(pd.group(1).strip())\n        except Exception:\n            continue\n        if ti and 0 <= (now - dt).total_seconds() <= 72 * 3600:\n            out.append((dt, _h.unescape(_re.sub(r"<!\\[CDATA\\[|\\]\\]>", "", ti.group(1))).strip()))\n    out.sort(key=lambda x: x[0], reverse=True)\n    return out[:limit]\n\n\ndef _vip1688_r9_news(pairs):\n    """VIP1688_R9: per DNA stock (listed or OTC): official material info first, then 72h news titles; code -> lines."""\n    import concurrent.futures as _cf\n    import datetime as _dt\n    import time as _t\n    t0 = _t.time()\n    now = _dt.datetime.now(_dt.timezone.utc)\n    tz = _dt.timezone(_dt.timedelta(hours=8))\n\n    def one(code, name):\n        got = _vip1688_r9_gnews(f"{name} {code}", now)\n        if len(got) < 2:\n            got += _vip1688_r9_gnews(name, now)\n        seen, lines = set(), []\n        for dt, ti in sorted(got, key=lambda x: x[0], reverse=True):\n            key = ti.rsplit(" - ", 1)[0]\n            if key not in seen:\n                seen.add(key)\n                lines.append(f"📰 {dt.astimezone(tz):%m/%d} {ti}")\n        return lines\n    out = {}\n    with _cf.ThreadPoolExecutor(max_workers=6) as ex:\n        mf = ex.submit(_vip1688_r9_material)\n        fs = {code: ex.submit(one, code, name) for code, name in pairs if code and name}\n        try:\n            mat = mf.result(timeout=15)\n        except Exception:\n            mat = {}\n        for code, f in fs.items():\n            try:\n                news = f.result(timeout=15)\n            except Exception as e:\n                print(f"[VIP1688_R9_NEWS_ERR] {code} {type(e).__name__}: {str(e)[:120]}", flush=True)\n                news = None\n            m = [f"📢 {d} {s}".replace("📢  ", "📢 ") for d, s in mat.get(code, [])]\n            out[code] = None if (news is None and not m) else (m + (news or []))[:3]\n    print(f"[VIP1688_R9_NEWS] " + " ".join(f"{c}={len(v) if v is not None else \'ERR\'}" for c, v in out.items())\n          + f" ms={int((_t.time() - t0) * 1000)}", flush=True)\n    return out\n\n\ndef _vip1688_r9_prepare(tx_fut, dna_symbols, results):\n    """VIP1688_R9: collect TX/TAIEX (max 20s) for the AI data, start the news fetch in background (runs during AI)."""\n    import re as _re\n    tx = None\n    try:\n        tx = tx_fut.result(timeout=20) if tx_fut is not None else None\n    except Exception as e:\n        print(f"[VIP1688_R9_TX_ERR] {type(e).__name__}: {str(e)[:160]}", flush=True)\n    pairs = []\n    for s, r in zip(list(dna_symbols or [])[:5], list(results or [])[:5]):\n        d = r[1] if (isinstance(r, (list, tuple)) and len(r) > 1 and r[0]) else None\n        if isinstance(d, dict):\n            pairs.append((str(s).strip(), _re.split(r"[\\s|｜(（📈📉]", str(d.get("name") or "").strip())[0]))\n    _VIP1688_R8_TLS.r9 = {"tx": tx, "news": _vip1688_r9_start(_vip1688_r9_news, pairs)}\n    return tx\n\n\ndef _vip1688_r9_take():\n    r9 = getattr(_VIP1688_R8_TLS, "r9", None) or {}\n    _VIP1688_R8_TLS.r9 = None\n    return r9\n\n\ndef _vip1688_r9_add_news(bubbles, pairs, r9):\n    """VIP1688_R9: 72h news / material info under each DNA stock card."""\n    news, ok = {}, False\n    try:\n        f = (r9 or {}).get("news")\n        if f is not None:\n            news, ok = f.result(timeout=20) or {}, True\n    except Exception as e:\n        print(f"[VIP1688_R9_NEWS_ERR] collect {type(e).__name__}: {str(e)[:120]}", flush=True)\n    for bub, (sid, d) in zip(bubbles, pairs):\n        if not isinstance(d, dict):\n            continue\n        items = news.get(str(sid).strip()) if ok else None\n        body = bub["body"]["contents"]\n        body.append({"type": "separator", "margin": "md"})\n        body.append(_vip1688_r8_txt("72小時新聞與重大訊息", "sm", "#1A1A2E", True, margin="md"))\n        if items:\n            body.extend(_vip1688_r8_txt(x[:72], "xs", "#555555", margin="sm") for x in items)\n        else:\n            body.append(_vip1688_r8_txt("72小時內無相關新聞" if items == [] else "新聞來源暫時無法取得", "xs", _VIP1688_R8_NA, margin="sm"))\n\n\ndef _vip1688_r9_tx_rows(r9):\n    """VIP1688_R9: TX vs TAIEX rows (close, change, %, basis); red up / green down / gray missing."""\n    tx = (r9 or {}).get("tx")\n    sep = {"type": "separator", "margin": "md"}\n    if not isinstance(tx, dict):\n        return [sep, _vip1688_r8_row("台指期／加權指數", "資料取得失敗", _VIP1688_R8_NA)]\n\n    def fmt(v, c, p):\n        if v is None:\n            return "資料不足"\n        s = _vip1688_r8_fmt(v)\n        if c is not None:\n            s += f" {\'▲\' if c > 0 else (\'▼\' if c < 0 else \'\')}{_vip1688_r8_fmt(abs(c))}"\n        return s + (f"（{p:+.2f}%）" if p is not None else "")\n    day, mon, b = tx.get("期貨日") or "", tx.get("月份") or "", tx.get("期現價差")\n    return [sep, _vip1688_r8_txt(f"台指期 vs 加權指數（{day[4:6]}/{day[6:]} 收盤）" if len(day) == 8 else "台指期 vs 加權指數",\n                                 "sm", "#1A1A2E", True, margin="md"),\n            _vip1688_r8_row(f"台指期 {int(mon[4:6])}月" if len(mon) == 6 else "台指期近月",\n                            fmt(tx.get("台指期收盤"), tx.get("台指期漲跌"), tx.get("台指期漲跌幅%")), _vip1688_r8_color(tx.get("台指期漲跌"))),\n            _vip1688_r8_row("加權指數", fmt(tx.get("加權指數收盤"), tx.get("加權指數漲跌"), tx.get("加權指數漲跌幅%")),\n                            _vip1688_r8_color(tx.get("加權指數漲跌"))),\n            _vip1688_r8_row("期現價差", f"{b:+,.2f} {\'正價差\' if b > 0 else (\'逆價差\' if b < 0 else \'平價\')}" if b is not None\n                            else "日期不一致，不計算", _vip1688_r8_color(b))]\n\n\n'
ANCHOR = "def _vip1688_r7_stock_line("
START_OLD = "        _r8c_insti_fut = _vip1688_r8c_insti_start()  # VIP1688_R8C\n"
START_NEW = START_OLD + "        _r9_tx_fut = _vip1688_r9_start(_vip1688_r9_tx)  # VIP1688_R9\n"
COLLECT = "        inst_buy, inst_sell = _vip1688_r8c_insti_collect(_r8c_insti_fut)  # VIP1688_R8C\n"
DATA_MARK = "        data_str = json.dumps({\n"
PREP = "        _r9_tx = _vip1688_r9_prepare(_r9_tx_fut, dna_symbols, _8888_results)  # VIP1688_R9\n"
DATA_ENTRY = '            "台指期與加權指數": _r9_tx,  # VIP1688_R9\n'
P_OLD = "最多3句條件式策略與失效條件；無期貨數據須註明『期貨資料不足』"
P_NEW = "依『台指期與加權指數』判讀期現價差與聯動，不得重述數字，最多3句條件式策略與失效條件；該項為空時註明『期貨資料不足』"
STOCK_OLD = "    b += [_vip1688_r8_stock_bubble(sid, d, ai1) for sid, d in pairs]\n"
STOCK_NEW = ("    _r9 = _vip1688_r9_take()  # VIP1688_R9\n" + STOCK_OLD
             + "    _vip1688_r9_add_news(b[1:], pairs, _r9)  # VIP1688_R9\n")
US_OLD = '    us_note = "\\n\\n".join(x for x in (ch.get(4), ch.get(5)) if x)[:480]\n'
US_NEW = "    rows8 += _vip1688_r9_tx_rows(_r9)  # VIP1688_R9\n" + US_OLD
EDITS = [("anchor", ANCHOR, HELPER + ANCHOR), ("start", START_OLD, START_NEW),
         ("collect", COLLECT + DATA_MARK, COLLECT + PREP + DATA_MARK + DATA_ENTRY),
         ("prompt", P_OLD, P_NEW), ("stock", STOCK_OLD, STOCK_NEW), ("us", US_OLD, US_NEW)]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def need(cond, msg, **dbg):
    if not cond:
        raise RuntimeError(f"{msg} | debug={dbg}")


def find_src():
    hits = [d for d in sorted(glob.glob(os.path.join(HOME, "vip1688_r8d_*", "source")))
            if os.path.isfile(os.path.join(d, "app.py")) and sha(open(os.path.join(d, "app.py"), "rb").read()) == SRC_SHA]
    need(hits, "R8d candidate with expected SHA not found", searched=glob.glob(os.path.join(HOME, "vip1688_r8d_*")))
    return hits[-1]


def patch(t):
    need("_vip1688_r9_" not in t, "R9 already applied")
    for name, old, new in EDITS:
        need(t.count(old) == 1, f"{name} count != 1", count=t.count(old))
        t = t.replace(old, new)
    return t


class _Resp:
    def __init__(self, b):
        self.content, self.text = b, b.decode("utf-8")

    def raise_for_status(self):
        pass


def behaviour(t):
    s = t.index("import threading as _vip1688_r8_threading")
    e = t.index(ANCHOR)
    ns = {"FlexSendMessage": lambda **k: k}
    exec(compile(t[s:e], "r9", "exec"), ns)
    J = lambda x: json.dumps(x, ensure_ascii=False)
    r = {}
    fut = [{"Date": "20261008", "Contract": "TX", "ContractMonth(Week)": "202610", "Last": "49349", "Change": "-619", "%": "-1.24%", "TradingSession": "一般"},
           {"Date": "20261008", "Contract": "TX", "ContractMonth(Week)": "202610", "Last": "49593", "Change": "-375", "%": "-0.75%", "TradingSession": "盤後"},
           {"Date": "20261008", "Contract": "TX", "ContractMonth(Week)": "202611", "Last": "49546", "Change": "-598", "%": "-1.19%", "TradingSession": "一般"},
           {"Date": "20261008", "Contract": "TX", "ContractMonth(Week)": "202610W2", "Last": "1", "Change": "0", "%": "0%", "TradingSession": "一般"},
           {"Date": "20261008", "Contract": "MTX", "ContractMonth(Week)": "202609", "Last": "2", "Change": "0", "%": "0%", "TradingSession": "一般"}]
    idx = [{"日期": "1151008", "指數": "發行量加權股價報酬指數", "收盤指數": "114031.08", "漲跌": "-", "漲跌點數": "1,139.84", "漲跌百分比": "-0.99"},
           {"日期": "1151008", "指數": "發行量加權股價指數", "收盤指數": "49313.44", "漲跌": "-", "漲跌點數": "492.93", "漲跌百分比": "-0.99"}]
    mat_l = [{"出表日期": "1151012", "發言日期": "1151011", "公司代號": "2072", "公司名稱": "世紀風電", "主旨 ": "公告本公司名稱\r\n更名"}]
    mat_o = [{"SpokesmanDate": "1151010", "SecuritiesCompanyCode": "6515", "Subject": "董事會決議發放股利"}]
    data = {"DailyMarketReportFut": fut, "MI_INDEX": idx, "t187ap04_L": mat_l, "mopsfin_t187ap04_O": mat_o}
    ns["_vip1688_r9_json"] = lambda url, timeout=15: data[url.rsplit("/", 1)[-1]]
    tx = ns["_vip1688_r9_tx"]()
    r["tx_near_regular"] = tx["台指期收盤"] == 49349 and tx["月份"] == "202610" and tx["台指期漲跌幅%"] == -1.24
    r["taiex_signed"] = tx["加權指數收盤"] == 49313.44 and tx["加權指數漲跌"] == -492.93 and tx["加權指數漲跌幅%"] == -0.99
    r["basis_same_day"] = tx["期現價差"] == 35.56 and tx["現貨日"] == "20261008"
    idx2 = [dict(idx[1], 日期="1151007")]
    data["MI_INDEX"] = idx2
    r["basis_none_when_day_differs"] = ns["_vip1688_r9_tx"]()["期現價差"] is None
    data["MI_INDEX"] = idx
    mat = ns["_vip1688_r9_material"]()
    r["material_listed_and_otc"] = mat.get("2072") == [("10/11", "公告本公司名稱更名")] and mat.get("6515") == [("10/10", "董事會決議發放股利")]
    now = datetime.datetime.now(datetime.timezone.utc)
    rss = "".join(f"<item><title>{ti}</title><pubDate>{email.utils.format_datetime(now - datetime.timedelta(hours=h))}</pubDate></item>"
                  for ti, h in (("健策營收創高 &amp; 新高 - 經濟日報", 5), ("健策舊聞 - 工商時報", 80), ("<![CDATA[健策法說 - 鉅亨網]]>", 30)))
    fake = types.ModuleType("requests")
    fake.get = lambda url, timeout=8, headers=None: _Resp(rss.encode("utf-8"))
    old_req = sys.modules.get("requests")
    sys.modules["requests"] = fake
    try:
        g = ns["_vip1688_r9_gnews"]("健策 3653", now)
        r["gnews_72h_filter"] = [x[1] for x in g] == ["健策營收創高 & 新高 - 經濟日報", "健策法說 - 鉅亨網"]
        news = ns["_vip1688_r9_news"]([("3653", "健策"), ("6515", "穎崴")])
        r["news_material_first_dedup"] = (news["6515"][0] == "📢 10/10 董事會決議發放股利" and len(news["3653"]) == 2
                                          and news["3653"][0].startswith("📰 ") and "營收創高" in news["3653"][0])
    finally:
        if old_req is None:
            sys.modules.pop("requests", None)
        else:
            sys.modules["requests"] = old_req
    mk = lambda n, p, c: {"name": n, "output_fields": {"price": {"value": p}, "change": {"value": c}, "MA5": {"value": "7011.0"}}}
    res = [("3653", mk("健策", "7165", "360")), ("6515", mk("穎崴 📈", "5615", "-95")), (None, None)]
    done = types.SimpleNamespace(result=lambda timeout=None: {"3653": ["📰 10/11 健策營收創高"], "6515": []})
    ns["_vip1688_r9_start"] = lambda fn, *a: done if fn is ns["_vip1688_r9_news"] else None
    got = ns["_vip1688_r9_prepare"](types.SimpleNamespace(result=lambda timeout=None: tx), ["3653", "6515", "3533"], res)
    r["prepare_returns_tx"] = got is tx and ns["_VIP1688_R8_TLS"].r9["news"] is done
    ai = ("═══【第一章：DNA技術】═══\n3653：站上MA5。\n═══【第五章：台指聯動與策略】═══\n期現價差35.56點偏正。若跌破月線則停損。\n"
          "═══【第六章：總結】═══\n偏空整理。")
    c, size = ns["_vip1688_r8_build"](["3653", "6515", "3533"], res, [], [], [], {"NVDA": {"price": 1, "change_pct": -1.0}}, ai, "10/08", "休市")
    s1, s2, s3, us = J(c["contents"][1]), J(c["contents"][2]), J(c["contents"][3]), J(c["contents"][-1])
    r["stock_news_shown"] = "72小時新聞與重大訊息" in s1 and "📰 10/11 健策營收創高" in s1
    r["stock_no_news_gray"] = "72小時內無相關新聞" in s2 and "#9E9E9E" in s2
    r["failed_stock_no_news"] = "72小時新聞" not in s3
    r["us_tx_rows"] = ("台指期 10月" in us and "49,349 ▼619（-1.24%）" in us and "49,313.44 ▼492.93（-0.99%）" in us
                       and '"text": "+35.56 正價差", "size": "sm", "color": "#E74C3C"' in us)
    r["us_note_dedup"] = "35.56點" not in us and "若跌破月線則停損" in us
    r["tls_cleared"] = ns["_VIP1688_R8_TLS"].r9 is None
    c2, _ = ns["_vip1688_r8_build"](["3653"], res[:1], [], [], [], {}, ai, "10/08", "")
    r["missing_r9_safe"] = "資料取得失敗" in J(c2["contents"][-1]) and "新聞來源暫時無法取得" in J(c2["contents"][1])
    r["size_ok"] = size < 45000 and '"text": ""' not in J(c)
    i = t.index(PREP)
    r["wiring_order"] = (t.index("_8888_results = ") < i and t.index("_r9_tx_fut = _vip1688_r9_start") < i
                         < t.index(DATA_ENTRY) < t.index("# 8888精華報使用", i))
    return r


def main():
    out = {"status": "STOP", "revision": "VIP1688_R9", "deployed": False, "line_sent": False, "ai_called": False}
    dst = None
    try:
        src = find_src()
        app = os.path.join(src, "app.py")
        old = open(app, "rb").read().decode("utf-8")
        new = patch(old)
        compile(new, "app.py", "exec", dont_inherit=True)
        checks = behaviour(new)
        need(all(checks.values()), "behaviour check failed", checks=checks)
        diff = [l for l in difflib.unified_diff(old.splitlines(), new.splitlines(), "r8d", "r9", n=0, lineterm="")
                if l[:1] in "+-" and l[:3] not in ("+++", "---")]
        removed = [l[1:] for l in diff if l.startswith("-")]
        need(len(removed) <= 2 and all("期貨資料不足" in l for l in removed), "unexpected removed lines", removed=removed[:4])
        dst = os.path.join(HOME, "vip1688_r9_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        os.mkdir(dst)
        subprocess.run(["cp", "-al", src, os.path.join(dst, "source")], check=True)
        target = os.path.join(dst, "source", "app.py")
        tmp = target + ".r9tmp"
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
    print("R9_RESULT " + json.dumps(out, ensure_ascii=False))
    return 0 if out["status"] == "candidate_ready" else 2


if __name__ == "__main__":
    sys.exit(main())
