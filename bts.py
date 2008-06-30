#!/usr/bin/env python
from optparse import OptionParser
from beets import Library

def add(lib, paths):
    for path in paths:
        lib.add(path)
    lib.save()

def ls(lib, criteria):
    q = ' '.join(criteria)
    if not q.strip():
        q = None    # no criteria => match anything
    for item in lib.get(q):
        print item.artist + ' - ' + item.album + ' - ' + item.title

def imp(lib, paths):
    for path in paths:
        pass

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
        (add,        ['add']),
        (imp,        ['import', 'im', 'imp']),
        #(remove,     ['remove', 'rm']),
        #(update,     ['update', 'up']),
        #(write,      ['write', 'wr', 'w']),
        (ls,         ['list', 'ls']),
        (help,       ['help', 'h']),
    ]
    for test_command in avail_commands:
        if cmd in test_command[1]:
            (test_command[0])(lib, args)
            op.exit()
    
    # no command matched
    op.error('invalid command "' + cmd + '"')
