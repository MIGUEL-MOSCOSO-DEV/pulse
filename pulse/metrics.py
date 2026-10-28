import time
from pathlib import Path

import psutil

from .database import connection


def sample():
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(Path.home().anchor)
    processes = []
    for process in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            info = process.info
            if info["memory_info"]:
                processes.append((info["pid"], info["name"] or "Proceso", info["memory_info"].rss))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return {
        "time": time.time(),
        "cpu": psutil.cpu_percent(interval=0.1),
        "ram": memory.percent,
        "disk": disk.percent,
        "used": memory.used,
        "total": memory.total,
        "processes": sorted(processes, key=lambda row: row[2], reverse=True)[:12],
    }


class History:
    def __init__(self, path):
        self.path = path
        with connection(path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS samples(time REAL PRIMARY KEY,cpu REAL,ram REAL,disk REAL)"
            )

    def add(self, item):
        with connection(self.path) as db:
            db.execute(
                "INSERT OR REPLACE INTO samples VALUES(?,?,?,?)",
                (item["time"], item["cpu"], item["ram"], item["disk"]),
            )
            db.execute(
                "DELETE FROM samples WHERE time NOT IN (SELECT time FROM samples ORDER BY time DESC LIMIT 50000)"
            )

    def rows(self, limit=120):
        with connection(self.path) as db:
            return list(
                reversed(
                    db.execute(
                        "SELECT * FROM samples ORDER BY time DESC LIMIT ?", (limit,)
                    ).fetchall()
                )
            )


class Alerts:
    def __init__(self, cooldown=120):
        self.last = {}
        self.cooldown = cooldown

    def evaluate(self, item, thresholds, now=None):
        now = time.monotonic() if now is None else now
        messages = []
        for metric, threshold in thresholds.items():
            if not 1 <= threshold <= 100:
                raise ValueError("El umbral debe estar entre 1 y 100.")
            if (
                item[metric] >= threshold
                and now - self.last.get(metric, -float("inf")) >= self.cooldown
            ):
                messages.append(f"{metric.upper()} en {item[metric]:.1f}% (umbral {threshold}%)")
                self.last[metric] = now
        return messages
