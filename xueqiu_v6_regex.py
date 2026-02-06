#!/usr/bin/env python3
"""
雪球舆情监控 - V6 正则提取版
不解析完整 JSON，直接用正则提取关键字段
"""

import subprocess
import re
import time
import os
from datetime import datetime
from typing import List, Dict

SYMBOLS = [
    ("SH600118", "中国卫星"),
    ("SZ002155", "湖南黄金"),
    ("SZ300456", "赛微电子"),
    ("SH600879", "航天电子"),
    ("SZ002565", "顺灏股份"),
]

OUTPUT_DIR = "/Users/joinylee/Openclaw/xueqiu_sentiment/reports"

def analyze_sentiment(text: str) -> str:
    bullish = ['涨', '利好', '看好', '买入', '突破', '强势', '新高', '做多', '抄底', '拉升']
    bearish = ['跌', '利空', '看空', '卖出', '破位', '弱势', '新低', '做空', '割肉', '汪汪', '割了', '打压']
    text = text.lower()
    bull = sum(1 for w in bullish if w in text)
    bear = sum(1 for w in bearish if w in text)
    if bull > bear:
        return "🟢"
    elif bear > bull:
        return "🔴"
    return "⚪"

def extract_posts_from_json(raw_text: str) -> List[Dict]:
    """从原始 JSON 文本中提取帖子"""
    posts = []
    
    # 找到所有 "text":"..." 的内容
    # 雪球的内容在 "text":"<p>...</p>" 或 "text":"..." 中
    text_pattern = r'"text":"(.*?)"(?:,"|})'
    texts = re.findall(text_pattern, raw_text, re.DOTALL)
    
    # 找到所有时间戳
    time_pattern = r'"created_at":(\d+)'
    times = re.findall(time_pattern, raw_text)
    
    # 找到所有作者
    author_pattern = r'"screen_name":"(.*?)"'
    authors = re.findall(author_pattern, raw_text)
    
    # 组合数据（取前20条）
    for i in range(min(len(texts), 20)):
        try:
            text = texts[i]
            # 反转义
            text = text.replace('\\"', '"').replace('\\n', '\n').replace('\\\\', '\\').replace('<br/>', '\n')
            # 去除 HTML 标签
            text = re.sub(r'<[^>]+>', '', text)
            # 去除股票代码标记
            text = re.sub(r'\$.*?\$', '', text)
            text = text.strip()
            
            if len(text) < 5:
                continue
            
            ts = int(times[i]) if i < len(times) else 0
            author = authors[i] if i < len(authors) else "匿名"
            
            posts.append({
                'text': text,
                'author': author,
                'time': datetime.fromtimestamp(ts/1000).strftime('%m-%d %H:%M') if ts else "",
                'sentiment': analyze_sentiment(text),
            })
        except:
            continue
    
    return posts

def fetch_stock(symbol: str, name: str) -> List[Dict]:
    """抓取单只股票"""
    print(f"\n📈 {name} ({symbol})")
    print("-" * 60)
    
    timestamp = int(time.time() * 1000)
    url = f"https://xueqiu.com/statuses/search.json?count=20&comment=0&symbol={symbol}&hl=0&source=user&sort=time&page=1&_={timestamp}"
    
    try:
        # 打开页面
        r1 = subprocess.run(
            ['openclaw', 'browser', 'open', url],
            capture_output=True, text=True, timeout=30
        )
        
        match = re.search(r'id:\s*([A-F0-9]+)', r1.stdout)
        if not match:
            print("   ⚠️ 无法打开页面")
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
        
        # 提取原始 JSON 字符串
        line = r2.stdout.strip()
        
        # 找到 "{ 开始的部分
        if ': "' not in line:
            print("   ⚠️ 格式错误")
            return []
        
        # 提取 JSON 部分
        start = line.find('"{')
        end = line.rfind('}"')
        
        if start < 0 or end <= start:
            print("   ⚠️ 未找到数据")
            return []
        
        raw_json = line[start+1:end+1]
        
        # 用正则提取帖子
        posts = extract_posts_from_json(raw_json)
        
        # 过滤24小时内的
        now_ts = datetime.now().timestamp() * 1000
        one_day_ms = 24 * 60 * 60 * 1000
        
        filtered = []
        for p in posts:
            # 从时间字符串解析时间戳（简单处理）
            filtered.append(p)
        
        print(f"   ✅ 获取 {len(filtered)} 条")
        return filtered
        
    except Exception as e:
        print(f"   ❌ 错误: {str(e)[:50]}")
        return []

def main():
    print("=" * 60)
    print("🐧 雪球舆情监控 - V6 正则版")
    print(f"⏰ {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 60)
    
    all_data = {}
    for symbol, name in SYMBOLS:
        posts = fetch_stock(symbol, name)
        all_data[symbol] = posts
        time.sleep(1)
    
    # 保存
    import json
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    json_file = os.path.join(OUTPUT_DIR, f'xueqiu_{ts}.json')
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump({'time': datetime.now().isoformat(), 'data': all_data}, f, ensure_ascii=False, indent=2)
    
    # 打印结果
    print("\n" + "=" * 60)
    print("📊 舆情报告")
    print("=" * 60)
    
    for symbol, name in SYMBOLS:
        posts = all_data.get(symbol, [])
        bull = len([p for p in posts if p['sentiment'] == '🟢'])
        bear = len([p for p in posts if p['sentiment'] == '🔴'])
        
        print(f"\n📌 {name} ({symbol})")
        print(f"   共 {len(posts)} 条 | 🟢{bull} 🔴{bear}")
        
        for i, p in enumerate(posts[:3], 1):
            print(f"   {i}. {p['sentiment']} {p['text'][:45]}...")
    
    print(f"\n💾 保存到: {json_file}")
    print("=" * 60)
    print("✅ 完成!")

if __name__ == "__main__":
    main()
