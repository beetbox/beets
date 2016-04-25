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

"""This module provides the default commands for beets' command-line
interface.
"""

from __future__ import division, absolute_import, print_function

import os
import re
from collections import namedtuple, Counter
from itertools import chain

import beets
from beets import ui
from beets.ui import print_, input_, decargs, show_path_changes
from beets import autotag
from beets.autotag import Recommendation
from beets.autotag import hooks
from beets import plugins
from beets import importer
from beets import util
from beets.util import syspath, normpath, ancestry, displayable_path
from beets import library
from beets import config
from beets import logging
from beets.util.confit import _package_path

VARIOUS_ARTISTS = u'Various Artists'
PromptChoice = namedtuple('ExtraChoice', ['short', 'long', 'callback'])

# Global logger.
log = logging.getLogger('beets')

# The list of default subcommands. This is populated with Subcommand
# objects that can be fed to a SubcommandsOptionParser.
default_commands = []


# Utilities.

def _do_query(lib, query, album, also_items=True):
    """For commands that operate on matched items, performs a query
    and returns a list of matching items and a list of matching
    albums. (The latter is only nonempty when album is True.) Raises
    a UserError if no items match. also_items controls whether, when
    fetching albums, the associated items should be fetched also.
    """
    if album:
        albums = list(lib.albums(query))
        items = []
        if also_items:
            for al in albums:
                items += al.items()

    else:
        albums = []
        items = list(lib.items(query))

    if album and not albums:
        raise ui.UserError(u'No matching albums found.')
    elif not album and not items:
        raise ui.UserError(u'No matching items found.')

    return items, albums


# fields: Shows a list of available fields for queries and format strings.

def _print_keys(query):
    """Given a SQLite query result, print the `key` field of each
    returned row, with identation of 2 spaces.
    """
    for row in query:
        print_(' ' * 2 + row[b'key'])


def fields_func(lib, opts, args):
    def _print_rows(names):
        names.sort()
        print_("  " + "\n  ".join(names))

    print_(u"Item fields:")
    _print_rows(library.Item.all_keys())

    print_(u"Album fields:")
    _print_rows(library.Album.all_keys())

    with lib.transaction() as tx:
        # The SQL uses the DISTINCT to get unique values from the query
        unique_fields = 'SELECT DISTINCT key FROM (%s)'

        print_(u"Item flexible attributes:")
        _print_keys(tx.query(unique_fields % library.Item._flex_table))

        print_(u"Album flexible attributes:")
        _print_keys(tx.query(unique_fields % library.Album._flex_table))

fields_cmd = ui.Subcommand(
    'fields',
    help=u'show fields available for queries and format strings'
)
fields_cmd.func = fields_func
default_commands.append(fields_cmd)


# help: Print help text for commands

class HelpCommand(ui.Subcommand):

    def __init__(self):
        super(HelpCommand, self).__init__(
            'help', aliases=('?',),
            help=u'give detailed help on a specific sub-command',
        )

    def func(self, lib, opts, args):
        if args:
            cmdname = args[0]
            helpcommand = self.root_parser._subcommand_for_name(cmdname)
            if not helpcommand:
                raise ui.UserError(u"unknown command '{0}'".format(cmdname))
            helpcommand.print_help()
        else:
            self.root_parser.print_help()


default_commands.append(HelpCommand())


# import: Autotagger and importer.

# Importer utilities and support.

def disambig_string(info):
    """Generate a string for an AlbumInfo or TrackInfo object that
    provides context that helps disambiguate similar-looking albums and
    tracks.
    """
    disambig = []
    if info.data_source and info.data_source != 'MusicBrainz':
        disambig.append(info.data_source)

    if isinstance(info, hooks.AlbumInfo):
        if info.media:
            if info.mediums > 1:
                disambig.append(u'{0}x{1}'.format(
                    info.mediums, info.media
                ))
            else:
                disambig.append(info.media)
        if info.year:
            disambig.append(unicode(info.year))
        if info.country:
            disambig.append(info.country)
        if info.label:
            disambig.append(info.label)
        if info.albumdisambig:
            disambig.append(info.albumdisambig)

    if disambig:
        return u', '.join(disambig)


def dist_string(dist):
    """Formats a distance (a float) as a colorized similarity percentage
    string.
    """
    out = u'%.1f%%' % ((1 - dist) * 100)
    if dist <= config['match']['strong_rec_thresh'].as_number():
        out = ui.colorize('text_success', out)
    elif dist <= config['match']['medium_rec_thresh'].as_number():
        out = ui.colorize('text_warning', out)
    else:
        out = ui.colorize('text_error', out)
    return out


def penalty_string(distance, limit=None):
    """Returns a colorized string that indicates all the penalties
    applied to a distance object.
    """
    penalties = []
    for key in distance.keys():
        key = key.replace('album_', '')
        key = key.replace('track_', '')
        key = key.replace('_', ' ')
        penalties.append(key)
    if penalties:
        if limit and len(penalties) > limit:
            penalties = penalties[:limit] + ['...']
        return ui.colorize('text_warning', u'(%s)' % ', '.join(penalties))


