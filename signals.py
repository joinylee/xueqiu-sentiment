#!/usr/bin/env python3
"""
交易信号检测模块
基于舆情数据生成交易信号
"""

import json
import sys
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

# 信号类型
SIGNAL_OPPORTUNITY = "机会型"  # 舆情升温+价格不动
SIGNAL_WARNING = "风险型"  # 情绪极端/风险信号
SIGNAL_VERIFY = "验证型"  # 舆情与价格同步

class SentimentSignals:
    """舆情信号检测器"""
    
    def __init__(self):
        # 信号规则配置
        self.config = {
            "heat_threshold": 5.0,  # 热度阈值
            "intensity_threshold": 3.0,  # 情绪强度阈值
            "bullish_ratio_threshold": 0.8,  # 多头占比过高阈值
            "leading_weight": 1.5,  # 领先信号权重
        }
    
    def calculate_heat(self, items: List[Dict]) -> float:
        """
        计算舆情热度指数
        
        公式: Σ(likes + comments * 2 + reposts * 3)
        """
        total = 0
        for item in items:
            total += item.get("likes", 0)
            total += item.get("comments", 0) * 2
            total += item.get("reposts", 0) * 3
        return total / len(items) if items else 0
    
    def calculate_sentiment_bias(self, items: List[Dict]) -> Tuple[float, Dict]:
        """
        计算情绪偏向
        
        Returns:
            (bias, details): bias范围 -1(完全空) 到 1(完全多)
        """
        if not items:
            return 0, {"positive": 0, "negative": 0, "neutral": 0}
        
        scores = []
        for item in items:
            analysis = item.get("analysis", {})
            if "error" in analysis:
                continue
            
            sentiment = analysis.get("sentiment", "中性")
            intensity = analysis.get("intensity", 1)
            
            if sentiment == "多":
                scores.append(intensity)
            elif sentiment == "空":
                scores.append(-intensity)
            else:
                scores.append(0)
        
        if not scores:
            return 0, {"positive": 0, "negative": 0, "neutral": len(items)}
        
        # 计算偏向
        bias = sum(scores) / (len(scores) * 5)  # 归一化到 -1 ~ 1
        
        return round(bias, 3), {
            "positive": len([s for s in scores if s > 0]),
            "negative": len([s for s in scores if s < 0]),
            "neutral": len([s for s in scores if s == 0]),
        }
    
    def calculate_weighted_intensity(self, items: List[Dict]) -> float:
        """
        计算加权情绪强度
        """
        if not items:
            return 0
        
        total_weight = 0
        total_intensity = 0
        
        for item in items:
            weight = item.get("weight", 0)
            intensity = item.get("analysis", {}).get("intensity", 1)
            
            total_weight += weight
            total_intensity += weight * intensity
        
        return round(total_intensity / total_weight, 2) if total_weight > 0 else 0
    
    def detect_signal(self, symbol: str, items: List[Dict], price_change: float = 0.0) -> Optional[Dict]:
        """
        检测交易信号
        
        Args:
            symbol: 股票代码
            items: 该股票的舆情数据
            price_change: 当日涨跌幅
        
        Returns:
            dict: 信号结果，没有信号返回None
        """
        if not items:
            return None
        
        heat = self.calculate_heat(items)
        bias, bias_detail = self.calculate_sentiment_bias(items)
        avg_intensity = self.calculate_weighted_intensity(items)
        leading_count = len([i for i in items if i.get("analysis", {}).get("leading") == "是"])
        
        # 信号1: 机会型 - 舆情升温 + 价格不动
        if heat > self.config["heat_threshold"] and avg_intensity >= self.config["intensity_threshold"]:
            if abs(price_change) < 1.0:  # 价格横盘
                if bias > 0.2:  # 偏多
                    return {
                        "symbol": symbol,
                        "type": SIGNAL_OPPORTUNITY,
                        "signal": "潜在启动",
                        "confidence": "中" if heat < 20 else "高",
                        "reason": f"舆情热度↑↑({heat:.1f})，情绪偏多({bias:.2f})，但价格横盘({price_change:.2f}%)，存在主力吸筹迹象",
                        "metrics": {
                            "heat": round(heat, 2),
                            "bias": bias,
                            "avg_intensity": avg_intensity,
                            "leading_count": leading_count,
                        }
                    }
        
        # 信号2: 风险型 - 情绪极端过热
        bullish_ratio = bias_detail["positive"] / len(items) if items else 0
        if bullish_ratio > self.config["bullish_ratio_threshold"] and avg_intensity >= 4:
            return {
                "symbol": symbol,
                "type": SIGNAL_WARNING,
                "signal": "情绪过热",
                "confidence": "中",
                "reason": f"多头占比{bullish_ratio*100:.0f}%，情绪强度{avg_intensity}，警惕追高风险",
                "metrics": {
                    "bullish_ratio": round(bullish_ratio, 2),
                    "intensity": avg_intensity,
                }
            }
        
        # 信号3: 风险型 - 舆情转空 + 价格不跌
        if bias < -0.3 and price_change > -0.5 and price_change < 0:
            return {
                "symbol": symbol,
                "type": SIGNAL_WARNING,
                "signal": "洗盘信号",
                "confidence": "中",
                "reason": f"舆情明显偏空({bias:.2f})，但价格未跌，可能在洗盘",
                "metrics": {
                    "bias": bias,
                    "price_change": price_change,
                }
            }
        
        # 信号4: 验证型 - 舆情与价格同步
        if abs(price_change) > 2 and bias * price_change > 0:
            direction = "上涨" if price_change > 0 else "下跌"
            return {
                "symbol": symbol,
                "type": SIGNAL_VERIFY,
                "signal": f"情绪确认-{direction}",
                "confidence": "中",
                "reason": f"舆情与价格同步{direction}，确认当前趋势",
                "metrics": {
                    "bias": bias,
                    "price_change": price_change,
                }
            }
        
        return None
    
    def detect_all(self, analyzed_data: List[Dict], price_changes: Dict[str, float] = None) -> List[Dict]:
        """
        检测所有股票的交易信号
        
        Args:
            analyzed_data: 分析后的舆情数据
            price_changes: 股票涨跌幅字典 {symbol: change}
        
        Returns:
            list: 信号列表
        """
        # 按股票分组
        by_symbol = defaultdict(list)
        
        for item in analyzed_data:
            symbol = item.get("symbol")
            if symbol:
                by_symbol[symbol].append(item)
        
        # 检测每只股票
        signals = []
        
        for symbol, items in by_symbol.items():
            price_change = price_changes.get(symbol, 0.0) if price_changes else 0.0
            signal = self.detect_signal(symbol, items, price_change)
            
            if signal:
                signals.append(signal)
        
        # 按置信度和类型排序
        priority = {"高": 0, "中": 1, "低": 2}
        signals.sort(key=lambda x: (priority.get(x.get("confidence", "中"), 2), x.get("type")))
        
        return signals

