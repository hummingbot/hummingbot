import logging
import os

from hummingbot.logger import HummingbotLogger


class FlushingFileHandler(logging.FileHandler):
    def emit(self, record):
        super().emit(record)  # First, do the original emit work.
        self.flush()  # Then, force an immediate flush.


class IndentingLogger:
    _indent_str: str = ""

    def __init__(self, logger: HummingbotLogger | logging.Logger, class_name: str):
        self._logger: HummingbotLogger = logger
        self._class_name: str = class_name
        self._filehandler: FlushingFileHandler | None = None
        self._class_log_path: str | None = None

        if handler := self._update_first_file_handler():
            handler.setFormatter(logging.Formatter(f'{self._class_name:>50}: %(message)s'))

            logfile_dir: str = os.path.dirname(handler.baseFilename)
            classes_dir = os.path.join(logfile_dir, "classes")
            if not os.path.exists(classes_dir):
                os.mkdir(classes_dir)

            # Create a new file handler for the debug logger in a subdirectory
            # with the name of the class
            self._class_log_path = os.path.join(classes_dir, f"debug_{self._class_name}.log")
            self.refresh_handlers()

    def handle_error(self, record):
        import traceback
        print("Logging error:", traceback.format_exc())

    def refresh_handlers(self):
        if self._filehandler is None and self._class_log_path is not None:
            self._filehandler = FlushingFileHandler(self._class_log_path, encoding="utf-8", delay=False)
            self._filehandler.handleError = self.handle_error
            self._filehandler.setFormatter(logging.Formatter('%(asctime)s:[%(lineno)d] %(message)s'))
            self._filehandler.setLevel(logging.DEBUG)

        if self._filehandler and self._filehandler not in self._logger.handlers:
            self._logger.setLevel(logging.DEBUG)
            self._logger.addHandler(self._filehandler)
            self._logger.debug(f"Added new DEBUG file handler for {self._class_name}")

    def setLevel(self, level):
        self._logger.setLevel(level)
        if self._filehandler:
            self._filehandler.setLevel(level)

    def addHandler(self, handler):
        self._logger.addHandler(handler)
        if self._filehandler:
            self._filehandler.addHandler(handler)

    def debug(
            self,
            msg,
            indent_next: bool = False,
            unindent_next: bool = False,
            condition: bool = True,
            bullet: str = " "):

        if not condition:
            return

        self._logger.debug(self._indent_message(msg))

        if indent_next:
            self.add_indent(bullet=bullet)
        if unindent_next:
            self.remove_indent()

    def info(self, msg):
        self._logger.info(self._indent_message(msg))

    def warning(self, msg, *args, **kwargs):
        self._logger.warning(self._indent_message(msg), *args, **kwargs)

    def error(self, msg, exc_info=False):
        self._logger.error(self._indent_message(msg), exc_info=exc_info)

    def critical(self, msg, exc_info=False):
        self._logger.critical(self._indent_message(msg), exc_info=exc_info)

    def exception(self, msg, *args, **kwargs):
        self._logger.exception(self._indent_message(msg), *args, **kwargs)

    def log(self, level, msg, *args, **kwargs):
        self._logger.log(level, msg, *args, **kwargs)

    def network(self, log_msg: str, app_warning_msg: str | None = None, *args, **kwargs):
        self._logger.network(log_msg, app_warning_msg, *args, **kwargs)

    def _indent_message(self, msg):
        msg = msg.replace('\n', '\n' + self._indent_str)
        msg = f"{self._indent_str}{msg}"
        return msg

    @staticmethod
    def _update_first_file_handler() -> logging.FileHandler | None:
        for handler in logging.getLoggerClass().root.handlers:
            if isinstance(handler, logging.FileHandler):
                return handler

    def add_indent(self, *, bullet: str = " "):
        # Simply make sure we only add 1 character, regardless of the ingenuity of the caller
        self._indent_str += f"{bullet[0]}   "

    def remove_indent(self):
        self._indent_str = self._indent_str[:-4]

    def ctx_indentation(self, msg="", bullet=" "):
        return _LoggingContext(self, msg=msg, bullet=bullet)


class _LoggingContext:
    def __init__(self, indenting_logger, *, msg: str, bullet: str = " "):
        self._indenting_logger = indenting_logger
        self._msg = msg
        self._bullet = bullet

    def __enter__(self):
        self._indenting_logger.debug(msg=self._msg, bullet=self._bullet)
        self._indenting_logger.add_indent(bullet=self._bullet)
        return self._indenting_logger

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._indenting_logger.remove_indent()
        self._indenting_logger.debug(msg="Done")
