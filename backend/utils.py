"""通用小工具：时间格式化、金额换算（分 <-> 元）、拼音生成。"""
from datetime import datetime

from pypinyin import lazy_pinyin, Style


def now_iso() -> str:
    """本地时间 ISO8601 字符串，精确到秒。"""
    return datetime.now().isoformat(timespec="seconds")


def today_str() -> str:
    """本地日期字符串 'YYYY-MM-DD'（打卡记录按此归属）。"""
    return datetime.now().strftime("%Y-%m-%d")


def to_yuan(cents: int) -> float:
    """分 -> 元（接口返回时统一换算，浮点误差不出数据库）。"""
    return round(cents / 100, 2)


def to_cents(yuan) -> int:
    """元 -> 分，兼容数字与字符串输入，如 '0.5' -> 50。"""
    return round(float(yuan) * 100)


def make_pinyin(text: str) -> str:
    """生成带声调拼音：'扫地' -> 'sǎo dì'（家长新增任务时自动填充）。"""
    return " ".join(lazy_pinyin(text, style=Style.TONE))
