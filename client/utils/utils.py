def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} Б"

    units = ["КБ", "МБ", "ГБ", "ТБ"]
    size = float(size_bytes)
    for unit in units:
        size /= 1024
        if size < 1024 or unit == units[-1]:
            precision = 2 if unit == "ТБ" and size >= 1 else 1
            return f"{size:.{precision}f} {unit}"

    return f"{size:.1f} ПБ"


def format_duration(seconds: int) -> str:
    minutes, remainder = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{remainder:02d}"
    return f"{minutes:02d}:{remainder:02d}"