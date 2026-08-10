import mediafile

from .util.deprecation import deprecate_for_maintainers

deprecate_for_maintainers("'beets.mediafile'", "'mediafile'", stacklevel=2)

# Import everything from the mediafile module into this module.
for key, value in mediafile.__dict__.items():
    if key not in ["__name__"]:
        globals()[key] = value

# Cleanup namespace.
del key, value, mediafile
