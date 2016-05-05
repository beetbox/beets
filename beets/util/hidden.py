"""Simple library to work out if a file is hidden on different platforms."""

import ctypes
import ctypes.util
import os.path
import sys


# Adjustments for CoreFoundation functions on OS X.
_CF_FUNCTION_MAPPINGS = {
    'CFRelease': {
        'argtypes': [ctypes.c_void_p],
        'restype': None
    },
    'CFURLCreateFromFileSystemRepresentation': {
        'argtypes': [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_long,
            ctypes.c_int
        ],
        'restype': ctypes.c_void_p
    },
    'CFURLCopyResourcePropertyForKey': {
        'argtypes':  [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p
        ],
        'restype': ctypes.c_void_p
    },
    'CFBooleanGetValue': {
        'argtypes': [ctypes.c_void_p],
        'restype': ctypes.c_int
    }
}


def _dict_attr_copy(source, destination):
    """Copy dict values from source on to destination as attributes."""
    for k, v in source.iteritems():
        if isinstance(v, dict):
            _dict_attr_copy(v, getattr(destination, k))
        else:
            setattr(destination, k, v)


def _is_hidden_osx(path):
    """Return whether or not a file is hidden on OS X.

    This uses CoreFoundation alongside CFURL to work out if a file has the
    "hidden" flag.
    """
    # Load CoreFoundation.
    cf_path = ctypes.util.find_library('CoreFoundation')
    cf = ctypes.cdll.LoadLibrary(cf_path)

    # Copy the adjustments on to the library.
    _dict_attr_copy(_CF_FUNCTION_MAPPINGS, cf)

    # Create a URL from the path.
    url = cf.CFURLCreateFromFileSystemRepresentation(None, path, len(path),
                                                     False)

    # Retrieve the hidden key.
    is_hidden_key = ctypes.c_void_p.in_dll(cf, 'kCFURLIsHiddenKey')

    # Create a void pointer and get the address of it.
    val = ctypes.c_void_p(0)
    val_address = ctypes.addressof(val)

    # Get the value (whether or not the file is hidden) for the hidden key and
    # store it in val.
    success = cf.CFURLCopyResourcePropertyForKey(url, is_hidden_key,
                                                 val_address, None)

    # Check if we were able to get the value for the hidden key.
    if success:

        # Retrieve the result as a boolean.
        result = cf.CFBooleanGetValue(val)

        # Release the value and URL.
        cf.CFRelease(val)
        cf.CFRelease(url)

        return bool(result)
    else:
        return False


def _is_hidden_win(path):
    """Return whether or not a file is hidden on Windows.

    This uses GetFileAttributes to work out if a file has the "hidden" flag
    (FILE_ATTRIBUTE_HIDDEN).
    """
    # FILE_ATTRIBUTE_HIDDEN = 2 (0x2) from GetFileAttributes documentation.
    hidden_mask = 2

    # Retrieve the attributes for the file.
    attrs = ctypes.windll.kernel32.GetFileAttributesW(path)

    # Ensure we have valid attribues and compare them against the mask.
    return attrs >= 0 and bool(attrs & hidden_mask)


def _is_hidden_dot(path):
    """Return whether or not a file starts with a dot.

    Files starting with a dot are seen as "hidden" files on Unix-based OSes.
    """
    return os.path.basename(path).startswith('.')


def is_hidden(path):
    """Return whether or not a file is hidden.

    This method works differently depending on the platform it is called on.

    On OS X, it uses both the result of `is_hidden_osx` and `is_hidden_dot` to
    work out if a file is hidden.

    On Windows, it uses the result of `is_hidden_win` to work out if a file is
    hidden.

    On any other operating systems (i.e. Linux), it uses `is_hidden_dot` to
    work out if a file is hidden.
    """
    # Convert the path to unicode if it is not already.
    if not isinstance(path, unicode):
        path = path.decode('utf-8')

    # Run platform specific functions depending on the platform
    if sys.platform == 'darwin':
        return _is_hidden_osx(path) or _is_hidden_dot(path)
    elif sys.platform == 'win32':
        return _is_hidden_win(path)
    else:
        return _is_hidden_dot(path)

__all__ = ['is_hidden']
