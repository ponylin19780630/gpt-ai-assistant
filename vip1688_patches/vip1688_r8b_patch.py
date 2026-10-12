"""VIP1688 R8b: REPORT_8888 only, on top of R8. (1) 10 large-cap rows filled from the official TWSE STOCK_DAY_ALL rows the
branch already fetched (holiday showed only '更新中'); (2) stock name no longer repeats the change text; (3) overview subtitle
no longer repeats the data date; (4) AI prompt no longer leaks English field names; (5) shorter notes so carousel cards
have similar height (LINE stretches every card to the tallest). No deploy, no LINE, no AI."""
import ast, datetime, difflib, glob, hashlib, json, os, subprocess, sys, traceback

HOME = os.path.expanduser("~")
SRC_SHA = "1c11fb0c4b75507a20ece6ffb37b7614d66a2714e6105cf6fda75bea9e0f09ce"
FILL = '''def _vip1688_r8_fill_tw10(tw_top10, rows):
    """VIP1688_R8B: fill missing large-cap % change from official TWSE STOCK_DAY_ALL rows (last trading day)."""
    try:
        idx = {str(r.get("Code", "")).strip(): r for r in (rows or []) if isinstance(r, dict)}
        out = []
        for s in (tw_top10 or []):
            s2 = dict(s) if isinstance(s, dict) else s
            if isinstance(s2, dict) and _vip1688_r8_num(s2.get("pct")) in (None, 0):
                r = idx.get(str(s2.get("code", "")).strip())
                close = _vip1688_r8_num((r or {}).get("ClosingPrice"))
                chg = _vip1688_r8_num(str((r or {}).get("Change", "")).replace("X", ""))
                if close is not None and chg is not None and close - chg > 0:
                    s2["pct"] = round(chg / (close - chg) * 100, 2)
                    s2["note"] = "最近交易日收盤"
            out.append(s2)
        n = sum(1 for s in out if isinstance(s, dict) and _vip1688_r8_num(s.get("pct")) not in (None, 0))
        print(f"[VIP1688_R8B_TW10_FILL] filled={n}/{len(out)} rows={len(idx)}", flush=True)
        return out
    except Exception as e:
        print(f"[VIP1688_R8B_TW10_FILL_ERR] {type(e).__name__}: {str(e)[:160]}", flush=True)
        return tw_top10


'''
EDITS = [
    ("helper_anchor", "def _vip1688_r7_stock_line(", FILL + "def _vip1688_r7_stock_line("),
    ("tw10_call", "        # DNA候選股技術數據（優先沿用 DNA 正式引擎",
     "        tw_top10 = _vip1688_r8_fill_tw10(tw_top10, _twse_all)  # VIP1688_R8B\n        # DNA候選股技術數據（優先沿用 DNA 正式引擎"),
    ("name_clean", '    name = str(d.get("name") or "").strip()\n',
     '    name = __import__("re").split(r"[\\s|｜(（📈📉]", str(d.get("name") or "").strip())[0]  # VIP1688_R8B\n'),
    ("subtitle", 'f"資料日 {date_note} 收盤｜{period_note}", rows1',
     'f"資料日 {date_note} 收盤" + ("｜休市" if "休市" in str(period_note) else ""), rows1'),
    ("chapter_cap", '"\\n".join(v)[:900] for k, v in out.items() if v}', '"\\n".join(v)[:420] for k, v in out.items() if v}'),
    ("stock_note_cap", '("\\n".join(mine)[:500] if mine', '("\\n".join(mine)[:240] if mine'),
    ("p_rule", "【鐵律】只能使用系統提供的JSON數據；", "【鐵律】只能使用系統提供的數據，輸出不得出現英文欄位名稱；"),
    ("p_dna", "只引用dna_stocks欄位數值", "只引用系統提供的個股數值"),
    ("p_tw10", "依tw_top10漲跌家數判斷", "依台灣10大權值股漲跌家數判斷"),
    ("p_inst", "只依inst_buy_top5/inst_sell_top5；", "只依系統提供的法人買賣超資料；"),
    ("p_us", "只依us_giants漲跌", "只依美股7巨頭漲跌"),
]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def need(cond, msg, **dbg):
    if not cond:
        raise RuntimeError(f"{msg} | debug={dbg}")


def find_src():
    hits = []
    for d in sorted(glob.glob(os.path.join(HOME, "vip1688_r8_*", "source"))):
        p = os.path.join(d, "app.py")
        if os.path.isfile(p) and sha(open(p, "rb").read()) == SRC_SHA:
            hits.append(d)
    need(len(hits) >= 1, "R8 candidate with expected SHA not found", searched=glob.glob(os.path.join(HOME, "vip1688_r8_*")))
    return hits[-1]


def patch(t):
    need("_vip1688_r8_fill_tw10" not in t, "R8b already applied")
    for name, old, new in EDITS:
        need(t.count(old) == 1, f"{name} target count != 1", count=t.count(old))
        t = t.replace(old, new)
    return t


