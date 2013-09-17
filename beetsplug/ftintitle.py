# This file is part of beets.
# Copyright 2013, Verrus, <github.com/Verrus/beets-plugin-featInTitle>
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

"""Moves "featured" artists to the title from the artist field.
"""
from beets.plugins import BeetsPlugin
from beets import ui
import re


def find_supplementary_artists(artistfield):
    return re.split(
        r'[fF]t\.|[fF]eaturing|[fF]eat\.|\b[wW]ith\b|&|vs\.|and',
        artistfield,
        1  # Only split on the first.
    )


def detect_if_featuring_artist_already_in_title(title):
    return re.split(
        r'[fF]t\.|[fF]eaturing|[fF]eat\.|\b[wW]ith\b|&',
        title
    )


def write_artist_field_only_and_print_edited_file_loc(track, albumartist,
                                                      sort_artist):
    """In the case where the featured artist is already in the title, just
    rewrite the artist fields.
    """
    print track.__getattr__("path")
    print "new artist field",albumartist.strip()
    track.artist = albumartist
    track.artist_sort = rewrite_sort_artist(sort_artist)
    track.write()


def write_artist_and_title_field_and_print_edited_file_loc(track, albumartist,
                                                           title, feat_part,
                                                           sort_artist):
    """Modify both the artist and title fields.
    """
    print track.__getattr__("path")
    print "albumartist:",albumartist," title:",title," featuartist:",feat_part
    track.artist = albumartist
    track.artist_sort = rewrite_sort_artist(sort_artist)
    track.title = title.strip() + " feat." + feat_part
    track.write()


def choose_writing_of_title_and_write(track, albumartist, title,
                                      feat_part, sort_artist):
    """Choose how to add new artists to the title and write the new
    metadata.
    """
    # If already in title, only replace the artist field.
    if len(detect_if_featuring_artist_already_in_title(title)) > 1:
        # no replace title
        write_artist_field_only_and_print_edited_file_loc(
            track, albumartist, sort_artist
        )
    else:
        # do replace title.
        write_artist_and_title_field_and_print_edited_file_loc(
            track, albumartist, title, feat_part, sort_artist
        )


def rewrite_sort_artist(sort_artist):
    """Remove featuring artists from the artist sort field.
    """
    return find_supplementary_artists(sort_artist)[0].strip()


def ft_in_title(item):
    """Look for featured artists in the item's artist fields and move
    them to the title.
    """
    artistfield  = item.artist.strip()
    title = item.title.strip()
    albumartist = item.albumartist.strip()
    sort_artist = item.artist_sort.strip()
    supp_artists = find_supplementary_artists(artistfield)

    if len(supp_artists) > 1 and albumartist != artistfield:
        # Found supplementary artist, and the albumArtist is
        # not a perfect match.

        albumartist_split = artistfield.split(albumartist)
        if len(albumartist_split) > 1 and albumartist_split[-1] != '':
            # Check if the artist field is composed of the
            # albumartist, AND check if the last element of
            # the split is not empty.
            # Last elements:
            feat_part = find_supplementary_artists(albumartist_split[-1])[-1]
            choose_writing_of_title_and_write(item, albumartist, title,
                                              feat_part, sort_artist)

        elif len(albumartist_split) > 1 and \
                len(find_supplementary_artists(albumartist_split[0])) > 1:
            # Check for inversion of artist and featuring,
            # if feat is listed on the first split.
            # First elements because of inversion:
            feat_part = find_supplementary_artists(albumartist_split[0])[0]
            choose_writing_of_title_and_write(item, albumartist, title,
                                              feat_part, sort_artist)

        else:
            print "#############################"
            print "ftInTitle has not touched this track, " \
                  "unsure what to do with this one.:"
            print "artistfield: ",artistfield
            print "albumArtist",albumartist
            print "titleField: ",title
            print item.__getattr__("path")
            print "#############################"


class FtInTitlePlugin(BeetsPlugin):
    def commands(self):
        cmd = ui.Subcommand('ftintitle',
                            help='move featured artists to the title field')
        def func(lib, opts, args):
            for item in lib.items():
                ft_in_title(item)
            print "Manual 'beet update' run is recommended. "
        cmd.func = func
        return [cmd]
