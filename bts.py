#!/usr/bin/env python
from optparse import OptionParser
from beets import Library

if __name__ == "__main__":
    # parse options
    usage = """usage: %prog [options] command
command is one of: add, remove, update, write, list, help"""
    op = OptionParser(usage=usage)
    op.add_option('-l', '--library', dest='libpath', metavar='PATH',
                  default='library.blb',
                  help='work on the specified library file')
    op.remove_option('--help')
    opts, args = op.parse_args()
    
    # make sure we have a command
    if len(args) < 1:
        op.error('no command specified')
    cmd = args.pop(0)
    
    lib = Library(opts.libpath)
    
    # make a "help" command
    def help(*args): op.print_help()
    
    # choose which command to invoke
    avail_commands = [
        (lib.add,    ['add']),
        (lib.remove, ['remove', 'rm']),
        (lib.update, ['update', 'up']),
        (lib.write,  ['write', 'wr', 'w']),
        (lib.list,   ['list', 'ls']),
        (help,       ['help', 'h'])
    ]
    for test_command in avail_commands:
        if cmd in test_command[1]:
            (test_command[0])(*args)
            op.exit()
    
    # no command matched
    op.error('invalid command "' + cmd + '"')
        