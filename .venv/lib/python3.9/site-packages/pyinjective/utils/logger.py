import logging
from logging import Logger
from typing import Type

# If the application using the SDK has its own logging configuration, the following basic configuration will have no
# effect
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


class LoggerProvider:
    def logger(self) -> Logger:
        return logging.getLogger(__name__)

    def logger_for_class(self, logging_class: Type) -> Logger:
        return logging.getLogger(f"{logging_class.__module__}.{logging_class.__name__}")
