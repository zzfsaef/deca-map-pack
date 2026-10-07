#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pack_maps.py —— 把镜像下来的 site/ 按保护区（地图）分别打包。

产出（默认写到 dist/，所有包解压时都指向同一个目录，也就是都会展开成 site/...）：

    deca-map-base.zip               框架 + deca/lib + 全部保护区的 JSON（很小，必下）
    deca-map-r6-育空河谷.zip         该保护区的热力图 + 底图瓦片
    deca-map-r6-育空河谷-images.zip  单个保护区超过 --split-gb 时自动拆成两张：
    deca-map-r6-育空河谷-tiles.zip      images = 热力图，tiles = 底图瓦片

用法:
    python pack_maps.py --site site --out dist                   # base + 全部保护区
    python pack_maps.py --site site --out dist --mode base        # 只打框架包
    python pack_maps.py --site site --out dist --mode maps --reserves r6 r10
    python pack_maps.py --site site --out dist --only r6          # 单保护区（矩阵任务用）

zip 里 PNG/JPG 这类本来就压过的文件按「存储」写入，不再浪费时间二次压缩。
"""

import argparse
import glob
import json
import os
import re
import sys
import zipfile

DATA_REL = os.path.join("deca", "hp", "data")   # site/ 下面放保护区数据的相对路径
TILE_RE = re.compile(r"/\d+/\d+/\d+\.[A-Za-z0-9]+$")   # .../t_topo/5/12/30.png
ALREADY_PACKED = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".ktx", ".ktx2", ".dds",
    ".wasm", ".glb", ".gltf", ".zip", ".gz", ".br", ".woff", ".woff2",
    ".mp3", ".ogg", ".wav", ".mp4", ".webm", ".bin", ".dat",
}
GIB = 1024 ** 3


# ------------------------------------------------------------------ 小工具

def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024


def safe_name(s):
    """文件名里不能出现的字符换掉，中文保留。"""
    return re.sub(r'[\\/:*?"<>|\s]+', "-", s).strip("-")


def load_reserve_names():
    """保护区英文全名 -> 官方中文名，直接复用 localize.py 里的表。"""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from localize import RESERVES  # noqa: WPS433
        return RESERVES
    except Exception as e:
        print(f"[pack] 读不到 localize.RESERVES（{e}），包名只用保护区 id", file=sys.stderr)
        return {}


def zh_name(rid_dir, names):
    """从 reserve.json 里认出这是哪张图，返回中文名。认不出就返回 None。"""
    for p in glob.glob(os.path.join(rid_dir, "*.json")):
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                txt = f.read()
        except OSError:
            continue
        for en in sorted(names, key=len, reverse=True):
            if en in txt:
                return names[en]
    return None


def tile_dirs(rid_dir):
    """layers.json 里 tile_map 图层的目录名集合，用来区分底图瓦片和热力图。"""
    out = set()
    p = os.path.join(rid_dir, "layers.json")
    if not os.path.isfile(p):
        return out
    try:
        with open(p, encoding="utf-8") as f:
            layers = json.load(f)
    except (OSError, ValueError):
        return out
    for L in layers if isinstance(layers, list) else []:
        url = L.get("url") or ""
        if L.get("layer_type") == "tile_map" and url:
            out.add(url.split("/")[0])
    return out


def walk_files(root):
    for dp, _dns, fns in os.walk(root):
        for fn in fns:
            yield os.path.join(dp, fn)


# ------------------------------------------------------------------ 打 zip

class Writer:
    """按顺序写 zip，顺便统计体积。"""

    def __init__(self, path):
        self.path = path
        self.zf = zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, allowZip64=True)
        self.raw = 0
        self.n = 0

    def add(self, fpath, arcname):
        ext = os.path.splitext(fpath)[1].lower()
        ctype = zipfile.ZIP_STORED if ext in ALREADY_PACKED else zipfile.ZIP_DEFLATED
        self.zf.write(fpath, arcname, compress_type=ctype)
        self.raw += os.path.getsize(fpath)
        self.n += 1
        if self.n % 500 == 0:
            print(f"    ... {self.n} 个文件 {human(self.raw)}", flush=True)

    def close(self):
        self.zf.close()
        return os.path.getsize(self.path)


def arcname_for(site, fpath):
    """zip 内路径以 site/ 开头，解压到同一目录就能拼成完整的站点。"""
    return "site/" + os.path.relpath(fpath, site).replace(os.sep, "/")


def write_zip(out_dir, name, items, note):
    """items: [(绝对路径, zip 内路径)]；返回 (文件名, zip 字节数, 原始字节数, 文件数)"""
    path = os.path.join(out_dir, name)
    w = Writer(path)
    for fpath, arc in items:
        w.add(fpath, arc)
    size = w.close()
    print(f"[pack] {name}  {human(size)}  （原始 {human(w.raw)}，{w.n} 个文件）{note}")
    return name, size, w.raw, w.n


# ------------------------------------------------------------------ base 包

def pack_base(site, out_dir, data_abs):
    items = []
    for f in walk_files(site):
        rel = os.path.relpath(f, site)
        # data/<rX>/ 下面：只收 JSON（体积小、不带图也能开界面），图片归各保护区包
        parts = rel.split(os.sep)
        if len(parts) >= 4 and os.sep.join(parts[:3]) == DATA_REL:
            if not f.lower().endswith(".json"):
                continue
        items.append((f, arcname_for(site, f)))
    if not items:
        print("[pack] site/ 里没东西，先跑镜像再打包", file=sys.stderr)
        return None
    return write_zip(out_dir, "deca-map-base.zip", items, "  ← 框架，必下")


# ------------------------------------------------------------------ 保护区包

def reserve_items(rid, rid_dir, site):
    """把某个保护区的文件分成 元数据 / 热力图 / 瓦片（按 zoom 分组）三类。"""
    tdirs = tile_dirs(rid_dir)
    meta, heat, tiles = [], [], {}
    for f in walk_files(rid_dir):
        arc = arcname_for(site, f)
        rel = os.path.relpath(f, rid_dir).replace(os.sep, "/")
        if "/" not in rel:                       # 直接躺在 data/<rX>/ 下面的 JSON
            meta.append((f, arc))
            continue
        head = rel.split("/")[0]
        if head in tdirs or TILE_RE.search("/" + rel):
            segs = rel.split("/")
            zoom = segs[1] if len(segs) > 2 and segs[1].isdigit() else "?"
            tiles.setdefault(zoom, []).append((f, arc))
        else:
            heat.append((f, arc))
    return meta, heat, tiles


def pack_reserve(site, out_dir, rid, names, split_gb):
    rid_dir = os.path.join(site, DATA_REL, rid)
    if not os.path.isdir(rid_dir):
        print(f"[pack] 跳过 {rid}：没有 {rid_dir}", file=sys.stderr)
        return []
    meta, heat, tiles = reserve_items(rid, rid_dir, site)
    n_img = len(heat) + sum(len(v) for v in tiles.values())
    if n_img == 0:
        print(f"[pack] 跳过 {rid}：一张图都没有（抓取失败？）", file=sys.stderr)
        return []

    zh = zh_name(rid_dir, names)
    stem = f"deca-map-{rid}-{safe_name(zh)}" if zh else f"deca-map-{rid}"
    total = sum(os.path.getsize(p) for p, _ in meta + heat + [x for v in tiles.values() for x in v])
    note = f"  {len(heat)} 张热力图 / {n_img - len(heat)} 张瓦片"
    limit = split_gb * GIB

    if total <= limit:
        return [write_zip(out_dir, stem + ".zip", meta + heat + [x for v in tiles.values() for x in v], note)]

    # 超过上限：热力图一张、瓦片按 zoom 从小到大攒着分卷。
    meta_size = sum(os.path.getsize(p) for p, _ in meta)
    plan = []                                    # [(zip 名, 文件列表, 备注)]
    if heat:
        s = sum(os.path.getsize(p) for p, _ in heat)
        note = "  ← 热力图"
        if s + meta_size > limit:
            print(f"[pack] 警告：{rid} 的热力图本身就有 {human(s)}，超过单包上限", file=sys.stderr)
            note = "  ← 热力图（超限）"
        plan.append((stem + "-images.zip", meta + heat, note))

    batches, batch, batch_size, batch_zooms = [], [], 0, []
    for z in sorted(tiles, key=lambda z: (z == "?", z.zfill(2))):
        s = sum(os.path.getsize(p) for p, _ in tiles[z])
        if batch and batch_size + meta_size + s > limit:
            batches.append((batch, batch_zooms))
            batch, batch_size, batch_zooms = [], 0, []
        batch += tiles[z]
        batch_size += s
        batch_zooms.append(z)
    if batch:
        batches.append((batch, batch_zooms))

    for i, (items, zs) in enumerate(batches):
        name = f"{stem}-tiles.zip" if len(batches) == 1 else f"{stem}-tiles-{i + 1}.zip"
        zr = zs[0] if len(zs) == 1 else f"{zs[0]}-{zs[-1]}"
        s = sum(os.path.getsize(p) for p, _ in items)
        if s + meta_size > limit:
            print(
                f"[pack] 警告：{rid} 的 zoom {zr} 一层就有 {human(s + meta_size)}，"
                f"没法再拆（GitHub 单资源上限 2GB，自己留意）",
                file=sys.stderr,
            )
        plan.append((name, meta + items, f"  ← 底图瓦片 zoom {zr}"))

    return [write_zip(out_dir, n, it, note) for n, it, note in plan]


# ------------------------------------------------------------------ 入口

def main(argv=None):
    ap = argparse.ArgumentParser(description="把 site/ 按保护区分别打包")
    ap.add_argument("--site", default="site", help="镜像目录")
    ap.add_argument("--out", default="dist", help="zip 输出目录")
    ap.add_argument("--mode", choices=["all", "base", "maps"], default="all")
    ap.add_argument("--reserves", nargs="*", default=None, help="只要这些保护区")
    ap.add_argument("--only", default=None, help="只打这一个保护区（等价 --reserves X）")
    ap.add_argument("--split-gb", type=float, default=1.8,
                    help="单个包超过这个大小就拆开（GitHub 单资源上限 2GB，默认 1.8）")
    a = ap.parse_args(argv)

    site = a.site
    out_dir = a.out
    data_abs = os.path.join(site, DATA_REL)
    if not os.path.isdir(data_abs):
        print(f"[pack] 找不到 {data_abs}", file=sys.stderr)
        return 1
    os.makedirs(out_dir, exist_ok=True)

    names = load_reserve_names()
    want = [a.only] if a.only else a.reserves
    rids = sorted(
        d for d in os.listdir(data_abs)
        if os.path.isdir(os.path.join(data_abs, d)) and (not want or d in want)
    )
    if want:
        missing = [r for r in want if r not in rids]
        if missing:
            print(f"[pack] 警告：site 里没有这些保护区 {missing}", file=sys.stderr)

    made = []
    if a.mode in ("all", "base"):
        r = pack_base(site, out_dir, data_abs)
        if r:
            made.append(("base",) + r)
    if a.mode in ("all", "maps"):
        for rid in rids:
            for r in pack_reserve(site, out_dir, rid, names, a.split_gb):
                made.append((rid,) + r)

    manifest = {
        "site": site,
        "packs": [
            {"reserve": rid, "name": name, "size": size, "raw": raw, "files": n}
            for rid, name, size, raw, n in made
        ],
    }
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    total = sum(m[2] for m in made)
    print(f"\n[pack] 共 {len(made)} 个包，合计 {human(total)} -> {out_dir}/")
    for rid, name, size, raw, n in made:
        print(f"    {human(size):>10}  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
