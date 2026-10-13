"""RK_R3: 排行榜個股卡加「外本比／投本比（當日｜近N日｜趨勢）」與權值股★。
只在 app.py 檔尾附加一段：包裝 _v9663_stock_bubble / _v9663_summary_bubble（原卡內容不變，只追加）。
數據沿用已上線的 insti_query_r1（INSTI_R3）函式；當日法人改用全市場官方資料，任何上市/上櫃個股皆可計算。
用法：python3 -B rk_r3_patch.py --src DIR --cand DIR [--app-sha SHA] [--no-net]
"""
import hashlib, os, subprocess, sys

APP_SHA = "f7340c7905ed68e5"          # 正式版 insti-r3e 的 app.py（前16碼）
INSTI_SHA = "3da9b6fe"                # 正式版 insti_query_r1.py（R3e，前8碼）
MARK = "# ===== RK_R3"
BLOCK = r'''
# ===== RK_R3：排行榜個股卡加外本比／投本比／權值股★（只包裝 _v9663_stock_bubble、_v9663_summary_bubble）=====
try:
    import re as _rkr3_re
    import threading as _rkr3_threading
    import time as _rkr3_time
    import insti_query_r1 as _rkr3_q
    _RKR3_PREV_BUBBLE = globals().get("_v9663_stock_bubble")
    _RKR3_PREV_SUMMARY = globals().get("_v9663_summary_bubble")
    if not callable(_RKR3_PREV_BUBBLE) or not callable(getattr(_rkr3_q, "_r3_lines", None)):
        raise RuntimeError("RK_R3 dependencies unavailable")
    _RKR3_CACHE = {"at": -1e9, "data": None}
    _RKR3_LOCK = _rkr3_threading.Lock()

    def _rkr3_data():
        """10 分鐘快取；失敗也快取 2 分鐘，避免每張卡重試卡住推播。"""
        c = _RKR3_CACHE
        age = _rkr3_time.monotonic() - c["at"]
        if c["data"] is not None and age < (600 if c["data"].get("ok") else 120):
            return c["data"]
        if not _RKR3_LOCK.acquire(timeout=25):
            return c["data"]
        try:
            age = _rkr3_time.monotonic() - c["at"]
            if c["data"] is not None and age < (600 if c["data"].get("ok") else 120):
                return c["data"]
            t0 = _rkr3_time.monotonic()
            try:
                snap = _rkr3_q.get_snapshot()
                hist = _rkr3_q._r3_history(snap, budget=20)
                day0 = _rkr3_q._r3_day_rows(snap.day, _rkr3_time.monotonic() + 15)
                shares = _rkr3_q._r3_shares()
                stars = set()
                for _try in range(2):
                    try:
                        stars = _rkr3_q._r3_star_set(shares)
                    except Exception as exc:
                        print(f"[RK_R3_STAR_ERR] {type(exc).__name__}: {str(exc)[:120]}", flush=True)
                    if len(stars) >= 60:
                        break
                data = {"hist": ([(snap.day, day0)] + hist[1:]) if day0 else None, "day": snap.day,
                        "shares": shares, "stars": stars, "stars_ok": len(stars) >= 60,
                        "ok": bool(day0) and len(stars) >= 60 and not ((getattr(_rkr3_q, "_R3_SHARES", {}) or {}).get("fail")),
                        "why": "" if day0 else "當日全市場法人資料暫缺"}
                print(f"[RK_R3_DATA] day={snap.day} days={len(hist)} day0_rows={len(day0 or {})} "
                      f"shares={len(shares)} stars={len(stars)} ms={int((_rkr3_time.monotonic() - t0) * 1000)}", flush=True)
            except Exception as exc:
                data = {"hist": None, "shares": {}, "stars": set(), "why": "官方法人資料逾時"}
                print(f"[RK_R3_DATA_ERR] {type(exc).__name__}: {str(exc)[:160]}", flush=True)
            c.update(at=_rkr3_time.monotonic(), data=data)
            return data
        finally:
            _RKR3_LOCK.release()

    def _rkr3_dark(bubble):
        st = ((bubble.get("styles") or {}).get("body") or {})
        col = str((bubble.get("body") or {}).get("backgroundColor") or st.get("backgroundColor") or "#FFFFFF")
        if not _rkr3_re.fullmatch(r"#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?", col):
            return False
        r, g, b = (int(col[i:i + 2], 16) for i in (1, 3, 5))
        return 0.299 * r + 0.587 * g + 0.114 * b < 128

    def _rkr3_line(parts, pal):
        spans = []
        for piece, sign in parts:
            if spans and spans[-1]["color"] == pal[sign]:
                spans[-1]["text"] += piece
            else:
                spans.append({"type": "span", "text": piece, "color": pal[sign]})
        return {"type": "text", "size": "xs", "wrap": True, "contents": spans}

    def _rkr3_star(bubble, code, gold):
        queue = [bubble.get("header"), bubble.get("body")]
        while queue:
            n = queue.pop(0)
            if not isinstance(n, dict):
                continue
            if n.get("type") == "text":
                spans = n.get("contents") if isinstance(n.get("contents"), list) else None
                txt = "".join(str(s.get("text", "")) for s in spans) if spans else str(n.get("text", ""))
                if code in txt:
                    keep = {k: n[k] for k in ("size", "weight") if k in n}
                    star = dict(type="span", text=" ★", color=gold, **keep)
                    if spans:
                        spans.append(star)
                    else:
                        first = dict(type="span", text=txt, **keep)
                        if "color" in n:
                            first["color"] = n["color"]
                        n["contents"] = [first, star]
                    return True
            queue.extend(n.get("contents") or [] if isinstance(n.get("contents"), list) else [])
        return False

    def _rkr3_stock_bubble(rec, *args, **kwargs):
        bubble = _RKR3_PREV_BUBBLE(rec, *args, **kwargs)
        try:
            code = str((rec or {}).get("code") or "").strip().upper()
            body = (bubble or {}).get("body") or {}
            if not code or not isinstance(body.get("contents"), list):
                return bubble
            data = _rkr3_data() or {"hist": None, "why": "官方法人資料逾時"}
            pal = _rkr3_q._R3_DARK if _rkr3_dark(bubble) else _rkr3_q._R3_LIGHT
            if data.get("hist") is not None:
                lines = _rkr3_q._r3_lines(code, data["hist"], data["shares"].get(code))
            else:
                t = f"外本比／投本比：資料不足（{data.get('why') or '官方法人資料逾時'}）"
                lines = [(t, [(t, None)])]
            new = [_rkr3_line(parts, pal) for _t, parts in lines]
            if data.get("hist") is not None and data.get("day") and len(lines[0][1]) > 1:
                new[0]["contents"].insert(0, {"type": "span", "text": f"法人{data['day']:%m/%d}｜", "color": pal["L"]})
            if code in (data.get("stars") or set()):
                gold = "#FFD700" if pal is _rkr3_q._R3_DARK else "#B8860B"
                if not _rkr3_star(bubble, code, gold):
                    new[0]["contents"].insert(0, {"type": "span", "text": "★權值股 ", "color": gold})
            body["contents"].extend(new)
        except Exception as exc:
            print(f"[RK_R3_BUBBLE_ERR] {type(exc).__name__}: {str(exc)[:160]}", flush=True)
        return bubble

    def _rkr3_summary_bubble(*args, **kwargs):
        bubble = _RKR3_PREV_SUMMARY(*args, **kwargs)
        try:
            body = (bubble or {}).get("body") or {}
            if isinstance(body.get("contents"), list):
                pal = _rkr3_q._R3_DARK if _rkr3_dark(bubble) else _rkr3_q._R3_LIGHT
                data = _rkr3_data() or {}
                day = f"法人資料日 {data['day']:%m/%d}（官方最新完整報表）｜" if data.get("day") else "法人資料暫缺｜"
                mkt = (getattr(_rkr3_q, "_R3_SHARES", {}) or {}).get("mkt") or {}
                st = data.get("stars") or set()
                tw, tp = sum(mkt.get(c) == "上市" for c in st), sum(mkt.get(c) == "上櫃" for c in st)
                star = ("★權值股＝上市市值前50＋上櫃市值前10" if data.get("stars_ok")
                        else f"★權值股：官方收盤價部分暫缺（上市{tw}/50、上櫃{tp}/10），本次僅標已取得者")
                body["contents"].append({"type": "text", "size": "xxs", "wrap": True, "color": pal["L"],
                                         "text": day + "外本比／投本比＝外資／投信買賣超÷發行股數×100%｜當日｜近5日累計｜趨勢；"
                                                 "數值紅正・綠負・黃0・灰缺；" + star})
        except Exception as exc:
            print(f"[RK_R3_SUMMARY_ERR] {type(exc).__name__}: {str(exc)[:160]}", flush=True)
        return bubble

    _v9663_stock_bubble = _rkr3_stock_bubble
    if callable(_RKR3_PREV_SUMMARY):
        _v9663_summary_bubble = _rkr3_summary_bubble
    print("[RK_R3_INIT] RK_R3b ranking cards: 外本比/投本比/★ + 法人資料日", flush=True)
except Exception as _rkr3_init_error:
    print(f"[RK_R3_INIT_ERR] {type(_rkr3_init_error).__name__}: {str(_rkr3_init_error)[:200]}", flush=True)
'''

