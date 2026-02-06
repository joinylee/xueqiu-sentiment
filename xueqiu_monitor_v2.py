#!/usr/bin/env python3
"""
雪球舆情监控 - 完整版 v2.0
功能：
1. 24小时时间窗口抓取
2. 自动翻页（max_id机制）
3. 使用browser绕过WAF
4. 限速防封
5. 情绪分析 + 关键词提取
6. 结果保存为JSON和Markdown报告

使用方法：
    python xueqiu_monitor_v2.py
"""

import subprocess
import json
import re
import time
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import sys

# ============ 配置 ============
SYMBOLS = [
    ("SH600118", "中国卫星"),
    ("SZ002155", "湖南黄金"),
    ("SZ300456", "赛微电子"),
    ("SH600879", "航天电子"),
    ("SZ002565", "顺灏股份"),
]

OUTPUT_DIR = "/Users/joinylee/Openclaw/xueqiu_sentiment/reports"
MAX_PAGES = 5  # 每只股票最大翻页数
SLEEP_TIME = 1.5  # 翻页间隔（秒）

# ============ 情绪分析 ============
BULLISH_WORDS = ['涨', '利好', '看好', '买入', '突破', '强势', '新高', '做多', '抄底', '拉升', '反弹', '涨停']
BEARISH_WORDS = ['跌', '利空', '看空', '卖出', '破位', '弱势', '新低', '做空', '割肉', '汪汪', '割了', '打压', '跳水']

def analyze_sentiment(text: str) -> Dict[str, Any]:
    """分析情绪"""
    text_lower = text.lower()
    bull_count = sum(1 for w in BULLISH_WORDS if w in text_lower)
    bear_count = sum(1 for w in BEARISH_WORDS if w in text_lower)
    
    if bull_count > bear_count:
        return {"type": "利多", "emoji": "🟢", "score": min(bull_count - bear_count, 5)}
    elif bear_count > bull_count:
        return {"type": "利空", "emoji": "🔴", "score": min(bear_count - bull_count, 5)}
    return {"type": "中性", "emoji": "⚪", "score": 0}

# ============ 数据抓取 ============
def fetch_page(symbol: str, max_id: Optional[int] = None) -> List[Dict]:
    """抓取单页数据"""
    url = f'https://xueqiu.com/query/v1/symbol/search/status?symbol={symbol}&count=20'
    if max_id:
        url += f'&max_id={max_id}'
    
    try:
        # 打开页面
        r1 = subprocess.run(
            ['openclaw', 'browser', 'open', url],
            capture_output=True, text=True, timeout=30
        )
        
        match = re.search(r'id:\s*([A-F0-9]+)', r1.stdout)
        if not match:
            print(f"   ⚠️ 无法获取页面ID")
            return []
        
        target_id = match.group(1)
        time.sleep(2)  # 等待页面加载
        
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
        
        # 解析JSON数据 - 使用更健壮的方式
        # 保存原始输出到临时文件，然后使用正则提取
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(r2.stdout)
            tmp_file = f.name
        
        try:
            with open(tmp_file, 'r') as f:
                content = f.read()
            
            os.unlink(tmp_file)
            
            # 找到JSON开始的位置
            if 'generic [ref=' not in content:
                return []
            
            # 格式: - generic [ref=e2]: "{...}"
            # 找到 ": " 后面的 "{ 开头
            marker = 'generic [ref='
            pos = content.find(marker)
            if pos < 0:
                return []
            
            # 从marker位置向后找 ": "
            colon_pos = content.find('": "', pos)
            if colon_pos < 0:
                return []
            
            # JSON从 ": " 后面开始，以 " 结尾
            start = colon_pos + 3  # 跳过 ": "
            
            # 找到行尾的 "
            end = content.find('"', start)
            if end < 0:
                end = len(content)
            
            if start >= end:
                return []
            
            json_str = content[start:end]
            
            try:
                data = json.loads(json_str)
                return data.get('list', [])
            except json.JSONDecodeError:
                # 尝试修复常见的JSON问题
                # 替换未转义的控制字符
                json_str = re.sub(r'[\x00-\x1F]', '', json_str)
                try:
                    data = json.loads(json_str)
                    return data.get('list', [])
                except:
                    return []
        except Exception as e:
            print(f"   解析错误: {e}")
            return []
        
    except Exception as e:
        print(f"   ❌ 抓取错误: {e}")
        return []

