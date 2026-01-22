#!/usr/bin/env python3
"""
LLM 摘要/翻译模块

功能：
- 提供与 LLM 提供商无关的接口
- 翻译标题和摘要为中文
- 生成摘要和提取标签
- 支持优雅降级（无 LLM 时保留原文）
"""

import json
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# 尝试导入可选依赖
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


@dataclass
class TranslationResult:
    """翻译结果"""
    title_zh: str
    summary_zh: str
    tags: List[str] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None


# 多语言翻译 prompt 模板
TRANSLATION_PROMPTS = {
    "zh": """你是一个 AI 资讯翻译助手。请将以下英文内容翻译为中文。

要求：
1. 保持专业术语的准确性，模型名称、公司名称保留原文
2. 翻译风格简洁，信息密度高
3. 避免营销语气和夸张表达

输入：
标题：{title}
摘要：{summary}

请直接按以下 JSON 格式输出（不要有其他内容）：
{{"title_zh": "翻译后的中文标题", "summary_zh": "翻译后的中文摘要"}}""",

    "en": """You are an AI news translation assistant. Please translate the following content into English.

Requirements:
1. Keep technical terms accurate, preserve model names and company names
2. Use concise style with high information density
3. Avoid marketing tone and exaggeration

Input:
Title: {title}
Summary: {summary}

Please output directly in the following JSON format (no other content):
{{"title_zh": "Translated English title", "summary_zh": "Translated English summary"}}""",

    "ja": """あなたはAIニュース翻訳アシスタントです。以下の内容を日本語に翻訳してください。

要件：
1. 専門用語の正確性を保ち、モデル名や企業名は原文のまま
2. 簡潔なスタイルで情報密度を高く
3. マーケティング調や誇張表現を避ける

入力：
タイトル：{title}
要約：{summary}

以下のJSON形式で直接出力してください（他の内容は不要）：
{{"title_zh": "翻訳後の日本語タイトル", "summary_zh": "翻訳後の日本語要約"}}""",
}


def get_translation_prompt(target_lang: str, title: str, summary: str) -> str:
    """获取指定语言的翻译 prompt"""
    template = TRANSLATION_PROMPTS.get(target_lang, TRANSLATION_PROMPTS["zh"])
    return template.format(title=title, summary=summary)


@dataclass
class SummarizeInput:
    """摘要输入"""
    title_raw: str
    summary_raw: str
    content: str = ""  # 可选的正文片段
    target_lang: str = "zh"  # 目标语言：zh/en/ja


