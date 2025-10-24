from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from typing_extensions import NotRequired, Unpack

if TYPE_CHECKING:
    from logging import Logger


class HumanReadableErrorArgs(TypedDict):
    reason: BaseException | bytes | str
    verb: str
    tb: NotRequired[str | None]


class HumanReadableError(Exception):
    """An Exception that can include a human-readable error message to
    be logged without a traceback. Can preserve a traceback for
    debugging purposes as well.

    Has at least two fields: `reason`, the underlying exception or a
    string describing the problem; and `verb`, the action being
    performed during the error.

    If `tb` is provided, it is a string containing a traceback for the
    associated exception. (Note that this is not necessary in Python 3.x
    and should be removed when we make the transition.)
    """

    error_kind: str = "Error"  # Human-readable description of error type.

    def __init__(self, **kwargs: Unpack[HumanReadableErrorArgs]) -> None:
        self.reason: BaseException | bytes | str = kwargs["reason"]
        self.verb: str = kwargs["verb"]
        self.tb: str | None = kwargs.get("tb")
        super().__init__(self.get_message())

    def _gerund(self) -> str:
        """Generate a (likely) gerund form of the English verb."""
        if " " in self.verb:
            return self.verb
        gerund: str = self.verb[:-1] if self.verb.endswith("e") else self.verb
        gerund += "ing"
        return gerund

    def _reasonstr(self) -> str:
        """Get the reason as a string."""
        if isinstance(self.reason, str):
            return self.reason
        elif isinstance(self.reason, bytes):
            return self.reason.decode("utf-8", "ignore")
        elif hasattr(self.reason, "strerror"):  # i.e., EnvironmentError
            return self.reason.strerror
        else:
            return f'"{self.reason}"'

    def get_message(self) -> str:
        """Create the human-readable description of the error, sans
        introduction.
        """
        raise NotImplementedError

    def log(self, logger: Logger) -> None:
        """Log to the provided `logger` a human-readable message as an
        error and a verbose traceback as a debug message.
        """
        if self.tb:
            logger.debug(self.tb)
        logger.error("{0.error_kind}: {0.args[0]}", self)
