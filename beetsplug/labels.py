# Copyright 2013, Steinthor Palsson <steinitzu@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

from beets.plugins import BeetsPlugin
from beets.ui import Subcommand
from beets.library import Query, ResultIterator, Album
from beets import ui
from beets.ui import Template

"""
A plugin which lets users give arbitrary labels 
to the music in the beets library.
"""

TABLES = """
CREATE TABLE IF NOT EXISTS labels (
        id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
        label VARCHAR NOT NULL);
CREATE TABLE IF NOT EXISTS labels_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        label_id INTEGER,
        item_id INTEGER,
        FOREIGN KEY (label_id) REFERENCES labels(id) ON DELETE CASCADE,
        FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS labels_albums(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        label_id INTEGER,
        album_id INTEGER,
        FOREIGN KEY (label_id) REFERENCES labels(id) ON DELETE CASCADE,
        FOREIGN KEY (album_id) REFERENCES albums(id) ON DELETE CASCADE);
"""

#Taken from 
#docs.python.org/2/library/optparse.html#callback-example-6-variable-arguments
#To allow variable number of arguments 
#for an option without creating an argparse (python2.7) dependency.
def vararg_callback(option, opt_str, value, parser):
    assert value is None
    value = []
    def floatable(str):
        try:
            float(str)
            return True
        except ValueError:
            return False
    for arg in parser.rargs:
        # stop on --foo like options
        if arg[:2] == "--" and len(arg) > 2:
            break
        # stop on -a, but not on -3 or -3.0
        if arg[:1] == "-" and len(arg) > 1 and not floatable(arg):
            break
        value.append(arg)
    del parser.rargs[:len(value)]
    setattr(parser.values, option.dest, value)

class LabelQuery(Query):
    """
    A query which looks for all items matching a list of labels.
    Only items matching all labels are returned.
    """    
    def __init__(self, labels, albums=False):
        self.labels=[l.lower() for l in labels]
        self.mode = 'album' if albums else 'item'

    def statement(self, columns='*'):
        columns = ','.join(['i.'+c for c in columns.split(',')])
        clause, subvals = self.clause()
        q = 'SELECT DISTINCT %s FROM %ss AS i ' % (columns, self.mode)
        q+=clause
        return q, subvals

    def clause(self):
        if not self.labels:
            return ''
        c = """
            EXISTS (SELECT 1 FROM labels_%ss AS li
            LEFT JOIN labels AS l ON li.label_id = l.id
            WHERE l.label = ? AND li.%s_id = i.id)
            """ % (self.mode, self.mode)
        clauses = [c for l in self.labels]
        clause = 'WHERE'+' AND '.join(clauses)
        return clause,self.labels

def make_env(lib):
    """
    Set up the environment.
    Create labels tables in the beets database if they don't exist.
    """
    t = lib.transaction()
    t.script(TABLES)    

def make_label(lib, label):
    """
    Create a new label and return its id.
    If label with same name exists, its id is returned without 
    any changes to the database.
    """
    label = label.lower()
    qget = 'SELECT id FROM labels WHERE label = ?;'
    qset = 'INSERT INTO labels (label) VALUES (?);'
    with lib.transaction() as tx:
        exlb = tx.query(qget, (label,))
        if exlb:
            return exlb[0]['id']
        else:
            return tx.mutate(qset, (label,))

def _mutate_labels(lib, query, labels, albums=False, remove=False):
    """
    Set or remove labels to items/albums matching query.
    """
    if albums:
        table = 'labels_albums'
        func = lib.albums
        field = 'album_id'
    else:
        table = 'labels_items'
        func = lib.items
        field = 'item_id'
    if remove:
        qset = '''
        DELETE FROM {table} 
        WHERE {table}.{field} = ? 
        AND {table}.label_id IN (
        SELECT id FROM labels WHERE label = ?);
        '''.format(table=table, field=field)
    else:
        qset = 'INSERT INTO {} ({}, label_id) VALUES (?, ?);'.format(
            table, field)
        labelids = [make_label(lib, a) for a in labels]
    items = func(query=query)
    with lib.transaction() as tx:    
        for item in items:
            itemid = item.id
            for i,l in enumerate(labels):
                if remove:
                    tx.mutate(qset, (itemid, l))
                    continue
                tx.mutate(qset, (itemid, labelids[i]))
                
def remove_labels(lib, query, labels, albums=False):
    """
    Remove given `labels` from items matching `query`.
    """
    _mutate_labels(lib, query, labels, albums=albums, remove=True)    

def set_labels(lib, query, labels, albums=False):
    """
    Set labels for items or albums matching a query.
    `query` can be a `Query` like object or a beets query string.
    """
    _mutate_labels(lib, query, labels, albums=albums, remove=False)

def get_items(lib, labels, albums=False):
    """
    Returns an iterable of items or albums matching given labels.
    """
    q = LabelQuery(labels, albums=albums)
    sql,subvals = q.statement()
    if albums:
        with lib.transaction() as tx:
            rows = tx.query(sql, subvals)
            items = [Album(lib, dict(row)) for row in rows]
    else:
        with lib.transaction() as tx:
            items = ResultIterator(tx.query(sql, subvals))
    return items

def get_labels(lib):
    """
    Returns a tuple(id,label) list of all existing labels.
    """
    q = 'SELECT id,label FROM labels ORDER BY label ASC;'
    with lib.transaction() as tx:
        res = [(row['id'], row['label']) for row in tx.query(q)]
    return res

def list_items(lib, labels, albums=False):
    """
    Print items or albums matching given list of labels.
    """
    tmpl = Template(ui._pick_format(albums, None))
    items = get_items(lib, labels, albums=albums)
    for item in items:
        ui.print_obj(item, lib, tmpl)

def list_labels(lib):
    """
    List all labels in the database.
    """
    for l in get_labels(lib):
        ui.print_(l[1])

def do_labels(lib, opts, args):
    make_env(lib)
    if not args:
        list_labels(lib)
        return
    args = ui.decargs(args)
    if opts.attach_query:
        q = ui.decargs(opts.attach_query)
        set_labels(lib, q, args, albums=opts.albums)
    elif opts.remove_query:
        q = ui.decargs(opts.remove_query)
        remove_labels(lib, q, args, albums=opts.albums)
    else:
        list_items(lib, args, albums=opts.albums)

class LabelsPlugin(BeetsPlugin):
    def commands(self):
        usage = 'beet labels args [--albums][-a|-r query]\n'\
        +'You can provide multiple labels separated by space.\n'\
        +'When no options orarguments are provided, a list '\
        +'of labels currently in the database is outputted.'
        cmd = Subcommand(
            'labels', 
            help='Get and set labels for your music.')
        cmd.parser.set_usage(usage)
        cmd.parser.add_option(
            '-a', '--attach-to', dest='attach_query',
            callback=vararg_callback, action='callback',
            help='Attaches the given labels to all items matching '\
                +'the following query.\n'\
                +'(Everything after -a will be treated as part of the query).')
        cmd.parser.add_option(
            '-r', '--remove-from', dest='remove_query',
            callback=vararg_callback, action='callback',
            help='Same as -a, but removes labels from matching items '\
                 +'instead of adding them.')
        cmd.parser.add_option(
            '--albums', action='store_true', dest='albums',
            help='Deal in albums instead of individual tracks.')
        cmd.func = do_labels
        return [cmd]


