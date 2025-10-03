# get_live_stream.py
"""
功能：从API获取直播流 + 远程白名单 → 生成 M3U8 播放列表
输出文件：live/current.m3u8
"""

import requests
import time
import json
import os
from urllib.parse import urlencode

# ================== 配置区 ==================

# 【1. 动态直播流 API 配置】
API_URL = "https://lwydapi.xichongtv.cn/a/appLive/info/35137_b14710553f9b43349f46d33cc2b7fcfd"
PARAMS = {
    'deviceType': '1',
    'centerId': '9',
    'deviceToken': 'beb09666-78c0-4ae8-94e9-b0b4180a31be',
    'latitudeValue': '0',
    'areaId': '907',
    'appCenterId': '907',
    'isTest': '0',
    'longitudeValue': '0',
    'deviceVersionType': 'android',
    'versionCodeGlobal': '5009037'
}
HEADERS = {
    'User-Agent': 'okhttp/3.12.12',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
}

# 【2. 远程白名单配置】
REMOTE_WHITELIST_URL = "https://raw.githubusercontent.com/xichongguo/live-stream/main/whitelist.txt"
WHITELIST_TIMEOUT = 10  # 请求超时时间（秒）

# 【3. 本地备用白名单】（远程失败时使用）
FALLBACK_WHITELIST = [
    ("备用-央视一套", "https://cctv1.live.com/index.m3u8"),
    ("备用-测试流", "http://devstreaming.apple.com/videos/streaming/examples/bipbop_4x3/gear1/prog_index.m3u8"),
]

# ================== 核心函数 ==================

def get_dynamic_stream():
    """
    从指定API获取直播流的m3u8地址并返回。
    """
    print("📡 正在请求直播源 API...")

    try:
        response = requests.get(
            API_URL,
            params=PARAMS,
            headers=HEADERS,
            verify=False,
            timeout=10
        )
        response.raise_for_status()

        try:
            data = response.json()
        except json.JSONDecodeError:
            print("❌ 错误：API返回的内容不是有效的JSON格式。")
            print("返回内容预览：", response.text[:200])
            return None

        if 'data' in data and 'm3u8Url' in data['data']:
            m3u8_url = data['data']['m3u8Url']
            print(f"✅ 成功获取动态直播流: {m3u8_url}")
            return m3u8_url
        else:
            print("❌ 错误：在返回的JSON数据中未找到 'data.m3u8Url' 字段。")
            print("完整返回数据：", json.dumps(data, ensure_ascii=False, indent=2))
            return None

    except requests.exceptions.RequestException as e:
        print(f"❌ 请求过程中发生错误: {e}")
        return None


def load_whitelist_from_remote():
    """
    从远程 URL 加载白名单
    :return: [(name, url)] 列表
    """
    print(f"🌐 正在加载远程白名单: {REMOTE_WHITELIST_URL}")
    try:
        response = requests.get(REMOTE_WHITELIST_URL, timeout=WHITELIST_TIMEOUT)
        response.raise_for_status()
        lines = response.text.strip().splitlines()
        whitelist = []
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue  # 跳过空行和注释
            if "," not in line:
                print(f"⚠️ 第 {line_num} 行格式错误（缺少逗号）: {line}")
                continue
            try:
                name, url = line.split(",", 1)
                name, url = name.strip(), url.strip()
                if not name or not url:
                    print(f"⚠️ 第 {line_num} 行名称或URL为空: {line}")
                    continue
                if not url.startswith(("http://", "https://")):
                    print(f"⚠️ 第 {line_num} 行URL无效: {url}")
                    continue
                whitelist.append((name, url))
            except Exception as e:
                print(f"⚠️ 解析第 {line_num} 行失败: {e}")
        print(f"✅ 成功加载 {len(whitelist)} 个远程直播源")
        return whitelist
    except Exception as e:
        print(f"❌ 加载远程白名单失败: {e}")
        return None


def get_whitelist():
    """
    获取白名单：优先远程，失败时使用本地备用
    """
    remote_list = load_whitelist_from_remote()
    if remote_list is not None and len(remote_list) > 0:
        return remote_list
    else:
        print("⚠️ 使用本地备用白名单")
        return FALLBACK_WHITELIST


def generate_m3u8_content(dynamic_url, whitelist):
    """
    生成标准 M3U8 播放列表内容
    """
    lines = ["#EXTM3U"]

    if dynamic_url:
        lines.append("#EXTINF:-1,自动获取流")
        lines.append(dynamic_url)

    for name, url in whitelist:
        lines.append(f"#EXTINF:-1,白名单-{name}")
        lines.append(url)

    return "\n".join(lines) + "\n"


def main():
    """
    主函数：获取直播流、生成 M3U8、写入文件
    """
    print("🚀 开始生成直播源播放列表...")

    # 创建输出目录
    os.makedirs('live', exist_ok=True)
    print("📁 已确保 live/ 目录存在")

    # 获取动态流
    dynamic_url = get_dynamic_stream()

    # 获取白名单（远程 + fallback）
    whitelist = get_whitelist()

    # 生成 M3U8 内容
    m3u8_content = generate_m3u8_content(dynamic_url, whitelist)

    # 写入文件
    output_path = 'live/current.m3u8'
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(m3u8_content)
        print(f"🎉 成功生成播放列表: {output_path}")
        print(f"📊 总计包含 {len(whitelist) + (1 if dynamic_url else 0)} 个直播源")
    except Exception as e:
        print(f"❌ 写入文件失败: {e}")
        return

    # 确保 .nojekyll 文件存在
    nojekyll_path = '.nojekyll'
    if not os.path.exists(nojekyll_path):
        try:
            open(nojekyll_path, 'w').close()
            print(f"✅ 已创建 {nojekyll_path} 文件")
        except Exception as e:
            print(f"⚠️ 创建 .nojekyll 文件失败: {e}")

    print("✅ 所有任务完成！")


# ============ 运行程序 ============
if __name__ == "__main__":
    main()