def show_change(cur_artist, cur_album, match):
    """Print out a representation of the changes that will be made if an
    album's tags are changed according to `match`, which must be an AlbumMatch
    object.
    """
    def show_album(artist, album):
        if artist:
            album_description = u'    %s - %s' % (artist, album)
        elif album:
            album_description = u'    %s' % album
        else:
            album_description = u'    (unknown album)'
        print_(album_description)

    def format_index(track_info):
        """Return a string representing the track index of the given
        TrackInfo or Item object.
        """
        if isinstance(track_info, hooks.TrackInfo):
            index = track_info.index
            medium_index = track_info.medium_index
            medium = track_info.medium
            mediums = match.info.mediums
        else:
            index = medium_index = track_info.track
            medium = track_info.disc
            mediums = track_info.disctotal
        if config['per_disc_numbering']:
            if mediums > 1:
                return u'{0}-{1}'.format(medium, medium_index)
            else:
                return unicode(medium_index)
        else:
            return unicode(index)

    # Identify the album in question.
    if cur_artist != match.info.artist or \
            (cur_album != match.info.album and
             match.info.album != VARIOUS_ARTISTS):
        artist_l, artist_r = cur_artist or '', match.info.artist
        album_l,  album_r = cur_album or '', match.info.album
        if artist_r == VARIOUS_ARTISTS:
            # Hide artists for VA releases.
            artist_l, artist_r = u'', u''

        artist_l, artist_r = ui.colordiff(artist_l, artist_r)
        album_l, album_r = ui.colordiff(album_l, album_r)

        print_(u"Correcting tags from:")
        show_album(artist_l, album_l)
        print_(u"To:")
        show_album(artist_r, album_r)
    else:
        print_(u"Tagging:\n    {0.artist} - {0.album}".format(match.info))

    # Data URL.
    if match.info.data_url:
        print_(u'URL:\n    %s' % match.info.data_url)

    # Info line.
    info = []
    # Similarity.
    info.append(u'(Similarity: %s)' % dist_string(match.distance))
    # Penalties.
    penalties = penalty_string(match.distance)
    if penalties:
        info.append(penalties)
    # Disambiguation.
    disambig = disambig_string(match.info)
    if disambig:
        info.append(ui.colorize('text_highlight_minor', u'(%s)' % disambig))
    print_(' '.join(info))

    # Tracks.
    pairs = match.mapping.items()
    pairs.sort(key=lambda (_, track_info): track_info.index)

    # Build up LHS and RHS for track difference display. The `lines` list
    # contains ``(lhs, rhs, width)`` tuples where `width` is the length (in
    # characters) of the uncolorized LHS.
    lines = []
    medium = disctitle = None
    for item, track_info in pairs:

        # Medium number and title.
        if medium != track_info.medium or disctitle != track_info.disctitle:
            media = match.info.media or 'Media'
            if match.info.mediums > 1 and track_info.disctitle:
                lhs = u'%s %s: %s' % (media, track_info.medium,
                                      track_info.disctitle)
            elif match.info.mediums > 1:
                lhs = u'%s %s' % (media, track_info.medium)
            elif track_info.disctitle:
                lhs = u'%s: %s' % (media, track_info.disctitle)
            else:
                lhs = None
            if lhs:
                lines.append((lhs, u'', 0))
            medium, disctitle = track_info.medium, track_info.disctitle

        # Titles.
        new_title = track_info.title
        if not item.title.strip():
            # If there's no title, we use the filename.
            cur_title = displayable_path(os.path.basename(item.path))
            lhs, rhs = cur_title, new_title
        else:
            cur_title = item.title.strip()
            lhs, rhs = ui.colordiff(cur_title, new_title)
        lhs_width = len(cur_title)

        # Track number change.
        cur_track, new_track = format_index(item), format_index(track_info)
        if cur_track != new_track:
            if item.track in (track_info.index, track_info.medium_index):
                color = 'text_highlight_minor'
            else:
                color = 'text_highlight'
            templ = ui.colorize(color, u' (#{0})')
            lhs += templ.format(cur_track)
            rhs += templ.format(new_track)
            lhs_width += len(cur_track) + 4

        # Length change.
        if item.length and track_info.length and \
                abs(item.length - track_info.length) > \
                config['ui']['length_diff_thresh'].as_number():
            cur_length = ui.human_seconds_short(item.length)
            new_length = ui.human_seconds_short(track_info.length)
            templ = ui.colorize('text_highlight', u' ({0})')
            lhs += templ.format(cur_length)
            rhs += templ.format(new_length)
            lhs_width += len(cur_length) + 3

        # Penalties.
        penalties = penalty_string(match.distance.tracks[track_info])
        if penalties:
            rhs += ' %s' % penalties

        if lhs != rhs:
            lines.append((u' * %s' % lhs, rhs, lhs_width))
        elif config['import']['detail']:
            lines.append((u' * %s' % lhs, '', lhs_width))

    # Print each track in two columns, or across two lines.
    col_width = (ui.term_width() - len(''.join([' * ', ' -> ']))) // 2
    if lines:
        max_width = max(w for _, _, w in lines)
        for lhs, rhs, lhs_width in lines:
            if not rhs:
                print_(lhs)
            elif max_width > col_width:
                print_(u'%s ->\n   %s' % (lhs, rhs))
            else:
                pad = max_width - lhs_width
                print_(u'%s%s -> %s' % (lhs, ' ' * pad, rhs))

    # Missing and unmatched tracks.
    if match.extra_tracks:
        print_(u'Missing tracks ({0}/{1} - {2:.1%}):'.format(
               len(match.extra_tracks),
               len(match.info.tracks),
               len(match.extra_tracks) / len(match.info.tracks)
               ))
    for track_info in match.extra_tracks:
        line = u' ! %s (#%s)' % (track_info.title, format_index(track_info))
        if track_info.length:
            line += u' (%s)' % ui.human_seconds_short(track_info.length)
        print_(ui.colorize('text_warning', line))
    if match.extra_items:
        print_(u'Unmatched tracks ({0}):'.format(len(match.extra_items)))
    for item in match.extra_items:
        line = u' ! %s (#%s)' % (item.title, format_index(item))
        if item.length:
            line += u' (%s)' % ui.human_seconds_short(item.length)
        print_(ui.colorize('text_warning', line))


def show_item_change(item, match):
    """Print out the change that would occur by tagging `item` with the
    metadata from `match`, a TrackMatch object.
    """
    cur_artist, new_artist = item.artist, match.info.artist
    cur_title, new_title = item.title, match.info.title

    if cur_artist != new_artist or cur_title != new_title:
        cur_artist, new_artist = ui.colordiff(cur_artist, new_artist)
        cur_title, new_title = ui.colordiff(cur_title, new_title)

        print_(u"Correcting track tags from:")
        print_(u"    %s - %s" % (cur_artist, cur_title))
        print_(u"To:")
        print_(u"    %s - %s" % (new_artist, new_title))

    else:
        print_(u"Tagging track: %s - %s" % (cur_artist, cur_title))

    # Data URL.
    if match.info.data_url:
        print_(u'URL:\n    %s' % match.info.data_url)

    # Info line.
    info = []
    # Similarity.
    info.append(u'(Similarity: %s)' % dist_string(match.distance))
    # Penalties.
    penalties = penalty_string(match.distance)
    if penalties:
        info.append(penalties)
    # Disambiguation.
    disambig = disambig_string(match.info)
    if disambig:
        info.append(ui.colorize('text_highlight_minor', u'(%s)' % disambig))
    print_(' '.join(info))


