from beets import util


class FileOperationError(Exception):
    """Indicate an error when interacting with a file on disk.

    Possibilities include an unsupported media type, a permissions
    error, and an unhandled Mutagen exception.
    """

    def __init__(self, path, reason):
        """Create an exception describing an operation on the file at
        `path` with the underlying (chained) exception `reason`.
        """
        super().__init__(path, reason)
        self.path = path
        self.reason = reason

    def __str__(self):
        """Get a string representing the error.

        Describe both the underlying reason and the file path in question.
        """
        return f"{util.displayable_path(self.path)}: {self.reason}"


class ReadError(FileOperationError):
    """An error while reading a file (i.e. in `Item.read`)."""

    def __str__(self):
        return "error reading " + str(super())


class WriteError(FileOperationError):
    """An error while writing a file (i.e. in `Item.write`)."""

    def __str__(self):
        return "error writing " + str(super())
