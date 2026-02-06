#!/usr/bin/env python3
"""
舆情分析模块 - LLM驱动
使用LLM对雪球内容进行深度分析
"""

import json
import sys
import os
import time
from typing import Dict, List, Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import LLM_MODEL, TEMPERATURE

# 配置（从config.py读取）
LLM_MODEL_CONFIG = LLM_MODEL  # "minimax/MiniMax-M2.1" 或 "moonshot/kimi-k2.5"
MAX_TOKENS = 1000

def get_llm_client():
    """
    获取LLM客户端
    优先使用 MiniMax，兼容 OpenAI
    """
    import json
    import os
    
    # 优先从环境变量读取
    api_key = os.environ.get("MINIMAX_API_KEY")
    
    # 如果没有环境变量，尝试从文件读取
    if not api_key:
        # 检查用户目录的配置文件
        key_file = os.path.expanduser("~/.config/minimax_api_key")
        if os.path.exists(key_file):
            with open(key_file, 'r') as f:
                api_key = f.read().strip()
    
    if api_key:
        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=api_key,
                base_url="https://api.minimax.chat/v1/text/chatcompletion_v2"
            )
            return client, "minimax"
        except Exception as e:
            print(f"⚠️ MiniMax客户端初始化失败: {e}")
    
    # 尝试 OpenAI
    try:
        from openai import OpenAI
        client = OpenAI()
        return client, "openai"
    except Exception as e:
        print(f"⚠️ OpenAI客户端初始化失败: {e}")
        return None, None

# 舆情分析Prompt（核心）
ANALYZE_PROMPT = """你是一名A股二级市场舆情分析员，服务对象是短线和波段交易。

请基于以下雪球用户内容进行分析，并输出结构化JSON结果。

【分析要求】
1. 情绪方向：多 / 空 / 中性
2. 情绪强度：1-5（5为极强）
3. 预期变化：预期上修 / 预期下修 / 分歧加大 / 无明显变化
4. 信息类型：业绩 / 政策 / 资金 / 事件/传闻 / 情绪宣泄 / 其他
5. 是否属于重复信息或噪音（是/否）
6. 判断该信息是否可能领先价格（是/否）
7. 用一句话总结对未来3-5个交易日股价的潜在影响

【注意】
- 不要复述原文
- 聚焦"是否影响交易决策"
- 如果是情绪噪音，请明确指出
- 输出必须是纯JSON，不要包含markdown代码块
- 如果内容太短无法分析，返回 {"error": "内容过短"}

【内容】
{text}
"""

def analyze_with_llm(text: str, client=None, provider=None) -> Dict:
    """
    使用LLM分析单条内容
    
    Args:
        text: 要分析的文本
        client: LLM客户端
        provider: 供应商 (minimax/openai)
    
    Returns:
        dict: 分析结果
    """
    if not text or len(text.strip()) < 10:
        return {"error": "内容过短"}
    
    # 简单关键词分析（备用方案）
    keyword_analysis = simple_keyword_analysis(text)
    if keyword_analysis:
        return keyword_analysis
    
    # 构建消息
    messages = [
        {"role": "system", "content": "你是一个专业的A股舆情分析师，输出必须是严格的JSON格式。"},
        {"role": "user", "content": ANALYZE_PROMPT.format(text=text[:2000])}  # 限制长度
    ]
    
    try:
        # 获取客户端
        if client is None:
            client, provider = get_llm_client()
        
        if client is None:
            return {"error": "无法初始化LLM客户端"}
        
        # 确定模型名称
        if provider == "minimax":
            model_name = LLM_MODEL_CONFIG.replace("minimax/", "")
        else:
            model_name = LLM_MODEL_CONFIG
        
        resp = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
        
        content = resp.choices[0].message.content
        
        # 清理并解析JSON
        content = content.strip()
        # 移除markdown代码块标记
        content = content.replace("```json", "").replace("```", "").strip()
        
        result = json.loads(content)
        
        # 验证必要字段
        if "sentiment" not in result:
            return {"error": "解析结果缺少必要字段"}
        
        return result
        
    except json.JSONDecodeError as e:
        print(f"⚠️ JSON解析失败: {e}")
        return {"error": f"JSON解析失败: {str(e)}"}
    except Exception as e:
        print(f"❌ 分析失败: {e}")
        return {"error": str(e)}


def simple_keyword_analysis(text: str) -> Dict:
    """
    简单关键词分析（无LLM时的备用方案）
    基于关键词判断情绪
    """
    text_lower = text.lower()
    
    # 关键词
    positive_words = ['涨', '看好', '买入', '加仓', '利好', '突破', '新高', '做多', '抄底', '低吸', '金叉', '放量']
    negative_words = ['跌', '看空', '卖出', '减仓', '利空', '破位', '新低', '做空', '割肉', '高抛', '死叉', '缩量', '被套', '亏损']
    
    pos_count = sum(1 for w in positive_words if w in text_lower)
    neg_count = sum(1 for w in negative_words if w in text_lower)
    
    if pos_count > neg_count:
        sentiment = "多"
        intensity = min(1 + pos_count, 5)
    elif neg_count > pos_count:
        sentiment = "空"
        intensity = min(1 + neg_count, 5)
    else:
        sentiment = "中性"
        intensity = 1
    
    return {
        "sentiment": sentiment,
        "intensity": intensity,
        "expectation": "无明显变化",
        "info_type": "其他",
        "noise": "否",
        "leading": "否",
        "summary": "基于关键词的简单分析",
        "_method": "keyword"
    }

