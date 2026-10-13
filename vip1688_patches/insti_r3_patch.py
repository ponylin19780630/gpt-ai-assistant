"""INSTI_R3: 三大法人同買/同賣卡片新增「外本比／投本比（當日｜近5日累計）＋趨勢」。
只改 insti_query_r1.py（在 __main__ 前插入；build_messages 以包裝方式加列，原輸出逐字不變）。
app.py、select_rows、_fetch_latest、_CONTEXT（1688 R13/R13b 依賴）完全不動。
用法：python3 -B insti_r3_patch.py [--src DIR] [--no-net]
"""
import hashlib, json, os, subprocess, sys, time

APP_SHA = "0f0dc47572b6293d1ff27f6631fb1954bc3ea010e861d21bec1b1e334258e1d4"
SRC_SHA = "28185d5967406ce879f635bd613a9211770f02be0fb2daa40cf4a7593d325b2b"
ANCHOR = '\nif __name__ == "__main__":\n'
INJECT = r'''
# ===== INSTI_R3：外本比／投本比（當日｜近5日累計）＋趨勢 =====
_R3_SHARES = {"day": None, "data": {}, "mkt": {}, "fail": set()}
_R3_STAR = {"day": None, "set": set(), "top": {}}
_R3_DAYS = {}
_R3_PREV = {}
_R3_LOCK = threading.Lock()
_R3_DARK = {1: "#FF7A7A", -1: "#5FD38D", 0: "#F5C518", None: "#9A9A9A", "L": "#B9B7B2"}
_R3_LIGHT = {1: "#B3261E", -1: "#1B6B3A", 0: "#7A5C00", None: "#5F5F5F", "L": "#504C46"}


def _r3_json(url, tries=2):
    """官方 OpenAPI 讀取；斷線/逾時重試（R3f）。"""
    last = None
    for k in range(tries):
        try:
            return _requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20).json()
        except Exception as exc:
            last = exc
            print(f"[INSTI_R3_HTTP_RETRY] {url.rsplit('/', 1)[-1]} try={k + 1} {type(exc).__name__}", flush=True)
            time.sleep(1.5)
    raise last


def _r3_shares():
    """官方發行股數（股）：TWSE t187ap03_L＋TPEx mopsfin_t187ap03_O，台北同日快取。"""
    day = dt.datetime.now(TAIPEI).date()
    if _R3_SHARES["day"] == day and _R3_SHARES["data"]:
        return _R3_SHARES["data"]
    out, mkt, fail = {}, {}, set()
    for url, ck, sk, mk in (
        ("https://openapi.twse.com.tw/v1/opendata/t187ap03_L", "公司代號",
         "已發行普通股數或TDR原股發行股數", "上市"),
        ("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O",
         "SecuritiesCompanyCode", "IssueShares", "上櫃"),
    ):
        name = url.rsplit("/", 1)[-1]
        try:
            rows = _r3_json(url)
            n = 0
            for r in rows if isinstance(rows, list) else []:
                k = ({str(a).strip(): v for a, v in r.items()}
                     if isinstance(r, dict) else {})
                try:
                    v = int(Decimal(str(k.get(sk, "")).replace(",", "").strip()))
                except (InvalidOperation, ValueError):
                    continue
                code = str(k.get(ck, "")).strip()
                if code and v > 0:
                    out[code] = v
                    mkt[code] = mk
                    n += 1
            print(f"[INSTI_R3_SHARES] src={name} n={n}", flush=True)
            if n == 0:
                fail.add(mk)
        except Exception as exc:
            fail.add(mk)
            print(f"[INSTI_R3_SHARES_ERR] src={name} {type(exc).__name__}: "
                  f"{str(exc)[:100]}", flush=True)
    # 任一市場失敗就不快取（下次重抓），並記錄失敗市場供「資料不足」如實說明。
    _R3_SHARES.update(day=None if fail else day, data=out, mkt=mkt, fail=fail)
    return out


def _r3_star_set(shares):
    """★權值股＝上市市值前50（官方發行股數×官方最近收盤價），台北同日快取。R3h：不再抓上櫃收盤價。"""
    day = dt.datetime.now(TAIPEI).date()
    if _R3_STAR["day"] == day and _R3_STAR["set"]:
        return _R3_STAR["set"]
    mkt, price = _R3_SHARES.get("mkt") or {}, {}
    for url in ("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL",):
        name = url.rsplit("/", 1)[-1]
        try:
            rows = _r3_json(url)
            n = 0
            for r in rows if isinstance(rows, list) else []:
                k = ({str(a).strip(): v for a, v in r.items()}
                     if isinstance(r, dict) else {})
                code = str(k.get("Code") or k.get("SecuritiesCompanyCode") or "").strip()
                try:
                    p = float(Decimal(str(k.get("ClosingPrice", k.get("Close", ""))).replace(",", "").strip()))
                except (InvalidOperation, ValueError):
                    continue
                if code and p > 0:
                    price[code] = p
                    n += 1
            print(f"[INSTI_R3_PRICE] src={name} n={n}", flush=True)
        except Exception as exc:
            print(f"[INSTI_R3_PRICE_ERR] src={name} {type(exc).__name__}: "
                  f"{str(exc)[:100]}", flush=True)
    caps = {}
    for code, sh in shares.items():
        if code in price and mkt.get(code) == "上市":
            caps.setdefault(mkt[code], []).append((sh * price[code], code))
    top = {m: [c for _, c in sorted(v, reverse=True)[:50]] for m, v in caps.items()}
    stars = set(top.get("上市", []))
    print(f"[INSTI_R3_STAR] 上市={len(stars)} 前5={top.get('上市', [])[:5]}", flush=True)
    if len(stars) == 50:
        _R3_STAR.update(day=day, set=stars, top=top)
    return stars


def _r3_day_rows(day, deadline):
    """單一過去交易日上市＋上櫃 {代號:(外資,投信)}；沿用附件官方抓取與日期核對。休市回 None。"""
    if day in _R3_DAYS:
        return _R3_DAYS[day]
    evidence = []
    token = _CONTEXT.set((deadline, day, evidence))
    try:
        tw, _ = original.fetch_twse(day)
        tp, _ = original.fetch_tpex(day) if tw is not None else (None, None)
        if tw is None or tp is None:
            data = None
        elif not tw or not tp or len(evidence) < 2:
            raise SourceError("上市上櫃資料或日期核對不完整")
        else:
            data = {str(r[1]).strip(): (r[3], r[4]) for r in tw + tp}
    finally:
        _CONTEXT.reset(token)
    _R3_DAYS[day] = data
    for old in sorted(_R3_DAYS)[:-10]:
        _R3_DAYS.pop(old, None)
    return data


def _r3_history(snapshot, budget=25):
    """當日（snapshot）＋往前補到共5個交易日；回傳 [(日期, {代號:(外資,投信)})]，新到舊。"""
    deadline = time.monotonic() + budget
    hist = [(snapshot.day, {r[1]: (r[3], r[4]) for r in snapshot.buy + snapshot.sell})]
    if not _R3_LOCK.acquire(timeout=budget):
        return hist
    try:
        cur = snapshot.day
        while len(hist) < 5 and time.monotonic() < deadline - 1:
            prev = _R3_PREV.get(cur)
            if prev is None:
                d = cur
                for _ in range(10):
                    d -= dt.timedelta(days=1)
                    if d.weekday() < 5 and _r3_day_rows(d, deadline) is not None:
                        prev = d
                        break
                if prev is None:
                    break
                _R3_PREV[cur] = prev
            rows = _r3_day_rows(prev, deadline)
            if rows is None:
                break
            hist.append((prev, rows))
            cur = prev
    except Exception as exc:
        print(f"[INSTI_R3_HIST_ERR] {type(exc).__name__}: {str(exc)[:120]} "
              f"days={len(hist)}", flush=True)
    finally:
        _R3_LOCK.release()
    return hist


def _r3_pct(v):
    """小於 0.0005% 的非零值不顯示成 ±0.000%（避免看似為 0）。"""
    if not v:
        return "0.000%"
    if abs(v) < 0.0005:
        return ("+" if v > 0 else "-") + "<0.001%"
    return f"{v:+.3f}%"


def _r3_lines(code, hist, issued):
    """回傳 [(純文字, [(片段, 方向)])]；每個數值依自身正負上色：1紅 -1綠 0黃 None灰 L中性。"""
    if not issued:
        fail = _R3_SHARES.get("fail") or set()
        t = ("外本比／投本比：資料不足（官方無發行股數，如ETF）" if not fail else
             f"外本比／投本比：資料不足（{'、'.join(sorted(fail))}官方發行股數來源暫缺，或為ETF）")
        return [(t, [(t, None)])]
    n = len(hist)
    out = []
    for label, i in (("外本比", 0), ("投本比", 1)):
        nets = [((rows or {}).get(code) or (0, 0))[i] for _, rows in hist]
        cum = sum(nets)
        s = (nets[0] > 0) - (nets[0] < 0)
        k = 0
        for v in nets:
            if s and (v > 0) - (v < 0) == s:
                k += 1
            else:
                break
        if n < 2:
            trend = ""
        elif not s:
            trend = "當日未進出"
        elif k == 1:
            trend = "轉買" if s > 0 else "轉賣"
        else:
            trend = f"連{'買' if s > 0 else '賣'}{k}日" + ("+" if k == n else "")
        parts = [(f"{label} ", "L"), (_r3_pct(nets[0] * 100 / issued), s),
                 (f"｜{n}日 ", "L"), (_r3_pct(cum * 100 / issued), (cum > 0) - (cum < 0))]
        if trend:
            parts += [("｜", "L"), (trend, s)]
        out.append(("".join(x for x, _ in parts), parts))
    return out


def _r3_inject(snapshot, out):
    t0 = time.monotonic()
    hist = _r3_history(snapshot)
    shares = _r3_shares()
    try:
        stars = _r3_star_set(shares)
    except Exception as exc:
        stars = set()
        print(f"[INSTI_R3_STAR_ERR] {type(exc).__name__}: {str(exc)[:120]}", flush=True)
    quotes = dict(snapshot.quotes)
    buy, sell = snapshot.buy[:REPORT_LIMIT], snapshot.sell[:REPORT_LIMIT]
    starts = {"三者同買": 0, "三者同賣": 0}
    miss, cards = [], 0
    for msg in out:
        if msg.get("type") != "flex":
            continue
        label = "三者同買" if "三者同買" in msg["altText"] else "三者同賣"
        rows = buy if label == "三者同買" else sell
        bubbles = msg["contents"]["contents"]
        added = []
        for bubble in bubbles:
            for card, row in zip(bubble["body"]["contents"],
                                 rows[starts[label]:starts[label] + 6]):
                quote = quotes.get((row[0], row[1]))
                pal = _R3_LIGHT if (quote and quote.highlight) else _R3_DARK
                title = card["contents"][0]
                if row[1] in stars and title.get("type") == "text":
                    keep = {k: title[k] for k in ("size", "weight") if k in title}
                    title["contents"] = [
                        dict(type="span", text=title.get("text", ""),
                             color=title.get("color", "#F5F1E8"), **keep),
                        dict(type="span", text=" ★",
                             color="#B8860B" if pal is _R3_LIGHT else "#FFD700", **keep)]
                issued = shares.get(row[1])
                if not issued:
                    miss.append(row[1])
                for _text, parts in _r3_lines(row[1], hist, issued):
                    spans = []
                    for piece, sign in parts:
                        if spans and spans[-1]["color"] == pal[sign]:
                            spans[-1]["text"] += piece
                        else:
                            spans.append({"type": "span", "text": piece, "color": pal[sign]})
                    el = {"type": "text", "size": "9px", "wrap": True, "contents": spans}
                    card["contents"].append(el)
                    added.append((card, el))
                cards += 1
            starts[label] += 6
        size = len(json.dumps(msg["contents"], ensure_ascii=False,
                              separators=(",", ":")).encode("utf-8"))
        big = max(len(json.dumps(b, ensure_ascii=False).encode("utf-8"))
                  for b in bubbles)
        if size > 50000 or big > 29000:
            for card, el in added:
                card["contents"] = [x for x in card["contents"] if x is not el]
            print(f"[INSTI_R3_SIZE_DROP] {label} carousel={size} bubble={big}",
                  flush=True)
        else:
            print(f"[INSTI_R3_SIZE_OK] {label} carousel={size} bubble={big}",
                  flush=True)
    days = [d for d, _ in hist]
    note = (f"\n外本比／投本比＝外資／投信買賣超÷發行股數×100%"
            f"\n格式：當日｜近{len(days)}日累計｜趨勢（連買/連賣N日、轉買/轉賣）"
            f"\n累計區間：{days[-1]:%m/%d}～{days[0]:%m/%d}；數值與趨勢字色：紅正/買・綠負/賣・黃0・灰缺")
    note += ("\n★權值股＝上市市值前50（發行股數×最近收盤價）" if len(stars) == 50
             else f"\n★權值股：上市收盤價暫缺（{len(stars)}/50），本次僅標已取得者")
    if miss:
        fl = _R3_SHARES.get("fail") or set()
        note += ((f"\n{'、'.join(sorted(fl))}官方發行股數來源暫缺，{len(miss)} 檔標資料不足："
                  if fl else f"\n無官方發行股數 {len(miss)} 檔（如ETF，標資料不足）：")
                 + "、".join(miss[:10]) + ("…" if len(miss) > 10 else ""))
    if out and out[0].get("type") == "text":
        key = "\n籌碼紀錄不代表未來漲跌"
        t = out[0]["text"]
        out[0]["text"] = t.replace(key, note + key, 1) if key in t else t + note
    print(f"[INSTI_R3_OK] days={[str(d) for d in days]} shares={len(shares)} "
          f"cards={cards} miss={len(miss)} ms={int((time.monotonic() - t0) * 1000)}",
          flush=True)


_r3_base_build = build_messages


def build_messages(snapshot, now=None):
    """INSTI_R3：原卡片逐字不變，僅於每檔卡片尾端追加外本比／投本比兩列；失敗只記錄、原卡照送。"""
    out = _r3_base_build(snapshot, now)
    try:
        _r3_inject(snapshot, out)
    except Exception as exc:
        print(f"[INSTI_R3_ERR] {type(exc).__name__}: {str(exc)[:160]}", flush=True)
    return out

'''

