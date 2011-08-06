# This file is part of beets.
# Copyright 2011, Adrian Sampson.
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
from beets.importer import _reopen_lib
import flask
from flask import g

app = flask.Flask(__name__)

@app.before_request
def before_request():
    g.lib = _reopen_lib(app.config['lib'])
@app.teardown_request
def teardown_request(req):
    g.lib.conn.close()

@app.route('/item/<int:item_id>')
def single_item(item_id):
    item = g.lib.get_item(item_id)
    return flask.jsonify(item.record)

@app.route('/item/')
def all_items():
    c = g.lib.conn.execute("SELECT id FROM items")
    all_ids = [row[0] for row in c]
    return flask.jsonify(item_ids=all_ids)

@app.route('/item/<int:item_id>/file')
def item_file(item_id):
    item = g.lib.get_item(item_id)
    return flask.send_file(item.path)

class WebPlugin(BeetsPlugin):
    def commands(self):
        cmd = ui.Subcommand('web', help='start a Web interface')
        def func(lib, config, opts, args):
            app.config['lib'] = lib
            app.run(debug=True)
        cmd.func = func
        return [cmd]
