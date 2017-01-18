# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Joël Charles.
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

"""
A (subset of) subsonic API implementation on top of Web plugin.
See http://www.subsonic.org/pages/api.jsp
"""

from __future__ import division, absolute_import, print_function

import datetime
import mimetypes
import os
import re
from time import time
from xml.dom.minidom import Text

import six
from flask import send_file, g, Response, Blueprint, request
from flask.json import jsonify

from beets.plugins import BeetsPlugin
from beets.util.random import random_objs
from beetsplug.web import app

DEFAULT_VERSION = '1.10.1'
subsonic_routes = Blueprint('subsonic', 'subsonic')


def dict2xml(d, root_node=None):
    """Transform python dict to XML string representation"""
    wrap = False if None is root_node or isinstance(d, list) else True
    root = 'objects' if None is root_node else root_node
    root_singular = root[:-1] if 's' == root[-1] and \
                                 None is root_node else root
    xml = ''
    children = []

    if isinstance(d, dict):
        for key, value in dict.items(d):
            if isinstance(value, dict):
                children.append(dict2xml(value, key))
            elif isinstance(value, list):
                children.append(dict2xml(value, key))
            else:
                t = Text()
                if isinstance(value, bool):
                    t.data = str(value).lower()
                elif isinstance(value, bytes):
                    t.data = value.decode('utf-8')
                elif not isinstance(value, six.text_type):
                    t.data = six.text_type(value)
                else:
                    t.data = value
                xml = u'{} {}="{}"'.format(xml, key, t.toxml())
    else:
        for value in d:
            children.append(dict2xml(value, root_singular))

    end_tag = u'>' if 0 < len(children) else u'/>'

    if wrap or isinstance(d, dict):
        xml = u"<{}{}{}".format(root, xml, end_tag)

    if 0 < len(children):
        for child in children:
            xml = u"{}{}".format(xml, child)

        if wrap or isinstance(d, dict):
            xml = u"{}</{}>".format(xml, root)

    return xml


def clean_dict_for_json(d):
    """Clean dict for future json export"""
    for key, value in d.items():
        if isinstance(value, dict):
            d[key] = clean_dict_for_json(value)
        elif isinstance(value, list):
            if len(value) == 0:
                del d[key]
            else:
                d[key] = [clean_dict_for_json(item) if isinstance(item, dict)
                          else item for item in value]
    return d


def jsonresponse(resp, error=False, version=DEFAULT_VERSION):
    """Returns a json string response of the given dict"""
    resp = clean_dict_for_json(resp)
    resp.update({
        'status': 'failed' if error else 'ok',
        'version': version,
        'xmlns': "http://subsonic.org/restapi"
    })
    return jsonify({'subsonic-response': resp})


def jsonpresponse(resp, callback, error=False, version=DEFAULT_VERSION):
    """Returns a jsonp string response of the given dict"""
    resp = jsonresponse(resp, error, version)
    resp.set_data('{}({})'.format(
        callback,
        resp.get_data(as_text=True)
    ))
    return resp


def xmlresponse(resp, error=False, version=DEFAULT_VERSION):
    """Returns an XML string response of the given dict"""
    resp.update({
        'status': 'failed' if error else 'ok',
        'version': version,
        'xmlns': "http://subsonic.org/restapi"
    })

    output = dict2xml(resp, "subsonic-response")

    return Response(
        u"{}{}".format(u'<?xml version="1.0" encoding="UTF-8"?>', output),
        content_type='text/xml; charset=utf-8')


@subsonic_routes.before_request
def subsonicify():
    """Adds `formatter` and `error_formatter` to each subsonic views requests.
    """
    if not request.path.endswith('.view'):
        return

    # Return a function to create the response.
    f = request.args.get('f')
    callback = request.args.get('callback')
    if f == 'jsonp':
        # Some clients (MiniSub, Perisonic) set f to jsonp without callback
        # for streamed data
        if not callback and request.endpoint not in ['subsonic.v_download',
                                                     'subsonic.v_cover_art']:
            return jsonresponse({
                'error': {
                    'code': 0,
                    'message': 'Missing callback'
                }
            }, error=True), 400
        request.formatter = lambda x, **kwargs: jsonpresponse(x, callback,
                                                              kwargs)
    elif f == "json":
        request.formatter = jsonresponse
    else:
        request.formatter = xmlresponse

    request.error_formatter = lambda code, msg: request.formatter(
        {'error': {'code': code, 'message': msg}}, error=True)


