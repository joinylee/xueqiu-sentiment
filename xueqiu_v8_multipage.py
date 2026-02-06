#!/usr/bin/env python3
"""
雪球舆情监控 - V8 多页版
支持翻页，获取更多讨论内容
"""

import subprocess
import re
import time
import os
from datetime import datetime

SYMBOLS = [
    ("SH600118", "中国卫星"),
    ("SZ002155", "湖南黄金"), 
    ("SZ300456", "赛微电子"),
    ("SH600879", "航天电子"),
    ("SZ002565", "顺灏股份"),
]

OUTPUT_DIR = "/Users/joinylee/Openclaw/xueqiu_sentiment/reports"
MAX_PAGES = 5  # 最大翻页数

def get_sentiment(text):
    bullish = ['涨', '利好', '看好', '买入', '突破', '强势', '新高', '做多', '抄底', '拉升']
    bearish = ['跌', '利空', '看空', '卖出', '破位', '弱势', '新低', '做空', '割肉', '汪汪']
    text = text.lower()
    bull = sum(1 for w in bullish if w in text)
    bear = sum(1 for w in bearish if w in text)
    if bull > bear: return "🟢"
    elif bear > bull: return "🔴"
    return "⚪"

def clean_text(text):
    """清洗文本"""
    text = text.replace('\\n', '\n').replace('\\t', ' ').replace('\\"', '"')
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\$[^$]+\$', '', text)
    text = ' '.join(text.split())
    return text.strip()

def extract_posts(raw_text):
    """提取帖子"""
    posts = []
    text_matches = list(re.finditer(r'"text":"(.*?)"[,}]', raw_text, re.DOTALL))
    time_matches = list(re.finditer(r'"created_at":(\d+)', raw_text))
    author_matches = list(re.finditer(r'"screen_name":"(.*?)"', raw_text))
    
    for i, tm in enumerate(text_matches[:20]):  # 每页最多20条
        try:
            text = tm.group(1)
            text = clean_text(text)
            if len(text) < 5 or len(text) > 500:
                continue
            
            ts = int(time_matches[i].group(1)) if i < len(time_matches) else 0
            author = author_matches[i].group(1) if i < len(author_matches) else "匿名"
            author = author.replace('\\"', '"')
            
            posts.append({
                'text': text[:150],
                'author': author[:20],
                'time': datetime.fromtimestamp(ts/1000).strftime('%m-%d %H:%M') if ts else '',
                'sentiment': get_sentiment(text),
                'timestamp': ts,
            })
        except:
            continue
    
    return posts

def fetch_page(symbol, page=1):
    """抓取单页"""
    ts = int(time.time() * 1000)
    url = f"https://xueqiu.com/statuses/search.json?count=20&symbol={symbol}&page={page}&_={ts}"
    
    try:
        r1 = subprocess.run(['openclaw', 'browser', 'open', url], 
            capture_output=True, text=True, timeout=30)
        
        m = re.search(r'id:\s*([A-F0-9]+)', r1.stdout)
        if not m: return []
        
        tid = m.group(1)
        time.sleep(2)
        
        r2 = subprocess.run(['openclaw', 'browser', 'snapshot', '--target-id', tid],
            capture_output=True, text=True, timeout=30)
        
        subprocess.run(['openclaw', 'browser', 'close', '--target-id', tid],
            capture_output=True, timeout=10)
        
        line = r2.stdout.strip()
        if 'generic [ref=' not in line:
            return []
        
        pos = line.find(': "')
        if pos < 0: return []
        
        start = pos + 2
        end = line.rfind('"')
        if end <= start: return []
        
        raw = line[start:end]
        raw = raw.replace('\\"', '"').replace('\\\\', '\\')
        
        return extract_posts(raw)
        
    except Exception as e:
        return []

def fetch_stock(symbol, name):
    """抓取多页"""
    print(f"\n📈 {name} ({symbol})")
    
    all_posts = []
    seen_texts = set()  # 去重
    
    for page in range(1, MAX_PAGES + 1):
        print(f"   第 {page} 页...", end=" ", flush=True)
        
        posts = fetch_page(symbol, page)
        if not posts:
            print("无数据")
            break
        
        # 去重
        new_posts = []
        for p in posts:
            if p['text'] not in seen_texts:
                seen_texts.add(p['text'])
                new_posts.append(p)
        
        all_posts.extend(new_posts)
        print(f"{len(new_posts)} 条")
        
        time.sleep(1.5)
    
    bull = len([p for p in all_posts if p['sentiment'] == '🟢'])
    bear = len([p for p in all_posts if p['sentiment'] == '🔴'])
    
    print(f"   ✅ 总计: {len(all_posts)} 条 (🟢{bull} 🔴{bear})")
    
    for i, p in enumerate(all_posts[:3], 1):
        print(f"   {i}. {p['sentiment']} {p['text'][:40]}...")
    
    return all_posts

def main():
    print("=" * 60)
    print("🐧 雪球舆情监控 - V8 多页版")
    print(f"⏰ {datetime.now().strftime('%H:%M:%S')}")
    print(f"📄 每只股票最多 {MAX_PAGES} 页")
    print("=" * 60)
    
    all_data = {}
    total = 0
    
    for symbol, name in SYMBOLS:
        posts = fetch_stock(symbol, name)
        all_data[symbol] = posts
        total += len(posts)
        time.sleep(1)
    
    # 保存
    import json
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    with open(f'{OUTPUT_DIR}/xueqiu_{ts}.json', 'w', encoding='utf-8') as f:
        json.dump({'time': datetime.now().isoformat(), 'data': all_data}, f, ensure_ascii=False, indent=2)
    
    # 汇总
    print("\n" + "=" * 60)
    print(f"📊 总计: {total} 条")
    print("=" * 60)
    for symbol, name in SYMBOLS:
        posts = all_data[symbol]
        bull = len([p for p in posts if p['sentiment'] == '🟢'])
        bear = len([p for p in posts if p['sentiment'] == '🔴'])
        print(f"   {name}: {len(posts)} 条 (🟢{bull} 🔴{bear})")

if __name__ == "__main__":
    main()
