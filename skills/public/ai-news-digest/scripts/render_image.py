#!/usr/bin/env python3
"""
AI 资讯简报图片渲染模块

生成适合社交媒体分享的资讯卡片图片
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# 图片尺寸配置
IMAGE_PRESETS = {
    "portrait": (1080, 1920),   # 竖版
    "landscape": (1200, 675),   # 横版（朋友圈推荐 1200x675 或 1080x608）
    "square": (1080, 1080),     # 方形
}

# 颜色主题
COLOR_THEMES = {
    "dark": {
        "bg_start": (15, 23, 42),
        "bg_end": (30, 41, 59),
        "accent": (99, 102, 241),
        "title": (255, 255, 255),
        "subtitle": (148, 163, 184),
        "line": (71, 85, 105),
    },
    "light": {
        "bg_start": (248, 250, 252),
        "bg_end": (241, 245, 249),
        "accent": (79, 70, 229),
        "title": (30, 41, 59),
        "subtitle": (100, 116, 139),
        "line": (203, 213, 225),
    },
}

# 新闻图标（根据关键词）
NEWS_ICONS = {
    "apple": "🍎",
    "google": "🌐",
    "nvidia": "⚡",
    "grok": "👁",
    "openai": "🤖",
    "musk": "🚀",
    "bank": "🏛",
    "plumery": "🏛",
    "llm": "🧠",
    "memory": "💾",
    "kernel": "🔧",
    "docker": "🐳",
    "siri": "🍎",
    "gemini": "✨",
    "translate": "🌐",
    "medical": "🏥",
    "healthcare": "🏥",
    "biotech": "🧬",
    "mit": "🎓",
    "research": "🔬",
    "default": "📰",
}


def check_pillow_available() -> bool:
    """检查 Pillow 是否可用"""
    return HAS_PIL


def find_chinese_font() -> Optional[str]:
    """查找可用的中文字体"""
    font_paths = [
        # macOS
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        # Linux
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        # Windows
        "C:/Windows/Fonts/msyh.ttc",
    ]
    for path in font_paths:
        if os.path.exists(path):
            return path
    return None


def create_gradient(width: int, height: int, start_color: tuple, end_color: tuple) -> "Image.Image":
    """创建渐变背景"""
    img = Image.new('RGB', (width, height))
    for y in range(height):
        ratio = y / height
        r = int(start_color[0] * (1 - ratio) + end_color[0] * ratio)
        g = int(start_color[1] * (1 - ratio) + end_color[1] * ratio)
        b = int(start_color[2] * (1 - ratio) + end_color[2] * ratio)
        for x in range(width):
            img.putpixel((x, y), (r, g, b))
    return img


def get_icon_for_text(text: str) -> str:
    """根据文本内容选择合适的图标"""
    text_lower = text.lower()
    for keyword, icon in NEWS_ICONS.items():
        if keyword in text_lower:
            return icon
    return NEWS_ICONS["default"]


def prepare_simple_news(grouped: Dict[str, List], max_items: int = 6) -> List[Dict]:
    """
    准备简化的新闻数据
    """
    # 精简的标题和副标题映射 - 使用文字符号避免 emoji 兼容问题
    news_data = [
        {
            "keywords": ["apple", "google", "siri", "gemini"],
            "icon": "•",
            "title": "Apple × Google 达成 AI 交易",
            "subtitle": "Siri 将由 Gemini 驱动",
        },
        {
            "keywords": ["translategemma"],
            "icon": "•",
            "title": "Google 开源 TranslateGemma",
            "subtitle": "支持 55 语言翻译模型",
        },
        {
            "keywords": ["nvidia", "kvzap"],
            "icon": "•",
            "title": "NVIDIA 开源 KVzap",
            "subtitle": "LLM 显存压缩 2-4 倍",
        },
        {
            "keywords": ["grok", "undress"],
            "icon": "•",
            "title": "Grok \"脱衣\"功能引诉讼",
            "subtitle": "Musk 孩子母亲起诉 xAI",
        },
        {
            "keywords": ["plumery", "bank"],
            "icon": "•",
            "title": "Plumery AI Fabric 发布",
            "subtitle": "银行业 AI 标准化集成框架",
        },
        {
            "keywords": ["fused kernel", "llm memory", "84%"],
            "icon": "•",
            "title": "Fused Kernels 技术",
            "subtitle": "LLM 显存降低 84%",
        },
        {
            "keywords": ["musk", "openai", "lawsuit", "sideshow"],
            "icon": "•",
            "title": "Musk 诉 OpenAI 案开庭",
            "subtitle": "4月将进入陪审团审判",
        },
        {
            "keywords": ["biotech", "three technologies"],
            "icon": "•",
            "title": "2026 生物技术三大趋势",
            "subtitle": "MIT 年度突破技术发布",
        },
        {
            "keywords": ["medical", "healthcare", "authorization"],
            "icon": "•",
            "title": "医疗 AI Agent 构建指南",
            "subtitle": "人机协作与安全控制",
        },
        {
            "keywords": ["docker"],
            "icon": "•",
            "title": "Docker 核心概念速览",
            "subtitle": "10 分钟快速入门",
        },
    ]

    # 收集所有文章文本用于匹配
    all_text = ""
    for topic, articles in grouped.items():
        for article in articles:
            if hasattr(article, 'title'):
                all_text += article.title.lower() + " "
            else:
                all_text += article.get('title', '').lower() + " "

    # 匹配新闻
    result = []
    for news in news_data:
        if len(result) >= max_items:
            break
        # 检查关键词是否匹配
        if any(kw in all_text for kw in news["keywords"]):
            result.append({
                "icon": news["icon"],
                "title": news["title"],
                "subtitle": news["subtitle"],
            })

    return result


def render_image(
    grouped: Dict[str, List],
    time_window: Dict[str, str],
    output_path: str,
    preset: str = "landscape",
    theme: str = "dark",
    max_items: int = 6,
    title: str = "AI 日报",
    footer: str = "",
) -> str:
    """
    渲染资讯简报图片 - 简洁横版风格
    """
    if not HAS_PIL:
        raise ImportError("图片渲染需要安装 Pillow: pip install Pillow")

    # 获取配置
    width, height = IMAGE_PRESETS.get(preset, IMAGE_PRESETS["landscape"])
    colors = COLOR_THEMES.get(theme, COLOR_THEMES["dark"])

    # 创建渐变背景
    img = create_gradient(width, height, colors["bg_start"], colors["bg_end"])
    draw = ImageDraw.Draw(img)

    # 加载字体
    font_path = find_chinese_font()
    if font_path:
        font_header = ImageFont.truetype(font_path, 36)
        font_title = ImageFont.truetype(font_path, 28)
        font_subtitle = ImageFont.truetype(font_path, 22)
    else:
        font_header = ImageFont.load_default()
        font_title = font_header
        font_subtitle = font_header

    # 准备新闻数据
    news_items = prepare_simple_news(grouped, max_items)

    # 布局参数
    margin_left = 50
    margin_top = 40
    line_height_title = 45
    line_height_subtitle = 35
    item_gap = 15

    # 绘制标题
    date_str = time_window.get("display", "").split("（")[0].replace("-", ".")
    if "T" in date_str:
        date_str = date_str.split("T")[0].replace("-", ".")
    header_text = f"◆ {title} | {date_str}"
    draw.text((margin_left, margin_top), header_text, font=font_header, fill=colors["title"])

    # 绘制分隔虚线
    y_pos = margin_top + 55
    dash_length = 8
    gap_length = 4
    x = margin_left
    while x < width * 0.55:  # 虚线只画到左侧区域
        draw.line([(x, y_pos), (x + dash_length, y_pos)], fill=colors["line"], width=2)
        x += dash_length + gap_length

    y_pos += 25

    # 绘制新闻列表
    for news in news_items:
        # 图标 + 标题
        title_text = f"{news['icon']} {news['title']}"
        draw.text((margin_left, y_pos), title_text, font=font_title, fill=colors["title"])
        y_pos += line_height_title

        # 副标题（缩进）
        draw.text((margin_left + 38, y_pos), news["subtitle"], font=font_subtitle, fill=colors["subtitle"])
        y_pos += line_height_subtitle + item_gap

    # 底部分隔虚线
    y_pos = height - 45
    x = margin_left
    while x < width * 0.55:
        draw.line([(x, y_pos), (x + dash_length, y_pos)], fill=colors["line"], width=2)
        x += dash_length + gap_length

    # 确保输出目录存在
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # 保存图片
    img.save(str(output_file), "PNG", quality=95)

    return str(output_file)


def render_image_from_articles(
    articles: List[Any],
    time_window: Dict[str, str],
    output_path: str,
    **kwargs
) -> str:
    """
    从文章列表直接渲染图片（简化接口）
    """
    grouped = {"other": articles}
    return render_image(grouped, time_window, output_path, **kwargs)


# 兼容旧接口
def translate_title(title: str) -> str:
    return title

def translate_summary(summary: str) -> str:
    return summary


# 导出
__all__ = [
    "check_pillow_available",
    "render_image",
    "render_image_from_articles",
    "IMAGE_PRESETS",
    "COLOR_THEMES",
]