def summarize_items(items, singleton):
    """Produces a brief summary line describing a set of items. Used for
    manually resolving duplicates during import.

    `items` is a list of `Item` objects. `singleton` indicates whether
    this is an album or single-item import (if the latter, them `items`
    should only have one element).
    """
    summary_parts = []
    if not singleton:
        summary_parts.append(u"{0} items".format(len(items)))

    format_counts = {}
    for item in items:
        format_counts[item.format] = format_counts.get(item.format, 0) + 1
    if len(format_counts) == 1:
        # A single format.
        summary_parts.append(items[0].format)
    else:
        # Enumerate all the formats by decreasing frequencies:
        for fmt, count in sorted(format_counts.items(),
                                 key=lambda (f, c): (-c, f)):
            summary_parts.append('{0} {1}'.format(fmt, count))

    if items:
        average_bitrate = sum([item.bitrate for item in items]) / len(items)
        total_duration = sum([item.length for item in items])
        total_filesize = sum([item.filesize for item in items])
        summary_parts.append(u'{0}kbps'.format(int(average_bitrate / 1000)))
        summary_parts.append(ui.human_seconds_short(total_duration))
        summary_parts.append(ui.human_bytes(total_filesize))

    return u', '.join(summary_parts)


def _summary_judgment(rec):
    """Determines whether a decision should be made without even asking
    the user. This occurs in quiet mode and when an action is chosen for
    NONE recommendations. Return an action or None if the user should be
    queried. May also print to the console if a summary judgment is
    made.
    """
    if config['import']['quiet']:
        if rec == Recommendation.strong:
            return importer.action.APPLY
        else:
            action = config['import']['quiet_fallback'].as_choice({
                'skip': importer.action.SKIP,
                'asis': importer.action.ASIS,
            })

    elif rec == Recommendation.none:
        action = config['import']['none_rec_action'].as_choice({
            'skip': importer.action.SKIP,
            'asis': importer.action.ASIS,
            'ask': None,
        })

    else:
        return None

    if action == importer.action.SKIP:
        print_(u'Skipping.')
    elif action == importer.action.ASIS:
        print_(u'Importing as-is.')
    return action


def choose_candidate(candidates, singleton, rec, cur_artist=None,
                     cur_album=None, item=None, itemcount=None,
                     extra_choices=[]):
    """Given a sorted list of candidates, ask the user for a selection
    of which candidate to use. Applies to both full albums and
    singletons  (tracks). Candidates are either AlbumMatch or TrackMatch
    objects depending on `singleton`. for albums, `cur_artist`,
    `cur_album`, and `itemcount` must be provided. For singletons,
    `item` must be provided.

    `extra_choices` is a list of `PromptChoice`s, containg the choices
    appended by the plugins after receiving the `before_choose_candidate`
    event. If not empty, the choices are appended to the prompt presented
    to the user.

    Returns one of the following:
    * the result of the choice, which may be SKIP, ASIS, TRACKS, or MANUAL
    * a candidate (an AlbumMatch/TrackMatch object)
    * the short letter of a `PromptChoice` (if the user selected one of
    the `extra_choices`).
    """
    # Sanity check.
    if singleton:
        assert item is not None
    else:
        assert cur_artist is not None
        assert cur_album is not None

    # Build helper variables for extra choices.
    extra_opts = tuple(c.long for c in extra_choices)
    extra_actions = tuple(c.short for c in extra_choices)

    # Zero candidates.
    if not candidates:
        if singleton:
            print_(u"No matching recordings found.")
            opts = (u'Use as-is', u'Skip', u'Enter search', u'enter Id',
                    u'aBort')
        else:
            print_(u"No matching release found for {0} tracks."
                   .format(itemcount))
            print_(u'For help, see: '
                   u'http://beets.readthedocs.org/en/latest/faq.html#nomatch')
            opts = (u'Use as-is', u'as Tracks', u'Group albums', u'Skip',
                    u'Enter search', u'enter Id', u'aBort')
        sel = ui.input_options(opts + extra_opts)
        if sel == u'u':
            return importer.action.ASIS
        elif sel == u't':
            assert not singleton
            return importer.action.TRACKS
        elif sel == u'e':
            return importer.action.MANUAL
        elif sel == u's':
            return importer.action.SKIP
        elif sel == u'b':
            raise importer.ImportAbort()
        elif sel == u'i':
            return importer.action.MANUAL_ID
        elif sel == u'g':
            return importer.action.ALBUMS
        elif sel in extra_actions:
            return sel
        else:
            assert False

    # Is the change good enough?
    bypass_candidates = False
    if rec != Recommendation.none:
        match = candidates[0]
        bypass_candidates = True

    while True:
        # Display and choose from candidates.
        require = rec <= Recommendation.low

        if not bypass_candidates:
            # Display list of candidates.
            print_(u'Finding tags for {0} "{1} - {2}".'.format(
                u'track' if singleton else u'album',
                item.artist if singleton else cur_artist,
                item.title if singleton else cur_album,
            ))

            print_(u'Candidates:')
            for i, match in enumerate(candidates):
                # Index, metadata, and distance.
                line = [
                    u'{0}.'.format(i + 1),
                    u'{0} - {1}'.format(
                        match.info.artist,
                        match.info.title if singleton else match.info.album,
                    ),
                    u'({0})'.format(dist_string(match.distance)),
                ]

                # Penalties.
                penalties = penalty_string(match.distance, 3)
                if penalties:
                    line.append(penalties)

                # Disambiguation
                disambig = disambig_string(match.info)
                if disambig:
                    line.append(ui.colorize('text_highlight_minor',
                                            u'(%s)' % disambig))

                print_(u' '.join(line))

            # Ask the user for a choice.
            if singleton:
                opts = (u'Skip', u'Use as-is', u'Enter search', u'enter Id',
                        u'aBort')
            else:
                opts = (u'Skip', u'Use as-is', u'as Tracks', u'Group albums',
                        u'Enter search', u'enter Id', u'aBort')
            sel = ui.input_options(opts + extra_opts,
                                   numrange=(1, len(candidates)))
            if sel == u's':
                return importer.action.SKIP
            elif sel == u'u':
                return importer.action.ASIS
            elif sel == u'm':
                pass
            elif sel == u'e':
                return importer.action.MANUAL
            elif sel == u't':
                assert not singleton
                return importer.action.TRACKS
            elif sel == u'b':
                raise importer.ImportAbort()
            elif sel == u'i':
                return importer.action.MANUAL_ID
            elif sel == u'g':
                return importer.action.ALBUMS
            elif sel in extra_actions:
                return sel
            else:  # Numerical selection.
                match = candidates[sel - 1]
                if sel != 1:
                    # When choosing anything but the first match,
                    # disable the default action.
                    require = True
        bypass_candidates = False

        # Show what we're about to do.
        if singleton:
            show_item_change(item, match)
        else:
            show_change(cur_artist, cur_album, match)

        # Exact match => tag automatically if we're not in timid mode.
        if rec == Recommendation.strong and not config['import']['timid']:
            return match

        # Ask for confirmation.
        if singleton:
            opts = (u'Apply', u'More candidates', u'Skip', u'Use as-is',
                    u'Enter search', u'enter Id', u'aBort')
        else:
            opts = (u'Apply', u'More candidates', u'Skip', u'Use as-is',
                    u'as Tracks', u'Group albums', u'Enter search',
                    u'enter Id', u'aBort')
        default = config['import']['default_action'].as_choice({
            u'apply': u'a',
            u'skip': u's',
            u'asis': u'u',
            u'none': None,
        })
        if default is None:
            require = True
        sel = ui.input_options(opts + extra_opts, require=require,
                               default=default)
        if sel == u'a':
            return match
        elif sel == u'g':
            return importer.action.ALBUMS
        elif sel == u's':
            return importer.action.SKIP
        elif sel == u'u':
            return importer.action.ASIS
        elif sel == u't':
            assert not singleton
            return importer.action.TRACKS
        elif sel == u'e':
            return importer.action.MANUAL
        elif sel == u'b':
            raise importer.ImportAbort()
        elif sel == u'i':
            return importer.action.MANUAL_ID
        elif sel in extra_actions:
            return sel


