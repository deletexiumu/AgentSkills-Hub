#!/usr/bin/env python3
"""
时间窗口解析模块

支持自然语言（今天/昨天/前天/today/yesterday）和日期字符串（YYYY-MM-DD）
解析为带时区的 (since, until) ISO 8601 时间戳。
"""

from datetime import datetime, timedelta
from typing import Tuple, Optional
import re

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo  # Python < 3.9 兼容


# 默认时区：UTC+8（Asia/Shanghai）
DEFAULT_TIMEZONE = "Asia/Shanghai"

# 自然语言映射：相对于当天的偏移天数
NATURAL_LANGUAGE_MAP = {
    "今天": 0,
    "today": 0,
    "昨天": -1,
    "yesterday": -1,
    "前天": -2,
}

# 日期格式正则
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def normalize_timezone(tz: Optional[str]) -> ZoneInfo:
    """
    将时区字符串规范化为 ZoneInfo 对象

    支持格式：
    - IANA 时区名：Asia/Shanghai, America/New_York
    - UTC 偏移量：UTC+8, UTC-5, +08:00, -05:00

    Args:
        tz: 时区字符串，None 时使用默认时区

    Returns:
        ZoneInfo 对象
    """
    if tz is None:
        return ZoneInfo(DEFAULT_TIMEZONE)

    tz = tz.strip()

    # 直接尝试作为 IANA 时区名
    try:
        return ZoneInfo(tz)
    except KeyError:
        pass

    # 处理 UTC+N / UTC-N 格式
    utc_offset_match = re.match(r"^UTC([+-])(\d{1,2})$", tz, re.IGNORECASE)
    if utc_offset_match:
        sign, hours = utc_offset_match.groups()
        offset_hours = int(hours)
        if sign == "-":
            offset_hours = -offset_hours
        # 转换为 Etc/GMT 格式（注意符号相反）
        if offset_hours == 0:
            return ZoneInfo("UTC")
        # Etc/GMT+N 表示 UTC-N（符号相反）
        etc_offset = -offset_hours
        etc_tz = f"Etc/GMT{'+' if etc_offset >= 0 else ''}{etc_offset}"
        try:
            return ZoneInfo(etc_tz)
        except KeyError:
            pass

    # 处理 +HH:MM / -HH:MM 格式
    offset_match = re.match(r"^([+-])(\d{2}):(\d{2})$", tz)
    if offset_match:
        sign, hours, minutes = offset_match.groups()
        offset_hours = int(hours)
        if int(minutes) == 0 and offset_hours <= 12:
            if sign == "-":
                offset_hours = -offset_hours
            if offset_hours == 0:
                return ZoneInfo("UTC")
            etc_offset = -offset_hours
            etc_tz = f"Etc/GMT{'+' if etc_offset >= 0 else ''}{etc_offset}"
            try:
                return ZoneInfo(etc_tz)
            except KeyError:
                pass

    # 都无法解析时，回退到默认时区
    return ZoneInfo(DEFAULT_TIMEZONE)


def parse_time_window(
    text: Optional[str] = None,
    tz: Optional[str] = None
) -> Tuple[str, str]:
    """
    解析时间窗口文本，返回带时区的 (since, until) ISO 8601 时间戳

    Args:
        text: 时间窗口描述，支持：
              - None 或空字符串：等同于 "今天"
              - 自然语言：今天/昨天/前天/today/yesterday
              - 日期字符串：YYYY-MM-DD
        tz: 时区字符串，None 时使用 UTC+8（Asia/Shanghai）

    Returns:
        (since, until) 元组，均为 ISO 8601 格式字符串
        - since: 当天 00:00:00
        - until: 当天 23:59:59

    Raises:
        ValueError: 无法解析的时间窗口文本

    Examples:
        >>> parse_time_window("今天", "Asia/Shanghai")
        ('2026-01-16T00:00:00+08:00', '2026-01-16T23:59:59+08:00')

        >>> parse_time_window("2026-01-15", "UTC+8")
        ('2026-01-15T00:00:00+08:00', '2026-01-15T23:59:59+08:00')
    """
    zone = normalize_timezone(tz)
    now = datetime.now(zone)

    # 默认或空字符串 → 今天
    if text is None or text.strip() == "":
        text = "今天"

    text = text.strip().lower()

    # 自然语言解析
    # 先尝试原始文本
    if text in NATURAL_LANGUAGE_MAP:
        offset_days = NATURAL_LANGUAGE_MAP[text]
        target_date = (now + timedelta(days=offset_days)).date()
    # 再尝试中文（非小写匹配）
    elif text.strip() in NATURAL_LANGUAGE_MAP:
        offset_days = NATURAL_LANGUAGE_MAP[text.strip()]
        target_date = (now + timedelta(days=offset_days)).date()
    # 日期字符串 YYYY-MM-DD
    elif DATE_PATTERN.match(text):
        try:
            target_date = datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError as e:
            raise ValueError(f"无效的日期格式: {text}") from e
    else:
        # 尝试原始大小写的中文
        original_text = text.strip()
        for key in NATURAL_LANGUAGE_MAP:
            if key.lower() == original_text.lower() or key == original_text:
                offset_days = NATURAL_LANGUAGE_MAP[key]
                target_date = (now + timedelta(days=offset_days)).date()
                break
        else:
            raise ValueError(f"无法解析的时间窗口: {text}")

    # 构建当天的起止时间
    since_dt = datetime(
        target_date.year, target_date.month, target_date.day,
        0, 0, 0, tzinfo=zone
    )
    until_dt = datetime(
        target_date.year, target_date.month, target_date.day,
        23, 59, 59, tzinfo=zone
    )

    return (since_dt.isoformat(), until_dt.isoformat())


