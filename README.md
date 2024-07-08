# CCTVDownloader

## 干什么用的

给朋友的妹妹写的一个脚本，用于批量下载央视某个频道的视频，比方说下面这个频道。

```html
https://tv.cctv.com/lm/gzsbqlx/index.shtml
```

坦白来说我是从来没有见过这么奇怪的需求, 怎么会有人把 CCTV 当成 CCAV 看。

![screenshot](https://github.com/by-justin/cctvdownloader/blob/main/imgs/screenshot.png?raw=true)

## 怎么用

用 Docker 部署。

```
git clone https://github.com/by-justin/cctvdownloader
docker build -t cctvdownloader .
docker run --rm -v ./data:/data cctvdownloader python3 /app/main.py --help
```

因为某些奇怪的原因, 国内访问会 403，要代理 `hls.cntv.cdn20.com`。在 clash 里面添加

```clash
DOMAIN-SUFFIX, hls.cntv.cdn20.com, PROXY
```

Enjoy!
