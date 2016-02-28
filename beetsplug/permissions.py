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
    """If the perm is a int it will first convert it to a string and back
    to an oct int. Else it just converts it to oct.
    """
    if isinstance(perm, int):
        return int(bytes(perm), 8)
    else:
        return int(perm, 8)


def check_permissions(path, permission):
    """Checks the permissions of a path.
    """
    return oct(os.stat(path).st_mode & 0o777) == oct(permission)


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
            u'file': 644,
            u'dir': 755
        })

        self.register_listener('item_imported', permissions)
        self.register_listener('album_imported', permissions)


def permissions(lib, item=None, album=None):
    """Running the permission fixer.
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
        os.chmod(util.bytestring_path(path), file_perm)

        # Checks if the destination path has the permissions configured.
        if not check_permissions(util.bytestring_path(path), file_perm):
            message = u'There was a problem setting permission on {}'.format(
                path)
            print(message)

        # Adding directories to the directory chmod queue.
        dir_chmod_queue.update(
            dirs_in_library(lib.directory,
                            path))

    # Change permissions for the directories.
    for path in dir_chmod_queue:
        # Chaning permissions on the destination directory.
        os.chmod(util.bytestring_path(path), dir_perm)

        # Checks if the destination path has the permissions configured.
        if not check_permissions(util.bytestring_path(path), dir_perm):
            message = u'There was a problem setting permission on {}'.format(
                path)
            print(message)
