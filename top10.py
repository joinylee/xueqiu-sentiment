#!/usr/bin/env python3
"""
Top10舆情聚合模块
每天只关注"信息密度异常"的股票
"""

import json
import sys
import os
from datetime import datetime
from typing import Dict, List
from collections import defaultdict

def calculate_top_score(stock_data: Dict) -> float:
    """
    计算Top10综合得分
    
    公式: 0.4×Total + 0.3×Acceleration + 0.2×|BiasShift| + 0.1×Danger
    """
    # 获取指标
    total_score = stock_data.get("total_score", 0)
    acceleration = stock_data.get("acceleration", 0)
    bias_shift = stock_data.get("bias_shift", 0)
    danger = stock_data.get("danger", 0)
    
    # 简单归一化（使用百分位会更准确）
    def normalize(val, max_val=100):
        return min(val / max_val, 1.0) if max_val > 0 else 0
    
    # 计算加权得分
    score = (
        0.4 * normalize(total_score, 50) +
        0.3 * normalize(acceleration, 5) +
        0.2 * abs(normalize(bias_shift, 1)) +
        0.1 * normalize(danger, 10)
    )
    
    return round(score, 3)

def aggregate_by_symbol(analyzed_data: List[Dict], time_window_hours: int = 2) -> List[Dict]:
    """
    按股票聚合舆情数据
    
    Args:
        analyzed_data: 分析后的舆情数据
        time_window_hours: 时间窗口（小时）
    
    Returns:
        list: 聚合后的股票数据
    """
    now = datetime.now().timestamp()
    cutoff = now - time_window_hours * 3600
    
    # 按股票分组
    by_symbol = defaultdict(lambda: {
        "items": [],
        "recent_items": [],
        "total_score": 0,
        "positive_count": 0,
        "negative_count": 0,
        "leading_count": 0,
        "total_weight": 0,
    })
    
    for item in analyzed_data:
        symbol = item.get("symbol")
        if not symbol:
            continue
        
        timestamp = item.get("timestamp", 0)
        weight = item.get("weight", 0)
        analysis = item.get("analysis", {})
        
        data = by_symbol[symbol]
        data["symbol"] = symbol
        data["items"].append(item)
        data["total_score"] += weight
        
        if timestamp > cutoff:
            data["recent_items"].append(item)
        
        if analysis.get("sentiment") == "多":
            data["positive_count"] += 1
        elif analysis.get("sentiment") == "空":
            data["negative_count"] += 1
        
        if analysis.get("leading") == "是":
            data["leading_count"] += 1
        
        data["total_weight"] += weight
    
    # 计算聚合指标
    result = []
    
    for symbol, data in by_symbol.items():
        items = data["items"]
        recent = data["recent_items"]
        
        if not items:
            continue
        
        # 舆情加速度 = 最近30分钟权重 ÷ 过去2小时平均
        recent_30min = [i for i in items if i.get("timestamp", 0) > now - 1800]
        if len(items) > 5 and sum(i.get("weight", 0) for i in items) > 0:
            avg_weight = data["total_weight"] / len(items)
            recent_weight = sum(i.get("weight", 0) for i in recent_30min) / max(len(recent_30min), 1)
            acceleration = recent_weight / avg_weight if avg_weight > 0 else 0
        else:
            acceleration = 1.0
        
        # 情绪偏移 = 近期情绪 - 整体情绪
        recent_positive = len([i for i in recent if i.get("analysis", {}).get("sentiment") == "多"])
        recent_negative = len([i for i in recent if i.get("analysis", {}).get("sentiment") == "空"])
        
        if len(recent) > 0:
            recent_bias = (recent_positive - recent_negative) / len(recent)
        else:
            recent_bias = 0
        
        overall_positive = data["positive_count"]
        overall_negative = data["negative_count"]
        
        if len(items) > 0:
            overall_bias = (overall_positive - overall_negative) / len(items)
        else:
            overall_bias = 0
        
        bias_shift = recent_bias - overall_bias
        
        # 分歧度 = 多头强度 × 空头强度
        positive_intensity = sum(
            i.get("analysis", {}).get("intensity", 0) 
            for i in items if i.get("analysis", {}).get("sentiment") == "多"
        )
        negative_intensity = sum(
            abs(i.get("analysis", {}).get("intensity", 0)) 
            for i in items if i.get("analysis", {}).get("sentiment") == "空"
        )
        danger = (positive_intensity / max(data["positive_count"], 1)) * \
                  (negative_intensity / max(data["negative_count"], 1)) if data["positive_count"] and data["negative_count"] else 0
        
        stock_data = {
            "symbol": symbol,
            "total_score": round(data["total_score"], 2),
            "item_count": len(items),
            "acceleration": round(acceleration, 2),
            "bias_shift": round(bias_shift, 3),
            "danger": round(danger, 2),
            "positive_count": data["positive_count"],
            "negative_count": data["negative_count"],
            "leading_count": data["leading_count"],
            "items": data["items"][:10],  # 只保留前10条
        }
        
        result.append(stock_data)
    
    # 按综合得分排序
    for stock in result:
        stock["top_score"] = calculate_top_score(stock)
    
    result.sort(key=lambda x: x["top_score"], reverse=True)
    
    return result

