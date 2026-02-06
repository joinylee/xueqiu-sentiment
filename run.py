#!/usr/bin/env python3
"""
雪球舆情监控 - 主入口
==========================

功能:
1. 抓取雪球个股讨论和快讯
2. LLM舆情分析
3. 生成交易信号
4. Top10聚合
5. 推送通知

使用:
    python run.py              # 完整流程
    python run.py --fetch      # 仅抓取
    python run.py --analyze    # 仅分析
    python run.py --signals    # 仅生成信号
    python run.py --top10      # 仅聚合Top10
    python run.py --send       # 仅推送
"""

import sys
import os
import json
import argparse
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import SYMBOLS

def step_fetch():
    """Step 1: 抓取数据"""
    print("\n" + "=" * 60)
    print("📥 Step 1: 抓取雪球数据")
    print("=" * 60)
    
    from fetch_status import fetch_discussions
    from fetch_livenews import fetch_livenews
    from normalize import save_normalized_data
    
    # 抓取个股讨论
    print(f"\n🐣 抓取 {len(SYMBOLS)} 只股票的讨论...")
    status_data = []
    for symbol in SYMBOLS:
        posts = fetch_discussions(symbol)
        status_data.extend(posts)
    
    print(f"   获取 {len(status_data)} 条讨论")
    
    # 抓取快讯
    print("\n📰 抓取雪球快讯...")
    livenews_data = fetch_livenews(50)
    print(f"   获取 {len(livenews_data)} 条快讯")
    
    # 标准化
    from normalize import normalize_all
    print("\n🔧 标准化数据...")
    normalized = normalize_all(status_data, livenews_data, SYMBOLS)
    print(f"   标准化 {len(normalized)} 条")
    
    # 保存
    save_normalized_data(normalized)
    
    return len(normalized)

def step_analyze():
    """Step 2: LLM分析"""
    print("\n" + "=" * 60)
    print("🧠 Step 2: LLM舆情分析")
    print("=" * 60)
    
    normalized_file = "/tmp/xueqiu_normalized.jsonl"
    
    if not os.path.exists(normalized_file):
        print("⚠️ 没有找到标准化数据，请先运行 --fetch")
        return 0
    
    # 读取数据
    items = []
    with open(normalized_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))
    
    print(f"📥 加载 {len(items)} 条数据")
    
    # 分析
    from analyze import batch_analyze, enrich_with_weights, save_analyzed_data
    
    analyzed = batch_analyze(items, limit=50)
    enriched = enrich_with_weights(analyzed)
    save_analyzed_data(enriched)
    
    # 统计
    positive = len([i for i in enriched if i.get("analysis", {}).get("sentiment") == "多"])
    negative = len([i for i in enriched if i.get("analysis", {}).get("sentiment") == "空"])
    neutral = len([i for i in enriched if i.get("analysis", {}).get("sentiment") == "中性"])
    
    print(f"\n📊 情绪统计:")
    print(f"   🟢 多: {positive} 条")
    print(f"   🔴 空: {negative} 条")
    print(f"   ⚪ 中: {neutral} 条")
    
    return len(enriched)

def step_signals():
    """Step 3: 生成信号"""
    print("\n" + "=" * 60)
    print("🚨 Step 3: 生成交易信号")
    print("=" * 60)
    
    analyzed_file = "/tmp/xueqiu_analyzed.jsonl"
    
    if not os.path.exists(analyzed_file):
        print("⚠️ 没有找到分析数据，请先运行 --fetch --analyze")
        return 0
    
    # 读取
    items = []
    with open(analyzed_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))
    
    print(f"📥 加载 {len(items)} 条分析数据")
    
    # 获取价格
    from signals import SentimentSignals, get_price_changes
    price_changes = get_price_changes(SYMBOLS)
    print(f"📈 获取 {len(price_changes)} 只股票价格")
    
    # 检测信号
    detector = SentimentSignals()
    signals = detector.detect_all(items, price_changes)
    
    print(f"\n🚨 检测到 {len(signals)} 个信号:")
    for i, signal in enumerate(signals[:10], 1):
        emoji = {"机会型": "🟢", "风险型": "🔴", "验证型": "🟡"}.get(signal.get("type"), "⚪")
        print(f"   {i}. {emoji} {signal['symbol']} | {signal['signal']}")
        print(f"      {signal['reason']}")
    
    # 保存
    with open("/tmp/xueqiu_signals.json", "w", encoding="utf-8") as f:
        json.dump(signals, f, ensure_ascii=False, indent=2)
    
    return len(signals)