def batch_analyze(items: List[Dict], limit: int = 50) -> List[Dict]:
    """
    批量分析舆情内容
    
    Args:
        items: 标准化后的数据列表
        limit: 最大分析数量
    
    Returns:
        list: 带分析结果的数据列表
    """
    client, provider = get_llm_client()
    
    use_keyword = client is None
    if use_keyword:
        print(f"\n🔍 开始分析 {min(len(items), limit)} 条内容 (使用关键词分析)...")
    else:
        print(f"\n🔍 开始分析 {min(len(items), limit)} 条内容 (使用 {provider})...")
    
    results = []
    count = 0
    
    for item in items[:limit]:
        if count >= limit:
            break
            
        text = item.get("text", "")
        if not text or len(text.strip()) < 10:
            continue
        
        print(f"  分析 [{count+1}/{min(len(items), limit)}]: {text[:30]}...")
        
        # 分析
        if use_keyword:
            analysis = simple_keyword_analysis(text)
        else:
            analysis = analyze_with_llm(text, client, provider)
        
        item["analysis"] = analysis
        
        results.append(item)
        count += 1
        
        # 控速
        sleep_time = 1.5 if provider == "minimax" else 1.2
        time.sleep(0.3 if use_keyword else sleep_time)
    
    print(f"\n✅ 分析完成: {len(results)} 条")
    return results

def calculate_weight(item: Dict) -> float:
    """
    计算舆情权重分
    
    公式: 情绪强度 × 预期变化系数 × 是否领先 × 来源权重 × 市场环境
    
    Args:
        item: 带分析结果的数据项
    
    Returns:
        float: 权重分
    """
    analysis = item.get("analysis", {})
    
    if "error" in analysis:
        return 0.0
    
    # 1. 情绪强度 (1-5)
    intensity = analysis.get("intensity", 1)
    
    # 2. 预期变化系数
    expectation_map = {
        "预期上修": 1.0,
        "预期下修": 1.0,  # 空头信息同样有价值
        "分歧加大": 0.7,
        "无明显变化": 0.5,  # 改为0.5，避免关键词分析数据被过滤
    }
    expectation_coef = expectation_map.get(analysis.get("expectation", "无明显变化"), 0.5)
    
    # 3. 是否领先价格
    leading = 1.5 if analysis.get("leading") == "是" else 0.7
    
    # 4. 来源权重
    source_weights = {
        "status": 1.0,  # 普通帖子
        "livenews": 1.2,  # 快讯权重更高
    }
    source_weight = source_weights.get(item.get("type"), 1.0)
    
    # 5. 噪音过滤
    if analysis.get("noise") == "是":
        return 0.0
    
    # 计算权重
    weight = intensity * expectation_coef * leading * source_weight
    
    return round(weight, 2)

def enrich_with_weights(analyzed_items: List[Dict]) -> List[Dict]:
    """
    为分析结果添加权重
    
    Args:
        analyzed_items: 已分析的数据列表
    
    Returns:
        list: 添加权重后的数据
    """
    for item in analyzed_items:
        item["weight"] = calculate_weight(item)
    
    # 过滤零权重（噪音）
    filtered = [i for i in analyzed_items if i.get("weight", 0) > 0]
    
    return filtered

def save_analyzed_data(data: List[Dict], filename: str = "/tmp/xueqiu_analyzed.jsonl"):
    """
    保存分析结果
    
    Args:
        data: 分析后的数据
        filename: 输出文件
    """
    with open(filename, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    
    print(f"💾 已保存 {len(data)} 条分析结果到 {filename}")

if __name__ == "__main__":
    from normalize import load_raw_data
    from config import SYMBOLS
    
    print("=" * 60)
    print("🧠 舆情分析（LLM驱动）")
    print("=" * 60)
    
    # 加载标准化数据
    raw_file = "/tmp/xueqiu_normalized.jsonl"
    
    if not os.path.exists(raw_file):
        print("\n⚠️ 没有找到标准化数据，请先运行 normalize.py")
        sys.exit(1)
    
    # 读取数据
    items = []
    with open(raw_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))
    
    print(f"📥 加载 {len(items)} 条标准化数据")
    
    # 批量分析（限制数量以控制成本）
    analyzed = batch_analyze(items, limit=30)
    
    # 添加权重
    enriched = enrich_with_weights(analyzed)
    
    # 保存
    save_analyzed_data(enriched)
    
    # 统计
    positive = len([i for i in enriched if i.get("analysis", {}).get("sentiment") == "多"])
    negative = len([i for i in enriched if i.get("analysis", {}).get("sentiment") == "空"])
    neutral = len([i for i in enriched if i.get("analysis", {}).get("sentiment") == "中性"])
    
    print(f"\n📊 情绪统计:")
    print(f"  - 多: {positive} 条")
    print(f"  - 空: {negative} 条")
    print(f"  - 中: {neutral} 条")
