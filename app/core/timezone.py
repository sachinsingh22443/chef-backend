from datetime import date, datetime
from zoneinfo import ZoneInfo


INDIA_TIMEZONE = ZoneInfo("Asia/Kolkata")


def now_india() -> datetime:
    """
    Current date/time in India.
    """
    return datetime.now(INDIA_TIMEZONE)


def today_india() -> date:
    """
    Current calendar date in India.
    """
    return now_india().date()