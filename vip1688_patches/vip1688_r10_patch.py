"""VIP1688 R10: REPORT_8888 only, on top of R9. 72h news items show the title and open the original article on tap
(Google News RSS <link>); official material info has no URL in the source data and stays plain text; size guard keeps
the carousel under 44KB. No deploy, no LINE, no AI."""
import datetime, difflib, email.utils, glob, hashlib, json, os, subprocess, sys, traceback, types

HOME = os.path.expanduser("~")
SRC_SHA = "f54f535ff52ff102e5f1c42fe63d70286bb838d9fa1c2d5335e5532d5d6439d5"
HELPER = 'def _vip1688_r10_news_item(x):\n    """VIP1688_R10: news title; tap opens the original article (http/https only, LINE uri limit 1000)."""\n    t, lk = (tuple(x) + ("",))[:2] if isinstance(x, (list, tuple)) else (x, "")\n    t, lk = str(t)[:90], str(lk or "")\n    if lk.startswith(("https://", "http://")) and len(lk) <= 1000:\n        return _vip1688_r8_txt("🔗 " + t, "xs", "#1E6FD9", margin="sm", decoration="underline",\n                               action={"type": "uri", "label": "開啟原文", "uri": lk})\n    return _vip1688_r8_txt(t, "xs", "#555555", margin="sm")\n\n\ndef _vip1688_r10_fit(b, limit=44000):\n    """VIP1688_R10: keep the carousel under the size cap by dropping the last linked news of the fullest stock card."""\n    import json as _j\n    n = 0\n    while len(_j.dumps({"type": "carousel", "contents": b}, ensure_ascii=False).encode("utf-8")) > limit:\n        best = None\n        for bub in b[1:6]:\n            body = (bub.get("body") or {}).get("contents") or []\n            k = sum(1 for c in body if isinstance(c, dict) and "action" in c)\n            if k > 1 and (best is None or k > best[0]):\n                best = (k, body)\n        if best is None:\n            break\n        body = best[1]\n        body.pop(max(i for i, c in enumerate(body) if isinstance(c, dict) and "action" in c))\n        n += 1\n    if n:\n        print(f"[VIP1688_R10_FIT] dropped={n}", flush=True)\n\n\n'
ANCHOR = "def _vip1688_r7_stock_line("
EDITS = [
    ("anchor", ANCHOR, HELPER + ANCHOR),
    ("gnews_link",
     '            out.append((dt, _h.unescape(_re.sub(r"<!\\[CDATA\\[|\\]\\]>", "", ti.group(1))).strip()))\n',
     '            lk = _re.search(r"<link>(.*?)</link>", it, _re.S)  # VIP1688_R10\n'
     '            out.append((dt, _h.unescape(_re.sub(r"<!\\[CDATA\\[|\\]\\]>", "", ti.group(1))).strip(),\n'
     '                        _h.unescape(lk.group(1).strip()) if lk else ""))\n'),
    ("news_loop", "        for dt, ti in sorted(got, key=lambda x: x[0], reverse=True):\n",
     "        for dt, ti, lk in sorted(got, key=lambda x: x[0], reverse=True):  # VIP1688_R10\n"),
    ("news_line", '                lines.append(f"📰 {dt.astimezone(tz):%m/%d} {ti}")\n',
     '                lines.append((f"📰 {dt.astimezone(tz):%m/%d} {ti}", lk))  # VIP1688_R10\n'),
    ("material_line", '            m = [f"📢 {d} {s}".replace("📢  ", "📢 ") for d, s in mat.get(code, [])]\n',
     '            m = [(f"📢 {d} {s}".replace("📢  ", "📢 "), "") for d, s in mat.get(code, [])]  # VIP1688_R10\n'),
    ("render", '            body.extend(_vip1688_r8_txt(x[:72], "xs", "#555555", margin="sm") for x in items)\n',
     "            body.extend(_vip1688_r10_news_item(x) for x in items)  # VIP1688_R10\n"),
    ("fit", '    carousel = {"type": "carousel", "contents": b}\n    size = len(_j.dumps(carousel',
     '    _vip1688_r10_fit(b)  # VIP1688_R10\n    carousel = {"type": "carousel", "contents": b}\n    size = len(_j.dumps(carousel'),
]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def need(cond, msg, **dbg):
    if not cond:
        raise RuntimeError(f"{msg} | debug={dbg}")


def find_src():
    hits = [d for d in sorted(glob.glob(os.path.join(HOME, "vip1688_r9_2026*", "source")))
            if os.path.isfile(os.path.join(d, "app.py")) and sha(open(os.path.join(d, "app.py"), "rb").read()) == SRC_SHA]
    need(hits, "R9 candidate with expected SHA not found", searched=glob.glob(os.path.join(HOME, "vip1688_r9_*")))
    return hits[-1]


