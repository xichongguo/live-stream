# get_live_stream.py
import requests
import os
import json
from datetime import datetime

# 创建输出目录
os.makedirs('live', exist_ok=True)

# ✅ 替换为可用的中文频道 JSON 数据源
CHANNELS_URL = "https://cdn.jsdelivr.net/gh/jihuidian/cn_broadcast@latest/channels.json"

def load_whitelist():
    """加载白名单"""
    if not os.path.exists('whitelist.txt'):
        print("⚠️ 未找到 whitelist.txt，将处理所有频道")
        return None
    with open('whitelist.txt', 'r', encoding='utf-8') as f:
        keywords = [line.strip() for line in f if line.strip()]
    return keywords

def filter_channels_by_whitelist(channels, keywords):
    """根据白名单过滤频道"""
    if not keywords:
        return channels
    filtered = []
    for ch in channels:
        name = ch.get('name', '').lower()
        if any(keyword.lower() in name for keyword in keywords):
            filtered.append(ch)
    print(f"✅ 白名单过滤后保留 {len(filtered)} 个频道")
    return filtered

def generate_m3u8_content(channels):
    """生成 M3U8 内容"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "#EXTM3U",
        f"# Generated at: {timestamp}",
        "# Source: jihuidian/cn_broadcast"
    ]
    current_group = None

    for ch in channels:
        name = ch.get("name", "Unknown")
        group = ch.get("group", "Other")
        logo = ch.get("logo", "")
        url = ch.get("url", "")

        if not url or not name:
            continue

        # 分组
        if group != current_group:
            lines.append(f"#EXTGRP:{group}")
            current_group = group

        # EXTINF 行
        lines.append(f"#EXTINF:-1 tvg-name=\"{name}\" group-title=\"{group}\",{name}")
        if logo:
            lines.append(f"#EXTVLCOPT:logo={logo}")
        lines.append(url)

    return "\n".join(lines) + "\n"

def generate_html_player():
    """生成简单的 HTML 播放器"""
    html = """<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
    <title>📺 直播播放器</title>
    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
    <script src="https://cdn.jsdelivr.net/npm/clappr@latest/dist/clappr.min.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f4f4f4; }
        #player { width: 100%; height: 80vh; max-width: 1000px; margin: 0 auto; }
        h1 { text-align: center; color: #333; }
        .info { text-align: center; color: #666; font-size: 0.9em; }
    </style>
</head>
<body>
    <h1>📺 直播播放器</h1>
    <div id="player"></div>
    <p class="info">自动加载 <code>current.m3u8</code> 列表</p>
    <script>
        const player = new Clappr.Player({
            source: './current.m3u8',
            parentId: '#player',
            autoPlay: false,
            mimeType: 'application/x-mpegurl',
            plugins: [HlsjsPlayback],
            playback: { hlsjsConfig: { backBufferLength: 90 } }
        });
    </script>
</body>
</html>"""
    if not keywords:with open('live/index.html', 'w', encoding='utf-8') as f:
        返回频道write(html)
    过滤后 = []print("✅ HTML 播放器已生成")

def        name = ch.get('name', '').lower()main():
        if any(keyword.lower() in name for keyword in keywords):print("🚀 开始获取直播源...")
            filtered.append(ch)load_whitelist()

    返回过滤结果try:
        response = requests.get(CHANNELS_URL, timeout=15)
        response.raise_for_status()
    时间戳 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")json()

    当前组 = 无# 注意：这个 JSON 是 { "channels": [...] } 格式
        channels = data.get("channels", [])
    对于 channels 中的 ch：print(f"✅ 成功获取 {len(channels)} 个频道")

        filtered = filter_channels_by_whitelist(channels, keywords)
        m3u8_content = generate_m3u8_content(filtered)

        with open('live/current.m3u8', 'w', encoding='utf-8') as f:
            f.write(m3u8_content)
        print(f"✅ 已生成 live/current.m3u8 ({len(filtered)} 个频道)")

        generate_html_player()

    except Exception as e:
        print(f"❌ 执行失败: {e}")

if __name__ == "__main__":
    main()