def manual_search(singleton):
    """Input either an artist and album (for full albums) or artist and
    track name (for singletons) for manual search.
    """
    artist = input_(u'Artist:')
    name = input_(u'Track:' if singleton else u'Album:')
    return artist.strip(), name.strip()


def manual_id(singleton):
    """Input an ID, either for an album ("release") or a track ("recording").
    """
    prompt = u'Enter {0} ID:'.format(u'recording' if singleton else u'release')
    return input_(prompt).strip()


class TerminalImportSession(importer.ImportSession):
    """An import session that runs in a terminal.
    """
    def choose_match(self, task):
        """Given an initial autotagging of items, go through an interactive
        dance with the user to ask for a choice of metadata. Returns an
        AlbumMatch object, ASIS, or SKIP.
        """
        # Show what we're tagging.
        print_()
        print_(displayable_path(task.paths, u'\n') +
               u' ({0} items)'.format(len(task.items)))

        # Take immediate action if appropriate.
        action = _summary_judgment(task.rec)
        if action == importer.action.APPLY:
            match = task.candidates[0]
            show_change(task.cur_artist, task.cur_album, match)
            return match
        elif action is not None:
            return action

        # Loop until we have a choice.
        candidates, rec = task.candidates, task.rec
        while True:
            # Gather extra choices from plugins.
            extra_choices = self._get_plugin_choices(task)
            extra_ops = {c.short: c.callback for c in extra_choices}

            # Ask for a choice from the user.
            choice = choose_candidate(
                candidates, False, rec, task.cur_artist, task.cur_album,
                itemcount=len(task.items), extra_choices=extra_choices
            )

            # Choose which tags to use.
            if choice in (importer.action.SKIP, importer.action.ASIS,
                          importer.action.TRACKS, importer.action.ALBUMS):
                # Pass selection to main control flow.
                return choice
            elif choice is importer.action.MANUAL:
                # Try again with manual search terms.
                search_artist, search_album = manual_search(False)
                _, _, candidates, rec = autotag.tag_album(
                    task.items, search_artist, search_album
                )
            elif choice is importer.action.MANUAL_ID:
                # Try a manually-entered ID.
                search_id = manual_id(False)
                if search_id:
                    _, _, candidates, rec = autotag.tag_album(
                        task.items, search_ids=search_id.split()
                    )
            elif choice in extra_ops.keys():
                # Allow extra ops to automatically set the post-choice.
                post_choice = extra_ops[choice](self, task)
                if isinstance(post_choice, importer.action):
                    # MANUAL and MANUAL_ID have no effect, even if returned.
                    return post_choice
            else:
                # We have a candidate! Finish tagging. Here, choice is an
                # AlbumMatch object.
                assert isinstance(choice, autotag.AlbumMatch)
                return choice

    def choose_item(self, task):
        """Ask the user for a choice about tagging a single item. Returns
        either an action constant or a TrackMatch object.
        """
        print_()
        print_(task.item.path)
        candidates, rec = task.candidates, task.rec

        # Take immediate action if appropriate.
        action = _summary_judgment(task.rec)
        if action == importer.action.APPLY:
            match = candidates[0]
            show_item_change(task.item, match)
            return match
        elif action is not None:
            return action

        while True:
            extra_choices = self._get_plugin_choices(task)
            extra_ops = {c.short: c.callback for c in extra_choices}

            # Ask for a choice.
            choice = choose_candidate(candidates, True, rec, item=task.item,
                                      extra_choices=extra_choices)

            if choice in (importer.action.SKIP, importer.action.ASIS):
                return choice
            elif choice == importer.action.TRACKS:
                assert False  # TRACKS is only legal for albums.
            elif choice == importer.action.MANUAL:
                # Continue in the loop with a new set of candidates.
                search_artist, search_title = manual_search(True)
                candidates, rec = autotag.tag_item(task.item, search_artist,
                                                   search_title)
            elif choice == importer.action.MANUAL_ID:
                # Ask for a track ID.
                search_id = manual_id(True)
                if search_id:
                    candidates, rec = autotag.tag_item(
                        task.item, search_ids=search_id.split())
            elif choice in extra_ops.keys():
                # Allow extra ops to automatically set the post-choice.
                post_choice = extra_ops[choice](self, task)
                if isinstance(post_choice, importer.action):
                    # MANUAL and MANUAL_ID have no effect, even if returned.
                    return post_choice
            else:
                # Chose a candidate.
                assert isinstance(choice, autotag.TrackMatch)
                return choice

    def resolve_duplicate(self, task, found_duplicates):
        """Decide what to do when a new album or item seems similar to one
        that's already in the library.
        """
        log.warn(u"This {0} is already in the library!",
                 (u"album" if task.is_album else u"item"))

        if config['import']['quiet']:
            # In quiet mode, don't prompt -- just skip.
            log.info(u'Skipping.')
            sel = u's'
        else:
            # Print some detail about the existing and new items so the
            # user can make an informed decision.
            for duplicate in found_duplicates:
                print_(u"Old: " + summarize_items(
                    list(duplicate.items()) if task.is_album else [duplicate],
                    not task.is_album,
                ))

            print_(u"New: " + summarize_items(
                task.imported_items(),
                not task.is_album,
            ))

            sel = ui.input_options(
                (u'Skip new', u'Keep both', u'Remove old')
            )

        if sel == u's':
            # Skip new.
            task.set_choice(importer.action.SKIP)
        elif sel == u'k':
            # Keep both. Do nothing; leave the choice intact.
            pass
        elif sel == u'r':
            # Remove old.
            task.should_remove_duplicates = True
        else:
            assert False

    def should_resume(self, path):
        return ui.input_yn(u"Import of the directory:\n{0}\n"
                           u"was interrupted. Resume (Y/n)?"
                           .format(displayable_path(path)))

    def _get_plugin_choices(self, task):
        """Get the extra choices appended to the plugins to the ui prompt.

        The `before_choose_candidate` event is sent to the plugins, with
        session and task as its parameters. Plugins are responsible for
        checking the right conditions and returning a list of `PromptChoice`s,
        which is flattened and checked for conflicts.

        If two or more choices have the same short letter, a warning is
        emitted and all but one choices are discarded, giving preference
        to the default importer choices.

        Returns a list of `PromptChoice`s.
        """
        # Send the before_choose_candidate event and flatten list.
        extra_choices = list(chain(*plugins.send('before_choose_candidate',
                                                 session=self, task=task)))
        # Take into account default options, for duplicate checking.
        all_choices = [PromptChoice(u'a', u'Apply', None),
                       PromptChoice(u's', u'Skip', None),
                       PromptChoice(u'u', u'Use as-is', None),
                       PromptChoice(u't', u'as Tracks', None),
                       PromptChoice(u'g', u'Group albums', None),
                       PromptChoice(u'e', u'Enter search', None),
                       PromptChoice(u'i', u'enter Id', None),
                       PromptChoice(u'b', u'aBort', None)] +\
            extra_choices

        short_letters = [c.short for c in all_choices]
        if len(short_letters) != len(set(short_letters)):
            # Duplicate short letter has been found.
            duplicates = [i for i, count in Counter(short_letters).items()
                          if count > 1]
            for short in duplicates:
                # Keep the first of the choices, removing the rest.
                dup_choices = [c for c in all_choices if c.short == short]
                for c in dup_choices[1:]:
                    log.warn(u"Prompt choice '{0}' removed due to conflict "
                             u"with '{1}' (short letter: '{2}')",
                             c.long, dup_choices[0].long, c.short)
                    extra_choices.remove(c)
        return extra_choices


