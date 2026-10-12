"""VIP1688 R8d: REPORT_8888 only, on top of R8c. Remove duplicated content:
(1) every card note drops sentences whose figures are all already shown in that card's table;
(2) AI prompt forbids restating table figures, adds chapter 6 summary, sentence caps;
(3) overview keeps only conclusions (no per-stock % / leader rows duplicated by later cards) and shows the summary;
(4) dealer (自營) row removed (source has no such field). No deploy, no LINE, no AI."""
import datetime, difflib, glob, hashlib, json, os, subprocess, sys, traceback

HOME = os.path.expanduser("~")
SRC_SHA = "18d5f8aa3257763efef5a420f533f28808372bc376adc3d7a9a5232a7a6a946c"
DEDUPE = '''def _vip1688_r8d_dedupe(notes, shown):
    """VIP1688_R8D: drop note sentences whose figures (decimals or values with %/元/張) are all already shown."""
    import re as _re

    def _all(s):
        out = set()
        for m in _re.findall(r"\\d[\\d,]*(?:\\.\\d+)?", str(s)):
            try:
                out.add(round(float(m.replace(",", "")), 2))
            except ValueError:
                pass
        return out

    def _vals(s):
        out = set()
        for m in _re.finditer(r"(\\d[\\d,]*(?:\\.\\d+)?)\\s*([%元張]?)", str(s)):
            if "." in m.group(1) or m.group(2):
                out.add(round(float(m.group(1).replace(",", "")), 2))
        return out
    seen = set()
    for s in shown:
        seen |= _all(s)
    keep = []
    for part in _re.split(r"(?<=[。！？；\\n])", str(notes or "")):
        p = part.strip().lstrip("🤖").strip()
        if not p:
            continue
        v = _vals(p)
        if v and v <= seen:
            continue
        keep.append(p)
    return "\\n".join(keep)


'''
OVERVIEW_NEW = '''    if sell:
        rows1.append(_vip1688_r8_row("法人同賣第1", f"{sell[0].get('name', '')}({sell[0].get('code', '')})", _VIP1688_R8_DN))
    names = "、".join(_name(d) for _, d in pairs if isinstance(d, dict))
    rows1.append(_vip1688_r8_row("DNA 候選", names or "資料不足", "#222222" if names else _VIP1688_R8_NA))
    b = [_vip1688_r8_bubble("💎 發財1688精華報", f"資料日 {date_note} 收盤" + ("｜休市" if "休市" in str(period_note) else ""),
                            rows1, "📌 今日重點\\n" + (ch.get(6) or "資料不足") + "\\n👉 左右滑動看個股、權值、法人、美股")]
'''
PROMPT_NEW = (
    "        # VIP1688_R7B: data-only prompt (no web search, no invented numbers) / VIP1688_R8D: no restated figures\n"
    "        ai_prompt = (\n"
    "            \"執行【含金量最高發財1688精華報】交叉解讀，與6666產業分析完全不同。\\n\"\n"
    "            \"【鐵律】只能使用系統提供的數據；不得聯網、不得自行補數字或點位；輸出不得出現英文欄位名稱。\"\n"
    "            \"價格、漲跌幅、均線、KD、RSI、MACD、張數都已列在卡片表格，解讀時一律不得重述這些數字，\"\n"
    "            \"只寫判讀結論、原因、支持與反證、條件；沒有的數據寫『資料不足』，不得推測連買天數、勝率、買賣動機。\\n\"\n"
    "            \"【資料日】以系統提供的period為準；休市時註明為最近交易日收盤。\\n\\n\"\n"
    "            \"依序輸出六章，每句不超過40字：\\n\"\n"
    "            \"═══【第一章：DNA技術】═══ 逐檔各一行，行首寫股票代號與冒號（例：3653：），1～2句判讀與反證。\\n\"\n"
    "            \"═══【第二章：大盤解析】═══ 一行『大盤多空判斷：偏多/偏空/中性』，再寫最多2句原因。\\n\"\n"
    "            \"═══【第三章：法人籌碼】═══ 最多3句，說明法人同步買賣超的族群特徵。\\n\"\n"
    "            \"═══【第四章：美股7巨頭】═══ 最多2句，說明對台股的可能影響，不得寫成勝率。\\n\"\n"
    "            \"═══【第五章：台指聯動與策略】═══ 最多3句條件式策略與失效條件；無期貨數據須註明『期貨資料不足』。\\n\"\n"
    "            \"═══【第六章：總結】═══ 3句今日重點結論。\"\n"
    "        )\n"
)
EDITS = [
    ("dealer_row", '(("外資", "foreign_buy"), ("投信", "trust_buy"), ("自營", "dealer_buy"))',
     '(("外資", "foreign_buy"), ("投信", "trust_buy"))'),
    ("note_dedupe", "    if notes:\n        body.append({\"type\": \"separator\", \"margin\": \"md\"})",
     "    notes = _vip1688_r8d_dedupe(notes, [title, subtitle] + [__import__(\"json\").dumps(r, ensure_ascii=False) for r in body])  # VIP1688_R8D\n"
     "    if notes:\n        body.append({\"type\": \"separator\", \"margin\": \"md\"})"),
    ("chapters_re", 'r"第([一二三四五])章"', 'r"第([一二三四五六])章"'),
    ("chapters_idx", '"一二三四五".index(m.group(1))', '"一二三四五六".index(m.group(1))'),
]
OV_START = "    if tw_has:\n        hi = max(tw_has"
OV_END = 'rows1, "👉 左右滑動：DNA 個股 ×5｜權值｜法人｜美股與策略")]\n'
P_START = "        # VIP1688_R7B: data-only prompt"
P_END = "        # 8888精華報使用"
ANCHOR = "def _vip1688_r7_stock_line("


