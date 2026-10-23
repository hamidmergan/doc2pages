"""The package logger, with brace formatting so a message reads like its arguments."""

import logging

_logger = logging.getLogger("doc2pages")


class _BraceLogger:
    """Formats ``"text {}"`` with its arguments the way str.format does."""

    def _log(self, level: int, message: str, *args) -> None:
        if _logger.isEnabledFor(level):
            _logger.log(level, message.format(*args) if args else message)

    def debug(self, message: str, *args) -> None:
        self._log(logging.DEBUG, message, *args)

    def info(self, message: str, *args) -> None:
        self._log(logging.INFO, message, *args)

    def warning(self, message: str, *args) -> None:
        self._log(logging.WARNING, message, *args)

    def error(self, message: str, *args) -> None:
        self._log(logging.ERROR, message, *args)


logger = _BraceLogger()