# The import command.


def import_files(lib, paths, query):
    """Import the files in the given list of paths or matching the
    query.
    """
    # Check the user-specified directories.
    for path in paths:
        if not os.path.exists(syspath(normpath(path))):
            raise ui.UserError(u'no such file or directory: {0}'.format(
                displayable_path(path)))

    # Check parameter consistency.
    if config['import']['quiet'] and config['import']['timid']:
        raise ui.UserError(u"can't be both quiet and timid")

    # Open the log.
    if config['import']['log'].get() is not None:
        logpath = syspath(config['import']['log'].as_filename())
        try:
            loghandler = logging.FileHandler(logpath)
        except IOError:
            raise ui.UserError(u"could not open log file for writing: "
                               u"{0}".format(displayable_path(logpath)))
    else:
        loghandler = None

    # Never ask for input in quiet mode.
    if config['import']['resume'].get() == 'ask' and \
            config['import']['quiet']:
        config['import']['resume'] = False

    session = TerminalImportSession(lib, loghandler, paths, query)
    session.run()

    # Emit event.
    plugins.send('import', lib=lib, paths=paths)


def import_func(lib, opts, args):
    config['import'].set_args(opts)

    # Special case: --copy flag suppresses import_move (which would
    # otherwise take precedence).
    if opts.copy:
        config['import']['move'] = False

    if opts.library:
        query = decargs(args)
        paths = []
    else:
        query = None
        paths = args
        if not paths:
            raise ui.UserError(u'no path specified')

    import_files(lib, paths, query)


import_cmd = ui.Subcommand(
    u'import', help=u'import new music', aliases=(u'imp', u'im')
)
import_cmd.parser.add_option(
    u'-c', u'--copy', action='store_true', default=None,
    help=u"copy tracks into library directory (default)"
)
import_cmd.parser.add_option(
    u'-C', u'--nocopy', action='store_false', dest='copy',
    help=u"don't copy tracks (opposite of -c)"
)
import_cmd.parser.add_option(
    u'-w', u'--write', action='store_true', default=None,
    help=u"write new metadata to files' tags (default)"
)
import_cmd.parser.add_option(
    u'-W', u'--nowrite', action='store_false', dest='write',
    help=u"don't write metadata (opposite of -w)"
)
import_cmd.parser.add_option(
    u'-a', u'--autotag', action='store_true', dest='autotag',
    help=u"infer tags for imported files (default)"
)
import_cmd.parser.add_option(
    u'-A', u'--noautotag', action='store_false', dest='autotag',
    help=u"don't infer tags for imported files (opposite of -a)"
)
import_cmd.parser.add_option(
    u'-p', u'--resume', action='store_true', default=None,
    help=u"resume importing if interrupted"
)
import_cmd.parser.add_option(
    u'-P', u'--noresume', action='store_false', dest='resume',
    help=u"do not try to resume importing"
)
import_cmd.parser.add_option(
    u'-q', u'--quiet', action='store_true', dest='quiet',
    help=u"never prompt for input: skip albums instead"
)
import_cmd.parser.add_option(
    u'-l', u'--log', dest='log',
    help=u'file to log untaggable albums for later review'
)
import_cmd.parser.add_option(
    u'-s', u'--singletons', action='store_true',
    help=u'import individual tracks instead of full albums'
)
import_cmd.parser.add_option(
    u'-t', u'--timid', dest='timid', action='store_true',
    help=u'always confirm all actions'
)
import_cmd.parser.add_option(
    u'-L', u'--library', dest='library', action='store_true',
    help=u'retag items matching a query'
)
import_cmd.parser.add_option(
    u'-i', u'--incremental', dest='incremental', action='store_true',
    help=u'skip already-imported directories'
)
import_cmd.parser.add_option(
    u'-I', u'--noincremental', dest='incremental', action='store_false',
    help=u'do not skip already-imported directories'
)
import_cmd.parser.add_option(
    u'--flat', dest='flat', action='store_true',
    help=u'import an entire tree as a single album'
)
import_cmd.parser.add_option(
    u'-g', u'--group-albums', dest='group_albums', action='store_true',
    help=u'group tracks in a folder into separate albums'
)
import_cmd.parser.add_option(
    u'--pretend', dest='pretend', action='store_true',
    help=u'just print the files to import'
)
import_cmd.parser.add_option(
    u'-S', u'--search-id', dest='search_ids', action='append',
    metavar='BACKEND_ID',
    help=u'restrict matching to a specific metadata backend ID'
)
import_cmd.func = import_func
default_commands.append(import_cmd)


# list: Query and show library contents.