PROBE = r'''
import json, sys
import insti_query_r1 as q
codes = sys.argv[1].split(",")
def fake_bubble(rec):
    return {"type": "bubble", "body": {"type": "box", "layout": "vertical", "backgroundColor": "#1F2430",
            "contents": [{"type": "text", "text": f"{rec['code']} 測試股", "weight": "bold", "size": "lg", "color": "#FFFFFF"},
                         {"type": "text", "text": "原卡內容", "size": "sm"}]},
            "footer": {"type": "box", "layout": "vertical", "contents": [{"type": "button", "action": {"type": "postback", "label": "x", "data": f"rk9|{rec['code']}|"}}]}}
def fake_summary(title, payload):
    return {"type": "bubble", "body": {"type": "box", "layout": "vertical", "contents": [{"type": "text", "text": title}]}}
ns = {"_v9663_stock_bubble": fake_bubble, "_v9663_summary_bubble": fake_summary}
exec(compile(open("RK_BLOCK.py", encoding="utf-8").read(), "RK_BLOCK.py", "exec"), ns)
for c in codes:
    b = ns["_v9663_stock_bubble"]({"code": c})
    orig = fake_bubble({"code": c})
    head = b["body"]["contents"][0]
    keep_ok = b["body"]["contents"][1] == orig["body"]["contents"][1] and b["footer"] == orig["footer"] and head.get("text") == orig["body"]["contents"][0]["text"]
    star = "★" if head.get("contents") else ""
    rows = ["".join(s["text"] for s in x["contents"]) for x in b["body"]["contents"][2:]]
    print("RK_ROW", c, star or "-", "原卡不變" if keep_ok else "原卡被改!", rows)
s = ns["_v9663_summary_bubble"]("🏆 排行榜精選", {})
print("RK_SUMMARY", s["body"]["contents"][-1]["text"])
b = ns["_v9663_stock_bubble"]({"code": codes[0]})
print("RK_CARD_BYTES", len(json.dumps(b, ensure_ascii=False, separators=(",", ":")).encode()), "vs 原卡", len(json.dumps(fake_bubble({"code": codes[0]}), ensure_ascii=False, separators=(",", ":")).encode()))
'''


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def need(c, m):
    if not c:
        print(f"[RK_STOP] {m}")
        sys.exit(1)