def get_price_changes(symbols: List[str]) -> Dict[str, float]:
    """
    获取股票涨跌幅
    """
    import requests
    
    changes = {}
    
    for symbol in symbols:
        market = "sh" if symbol.startswith("SH") or symbol.startswith("6") else "sz"
        code = symbol.replace("SH", "").replace("SZ", "")
        
        try:
            url = f"http://qt.gtimg.cn/q={market}{code}"
            r = requests.get(url, timeout=5)
            data = r.text.split("~")
            
            if len(data) > 32:
                change = float(data[32])
                changes[symbol] = change
                
        except Exception:
            pass
    
    return changes

if __name__ == "__main__":
    from normalize import load_raw_data
    from analyze import batch_analyze, enrich_with_weights
    
    print("=" * 60)
    print("🚨 交易信号检测")
    print("=" * 60)
    
    # 加载分析数据
    analyzed_file = "/tmp/xueqiu_analyzed.jsonl"
    
    if not os.path.exists(analyzed_file):
        print("\n⚠️ 没有找到分析数据，请先运行 analyze.py")
        sys.exit(1)
    
    # 读取数据
    items = []
    with open(analyzed_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))
    
    print(f"📥 加载 {len(items)} 条分析数据")
    
    # 获取价格
    from config import SYMBOLS
    price_changes = get_price_changes(SYMBOLS)
    print(f"📈 获取 {len(price_changes)} 只股票价格")
    
    # 检测信号
    detector = SentimentSignals()
    signals = detector.detect_all(items, price_changes)
    
    print(f"\n🚨 检测到 {len(signals)} 个信号:")
    
    for i, signal in enumerate(signals[:10], 1):
        emoji = {"机会型": "🟢", "风险型": "🔴", "验证型": "🟡"}.get(signal["type"], "⚪")
        print(f"  {i}. {emoji} {signal['symbol']} | {signal['type']} | {signal['signal']}")
        print(f"     {signal['reason']}")
    
    # 保存
    with open("/tmp/xueqiu_signals.json", "w", encoding="utf-8") as f:
        json.dump(signals, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 已保存到 /tmp/xueqiu_signals.json")
