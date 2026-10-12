"""VIP1688 R7: REPORT_8888 only. (a) DNA block = one clean line per stock. (b) AI: no web search (the search call
timed out 70+80+90s in every run), data-only prompt, no invented numbers.
Base = R6 candidate. Builds an isolated candidate (hardlink tree + new app.py). No deploy, no LINE, no AI."""
import ast, datetime, difflib, hashlib, json, os, subprocess, sys, traceback

HOME = os.path.expanduser("~")
SRC = os.path.join(HOME, "vip1688_r6_20261011_132148", "source")
SRC_SHA = "dc17af5f237ac634a7c87b9c0c4aa2e890d907a6c4eba8aa87dfed09fd797b76"
I8, I12, I16 = " " * 8, " " * 12, " " * 16
OLD = (
    I8 + "for idx, (py_s, d) in enumerate(_8888_results):\n"
    + I12 + "if py_s:\n"
    + I16 + "py_s_compact = _strip_stock_5field_summary_block(py_s)\n"
    + I16 + "_brief = _build_stock_5field_brief_block(d, title='', banner=(\"🧾 候選摘要\" if idx == 0 else ''), mode='brief') if isinstance(d, dict) else ''\n"
    + I16 + "_dna_block = (_brief + \"\\n\" + str(py_s_compact)).strip() if _brief else py_s_compact\n"
    + I16 + "dna_blocks.append(_clean_report_display_text(_dna_block))\n"
    + I16 + "dna_json.append(d)\n"
)
NEW = (
    I8 + "for idx, (py_s, d) in enumerate(_8888_results):\n"
    + I12 + "# VIP1688_R7A: one line per stock; failed fetch is listed, never dropped silently\n"
    + I12 + "dna_blocks.append(_vip1688_r7_stock_line(dna_symbols[idx] if idx < len(dna_symbols) else '', d if py_s else None))\n"
    + I12 + "if py_s:\n"
    + I16 + "dna_json.append(d)\n"
)
ANCHOR = "def build_report1688_flex("
P_START = '        ai_prompt = (\n            "執行【含金量最高發財1688精華報】'
P_END = '            "嚴禁空洞！所有點位/數值必須來自聯網搜尋！"\n        )\n'
OLD_SEARCH = "            use_search=True,\n            model=MODEL_LITE,\n"
NEW_SEARCH = "            use_search=False,  # VIP1688_R7B: search call timed out 3/3 attempts (240s) in real runs\n            model=MODEL_LITE,\n"
NEW_PROMPT = (
    "        # VIP1688_R7B: data-only prompt (no web search, no invented numbers)\n"
    "        ai_prompt = (\n"
    "            \"執行【含金量最高發財1688精華報】交叉解讀，與6666產業分析完全不同，嚴禁重複。\\n\"\n"
    "            \"【鐵律】只能使用系統提供的JSON數據；不得聯網、不得自行補數字或點位；\"\n"
    "            \"JSON沒有的數據一律寫『資料不足』，不得推測連買天數、勝率、買賣動機。\\n\"\n"
    "            \"【資料日】以JSON的period為準；休市時須註明為最近交易日收盤數據。\\n\\n\"\n"
    "            \"依序輸出五章，每章最多6行，同一數值全文只出現一次：\\n\"\n"
    "            \"═══【第一章：DNA技術】═══ 逐檔一句技術判讀（只用dna_stocks欄位），附支持與反證。\\n\"\n"
    "            \"═══【第二章：大盤解析】═══ 依tw_top10漲跌家數判斷，必須寫出一行『大盤多空判斷：偏多/偏空/中性』。\\n\"\n"
    "            \"═══【第三章：法人籌碼】═══ 只依inst_buy_top5/inst_sell_top5；無資料寫『資料不足』。\\n\"\n"
    "            \"═══【第四章：美股7巨頭】═══ 只依us_giants漲跌，說明對台股的可能影響，不得寫成勝率。\\n\"\n"
    "            \"═══【第五章：台指聯動與策略】═══ 只依前四章數據給條件式策略與失效條件；無期貨數據須註明『期貨資料不足』。\"\n"
    "        )\n"
)
HELPER = '''def _vip1688_r7_stock_line(sid, d):
    """VIP1688_R7A: 1688 DNA candidate one-liner. Reads original output_fields only; no recompute, no fill."""
    sid = str(sid or "").strip()
    if not isinstance(d, dict):
        return f"{sid}｜資料取得失敗（本檔未列入解讀）"
    fields = d.get("output_fields") if isinstance(d.get("output_fields"), dict) else {}

    def _val(key):
        meta = fields.get(key) if isinstance(fields.get(key), dict) else {}
        s = str(meta.get("value", "") or "").strip()
        return "" if s in ("N/A", "--", "None") else s

    def _num(s):
        try:
            x = float(str(s).replace(",", "").replace("+", "").replace("張", "").strip())
            return x if x == x else None
        except Exception:
            return None

    def _fmt(x):
        return f"{x:,.2f}".rstrip("0").rstrip(".")

    head = f"{sid} {str(d.get('name') or '').strip()}".strip()
    p, c, vol = _num(_val("price")), _num(_val("change")), _val("volume")
    if p is None:
        return f"{head}｜收盤資料不足"
    parts = [head, f"收 {_fmt(p)}"]
    if c is not None:
        if c == 0:
            parts.append("平盤")
        else:
            base = p - c
            pct = f"（{c / base * 100:+.2f}%）" if base > 0 else ""
            parts.append(("▲" if c > 0 else "▼") + _fmt(abs(c)) + pct)
    if vol:
        parts.append(f"量 {vol}")
    return "｜".join(parts)


'''


