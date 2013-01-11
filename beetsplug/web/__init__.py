# This file is part of beets.
# Copyright 2013, Adrian Sampson.
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

"""A Web interface to beets."""
from beets.plugins import BeetsPlugin
from beets import ui
from beets import util
import beets.library
import flask
from flask import g
import os


# Utilities.

def _rep(obj):
    """Get a flat -- i.e., JSON-ish -- representation of a beets Item or
    Album object.
    """
    if isinstance(obj, beets.library.Item):
        out = dict(obj.record)
        del out['path']

        # Get the size (in bytes) of the backing file. This is useful
        # for the Tomahawk resolver API.
        try:
            out['size'] = os.path.getsize(util.syspath(obj.path))
        except OSError:
            out['size'] = 0

        return out

    elif isinstance(obj, beets.library.Album):
        out = dict(obj._record)
        del out['artpath']
        out['items'] = [_rep(item) for item in obj.items()]
        return out


# Flask setup.

app = flask.Flask(__name__)

@app.before_request
def before_request():
    g.lib = app.config['lib']


# Items.

@app.route('/item/<int:item_id>')
def single_item(item_id):
    item = g.lib.get_item(item_id)
    return flask.jsonify(_rep(item))

@app.route('/item/')
def all_items():
    with g.lib.transaction() as tx:
        rows = tx.query("SELECT id FROM items")
    all_ids = [row[0] for row in rows]
    return flask.jsonify(item_ids=all_ids)

@app.route('/item/<int:item_id>/file')
def item_file(item_id):
    item = g.lib.get_item(item_id)
    return flask.send_file(item.path, as_attachment=True, attachment_filename=os.path.basename(item.path))

@app.route('/item/query/<path:query>')
def item_query(query):
    parts = query.split('/')
    items = g.lib.items(parts)
    return flask.jsonify(results=[_rep(item) for item in items])


# Albums.

@app.route('/album/<int:album_id>')
def single_album(album_id):
    album = g.lib.get_album(album_id)
    return flask.jsonify(_rep(album))

@app.route('/album/')
def all_albums():
    with g.lib.transaction() as tx:
        rows = tx.query("SELECT id FROM albums")
    all_ids = [row[0] for row in rows]
    return flask.jsonify(album_ids=all_ids)

@app.route('/album/query/<path:query>')
def album_query(query):
    parts = query.split('/')
    albums = g.lib.albums(parts)
    return flask.jsonify(results=[_rep(album) for album in albums])

@app.route('/album/<int:album_id>/art')
def album_art(album_id):
    album = g.lib.get_album(album_id)
    return flask.send_file(album.artpath)


# UI.

@app.route('/')
def home():
    return flask.render_template('index.html')


# Plugin hook.

class WebPlugin(BeetsPlugin):
    def __init__(self):
        super(WebPlugin, self).__init__()
        self.config.add({
            'host': u'',
            'port': 8337,
        })

    def commands(self):
        cmd = ui.Subcommand('web', help='start a Web interface')
        cmd.parser.add_option('-d', '--debug', action='store_true',
                              default=False, help='debug mode')
        def func(lib, opts, args):
            if args:
                self.config['host'] = args.pop(0)
            if args:
                self.config['port'] = int(args.pop(0))

            app.config['lib'] = lib
            app.run(host=self.config['host'].get(unicode),
                    port=self.config['port'].get(int),
                    debug=opts.debug, threaded=True)
        cmd.func = func
        return [cmd]
