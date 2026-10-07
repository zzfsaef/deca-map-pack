分卷打包废案

## 下载（按地图分开打包）

Release 里不再是「一个几百 MB 的大包」，而是**每张地图一个包**：

| 资源 | 大小 | 说明 |
|---|---|---|
| `deca-map-base.zip` | 几 MB | 框架 + 界面汉化 + 全部地图的 JSON。**必下** |
| `deca-map-r6-育空河谷自然保护区.zip` | 几百 MB | 该地图的热力图 + 底图瓦片 |
| `deca-map-<保护区>-images.zip` | — | 单张地图超过 1.8GB 时才会出现：热力图部分 |
| `deca-map-<保护区>-tiles-N.zip` | — | 同上：底图瓦片分卷 |

用法：

```bash
# 1. 把 base 和你想要的地图包都解压到同一个目录，会自动拼出 site/
unzip deca-map-base.zip
unzip deca-map-r6-育空河谷自然保护区.zip

# 2. 起个本地服务（站点靠 JS 拼路径，别直接双击 html）
python -m http.server 8000 --directory site

# 3. 打开
#    http://localhost:8000/deca/hp/map.html
```

只解压了某几张地图的话，切到没下载的保护区会缺图 —— 再下对应的包即可，包之间互不覆盖。

## 脚本

| 脚本 | 干什么 |
|---|---|
| `mirror_site.py` | 多线程镜像静态站，可续传（已下过的文件跳过） |
| `gen_urls.py` | 照 `layers.json` 生成图片/瓦片清单；`--split-dir` 按保护区分开写 |
| `localize.py` | 界面汉化，只改显示文字，不动 id/url 等程序字段 |
| `patch_saveload.py` | 给 map.html 加「选择存档文件夹」按钮，绕开拖放 |
| `pack_maps.py` | 把 `site/` 按保护区分别打包（超 1.8GB 自动分卷） |
| `check_coverage.py` | 抓完后对账，覆盖率不到 98% 就判定这次抓取不算数 |

自己抓某一张图：

```bash
# 先拿到该保护区的三个 JSON
for f in reserve pois layers; do
  curl -sSL --create-dirs -o "site/deca/hp/data/r6/$f.json" \
    "https://www.mathartbang.com/deca/hp/data/r6/$f.json"
done

python gen_urls.py --site site --reserves r6 > assets.txt
python mirror_site.py --out site --prefix /deca/ --seeds-file assets.txt --jobs 8
python check_coverage.py --site site --list assets.txt      # 先看有没有抓全
python localize.py --site site
python pack_maps.py --site site --out dist --mode maps --reserves r6
```

## 自动化

`.github/workflows/mirror.yml`，**手动触发**（Actions → Run workflow，可填要抓哪些保护区）：

- `base` 任务：抓框架 + `/deca/lib/` + 各保护区的 JSON，汉化，打 `deca-map-base.zip`
- `maps` 任务：一个保护区一个任务（矩阵并发，默认 3 个一组），各自抓图、对账、打包、上传
- 某个保护区的图没抓全 → 这一步直接失败、不发包，免得半残的地图被当成完整的发出去

