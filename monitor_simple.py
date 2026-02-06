#!/usr/bin/env python3
"""
雪球舆情监控 - 简化版（直接展示结果）
"""
import subprocess
import json
import time
import re
from datetime import datetime

SYMBOLS = [
    ("SH600118", "中国卫星"),
    ("SZ002155", "湖南黄金"),
    ("SZ300456", "赛微电子"),
    ("SH600879", "航天电子"),
    ("SZ002565", "顺灏股份"),
]

def get_sentiment(text):
    """简单情绪判断"""
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

def fetch_one(symbol, name):
    """抓取单只股票"""
    url = f'https://xueqiu.com/query/v1/symbol/search/status?symbol={symbol}&count=15&comment=0'
    
    try:
        # 打开页面
        result = subprocess.run(
            ['openclaw', 'browser', 'open', url],
            capture_output=True, text=True, timeout=30
        )
        
        match = re.search(r'id:\s*([A-F0-9]+)', result.stdout)
        if not match:
            return []
        
        target_id = match.group(1)
        time.sleep(2)
        
        # 获取内容
        result = subprocess.run(
            ['openclaw', 'browser', 'snapshot', '--target-id', target_id],
            capture_output=True, text=True, timeout=30
        )
        
        # 关闭页面
        subprocess.run(
            ['openclaw', 'browser', 'close', '--target-id', target_id],
            capture_output=True, timeout=10
        )
        
        # 提取JSON
        generic_match = re.search(r'generic \[ref=[^\]]+\]: "({.*?})"', result.stdout, re.DOTALL)
        if not generic_match:
            return []
        
        json_str = generic_match.group(1).replace('\\"', '"').replace('\\n', '\n')
        data = json.loads(json_str)
        
        posts = data.get('list', [])
        results = []
        
        for post in posts[:5]:  # 只取前5条
            text = re.sub(r'<[^>]+>', '', post.get('text', ''))
            text = text.replace('&nbsp;', ' ').replace('&quot;', '"').strip()
            
            # 提取时间
            ts = post.get('created_at', 0)
            dt = datetime.fromtimestamp(ts / 1000)
            time_str = dt.strftime("%H:%M")
            
            results.append({
                'text': text[:100] + '...' if len(text) > 100 else text,
                'time': time_str,
                'sentiment': get_sentiment(text),
                'author': post.get('user', {}).get('screen_name', '匿名')
            })
        
        return results
        
    except Exception as e:
        print(f"   错误: {e}")
        return []

# 主程序
print("="*70)
print("🐧 雪球舆情监控报告")
print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*70)

for symbol, name in SYMBOLS:
    print(f"\n📈 {name} ({symbol})")
    print("-"*70)
    
    posts = fetch_one(symbol, name)
    
    if posts:
        for i, post in enumerate(posts, 1):
            print(f"\n  {i}. {post['sentiment']} | {post['time']} | {post['author']}")
            print(f"     {post['text']}")
    else:
        print("   暂无数据")
    
    time.sleep(1.5)

print("\n" + "="*70)
print("✅ 监控完成")
print("="*70)