def sha(b):
    return hashlib.sha256(b).hexdigest()


def need(cond, msg, **dbg):
    if not cond:
        raise RuntimeError(f"{msg} | debug={dbg}")


def lines_of(text, needle):
    return [i + 1 for i, l in enumerate(text.splitlines()) if needle in l][:10]


def patch(text):
    need(text.count(OLD) == 1, "DNA loop target count != 1", count=text.count(OLD),
         loop_lines=lines_of(text, "for idx, (py_s, d) in enumerate(_8888_results):"))
    need(text.count(ANCHOR) == 1, "anchor count != 1", lines=lines_of(text, ANCHOR))
    need("_vip1688_r7_stock_line" not in text, "R7a already applied")
    text = text.replace(OLD, NEW)
    text = text.replace(ANCHOR, HELPER + ANCHOR)
    # anchor on the unique 1688 prompt (the elif line itself appears in 3 places)
    need(text.count(P_START) == 1, "1688 prompt start count != 1", count=text.count(P_START))
    ps = text.index(P_START)
    pe = text.find(P_END, ps)
    need(0 < pe - ps < 8000, "1688 prompt end not found near start", dist=pe - ps)
    pe += len(P_END)
    call = text[pe:pe + 1500]
    need(call.count(OLD_SEARCH) == 1, "use_search target near prompt count != 1", count=call.count(OLD_SEARCH))
    call = call.replace(OLD_SEARCH, NEW_SEARCH)
    return text[:ps] + NEW_PROMPT + call + text[pe + 1500:]