def main():
    a = sys.argv[1:]
    src, cand = a[a.index("--src") + 1], a[a.index("--cand") + 1]
    app_sha = a[a.index("--app-sha") + 1] if "--app-sha" in a else APP_SHA
    app, ins = os.path.join(src, "app.py"), os.path.join(src, "insti_query_r1.py")
    if "--no-net" not in a:
        need(sha(app).startswith(app_sha), f"app.py SHA 不符 {sha(app)[:16]}")
        need(sha(ins).startswith(INSTI_SHA), f"insti_query_r1.py SHA 不符 {sha(ins)[:8]}（須為已上線 R3e）")
    t = open(app, encoding="utf-8").read()
    need(MARK not in t, "已套用過 RK_R3")
    new = t.rstrip("\n") + "\n" + BLOCK
    compile(new, "app.py", "exec")
    need(not os.path.exists(cand), "候選目錄已存在")
    os.makedirs(os.path.dirname(cand), exist_ok=True)
    subprocess.run(["cp", "-al", src, cand], check=True)
    tmp = os.path.join(cand, ".rk_r3.tmp")
    open(tmp, "w", encoding="utf-8").write(new)
    os.replace(tmp, os.path.join(cand, "app.py"))
    need(os.stat(os.path.join(cand, "app.py")).st_nlink == 1, "候選 app.py 仍是硬連結")
    print(f"[RK_PATCHED] candidate={cand} app_sha={sha(os.path.join(cand, 'app.py'))[:16]} +lines={BLOCK.count(chr(10))}")
    if "--no-net" in a:
        return
    probe_dir = os.path.join(os.path.dirname(cand), "rk_probe")
    os.makedirs(probe_dir, exist_ok=True)
    open(os.path.join(probe_dir, "RK_BLOCK.py"), "w", encoding="utf-8").write(BLOCK)
    open(os.path.join(probe_dir, "probe.py"), "w", encoding="utf-8").write(PROBE)
    env = dict(os.environ, PYTHONPATH=cand)
    codes = "2330,2317,6488,3105,1101,8299,00992A,0050"
    r = subprocess.run([sys.executable, "-B", "probe.py", codes], cwd=probe_dir, env=env,
                       capture_output=True, text=True, timeout=300)
    print("\n".join(l for l in r.stdout.splitlines() if "逐筆核對" not in l)[-6000:])
    print(r.stderr[-2500:])
    print(f"[RK_DRY] exit={r.returncode}")


if __name__ == "__main__":
    main()
