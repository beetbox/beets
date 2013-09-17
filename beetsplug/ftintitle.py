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


# Helpers.

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


# Feat is already in title: only replace the artist field.
def write_artist_field_only_and_print_edited_file_loc(track, albumartist,
                                                      sort_artist):
    print track.__getattr__("path")
    print "new artist field",albumartist.strip()
    track.artist = albumartist
    track.artist_sort = rewrite_sort_artist(sort_artist)
    track.write()


# Write a new title and a new artist field.
def write_artist_and_title_field_and_print_edited_file_loc(track, albumartist,
                                                           title, feat_part,
                                                           sort_artist):
    print track.__getattr__("path")
    print "albumartist:",albumartist," title:",title," featuartist:",feat_part
    track.artist = albumartist
    track.artist_sort = rewrite_sort_artist(sort_artist)
    track.title = title.strip() + " feat." + feat_part
    track.write()


# Split the extended artistfield in the extended part and
# albumartist.
def split_on_album_artist(albumartist, artistfield):
    return re.split(albumartist, artistfield)


# Checks if title has a feat artist and calls the writing methods
# accordingly.
def choose_writing_of_title_and_write(track, albumartist, title,
                                        feat_part, sort_artist):
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


# Filter the sort artist with a regex split and strip.
def rewrite_sort_artist(sort_artist):
    return find_supplementary_artists(sort_artist)[0].strip()


class FtInTitlePlugin(BeetsPlugin):
    def commands(self):
        cmd = ui.Subcommand('ftintitle',
                            help='move featured artists to the title field')
        def func(lib, opts, args):

            for track in lib.items():
                artistfield  = track.artist.strip()
                title = track.title.strip()
                albumartist = track.albumartist.strip()
                sort_artist = track.artist_sort.strip()
                supp_artists = find_supplementary_artists(artistfield)

                if len(supp_artists) > 1 and albumartist != artistfield:
                    # Found supplementary artist, and the albumArtist is
                    # not a perfect match.

                    albumartist_split = split_on_album_artist(albumartist,
                                                              artistfield)
                    if len(albumartist_split) > 1 and \
                       albumartist_split[-1] != '':
                        # Check if the artist field is composed of the
                        # albumartist, AND check if the last element of
                        # the split is not empty.
                        feat_part = find_supplementary_artists(albumartist_split[-1])[-1] #last elements
                        choose_writing_of_title_and_write(track, albumartist,
                                                          title, feat_part,
                                                          sort_artist)

                    elif len(albumartist_split) > 1 and len(find_supplementary_artists(albumartist_split[0])) > 1:
                        # Check for inversion of artist and featuring,
                        # if feat is listed on the first split.
                        feat_part = find_supplementary_artists(albumartist_split[0])[0] #first elements because of inversion
                        choose_writing_of_title_and_write(track,albumartist,title,feat_part,sort_artist)

                    else:
                        print "#############################"
                        print "ftInTitle has not touched this track, unsure what to do with this one.:"
                        print "artistfield: ",artistfield
                        print "albumArtist",albumartist
                        print "titleField: ",title
                        print track.__getattr__("path")
                        print "#############################"

            print "Manual 'beet update' run is recommended. "
        cmd.func = func
        return [cmd]