class LLMProvider(ABC):
    """LLM 提供商抽象基类"""

    @abstractmethod
    def translate(self, input_data: SummarizeInput) -> TranslationResult:
        """翻译标题和摘要"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """检查是否可用"""
        pass


class AnthropicProvider(LLMProvider):
    """Anthropic Claude 提供商"""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-haiku-20240307"):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model

    def is_available(self) -> bool:
        return HAS_ANTHROPIC and bool(self.api_key)

    def translate(self, input_data: SummarizeInput) -> TranslationResult:
        if not self.is_available():
            return TranslationResult(
                title_zh=input_data.title_raw,
                summary_zh=input_data.summary_raw,
                success=False,
                error="Anthropic API 不可用"
            )

        # 使用多语言 prompt
        prompt = get_translation_prompt(
            input_data.target_lang,
            input_data.title_raw,
            input_data.summary_raw
        )

        try:
            client = anthropic.Anthropic(api_key=self.api_key)
            response = client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            result_text = response.content[0].text.strip()
            # 尝试提取 JSON
            json_match = re.search(r'\{[^}]+\}', result_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return TranslationResult(
                    title_zh=data.get("title_zh", input_data.title_raw),
                    summary_zh=data.get("summary_zh", input_data.summary_raw),
                    success=True
                )
        except Exception as e:
            return TranslationResult(
                title_zh=input_data.title_raw,
                summary_zh=input_data.summary_raw,
                success=False,
                error=str(e)
            )

        return TranslationResult(
            title_zh=input_data.title_raw,
            summary_zh=input_data.summary_raw,
            success=False,
            error="无法解析响应"
        )


class OpenAIProvider(LLMProvider):
    """OpenAI 提供商"""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-3.5-turbo"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model

    def is_available(self) -> bool:
        return HAS_OPENAI and bool(self.api_key)

    def translate(self, input_data: SummarizeInput) -> TranslationResult:
        if not self.is_available():
            return TranslationResult(
                title_zh=input_data.title_raw,
                summary_zh=input_data.summary_raw,
                success=False,
                error="OpenAI API 不可用"
            )

        # 使用多语言 prompt
        prompt = get_translation_prompt(
            input_data.target_lang,
            input_data.title_raw,
            input_data.summary_raw
        )

        try:
            client = openai.OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024
            )
            result_text = response.choices[0].message.content.strip()
            json_match = re.search(r'\{[^}]+\}', result_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return TranslationResult(
                    title_zh=data.get("title_zh", input_data.title_raw),
                    summary_zh=data.get("summary_zh", input_data.summary_raw),
                    success=True
                )
        except Exception as e:
            return TranslationResult(
                title_zh=input_data.title_raw,
                summary_zh=input_data.summary_raw,
                success=False,
                error=str(e)
            )

        return TranslationResult(
            title_zh=input_data.title_raw,
            summary_zh=input_data.summary_raw,
            success=False,
            error="无法解析响应"
        )


class NoOpProvider(LLMProvider):
    """无操作提供商（用于测试或降级）"""

    def is_available(self) -> bool:
        return True

    def translate(self, input_data: SummarizeInput) -> TranslationResult:
        return TranslationResult(
            title_zh=input_data.title_raw,
            summary_zh=input_data.summary_raw,
            success=False,
            error="未配置 LLM 提供商"
        )


class LLMSummarizer:
    """LLM 摘要器"""

    def __init__(self, provider: Optional[LLMProvider] = None):
        """
        初始化摘要器

        Args:
            provider: LLM 提供商，None 时自动选择可用的提供商
        """
        self.provider = provider or self._auto_select_provider()

    def _auto_select_provider(self) -> LLMProvider:
        """自动选择可用的提供商"""
        # 优先 Anthropic
        anthropic_provider = AnthropicProvider()
        if anthropic_provider.is_available():
            return anthropic_provider

        # 其次 OpenAI
        openai_provider = OpenAIProvider()
        if openai_provider.is_available():
            return openai_provider

        # 降级到 NoOp
        return NoOpProvider()

    def is_available(self) -> bool:
        """检查是否有可用的 LLM"""
        return self.provider.is_available() and not isinstance(self.provider, NoOpProvider)

    def translate_article(
        self,
        title_raw: str,
        summary_raw: str,
        source_lang: str = "en",
        target_lang: str = "zh"
    ) -> TranslationResult:
        """
        翻译单篇文章

        Args:
            title_raw: 原始标题
            summary_raw: 原始摘要
            source_lang: 源语言
            target_lang: 目标语言

        Returns:
            TranslationResult
        """
        # 如果源语言已经是目标语言，不翻译
        if source_lang == target_lang:
            return TranslationResult(
                title_zh=title_raw,
                summary_zh=summary_raw,
                success=True
            )

        input_data = SummarizeInput(
            title_raw=title_raw,
            summary_raw=summary_raw,
            target_lang=target_lang
        )

        return self.provider.translate(input_data)

    def process_articles(
        self,
        articles: List[Any],
        source_lang_field: str = "source_lang",
        target_lang: str = "zh"
    ) -> List[Any]:
        """
        批量处理文章

        Args:
            articles: 文章列表（需要有 title, title_raw, summary, summary_raw 属性）
            source_lang_field: 表示源语言的字段名
            target_lang: 目标语言

        Returns:
            处理后的文章列表
        """
        for article in articles:
            title_raw = getattr(article, 'title_raw', '') or getattr(article, 'title', '')
            summary_raw = getattr(article, 'summary_raw', '') or getattr(article, 'summary', '')
            source_lang = getattr(article, source_lang_field, 'en')

            # 检测是否需要翻译（简单检测是否包含中文）
            has_chinese = bool(re.search(r'[\u4e00-\u9fff]', title_raw + summary_raw))
            if has_chinese:
                source_lang = "zh"

            result = self.translate_article(title_raw, summary_raw, source_lang, target_lang)

            # 更新文章
            if result.success:
                article.title = result.title_zh
                article.summary = result.summary_zh
            else:
                # 翻译失败，添加未翻译标记
                if hasattr(article, 'flags'):
                    if 'untranslated' not in article.flags:
                        article.flags.append('untranslated')

        return articles


def create_summarizer(
    provider_name: Optional[str] = None,
    api_key: Optional[str] = None
) -> LLMSummarizer:
    """
    创建摘要器

    Args:
        provider_name: 提供商名称（anthropic/openai/noop）
        api_key: API 密钥

    Returns:
        LLMSummarizer 实例
    """
    if provider_name == "anthropic":
        provider = AnthropicProvider(api_key=api_key)
    elif provider_name == "openai":
        provider = OpenAIProvider(api_key=api_key)
    elif provider_name == "noop":
        provider = NoOpProvider()
    else:
        provider = None  # 自动选择

    return LLMSummarizer(provider=provider)


# ============ 自测试 ============
def _run_self_tests():
    """运行内置自测试"""
    import sys

    errors = []

    # 测试 1: NoOp 提供商
    try:
        provider = NoOpProvider()
        assert provider.is_available(), "NoOp 应该总是可用"
        result = provider.translate(SummarizeInput(
            title_raw="Test Title",
            summary_raw="Test Summary"
        ))
        assert result.title_zh == "Test Title", "NoOp 应返回原文"
        assert not result.success, "NoOp 应标记为不成功（降级）"
        print("✓ 测试1: NoOp 提供商通过")
    except Exception as e:
        errors.append(f"测试1失败: {e}")
        print(f"✗ 测试1: {e}")

    # 测试 2: TranslationResult 数据结构
    try:
        result = TranslationResult(
            title_zh="测试标题",
            summary_zh="测试摘要",
            tags=["标签1", "标签2"],
            success=True
        )
        assert result.title_zh == "测试标题"
        assert len(result.tags) == 2
        print("✓ 测试2: TranslationResult 数据结构通过")
    except Exception as e:
        errors.append(f"测试2失败: {e}")
        print(f"✗ 测试2: {e}")

    # 测试 3: 自动选择提供商
    try:
        summarizer = LLMSummarizer()
        assert summarizer.provider is not None, "应有默认提供商"
        print(f"✓ 测试3: 自动选择提供商通过（选中: {type(summarizer.provider).__name__}）")
    except Exception as e:
        errors.append(f"测试3失败: {e}")
        print(f"✗ 测试3: {e}")

    # 测试 4: 创建摘要器便捷函数
    try:
        summarizer = create_summarizer("noop")
        assert isinstance(summarizer.provider, NoOpProvider)
        print("✓ 测试4: 创建摘要器便捷函数通过")
    except Exception as e:
        errors.append(f"测试4失败: {e}")
        print(f"✗ 测试4: {e}")

    # 测试 5: 中文检测（不翻译中文内容）
    try:
        summarizer = create_summarizer("noop")
        result = summarizer.translate_article(
            title_raw="这是中文标题",
            summary_raw="这是中文摘要",
            source_lang="zh",
            target_lang="zh"
        )
        assert result.success, "中文到中文不需要翻译"
        assert result.title_zh == "这是中文标题"
        print("✓ 测试5: 中文检测通过")
    except Exception as e:
        errors.append(f"测试5失败: {e}")
        print(f"✗ 测试5: {e}")

    # 测试 6: 批量处理（模拟）
    try:
        from dataclasses import dataclass, field

        @dataclass
        class TestArticle:
            title: str = ""
            title_raw: str = ""
            summary: str = ""
            summary_raw: str = ""
            flags: List[str] = field(default_factory=list)

        articles = [
            TestArticle(title_raw="English Title", summary_raw="English Summary"),
            TestArticle(title_raw="中文标题", summary_raw="中文摘要"),
        ]

        summarizer = create_summarizer("noop")
        processed = summarizer.process_articles(articles)

        assert len(processed) == 2
        # NoOp 应该将英文标记为未翻译
        assert "untranslated" in processed[0].flags
        print("✓ 测试6: 批量处理通过")
    except Exception as e:
        errors.append(f"测试6失败: {e}")
        print(f"✗ 测试6: {e}")

    # 测试 7: 提供商可用性检查
    try:
        anthropic_available = AnthropicProvider().is_available()
        openai_available = OpenAIProvider().is_available()
        print(f"✓ 测试7: 提供商可用性检查通过")
        print(f"    Anthropic: {'可用' if anthropic_available else '不可用'}")
        print(f"    OpenAI: {'可用' if openai_available else '不可用'}")
    except Exception as e:
        errors.append(f"测试7失败: {e}")
        print(f"✗ 测试7: {e}")

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