def patch(t):
    need("_vip1688_r10_" not in t, "R10 already applied")
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
    exec(compile(t[s:e], "r10", "exec"), ns)
    J = lambda x: json.dumps(x, ensure_ascii=False)
    r = {}
    now = datetime.datetime.now(datetime.timezone.utc)
    L1 = "https://news.google.com/rss/articles/CBMiAAA?oc=5"
    rss = "".join(f"<item><title>{ti}</title><link>{lk}</link><pubDate>{email.utils.format_datetime(now - datetime.timedelta(hours=h))}</pubDate></item>"
                  for ti, lk, h in (("健策營收創高 - 經濟日報", L1, 5), ("健策舊聞 - 工商時報", "https://x/old", 80),
                                    ("健策法說 - 鉅亨網", "https://news.google.com/rss/articles/B?a=1&amp;b=2", 30)))
    fake = types.ModuleType("requests")
    fake.get = lambda url, timeout=8, headers=None: _Resp(rss.encode("utf-8"))
    ns["_vip1688_r9_json"] = lambda url, timeout=15: ([{"發言日期": "1151011", "公司代號": "6515", "主旨 ": "董事會決議"}]
                                                       if url.endswith("_L") else [])
    old_req = sys.modules.get("requests")
    sys.modules["requests"] = fake
    try:
        g = ns["_vip1688_r9_gnews"]("健策 3653", now)
        r["gnews_has_link"] = [(x[1], x[2]) for x in g] == [("健策營收創高 - 經濟日報", L1),
                                                            ("健策法說 - 鉅亨網", "https://news.google.com/rss/articles/B?a=1&b=2")]
        news = ns["_vip1688_r9_news"]([("3653", "健策"), ("6515", "穎崴")])
        r["news_tuples"] = news["3653"][0][1] == L1 and news["6515"][0] == ("📢 10/11 董事會決議", "")
    finally:
        if old_req is None:
            sys.modules.pop("requests", None)
        else:
            sys.modules["requests"] = old_req
    it = ns["_vip1688_r10_news_item"](("📰 10/12 健策營收創高 - 經濟日報", L1))
    r["item_tap_opens_article"] = it["action"] == {"type": "uri", "label": "開啟原文", "uri": L1} and it["text"].startswith("🔗 📰 10/12 健策")
    r["item_bad_link_plain"] = "action" not in ns["_vip1688_r10_news_item"](("x", "javascript:alert(1)")) \
        and "action" not in ns["_vip1688_r10_news_item"](("x", "https://a/" + "b" * 1000))
    r["item_material_plain"] = "action" not in ns["_vip1688_r10_news_item"](("📢 10/11 董事會決議", "")) \
        and ns["_vip1688_r10_news_item"]("舊格式")["text"] == "舊格式"
    mk = lambda n: {"name": n, "output_fields": {"price": {"value": "100"}, "change": {"value": "1"}}}
    res = [(c, mk(n)) for c, n in (("3653", "健策"), ("3661", "世芯"), ("6515", "穎崴"), ("3533", "嘉澤"), ("8996", "高力"))]
    longlink = "https://news.google.com/rss/articles/" + "C" * 900
    items = {c: [(f"📰 10/12 新聞{i} 標題標題標題標題標題標題標題標題標題標題", longlink) for i in range(3)] for c, _ in res}
    done = types.SimpleNamespace(result=lambda timeout=None: items)
    ns["_VIP1688_R8_TLS"].r9 = {"tx": None, "news": done}
    ai = "═══【第一章：DNA技術】═══\n" + "\n".join(f"{c}：" + "長" * 120 for c, _ in res) + "\n═══【第五章：台指聯動與策略】═══\n" + "策" * 400
    c, size = ns["_vip1688_r8_build"]([x[0] for x in res], res, [], [], [], {}, ai, "10/08", "")
    s1 = J(c["contents"][1])
    r["card_has_linked_news"] = '"uri": "https://news.google.com/rss/articles/' in s1 and "72小時新聞與重大訊息" in s1
    r["fit_under_cap"] = size <= 44000 and all(J(b).count('"action"') >= 1 for b in c["contents"][1:6])
    big = [{"type": "bubble"}] + [{"body": {"contents": [{"type": "text", "text": "x"}] + [ns["_vip1688_r10_news_item"]((f"t{i}", longlink))
                                                       for i in range(3)]}} for _ in range(5)] + [{"type": "bubble"}]
    ns["_vip1688_r10_fit"](big, limit=12000)
    left = [J(b).count('"action"') for b in big[1:6]]
    r["fit_trims_keeps_one"] = len(J({"type": "carousel", "contents": big}).encode("utf-8")) <= 12000 and min(left) >= 1 and sum(left) < 15
    ns["_VIP1688_R8_TLS"].r9 = {"tx": None, "news": types.SimpleNamespace(result=lambda timeout=None: {"3653": [("📰 a", L1)]})}
    c2, _ = ns["_vip1688_r8_build"](["3653"], res[:1], [], [], [], {}, "", "10/08", "")
    r["small_report_untouched"] = J(c2["contents"][1]).count('"action"') == 1
    return r


def main():
    out = {"status": "STOP", "revision": "VIP1688_R10", "deployed": False, "line_sent": False, "ai_called": False}
    dst = None
    try:
        src = find_src()
        app = os.path.join(src, "app.py")
        old = open(app, "rb").read().decode("utf-8")
        new = patch(old)
        compile(new, "app.py", "exec", dont_inherit=True)
        checks = behaviour(new)
        need(all(checks.values()), "behaviour check failed", checks=checks)
        diff = [l for l in difflib.unified_diff(old.splitlines(), new.splitlines(), "r9", "r10", n=0, lineterm="")
                if l[:1] in "+-" and l[:3] not in ("+++", "---")]
        removed = [l[1:] for l in diff if l.startswith("-")]
        need(len(removed) == 5, "unexpected removed line count", removed=removed[:8])
        dst = os.path.join(HOME, "vip1688_r10_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        os.mkdir(dst)
        subprocess.run(["cp", "-al", src, os.path.join(dst, "source")], check=True)
        target = os.path.join(dst, "source", "app.py")
        tmp = target + ".r10tmp"
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
    print("R10_RESULT " + json.dumps(out, ensure_ascii=False))
    return 0 if out["status"] == "candidate_ready" else 2


if __name__ == "__main__":
    sys.exit(main())
