# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Susanna Maria Hepp http://github.com/SusannaMaria
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
from networkx.readwrite import json_graph
import json

LASTFM = pylast.LastFMNetwork(api_key=plugins.LASTFM_KEY)

PYLAST_EXCEPTIONS = (
    pylast.WSError,
    pylast.MalformedResponseError,
    pylast.NetworkError,
)

G = nx.Graph(program="https://github.com/beetbox/beets")


class SimilarityPlugin(plugins.BeetsPlugin):
    """Determine similarity of artists."""

    def __init__(self):
        """Class constructor, initialize things."""
        super(SimilarityPlugin, self).__init__()

        config['lastfm'].add({'user':     '',
                              'api_key':  plugins.LASTFM_KEY, })
        config['lastfm']['api_key'].redact = True

        self.config.add({'gexf': 'similarity.gexf',
                         'per_page': 500,
                         'retry_limit': 3,
                         'show': False,
                         'json': 'similarity.json',
                         'depth': 3, })
        self.item_types = {'play_count':  types.INTEGER, }

        self._artistsOwned = list()
        self._artistsForeign = list()
        self._relations = list()

    def commands(self):
        """Define the command of plugin and its options and arguments."""
        cmd = ui.Subcommand('similarity',
                            help=u'get similarity for artists')

        cmd.parser.add_option(
            u'-g', u'--gexf', dest='gexf',  metavar='FILE',
            action='store',
            help=u'read and write Graph as gexf-FILE.'
        )

        cmd.parser.add_option(
            u'-j', u'--json', dest='json',  metavar='FILE',
            action='store',
            help=u'write Graph as json-FILE.'
        )

        cmd.parser.add_option(
            u'-s', u'--show', dest='depth',  metavar='DEPTH',
            action='store',
            help=u'How is the depth of searching.'
        )

        cmd.parser.add_option(
            u'-d', u'--depth',

        )

        def func(lib, opts, args):

            self.config.set_args(opts)
            show = self.config['show']
            gmlfile = self.config['gexf'].as_str()
            depth = self.config['depth'].as_str()

            items = lib.items(ui.decargs(args))

            self.import_similarity(lib, items, show, gmlfile, depth)

        cmd.func = func
        return [cmd]

    def import_similarity(self, lib, items, show, gexf, depth):
        """
        Import gml-file which contains similarity.

        Edges are similarity and Nodes are artists.
        """
        if os.path.isfile(gexf) and os.access(gexf, os.R_OK):
            self._log.info(u'import of gexf file')
            self.import_graph(gexf, show)
        else:
            self._log.info(u'no gexf file found, processing last.fm query')
            # create node for each similar artist
            self.collect_artists(items)
            # create node for each similar artist
            self.get_similar(lib, depth)
            self.create_graph(gexf, show)
            self._log.info(u'Artist owned: {}', len(self._artistsOwned))
            self._log.info(u'Artist foreign: {}', len(self._artistsForeign))
            self._log.info(u'Relations: {}', len(self._relations))

    def collect_artists(self, items):
        """Collect artists from query."""
        for item in items:
            if item['mb_albumartistid']:
                artistnode = ArtistNode(item['mb_albumartistid'],
                                        item['albumartist'],
                                        True)
                artistnode['group'] = 1
                if artistnode not in self._artistsOwned:
                    self._artistsOwned.append(artistnode)

    def get_similar(self, lib, depth):
        """Collect artists from query."""
        depthcounter = 1
        while True:
            havechilds = False
            self._log.info(u'Level: {}-{}', depthcounter, depth)
            if depthcounter > int(depth):
                self._log.info(u'out!')
                break
            depthcounter += 1
            artistsshadow = list()
            for artist in self._artistsOwned:
                if not artist['checked']:
                    self._log.info(u'Artist: {}-{}', artist['mbid'],
                                   artist['name'])
                    try:
                        lastfm_artist = LASTFM.get_artist_by_mbid(
                            artist['mbid'])

                        similar_artists = lastfm_artist.get_similar(10)
                        artist['checked'] = True

                        # using nested lists
                        #       similarArtists[idx][0] - Artist object
                        #       similarArtists[idx][1] - last.fm match value
                        for artistinfo in similar_artists:
                            mbid = artistinfo[0].get_mbid()
                            name = artistinfo[0].get_name()

                            if mbid:
                                artistnode = ArtistNode(mbid, name)
                                artistnode['group'] = depthcounter
                                if len(lib.items('mb_artistid:' + mbid)) > 0:
                                    if ((artistnode not in
                                         self._artistsOwned) and
                                        (artistnode not in
                                         artistsshadow)):
                                        artistsshadow.append(artistnode)
                                        self._log.info(u'I own this: {}', name)
                                        havechilds = True
                                if artistnode not in self._artistsForeign:
                                    self._artistsForeign.append(artistnode)

                                relation = Relation(artist['mbid'],
                                                    mbid,
                                                    artistinfo[1] * 1000)

                                # if relation not in _relations:
                                self._relations.append(relation)
                    except PYLAST_EXCEPTIONS as exc:
                        self._log.debug(u'last.fm error: {0}', exc)
            self._artistsOwned.extend(artistsshadow)
            del artistsshadow[:]
            if not havechilds:
                break

    def create_graph(self, gexf, show):
        """Create graph out of collected artists and relations."""
        for relation in self._relations:
            G.add_edge(relation['source_mbid'],
                       relation['target_mbid'],
                       smbid=relation['source_mbid'],
                       tmbid=relation['target_mbid'],
                       rate=relation['rate'])
            self._log.debug(u'{}#{}', relation['source_mbid'],
                            relation['target_mbid'])

        custom_labels = {}
        for owned_artist in self._artistsOwned:
            G.add_node(owned_artist['mbid'],
                       mbid=owned_artist['mbid'],
                       group=owned_artist['group'],
                       name=owned_artist['name'])
            custom_labels[owned_artist['mbid']] = owned_artist['name']
            self._log.debug(u'#{}', owned_artist['mbid'])

        for foreign_artist in self._artistsForeign:
            if foreign_artist not in self._artistsOwned:
                custom_labels[foreign_artist['mbid']] = foreign_artist['name']
                G.add_node(foreign_artist['mbid'],
                           mbid=foreign_artist['mbid'],
                           group=foreign_artist['group'],
                           name=foreign_artist['name'])
                self._log.debug(u'#{}', foreign_artist['mbid'])

        h = nx.relabel_nodes(G, custom_labels)
        if show:
            nx.draw(G, labels=custom_labels)
            plt.show()
        nx.write_gexf(h, gexf)
        data = json_graph.node_link_data(h)

        with open('result.json', 'w') as fp:
            json.dump(data, fp)

    def import_graph(self, gexf, show):
        """Import graph from previous created gml file."""
        # i = nx.read_gml(gmlfile, label='label')
        i = nx.read_gexf(gexf, None, relabel=True)
        for artist in i.nodes(data=True):
            self._log.debug(u'{}', artist)
            artistnode = ArtistNode(artist[1]['mbid'], artist[0])
            if artist[1]['group'] == 1:
                if artistnode not in self._artistsOwned:
                    self._artistsOwned.append(artistnode)
            else:
                if artistnode not in self._artistsForeign:
                    self._artistsForeign.append(artistnode)
        for relitem in i.edges(data=True):
            relation = Relation(relitem[2]['smbid'],
                                relitem[2]['tmbid'],
                                relitem[2]['rate'])
            self._relations.append(relation)

        if show:
            nx.draw_networkx(i)
            plt.show()

        data = json_graph.node_link_data(i)

        with open('result.json', 'w') as fp:
            json.dump(data, fp)


class Relation():
    """Relations between Artists."""

    def __init__(self, source_mbid, target_mbid, rate):
        """Constructor of class."""
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
        """Define a getitem function."""
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
    checked = False
    group = 0

    def __init__(self, mbid, name, owned=False, checked=False, group=0):
        """Constructor of class."""
        self.mbid = mbid
        self.name = name
        self.owned = owned
        self.checked = checked
        self.group = group

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
        """Define a getitem function."""
        if key == 'mbid':
            return self.mbid
        elif key == 'name':
            return self.name
        elif key == 'owned':
            return self.owned
        elif key == 'owned':
            return self.owned
        elif key == 'checked':
            return self.checked
        elif key == 'group':
            return self.group
        else:
            return None

    def __setitem__(self, key, value):
        """Define a setitem function."""
        if key == 'mbid':
            self.mbid = value
        elif key == 'name':
            self.name = value
        elif key == 'owned':
            self.owned = value
        elif key == 'owned':
            self.owned = value
        elif key == 'checked':
            self.checked = value
        elif key == 'group':
            self.group = value