def step_top10():
    """Step 4: 生成Top10"""
    print("\n" + "=" * 60)
    print("📊 Step 4: 生成Top10舆情")
    print("=" * 60)
    
    analyzed_file = "/tmp/xueqiu_analyzed.jsonl"
    
    if not os.path.exists(analyzed_file):
        print("⚠️ 没有找到分析数据，请先运行 --fetch --analyze")
        return 0
    
    # 读取
    items = []
    with open(analyzed_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))
    
    print(f"📥 加载 {len(items)} 条分析数据")
    
    # 聚合
    from top10 import aggregate_by_symbol, generate_top10
    from signals import get_price_changes
    
    aggregated = aggregate_by_symbol(items)
    print(f"📊 聚合为 {len(aggregated)} 只股票")
    
    # 获取价格
    price_changes = get_price_changes(SYMBOLS)
    
    # 生成Top10
    top10 = generate_top10(aggregated, price_changes, limit=10)
    
    print(f"\n🎯 Top10舆情股票:")
    for item in top10:
        emoji = {"机会型": "🟢", "风险型": "🔴", "验证型": "🟡", "关注型": "🟠"}.get(item.get("type"), "⚪")
        print(f"   {item['rank']}. {emoji} {item['symbol']} | {item['type']}")
        print(f"      {item['reason']}")
    
    # 保存
    with open("/tmp/xueqiu_top10.json", "w", encoding="utf-8") as f:
        json.dump(top10, f, ensure_ascii=False, indent=2)
    
    return len(top10)

def step_send():
    """Step 5: 推送"""
    print("\n" + "=" * 60)
    print("📤 Step 5: 推送到Telegram")
    print("=" * 60)
    
    from send_telegram import send_top10, send_signals
    
    success = 0
    
    if os.path.exists("/tmp/xueqiu_top10.json"):
        if send_top10():
            success += 1
    
    if os.path.exists("/tmp/xueqiu_signals.json"):
        if send_signals():
            success += 1
    
    return success

def main():
    parser = argparse.ArgumentParser(description="雪球舆情监控")
    parser.add_argument("--fetch", action="store_true", help="仅抓取数据")
    parser.add_argument("--analyze", action="store_true", help="仅分析")
    parser.add_argument("--signals", action="store_true", help="仅生成信号")
    parser.add_argument("--top10", action="store_true", help="仅生成Top10")
    parser.add_argument("--send", action="store_true", help="仅推送")
    parser.add_argument("--all", action="store_true", help="完整流程")
    
    args = parser.parse_args()
    
    # 默认完整流程
    if not any([args.fetch, args.analyze, args.signals, args.top10, args.send]):
        args.all = True
    
    print("\n" + "=" * 60)
    print("🐧 雪球舆情监控系统")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print(f"📦 监控 {len(SYMBOLS)} 只股票: {', '.join(SYMBOLS)}")
    
    # 执行步骤
    stats = {}
    
    if args.fetch or args.all:
        stats["fetched"] = step_fetch()
    
    if args.analyze or args.all:
        stats["analyzed"] = step_analyze()
    
    if args.signals or args.all:
        stats["signals"] = step_signals()
    
    if args.top10 or args.all:
        stats["top10"] = step_top10()
    
    if args.send or args.all:
        stats["sent"] = step_send()
    
    # 总结
    print("\n" + "=" * 60)
    print("✅ 完成统计")
    print("=" * 60)
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    print("\n💡 文件位置:")
    print("   - 标准化数据: /tmp/xueqiu_normalized.jsonl")
    print("   - 分析结果: /tmp/xueqiu_analyzed.jsonl")
    print("   - 信号: /tmp/xueqiu_signals.json")
    print("   - Top10: /tmp/xueqiu_top10.json")

if __name__ == "__main__":
    main()