@subsonic_routes.after_request
def set_content_type(response):
    """Automatic Content-Type calculation"""
    if not request.path.endswith('.view'):
        return response

    if response.mimetype.startswith('text'):
        f = request.args.get('f')
        response.headers['content-type'] = 'application/json'\
            if f in ['jsonp', 'json'] else 'text/xml'

    return response


@subsonic_routes.errorhandler(404)
def not_found(error):
    """Handles `Not implemented` message"""
    if not request.path.endswith('.view'):
        return error

    return request.error_formatter(0, 'Not implemented'), 501


def get_query(from_year=None, to_year=None, genre=None):
    """Generates a query for year range and genre"""
    if from_year is not None or to_year is not None:
        return u'year:{}..{}'.format(
            from_year if from_year is not None else '',
            to_year if to_year is not None else '')
    if genre is not None:
        return u'genre:{}'.format(genre)
    return u''


def get_query_by_type(atype, from_year=None, to_year=None, genre=None):
    """Generates a query for a given type"""
    if atype == 'newest':
        return u'added-'
    elif atype == 'starred':
        return u'^'
    elif atype == 'byYear':
        return u'year:{}..{} year+'.format(from_year, to_year)
    elif atype == 'genre':
        return u'genre:{} genre+'.format(genre)
    elif atype == 'alphabeticalByName':
        return u'album+'
    elif atype == 'alphabeticalByArtist':
        return u'albumartist+ album+'
    # elif atype == 'highest':
    #     return u''
    # elif atype == 'frequent':
    #     return u''
    # elif atype == 'recent':
    #     return u''
    return u'album+'


def format_track_id(eid):
    """Transform numeric track ID to generic ID so that this API can easily
    know its type"""
    return 'TR%s' % eid


def format_artist_id(eid):
    """Transform numeric artist ID to generic ID so that this API can easily
    know its type"""
    return 'AR%s' % eid


def format_album_id(eid):
    """Transform numeric album ID to generic ID so that this API can easily
    know its type"""
    return 'AL%s' % eid


def is_track_id(eid):
    """Check if given generic ID corresponds to a track"""
    return eid.startswith('TR')


def is_artist_id(eid):
    """Check if given generic ID corresponds to an artist"""
    return eid.startswith('AR')


def is_album_id(eid):
    """Check if given generic ID corresponds to an album"""
    return eid.startswith('AL')


def clean_id(eid):
    """Generic ID to beets ID"""
    return eid[2:]


def format_artist(artist, count=None):
    """Artist dict representation for subsonic API"""
    info = {
        'id': format_artist_id(artist),
        'name': artist
    }
    if count is not None:
        info['albumCount'] = count
    return info


def format_album(album, child=False):
    """Album dict representation for subsonic API"""
    info = {
        'id': format_album_id(album.id),
        'artist': album.albumartist,
        'artistId': format_artist_id(album.albumartist),
        'duration': int(album.duration),
        'created': datetime.datetime.fromtimestamp(album.added).isoformat(),
        'year': album.year,
        'coverArt': format_album_id(album.id),
        'averageRating': 0
    }

    if child:
        info['isDir'] = True
        if album.year:
            info['title'] = u"{} ({})".format(album.album, album.year)
        else:
            info['title'] = album.album
        info['parent'] = format_artist_id(album.albumartist)
    else:
        info['songCount'] = album.track_count
        info['name'] = album.album

    return info


