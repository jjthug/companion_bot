# worker.py
from uvicorn.workers import UvicornWorker

class CompanionUvicornWorker(UvicornWorker):
    CONFIG_KWARGS = {
        "ws_max_size": 6 * 1024 * 1024,   # 6 MB frame cap
        "log_config": None,               # don't let uvicorn override structlog
    }