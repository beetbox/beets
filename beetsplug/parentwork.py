# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2017, Dorian Soergel.
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

"""Gets work title, disambiguation, parent work and its disambiguation,
composer, composer sort name and performers
"""

from __future__ import division, absolute_import, print_function

from beets import ui
from beets.plugins import BeetsPlugin

import musicbrainzngs


def work_father(mb_workid, work_date=None):
    """ This function finds the id of the father work given its id"""
    work_info = musicbrainzngs.get_work_by_id(mb_workid,
                                              includes=["work-rels",
                                                        "artist-rels"])
    if 'artist-relation-list' in work_info['work'] and work_date is None:
        for artist in work_info['work']['artist-relation-list']:
            if artist['type'] == 'composer':
                if 'end' in artist.keys():
                    work_date = artist['end']

    if 'work-relation-list' in work_info['work']:
        for work_father in work_info['work']['work-relation-list']:
            if work_father['type'] == 'parts' \
                    and work_father.get('direction') == 'backward':
                father_id = work_father['work']['id']
                return father_id, work_date
    return None, work_date


def work_parent(mb_workid):
    """This function finds the parentwork id of a work given its id. """
    work_date = None
    while True:
        (new_mb_workid, work_date) = work_father(mb_workid, work_date)
        if not new_mb_workid:
            return mb_workid, work_date
        mb_workid = new_mb_workid
    return mb_workid, work_date


def find_parentwork(mb_workid):
    """This function gives the work relationships (dict) of a parentwork
    given the id of the work"""
    parent_id, work_date = work_parent(mb_workid)
    work_info = musicbrainzngs.get_work_by_id(parent_id,
                                              includes=["artist-rels"])
    return work_info, work_date


class ParentWorkPlugin(BeetsPlugin):
    def __init__(self):
        super(ParentWorkPlugin, self).__init__()

        self.config.add({
            'auto': False,
            'force': False,
        })

        self._command = ui.Subcommand(
            'parentwork',
            help=u'Fetches parent works, composers and dates')

        self._command.parser.add_option(
            u'-f', u'--force', dest='force',
            action='store_true', default=None,
            help=u'Re-fetches all parent works')

        if self.config['auto']:
            self.import_stages = [self.imported]

    def commands(self):

        def func(lib, opts, args):
            self.config.set_args(opts)
            force_parent = self.config['force'].get(bool)
            write = ui.should_write()

            for item in lib.items(ui.decargs(args)):
                self.find_work(item, force_parent)
                item.store()
                if write:
                    item.try_write()

        self._command.func = func
        return [self._command]

    def imported(self, session, task):
        """Import hook for fetching parent works automatically.
        """
        force_parent = self.config['force'].get(bool)

        for item in task.imported_items():
            self.find_work(item, force_parent)
            item.store()

    def get_info(self, item, work_info):
        """Given the parentwork info dict, this function fetches
        parent_composer, parent_composer_sort, parentwork,
        parentwork_disambig, mb_workid and composer_ids"""

        parent_composer = []
        parent_composer_sort = []

        composer_exists = False
        if 'artist-relation-list' in work_info['work']:
            for artist in work_info['work']['artist-relation-list']:
                if artist['type'] == 'composer':
                    parent_composer.append(artist['artist']['name'])
                    parent_composer_sort.append(artist['artist']['sort-name'])
        if not composer_exists:
            self._log.info(item.artist + ' - ' + item.title)
            self._log.debug(
                "no composer, add one at https://musicbrainz.org/work/" +
                work_info['work']['id'])
        parentwork = work_info['work']['title']
        mb_parentworkid = work_info['work']['id']
        if 'disambiguation' in work_info['work']:
            parentwork_disambig = work_info['work']['disambiguation']
        else:
            parentwork_disambig.append('')
        return parentwork, mb_parentworkid, parentwork_disambig,
        parent_composer, parent_composer_sort

    def find_work(self, item, force):

        recording_id = item.mb_trackid
        try:
            item.parentwork
            hasparent = True
        except AttributeError:
            hasparent = False
        hasawork = True
        if not item.mb_workid:
            self._log.info("No work attached, recording id: " +
                           recording_id)
            self._log.info(item.artist + ' - ' + item.title)
            self._log.info("add one at https://musicbrainz.org" +
                           "/recording/" + recording_id)
            hasawork = False
        found = False

        if hasawork and (force or (not hasparent)):
            try:
                work_info, work_date = find_parentwork(item.mb_workid)
                (parentwork, mb_parentworkid, parentwork_disambig,
                 parent_composer,
                 parent_composer_sort) = self.get_info(item, work_info)
                found = True
            except musicbrainzngs.musicbrainz.WebServiceError:
                self._log.debug("Work unreachable")
                found = False
        elif parentwork:
            self._log.debug("Work already in library, not necessary fetching")
            return

        if found:
            self._log.debug("Finished searching work for: " +
                            item.artist + ' - ' + item.title)
            self._log.debug("Work fetched: " + parentwork +
                            ' - ' + u', '.join(parent_composer))
            item['parentwork'] = parentwork
            item['parentwork_disambig'] = parentwork_disambig
            item['mb_parentworkid'] = mb_parentworkid
            item['parent_composer'] = u''
            item['parent_composer'] = u', '.join(parent_composer)
            item['parent_composer_sort'] = u''
            item['parent_composer_sort'] = u', '.join(parent_composer_sort)
            if work_date:
                item['work_date'] = work_date
            ui.show_model_changes(
                item, fields=['parentwork', 'parentwork_disambig',
                              'mb_parentworkid', 'parent_composer',
                              'parent_composer_sort', 'work_date'])

            item.store()