def format_track(track):
    """Track dict representation for subsonic API"""
    albumid = format_album_id(track.album_id)
    unicodepath = track.path.decode('utf-8')
    info = {
        "id": format_track_id(track.id),
        "parent": albumid,
        "title": track.title,
        "isDir": False,
        "isVideo": False,
        "type": 'music',
        "albumId": albumid,
        "album": track.album,
        "artistId": format_artist_id(track.albumartist),
        "artist": track.albumartist,
        "genre": track.genre,
        "covertArt": albumid,
        "duration": int(track.length),
        "bitRate": int(track.bitrate / 1000),
        "track": track.track,
        "year": track.year,
        "size": os.path.getsize(unicodepath),
        'created': datetime.datetime.fromtimestamp(track.added).isoformat(),
        "contentType": mimetypes.guess_type(unicodepath)[0]
    }
    return info


def check_parameter(req, key, allow_none=True, choices=None, fct=None):
    """Check if a URL parameter is valid"""
    val = req.args.get(key)
    if val is None and not allow_none:
        return False, req.error_formatter(
            10, 'Missing parameter {}'.format(key))
    if choices is not None and val not in choices:
        return False, req.error_formatter(
            0, 'Invalid value {} for parameter {}'.format(val, key))
    if fct is not None:
        try:
            return True, fct(val)
        except:
            return False, req.error_formatter(
                0, 'Invalid parameter {}'.format(key))
    return True, val


def _limit(l, offset, size):
    """Mimic LIMIT/OFFSET in python"""
    maxv = offset + size
    for i, e, in enumerate(l):
        if i >= maxv:
            break
        if i >= offset:
            yield e


def _album_list():
    """Helper for generating album list"""
    ok, atype = check_parameter(request, 'type', allow_none=False,
                                choices=['random', 'newest', 'highest',
                                         'frequent', 'recent', 'starred',
                                         'alphabeticalByName',
                                         'alphabeticalByArtist', 'byYear',
                                         'genre'])
    if not ok:
        return False, atype
    ok, size = check_parameter(request, 'size',
                               fct=lambda val: int(val) if val else 10)
    if not ok:
        return False, size
    ok, offset = check_parameter(request, 'offset',
                                 fct=lambda val: int(val) if val else 0)
    if not ok:
        return False, offset
    ok, from_year = check_parameter(request, 'fromYear',
                                    fct=lambda val: int(val) if val else None)
    if not ok:
        return False, from_year
    ok, to_year = check_parameter(request, 'toYear',
                                  fct=lambda val: int(val) if val else None)
    if not ok:
        return False, to_year
    genre = request.args.get('genre')

    if atype == "byYear" and (not from_year or not to_year):
        return False, request.error_formatter(
            10, 'Missing parameter fromYear or toYear')
    elif atype == "genre" and not genre:
        return False, request.error_formatter(10, 'Missing parameter genre')

    if atype == "random":
        return True, random_objs(list(g.lib.albums(u'')), True, number=size)
    else:
        query = get_query_by_type(atype, from_year=from_year, to_year=to_year,
                                  genre=genre)
        return True, _limit(g.lib.albums(query), offset, size)


@subsonic_routes.route('/rest/ping.view', methods=['GET', 'POST'])
def v_ping():
    return request.formatter({})


@subsonic_routes.route('/rest/getLicense.view', methods=['GET', 'POST'])
def v_show_license():
    return request.formatter({'license': {'valid': True}})


@subsonic_routes.route('/rest/getMusicFolders.view', methods=['GET', 'POST'])
def v_music_folders():
    return request.formatter({
        'musicFolders': {
            'musicFolder': [{
                'id': 1,
                'name': 'Music'
            }]
        }
    })


