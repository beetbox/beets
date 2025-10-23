Handling Paths
==============

A great deal of convention deals with the handling of **paths**. Paths are
stored internally—in the database, for instance—as byte strings (i.e., ``bytes``
instead of ``str`` in Python 3). This is because POSIX operating systems’ path
names are only reliably usable as byte strings—operating systems typically
recommend but do not require that filenames use a given encoding, so violations
of any reported encoding are inevitable. On Windows, the strings are always
encoded with UTF-8; on Unix, the encoding is controlled by the filesystem. Here
are some guidelines to follow:

- If you have a Unicode path or you’re not sure whether something is Unicode or
  not, pass it through ``bytestring_path`` function in the ``beets.util`` module
  to convert it to bytes.
- Pass every path name through the ``syspath`` function (also in ``beets.util``)
  before sending it to any *operating system* file operation (``open``, for
  example). This is necessary to use long filenames (which, maddeningly, must be
  Unicode) on Windows. This allows us to consistently store bytes in the
  database but use the native encoding rule on both POSIX and Windows.
- Similarly, the ``displayable_path`` utility function converts bytestring paths
  to a Unicode string for displaying to the user. Every time you want to print
  out a string to the terminal or log it with the ``logging`` module, feed it
  through this function.
