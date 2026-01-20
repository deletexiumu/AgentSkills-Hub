#!/usr/bin/env python3
"""
微信聊天今日报告生成器

从 DuckDB 读取微信聊天记录，生成结构化 Markdown 报告。
"""

import argparse
import duckdb
from datetime import datetime, date, timedelta
from pathlib import Path
import sys


class WeChatReportGenerator:
    """微信日报生成器"""

    # 工作相关群聊关键词
    WORK_CHAT_KEYWORDS = [
        '运维', '开发', '技术', '对接', '沟通', '项目', '实施',
        '测试', '产业', '平台', '系统', '数据', '中台'
    ]

    # 工作相关私聊关键词（公司/部门前缀）
    WORK_CONTACT_KEYWORDS = [
        '神码', '神州', '东方', '国信', '合合', '拓尔思', '上奇',
        '来未来', '永洪', '大数据部', '国创'
    ]

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

    def get_overview(self) -> dict:
        """获取数据概览"""
        total = self.conn.execute(f"""
            SELECT COUNT(*) FROM wechat_message
            WHERE message_ts >= {self.ts_start} AND message_ts <= {self.ts_end}
        """).fetchone()[0]

        chat_count = self.conn.execute(f"""
            SELECT COUNT(DISTINCT chat_id) FROM wechat_message
            WHERE message_ts >= {self.ts_start} AND message_ts <= {self.ts_end}
        """).fetchone()[0]

        sender_count = self.conn.execute(f"""
            SELECT COUNT(DISTINCT sender_id) FROM wechat_message
            WHERE message_ts >= {self.ts_start} AND message_ts <= {self.ts_end}
              AND sender_id IS NOT NULL
        """).fetchone()[0]

        # 峰值时段
        peak = self.conn.execute(f"""
            SELECT EXTRACT(HOUR FROM to_timestamp(message_ts/1000)) as hour, COUNT(*) as cnt
            FROM wechat_message
            WHERE message_ts >= {self.ts_start} AND message_ts <= {self.ts_end}
            GROUP BY hour
            ORDER BY cnt DESC
            LIMIT 1
        """).fetchone()

        return {
            'total': total,
            'chat_count': chat_count,
            'sender_count': sender_count,
            'peak_hour': int(peak[0]) if peak else 0,
            'peak_count': peak[1] if peak else 0
        }

    def get_chat_ranking(self, limit: int = 15) -> list:
        """获取聊天活跃度排行"""
        return self.conn.execute(f"""
            SELECT chat_name, chat_type, COUNT(*) as cnt
            FROM wechat_message
            WHERE message_ts >= {self.ts_start} AND message_ts <= {self.ts_end}
            GROUP BY chat_id, chat_name, chat_type
            ORDER BY cnt DESC
            LIMIT {limit}
        """).fetchall()

    def get_message_types(self) -> list:
        """获取消息类型分布（过滤乱码）"""
        results = self.conn.execute(f"""
            SELECT msg_type_name, COUNT(*) as cnt
            FROM wechat_message
            WHERE message_ts >= {self.ts_start} AND message_ts <= {self.ts_end}
            GROUP BY msg_type_name
            ORDER BY cnt DESC
        """).fetchall()
        # 过滤掉乱码（非中文/英文的类型名）
        import re
        clean_results = []
        seen_types = set()
        for name, cnt in results:
            if name and re.match(r'^[\u4e00-\u9fa5a-zA-Z]+$', name) and name not in seen_types:
                clean_results.append((name, cnt))
                seen_types.add(name)
        return clean_results

    def get_top_senders(self, limit: int = 10) -> list:
        """获取活跃发送者"""
        return self.conn.execute(f"""
            SELECT sender_name, COUNT(*) as cnt
            FROM wechat_message
            WHERE message_ts >= {self.ts_start} AND message_ts <= {self.ts_end}
              AND sender_name IS NOT NULL AND sender_name != ''
            GROUP BY sender_id, sender_name
            ORDER BY cnt DESC
            LIMIT {limit}
        """).fetchall()

    def get_hourly_distribution(self) -> list:
        """获取按小时分布"""
        return self.conn.execute(f"""
            SELECT EXTRACT(HOUR FROM to_timestamp(message_ts/1000)) as hour, COUNT(*) as cnt
            FROM wechat_message
            WHERE message_ts >= {self.ts_start} AND message_ts <= {self.ts_end}
            GROUP BY hour
            ORDER BY hour
        """).fetchall()

    def is_work_chat(self, chat_name: str, chat_type: int) -> bool:
        """判断是否工作相关聊天"""
        if not chat_name:
            return False
        for kw in self.WORK_CHAT_KEYWORDS:
            if kw in chat_name:
                return True
        if chat_type == 1:  # 私聊
            for kw in self.WORK_CONTACT_KEYWORDS:
                if chat_name.startswith(kw) or kw in chat_name:
                    return True
        return False

    def get_todo_messages(self, my_name: str = "淇奥") -> list:
        """提取需要跟进的待办事项（智能分析）"""
        # 获取所有工作相关聊天的文本消息
        all_work_msgs = self.conn.execute(f"""
            SELECT chat_name, chat_type, sender_name, text, message_ts
            FROM wechat_message
            WHERE message_ts >= {self.ts_start} AND message_ts <= {self.ts_end}
              AND msg_type = 1
              AND text IS NOT NULL AND LENGTH(text) > 5
              AND sender_name != ?
            ORDER BY message_ts
        """, [my_name]).fetchall()

        results = []
        for chat_name, chat_type, sender, text, ts in all_work_msgs:
            if not self.is_work_chat(chat_name, chat_type):
                continue

            score = 0
            reason = []

            # 1. 直接@我的消息 (高优先级)
            if f'@{my_name}' in text:
                score += 10
                reason.append("@我")

            # 2. 问题/故障相关
            if any(kw in text for kw in ['问题', '故障', '报错', '异常', '失败', 'bug', '挂了', '不行', '错误']):
                score += 5
                reason.append("问题")

            # 3. 请求帮助
            if any(kw in text for kw in ['帮忙', '麻烦', '协助', '支持一下']):
                score += 4
                reason.append("请求")

            # 4. 任务/进度相关
            if any(kw in text for kw in ['什么时候', '进度', '完成', '截止', 'deadline', '今天', '明天', '周五', '尽快', '抓紧', '急']):
                score += 3
                reason.append("进度")

            # 5. 确认/反馈相关
            if any(kw in text for kw in ['确认', '反馈', '回复', '看一下', '看下', '检查']):
                score += 2
                reason.append("确认")

            # 6. 会议/沟通
            if any(kw in text for kw in ['会议', '开会', '沟通', '讨论', '对接']):
                score += 2
                reason.append("会议")

            if score >= 5:  # 只保留分数>=5的
                results.append((chat_name, sender, text, ts, score, '|'.join(reason)))

        # 按分数降序，时间升序
        results.sort(key=lambda x: (-x[4], x[3]))
        return results[:25]  # 最多25条

    def get_fun_messages(self) -> list:
        """提取趣事/吃瓜内容（非工作群的有趣消息）"""
        # 非工作群的消息
        all_msgs = self.conn.execute(f"""
            SELECT chat_name, chat_type, sender_name, text, message_ts
            FROM wechat_message
            WHERE message_ts >= {self.ts_start} AND message_ts <= {self.ts_end}
              AND msg_type = 1
              AND text IS NOT NULL AND LENGTH(text) > 10
              AND chat_type = 2
            ORDER BY message_ts
        """).fetchall()

        results = []
        for chat_name, chat_type, sender, text, ts in all_msgs:
            # 排除工作群
            if self.is_work_chat(chat_name, chat_type):
                continue

            score = 0
            tags = []

            # 1. 吃瓜/八卦关键词
            if any(kw in text for kw in ['吃瓜', '八卦', '瓜', '劲爆', '爆料', '听说', '据说', '传闻']):
                score += 5
                tags.append("吃瓜")

            # 2. 搞笑/有趣
            if any(kw in text for kw in ['哈哈', '笑死', '绝了', '离谱', '逆天', '笑不活', '乐死', '太搞了', '整活']):
                score += 4
                tags.append("搞笑")

            # 3. 新闻/热点
            if any(kw in text for kw in ['热搜', '新闻', '刚刚', '突发', '重磅', '官宣']):
                score += 3
                tags.append("热点")

            # 4. 分享/推荐
            if any(kw in text for kw in ['推荐', '安利', '好用', '神器', '宝藏', '分享']):
                score += 2
                tags.append("分享")

            # 5. 情绪强烈
            if any(kw in text for kw in ['！！', '??', '卧槽', '我靠', '天哪', '啊啊啊', '救命']):
                score += 2
                tags.append("情绪")

            # 6. 游戏相关趣事
            if any(kw in text for kw in ['欧皇', '非酋', '出货', '毕业', '上分', '翻车', '金色传说']):
                score += 2
                tags.append("游戏")

            if score >= 3:
                results.append((chat_name, sender, text, ts, score, tags))

        # 按分数降序
        results.sort(key=lambda x: -x[4])
        return results[:20]  # 最多20条

    def generate_report(self) -> str:
        """生成报告内容"""
        lines = []

        # 标题
        date_str = self.target_date.strftime('%Y-%m-%d')
        weekday = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][self.target_date.weekday()]
        lines.append(f"# 微信日报 ({date_str} {weekday})")
        lines.append("")

        # 数据概览
        overview = self.get_overview()
        if overview['total'] == 0:
            lines.append("> 当日无消息数据")
            return "\n".join(lines)

        lines.append("## 一、数据概览")
        lines.append("")
        lines.append("| 指标 | 数值 |")
        lines.append("|------|------|")
        lines.append(f"| **消息总数** | {overview['total']:,} 条 |")
        lines.append(f"| **活跃聊天** | {overview['chat_count']} 个 |")
        lines.append(f"| **活跃人数** | {overview['sender_count']} 人 |")
        lines.append(f"| **峰值时段** | {overview['peak_hour']:02d}:00 ({overview['peak_count']}条) |")
        lines.append("")

        # 聊天活跃度
        lines.append("---")
        lines.append("")
        lines.append("## 二、聊天活跃度 TOP 15")
        lines.append("")
        lines.append("| 排名 | 聊天 | 类型 | 消息数 |")
        lines.append("|------|------|------|--------|")
        for idx, (name, ctype, cnt) in enumerate(self.get_chat_ranking(), 1):
            type_name = "群聊" if ctype == 2 else "私聊"
            display_name = (name[:20] + "...") if name and len(name) > 20 else name
            lines.append(f"| {idx} | {display_name} | {type_name} | {cnt} |")
        lines.append("")

        # 消息类型分布
        lines.append("---")
        lines.append("")
        lines.append("## 三、消息类型分布")
        lines.append("")
        for mtype, cnt in self.get_message_types():
            lines.append(f"- **{mtype}**: {cnt:,} 条")
        lines.append("")

        # 待办事项摘要
        lines.append("---")
        lines.append("")
        lines.append("## 四、待办事项")
        lines.append("")

        chat_ranking = self.get_chat_ranking(50)
        work_chats = [(name, ctype, cnt) for name, ctype, cnt in chat_ranking
                      if self.is_work_chat(name, ctype) and ctype == 2]
        work_privates = [(name, ctype, cnt) for name, ctype, cnt in chat_ranking
                         if self.is_work_chat(name, ctype) and ctype == 1]

        todo_msgs = self.get_todo_messages()
        if todo_msgs:
            lines.append(f"以下 **{len(todo_msgs)}** 条消息可能需要你跟进：")
            lines.append("")
            for chat_name, sender, text, ts, score, reason in todo_msgs:
                time_str = datetime.fromtimestamp(ts / 1000).strftime('%H:%M')
                text_short = text[:65].replace('\n', ' ')
                if len(text) > 65:
                    text_short += "..."
                chat_short = (chat_name[:10] + "..") if chat_name and len(chat_name) > 10 else chat_name
                lines.append(f"- `{time_str}` [{reason}] **{chat_short}** | {sender}: {text_short}")
            lines.append("")
        else:
            lines.append("> 今日无待办事项，摸鱼愉快！")
            lines.append("")

        # 趣事吃瓜
        lines.append("---")
        lines.append("")
        lines.append("## 五、趣事吃瓜")
        lines.append("")

        fun_msgs = self.get_fun_messages()
        if fun_msgs:
            lines.append(f"今日 **{len(fun_msgs)}** 条有趣内容：")
            lines.append("")
            for chat_name, sender, text, ts, score, tags in fun_msgs:
                time_str = datetime.fromtimestamp(ts / 1000).strftime('%H:%M')
                text_short = text[:70].replace('\n', ' ')
                if len(text) > 70:
                    text_short += "..."
                chat_short = (chat_name[:10] + "..") if chat_name and len(chat_name) > 10 else chat_name
                tag_str = ' '.join([f"#{t}" for t in tags])
                lines.append(f"- `{time_str}` **{chat_short}** | {sender}: {text_short} {tag_str}")
            lines.append("")
        else:
            lines.append("> 今日风平浪静，无瓜可吃。")
            lines.append("")

        # 活跃发送者
        lines.append("---")
        lines.append("")
        lines.append("## 六、活跃发送者 TOP 10")
        lines.append("")
        lines.append("| 排名 | 发送者 | 消息数 |")
        lines.append("|------|--------|--------|")
        for idx, (sender, cnt) in enumerate(self.get_top_senders(), 1):
            lines.append(f"| {idx} | {sender} | {cnt} |")
        lines.append("")

        # 时间分布
        lines.append("---")
        lines.append("")
        lines.append("## 七、消息时间分布")
        lines.append("")
        lines.append("```")
        hourly = {int(h): c for h, c in self.get_hourly_distribution()}
        max_cnt = max(hourly.values()) if hourly else 1
        for hour in range(24):
            cnt = hourly.get(hour, 0)
            bar_len = int(cnt / max_cnt * 30) if max_cnt > 0 else 0
            bar = "█" * bar_len
            lines.append(f"{hour:02d}:00 | {bar:<30} {cnt:>4}")
        lines.append("```")
        lines.append("")

        # 一句话总结
        lines.append("---")
        lines.append("")
        lines.append("## 今日总结")
        lines.append("")
        summary = self.generate_summary(overview, chat_ranking, work_chats, work_privates)
        lines.append(f"> {summary}")
        lines.append("")

        # 页脚
        lines.append("---")
        lines.append("")
        lines.append(f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

        return "\n".join(lines)

    def generate_summary(self, overview: dict, chat_ranking: list, work_chats: list, work_privates: list) -> str:
        """生成一句话幽默总结"""
        import random

        total = overview['total']
        peak_hour = overview['peak_hour']

        # 最活跃的聊天
        top_chat = chat_ranking[0][0] if chat_ranking else "无"
        top_chat_cnt = chat_ranking[0][2] if chat_ranking else 0

        # 工作相关数量
        work_chat_cnt = len(work_chats)
        work_private_cnt = len(work_privates)
        work_total = work_chat_cnt + work_private_cnt

        # 根据不同情况生成幽默总结
        summaries = []

        # 消息量相关
        if total > 5000:
            summaries.extend([
                f"今天 {total:,} 条消息，手指已阵亡，建议明天带备用拇指上班。",
                f"{total:,} 条消息的重量，压得微信都喘不过气来。",
                f"日收消息 {total:,} 条，这不是聊天，这是渡劫。",
            ])
        elif total > 3000:
            summaries.extend([
                f"{total:,} 条消息，今天的微信比地铁还挤。",
                f"收获 {total:,} 条消息，看完已是明日。",
                f"{total:,} 条消息轰炸完毕，耳朵虽然没听见，但眼睛已经聋了。",
            ])
        elif total > 1500:
            summaries.extend([
                f"{total:,} 条消息，不多不少，刚好够塞满通勤时间。",
                f"今日 {total:,} 条，中规中矩的一天，明天继续卷。",
            ])
        elif total > 500:
            summaries.extend([
                f"只有 {total:,} 条消息，难得清净，是不是有人把我屏蔽了？",
                f"{total:,} 条消息，岁月静好，适合摸鱼。",
            ])
        else:
            summaries.extend([
                f"全天才 {total:,} 条消息，要么今天是周末，要么我被全世界遗忘了。",
                f"{total:,} 条消息，安静得可怕，是暴风雨前的宁静吗？",
            ])

        # 最活跃群相关
        if top_chat_cnt > 500:
            summaries.extend([
                f"「{top_chat}」以 {top_chat_cnt} 条消息荣获今日话痨冠军，奖品是更多的未读消息。",
                f"「{top_chat}」狂飙 {top_chat_cnt} 条，群友们是把年假攒的话今天说完了吗？",
            ])
        elif top_chat_cnt > 200:
            summaries.append(f"「{top_chat}」贡献了 {top_chat_cnt} 条，是今天的气氛担当。")

        # 工作相关
        if work_total > 15:
            summaries.extend([
                f"对接了 {work_total} 个工作会话，打工人の极限就是没有极限。",
                f"{work_total} 个工作群在线battle，这班上得比综艺还热闹。",
            ])
        elif work_total > 8:
            summaries.append(f"{work_total} 个工作会话同时在线，多线程打工，CPU快冒烟了。")
        elif work_total == 0:
            summaries.append("今天居然零工作消息，不是休假就是被优化了，细思极恐。")

        # 高峰时段相关
        if peak_hour >= 22:
            summaries.append(f"消息高峰居然在 {peak_hour} 点，夜猫子们真的不用睡觉吗？")
        elif peak_hour <= 6:
            summaries.append(f"凌晨 {peak_hour} 点是高峰？这届网友卷得太离谱了。")
        elif 12 <= peak_hour <= 14:
            summaries.append(f"高峰在午饭时间，果然吃饭不聊天，聊天不吃饭是不可能的。")

        return random.choice(summaries)


def main():
    parser = argparse.ArgumentParser(description='生成微信聊天今日报告')
    parser.add_argument('--date', '-d', type=str, help='指定日期 (YYYY-MM-DD)，默认今天')
    parser.add_argument('--output', '-o', type=str, default='.', help='输出目录，默认当前目录')
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

    # 输出路径
    output_dir = Path(args.output)
    if not output_dir.exists():
        output_dir.mkdir(parents=True)

    output_file = output_dir / f"wechat-report-{target_date.strftime('%Y-%m-%d')}.md"

    print(f"生成微信日报: {target_date}")
    print(f"数据库: {args.db}")
    print(f"输出文件: {output_file}")
    print()

    # 生成报告
    generator = WeChatReportGenerator(args.db, target_date)
    generator.connect()

    try:
        report = generator.generate_report()

        # 写入文件
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"报告已生成: {output_file}")
        print()
        print("=" * 50)
        print("报告摘要:")
        print("=" * 50)
        # 打印前30行作为摘要
        for line in report.split('\n')[:30]:
            print(line)
        print("...")
        print(f"\n完整报告请查看: {output_file}")

    finally:
        generator.close()


if __name__ == '__main__':
    main()