@subsonic_routes.route('/rest/getArtists.view', methods=['GET', 'POST'])
@subsonic_routes.route('/rest/getIndexes.view', methods=['GET', 'POST'])
def v_indexes():
    """
    Parameters ifModifiedSince and musicFolderId are ignored
    """
    last_modif = int(time() * 1000)
    indexes = {}
    with g.lib.transaction() as tx:
        rows = tx.query("SELECT albumartist, COUNT(albums.id) "
                        "FROM albums "
                        "GROUP BY albumartist "
                        "ORDER BY albumartist")

    for artist, count, in rows:
        if artist is None:
            continue
        letter = artist[0].upper()
        if letter == "X" or letter == "Y" or letter == "Z":
            letter = "X-Z"
        elif re.match("^[A-W]$", letter) is None:
            letter = "#"

        if letter not in indexes:
            indexes[letter] = []
        indexes[letter].append((artist, count))

    return request.formatter({
        'indexes': {
            'lastModified': last_modif,
            'ignoredArticles': '',
            'index': [{
                'name': k,
                'artist': [format_artist(a, count) for a, count, in v]
            } for k, v in sorted(indexes.items(), key=lambda x: x[1][0])],
        }
    })


@subsonic_routes.route('/rest/getMusicDirectory.view', methods=['GET', 'POST'])
def v_music_directory():
    eid = request.args.get('id')
    cid = clean_id(eid)
    if is_artist_id(eid):
        children = g.lib.albums(u'albumartist:{}'.format(cid))
        format_child = lambda x: format_album(x, child=True)
    elif is_album_id(eid):
        children = g.lib.items(u'album:{}'.format(cid))
        format_child = format_track
    else:
        return request.error_formatter(10, 'Missing or invalid id')

    return request.formatter({'directory': {
        'id': eid,
        'name': cid,
        'child': [format_child(child) for child in children]
    }})


@subsonic_routes.route('/rest/getArtist.view', methods=['GET', 'POST'])
def v_artist():
    eid = request.args.get('id')
    cid = clean_id(eid)
    if not is_artist_id(eid):
        return request.error_formatter(10, 'Missing or invalid Artist id')

    albums = g.lib.albums(u'albumartist:{}'.format(cid))

    if len(albums) == 0:
        return request.error_formatter(70, 'Artist not found'), 404

    return request.formatter({'artist': {
        'id': eid,
        'name': cid,
        'albumCount': len(albums),
        'album': [format_album(album) for album in albums]
    }})


@subsonic_routes.route('/rest/getAlbum.view', methods=['GET', 'POST'])
def v_album():
    eid = request.args.get('id')
    cid = clean_id(eid)
    if not is_album_id(eid):
        return request.error_formatter(10, 'Missing or invalid Album id')

    album = g.lib.get_album(int(cid))

    if album is None:
        return request.error_formatter(70, 'Album not found'), 404

    tracks = album.items()

    return request.formatter({'album': {
        'id': eid,
        'name': cid,
        'songCount': len(tracks),
        'song': [format_track(track) for track in tracks]
    }})


@subsonic_routes.route('/rest/getSong.view', methods=['GET', 'POST'])
def v_song():
    eid = request.args.get('id')
    cid = clean_id(eid)
    if not is_track_id(eid):
        return request.error_formatter(10, 'Missing or invalid Song id')

    tr = g.lib.get_item(cid)

    if not tr:
        return request.error_formatter(70, 'Song not found'), 404

    return request.formatter({'song': format_track(tr)})


@subsonic_routes.route('/rest/getRandomSongs.view', methods=['GET', 'POST'])
def v_random_songs():
    ok, size = check_parameter(request, 'size',
                               fct=lambda val: int(val) if val else 10)
    if not ok:
        return False, size
    size = min(size, 50)
    from_year = request.args.get('fromYear')
    to_year = request.args.get('toYear')
    genre = request.args.get('genre')

    query = get_query(from_year=from_year, to_year=to_year, genre=genre)

    return request.formatter({'randomSongs': {
        'song': [format_track(track) for track in
                 random_objs(list(g.lib.items(query)), False, number=size)]
    }})


@subsonic_routes.route('/rest/getAlbumList.view', methods=['GET', 'POST'])
def v_album_list():
    ok, albums = _album_list()
    if not ok:
        return albums

    return request.formatter({'albumList': {
        'album': [format_album(album, child=True) for album in albums]
    }})


