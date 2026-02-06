#!/usr/bin/env python3
"""
抓取雪球快讯数据
API: /statuses/livenews/list.json
快讯是情绪突变信号的重要来源
"""

import requests
import json
import sys
import os
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import BASE_URL, HEADERS, COOKIES, REQUEST_TIMEOUT, LIVENEWS_COUNT

def fetch_livenews(count=50):
    """
    获取最新快讯
    
    Args:
        count: 获取数量
    
    Returns:
        list: 快讯列表
    """
    url = f"{BASE_URL}/statuses/livenews/list.json"
    params = {"count": count}
    
    try:
        print("📡 正在获取雪球快讯...")
        r = requests.get(
            url, 
            headers=HEADERS, 
            cookies=COOKIES, 
            params=params, 
            timeout=REQUEST_TIMEOUT
        )
        r.raise_for_status()
        
        data = r.json()
        return data.get("items", [])
        
    except Exception as e:
        print(f"❌ 获取快讯失败: {e}")
        return []

def fetch_recent_livenews(hours=2):
    """
    获取最近N小时的快讯
    
    Args:
        hours: 小时数
    
    Returns:
        list: 快讯列表
    """
    all_news = []
    count = 100  # 多取一些
    
    while len(all_news) < 50:  # 至少50条
        news = fetch_livenews(count)
        if not news:
            break
        
        # 过滤时间
        cutoff = datetime.now().timestamp() - hours * 3600
        recent = [n for n in news if n.get("created_at", 0) / 1000 > cutoff]
        
        if recent:
            all_news.extend(recent)
            break
        else:
            # 没有最近的，快讯可能在其他端
            all_news.extend(news[:50])
            break
    
    return all_news[:100]  # 最多100条

if __name__ == "__main__":
    print("=" * 60)
    print("📰 雪球快讯抓取")
    print("=" * 60)
    
    news = fetch_livenews()
    
    print(f"\n✅ 获取 {len(news)} 条快讯")
    
    # 保存
    with open("/tmp/xueqiu_livenews_raw.json", "w", encoding="utf-8") as f:
        json.dump(news, f, ensure_ascii=False, indent=2)
    
    print("💾 已保存到 /tmp/xueqiu_livenews_raw.json")
    
    # 显示最新5条
    if news:
        print("\n📋 最新快讯:")
        for i, n in enumerate(news[:5], 1):
            text = n.get("text", "")[:50]
            print(f"  {i}. {text}...")
