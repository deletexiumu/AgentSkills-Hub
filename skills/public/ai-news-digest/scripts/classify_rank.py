#!/usr/bin/env python3
"""
主题分类与排序模块

功能：
- 基于关键词的主题分类
- 基于时间、信源权重、关键词的排序
- 支持用户自定义包含/排除关键词
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

# 主题定义
TOPICS = ["research", "product", "opensource", "funding", "policy", "other"]

# 主题关键词（强指示词权重 = 3，普通词权重 = 1）
# 格式：(关键词, 权重)
TOPIC_KEYWORDS: Dict[str, List[Tuple[str, int]]] = {
    "research": [
        # 强指示词
        ("paper", 3), ("research", 3), ("study", 3), ("arxiv", 3), ("preprint", 3),
        ("论文", 3), ("研究", 3), ("学术", 3), ("实验", 3),
        ("benchmark", 3), ("evaluation", 3), ("sota", 3), ("state-of-the-art", 3),
        ("neural", 2), ("transformer", 2), ("attention", 2), ("diffusion", 2),
        ("training", 2), ("fine-tuning", 2), ("pre-training", 2),
        # 实验室
        ("openai", 2), ("anthropic", 2), ("deepmind", 2), ("google brain", 2),
        ("stanford", 2), ("berkeley", 2), ("mit", 2), ("cmu", 2),
        ("清华", 2), ("北大", 2), ("中科院", 2),
        # 研究领域
        ("nlp", 1), ("natural language", 1), ("computer vision", 1),
        ("reinforcement learning", 2), ("rlhf", 2),
        ("multimodal", 1), ("reasoning", 2), ("chain-of-thought", 2),
    ],
    "product": [
        # 强指示词
        ("launch", 3), ("release", 3), ("announce", 3), ("introduce", 3), ("unveil", 3),
        ("发布", 3), ("上线", 3), ("推出", 3), ("更新", 3), ("升级", 3),
        ("api", 2), ("sdk", 2), ("platform", 2), ("service", 2),
        ("gpt-4", 3), ("gpt-5", 3), ("claude", 3), ("gemini", 3), ("llama", 2),
        ("chatgpt", 3), ("copilot", 2), ("bard", 2),
        # 产品类型
        ("assistant", 2), ("chatbot", 2), ("agent", 2),
        ("助手", 2), ("机器人", 2), ("智能体", 2),
        ("app", 1), ("tool", 1), ("plugin", 1),
        # 功能
        ("feature", 1), ("capability", 1), ("improvement", 1),
        ("功能", 1), ("能力", 1), ("改进", 1),
    ],
    "opensource": [
        # 强指示词
        ("open source", 3), ("opensource", 3), ("open-source", 3),
        ("开源", 3), ("开放源代码", 3),
        ("github", 2), ("gitlab", 2), ("huggingface", 2),
        ("repository", 2), ("repo", 2), ("library", 2), ("framework", 2),
        ("mit license", 2), ("apache license", 2),
        # 工具框架
        ("pytorch", 2), ("tensorflow", 2), ("jax", 2),
        ("langchain", 2), ("llamaindex", 2), ("autogen", 2),
        ("vllm", 2), ("ollama", 2), ("llama.cpp", 2),
        # 工程实践
        ("tutorial", 1), ("guide", 1), ("how-to", 1),
        ("教程", 1), ("指南", 1), ("实践", 1),
        ("deployment", 1), ("inference", 1), ("serving", 1),
        ("部署", 1), ("推理", 1),
    ],
    "funding": [
        # 强指示词
        ("funding", 3), ("investment", 3), ("raise", 3),
        ("series a", 3), ("series b", 3), ("series c", 3),
        ("融资", 3), ("投资", 3), ("募资", 3), ("轮", 2),
        ("valuation", 3), ("billion", 2), ("million", 2),
        ("估值", 3), ("亿", 2),
        ("acquisition", 3), ("acquire", 3), ("merge", 3),
        ("收购", 3), ("并购", 3), ("合并", 3),
        # 商业活动
        ("partnership", 2), ("collaborate", 1), ("deal", 2),
        ("合作", 1), ("战略", 1), ("协议", 1),
        ("ipo", 3), ("public", 1), ("stock", 1),
        ("上市", 2),
        # 公司
        ("startup", 2), ("unicorn", 2),
        ("创业", 2), ("独角兽", 2),
        ("vc", 2), ("venture capital", 2),
        ("风投", 2), ("资本", 1),
    ],
    "policy": [
        # 强指示词
        ("regulation", 3), ("policy", 3), ("law", 3), ("legislation", 3),
        ("监管", 3), ("政策", 3), ("法规", 3), ("立法", 3),
        ("safety", 3), ("security", 2), ("alignment", 3),
        ("安全", 2), ("对齐", 3), ("可信", 2),
        ("ethics", 3), ("ethical", 3), ("responsible", 2),
        ("伦理", 3), ("道德", 2), ("负责任", 2),
        # 机构
        ("eu", 2), ("european union", 2), ("congress", 2), ("senate", 2),
        ("欧盟", 2), ("国会", 2), ("政府", 1), ("工信部", 2),
        # 议题
        ("bias", 2), ("fairness", 2), ("discrimination", 2),
        ("偏见", 2), ("公平", 2), ("歧视", 2),
        ("privacy", 2), ("copyright", 2), ("intellectual property", 2),
        ("隐私", 2), ("版权", 2), ("知识产权", 2),
        ("deepfake", 3), ("misinformation", 2),
        ("深度伪造", 3), ("虚假信息", 2),
        ("existential risk", 3), ("x-risk", 3), ("agi safety", 3),
        ("生存风险", 3),
    ],
}


@dataclass
class ClassifyConfig:
    """分类配置"""
    min_score_threshold: int = 2  # 最低分数阈值
    include_keywords: Dict[str, List[str]] = field(default_factory=dict)  # 额外包含的关键词
    exclude_keywords: Dict[str, List[str]] = field(default_factory=dict)  # 排除的关键词


@dataclass
class RankConfig:
    """排序配置"""
    source_weights: Dict[str, int] = field(default_factory=dict)  # 信源权重
    recency_weight: float = 1.0  # 时间新鲜度权重
    source_weight: float = 0.5  # 信源权重系数
    keyword_boost_weight: float = 0.3  # 关键词加成权重


class TopicClassifier:
    """主题分类器"""

    def __init__(self, config: Optional[ClassifyConfig] = None):
        self.config = config or ClassifyConfig()
        self._build_keyword_patterns()

    def _build_keyword_patterns(self) -> None:
        """构建关键词匹配模式"""
        self.patterns: Dict[str, List[Tuple[re.Pattern, int]]] = {}

        for topic, keywords in TOPIC_KEYWORDS.items():
            patterns = []
            for keyword, weight in keywords:
                # 转义特殊字符，创建不区分大小写的模式
                pattern = re.compile(
                    r"\b" + re.escape(keyword).replace(r"\ ", r"\s+") + r"\b",
                    re.IGNORECASE
                )
                patterns.append((pattern, weight))

            # 添加用户自定义包含关键词
            if topic in self.config.include_keywords:
                for keyword in self.config.include_keywords[topic]:
                    pattern = re.compile(r"\b" + re.escape(keyword) + r"\b", re.IGNORECASE)
                    patterns.append((pattern, 3))  # 用户指定的关键词给高权重

            self.patterns[topic] = patterns

    def classify(self, title: str, summary: str = "", tags: List[str] = None) -> Tuple[str, Dict[str, int]]:
        """
        对文章进行主题分类

        Args:
            title: 标题
            summary: 摘要
            tags: 标签列表

        Returns:
            (主题, 各主题得分)
        """
        text = f"{title} {summary} {' '.join(tags or [])}"
        scores: Dict[str, int] = {}

        for topic, patterns in self.patterns.items():
            score = 0
            for pattern, weight in patterns:
                if pattern.search(text):
                    score += weight
            scores[topic] = score

        # 检查排除关键词
        for topic, exclude_words in self.config.exclude_keywords.items():
            for word in exclude_words:
                if word.lower() in text.lower():
                    scores[topic] = 0
                    break

        # 找出最高分主题
        if not scores:
            return "other", scores

        max_topic = max(scores, key=lambda t: scores[t])
        max_score = scores[max_topic]

        if max_score < self.config.min_score_threshold:
            return "other", scores

        return max_topic, scores


class ArticleRanker:
    """文章排序器"""

    def __init__(self, config: Optional[RankConfig] = None):
        self.config = config or RankConfig()

    def calculate_score(
        self,
        published_at: Optional[str],
        source_id: str,
        topic_score: int,
        reference_time: Optional[datetime] = None
    ) -> float:
        """
        计算文章排序得分

        Args:
            published_at: 发布时间（ISO 8601）
            source_id: 信源 ID
            topic_score: 主题分类得分
            reference_time: 参考时间（用于计算新鲜度）

        Returns:
            排序得分（越高越优先）
        """
        score = 0.0

        # 1. 时间新鲜度得分
        if published_at:
            try:
                pub_time = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                ref_time = reference_time or datetime.now(ZoneInfo("Asia/Shanghai"))

                # 计算小时差
                hours_diff = (ref_time - pub_time).total_seconds() / 3600
                # 新鲜度衰减：24 小时内满分，之后逐渐衰减
                recency_score = max(0, 100 - hours_diff * 2)
                score += recency_score * self.config.recency_weight
            except (ValueError, AttributeError):
                pass

        # 2. 信源权重得分
        source_weight = self.config.source_weights.get(source_id, 5)  # 默认 5
        score += source_weight * 10 * self.config.source_weight

        # 3. 关键词匹配加成
        score += topic_score * 5 * self.config.keyword_boost_weight

        return score


def classify_and_rank_articles(
    items: List,
    source_weights: Optional[Dict[str, int]] = None,
    classify_config: Optional[ClassifyConfig] = None,
    rank_config: Optional[RankConfig] = None
) -> Dict[str, List]:
    """
    对文章列表进行分类和排序

    Args:
        items: 文章列表（需要有 title, summary, tags, published_at, source_id 属性）
        source_weights: 信源权重字典
        classify_config: 分类配置
        rank_config: 排序配置

    Returns:
        按主题分组并排序的字典
    """
    classifier = TopicClassifier(classify_config)

    if rank_config is None:
        rank_config = RankConfig()
    if source_weights:
        rank_config.source_weights = source_weights
    ranker = ArticleRanker(rank_config)

    # 初始化分组
    grouped: Dict[str, List] = {topic: [] for topic in TOPICS}

    # 分类
    for item in items:
        topic, scores = classifier.classify(
            getattr(item, 'title', ''),
            getattr(item, 'summary', ''),
            getattr(item, 'tags', [])
        )
        item.topic = topic

        # 计算排序得分
        score = ranker.calculate_score(
            getattr(item, 'published_at', None),
            getattr(item, 'source_id', ''),
            scores.get(topic, 0)
        )
        item.score = score

        grouped[topic].append(item)

    # 每个分组内按得分降序排序
    for topic in grouped:
        grouped[topic].sort(key=lambda x: getattr(x, 'score', 0), reverse=True)

    return grouped


# ============ 自测试 ============
def _run_self_tests():
    """运行内置自测试"""
    import sys
    from dataclasses import dataclass, field

    errors = []

    # 测试数据类
    @dataclass
    class TestItem:
        title: str
        summary: str = ""
        tags: List[str] = field(default_factory=list)
        published_at: Optional[str] = None
        source_id: str = "test"
        topic: str = "other"
        score: float = 0.0

    # 测试 1: 研究类分类
    try:
        classifier = TopicClassifier()
        topic, scores = classifier.classify("New Research Paper on Transformer Architecture", "A study of attention mechanisms")
        assert topic == "research", f"应分类为 research: {topic}"
        print("✓ 测试1: 研究类分类通过")
    except Exception as e:
        errors.append(f"测试1失败: {e}")
        print(f"✗ 测试1: {e}")

    # 测试 2: 产品类分类
    try:
        topic, scores = classifier.classify("OpenAI Launches GPT-5", "New AI assistant with improved capabilities")
        assert topic == "product", f"应分类为 product: {topic}"
        print("✓ 测试2: 产品类分类通过")
    except Exception as e:
        errors.append(f"测试2失败: {e}")
        print(f"✗ 测试2: {e}")

    # 测试 3: 开源类分类
    try:
        topic, scores = classifier.classify("LangChain 发布新版本", "开源框架更新，支持更多功能")
        assert topic == "opensource", f"应分类为 opensource: {topic}"
        print("✓ 测试3: 开源类分类通过")
    except Exception as e:
        errors.append(f"测试3失败: {e}")
        print(f"✗ 测试3: {e}")

    # 测试 4: 投融资类分类
    try:
        topic, scores = classifier.classify("AI Startup Raises $100 Million in Series B Funding")
        assert topic == "funding", f"应分类为 funding: {topic}"
        print("✓ 测试4: 投融资类分类通过")
    except Exception as e:
        errors.append(f"测试4失败: {e}")
        print(f"✗ 测试4: {e}")

    # 测试 5: 政策类分类
    try:
        topic, scores = classifier.classify("EU Proposes New AI Regulation", "New safety and ethics requirements for AI systems")
        assert topic == "policy", f"应分类为 policy: {topic}"
        print("✓ 测试5: 政策类分类通过")
    except Exception as e:
        errors.append(f"测试5失败: {e}")
        print(f"✗ 测试5: {e}")

    # 测试 6: 未分类（other）
    try:
        topic, scores = classifier.classify("今天天气真好")
        assert topic == "other", f"应分类为 other: {topic}"
        print("✓ 测试6: 未分类（other）通过")
    except Exception as e:
        errors.append(f"测试6失败: {e}")
        print(f"✗ 测试6: {e}")

    # 测试 7: 排序得分计算
    try:
        ranker = ArticleRanker(RankConfig(source_weights={"source1": 9, "source2": 5}))
        now = datetime.now(ZoneInfo("Asia/Shanghai"))

        score1 = ranker.calculate_score(
            now.isoformat(),
            "source1",
            10,
            now
        )
        score2 = ranker.calculate_score(
            now.isoformat(),
            "source2",
            10,
            now
        )
        assert score1 > score2, f"高权重信源应有更高得分: {score1} vs {score2}"
        print("✓ 测试7: 排序得分计算通过")
    except Exception as e:
        errors.append(f"测试7失败: {e}")
        print(f"✗ 测试7: {e}")

    # 测试 8: 完整分类排序流程
    try:
        items = [
            TestItem(title="OpenAI 发布 GPT-5", published_at="2026-01-16T10:00:00+08:00", source_id="s1"),
            TestItem(title="New Research Paper", published_at="2026-01-16T08:00:00+08:00", source_id="s2"),
            TestItem(title="AI Startup 融资", published_at="2026-01-16T12:00:00+08:00", source_id="s3"),
        ]
        grouped = classify_and_rank_articles(items, source_weights={"s1": 9, "s2": 7, "s3": 5})

        assert len(grouped["product"]) >= 1, "应有产品类文章"
        assert len(grouped["research"]) >= 1, "应有研究类文章"
        assert len(grouped["funding"]) >= 1, "应有投融资类文章"
        print("✓ 测试8: 完整分类排序流程通过")
    except Exception as e:
        errors.append(f"测试8失败: {e}")
        print(f"✗ 测试8: {e}")

    # 汇总
    print()
    if errors:
        print(f"自测试完成，{len(errors)} 个失败:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("✓ 所有自测试通过")
        sys.exit(0)


if __name__ == "__main__":
    _run_self_tests()
