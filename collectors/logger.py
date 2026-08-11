import logging
import os

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

_FMT = "%(asctime)s %(levelname)s %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def _make_logger(name: str, log_file: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(_FMT, datefmt=_DATEFMT)

    fh = logging.FileHandler(os.path.join(LOG_DIR, log_file), encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


error_logger = _make_logger("tro.error", "error.log")

# error_logger is shared; file handlers for it are added below so errors
# also land in error.log regardless of which module raises them.
_error_fh = logging.FileHandler(
    os.path.join(LOG_DIR, "error.log"), encoding="utf-8"
)
_error_fh.setLevel(logging.ERROR)
_error_fh.setFormatter(logging.Formatter(_FMT, datefmt=_DATEFMT))


def _make_logger_with_error(name: str, log_file: str) -> logging.Logger:
    logger = _make_logger(name, log_file)
    # Also route ERROR+ to the shared error.log
    logger.addHandler(_error_fh)
    return logger


collector_logger = _make_logger_with_error("tro.collector", "collector.log")
cleaner_logger = _make_logger_with_error("tro.cleaner", "cleaner.log")