def fetch_24h_posts(symbol: str, name: str) -> List[Dict]:
    """抓取24小时内的所有讨论"""
    print(f"\n📡 {name} ({symbol})")
    print("-" * 60)
    
    now_ts = datetime.now().timestamp() * 1000
    one_day_ms = 24 * 60 * 60 * 1000
    
    all_posts = []
    max_id = None
    page = 1
    
    while page <= MAX_PAGES:
        print(f"   抓取第 {page} 页...", end=" ")
        
        posts = fetch_page(symbol, max_id)
        if not posts:
            print("无数据")
            break
        
        valid_count = 0
        stop_fetch = False
        
        for post in posts:
            ts = post.get('created_at', 0)
            
            # 检查是否超过24小时
            if now_ts - ts > one_day_ms:
                stop_fetch = True
                break
            
            # 清洗文本
            html_text = post.get('text', '')
            plain_text = re.sub(r'<[^>]+>', '', html_text)
            plain_text = plain_text.replace('&nbsp;', ' ').replace('&quot;', '"').strip()
            
            if len(plain_text) < 5:  # 过滤太短的
                continue
            
            # 分析情绪
            sentiment = analyze_sentiment(plain_text)
            
            all_posts.append({
                'id': post.get('id'),
                'text': plain_text,
                'author': post.get('user', {}).get('screen_name', '匿名'),
                'timestamp': ts,
                'time_str': datetime.fromtimestamp(ts/1000).strftime('%m-%d %H:%M'),
                'likes': post.get('like_count', 0),
                'comments': post.get('reply_count', 0),
                'views': post.get('view_count', 0),
                'sentiment': sentiment,
            })
            valid_count += 1
        
        print(f"获取 {valid_count} 条")
        
        if stop_fetch or valid_count < len(posts):
            print(f"   ⏰ 已超出24小时或到达末尾")
            break
        
        # 下一页
        max_id = posts[-1].get('id')
        page += 1
        time.sleep(SLEEP_TIME)
    
    print(f"   ✅ 总计: {len(all_posts)} 条")
    return all_posts

# ============ 生成报告 ============
def generate_report(all_data: Dict[str, List[Dict]]) -> str:
    """生成Markdown报告"""
    now = datetime.now()
    report = f"""# 📊 雪球舆情监控报告

**生成时间**: {now.strftime('%Y-%m-%d %H:%M:%S')}  
**监控股票**: {len(SYMBOLS)} 只

---

"""
    
    for symbol, name in SYMBOLS:
        posts = all_data.get(symbol, [])
        
        # 统计
        bull = len([p for p in posts if p['sentiment']['type'] == '利多'])
        bear = len([p for p in posts if p['sentiment']['type'] == '利空'])
        neutral = len([p for p in posts if p['sentiment']['type'] == '中性'])
        
        report += f"""## 📈 {name} ({symbol})

**统计**: 共 {len(posts)} 条 | 🟢 {bull} | 🔴 {bear} | ⚪ {neutral}

"""
        
        if posts:
            report += "### 最新讨论\n\n"
            for i, p in enumerate(posts[:5], 1):
                report += f"{i}. {p['sentiment']['emoji']} **{p['time_str']}** | {p['author']}\n"
                report += f"   > {p['text'][:100]}{'...' if len(p['text']) > 100 else ''}\n\n"
        else:
            report += "*暂无数据*\n\n"
        
        report += "---\n\n"
    
    return report

def save_results(all_data: Dict[str, List[Dict]], report: str):
    """保存结果"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 保存JSON
    json_file = os.path.join(OUTPUT_DIR, f'xueqiu_{timestamp}.json')
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump({
            'fetch_time': datetime.now().isoformat(),
            'data': all_data
        }, f, ensure_ascii=False, indent=2)
    
    # 保存Markdown报告
    md_file = os.path.join(OUTPUT_DIR, f'report_{timestamp}.md')
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n💾 结果已保存:")
    print(f"   JSON: {json_file}")
    print(f"   报告: {md_file}")

# ============ 主程序 ============
def main():
    print("=" * 60)
    print("🐧 雪球舆情监控 - 完整版 v2.0")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print(f"\n配置:")
    print(f"   股票数: {len(SYMBOLS)}")
    print(f"   最大页数: {MAX_PAGES}")
    print(f"   限速: {SLEEP_TIME}秒/页")
    
    # 抓取数据
    all_data = {}
    for symbol, name in SYMBOLS:
        posts = fetch_24h_posts(symbol, name)
        all_data[symbol] = posts
        time.sleep(1)  # 股票间间隔
    
    # 生成报告
    print("\n" + "=" * 60)
    print("📊 生成报告...")
    print("=" * 60)
    
    report = generate_report(all_data)
    save_results(all_data, report)
    
    # 打印摘要
    print("\n📈 监控摘要:")
    print("-" * 60)
    for symbol, name in SYMBOLS:
        posts = all_data.get(symbol, [])
        bull = len([p for p in posts if p['sentiment']['type'] == '利多'])
        bear = len([p for p in posts if p['sentiment']['type'] == '利空'])
        print(f"   {name}: {len(posts)}条 (🟢{bull} 🔴{bear})")
    
    print("\n" + "=" * 60)
    print("✅ 监控完成!")
    print("=" * 60)

if __name__ == "__main__":
    main()
