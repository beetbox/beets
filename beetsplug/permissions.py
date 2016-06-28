# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, print_function

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
    """If the perm is a int then just return it, otherwise convert it to oct.
    """
    if isinstance(perm, int):
        return perm
    else:
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
        log.warn(
            u'could not set permissions on {}',
            util.displayable_path(path),
        )
        log.debug(
            u'set permissions to {}, but permissions are now {}',
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
        super(Permissions, self).__init__()

        # Adding defaults.
        self.config.add({
            u'file': '644',
            u'dir': '755'
        })

        self.register_listener('item_imported', self.fix)
        self.register_listener('album_imported', self.fix)

    def fix(self, lib, item=None, album=None):
        """Fix the permissions for an imported Item or Album.
        """
        # Getting the config.
        file_perm = config['permissions']['file'].get()
        dir_perm = config['permissions']['dir'].get()

        # Converts permissions to oct.
        file_perm = convert_perm(file_perm)
        dir_perm = convert_perm(dir_perm)

        # Create chmod_queue.
        file_chmod_queue = []
        if item:
            file_chmod_queue.append(item.path)
        elif album:
            for album_item in album.items():
                file_chmod_queue.append(album_item.path)

        # A set of directories to change permissions for.
        dir_chmod_queue = set()

        for path in file_chmod_queue:
            # Changing permissions on the destination file.
            os.chmod(util.syspath(path), file_perm)

            # Checks if the destination path has the permissions configured.
            assert_permissions(path, file_perm, self._log)

            # Adding directories to the directory chmod queue.
            dir_chmod_queue.update(
                dirs_in_library(lib.directory,
                                path))

        # Change permissions for the directories.
        for path in dir_chmod_queue:
            # Chaning permissions on the destination directory.
            os.chmod(util.syspath(path), dir_perm)

            # Checks if the destination path has the permissions configured.
            assert_permissions(path, dir_perm, self._log)