def get_timezone_display(tz: Optional[str] = None) -> str:
    """
    获取时区的显示名称

    Args:
        tz: 时区字符串

    Returns:
        用于显示的时区名称
    """
    zone = normalize_timezone(tz)
    return str(zone)


# ============ 自测试 ============
def _run_self_tests():
    """运行内置自测试"""
    import sys

    errors = []

    # 测试 1: 默认（None）应等同于今天
    try:
        since, until = parse_time_window(None, "Asia/Shanghai")
        assert "T00:00:00" in since, f"since 应包含 00:00:00: {since}"
        assert "T23:59:59" in until, f"until 应包含 23:59:59: {until}"
        assert "+08:00" in since, f"since 应包含 +08:00: {since}"
        print("✓ 测试1: 默认值（None → 今天）通过")
    except Exception as e:
        errors.append(f"测试1失败: {e}")
        print(f"✗ 测试1: {e}")

    # 测试 2: "今天"
    try:
        since, until = parse_time_window("今天", "Asia/Shanghai")
        assert "T00:00:00" in since
        assert "+08:00" in since
        print("✓ 测试2: '今天' 通过")
    except Exception as e:
        errors.append(f"测试2失败: {e}")
        print(f"✗ 测试2: {e}")

    # 测试 3: "today"
    try:
        since, until = parse_time_window("today", "Asia/Shanghai")
        assert "T00:00:00" in since
        print("✓ 测试3: 'today' 通过")
    except Exception as e:
        errors.append(f"测试3失败: {e}")
        print(f"✗ 测试3: {e}")

    # 测试 4: "昨天"
    try:
        since, until = parse_time_window("昨天", "Asia/Shanghai")
        assert "T00:00:00" in since
        print("✓ 测试4: '昨天' 通过")
    except Exception as e:
        errors.append(f"测试4失败: {e}")
        print(f"✗ 测试4: {e}")

    # 测试 5: "yesterday"
    try:
        since, until = parse_time_window("yesterday", "Asia/Shanghai")
        assert "T00:00:00" in since
        print("✓ 测试5: 'yesterday' 通过")
    except Exception as e:
        errors.append(f"测试5失败: {e}")
        print(f"✗ 测试5: {e}")

    # 测试 6: "前天"
    try:
        since, until = parse_time_window("前天", "Asia/Shanghai")
        assert "T00:00:00" in since
        print("✓ 测试6: '前天' 通过")
    except Exception as e:
        errors.append(f"测试6失败: {e}")
        print(f"✗ 测试6: {e}")

    # 测试 7: YYYY-MM-DD 格式
    try:
        since, until = parse_time_window("2026-01-15", "Asia/Shanghai")
        assert "2026-01-15T00:00:00" in since, f"since 应包含指定日期: {since}"
        assert "2026-01-15T23:59:59" in until, f"until 应包含指定日期: {until}"
        print("✓ 测试7: 'YYYY-MM-DD' 格式通过")
    except Exception as e:
        errors.append(f"测试7失败: {e}")
        print(f"✗ 测试7: {e}")

    # 测试 8: UTC+8 时区别名
    try:
        since, until = parse_time_window("今天", "UTC+8")
        assert "+08:00" in since or "Asia" in since, f"应识别 UTC+8: {since}"
        print("✓ 测试8: 'UTC+8' 时区通过")
    except Exception as e:
        errors.append(f"测试8失败: {e}")
        print(f"✗ 测试8: {e}")

    # 测试 9: 无效输入应抛出 ValueError
    try:
        parse_time_window("无效的时间", "Asia/Shanghai")
        errors.append("测试9失败: 应抛出 ValueError")
        print("✗ 测试9: 应抛出 ValueError 但未抛出")
    except ValueError:
        print("✓ 测试9: 无效输入正确抛出 ValueError")
    except Exception as e:
        errors.append(f"测试9失败: 非预期异常 {e}")
        print(f"✗ 测试9: {e}")

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