PROBE = r'''
import datetime as dt, json, sys
import insti_query_r1 as q
now = dt.datetime.now(q.TAIPEI)
snap = q.get_snapshot(now)
base = json.dumps(q._r3_base_build(snap, now), ensure_ascii=False, sort_keys=True)
out = q.build_messages(snap, now)
def strip(o):
    o = json.loads(json.dumps(o, ensure_ascii=False))
    for m in o[1:]:
        for b in m["contents"]["contents"]:
            for c in b["body"]["contents"]:
                if (c["contents"][0].get("contents") or [{}])[-1].get("text") == " ★":
                    c["contents"][0].pop("contents")
                c["contents"] = [x for x in c["contents"] if not (x.get("type") == "text" and str(x.get("text") or (x.get("contents") or [{}])[0].get("text", "")).startswith(("外本比", "投本比")))]
    o[0]["text"] = o[0]["text"].split("\n外本比／投本比＝")[0] + ("\n籌碼紀錄不代表未來漲跌，投資請審慎評估。" if "\n籌碼紀錄不代表" in o[0]["text"] else "")
    return o
s = strip(out)
same = json.dumps(s, ensure_ascii=False, sort_keys=True) == base
sh = q._R3_SHARES["data"]
rows = list(snap.buy[:30]) + list(snap.sell[:30])
mx = {}
for r in rows:
    if r[1] in sh:
        mx.setdefault(r[0], []).append((round(r[3] * 100 / sh[r[1]], 3), r[1], r[2]))
mx = {k: sorted(v, key=lambda x: -abs(x[0]))[:3] for k, v in mx.items()}
print("ORIGINAL_UNCHANGED", same)
print("CARD_LAYOUT", out[1]["contents"]["contents"][0]["body"]["contents"][0].get("layout"))
print("SHARES_SAMPLE", {c: sh.get(c) for c in ("2330", "2317", "6488", "8299", "3105")})
print("TOP3_ABS_FOREIGN_DAY_RATIO_BY_MARKET", mx)
hist = q._r3_history(snap)
print("HIST_DAYS", [str(d) for d, _ in hist])
print("STAR_TOP", q._R3_STAR.get("top"))
print("STAR_ON_CARDS", sorted(r[1] for r in list(snap.buy[:30]) + list(snap.sell[:30]) if r[1] in q._R3_STAR.get("set", set())))
for r in [x for x in snap.buy[:3]] + [x for x in snap.sell[:3]]:
    print("ROW", r[0], r[1], r[2], "外", int(r[3] / 1000), "投", int(r[4] / 1000), "發行股", sh.get(r[1]), [x for x, _ in q._r3_lines(r[1], hist, sh.get(r[1]))])
print("SUMMARY_TEXT_BEGIN"); print(out[0]["text"]); print("SUMMARY_TEXT_END")
open(__import__("os").path.expanduser("~/insti_r3_dry.json"), "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
'''


