import logging
import os

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "llm.log")
APP_LOG_FILE = os.path.join(LOG_DIR, "app.log")

logger = logging.getLogger("expense_bot")
logger.setLevel(logging.INFO)
logger.propagate = False

file_handler = logging.FileHandler(LOG_FILE)
file_handler.setLevel(logging.INFO)

app_file_handler = logging.FileHandler(APP_LOG_FILE)
app_file_handler.setLevel(logging.INFO)

formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s"
)

file_handler.setFormatter(formatter)
app_file_handler.setFormatter(formatter)

if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(app_file_handler)