def list_items(lib, query, album, fmt=''):
    """Print out items in lib matching query. If album, then search for
    albums instead of single items.
    """
    if album:
        for album in lib.albums(query):
            ui.print_(format(album, fmt))
    else:
        for item in lib.items(query):
            ui.print_(format(item, fmt))


def list_func(lib, opts, args):
    list_items(lib, decargs(args), opts.album)


list_cmd = ui.Subcommand(u'list', help=u'query the library', aliases=(u'ls',))
list_cmd.parser.usage += u"\n" \
    u'Example: %prog -f \'$album: $title\' artist:beatles'
list_cmd.parser.add_all_common_options()
list_cmd.func = list_func
default_commands.append(list_cmd)


# update: Update library contents according to on-disk tags.

def update_items(lib, query, album, move, pretend):
    """For all the items matched by the query, update the library to
    reflect the item's embedded tags.
    """
    with lib.transaction():
        items, _ = _do_query(lib, query, album)

        # Walk through the items and pick up their changes.
        affected_albums = set()
        for item in items:
            # Item deleted?
            if not os.path.exists(syspath(item.path)):
                ui.print_(format(item))
                ui.print_(ui.colorize('text_error', u'  deleted'))
                if not pretend:
                    item.remove(True)
                affected_albums.add(item.album_id)
                continue

            # Did the item change since last checked?
            if item.current_mtime() <= item.mtime:
                log.debug(u'skipping {0} because mtime is up to date ({1})',
                          displayable_path(item.path), item.mtime)
                continue

            # Read new data.
            try:
                item.read()
            except library.ReadError as exc:
                log.error(u'error reading {0}: {1}',
                          displayable_path(item.path), exc)
                continue

            # Special-case album artist when it matches track artist. (Hacky
            # but necessary for preserving album-level metadata for non-
            # autotagged imports.)
            if not item.albumartist:
                old_item = lib.get_item(item.id)
                if old_item.albumartist == old_item.artist == item.artist:
                    item.albumartist = old_item.albumartist
                    item._dirty.discard(u'albumartist')

            # Check for and display changes.
            changed = ui.show_model_changes(item,
                                            fields=library.Item._media_fields)

            # Save changes.
            if not pretend:
                if changed:
                    # Move the item if it's in the library.
                    if move and lib.directory in ancestry(item.path):
                        item.move()

                    item.store()
                    affected_albums.add(item.album_id)
                else:
                    # The file's mtime was different, but there were no
                    # changes to the metadata. Store the new mtime,
                    # which is set in the call to read(), so we don't
                    # check this again in the future.
                    item.store()

        # Skip album changes while pretending.
        if pretend:
            return

        # Modify affected albums to reflect changes in their items.
        for album_id in affected_albums:
            if album_id is None:  # Singletons.
                continue
            album = lib.get_album(album_id)
            if not album:  # Empty albums have already been removed.
                log.debug(u'emptied album {0}', album_id)
                continue
            first_item = album.items().get()

            # Update album structure to reflect an item in it.
            for key in library.Album.item_keys:
                album[key] = first_item[key]
            album.store()

            # Move album art (and any inconsistent items).
            if move and lib.directory in ancestry(first_item.path):
                log.debug(u'moving album {0}', album_id)
                album.move()


def update_func(lib, opts, args):
    update_items(lib, decargs(args), opts.album, ui.should_move(opts.move),
                 opts.pretend)


update_cmd = ui.Subcommand(
    u'update', help=u'update the library', aliases=(u'upd', u'up',)
)
update_cmd.parser.add_album_option()
update_cmd.parser.add_format_option()
update_cmd.parser.add_option(
    u'-m', u'--move', action='store_true', dest='move',
    help=u"move files in the library directory"
)
update_cmd.parser.add_option(
    u'-M', u'--nomove', action='store_false', dest='move',
    help=u"don't move files in library"
)
update_cmd.parser.add_option(
    u'-p', u'--pretend', action='store_true',
    help=u"show all changes but do nothing"
)
update_cmd.func = update_func
default_commands.append(update_cmd)


# remove: Remove items from library, delete files.

def remove_items(lib, query, album, delete):
    """Remove items matching query from lib. If album, then match and
    remove whole albums. If delete, also remove files from disk.
    """
    # Get the matching items.
    items, albums = _do_query(lib, query, album)

    # Prepare confirmation with user.
    print_()
    if delete:
        fmt = u'$path - $title'
        prompt = u'Really DELETE %i file%s (y/n)?' % \
                 (len(items), 's' if len(items) > 1 else '')
    else:
        fmt = ''
        prompt = u'Really remove %i item%s from the library (y/n)?' % \
                 (len(items), 's' if len(items) > 1 else '')

    # Show all the items.
    for item in items:
        ui.print_(format(item, fmt))

    # Confirm with user.
    if not ui.input_yn(prompt, True):
        return

    # Remove (and possibly delete) items.
    with lib.transaction():
        for obj in (albums if album else items):
            obj.remove(delete)


def remove_func(lib, opts, args):
    remove_items(lib, decargs(args), opts.album, opts.delete)


remove_cmd = ui.Subcommand(
    u'remove', help=u'remove matching items from the library', aliases=(u'rm',)
)
remove_cmd.parser.add_option(
    u"-d", u"--delete", action="store_true",
    help=u"also remove files from disk"
)
remove_cmd.parser.add_album_option()
remove_cmd.func = remove_func
default_commands.append(remove_cmd)


# stats: Show library/query statistics.

def show_stats(lib, query, exact):
    """Shows some statistics about the matched items."""
    items = lib.items(query)

    total_size = 0
    total_time = 0.0
    total_items = 0
    artists = set()
    albums = set()
    album_artists = set()

    for item in items:
        if exact:
            try:
                total_size += os.path.getsize(syspath(item.path))
            except OSError as exc:
                log.info(u'could not get size of {}: {}', item.path, exc)
        else:
            total_size += int(item.length * item.bitrate / 8)
        total_time += item.length
        total_items += 1
        artists.add(item.artist)
        album_artists.add(item.albumartist)
        if item.album_id:
            albums.add(item.album_id)

    size_str = u'' + ui.human_bytes(total_size)
    if exact:
        size_str += u' ({0} bytes)'.format(total_size)

    print_(u"""Tracks: {0}
Total time: {1}{2}
{3}: {4}
Artists: {5}
Albums: {6}
Album artists: {7}""".format(
        total_items,
        ui.human_seconds(total_time),
        u' ({0:.2f} seconds)'.format(total_time) if exact else '',
        u'Total size' if exact else u'Approximate total size',
        size_str,
        len(artists),
        len(albums),
        len(album_artists)),
    )


def stats_func(lib, opts, args):
    show_stats(lib, decargs(args), opts.exact)


