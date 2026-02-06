#!/usr/bin/env python3
"""
雪球舆情监控 - V5 终极版
重点解决 JSON 解析问题
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
        return "🟢"
    elif bear > bull:
        return "🔴"
    return "⚪"

def safe_parse_json(json_str: str) -> Dict:
    """安全解析 JSON，处理各种异常情况"""
    try:
        # 第一次尝试：直接解析
        return json.loads(json_str)
    except:
        pass
    
    try:
        # 第二次：处理未转义的控制字符
        # 替换控制字符（除了正常的 \n \t \r）
        cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', json_str)
        return json.loads(cleaned)
    except:
        pass
    
    try:
        # 第三次：尝试用 ast.literal_eval
        import ast
        return ast.literal_eval(json_str)
    except:
        pass
    
    try:
        # 第四次：修复常见 JSON 问题
        # 替换单引号为双引号
        cleaned = json_str.replace("'", '"')
        # 修复缺失引号的键
        cleaned = re.sub(r'(\w+):', r'"\1":', cleaned)
        return json.loads(cleaned)
    except:
        pass
    
    return {}

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
        
        # 解析 JSON
        line = r2.stdout.strip()
        
        # 找到 ": " 后的 JSON 字符串
        if ': "' not in line:
            return []
        
        # 提取 "{ 开头，}" 结尾的部分
        start = line.find('"{')
        end = line.rfind('}"')
        
        if start < 0 or end <= start:
            return []
        
        # 提取 JSON 字符串（去掉外层引号）
        json_str = line[start+1:end+1]
        
        # 反转义
        json_str = json_str.replace('\\"', '"').replace('\\n', '\n').replace('\\\\', '\\').replace('\\/', '/')
        
        # 安全解析
        data = safe_parse_json(json_str)
        return data.get('list', [])
        
    except Exception as e:
        return []

def fetch_stock(symbol: str, name: str) -> List[Dict]:
    """抓取单只股票"""
    print(f"\n📈 {name} ({symbol})")
    print("-" * 60)
    
    now_ts = datetime.now().timestamp() * 1000
    one_day_ms = 24 * 60 * 60 * 1000
    
    all_posts = []
    
    for page in range(1, MAX_PAGES + 1):
        print(f"   第 {page} 页...", end=" ", flush=True)
        
        posts = fetch_posts_browser(symbol, page)
        if not posts:
            print("无数据/失败")
            break
        
        valid = 0
        stop = False
        
        for post in posts:
            ts = post.get('created_at', 0)
            if now_ts - ts > one_day_ms:
                stop = True
                break
            
            text = re.sub(r'<[^>]+>', '', post.get('text', ''))
            text = text.replace('&nbsp;', ' ').replace('&quot;', '"').replace('&lt;', '<').replace('&gt;', '>').strip()
            
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
            break
        
        time.sleep(1.5)
    
    print(f"   ✅ 总计: {len(all_posts)} 条")
    return all_posts

def main():
    print("=" * 60)
    print("🐧 雪球舆情监控 - V5 终极版")
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
        
        if posts:
            for i, p in enumerate(posts[:3], 1):
                print(f"   {i}. {p['sentiment']} [{p['time']}] {p['text'][:50]}...")
    
    print(f"\n💾 保存到: {json_file}")
    print("=" * 60)
    print("✅ 完成!")

if __name__ == "__main__":
    main()
