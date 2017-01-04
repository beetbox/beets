# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Rafael Bodill http://github.com/rafi
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

from __future__ import division, absolute_import, print_function

import pylast
from beets import ui
from beets import config
from beets import plugins
from beets.dbcore import types

import networkx as nx
import matplotlib.pyplot as plt

_artistsOwned = list()
_artistsForeign = list()
_relations = list()

LASTFM = pylast.LastFMNetwork(api_key=plugins.LASTFM_KEY)

PYLAST_EXCEPTIONS = (
    pylast.WSError,
    pylast.MalformedResponseError,
    pylast.NetworkError,
)

REPLACE = {
    u'\u2010': '-',
}

G = nx.Graph(day="Friday")


class SimilarityPlugin(plugins.BeetsPlugin):
    """List duplicate tracks or albums."""

    def __init__(self):
        """List duplicate tracks or albums."""
        super(SimilarityPlugin, self).__init__()

        config['lastfm'].add({'user':     '',
                              'api_key':  plugins.LASTFM_KEY, })
        config['lastfm']['api_key'].redact = True
        self.config.add({
                        'per_page': 500,
                        'retry_limit': 3,
                        })
        self.item_types = {'play_count':  types.INTEGER, }

    def commands(self):
        """List duplicate tracks or albums."""
        cmd = ui.Subcommand('similarity',
                            help=u'get similarity for artists')

        def func(lib, opts, args):
            self.config.set_args(opts)

            items = lib.items(ui.decargs(args))

            self.import_similarity(lib, items)

        cmd.func = func
        return [cmd]

    def import_similarity(self, lib, items):
        """List duplicate tracks or albums."""
        # create node for each similar artist
        self.collect_artists(items)
        # create node for each similar artist
        self.get_similar()
        # self.clear_foreign_artists()
        self.create_graph()
        self._log.info(u'Artist owned: {}', len(_artistsOwned))
        self._log.info(u'Artist foreign: {}', len(_artistsForeign))
        self._log.info(u'Relations: {}', len(_relations))
# get_artist_by_mbid

    def collect_artists(self, items):
        """Collect artists from query."""
        for item in items:
            if item['mb_albumartistid']:
                artistnode = ArtistNode(item['mb_albumartistid'],
                                        item['albumartist'],
                                        True)
                if artistnode not in _artistsOwned:
                    _artistsOwned.append(artistnode)

    def get_similar(self):
        """Collect artists from query."""
        for artist in _artistsOwned:
                self._log.info(u'Artist: {}-{}', artist['mbid'],
                               artist['name'])
                lastfm_artist = LASTFM.get_artist_by_mbid(artist['mbid'])

                similar_artists = lastfm_artist.get_similar(10)

                # using nested lists
                #       similarArtists[idx][0] - Artist object
                #       similarArtists[idx][1] - last.fm match value
                for artistinfo in similar_artists:
                    mbid = artistinfo[0].get_mbid()
                    name = artistinfo[0].get_name()

                    if mbid:
                        artistnode = ArtistNode(mbid, name)
                        if artistnode not in _artistsForeign:
                            _artistsForeign.append(artistnode)

                        relation = Relation(artist['mbid'],
                                            mbid,
                                            artistinfo[1])

                        # if relation not in _relations:
                        _relations.append(relation)

    def clear_foreign_artists(self):
        """Collect artists from query."""
        for owned_artist in _artistsOwned:
            for foreign_artist in _artistsForeign:
                if owned_artist['mbid'] == foreign_artist['mbid']:
                    _artistsForeign.remove(foreign_artist)
                    break

    def create_graph(self):
        """Collect artists from query."""
        for relation in _relations:
            G.add_edge(relation['source_mbid'],
                       relation['target_mbid'])
            self._log.debug(u'{}#{}', relation['source_mbid'],
                            relation['target_mbid'])

        custom_labels = {}
        for owned_artist in _artistsOwned:
            G.add_node(owned_artist['mbid'], mbid=owned_artist['mbid'])
            custom_labels[owned_artist['mbid']] = owned_artist['name']
            self._log.debug(u'#{}', owned_artist['mbid'])

        for foreign_artist in _artistsForeign:
            if foreign_artist not in _artistsOwned:
                custom_labels[foreign_artist['mbid']] = foreign_artist['name']
                G.add_node(foreign_artist['mbid'], mbid=foreign_artist['mbid'])
                self._log.debug(u'#{}', foreign_artist['mbid'])

        h = nx.relabel_nodes(G, custom_labels)

        nx.draw(G, labels=custom_labels)
        plt.show()

        nx.write_gml(h, "similar.gml")


class Relation():
    """Relations."""

    def __init__(self, source_mbid, target_mbid, rate):
        """Relations."""
        self.source_mbid = source_mbid
        self.target_mbid = target_mbid
        self.rate = rate

    def __eq__(self, other):
        """Override the default Equals behavior."""
        if isinstance(other, self.__class__):
            if (self.source_mbid == other.source_mbid and
                    self.target_mbid == other.target_mbid):
                return True
            elif (self.target_mbid == other.source_mbid and
                  self.target_mbid == other.source_mbid):
                # Since both conditions are true
                return True
            else:
                return False

    def __ne__(self, other):
        """Define a non-equality test."""
        if isinstance(other, self.__class__):
            return not self.__eq__(other)

    def __getitem__(self, key):
        """Define a non-equality test."""
        if key == 'source_mbid':
            return self.source_mbid
        elif key == 'target_mbid':
            return self.target_mbid
        elif key == 'rate':
            return self.rate
        else:
            return None


class ArtistNode():
    """Artist Nodes."""

    mbid = u''
    name = u''
    owned = False

    def __init__(self, mbid, name, owned=False):
        """Relations."""
        self.mbid = mbid
        self.name = name

    def __eq__(self, other):
        """Override the default Equals behavior."""
        if isinstance(other, self.__class__):
            return self.mbid == other.mbid
        return False

    def __ne__(self, other):
        """Define a non-equality test."""
        if isinstance(other, self.__class__):
            return not self.__eq__(other)

    def __getitem__(self, key):
        """Define a non-equality test."""
        if key == 'mbid':
            return self.mbid
        elif key == 'name':
            return self.name
        elif key == 'owned':
            return self.owned
        else:
            return None
