import requests
import time
import json
from urllib.parse import urlencode

def get_live_stream_url():
    """
    从指定API获取直播流的m3u8地址并返回。
    """
    # 当前时间戳
    t = int(time.time())
    
    # ==================== API 接口配置 ====================
    # 您可以切换注释来测试不同的API
    # API 1 (带参数)
    # api_url = f"https://lwyd.xichongtv.cn//a/appLive/findHotLiveList?{urlencode({'number': 6, 'areaId': 907, 'deviceVersionType': 'h5', 'vt': str(t) + str(t)})}"
    
    # API 2 (您代码中实际使用的)
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
    
    # 请求头，模拟手机客户端
    headers = {
        'User-Agent': 'okhttp/3.12.12', # 模拟安卓APP的请求
        # 'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    }
    
    # ==================== 发送请求 ====================
    try:
        response = requests.get(
            api_url,
            params=params,  # GET 请求的参数
            headers=headers,
            verify=False,   # 忽略SSL证书验证 (对应PHP的 CURLOPT_SSL_VERIFYPEER)
            timeout=10      # 设置超时
        )
        
        # 检查HTTP状态码
        response.raise_for_status()
        
        # ==================== 解析JSON ====================
        try:
            data = response.json()  # 将响应内容解析为JSON
        except json.JSONDecodeError:
            print("错误：API返回的内容不是有效的JSON格式。")
            print("返回内容预览：", response.text[:200])
            return None
        
        # ==================== 提取m3u8地址 ====================
        # 根据您的PHP代码，路径是 data -> m3u8Url
        if 'data' in data and 'm3u8Url' in data['data']:
            m3u8_url = data['data']['m3u8Url']
            print(f"成功获取直播流地址: {m3u8_url}")
            return m3u8_url
        else:
            print("错误：在返回的JSON数据中未找到 'data.m3u8Url' 字段。")
            print("完整返回数据：", json.dumps(data, ensure_ascii=False, indent=2))
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"请求过程中发生错误: {e}")
        return None

def main():
    """
    主函数：获取直播流地址并打印（模拟重定向）。
    """
    print("正在请求直播源API...")
    m3u8_url = get_live_stream_url()
    
    if m3u8_url:
        # 在Web环境中，这里应该发送一个HTTP 302重定向
        # 例如在Flask中: return redirect(m3u8_url)
        # 在纯Python脚本中，我们打印出来，您可以手动在播放器中打开
        print("\n" + "="*50)
        print("✅ 操作完成！")
        print(f"请在VLC、PotPlayer等播放器中打开以下地址进行播放：")
        print(m3u8_url)
        print("="*50)
    else:
        print("❌ 未能获取到有效的直播流地址。")

# ============ 运行程序 ============
if __name__ == "__main__":
    main()