@subsonic_routes.route('/rest/getAlbumList2.view', methods=['GET', 'POST'])
def v_album_list2():
    ok, albums = _album_list()
    if not ok:
        return albums

    return request.formatter({'albumList2': {
        'album': [format_album(album) for album in albums]
    }})


@subsonic_routes.route('/rest/search2.view', methods=['GET', 'POST'])
@subsonic_routes.route('/rest/search3.view', methods=['GET', 'POST'])
def v_search2and3():
    q = request.args.get('query')
    if not q:
        return request.error_formatter(10, 'Missing query parameter')
    ok, artist_count = check_parameter(request, 'artistCount',
                                       fct=lambda val: int(val) if val else 20)
    if not ok:
        return False, artist_count
    ok, artist_offset = check_parameter(request, 'artistOffset',
                                        fct=lambda val: int(val) if val else 0)
    if not ok:
        return False, artist_offset
    ok, album_count = check_parameter(request, 'albumCount',
                                      fct=lambda val: int(val) if val else 20)
    if not ok:
        return False, album_count
    ok, album_offset = check_parameter(request, 'albumOffset',
                                       fct=lambda val: int(val) if val else 0)
    if not ok:
        return False, album_offset
    ok, song_count = check_parameter(request, 'songCount',
                                     fct=lambda val: int(val) if val else 20)
    if not ok:
        return False, song_count
    ok, song_offset = check_parameter(request, 'songOffset',
                                      fct=lambda val: int(val) if val else 0)
    if not ok:
        return False, song_offset

    with g.lib.transaction() as tx:
        rows = tx.query("SELECT albumartist, COUNT(albums.id) "
                        "FROM albums "
                        "WHERE albumartist LIKE '%%' || ? || '%%' ESCAPE '\\' "
                        "GROUP BY albumartist "
                        "ORDER BY albumartist "
                        "LIMIT ? OFFSET ?",
                        [q, artist_count, artist_offset])
    albums = _limit(g.lib.albums(u'album:{}'.format(q)), album_offset,
                    album_count)
    tracks = _limit(g.lib.items(u'title:{}'.format(q)), song_offset,
                    song_count)

    return request.formatter({'searchResult2': {
        'artist': [format_artist(artist, count) for artist, count, in rows],
        'album': [format_album(album) for album in albums],
        'track': [format_track(track) for track in tracks]
    }})


@subsonic_routes.route('/rest/getCoverArt.view', methods=['GET', 'POST'])
def v_cover_art():
    eid = request.args.get('id')
    cid = clean_id(eid)
    if not is_track_id(eid) and not is_album_id(eid):
        return request.error_formatter(10, 'Invalid id')

    if is_track_id(eid):
        tr = g.lib.get_item(int(cid))
        if tr is None:
            return request.error_formatter(70, 'Cover art not found'), 404
        else:
            album = tr.get_album()
    else:
        album = g.lib.get_album(int(cid))
    if album is None or album.artpath is None or not os.path.isfile(
            album.artpath):
        return request.error_formatter(70, 'Cover art not found'), 404
    else:
        return send_file(album.artpath, conditional=True,
                         mimetype=mimetypes.guess_type(album.artpath)[0])


@subsonic_routes.route('/rest/download.view', methods=['GET', 'POST'])
@subsonic_routes.route('/rest/stream.view', methods=['GET', 'POST'])
def v_download():
    eid = request.args.get('id')
    cid = clean_id(eid)
    if not is_track_id(eid):
        return request.error_formatter(10, 'Invalid id')

    tr = g.lib.get_item(int(cid))

    if tr is None or tr.path is None or not os.path.isfile(tr.path):
        return request.error_formatter(70, 'Track not found'), 404
    else:
        return send_file(tr.path, conditional=True,
                         mimetype=mimetypes.guess_type(tr.path)[0])


class SubsonicPlugin(BeetsPlugin):
    def __init__(self):
        super(SubsonicPlugin, self).__init__()
        app.register_blueprint(subsonic_routes)
