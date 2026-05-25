import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logger(name="swarm_coder"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        log_file = "swarm_coder.log"
        handler = RotatingFileHandler(log_file, backupCount=5, encoding="utf-8")

        if os.path.isfile(log_file) and os.path.getsize(log_file) > 0:
            handler.doRollover()

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


logger = setup_logger()