def behaviour(t):
    s = t.index("import threading as _vip1688_r8_threading")
    e = t.index("def _vip1688_r7_stock_line(")
    ns = {"FlexSendMessage": lambda **k: k}
    exec(compile(t[s:e], "r8b", "exec"), ns)
    r = {}
    tw = [{"code": "2330", "name": "台積電", "pct": 0, "note": "更新中"}, {"code": "2317", "name": "鴻海", "pct": 0, "note": "更新中"},
          {"code": "2454", "name": "聯發科", "pct": 1.5, "note": ""}, {"code": "9999", "name": "無資料", "pct": 0, "note": "更新中"}]
    rows = [{"Code": "2330", "ClosingPrice": "1,450.00", "Change": "-15.00"}, {"Code": "2317", "ClosingPrice": "210.5", "Change": "+3.5"},
            {"Code": "2454", "ClosingPrice": "1300", "Change": "99"}]
    f = ns["_vip1688_r8_fill_tw10"](tw, rows)
    r["tw10_filled_down"] = f[0]["pct"] == round(-15 / 1465 * 100, 2) and f[0]["note"] == "最近交易日收盤"
    r["tw10_filled_up"] = f[1]["pct"] == round(3.5 / 207 * 100, 2)
    r["tw10_existing_kept"] = f[2]["pct"] == 1.5
    r["tw10_missing_stays_zero"] = f[3]["pct"] == 0
    r["tw10_input_not_mutated"] = tw[0]["pct"] == 0
    r["tw10_bad_rows_safe"] = ns["_vip1688_r8_fill_tw10"](tw, None)[0]["pct"] == 0 and ns["_vip1688_r8_fill_tw10"](None, rows) == []
    d = {"name": "健策 📈 +360.0 (+5.29%)", "output_fields": {"price": {"value": "7165"}, "change": {"value": "360"}}}
    b = ns["_vip1688_r8_stock_bubble"]("3653", d, ["3653：" + "很長" * 300])
    title = b["header"]["contents"][0]["text"]
    r["name_clean"] = title == "3653 健策"
    note = b["body"]["contents"][-1]["text"]
    r["stock_note_capped"] = len(note) <= 245
    c, _ = ns["_vip1688_r8_build"](["3653"], [("x", d)], f, [], [], {}, "═══【第二章：大盤】═══\n" + "長" * 2000, "10/08", "盤前，數據基準：10/08收盤")
    sub = c["contents"][0]["header"]["contents"][1]["text"]
    r["overview_subtitle_no_dup"] = sub == "資料日 10/08 收盤"
    card7 = json.dumps(c["contents"][-2], ensure_ascii=False)
    r["card7_shows_tw10_pct"] = "台積電(2330)" in card7 and "-1.02%" in card7 and "+1.69%" in card7
    r["chapter_capped"] = len(c["contents"][-2]["body"]["contents"][-1]["text"]) <= 425
    i = t.index("# VIP1688_R7B: data-only prompt")
    p = t[i:t.find("# 8888精華報使用", i)]
    r["prompt_no_field_names"] = not any(k in p for k in ("dna_stocks", "tw_top10", "inst_buy_top5", "inst_sell_top5", "us_giants"))
    r["fill_called_before_dna"] = t.index("tw_top10 = _vip1688_r8_fill_tw10(tw_top10, _twse_all)") < t.index("# DNA候選股技術數據（優先沿用 DNA 正式引擎")
    return r


def main():
    out = {"status": "STOP", "revision": "VIP1688_R8B", "deployed": False, "line_sent": False, "ai_called": False}
    dst = None
    try:
        src = find_src()
        app = os.path.join(src, "app.py")
        raw = open(app, "rb").read()
        old = raw.decode("utf-8")
        new = patch(old)
        compile(new, "app.py", "exec", dont_inherit=True)
        checks = behaviour(new)
        need(all(checks.values()), "behaviour check failed", checks=checks)
        diff = [l for l in difflib.unified_diff(old.splitlines(), new.splitlines(), "r8", "r8b", n=0, lineterm="")
                if l[:1] in "+-" and l[:3] not in ("+++", "---")]
        removed = [l[1:] for l in diff if l.startswith("-")]
        olds = "\n".join(o for _, o, _ in EDITS)
        need(all(any(seg and seg in l for seg in olds.split("\n")) for l in removed), "unexpected removed lines", removed=removed[:6])
        dst = os.path.join(HOME, "vip1688_r8b_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        os.mkdir(dst)
        subprocess.run(["cp", "-al", src, os.path.join(dst, "source")], check=True)
        target = os.path.join(dst, "source", "app.py")
        tmp = target + ".r8btmp"
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
    print("R8B_RESULT " + json.dumps(out, ensure_ascii=False))
    return 0 if out["status"] == "candidate_ready" else 2


if __name__ == "__main__":
    sys.exit(main())