def behaviour(text):
    tree = ast.parse(text)
    hits = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_vip1688_r7_stock_line"]
    need(len(hits) == 1, "helper not module-level exactly once", count=len(hits))
    ns = {}
    exec(compile(ast.Module(body=hits, type_ignores=[]), "r7a", "exec"), ns)
    f = ns["_vip1688_r7_stock_line"]
    mk = lambda p, c, v, n="健策": {"name": n, "output_fields": {"price": {"value": p}, "change": {"value": c}, "volume": {"value": v}}}
    cases = {
        "up": (f("3653", mk("7165.0", "360.0", "1,629張")), "3653 健策｜收 7,165｜▲360（+5.29%）｜量 1,629張"),
        "down": (f("6515", mk("5615.0", "-95.0", "1,100張", "穎崴")), "6515 穎崴｜收 5,615｜▼95（-1.66%）｜量 1,100張"),
        "flat": (f("2330", mk("1000", "0", "")), "2330 健策｜收 1,000｜平盤"),
        "no_price": (f("1234", mk("N/A", "", "")), "1234 健策｜收盤資料不足"),
        "fetch_fail": (f("8996", None), "8996｜資料取得失敗（本檔未列入解讀）"),
        "nan": (f("1111", mk("nan", "1", "")), "1111 健策｜收盤資料不足"),
        "bad_type": (f("2222", {"name": "X", "output_fields": "bad"}), "2222 X｜收盤資料不足"),
    }
    res = {k: got == want for k, (got, want) in cases.items()}
    i = text.index("        # VIP1688_R7B: data-only prompt")
    j = text.find("        # 8888精華報使用", i)
    pblock = text[i:j] if 0 < j - i < 4000 else ""
    call = text[j:j + 600] if pblock else ""
    res["r7b_no_search_flag"] = "use_search=True" not in call and call.count("use_search=False") == 1
    res["r7b_prompt_has_no_web"] = bool(pblock) and "聯網搜尋" not in pblock and "搜尋『" not in pblock
    res["r7b_dashboard_hook_kept"] = "大盤多空判斷：" in pblock
    res["_got"] = {k: got for k, (got, want) in cases.items() if got != want}
    return res


def main():
    out = {"status": "STOP", "revision": "VIP1688_R7", "deployed": False, "line_sent": False, "ai_called": False}
    dst = None
    try:
        app = os.path.join(SRC, "app.py")
        raw = open(app, "rb").read()
        need(sha(raw) == SRC_SHA, "source app SHA mismatch", got=sha(raw))
        old = raw.decode("utf-8")
        new = patch(old)
        compile(new, "app.py", "exec", dont_inherit=True)
        checks = behaviour(new)
        need(all(v for k, v in checks.items() if k != "_got"), "behaviour check failed", checks=checks)
        diff = [l for l in difflib.unified_diff(old.splitlines(), new.splitlines(), "r6", "r7", n=0, lineterm="")
                if l[:1] in "+-" and l[:3] not in ("+++", "---")]
        removed = [l[1:] for l in diff if l.startswith("-")]
        allowed = set(OLD.split("\n")) | set(OLD_SEARCH.split("\n")) | {"            use_search=True,"}
        p_old = old[old.index(P_START):old.index(P_END) + len(P_END)]
        allowed |= set(p_old.split("\n"))
        need(removed and all(l in allowed for l in removed), "unexpected removed lines",
             removed=[l for l in removed if l not in allowed][:5])
        dst = os.path.join(HOME, "vip1688_r7_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        os.mkdir(dst)
        subprocess.run(["cp", "-al", SRC, os.path.join(dst, "source")], check=True)
        target = os.path.join(dst, "source", "app.py")
        tmp = target + ".r7tmp"
        with open(tmp, "wb") as fh:
            fh.write(new.encode("utf-8"))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
        nb = open(target, "rb").read()
        need(nb == new.encode("utf-8"), "written app mismatch")
        need(sha(open(app, "rb").read()) == SRC_SHA, "SOURCE CHANGED - stop")
        need(os.stat(target).st_nlink == 1, "candidate app still hardlinked", nlink=os.stat(target).st_nlink)
        out.update(status="candidate_ready", candidate=os.path.join(dst, "source"), src_sha_unchanged=True,
                   new_app_sha=sha(nb), checks={k: v for k, v in checks.items() if k != "_got"},
                   removed_lines=len(removed), added_lines=len(diff) - len(removed))
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
        out["traceback"] = traceback.format_exc()[-1500:]
        out["partial_candidate"] = dst
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if out["status"] == "candidate_ready" else 2


if __name__ == "__main__":
    sys.exit(main())
