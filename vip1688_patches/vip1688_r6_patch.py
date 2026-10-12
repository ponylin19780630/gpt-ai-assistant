"""VIP1688 R6: REPORT_8888 only. 1) P6AH stops patching 1688 as a stock report. 2) 1688 Flex red=up/green=down.
Builds an isolated candidate (hardlink tree + new app.py). No deploy, no LINE, no AI, no app import."""
import ast, datetime, difflib, hashlib, json, os, re, subprocess, sys, traceback

HOME = os.path.expanduser("~")
SRC = os.path.join(HOME, "insti_line_r1_o7_ze2j6", "source")
SRC_SHA = "15694da566406e1cbecd7a20162b3d2f9edebde6933ae9e5c8a144a5634ab874"
OLD1 = "MODE=VIP_DNA(?![A-Z0-9_])', upper):"
NEW1 = "MODE=(?:VIP_DNA|REPORT_8888)(?![A-Z0-9_])', upper):"
GREEN, RED, TMP = '"#27AE60", "#1A2A1A"', '"#E74C3C", "#2A1A1A"', "\x00R6SWAP\x00"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def need(cond, msg, **dbg):
    if not cond:
        raise RuntimeError(f"{msg} | debug={dbg}")


def lines_of(text, needle):
    return [i + 1 for i, l in enumerate(text.splitlines()) if needle in l][:10]


def patch(text):
    need(text.count(OLD1) == 1, "P6AH target count != 1", count=text.count(OLD1), lines=lines_of(text, OLD1))
    defs = lines_of(text, "def build_report1688_flex(")
    need(len(defs) == 1, "build_report1688_flex def count != 1", lines=defs)
    over = [n for n in lines_of(text, "build_report1688_flex") if n != defs[0]]
    over = [n for n in over if re.search(r"build_report1688_flex\s*=|\[.build_report1688_flex.\]\s*=",
                                         text.splitlines()[n - 1])]
    need(not over, "build_report1688_flex is reassigned elsewhere", lines=over)
    s = text.index("def build_report1688_flex(")
    e = text.find("\ndef ", s + 10)
    e = len(text) if e < 0 else e
    body = text[s:e]
    need(body.count(GREEN) == 4 and body.count(RED) == 4, "color pair count != 4/4",
         green=body.count(GREEN), red=body.count(RED))
    body = body.replace(GREEN, TMP).replace(RED, GREEN).replace(TMP, RED)
    return text[:s].replace(OLD1, NEW1) + body + text[e:].replace(OLD1, NEW1)


def func(tree, name):
    hits = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name]
    need(len(hits) == 1, f"AST def count != 1: {name}", count=len(hits))
    return ast.Module(body=[hits[0]], type_ignores=[])


def colors(node, out):
    if isinstance(node, dict):
        if isinstance(node.get("text"), str) and "color" in node:
            out[node["text"]] = node["color"]
        for v in node.values():
            colors(v, out)
    elif isinstance(node, list):
        for v in node:
            colors(v, out)
    return out


def behaviour(text):
    tree = ast.parse(text)
    ns = {"_v9670p6ah_re": re, "_V9670P6AH_Any": object, "FlexSendMessage": lambda **k: k}
    exec(compile(func(tree, "_v9670p6ah_is_stock_report_text"), "p6ah", "exec"), ns)
    exec(compile(func(tree, "build_report1688_flex"), "r1688", "exec"), ns)
    f = ns["_v9670p6ah_is_stock_report_text"]
    res = {
        "p6ah_1688_excluded": f("seg=2 mode=REPORT_8888", ["第一章 DNA"]) is False,
        "p6ah_vip_dna_excluded": f("seg=0 mode=VIP_DNA", ["第一章"]) is False,
        "p6ah_stock_kept": f("seg=1 mode=STOCK", ["深度研報：2330"]) is True,
    }
    up = "台灣10大權值股\n A +1% 📈\n B +2% 📈\n C -1% 📉\n美股7巨頭\n x 📈\n y 📈\n z 📉\n大盤多空判斷：偏多\n台指期 法人偏多"
    dn = up.replace("📈", "§").replace("📉", "📈").replace("§", "📉").replace("偏多", "偏空")
    cu = colors(ns["build_report1688_flex"]("t", up)["contents"], {})
    cd = colors(ns["build_report1688_flex"]("t", dn)["contents"], {})
    res.update({
        "tw_up_red": cu.get("4漲/2跌") == "#E74C3C", "tw_down_green": cd.get("2漲/4跌") == "#27AE60",
        "us_up_red": cu.get("📈 2漲/1跌") == "#E74C3C", "us_down_green": cd.get("📉 1漲/2跌") == "#27AE60",
        "mkt_up_red": cu.get("偏多 ✅") == "#E74C3C", "mkt_down_green": cd.get("偏空 🔻") == "#27AE60",
        "tx_up_red": cu.get("期偏多") == "#E74C3C", "tx_down_green": cd.get("期偏空") == "#27AE60",
    })
    return res


def main():
    out = {"status": "STOP", "revision": "VIP1688_R6", "deployed": False, "line_sent": False, "ai_called": False}
    dst = None
    try:
        app = os.path.join(SRC, "app.py")
        raw = open(app, "rb").read()
        need(sha(raw) == SRC_SHA, "source app SHA mismatch", got=sha(raw))
        old = raw.decode("utf-8")
        new = patch(old)
        compile(new, "app.py", "exec", dont_inherit=True)
        checks = behaviour(new)
        need(all(checks.values()), "behaviour check failed", checks=checks)
        diff = [l for l in difflib.unified_diff(old.splitlines(), new.splitlines(), "orig", "r6", n=0, lineterm="")
                if l[:1] in "+-" and l[:3] not in ("+++", "---")]
        need(len(diff) == 18, "unexpected diff size", diff_lines=len(diff))
        dst = os.path.join(HOME, "vip1688_r6_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        os.mkdir(dst)
        subprocess.run(["cp", "-al", SRC, os.path.join(dst, "source")], check=True)
        target = os.path.join(dst, "source", "app.py")
        tmp = target + ".r6tmp"
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
                   new_app_sha=sha(nb), checks=checks, diff=diff)
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
        out["traceback"] = traceback.format_exc()[-1500:]
        out["partial_candidate"] = dst
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if out["status"] == "candidate_ready" else 2


if __name__ == "__main__":
    sys.exit(main())
