'''
Fixes file permissions after the file gets written on import.

Put something like the following in your config.yaml to configure:

    fix_permissions:
            file: 0644

IMPORTANT: Write it exactly in this format. Else you could run into problems.
'''

import os
from beets import config
from beets.plugins import BeetsPlugin


def check_permissions(path, permission):
    ''' checks the permissions on the written path '''
    return oct(os.stat(path).st_mode & 0777) == oct(permission)


class FixPermissions(BeetsPlugin):
    ''' our plugin class '''
    pass


@FixPermissions.listen('after_write')
def fix_permissions(path):
    file_perm = config['fix_permissions'].get()['file']

    # doing the permission magic
    os.chmod(path, file_perm)

    # check permissions
    if not check_permissions(path, file_perm):
        message = 'There was a problem fixing permission on {}'.format(path)
        print(message)
