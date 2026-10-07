#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_urls.py —— 从已经镜像下来的 layers.json 里，生成全部图片和瓦片的下载清单。

layers.json 里两种图层：
  {"layer_type":"tile_map","url":"data/r0/t_topo/{z}/{x}/{y}.png","max_zoom":5}
  {"layer_type":"image",   "url":"data/r0/t_red_deer_spawn/full.png"}

用法:
    python gen_urls.py --site site > assets.txt                   # 全部保护区
    python gen_urls.py --site site --reserves r0 r1 > assets.txt  # 只要这两个
    python gen_urls.py --site site --no-tiles > assets.txt        # 不要底图瓦片
    python gen_urls.py --site site --split-dir urls               # 按保护区分别写 urls/r0.txt ...

生成的清单交给 mirror_site.py --seeds-file 使用；--split-dir 适合一个保护区
一个任务地分头抓（每个保护区的包也就分开打了）。
"""

import argparse
import glob
import json
import os
import sys

DEFAULT_BASE = "https://www.mathartbang.com/deca/hp/"


def urls_for_reserve(path, base, tiles=True, images=True):
    """读一个 layers.json，返回 (图片 URL 列表, 瓦片 URL 列表)。"""
    imgs, til = [], []
    for layer in json.load(open(path, encoding="utf-8")):
        url = layer.get("url")
        if not url:
            continue
        if layer.get("layer_type") == "tile_map":
            if not tiles:
                continue
            mz = int(layer.get("max_zoom", 5))
            for z in range(mz + 1):
                n = 2 ** z
                for x in range(n):
                    for y in range(n):
                        til.append(
                            base
                            + url.replace("{z}", str(z))
                                  .replace("{x}", str(x))
                                  .replace("{y}", str(y))
                        )
        elif images:
            imgs.append(base + url)
    return imgs, til


def main(argv=None):
    ap = argparse.ArgumentParser(description="从 layers.json 生成图片/瓦片 URL 清单")
    ap.add_argument("--site", default="site", help="镜像目录")
    ap.add_argument("--base", default=DEFAULT_BASE, help="站点前缀")
    ap.add_argument("--reserves", nargs="*", default=None, help="只要这些保护区")
    ap.add_argument("--tiles", dest="tiles", action="store_true", default=True)
    ap.add_argument("--no-tiles", dest="tiles", action="store_false", help="跳过底图瓦片")
    ap.add_argument("--images", dest="images", action="store_true", default=True)
    ap.add_argument("--no-images", dest="images", action="store_false", help="跳过热力图")
    ap.add_argument("--split-dir", default=None,
                    help="按保护区分别写入该目录下的 <保护区>.txt，而不是全打到 stdout")
    a = ap.parse_args(argv)

    pattern = os.path.join(a.site, "deca", "hp", "data", "*", "layers.json")
    files = sorted(glob.glob(pattern))
    if not files:
        print(f"[gen_urls] 找不到 layers.json（找的是 {pattern}）", file=sys.stderr)
        print("[gen_urls] 请先跑第一遍镜像把 data/*/layers.json 抓下来", file=sys.stderr)
        return 1

    n_img = n_tile = 0
    kept = set()
    per_reserve = {}
    for p in files:
        rid = os.path.basename(os.path.dirname(p))
        if a.reserves and rid not in a.reserves:
            continue
        kept.add(rid)
        imgs, til = urls_for_reserve(p, a.base, a.tiles, a.images)
        n_img += len(imgs)
        n_tile += len(til)
        per_reserve[rid] = imgs + til

    if a.split_dir:
        os.makedirs(a.split_dir, exist_ok=True)
        for rid, urls in sorted(per_reserve.items()):
            out = os.path.join(a.split_dir, f"{rid}.txt")
            with open(out, "w", encoding="utf-8", newline="\n") as f:
                f.write("\n".join(urls) + ("\n" if urls else ""))
            print(f"[gen_urls] {out}: {len(urls)} 个 URL", file=sys.stderr)
    else:
        out = []
        for rid in sorted(per_reserve):
            out += per_reserve[rid]
        sys.stdout.write("\n".join(out) + ("\n" if out else ""))
        sys.stdout.flush()

    print(
        f"[gen_urls] 保护区 {len(kept)} 个 → 热力图 {n_img} 张，瓦片 {n_tile} 张，"
        f"共计 {n_img + n_tile} 个 URL",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
