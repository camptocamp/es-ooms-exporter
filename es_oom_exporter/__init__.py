import logging
import os


logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)-15s %(levelname)5s %(name)s %(message)s"
)
