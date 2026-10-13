import hashlib, os, sys
H = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "~")
PROTECT = {H + "/vip1688_r13b_20261012_024917/source", H + "/insti_line_r1_o7_ze2j6/source"}
dirs = []
for root, ds, fs in os.walk(H):
    depth = root[len(H):].count(os.sep)
    ds[:] = [d for d in ds if not d.startswith(".")] if depth < 2 else []
    if "app.py" in fs and root != H:
        dirs.append(root)
dirs = [d for d in dirs if not any(o != d and o.startswith(d + os.sep) for o in dirs)]
def fsha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.digest()
def tree(d):
    h = hashlib.sha256(); n = size = free = 0
    for r, ds, fs in os.walk(d):
        ds[:] = sorted(x for x in ds if x != "__pycache__")
        for f in sorted(fs):
            p = os.path.join(r, f)
            if os.path.islink(p) or not os.path.isfile(p):
                continue
            st = os.stat(p)
            h.update(os.path.relpath(p, d).encode() + b"\0" + fsha(p))
            n += 1; size += st.st_size; free += st.st_size if st.st_nlink == 1 else 0
    return h.hexdigest()[:12], n, size, free
groups = {}
for d in dirs:
    groups.setdefault(fsha(os.path.join(d, "app.py")).hex()[:8], []).append(d)
dels, total = [], 0
for a, ds in sorted(groups.items()):
    if len(ds) < 2:
        continue
    clus = {}
    for d in ds:
        r = tree(d)
        clus.setdefault(r[0], [r, []])[1].append(d)
    for td, ((_, n, size, _f), ms) in clus.items():
        if len(ms) < 2:
            continue
        ms.sort(key=lambda d: (d in PROTECT, os.path.getmtime(os.path.join(d, "app.py"))), reverse=True)
        print(f"[同內容] app={a} tree={td} 檔數={n} 大小={size/1048576:.1f}M 保留→ {ms[0]}")
        for d in ms[1:]:
            if d in PROTECT:
                continue
            f2 = tree(d)[3]
            print(f"   刪除候選 可釋放={f2/1048576:.1f}M {d}")
            dels.append(f"{a} {td} {d}"); total += f2
out = os.path.join(H, "cleanup_candidates_20261013.txt")
open(out, "w").write("\n".join(dels) + ("\n" if dels else ""))
print(f"[DUP_SCAN] 目錄={len(dirs)} 刪除候選={len(dels)} 預估可釋放={total/1048576:.1f}M 清單={out}")
