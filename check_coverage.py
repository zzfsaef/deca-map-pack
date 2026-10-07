#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_coverage.py —— 抓完之后对账：清单里的图片，到底有多少真的落到 site/ 里了。

mirror_site.py 的立场是「下到东西就算成功，个别 404 不拖垮流水线」，
这对着单个站点没问题，但按地图发包时很危险：抓一半也能打出一个包，
用户下回去以为是完整地图。所以在打包之前卡一道覆盖率。

用法:
    python check_coverage.py --site site --list assets.txt
    python check_coverage.py --site site --list assets.txt --min 0.98 --missing-out missing.txt
"""

import argparse
import os
import sys
import urllib.parse

DEFAULT_PREFIX = "/deca/hp/"


def local_path(site, prefix, url):
    """URL -> 本地文件：和 mirror_site.py 一样，按 URL 路径原样落到 site/ 下。

    data/r6/t_topo/0/0/0.png 这种是相对站点根的，拼出来是 /deca/hp/data/r6/...，
    所以这里要用完整路径，不能只砍掉前缀。——否则永远对不上账。
    """
    path = urllib.parse.unquote(urllib.parse.urlsplit(url).path or "")
    if not path.startswith(prefix):
        return None
    return os.path.join(site, *path.lstrip("/").split("/"))


def main(argv=None):
    ap = argparse.ArgumentParser(description="校验图片覆盖率")
    ap.add_argument("--site", default="site")
    ap.add_argument("--list", required=True, help="gen_urls.py 生成的清单")
    ap.add_argument("--prefix", default=DEFAULT_PREFIX,
                    help="站点根路径前缀，只对账这个前缀下的 URL（默认 /deca/hp/）")
    ap.add_argument("--min", type=float, default=0.98, help="覆盖率低于这个就失败（默认 0.98）")
    ap.add_argument("--missing-out", default=None, help="把没抓到的 URL 写到这个文件")
    ap.add_argument("--quiet", action="store_true", help="只输出一行结果")
    a = ap.parse_args(argv)

    with open(a.list, encoding="utf-8") as f:
        urls = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    if not urls:
        print(f"[check] {a.list} 是空的，没法对账", file=sys.stderr)
        return 1

    missing, skipped = [], 0
    for u in urls:
        p = local_path(a.site, a.prefix, u)
        if p is None:
            skipped += 1
            continue
        if not os.path.isfile(p) or os.path.getsize(p) == 0:
            missing.append(u)

    checked = len(urls) - skipped
    got = checked - len(missing)
    rate = got / checked if checked else 0.0
    print(f"[check] 清单 {len(urls)} 条 → 已抓 {got}，缺 {len(missing)}，覆盖率 {rate:.2%}")
    if skipped:
        print(f"[check] 有 {skipped} 条不在 {a.prefix} 下，跳过（不计入覆盖率）", file=sys.stderr)
    if missing and not a.quiet:
        print("[check] 缺失样例：")
        for u in missing[:10]:
            print("   ", u)
    if a.missing_out:
        with open(a.missing_out, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(missing) + ("\n" if missing else ""))

    if rate < a.min:
        print(f"[check] 覆盖率 {rate:.2%} < {a.min:.0%}，先别发包，重跑一次抓取", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
