"""Fixes file permissions after the file gets written on import. Put something
like the following in your config.yaml to configure:

    permissions:
            file: 644
            dir: 755
"""
import os
from beets import config, util
from beets.plugins import BeetsPlugin
from beets.util import ancestry


def convert_perm(perm):
    """Convert a string to an integer, interpreting the text as octal.
    Or, if `perm` is an integer, reinterpret it as an octal number that
    has been "misinterpreted" as decimal.
    """
    if isinstance(perm, int):
        perm = str(perm)
    return int(perm, 8)


def check_permissions(path, permission):
    """Check whether the file's permissions equal the given vector.
    Return a boolean.
    """
    return oct(os.stat(path).st_mode & 0o777) == oct(permission)


def assert_permissions(path, permission, log):
    """Check whether the file's permissions are as expected, otherwise,
    log a warning message. Return a boolean indicating the match, like
    `check_permissions`.
    """
    if not check_permissions(util.syspath(path), permission):
        log.warning(
            'could not set permissions on {}',
            util.displayable_path(path),
        )
        log.debug(
            'set permissions to {}, but permissions are now {}',
            permission,
            os.stat(util.syspath(path)).st_mode & 0o777,
        )


def dirs_in_library(library, item):
    """Creates a list of ancestor directories in the beets library path.
    """
    return [ancestor
            for ancestor in ancestry(item)
            if ancestor.startswith(library)][1:]


class Permissions(BeetsPlugin):
    def __init__(self):
        super().__init__()

        # Adding defaults.
        self.config.add({
            'file': '644',
            'dir': '755',
        })

        self.register_listener('item_imported', self.fix)
        self.register_listener('album_imported', self.fix)
        self.register_listener('art_set', self.fix_art)

    def fix(self, lib, item=None, album=None):
        """Fix the permissions for an imported Item or Album.
        """
        files = []
        dirs = set()
        if item:
            files.append(item.path)
            dirs.update(dirs_in_library(lib.directory, item.path))
        elif album:
            for album_item in album.items():
                files.append(album_item.path)
                dirs.update(dirs_in_library(lib.directory, album_item.path))
        self.set_permissions(files=files, dirs=dirs)

    def fix_art(self, album):
        """Fix the permission for Album art file.
        """
        if album.artpath:
            self.set_permissions(files=[album.artpath])

    def set_permissions(self, files=[], dirs=[]):
        # Get the configured permissions. The user can specify this either a
        # string (in YAML quotes) or, for convenience, as an integer so the
        # quotes can be omitted. In the latter case, we need to reinterpret the
        # integer as octal, not decimal.
        file_perm = config['permissions']['file'].get()
        dir_perm = config['permissions']['dir'].get()
        file_perm = convert_perm(file_perm)
        dir_perm = convert_perm(dir_perm)

        for path in files:
            # Changing permissions on the destination file.
            self._log.debug(
                'setting file permissions on {}',
                util.displayable_path(path),
            )
            os.chmod(util.syspath(path), file_perm)

            # Checks if the destination path has the permissions configured.
            assert_permissions(path, file_perm, self._log)

        # Change permissions for the directories.
        for path in dirs:
            # Changing permissions on the destination directory.
            self._log.debug(
                'setting directory permissions on {}',
                util.displayable_path(path),
            )
            os.chmod(util.syspath(path), dir_perm)

            # Checks if the destination path has the permissions configured.
            assert_permissions(path, dir_perm, self._log)