def sha(b):
    return hashlib.sha256(b).hexdigest()


def need(cond, msg):
    if not cond:
        print(f"[R3_STOP] {msg}")
        sys.exit(1)


def main():
    a = sys.argv[1:]
    src = os.path.expanduser(a[a.index("--src") + 1] if "--src" in a else "~/vip1688_r13b_20261012_024917/source")
    app, ins = os.path.join(src, "app.py"), os.path.join(src, "insti_query_r1.py")
    app_sha = a[a.index("--app-sha") + 1] if "--app-sha" in a else APP_SHA
    if "--no-net" not in a:
        need(sha(open(app, "rb").read()) == app_sha, "app.py SHA 不符（正式版已變更）")
    t = open(ins, "rb").read()
    need(sha(t) == SRC_SHA, "insti_query_r1.py SHA 不符")
    t = t.decode("utf-8")
    need(t.count(ANCHOR) == 1 and "INSTI_R3" not in t, "錨點不唯一或已套用")
    new = t.replace(ANCHOR, INJECT + ANCHOR, 1)
    compile(new, "insti_query_r1.py", "exec")
    cand = os.path.expanduser(f"~/insti_r3_{time.strftime('%Y%m%d_%H%M%S')}/source") if "--no-net" not in a else src + "_r3"
    if "--cand" in a:
        cand = a[a.index("--cand") + 1]
        need(not os.path.exists(cand), "候選目錄已存在")
    os.makedirs(os.path.dirname(cand), exist_ok=True)
    subprocess.run(["cp", "-al", src, cand], check=True)
    tmp = os.path.join(cand, ".insti_r3.tmp")
    open(tmp, "w", encoding="utf-8").write(new)
    os.replace(tmp, os.path.join(cand, "insti_query_r1.py"))
    ci = os.path.join(cand, "insti_query_r1.py")
    need(os.stat(ci).st_nlink == 1, "候選檔仍是硬連結")
    need(sha(open(ins, "rb").read()) == SRC_SHA, "基底被改動")
    print(f"[R3_PATCHED] candidate={cand} insti_sha={sha(open(ci, 'rb').read())} "
          f"+lines={new.count(chr(10)) - t.count(chr(10))}")
    if "--no-net" in a:
        return
    r = subprocess.run([sys.executable, "-B", "-c", PROBE], cwd=cand, capture_output=True, text=True, timeout=300)
    print(r.stdout[-6000:])
    print(r.stderr[-3000:])
    print(f"[R3_DRY] exit={r.returncode} json=~/insti_r3_dry.json")


if __name__ == "__main__":
    main()