stats_cmd = ui.Subcommand(
    u'stats', help=u'show statistics about the library or a query'
)
stats_cmd.parser.add_option(
    u'-e', u'--exact', action='store_true',
    help=u'exact size and time'
)
stats_cmd.func = stats_func
default_commands.append(stats_cmd)


# version: Show current beets version.

def show_version(lib, opts, args):
    print_(u'beets version %s' % beets.__version__)
    # Show plugins.
    names = sorted(p.name for p in plugins.find_plugins())
    if names:
        print_(u'plugins:', ', '.join(names))
    else:
        print_(u'no plugins loaded')


version_cmd = ui.Subcommand(
    u'version', help=u'output version information'
)
version_cmd.func = show_version
default_commands.append(version_cmd)


# modify: Declaratively change metadata.

def modify_items(lib, mods, dels, query, write, move, album, confirm):
    """Modifies matching items according to user-specified assignments and
    deletions.

    `mods` is a dictionary of field and value pairse indicating
    assignments. `dels` is a list of fields to be deleted.
    """
    # Parse key=value specifications into a dictionary.
    model_cls = library.Album if album else library.Item

    for key, value in mods.items():
        mods[key] = model_cls._parse(key, value)

    # Get the items to modify.
    items, albums = _do_query(lib, query, album, False)
    objs = albums if album else items

    # Apply changes *temporarily*, preview them, and collect modified
    # objects.
    print_(u'Modifying {0} {1}s.'
           .format(len(objs), u'album' if album else u'item'))
    changed = set()
    for obj in objs:
        if print_and_modify(obj, mods, dels):
            changed.add(obj)

    # Still something to do?
    if not changed:
        print_(u'No changes to make.')
        return

    # Confirm action.
    if confirm:
        if write and move:
            extra = u', move and write tags'
        elif write:
            extra = u' and write tags'
        elif move:
            extra = u' and move'
        else:
            extra = u''

        changed = ui.input_select_objects(
            u'Really modify%s' % extra, changed,
            lambda o: print_and_modify(o, mods, dels)
        )

    # Apply changes to database and files
    with lib.transaction():
        for obj in changed:
            obj.try_sync(write, move)


def print_and_modify(obj, mods, dels):
    """Print the modifications to an item and return a bool indicating
    whether any changes were made.

    `mods` is a dictionary of fields and values to update on the object;
    `dels` is a sequence of fields to delete.
    """
    obj.update(mods)
    for field in dels:
        try:
            del obj[field]
        except KeyError:
            pass
    return ui.show_model_changes(obj)


def modify_parse_args(args):
    """Split the arguments for the modify subcommand into query parts,
    assignments (field=value), and deletions (field!).  Returns the result as
    a three-tuple in that order.
    """
    mods = {}
    dels = []
    query = []
    for arg in args:
        if arg.endswith('!') and '=' not in arg and ':' not in arg:
            dels.append(arg[:-1])  # Strip trailing !.
        elif '=' in arg and ':' not in arg.split('=', 1)[0]:
            key, val = arg.split('=', 1)
            mods[key] = val
        else:
            query.append(arg)
    return query, mods, dels


def modify_func(lib, opts, args):
    query, mods, dels = modify_parse_args(decargs(args))
    if not mods and not dels:
        raise ui.UserError(u'no modifications specified')
    modify_items(lib, mods, dels, query, ui.should_write(opts.write),
                 ui.should_move(opts.move), opts.album, not opts.yes)


modify_cmd = ui.Subcommand(
    u'modify', help=u'change metadata fields', aliases=(u'mod',)
)
modify_cmd.parser.add_option(
    u'-m', u'--move', action='store_true', dest='move',
    help=u"move files in the library directory"
)
modify_cmd.parser.add_option(
    u'-M', u'--nomove', action='store_false', dest='move',
    help=u"don't move files in library"
)
modify_cmd.parser.add_option(
    u'-w', u'--write', action='store_true', default=None,
    help=u"write new metadata to files' tags (default)"
)
modify_cmd.parser.add_option(
    u'-W', u'--nowrite', action='store_false', dest='write',
    help=u"don't write metadata (opposite of -w)"
)
modify_cmd.parser.add_album_option()
modify_cmd.parser.add_format_option(target='item')
modify_cmd.parser.add_option(
    u'-y', u'--yes', action='store_true',
    help=u'skip confirmation'
)
modify_cmd.func = modify_func
default_commands.append(modify_cmd)


# move: Move/copy files to the library or a new base directory.

def move_items(lib, dest, query, copy, album, pretend, confirm=False):
    """Moves or copies items to a new base directory, given by dest. If
    dest is None, then the library's base directory is used, making the
    command "consolidate" files.
    """
    items, albums = _do_query(lib, query, album, False)
    objs = albums if album else items

    # Filter out files that don't need to be moved.
    isitemmoved = lambda item: item.path != item.destination(basedir=dest)
    isalbummoved = lambda album: any(isitemmoved(i) for i in album.items())
    objs = [o for o in objs if (isalbummoved if album else isitemmoved)(o)]

    action = u'Copying' if copy else u'Moving'
    act = u'copy' if copy else u'move'
    entity = u'album' if album else u'item'
    log.info(u'{0} {1} {2}{3}.', action, len(objs), entity,
             u's' if len(objs) != 1 else u'')
    if not objs:
        return

    if pretend:
        if album:
            show_path_changes([(item.path, item.destination(basedir=dest))
                               for obj in objs for item in obj.items()])
        else:
            show_path_changes([(obj.path, obj.destination(basedir=dest))
                               for obj in objs])
    else:
        if confirm:
            objs = ui.input_select_objects(
                u'Really %s' % act, objs,
                lambda o: show_path_changes(
                    [(o.path, o.destination(basedir=dest))]))

        for obj in objs:
            log.debug(u'moving: {0}', util.displayable_path(obj.path))

            obj.move(copy, basedir=dest)
            obj.store()


def move_func(lib, opts, args):
    dest = opts.dest
    if dest is not None:
        dest = normpath(dest)
        if not os.path.isdir(dest):
            raise ui.UserError(u'no such directory: %s' % dest)

    move_items(lib, dest, decargs(args), opts.copy, opts.album, opts.pretend,
               opts.timid)


