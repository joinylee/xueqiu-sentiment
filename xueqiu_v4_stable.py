#!/usr/bin/env python3
"""
雪球舆情监控 - V4 稳定版
使用 browser + 正确解析 JSON
"""

import subprocess
import json
import re
import time
import os
from datetime import datetime
from typing import List, Dict

# ============ 配置 ============
SYMBOLS = [
    ("SH600118", "中国卫星"),
    ("SZ002155", "湖南黄金"),
    ("SZ300456", "赛微电子"),
    ("SH600879", "航天电子"),
    ("SZ002565", "顺灏股份"),
]

OUTPUT_DIR = "/Users/joinylee/Openclaw/xueqiu_sentiment/reports"
MAX_PAGES = 3

def analyze_sentiment(text: str) -> str:
    bullish = ['涨', '利好', '看好', '买入', '突破', '强势', '新高', '做多', '抄底', '拉升']
    bearish = ['跌', '利空', '看空', '卖出', '破位', '弱势', '新低', '做空', '割肉', '汪汪', '割了', '打压']
    text = text.lower()
    bull = sum(1 for w in bullish if w in text)
    bear = sum(1 for w in bearish if w in text)
    if bull > bear:
        return "🟢 利多"
    elif bear > bull:
        return "🔴 利空"
    return "⚪ 中性"

def fetch_posts_browser(symbol: str, page: int = 1) -> List[Dict]:
    """使用 browser 抓取数据"""
    timestamp = int(time.time() * 1000)
    url = f"https://xueqiu.com/statuses/search.json?count=20&comment=0&symbol={symbol}&hl=0&source=user&sort=time&page={page}&_={timestamp}"
    
    try:
        # 打开页面
        r1 = subprocess.run(
            ['openclaw', 'browser', 'open', url],
            capture_output=True, text=True, timeout=30
        )
        
        # 提取 target_id
        match = re.search(r'id:\s*([A-F0-9]+)', r1.stdout)
        if not match:
            return []
        
        target_id = match.group(1)
        time.sleep(2)
        
        # 获取快照
        r2 = subprocess.run(
            ['openclaw', 'browser', 'snapshot', '--target-id', target_id],
            capture_output=True, text=True, timeout=30
        )
        
        # 关闭页面
        subprocess.run(
            ['openclaw', 'browser', 'close', '--target-id', target_id],
            capture_output=True, timeout=10
        )
        
        # 解析 JSON - 格式: - generic [ref=e2]: "{...}"
        line = r2.stdout.strip()
        
        # 找到 ": " 后面的内容
        if ': "' not in line:
            return []
        
        # 提取 JSON 字符串（去掉外层引号）
        json_str = line.split(': "', 1)[1]
        if json_str.endswith('"'):
            json_str = json_str[:-1]
        
        # 反转义
        json_str = json_str.replace('\\"', '"').replace('\\n', '\n').replace('\\\\', '\\')
        
        data = json.loads(json_str)
        return data.get('list', [])
        
    except Exception as e:
        print(f"   错误: {str(e)[:50]}")
        return []

def fetch_stock(symbol: str, name: str) -> List[Dict]:
    """抓取单只股票"""
    print(f"\n📈 {name} ({symbol})")
    print("-" * 60)
    
    now_ts = datetime.now().timestamp() * 1000
    one_day_ms = 24 * 60 * 60 * 1000
    
    all_posts = []
    
    for page in range(1, MAX_PAGES + 1):
        print(f"   第 {page} 页...", end=" ")
        
        posts = fetch_posts_browser(symbol, page)
        if not posts:
            print("无数据")
            break
        
        valid = 0
        stop = False
        
        for post in posts:
            ts = post.get('created_at', 0)
            if now_ts - ts > one_day_ms:
                stop = True
                break
            
            text = re.sub(r'<[^>]+>', '', post.get('text', ''))
            text = text.replace('&nbsp;', ' ').replace('&quot;', '"').strip()
            
            if len(text) < 5:
                continue
            
            all_posts.append({
                'text': text,
                'author': post.get('user', {}).get('screen_name', '匿名'),
                'time': datetime.fromtimestamp(ts/1000).strftime('%m-%d %H:%M'),
                'sentiment': analyze_sentiment(text),
            })
            valid += 1
        
        print(f"{valid} 条")
        
        if stop:
            print(f"   ⏰ 超出24小时")
            break
        
        time.sleep(1.5)
    
    print(f"   ✅ 总计: {len(all_posts)} 条")
    return all_posts

def main():
    print("=" * 60)
    print("🐧 雪球舆情监控 - V4 稳定版")
    print(f"⏰ {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 60)
    
    all_data = {}
    for symbol, name in SYMBOLS:
        posts = fetch_stock(symbol, name)
        all_data[symbol] = posts
    
    # 保存
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    json_file = os.path.join(OUTPUT_DIR, f'xueqiu_{ts}.json')
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump({'time': datetime.now().isoformat(), 'data': all_data}, f, ensure_ascii=False, indent=2)
    
    # 打印摘要
    print("\n" + "=" * 60)
    print("📊 摘要")
    print("=" * 60)
    for symbol, name in SYMBOLS:
        posts = all_data.get(symbol, [])
        bull = len([p for p in posts if '利多' in p['sentiment']])
        bear = len([p for p in posts if '利空' in p['sentiment']])
        print(f"   {name}: {len(posts)}条 (🟢{bull} 🔴{bear})")
    
    print(f"\n💾 已保存: {json_file}")
    print("=" * 60)
    print("✅ 完成!")

if __name__ == "__main__":
    main()