def sha(b):
    return hashlib.sha256(b).hexdigest()


def need(cond, msg, **dbg):
    if not cond:
        raise RuntimeError(f"{msg} | debug={dbg}")


def find_src():
    hits = [d for d in sorted(glob.glob(os.path.join(HOME, "vip1688_r8c_*", "source")))
            if os.path.isfile(os.path.join(d, "app.py")) and sha(open(os.path.join(d, "app.py"), "rb").read()) == SRC_SHA]
    need(hits, "R8c candidate with expected SHA not found", searched=glob.glob(os.path.join(HOME, "vip1688_r8c_*")))
    return hits[-1]


def patch(t):
    need("_vip1688_r8d_" not in t, "R8d already applied")
    for name, old, new in EDITS:
        need(t.count(old) == 1, f"{name} count != 1", count=t.count(old))
        t = t.replace(old, new)
    for name, s in (("ov_start", OV_START), ("ov_end", OV_END), ("p_start", P_START), ("anchor", ANCHOR)):
        need(t.count(s) == 1, f"{name} count != 1", count=t.count(s))
    a, z = t.index(OV_START), t.index(OV_END) + len(OV_END)
    need(0 < z - a < 3000, "overview region invalid", dist=z - a)
    t = t[:a] + OVERVIEW_NEW + t[z:]
    a = t.index(P_START)
    z = t.find(P_END, a)
    need(0 < z - a < 4000, "prompt region invalid", dist=z - a)
    t = t[:a] + PROMPT_NEW + t[z:]
    return t.replace(ANCHOR, DEDUPE + ANCHOR)


