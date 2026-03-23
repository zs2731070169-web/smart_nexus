from datetime import datetime, timezone, timedelta


def get_expire_datetime(expires_at: datetime) -> int:
    """
    获取过期时间
    :return:
    """
    return int((expires_at - datetime.now(timezone.utc)).total_seconds())


def datetime_format(time_at: datetime) -> str:
    """
    获取格式化时间
    :param time_at:
    :return:
    """
    return time_at.strftime(format="%Y-%m-%d %H:%M:%S")


def delay_time(days: int=0, hours: int=0, minutes: int=0, seconds: int=0) -> datetime:
    """
    获取东八区时间
    :param days:
    :param hours:
    :param minutes:
    :param seconds:
    :return:
    """
    zone = timezone(timedelta(hours=8))
    total_time = datetime.now(zone) + timedelta(days=days, seconds=seconds, minutes=minutes, hours=hours)
    return total_time
