import os
from pathlib import Path


def data_dir():
    root = Path(os.environ.get("PULSE_HOME", Path.home() / ".pulse"))
    root.mkdir(parents=True, exist_ok=True)
    return root
