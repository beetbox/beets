# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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
from __future__ import division, absolute_import, print_function

from beets.plugins import BeetsPlugin
from beets import ui
from beets import util
import beets.library
import flask
from flask import g
from werkzeug.routing import BaseConverter, PathConverter
import os
import json


# Utilities.

def _rep(obj, expand=False):
    """Get a flat -- i.e., JSON-ish -- representation of a beets Item or
    Album object. For Albums, `expand` dictates whether tracks are
    included.
    """
    out = dict(obj)

    if isinstance(obj, beets.library.Item):
        if app.config.get('INCLUDE_PATHS', False):
            out['path'] = util.displayable_path(out['path'])
        else:
            del out['path']

        # Get the size (in bytes) of the backing file. This is useful
        # for the Tomahawk resolver API.
        try:
            out['size'] = os.path.getsize(util.syspath(obj.path))
        except OSError:
            out['size'] = 0

        return out

    elif isinstance(obj, beets.library.Album):
        del out['artpath']
        if expand:
            out['items'] = [_rep(item) for item in obj.items()]
        return out


def json_generator(items, root, expand=False):
    """Generator that dumps list of beets Items or Albums as JSON

    :param root:  root key for JSON
    :param items: list of :class:`Item` or :class:`Album` to dump
    :param expand: If true every :class:`Album` contains its items in the json
                   representation
    :returns:     generator that yields strings
    """
    yield '{"%s":[' % root
    first = True
    for item in items:
        if first:
            first = False
        else:
            yield ','
        yield json.dumps(_rep(item, expand=expand))
    yield ']}'


def is_expand():
    """Returns whether the current request is for an expanded response."""

    return flask.request.args.get('expand') is not None


def resource(name):
    """Decorates a function to handle RESTful HTTP requests for a resource.
    """
    def make_responder(retriever):
        def responder(ids):
            entities = [retriever(id) for id in ids]
            entities = [entity for entity in entities if entity]

            if len(entities) == 1:
                return flask.jsonify(_rep(entities[0], expand=is_expand()))
            elif entities:
                return app.response_class(
                    json_generator(entities, root=name),
                    mimetype='application/json'
                )
            else:
                return flask.abort(404)
        responder.__name__ = 'get_{0}'.format(name)
        return responder
    return make_responder


def resource_query(name):
    """Decorates a function to handle RESTful HTTP queries for resources.
    """
    def make_responder(query_func):
        def responder(queries):
            return app.response_class(
                json_generator(
                    query_func(queries),
                    root='results', expand=is_expand()
                ),
                mimetype='application/json'
            )
        responder.__name__ = 'query_{0}'.format(name)
        return responder
    return make_responder


def resource_list(name):
    """Decorates a function to handle RESTful HTTP request for a list of
    resources.
    """
    def make_responder(list_all):
        def responder():
            return app.response_class(
                json_generator(list_all(), root=name, expand=is_expand()),
                mimetype='application/json'
            )
        responder.__name__ = 'all_{0}'.format(name)
        return responder
    return make_responder


def _get_unique_table_field_values(model, field, sort_field):
    """ retrieve all unique values belonging to a key from a model """
    if field not in model.all_keys() or sort_field not in model.all_keys():
        raise KeyError
    with g.lib.transaction() as tx:
        rows = tx.query('SELECT DISTINCT "{0}" FROM "{1}" ORDER BY "{2}"'
                        .format(field, model._table, sort_field))
    return [row[0] for row in rows]


class IdListConverter(BaseConverter):
    """Converts comma separated lists of ids in urls to integer lists.
    """

    def to_python(self, value):
        ids = []
        for id in value.split(','):
            try:
                ids.append(int(id))
            except ValueError:
                pass
        return ids

    def to_url(self, value):
        return ','.join(value)


class QueryConverter(PathConverter):
    """Converts slash separated lists of queries in the url to string list.
    """

    def to_python(self, value):
        return value.split('/')

    def to_url(self, value):
        return ','.join(value)


class EverythingConverter(PathConverter):
    regex = '.*?'


# Flask setup.

app = flask.Flask(__name__)
app.url_map.converters['idlist'] = IdListConverter
app.url_map.converters['query'] = QueryConverter
app.url_map.converters['everything'] = EverythingConverter


@app.before_request
def before_request():
    g.lib = app.config['lib']


# Items.

@app.route('/item/<idlist:ids>')
@resource('items')
def get_item(id):
    return g.lib.get_item(id)


@app.route('/item/')
@app.route('/item/query/')
@resource_list('items')
def all_items():
    return g.lib.items()


@app.route('/item/<int:item_id>/file')
def item_file(item_id):
    item = g.lib.get_item(item_id)
    response = flask.send_file(
        util.py3_path(item.path),
        as_attachment=True,
        attachment_filename=os.path.basename(util.py3_path(item.path)),
    )
    response.headers['Content-Length'] = os.path.getsize(item.path)
    return response


