# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2015, Adrian Sampson.
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


from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

from beets.plugins import BeetsPlugin
from beets import ui
import os
from beets.ui.commands import _do_query
from os.path import relpath
from beets import util
from beets.util import normpath, syspath
import codecs
import string
import re


class Txt2Playlistplugin(BeetsPlugin):

    def __init__(self):
        super(Txt2Playlistplugin, self).__init__()
        self.config.add({
            'relative_to': None,
            'use_folders': False,
            'playlist_dir': u'.',
        })

    include = set().union(string.ascii_lowercase, string.digits)

    def commands(self):
        txt2pls = ui.Subcommand('txt2pls',
                                help='saves a playlist from a textfile\
                                passed as argument.')
        txt2pls.func = self.txt2pls_cmd
        return [txt2pls]

    def cleanLineNrs(self, sourcelines):
        """if the line starts with a listnumber (ex: 10.) we remove it.
        """
        return [" ".join(line.split()[1:]) for line in sourcelines]

    def cleanLineEnd(self, sourcelines):
        """if the line ends with anything between () or [] (ex: (1967))
         we remove it
        """
        starttoken = sourcelines[0].split()[-1].split('x')[0]
        endtoken = sourcelines[0].split()[-1].split('x')[1]
        regex = re.compile(re.escape(starttoken) + '.+?' + re.escape(endtoken))
        return [re.sub(regex, "", line) if
                line.endswith(endtoken) else
                line for line in sourcelines]

    def getDelimiter(self, sourcelines):
        """if the format is ex: artist: - title: ...
         we return artist:, -, title:
         if the format contains album: we return albms=true
        """
        albms = False
        sourceFields = sourcelines[0].split()
        delimiter = sourceFields[1]
        self.include = set().union(self.include, delimiter)
        if "album:" in sourceFields:
            albms = True
        return sourceFields[0], delimiter, sourceFields[2], albms

    def txt2pls_cmd(self, lib, opts, args):
        """this reads a textfile of the following formats
        first line: contains the title of the playlist
        second line : expresses the format of the rest of the list. ex:
                x. album:  - albumartist: (x)     2. White - The Beatles (1967)
                albumartist: -- album: [x]        The Beatles -- white [1967]
                artist: * title:                  John Lennon * imagine
                where x. represents the linenumberings if the list has that.
                      (x) or [x] is anything in between brackets at the end of
                      the line
                artist:,albumartist:,title:,album: should be obvious
        all the other lines follow the format from the second line
        If no playlist_dir in config, playlist will get saved in dir of .
        """
        self.relative_to = self.config['relative_to'].get()
        self.use_folders = self.config['use_folders'].get(bool)
        self.playlist_dir = self.config['playlist_dir'].as_filename()
        albms = False
        delimiter = "-"
        for arg in args:
            path = normpath(arg)
            if os.path.isfile(syspath(path)):
                with codecs.open(path, 'r', "utf-8") as f:
                    sourcelist = f.read()
                sourcelines = sourcelist.splitlines()
                playlistname = sourcelines[0]
                sourcelines = sourcelines[1:]
                # if the line starts with x we an delete the first part
                if sourcelines[0].startswith('x'):
                    sourcelines = self.cleanLineNrs(sourcelines)
                # if the line ends with x we can delete the last part
                # if x is surrounded with()[] ... we use that to help
                if 'x' in sourcelines[0].split()[-1]:
                    sourcelines = self.cleanLineEnd(sourcelines)
                sf1, delimiter, sf2, albm = self.getDelimiter(sourcelines)
                sourcelines = [self.cleanup(line)for line in sourcelines]
                hits = []
                for line in sourcelines[1:]:
                    if delimiter not in line:
                        ui.print_(ui.colorize(
                            'text_error',
                            'NO:{} in {}. Fix source!!!'.
                            format(delimiter, line)))
                        return
                    artistOrAlbum = line.split(delimiter)
                    if artistOrAlbum:
                        artist = artistOrAlbum[0]
                        album = artistOrAlbum[1]
                        q = (sf1 + artist + " " + sf2 + album)
                        try:
                            items, albums = _do_query(lib, q, albms, False)
                            objs = albums if albms else items
                            if objs:
                                ui.print_("need:{}".format(line))
                                hits.append(objs[0])
                                ui.print_(ui.colorize(
                                    'text_success', 'got:{}'.
                                    format(format(objs[0]))))
                        except:
                            ui.print_(ui.colorize(
                                'text_error', 'miss:{}-{}'.
                                format(artist, album)))
        paths = self.get_paths(hits, albms, lib)
        self._save_playlist(playlistname, paths)

    def cleanup(self, dirty):
        """simplify the name by getting rid of some not important characters
        """
        clean = ""
        dirty = dirty.lower()
        for ch in dirty:
            if ch in self.include:
                clean += ch
            else:
                clean += " "
        return clean

    def _save_playlist(self, filename, paths):
        name = filename.replace(" ", "_") + ".m3u"
        m3ufile = util.normpath(os.path.join(self.playlist_dir, name))
        with open(m3ufile, 'w') as m3u:
            for item in paths:
                m3u.write(item + b'\n')
        self._log.info(u'Saved :{} ', m3ufile)
        return m3ufile

    def get_paths(self, objs, albies, lib):
        if albies:
            paths = []
            sort = lib.get_default_album_sort()
            for album in objs:
                if self.use_folders:
                    paths.append(album.item_dir())
                else:
                    paths.extend(item.path
                                 for item in sort.sort(album.items()))
        else:
            paths = [item.path for item in objs]
            if self.relative_to:
                paths = [relpath(path, self.relative_to) for path in paths]
        return paths
