class Doc2PagesError(Exception):
    """Base class of all errors in this package."""


class ConfigError(Doc2PagesError):
    """A setting is missing or a value is invalid."""


class LimitError(Doc2PagesError):
    """A limit was exceeded."""


class UnsupportedFileError(Doc2PagesError):
    """The file type is not supported or the file cannot be read."""


class NoReadableText(UnsupportedFileError):
    """The file carries no text at all, a scan without a text layer for instance."""


class ModelError(Doc2PagesError):
    """The model server did not answer, or the answer was unusable."""
