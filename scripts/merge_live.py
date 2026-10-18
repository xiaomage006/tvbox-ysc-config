#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CI 用：把上游自动更新项目的公网源并入，生成 live/tv.txt。

设计要点：
- live/core.txt 是本地实测过的核心清单，CI 只读不改。
- CI 运行在 GitHub 海外机器，无法验证各省 ISP 单播地址，所以只并入
  "域名型"（公网 CDN）的流，跳过裸 IP 型单播。
- 输出 live/tv.txt = core.txt + 「上游备用」分组。
"""
import ipaddress
import re
import ssl
import sys
import urllib.error
import urllib.request
from urllib.parse import urlparse

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"

UPSTREAMS = [
    ("ssili126/tv", "https://raw.githubusercontent.com/ssili126/tv/main/itvlist.txt"),
    ("vbskycn/iptv", "https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.txt"),
    ("iptv-org/cn", "https://iptv-org.github.io/iptv/countries/cn.m3u"),
]


def fetch(url, timeout=30):
    r = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(r, timeout=timeout, context=CTX) as x:
        return x.read().decode("utf-8", "replace")


def is_public_domain(url):
    """只接受域名主机的流，跳过裸 IP 单播与 IPv6 地址。"""
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return False
    if not host:
        return False
    if host.startswith("["):
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    if "." not in host:
        return False
    # 本地/保留
    if host in ("localhost",):
        return False
    return True


def parse_txt(text):
    out, group = [], ""
    for l in text.splitlines():
        l = l.strip()
        if not l:
            continue
        if l.endswith(",#genre#"):
            group = l[:-8].strip(",").strip()
            continue
        if "," in l and "http" in l:
            name, url = l.split(",", 1)
            out.append((name.strip(), url.strip()))
    return out


def parse_m3u(text):
    out, cur = [], ""
    for l in text.splitlines():
        l = l.strip()
        if l.startswith("#EXTINF"):
            m = re.search(r'tvg-name="([^"]+)"', l)
            cur = m.group(1).strip() if m else l.rsplit(",", 1)[-1].strip()
        elif l and not l.startswith("#") and cur:
            out.append((cur, l))
            cur = ""
    return out


def main():
    core = []
    try:
        core = [l.rstrip("\n") for l in open("live/core.txt", encoding="utf-8") if l.strip()]
    except FileNotFoundError:
        print("warning: live/core.txt missing")

    core_urls = {l.split(",", 1)[1] for l in core if "," in l and "http" in l}

    seen = set(core_urls)
    extra = []
    for name, url in UPSTREAMS:
        try:
            txt = fetch(url)
        except Exception as e:
            print("skip %s (%s)" % (name, type(e).__name__))
            continue
        items = parse_m3u(txt) if txt.lstrip().startswith("#EXTM3U") else parse_txt(txt)
        added = 0
        for ch, u in items:
            if u in seen:
                continue
            if not is_public_domain(u):
                continue
            seen.add(u)
            extra.append((ch, u))
            added += 1
        print("%s: %d candidates, +%d public" % (name, len(items), added))

    out = list(core)
    if extra:
        out.append("上游备用,#genre#")
        for ch, u in extra:
            out.append("%s,%s" % (ch, u))

    with open("live/tv.txt", "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")
    print("live/tv.txt: %d lines (core %d + extras %d)" % (len(out), len(core), len(extra)))


if __name__ == "__main__":
    main()
