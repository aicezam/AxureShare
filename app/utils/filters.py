"""Jinja2 模板过滤器。"""

from datetime import datetime, timedelta

def datetime_cn(value: datetime | None, format: str = "%Y-%m-%d %H:%M") -> str:
    """将 UTC 时间转换为北京时间并格式化。
    
    Args:
        value: UTC 时间对象
        format: 格式化字符串
        
    Returns:
        格式化后的北京时间字符串
    """
    if value is None:
        return ""
    
    # 转换为北京时间 (UTC+8)
    beijing_time = value + timedelta(hours=8)
    return beijing_time.strftime(format)
