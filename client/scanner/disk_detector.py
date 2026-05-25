import psutil


def get_available_disks() -> list[dict]:
    disks = []
    for partition in psutil.disk_partitions(all=False):
        if "cdrom" in partition.opts or partition.fstype == "":
            continue
        try:
            usage = psutil.disk_usage(partition.mountpoint)
        except (PermissionError, OSError):
            continue
        disks.append(
            {
                "device": partition.device,
                "mountpoint": partition.mountpoint,
                "fstype": partition.fstype,
                "total_bytes": usage.total,
                "used_bytes": usage.used,
                "free_bytes": usage.free,
                "percent_used": usage.percent,
            }
        )
    return disks
