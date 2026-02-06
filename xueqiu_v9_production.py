#!/usr/bin/env python3
"""
雪球舆情监控 - V9 生产版
完整功能：多页抓取 + 股票池 + 报告生成
"""

import subprocess
import re
import time
import os
import json
from datetime import datetime

# ============ 股票池配置 ============
SYMBOLS = [
    ("SH600118", "中国卫星"),
    ("SZ002155", "湖南黄金"),
    ("SZ300456", "赛微电子"),
    ("SH600879", "航天电子"),
    ("SZ002565", "顺灏股份"),
    ("SH603667", "五洲新春"),
    ("SH601869", "长飞光纤"),
    ("SZ002112", "三变科技"),
    ("SZ002361", "神剑股份"),
    ("SZ002342", "巨力索具"),
    ("SZ300136", "信维通信"),
]

OUTPUT_DIR = "/Users/joinylee/Openclaw/xueqiu_sentiment/reports"
MAX_PAGES = 7  # 每天抓取7页

# ============ 情绪分析 ============
def get_sentiment(text):
    bullish = ['涨', '利好', '看好', '买入', '突破', '强势', '新高', '做多', '抄底', '拉升', '涨停']
    bearish = ['跌', '利空', '看空', '卖出', '破位', '弱势', '新低', '做空', '割肉', '汪汪', '割了', '打压']
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
    
    for i, tm in enumerate(text_matches[:20]):
        try:
            text = tm.group(1)
            text = clean_text(text)
            if len(text) < 5 or len(text) > 600:
                continue
            
            ts = int(time_matches[i].group(1)) if i < len(time_matches) else 0
            author = author_matches[i].group(1) if i < len(author_matches) else "匿名"
            author = author.replace('\\"', '"')
            
            posts.append({
                'text': text[:200],
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
    seen_texts = set()
    
    for page in range(1, MAX_PAGES + 1):
        print(f"   第 {page}/{MAX_PAGES} 页...", end=" ", flush=True)
        
        posts = fetch_page(symbol, page)
        if not posts:
            print("无数据")
            break
        
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
    
    # 显示最新3条
    for i, p in enumerate(sorted(all_posts, key=lambda x: x['timestamp'], reverse=True)[:3], 1):
        print(f"   {i}. {p['sentiment']} [{p['time']}] {p['text'][:45]}...")
    
    return all_posts

def generate_report(all_data):
    """生成 Markdown 报告"""
    now = datetime.now()
    report = f"""# 📊 雪球舆情监控报告

**生成时间**: {now.strftime('%Y-%m-%d %H:%M:%S')}  
**监控股票**: {len(SYMBOLS)} 只  
**抓取页数**: {MAX_PAGES} 页/只

---

"""
    
    total_bull = total_bear = 0
    
    for symbol, name in SYMBOLS:
        posts = all_data.get(symbol, [])
        bull = len([p for p in posts if p['sentiment'] == '🟢'])
        bear = len([p for p in posts if p['sentiment'] == '🔴'])
        total_bull += bull
        total_bear += bear
        
        report += f"""## 📈 {name} ({symbol})

**统计**: 共 {len(posts)} 条 | 🟢 {bull} | 🔴 {bear} | ⚪ {len(posts) - bull - bear}

"""
        
        if posts:
            # 按时间排序，取最新5条
            sorted_posts = sorted(posts, key=lambda x: x.get('timestamp', 0), reverse=True)
            report += "### 最新讨论\n\n"
            for i, p in enumerate(sorted_posts[:5], 1):
                report += f"{i}. {p['sentiment']} **{p['time']}** | {p['author']}\n"
                report += f"   > {p['text'][:100]}{'...' if len(p['text']) > 100 else ''}\n\n"
        else:
            report += "*暂无数据*\n\n"
        
        report += "---\n\n"
    
    # 添加汇总
    total = sum(len(v) for v in all_data.values())
    report += f"""## 📊 汇总

**总计**: {total} 条讨论  
**利多**: {total_bull} 条 🟢  
**利空**: {total_bear} 条 🔴  
**中性**: {total - total_bull - total_bear} 条 ⚪

"""
    
    return report

def main():
    print("=" * 70)
    print("🐧 雪球舆情监控 - V9 生产版")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 股票数: {len(SYMBOLS)} | 页数: {MAX_PAGES}")
    print("=" * 70)
    
    all_data = {}
    total_count = 0
    
    for i, (symbol, name) in enumerate(SYMBOLS, 1):
        print(f"\n[{i}/{len(SYMBOLS)}]", end="")
        posts = fetch_stock(symbol, name)
        all_data[symbol] = posts
        total_count += len(posts)
        time.sleep(1)
    
    # 保存 JSON
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    json_file = os.path.join(OUTPUT_DIR, f'xueqiu_{ts}.json')
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump({
            'fetch_time': datetime.now().isoformat(),
            'max_pages': MAX_PAGES,
            'total_posts': total_count,
            'data': all_data
        }, f, ensure_ascii=False, indent=2)
    
    # 生成并保存 Markdown 报告
    report = generate_report(all_data)
    md_file = os.path.join(OUTPUT_DIR, f'report_{ts}.md')
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    # 打印汇总
    print("\n" + "=" * 70)
    print("📊 汇总报告")
    print("=" * 70)
    print(f"总计抓取: {total_count} 条")
    print()
    
    for symbol, name in SYMBOLS:
        posts = all_data[symbol]
        bull = len([p for p in posts if p['sentiment'] == '🟢'])
        bear = len([p for p in posts if p['sentiment'] == '🔴'])
        print(f"  {name:10s} ({symbol}): {len(posts):3d} 条 (🟢{bull:2d} 🔴{bear:2d})")
    
    print()
    print(f"💾 JSON: {json_file}")
    print(f"📄 报告: {md_file}")
    print("=" * 70)
    print("✅ 完成!")

if __name__ == "__main__":
    main()
