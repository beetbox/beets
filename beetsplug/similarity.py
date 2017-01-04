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
import os.path

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

        self.config.add({'gmlfile': 'similarity.gml',
                         'per_page': 500,
                         'retry_limit': 3,
                         'show': False, })
        self.item_types = {'play_count':  types.INTEGER, }

    def commands(self):
        """List duplicate tracks or albums."""
        cmd = ui.Subcommand('similarity',
                            help=u'get similarity for artists')

        cmd.parser.add_option(
            u'-g', u'--graphml', dest='gmlfile',  metavar='FILE',
            action='store',
            help=u'read and write Graph as gml-FILE.'
        )

        cmd.parser.add_option(
            u'-s', u'--show',
            action='store_true',
            help=u'Show graph of relations.'
        )

        def func(lib, opts, args):

            self.config.set_args(opts)
            show = self.config['show']
            gmlfile = self.config['gmlfile'].as_str()

            items = lib.items(ui.decargs(args))

            self.import_similarity(lib, items, show, gmlfile)

        cmd.func = func
        return [cmd]

    def import_similarity(self, lib, items, show, gmlfile):
        """List duplicate tracks or albums."""
        if os.path.isfile(gmlfile) and os.access(gmlfile, os.R_OK):
            self._log.info(u'import of gmlfile')
            self.import_graph(gmlfile)
        else:
            self._log.info(u'no gmlfile found, processing last.fm query')
            # create node for each similar artist
            self.collect_artists(items)
            # create node for each similar artist
            self.get_similar()
            # self.clear_foreign_artists()
            self.create_graph(gmlfile, show)
            self._log.info(u'Artist owned: {}', len(_artistsOwned))
            self._log.info(u'Artist foreign: {}', len(_artistsForeign))
            self._log.info(u'Relations: {}', len(_relations))

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
                try:
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
                except pylast.WSError:
                    pass

    def clear_foreign_artists(self):
        """Collect artists from query."""
        for owned_artist in _artistsOwned:
            for foreign_artist in _artistsForeign:
                if owned_artist['mbid'] == foreign_artist['mbid']:
                    _artistsForeign.remove(foreign_artist)
                    break

    def create_graph(self, gmlfile, show):
        """Collect artists from query."""
        for relation in _relations:
            G.add_edge(relation['source_mbid'],
                       relation['target_mbid'],
                       smbid=relation['source_mbid'],
                       tmbid=relation['target_mbid'],
                       rate=relation['rate'])
            self._log.debug(u'{}#{}', relation['source_mbid'],
                            relation['target_mbid'])

        custom_labels = {}
        for owned_artist in _artistsOwned:
            G.add_node(owned_artist['mbid'],
                       mbid=owned_artist['mbid'],
                       owned='True')
            custom_labels[owned_artist['mbid']] = owned_artist['name']
            self._log.debug(u'#{}', owned_artist['mbid'])

        for foreign_artist in _artistsForeign:
            if foreign_artist not in _artistsOwned:
                custom_labels[foreign_artist['mbid']] = foreign_artist['name']
                G.add_node(foreign_artist['mbid'],
                           mbid=foreign_artist['mbid'],
                           owned='False')
                self._log.debug(u'#{}', foreign_artist['mbid'])

        h = nx.relabel_nodes(G, custom_labels)
        if show:
            nx.draw(G, labels=custom_labels)
            plt.show()

        nx.write_gml(h, gmlfile)

    def import_graph(self, gmlfile):
        """Collect artists from query."""
        i = nx.read_gml(gmlfile, label='label')
        custom_labels = {}

        counter = 0
        for artist in i.nodes(data=True):
            self._log.debug(u'{}', artist)
            artistnode = ArtistNode(artist[1]['mbid'], artist[0])
            custom_labels[counter] = artistnode['name']
            counter += 1
            if artist[1]['owned'] == 'True':
                if artistnode not in _artistsOwned:
                    _artistsOwned.append(artistnode)
            else:
                if artistnode not in _artistsForeign:
                    _artistsForeign.append(artistnode)
        for relitem in i.edges(data=True):
            relation = Relation(relitem[2]['smbid'],
                                relitem[2]['tmbid'],
                                relitem[2]['rate'])
            _relations.append(relation)

        self._log.debug(u'{}', custom_labels)

        nx.draw_networkx(i)
        plt.show()


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