def behaviour(t):
    s = t.index("import threading as _vip1688_r8_threading")
    e = t.index("def _vip1688_r7_stock_line(")
    ns = {"FlexSendMessage": lambda **k: k}
    exec(compile(t[s:e], "r8d", "exec"), ns)
    J = lambda x: json.dumps(x, ensure_ascii=False)
    r = {}
    dd = ns["_vip1688_r8d_dedupe"]
    shown = ['收 7,165  ▲360（+5.29%）', '{"text": "7011.0"}', '{"text": "82.47 / 81.73"}', '{"text": "+247張"}']
    out = dd("🤖 3653：股價7165.0元站於MA5值7011.0元之上。KD 82.47 偏高。乖離率14.51%過熱為反證。外資買超247張支撐。", shown)
    r["dup_sentences_dropped"] = "7011.0" not in out and "82.47" not in out and "247張" not in out
    r["new_figure_kept"] = "14.51%" in out
    r["no_number_sentence_kept"] = dd("短線動能延續。3653：站穩支撐。", shown) == "短線動能延續。\n3653：站穩支撐。"
    r["code_only_not_dropped"] = "3653" in dd("3653：多頭排列。", ["3653 健策"])
    r["all_dup_gives_empty"] = dd("🤖 台積電下跌1.35%。", ['{"text": "-1.35%"}']) == ""
    mk = lambda n, p, c: {"name": n, "output_fields": {"price": {"value": p}, "change": {"value": c}, "volume": {"value": "1,629張"},
                                                        "MA5": {"value": "7011.0"}, "foreign_buy": {"value": "+247張"},
                                                        "dealer_buy": {"value": "+9張"}}}
    res = [("x", mk("健策", "7165", "360")), ("x", mk("穎崴", "5615", "-95")), (None, None)]
    tw = [{"code": "2330", "name": "台積電", "pct": -1.35}, {"code": "1301", "name": "台塑", "pct": 7.82}]
    buy = [{"code": "2408", "name": "南亞科", "net": 9000000, "pct": 2.1, "day": "2026-10-08"}]
    sell = [{"code": "2303", "name": "聯電", "net": -5000000, "pct": -0.67, "day": "2026-10-08"}]
    ai = ("═══【第一章：DNA技術】═══\n3653：股價7165.0元站上MA5值7011.0元。乖離14.51%偏熱。\n"
          "═══【第二章：大盤解析】═══\n大盤多空判斷：偏空\n台積電下跌1.35%、台塑上漲7.82%。電子權值承壓。\n"
          "═══【第六章：總結】═══\n權值偏空、個股分化。\n法人集中記憶體。\n逢高不追。")
    c, size = ns["_vip1688_r8_build"](["3653", "6515", "3533"], res, tw, buy, sell, {}, ai, "10/08", "休市")
    ov, s1, tw_card = J(c["contents"][0]), J(c["contents"][1]), J(c["contents"][-3])
    r["overview_no_pct_dup"] = "+5.29%" not in ov and "權值領漲" not in ov and "-1.35%" not in ov
    r["overview_has_summary"] = "📌 今日重點" in ov and "法人集中記憶體" in ov and "健策、穎崴" in ov
    r["overview_insti_both"] = "南亞科(2408)" in ov and "聯電(2303)" in ov
    r["dealer_row_removed"] = "自營" not in s1 and "+9張" not in s1
    r["stock_note_dedup"] = "7011.0元" not in s1 and "14.51%" in s1
    r["tw_note_dedup"] = "下跌1.35%" not in tw_card and "電子權值承壓" in tw_card
    r["size_ok"] = size < 45000 and '"text": ""' not in J(c)
    i = t.index(P_START)
    p = t[i:t.index(P_END, i)]
    r["prompt_rules"] = "不得重述這些數字" in p and "第六章：總結" in p and "dna_stocks" not in p
    return r


def main():
    out = {"status": "STOP", "revision": "VIP1688_R8D", "deployed": False, "line_sent": False, "ai_called": False}
    dst = None
    try:
        src = find_src()
        app = os.path.join(src, "app.py")
        old = open(app, "rb").read().decode("utf-8")
        new = patch(old)
        compile(new, "app.py", "exec", dont_inherit=True)
        checks = behaviour(new)
        need(all(checks.values()), "behaviour check failed", checks=checks)
        diff = [l for l in difflib.unified_diff(old.splitlines(), new.splitlines(), "r8c", "r8d", n=0, lineterm="")
                if l[:1] in "+-" and l[:3] not in ("+++", "---")]
        removed = [l[1:] for l in diff if l.startswith("-")]
        dst = os.path.join(HOME, "vip1688_r8d_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        os.mkdir(dst)
        subprocess.run(["cp", "-al", src, os.path.join(dst, "source")], check=True)
        target = os.path.join(dst, "source", "app.py")
        tmp = target + ".r8dtmp"
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
    print("R8D_RESULT " + json.dumps(out, ensure_ascii=False))
    return 0 if out["status"] == "candidate_ready" else 2


if __name__ == "__main__":
    sys.exit(main())