@app.route('/item/query/<query:queries>')
@resource_query('items')
def item_query(queries):
    return g.lib.items(queries)


@app.route('/item/path/<everything:path>')
def item_at_path(path):
    query = beets.library.PathQuery('path', path.encode('utf-8'))
    item = g.lib.items(query).get()
    if item:
        return flask.jsonify(_rep(item))
    else:
        return flask.abort(404)


@app.route('/item/values/<string:key>')
def item_unique_field_values(key):
    sort_key = flask.request.args.get('sort_key', key)
    try:
        values = _get_unique_table_field_values(beets.library.Item, key,
                                                sort_key)
    except KeyError:
        return flask.abort(404)
    return flask.jsonify(values=values)


# Albums.

@app.route('/album/<idlist:ids>')
@resource('albums')
def get_album(id):
    return g.lib.get_album(id)


@app.route('/album/')
@app.route('/album/query/')
@resource_list('albums')
def all_albums():
    return g.lib.albums()


@app.route('/album/query/<query:queries>')
@resource_query('albums')
def album_query(queries):
    return g.lib.albums(queries)


@app.route('/album/<int:album_id>/art')
def album_art(album_id):
    album = g.lib.get_album(album_id)
    if album.artpath:
        return flask.send_file(album.artpath)
    else:
        return flask.abort(404)


@app.route('/album/values/<string:key>')
def album_unique_field_values(key):
    sort_key = flask.request.args.get('sort_key', key)
    try:
        values = _get_unique_table_field_values(beets.library.Album, key,
                                                sort_key)
    except KeyError:
        return flask.abort(404)
    return flask.jsonify(values=values)


# Artists.

@app.route('/artist/')
def all_artists():
    with g.lib.transaction() as tx:
        rows = tx.query("SELECT DISTINCT albumartist FROM albums")
    all_artists = [row[0] for row in rows]
    return flask.jsonify(artist_names=all_artists)


# Library information.

@app.route('/stats')
def stats():
    with g.lib.transaction() as tx:
        item_rows = tx.query("SELECT COUNT(*) FROM items")
        album_rows = tx.query("SELECT COUNT(*) FROM albums")
    return flask.jsonify({
        'items': item_rows[0][0],
        'albums': album_rows[0][0],
    })


# UI.

@app.route('/')
def home():
    return flask.render_template('index.html')


# Plugin hook.

class WebPlugin(BeetsPlugin):
    def __init__(self):
        super(WebPlugin, self).__init__()
        self.config.add({
            'host': u'127.0.0.1',
            'port': 8337,
            'cors': '',
            'reverse_proxy': False,
            'include_paths': False,
        })

    def commands(self):
        cmd = ui.Subcommand('web', help=u'start a Web interface')
        cmd.parser.add_option(u'-d', u'--debug', action='store_true',
                              default=False, help=u'debug mode')

        def func(lib, opts, args):
            args = ui.decargs(args)
            if args:
                self.config['host'] = args.pop(0)
            if args:
                self.config['port'] = int(args.pop(0))

            app.config['lib'] = lib
            # Normalizes json output
            app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

            app.config['INCLUDE_PATHS'] = self.config['include_paths']

            # Enable CORS if required.
            if self.config['cors']:
                self._log.info(u'Enabling CORS with origin: {0}',
                               self.config['cors'])
                from flask.ext.cors import CORS
                app.config['CORS_ALLOW_HEADERS'] = "Content-Type"
                app.config['CORS_RESOURCES'] = {
                    r"/*": {"origins": self.config['cors'].get(str)}
                }
                CORS(app)

            # Allow serving behind a reverse proxy
            if self.config['reverse_proxy']:
                app.wsgi_app = ReverseProxied(app.wsgi_app)

            # Start the web application.
            app.run(host=self.config['host'].as_str(),
                    port=self.config['port'].get(int),
                    debug=opts.debug, threaded=True)
        cmd.func = func
        return [cmd]


class ReverseProxied(object):
    '''Wrap the application in this middleware and configure the
    front-end server to add these headers, to let you quietly bind
    this to a URL other than / and to an HTTP scheme that is
    different than what is used locally.

    In nginx:
    location /myprefix {
        proxy_pass http://192.168.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Scheme $scheme;
        proxy_set_header X-Script-Name /myprefix;
        }

    From: http://flask.pocoo.org/snippets/35/

    :param app: the WSGI application
    '''
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        script_name = environ.get('HTTP_X_SCRIPT_NAME', '')
        if script_name:
            environ['SCRIPT_NAME'] = script_name
            path_info = environ['PATH_INFO']
            if path_info.startswith(script_name):
                environ['PATH_INFO'] = path_info[len(script_name):]

        scheme = environ.get('HTTP_X_SCHEME', '')
        if scheme:
            environ['wsgi.url_scheme'] = scheme
        return self.app(environ, start_response)
