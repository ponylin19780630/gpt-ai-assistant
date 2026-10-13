"""VIP1688 R9 read-only probe: existing news/futures code in app.py + live official endpoints. No deploy, no LINE, no writes except the report."""
import glob, json, os, re, time, urllib.request

HOME = os.path.expanduser("~")
OUT = os.path.join(HOME, "vip1688_r9_probe.txt")
L = []
P = L.append
MASK = [(re.compile(r"(['\"])[A-Za-z0-9_\-+=]{20,}\1"), r"\1<MASK>\1"),
        (re.compile(r"(?i)((?:key|token|secret|password|apikey|api_key)\s*[=:]\s*)[^&'\"\s,)]+"), r"\1<MASK>")]


def m(s):
    for r, t in MASK:
        s = r.sub(t, s)
    return s[:220]


apps = sorted(glob.glob(os.path.join(HOME, "vip1688_r8d_*", "source", "app.py")))
app = apps[-1]
src = open(app, encoding="utf-8").read().splitlines()
P(f"### APP {app} lines={len(src)}")
NAME = re.compile(r"^\s*def\s+(\w*(?:news|cnyes|technews|rss|mops|announce|material|futures|taifex|txf|basis|mtx|spread|taiex)\w*)\s*\(", re.I)
defs = [(i, NAME.match(l).group(1)) for i, l in enumerate(src) if NAME.match(l)]
P(f"### DEFS {len(defs)}")
for i, n in defs:
    P(f"{i + 1}\t{m(src[i].strip())}")
DOM = re.compile(r"taifex\.com\.tw|cnyes\.com|technews|news\.google|mops\.twse|t187ap04|MI_INDEX|tpex\.org\.tw/(?:openapi|web)|FUTURES_CHIP")
hits = [i for i, l in enumerate(src) if DOM.search(l)]
P(f"### URL/MODE HITS {len(hits)} (first 150)")
for i in hits[:150]:
    P(f"{i + 1}\t{m(src[i].strip())}")
body = [(i, n) for i, n in defs if src[i].startswith("def ") and re.search(r"(?i)taifex|futures|txf|news|mops|announce", n)]
P(f"### BODIES {len(body)} (first 14, 45 lines each)")
for i, n in body[:14]:
    P(f"##### {n} @ {i + 1}")
    for k in range(i, min(i + 45, len(src))):
        if k > i and src[k].startswith(("def ", "class ")):
            break
        P(f"{k + 1}\t{m(src[k])}")


def get(url, timeout=20):
    t = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json,text/xml,*/*"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            b = r.read()
            return r.status, r.headers.get("Content-Type", ""), b, int((time.time() - t) * 1000)
    except Exception as e:
        return f"ERR {type(e).__name__}: {str(e)[:120]}", "", b"", int((time.time() - t) * 1000)


def js(b):
    try:
        return json.loads(b.decode("utf-8-sig"))
    except Exception:
        return None


P("### LIVE PROBES")
for name, url in (("TWSE_SWAGGER", "https://openapi.twse.com.tw/v1/swagger.json"),
                  ("TPEX_SWAGGER", "https://www.tpex.org.tw/openapi/swagger.json"),
                  ("TAIFEX_SWAGGER", "https://openapi.taifex.com.tw/swagger.json")):
    st, ct, b, ms = get(url)
    d = js(b) or {}
    paths = list((d.get("paths") or {}).keys())
    pick = [p for p in paths if re.search(r"(?i)t187ap04|MI_INDEX|DailyMarketReport|Fut|news|重大", p)]
    P(f"{name} status={st} ms={ms} paths={len(paths)} pick={pick[:25]}")

for name, url in (("TAIFEX_FUT", "https://openapi.taifex.com.tw/v1/DailyMarketReportFut"),
                  ("TWSE_MI_INDEX", "https://openapi.twse.com.tw/v1/exchangeReport/MI_INDEX"),
                  ("TWSE_MATERIAL_L", "https://openapi.twse.com.tw/v1/opendata/t187ap04_L"),
                  ("CNYES_TW", "https://api.cnyes.com/media/api/v1/newslist/category/tw_stock?limit=3"),
                  ("GNEWS_2330", "https://news.google.com/rss/search?q=%E5%8F%B0%E7%A9%8D%E9%9B%BB+when:3d&hl=zh-TW&gl=TW&ceid=TW:zh-Hant")):
    st, ct, b, ms = get(url)
    P(f"{name} status={st} ms={ms} type={ct[:40]} bytes={len(b)}")
    d = js(b)
    if isinstance(d, list):
        P(f"  rows={len(d)} keys={list(d[0].keys()) if d and isinstance(d[0], dict) else None}")
        if name == "TAIFEX_FUT":
            for r in [r for r in d if str(r.get("Contract", "")).strip() == "TX"][:4]:
                P(f"  TX {json.dumps(r, ensure_ascii=False)[:400]}")
        elif name == "TWSE_MI_INDEX":
            for r in [r for r in d if "發行量加權" in json.dumps(r, ensure_ascii=False)][:2]:
                P(f"  IDX {json.dumps(r, ensure_ascii=False)[:300]}")
        else:
            for r in d[:2]:
                P(f"  ROW {json.dumps(r, ensure_ascii=False)[:400]}")
    elif isinstance(d, dict):
        P(f"  keys={list(d.keys())[:12]} sample={json.dumps(d, ensure_ascii=False)[:500]}")
    elif b:
        t = b.decode("utf-8", "replace")
        for it in re.findall(r"<item>.*?</item>", t, re.S)[:3]:
            ti = re.search(r"<title>(.*?)</title>", it, re.S)
            pd = re.search(r"<pubDate>(.*?)</pubDate>", it, re.S)
            P(f"  ITEM {(ti.group(1) if ti else '')[:120]} | {pd.group(1) if pd else ''}")
open(OUT, "w", encoding="utf-8").write("\n".join(L) + "\n")
print(f"R9_PROBE_DONE lines={len(L)} defs={len(defs)} hits={len(hits)} out={OUT}")