def assign_type(stock_data: Dict, price_change: float = 0) -> str:
    """
    为股票分配用途类型
    """
    score = stock_data["top_score"]
    acceleration = stock_data["acceleration"]
    bias_shift = stock_data["bias_shift"]
    danger = stock_data["danger"]
    item_count = stock_data["item_count"]
    
    # 机会型: 舆情升温 + 偏多 + 价格未动
    if acceleration > 1.5 and bias_shift > 0.1 and abs(price_change) < 1.0 and score > 0.3:
        return "机会型"
    
    # 风险型: 情绪极端或分歧放大
    if danger > 1.5 or (stock_data["positive_count"] / item_count > 0.8 and score > 0.4):
        return "风险型"
    
    # 验证型: 舆情与价格同步
    if abs(price_change) > 2 and bias_shift * price_change > 0:
        return "验证型"
    
    # 关注型: 综合得分还可以
    if score > 0.2:
        return "关注型"
    
    return "普通"

def generate_top10(aggregated_data: List[Dict], price_changes: Dict[str, float], limit: int = 10) -> List[Dict]:
    """
    生成Top10舆情列表
    
    Args:
        aggregated_data: 聚合后的数据
        price_changes: 股票涨跌幅
        limit: 返回数量
    
    Returns:
        list: Top10列表
    """
    top10 = []
    
    for stock in aggregated_data[:limit * 2]:  # 先取更多
        symbol = stock["symbol"]
        price_change = price_changes.get(symbol, 0)
        
        stock_type = assign_type(stock, price_change)
        
        # 生成原因
        reasons = []
        
        if stock["acceleration"] > 1.5:
            reasons.append(f"舆情加速度↑({stock['acceleration']}x)")
        
        if stock["bias_shift"] > 0.2:
            reasons.append(f"情绪偏移↑({stock['bias_shift']:.2f})")
        
        if stock["leading_count"] > 0:
            reasons.append(f"领先信号{stock['leading_count']}条")
        
        if stock["item_count"] > 10:
            reasons.append(f"讨论{item_count}条")
        
        reason = "，".join(reasons[:2]) if reasons else "综合舆情关注"
        
        top10.append({
            "rank": len(top10) + 1,
            "symbol": symbol,
            "type": stock_type,
            "reason": reason,
            "top_score": stock["top_score"],
            "price_change": price_change,
            "total_score": stock["total_score"],
            "item_count": stock["item_count"],
        })
        
        if len(top10) >= limit:
            break
    
    return top10

if __name__ == "__main__":
    from normalize import load_raw_data
    from analyze import batch_analyze, enrich_with_weights
    from signals import get_price_changes
    
    print("=" * 60)
    print("📊 Top10舆情聚合")
    print("=" * 60)
    
    # 加载数据
    analyzed_file = "/tmp/xueqiu_analyzed.jsonl"
    
    if not os.path.exists(analyzed_file):
        print("\n⚠️ 没有找到分析数据")
        sys.exit(1)
    
    # 读取
    items = []
    with open(analyzed_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))
    
    print(f"📥 加载 {len(items)} 条分析数据")
    
    # 聚合
    aggregated = aggregate_by_symbol(items)
    print(f"📊 聚合为 {len(aggregated)} 只股票")
    
    # 获取价格
    from config import SYMBOLS
    price_changes = get_price_changes(SYMBOLS)
    print(f"📈 获取 {len(price_changes)} 只股票价格")
    
    # 生成Top10
    top10 = generate_top10(aggregated, price_changes)
    
    print(f"\n🎯 Top10舆情股票:")
    for item in top10:
        emoji = {"机会型": "🟢", "风险型": "🔴", "验证型": "🟡", "关注型": "🟡"}.get(item["type"], "⚪")
        print(f"  {item['rank']}. {emoji} {item['symbol']} | {item['type']}")
        print(f"     {item['reason']}")
    
    # 保存
    with open("/tmp/xueqiu_top10.json", "w", encoding="utf-8") as f:
        json.dump(top10, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 已保存到 /tmp/xueqiu_top10.json")
