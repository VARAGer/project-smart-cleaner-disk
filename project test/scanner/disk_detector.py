import psutil
def get_avaible_disks() -> list[dict]:
    disks = []
    for partition in psutil.disk_partitions(all = False): #проверяет только реальные диски
        if "cdrom" in partition.opts or partition.fstype == "": #ббудет пропускать не нужные диски по типу флэхи или двд диски
            continue
        try:
            usage = psutil.disk_usage(partition.mountpoint)#считывает данные на дискаче
        except PermissionError:
            continue
        disks.append({
            "device": partition.device,
            "mountpoint": partition.mountpoint,
            "fstype": partition.fstype,
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "percent_used": usage.percent,
        })
    return disks