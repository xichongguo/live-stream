# -*- coding: utf-8 -*-
import requests
import hashlib
import time
import os
import json

class IPTVUpdater:
    def __init__(self):
        # --- 南充/西充 配置 ---
        self.json_url = "http://kstatic.sctvcloud.com/static/N1300/list/1835203958696394753.json"
        self.secret_key = "5df6d8b743257e0e38b869a07d8819d2"
        self.base_domain = "https://ncpull.cnncw.cn"
        
        # --- 央视 (CCTV) 公共源配置 ---
        # 使用了通用的公共源，确保CCTV-1等频道有效
        self.cctv_sources = {
            "CCTV-1": "http://ivi.bupt.edu.cn/hls/cctv1.m3u8",
            "CCTV-2": "http://ivi.bupt.edu.cn/hls/cctv2.m3u8",
            "CCTV-3": "http://ivi.bupt.edu.cn/hls/cctv3.m3u8",
            "CCTV-4": "http://ivi.bupt.edu.cn/hls/cctv4.m3u8",
            "CCTV-5": "http://ivi.bupt.edu.cn/hls/cctv5.m3u8",
            "CCTV-5+": "http://ivi.bupt.edu.cn/hls/cctv5plus.m3u8",
            "CCTV-6": "http://ivi.bupt.edu.cn/hls/cctv6.m3u8",
            "CCTV-7": "http://ivi.bupt.edu.cn/hls/cctv7.m3u8",
            "CCTV-8": "http://ivi.bupt.edu.cn/hls/cctv8.m3u8",
            "CCTV-9": "http://ivi.bupt.edu.cn/hls/cctv9.m3u8",
            "CCTV-10": "http://ivi.bupt.edu.cn/hls/cctv10.m3u8",
            "CCTV-11": "http://ivi.bupt.edu.cn/hls/cctv11.m3u8",
            "CCTV-12": "http://ivi.bupt.edu.cn/hls/cctv12.m3u8",
            "CCTV-13": "http://ivi.bupt.edu.cn/hls/cctv13.m3u8",
            "CCTV-14": "http://ivi.bupt.edu.cn/hls/cctv14.m3u8",
            "CCTV-15": "http://ivi.bupt.edu.cn/hls/cctv15.m3u8",
            "CCTV-16": "http://ivi.bupt.edu.cn/hls/cctv16.m3u8",
            "CCTV-4K": "http://ivi.bupt.edu.cn/hls/cctv4k.m3u8",
            "CCTV-8K": "http://ivi.bupt.edu.cn/hls/cctv8k.m3u8",
            "CCTV-News": "http://ivi.bupt.edu.cn/hls/cctvnews.m3u8",
            "CCTV-Français": "http://ivi.bupt.edu.cn/hls/cctvfrancais.m3u8",
            "CCTV-العربية": "http://ivi.bupt.edu.cn/hls/cctvalarabiya.m3u8",
            "CCTV-Русский": "http://ivi.bupt.edu.cn/hls/cctvryssiya.m3u8",
            "CCTV-Español": "http://ivi.bupt.edu.cn/hls/cctvespanol.m3u8",
        }
        
        # --- 输出配置 ---
        self.output_dir = "live"
        self.output_file = os.path.join(self.output_dir, "current.m3u8")
        
        # 请求头伪装
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    def generate_signature(self, path, timestamp):
        """核心算法：MD5(密钥 + 路径 + 时间戳)"""
        raw_string = f"{self.secret_key}{path}{timestamp}"
        return hashlib.md5(raw_string.encode('utf-8')).hexdigest()

    def get_dynamic_channels(self):
        """获取南充/西充动态频道"""
        channels = []
        try:
            print(f"🚀 正在连接南充服务器获取频道列表...")
            response = requests.get(self.json_url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("isSuccess"):
                    # 解析 JSON 结构找到频道列表
                    items = data["data"][0]["propValue"]["children"][0]["dataList"]
                    
                    # 设置过期时间：当前时间 + 2小时 (7200秒)
                    expire_time = int(time.time()) + 7200
                    
                    for item in items:
                        title = item.get("title")
                        # 优先处理：南充综合、南充科教
                        if "南充综合" in title or "南充科教" in title:
                            try:
                                # 尝试从 liveStream 字段提取 ID
                                live_stream = item.get("liveStream", "")
                                # 正则提取 ID，格式通常是 /live/{id}/playlist.m3u8
                                import re
                                match = re.search(r'/live/([^/]+)/playlist\.m3u8', live_stream)
                                channel_id = match.group(1) if match else None
                                
                                # 如果正则没提取到，尝试从 URL 分割
                                if not channel_id:
                                    parts = live_stream.split("/")
                                    channel_id = parts[parts.index("live") + 1] if "live" in parts else None
                                
                                if channel_id:
                                    # 构造路径
                                    path = f"/live/{channel_id}/playlist.m3u8"
                                    # 计算签名
                                    ws_secret = self.generate_signature(path, expire_time)
                                    # 拼接最终地址
                                    final_url = f"{self.base_domain}{path}?wsSecret={ws_secret}&wsTime={expire_time}"
                                    
                                    # 确定分组
                                    group = "本地节目" if "南充" in title else "本地节目"
                                    
                                    channels.append({
                                        "name": title,
                                        "url": final_url,
                                        "group": group
                                    })
                                    print(f"✅ 成功生成: {title}")
                                else:
                                    print(f"❌ 无法提取 ID: {title}")
                            except Exception as e:
                                print(f"❌ 处理频道失败 {title}: {e}")
                                
                else:
                    print(f"❌ API返回错误: {data.get('msg')}")
            else:
                print(f"❌ 网络请求失败，状态码: {response.status_code}")
                
        except Exception as e:
            print(f"❌ 获取南充源时发生异常: {e}")
        
        return channels

    def get_cctv_channels(self):
        """获取央视频道列表"""
        channels = []
        for name, url in self.cctv_sources.items():
            channels.append({
                "name": name,
                "url": url,
                "group": "央视"
            })
        print(f"✅ 已加载 {len(self.cctv_sources)} 个央视频道")
        return channels

    def write_to_m3u8(self, channels):
        """写入 M3U8 文件"""
        # 创建目录
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        with open(self.output_file, 'w', encoding='utf-8') as f:
            # 写入 M3U 头部
            f.write('#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml.gz"\n')
            
            # 按分组写入 (先写央视，再写本地)
            # 这里简单按列表顺序，你可以调整 get_channels 的顺序
            for channel in channels:
                f.write(f'#EXTINF:-1 tvg-name="{channel["name"]}" group-title="{channel["group"]}",{channel["name"]}\n')
                f.write(f'{channel["url"]}\n')
        
        print(f"\n🎉 合并完成！文件已保存至: {os.path.abspath(self.output_file)}")
        print(f"📺 共写入 {len(channels)} 个频道")

    def run(self):
        """主运行函数"""
        all_channels = []
        
        # 1. 获取南充动态源
        nanchong_channels = self.get_dynamic_channels()
        all_channels.extend(nanchong_channels)
        
        # 2. 获取央视源
        cctv_channels = self.get_cctv_channels()
        all_channels.extend(cctv_channels)
        
        # 3. 写入文件
        self.write_to_m3u8(all_channels)

if __name__ == "__main__":
    updater = IPTVUpdater()
    updater.run()
    
    print("\n💡 提示：按任意键退出...")
    input()
