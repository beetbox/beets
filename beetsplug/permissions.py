from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

"""Fixes file permissions after the file gets written on import. Put something
like the following in your config.yaml to configure:

    permissions:
            file: 644
            dir: 755
"""
import os
from collections import OrderedDict
from beets import config, util
from beets.plugins import BeetsPlugin
from beets.util import displayable_path


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


def get_music_directories(music_directory, imported_item):
    """Creates a list of directories the imported item is in.
    """
    # Checks for the directory in config and if it has a tilde in it.
    # If its that way it will be expanded to the full path.
    if '~' in music_directory:
        music_directory = os.path.expanduser(music_directory)

    # Getting the absolute path of the directory.
    music_directory = os.path.abspath(music_directory)

    # Creates a differential path list of the directory config path and
    # the path of the imported item.
    differential_path_list = os.path.split(
        displayable_path(imported_item).split(
            music_directory)[1])[0].split('/')[1:]

    # Creating a list with full paths of all directories in the music library
    # we need to look at for chaning permissions.
    directory_list = []
    for path in differential_path_list:
        if len(directory_list) > 0:
            directory_list.append(os.path.join(directory_list[-1], path))
        else:
            directory_list.append(os.path.join(music_directory, path))

    return directory_list


class Permissions(BeetsPlugin):
    def __init__(self):
        super(Permissions, self).__init__()

        # Adding defaults.
        self.config.add({
            u'file': 644,
            u'dir': 755
        })


@Permissions.listen('item_imported')
@Permissions.listen('album_imported')
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

    # A list of directories to set permissions for.
    dir_chmod_queue = []

    for path in file_chmod_queue:
        # Changing permissions on the destination file.
        os.chmod(util.bytestring_path(path), file_perm)

        # Checks if the destination path has the permissions configured.
        if not check_permissions(util.bytestring_path(path), file_perm):
            message = 'There was a problem setting permission on {}'.format(
                path)
            print(message)

        # Adding directories to the chmod queue.
        dir_chmod_queue.append(
            get_music_directories(config['directory'].get(), path))

    # Unpack sublists.
    dir_chmod_queue = [directory
                       for dir_list in dir_chmod_queue
                       for directory in dir_list]

    # Get rid of the duplicates.
    dir_chmod_queue = list(OrderedDict.fromkeys(dir_chmod_queue))

    # Change permissions for the directories.
    for path in dir_chmod_queue:
        # Chaning permissions on the destination directory.
        os.chmod(util.bytestring_path(path), dir_perm)
        # Checks if the destination path has the permissions configured.

        if not check_permissions(util.bytestring_path(path), dir_perm):
            message = 'There was a problem setting permission on {}'.format(
                path)
            print(message)
