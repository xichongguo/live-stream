# get_live_stream.py
import requests
import time
import json
import os

def get_live_stream_url():
    t = int(time.time())
    
    api_url = "https://lwydapi.xichongtv.cn/a/appLive/info/35137_b14710553f9b43349f46d33cc2b7fcfd"
    params = {
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
    
    headers = {
        'User-Agent': 'okhttp/3.12.12',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    }
    
    try:
        response = requests.get(
            api_url,
            params=params,
            headers=headers,
            verify=False,
            timeout=10
        )
        response.raise_for_status()
        
        data = response.json()
        
        if 'data' in data and 'm3u8Url' in data['data']:
            m3u8_url = data['data']['m3u8Url']
            print(f"✅ 成功获取直播流地址: {m3u8_url}")
            return m3u8_url
        else:
            print("❌ 未找到 m3u8Url 字段")
            return None
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None

def main():
    print("🚀 开始获取直播源...")
    m3u8_url = get_live_stream_url()
    
    if m3u8_url:
        # 创建 live 目录
        os.makedirs('live', exist_ok=True)
        
        # 写入 current.m3u8 文件
        with open('live/current.m3u8', 'w') as f:
            f.write(m3u8_url)
        
        print(f"🎉 已更新直播源文件: live/current.m3u8")
    else:
        print("❌ 获取失败，文件未更新。")

if __name__ == "__main__":
    main()