#!/usr/bin/env python3
"""
微信聊天数据提取脚本

提取当日聊天数据，输出统计信息和对话内容，供 AI 概括提炼。
"""

import argparse
import duckdb
from datetime import datetime, date
from collections import defaultdict
import sys


class WeChatDataExtractor:
    """微信数据提取器"""

    # 工作相关关键词
    WORK_KEYWORDS = [
        '运维', '开发', '技术', '对接', '沟通', '项目', '实施',
        '测试', '产业', '平台', '系统', '数据', '中台', '神码',
        '神州', '东方', '国信', '拓尔思', '上奇', '永洪', '大数据部', '国创'
    ]

    # 趣事群（非工作群中活跃的）
    FUN_CHAT_PATTERNS = ['秀坊', '业主群', '弓月城', 'AI交流']

    def __init__(self, db_path: str, target_date: date):
        self.db_path = db_path
        self.target_date = target_date
        self.conn = None

        # 时间戳范围 (毫秒)
        self.ts_start = int(datetime(target_date.year, target_date.month, target_date.day).timestamp() * 1000)
        self.ts_end = int(datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59).timestamp() * 1000)

    def connect(self):
        """连接数据库"""
        try:
            self.conn = duckdb.connect(self.db_path, read_only=True, config={'access_mode': 'read_only'})
        except Exception as e:
            print(f"数据库连接失败: {e}", file=sys.stderr)
            sys.exit(1)

    def close(self):
        """关闭连接"""
        if self.conn:
            self.conn.close()

    def is_work_chat(self, chat_name: str) -> bool:
        """判断是否工作相关聊天"""
        if not chat_name:
            return False
        return any(kw in chat_name for kw in self.WORK_KEYWORDS)

    def is_fun_chat(self, chat_name: str) -> bool:
        """判断是否趣事群"""
        if not chat_name:
            return False
        return any(pattern in chat_name for pattern in self.FUN_CHAT_PATTERNS)

    def extract_statistics(self):
        """提取统计数据"""
        print("=" * 60)
        print(f"【数据统计】{self.target_date}")
        print("=" * 60)

        # 总消息数
        total = self.conn.execute(f"""
            SELECT COUNT(*) FROM wechat_message
            WHERE message_ts >= {self.ts_start} AND message_ts <= {self.ts_end}
        """).fetchone()[0]
        print(f"\n消息总数: {total:,}")

        # 活跃聊天数
        chat_count = self.conn.execute(f"""
            SELECT COUNT(DISTINCT chat_id) FROM wechat_message
            WHERE message_ts >= {self.ts_start} AND message_ts <= {self.ts_end}
        """).fetchone()[0]
        print(f"活跃聊天: {chat_count}")

        # 活跃人数
        sender_count = self.conn.execute(f"""
            SELECT COUNT(DISTINCT sender_id) FROM wechat_message
            WHERE message_ts >= {self.ts_start} AND message_ts <= {self.ts_end}
              AND sender_id IS NOT NULL
        """).fetchone()[0]
        print(f"活跃人数: {sender_count}")

        # 峰值时段
        peak = self.conn.execute(f"""
            SELECT EXTRACT(HOUR FROM to_timestamp(message_ts/1000)) as hour, COUNT(*) as cnt
            FROM wechat_message
            WHERE message_ts >= {self.ts_start} AND message_ts <= {self.ts_end}
            GROUP BY hour
            ORDER BY cnt DESC
            LIMIT 1
        """).fetchone()
        if peak:
            print(f"峰值时段: {int(peak[0]):02d}:00 ({peak[1]}条)")

        # 聊天活跃度 TOP 15
        print("\n--- 聊天活跃度 TOP 15 ---")
        chats = self.conn.execute(f"""
            SELECT chat_name, chat_type, COUNT(*) as cnt
            FROM wechat_message
            WHERE message_ts >= {self.ts_start} AND message_ts <= {self.ts_end}
            GROUP BY chat_id, chat_name, chat_type
            ORDER BY cnt DESC
            LIMIT 15
        """).fetchall()
        for i, (name, ctype, cnt) in enumerate(chats, 1):
            type_name = "群聊" if ctype == 2 else "私聊"
            print(f"  {i}. [{type_name}] {name}: {cnt}")

        # 消息类型分布
        print("\n--- 消息类型分布 ---")
        import re
        types = self.conn.execute(f"""
            SELECT msg_type_name, COUNT(*) as cnt
            FROM wechat_message
            WHERE message_ts >= {self.ts_start} AND message_ts <= {self.ts_end}
            GROUP BY msg_type_name
            ORDER BY cnt DESC
        """).fetchall()
        for name, cnt in types:
            if name and re.match(r'^[\u4e00-\u9fa5a-zA-Z]+$', name):
                print(f"  {name}: {cnt:,}")

        # 活跃发送者 TOP 10
        print("\n--- 活跃发送者 TOP 10 ---")
        senders = self.conn.execute(f"""
            SELECT sender_name, COUNT(*) as cnt
            FROM wechat_message
            WHERE message_ts >= {self.ts_start} AND message_ts <= {self.ts_end}
              AND sender_name IS NOT NULL AND sender_name != ''
            GROUP BY sender_id, sender_name
            ORDER BY cnt DESC
            LIMIT 10
        """).fetchall()
        for i, (sender, cnt) in enumerate(senders, 1):
            print(f"  {i}. {sender}: {cnt}")

        # 时间分布
        print("\n--- 消息时间分布 ---")
        hours = self.conn.execute(f"""
            SELECT EXTRACT(HOUR FROM to_timestamp(message_ts/1000)) as hour, COUNT(*) as cnt
            FROM wechat_message
            WHERE message_ts >= {self.ts_start} AND message_ts <= {self.ts_end}
            GROUP BY hour
            ORDER BY hour
        """).fetchall()
        hourly = {int(h): c for h, c in hours}
        max_cnt = max(hourly.values()) if hourly else 1
        for hour in range(24):
            cnt = hourly.get(hour, 0)
            if cnt > 0:
                bar_len = int(cnt / max_cnt * 30)
                bar = "█" * bar_len
                print(f"  {hour:02d}:00 | {bar:<30} {cnt:>4}")

    def extract_work_chats(self):
        """提取工作群完整对话"""
        print("\n\n")
        print("=" * 60)
        print("【工作相关聊天 - 完整上下文】")
        print("=" * 60)

        # 获取活跃的工作聊天
        work_chats = self.conn.execute(f"""
            SELECT chat_name, COUNT(*) as cnt
            FROM wechat_message
            WHERE message_ts >= {self.ts_start} AND message_ts <= {self.ts_end}
            GROUP BY chat_name
            HAVING cnt >= 10
            ORDER BY cnt DESC
        """).fetchall()

        for chat_name, cnt in work_chats:
            if not self.is_work_chat(chat_name):
                continue

            print(f"\n\n### {chat_name} ({cnt}条)")
            print("-" * 50)

            msgs = self.conn.execute(f"""
                SELECT sender_name, text, message_ts
                FROM wechat_message
                WHERE message_ts >= {self.ts_start} AND message_ts <= {self.ts_end}
                  AND chat_name = ?
                  AND msg_type = 1
                  AND text IS NOT NULL AND text != ''
                ORDER BY message_ts
            """, [chat_name]).fetchall()

            for sender, text, ts in msgs[:50]:
                time_str = datetime.fromtimestamp(ts / 1000).strftime('%H:%M')
                text_short = text[:120].replace('\n', ' ')
                print(f"{time_str} {sender}: {text_short}")

    def extract_fun_chats(self):
        """提取趣事群对话"""
        print("\n\n")
        print("=" * 60)
        print("【非工作群 - 趣事吃瓜素材】")
        print("=" * 60)

        # 获取活跃的非工作聊天
        all_chats = self.conn.execute(f"""
            SELECT chat_name, COUNT(*) as cnt
            FROM wechat_message
            WHERE message_ts >= {self.ts_start} AND message_ts <= {self.ts_end}
              AND chat_type = 2
            GROUP BY chat_name
            HAVING cnt >= 50
            ORDER BY cnt DESC
        """).fetchall()

        for chat_name, cnt in all_chats:
            if self.is_work_chat(chat_name):
                continue
            if not self.is_fun_chat(chat_name):
                continue

            print(f"\n\n### {chat_name} ({cnt}条)")
            print("-" * 50)

            msgs = self.conn.execute(f"""
                SELECT sender_name, text, message_ts
                FROM wechat_message
                WHERE message_ts >= {self.ts_start} AND message_ts <= {self.ts_end}
                  AND chat_name LIKE ?
                  AND msg_type = 1
                  AND text IS NOT NULL AND LENGTH(text) > 10
                ORDER BY message_ts
            """, [f"{chat_name}%"]).fetchall()

            for sender, text, ts in msgs[:80]:
                time_str = datetime.fromtimestamp(ts / 1000).strftime('%H:%M')
                text_short = text[:120].replace('\n', ' ')
                print(f"{time_str} {sender}: {text_short}")

    def extract_all(self):
        """提取所有数据"""
        self.connect()
        try:
            self.extract_statistics()
            self.extract_work_chats()
            self.extract_fun_chats()
        finally:
            self.close()


def main():
    parser = argparse.ArgumentParser(description='提取微信聊天数据供 AI 分析')
    parser.add_argument('--date', '-d', type=str, help='指定日期 (YYYY-MM-DD)，默认今天')
    parser.add_argument('--db', type=str, default='/Users/cookie/Documents/wechat/wechat.duckdb',
                        help='DuckDB 数据库路径')
    args = parser.parse_args()

    # 解析日期
    if args.date:
        try:
            target_date = datetime.strptime(args.date, '%Y-%m-%d').date()
        except ValueError:
            print(f"日期格式错误: {args.date}，应为 YYYY-MM-DD", file=sys.stderr)
            sys.exit(1)
    else:
        target_date = date.today()

    extractor = WeChatDataExtractor(args.db, target_date)
    extractor.extract_all()


if __name__ == '__main__':
    main()