move_cmd = ui.Subcommand(
    u'move', help=u'move or copy items', aliases=(u'mv',)
)
move_cmd.parser.add_option(
    u'-d', u'--dest', metavar='DIR', dest='dest',
    help=u'destination directory'
)
move_cmd.parser.add_option(
    u'-c', u'--copy', default=False, action='store_true',
    help=u'copy instead of moving'
)
move_cmd.parser.add_option(
    u'-p', u'--pretend', default=False, action='store_true',
    help=u'show how files would be moved, but don\'t touch anything'
)
move_cmd.parser.add_option(
    u'-t', u'--timid', dest='timid', action='store_true',
    help=u'always confirm all actions'
)
move_cmd.parser.add_album_option()
move_cmd.func = move_func
default_commands.append(move_cmd)


# write: Write tags into files.

def write_items(lib, query, pretend, force):
    """Write tag information from the database to the respective files
    in the filesystem.
    """
    items, albums = _do_query(lib, query, False, False)

    for item in items:
        # Item deleted?
        if not os.path.exists(syspath(item.path)):
            log.info(u'missing file: {0}', util.displayable_path(item.path))
            continue

        # Get an Item object reflecting the "clean" (on-disk) state.
        try:
            clean_item = library.Item.from_path(item.path)
        except library.ReadError as exc:
            log.error(u'error reading {0}: {1}',
                      displayable_path(item.path), exc)
            continue

        # Check for and display changes.
        changed = ui.show_model_changes(item, clean_item,
                                        library.Item._media_tag_fields, force)
        if (changed or force) and not pretend:
            # We use `try_sync` here to keep the mtime up to date in the
            # database.
            item.try_sync(True, False)


def write_func(lib, opts, args):
    write_items(lib, decargs(args), opts.pretend, opts.force)


write_cmd = ui.Subcommand(u'write', help=u'write tag information to files')
write_cmd.parser.add_option(
    u'-p', u'--pretend', action='store_true',
    help=u"show all changes but do nothing"
)
write_cmd.parser.add_option(
    u'-f', u'--force', action='store_true',
    help=u"write tags even if the existing tags match the database"
)
write_cmd.func = write_func
default_commands.append(write_cmd)


# config: Show and edit user configuration.

def config_func(lib, opts, args):
    # Make sure lazy configuration is loaded
    config.resolve()

    # Print paths.
    if opts.paths:
        filenames = []
        for source in config.sources:
            if not opts.defaults and source.default:
                continue
            if source.filename:
                filenames.append(source.filename)

        # In case the user config file does not exist, prepend it to the
        # list.
        user_path = config.user_config_path()
        if user_path not in filenames:
            filenames.insert(0, user_path)

        for filename in filenames:
            print_(filename)

    # Open in editor.
    elif opts.edit:
        config_edit()

    # Dump configuration.
    else:
        print_(config.dump(full=opts.defaults, redact=opts.redact))


def config_edit():
    """Open a program to edit the user configuration.
    An empty config file is created if no existing config file exists.
    """
    path = config.user_config_path()
    editor = util.editor_command()
    try:
        if not os.path.isfile(path):
            open(path, 'w+').close()
        util.interactive_open([path], editor)
    except OSError as exc:
        message = u"Could not edit configuration: {0}".format(exc)
        if not editor:
            message += u". Please set the EDITOR environment variable"
        raise ui.UserError(message)

config_cmd = ui.Subcommand(u'config',
                           help=u'show or edit the user configuration')
config_cmd.parser.add_option(
    u'-p', u'--paths', action='store_true',
    help=u'show files that configuration was loaded from'
)
config_cmd.parser.add_option(
    u'-e', u'--edit', action='store_true',
    help=u'edit user configuration with $EDITOR'
)
config_cmd.parser.add_option(
    u'-d', u'--defaults', action='store_true',
    help=u'include the default configuration'
)
config_cmd.parser.add_option(
    u'-c', u'--clear', action='store_false',
    dest='redact', default=True,
    help=u'do not redact sensitive fields'
)
config_cmd.func = config_func
default_commands.append(config_cmd)


# completion: print completion script

def print_completion(*args):
    for line in completion_script(default_commands + plugins.commands()):
        print_(line, end='')
    if not any(map(os.path.isfile, BASH_COMPLETION_PATHS)):
        log.warn(u'Warning: Unable to find the bash-completion package. '
                 u'Command line completion might not work.')

BASH_COMPLETION_PATHS = map(syspath, [
    u'/etc/bash_completion',
    u'/usr/share/bash-completion/bash_completion',
    u'/usr/share/local/bash-completion/bash_completion',
    u'/opt/local/share/bash-completion/bash_completion',  # SmartOS
    u'/usr/local/etc/bash_completion',  # Homebrew
])


def completion_script(commands):
    """Yield the full completion shell script as strings.

    ``commands`` is alist of ``ui.Subcommand`` instances to generate
    completion data for.
    """
    base_script = os.path.join(_package_path('beets.ui'), 'completion_base.sh')
    with open(base_script, 'r') as base_script:
        yield base_script.read()

    options = {}
    aliases = {}
    command_names = []

    # Collect subcommands
    for cmd in commands:
        name = cmd.name
        command_names.append(name)

        for alias in cmd.aliases:
            if re.match(r'^\w+$', alias):
                aliases[alias] = name

        options[name] = {'flags': [], 'opts': []}
        for opts in cmd.parser._get_all_options()[1:]:
            if opts.action in ('store_true', 'store_false'):
                option_type = 'flags'
            else:
                option_type = 'opts'

            options[name][option_type].extend(
                opts._short_opts + opts._long_opts
            )

    # Add global options
    options['_global'] = {
        'flags': [u'-v', u'--verbose'],
        'opts': u'-l --library -c --config -d --directory -h --help'.split(
            u' ')
    }

    # Add flags common to all commands
    options['_common'] = {
        'flags': [u'-h', u'--help']
    }

    # Start generating the script
    yield u"_beet() {\n"

    # Command names
    yield u"  local commands='%s'\n" % ' '.join(command_names)
    yield u"\n"

    # Command aliases
    yield u"  local aliases='%s'\n" % ' '.join(aliases.keys())
    for alias, cmd in aliases.items():
        yield u"  local alias__%s=%s\n" % (alias, cmd)
    yield u'\n'

    # Fields
    yield u"  fields='%s'\n" % ' '.join(
        set(library.Item._fields.keys() + library.Album._fields.keys())
    )

    # Command options
    for cmd, opts in options.items():
        for option_type, option_list in opts.items():
            if option_list:
                option_list = ' '.join(option_list)
                yield u"  local %s__%s='%s'\n" % (
                    option_type, cmd, option_list)

    yield u'  _beet_dispatch\n'
    yield u'}\n'


completion_cmd = ui.Subcommand(
    'completion',
    help=u'print shell script that provides command line completion'
)
completion_cmd.func = print_completion
completion_cmd.hide = True
default_commands.append(completion_cmd)
