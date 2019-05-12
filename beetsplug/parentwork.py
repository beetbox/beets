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


def work_father(work_id, work_date=None):
    """ This function finds the id of the father work given its id"""
    work_info = musicbrainzngs.get_work_by_id(work_id,
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


def work_parent(work_id):
    """This function finds the parentwork id of a work given its id. """
    work_date = None
    while True:
        (new_work_id, work_date) = work_father(work_id, work_date)
        if not new_work_id:
            return work_id, work_date
            break
        work_id = new_work_id
    return work_id, work_date


def find_parentwork(work_id):
    """This function gives the work relationships (dict) of a parent_work
    given the id of the work"""
    parent_id, work_date = work_parent(work_id)
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

    def get_info(self, item, work_info, parent_composer, parent_composer_sort,
                 parent_work, parent_work_disambig, parent_work_id,
                 composer_ids):
        """Given the parentwork info dict, this function updates
        parent_composer, parent_composer_sort, parent_work,
        parent_work_disambig, work_ids and composer_ids"""
        composer_exists = False
        if 'artist-relation-list' in work_info['work']:
            for artist in work_info['work']['artist-relation-list']:
                if artist['type'] == 'composer':
                    composer_exists = True
                    if artist['artist']['id'] not in composer_ids:
                        composer_ids.add(artist['artist']['id'])
                        parent_composer.append(artist['artist']['name'])
                        parent_composer_sort.append(artist['artist']
                                                    ['sort-name'])
        if not composer_exists:
            self._log.info(item.artist + ' - ' + item.title)
            self._log.info(
                "no composer, add one at https://musicbrainz.org/work/" +
                work_info['work']['id'])
        if work_info['work']['id'] in parent_work_id:
            pass
        else:
            parent_work.append(work_info['work']['title'])
            parent_work_id.append(work_info['work']['id'])
            if 'disambiguation' in work_info['work']:
                parent_work_disambig.append(work_info['work']
                                            ['disambiguation'])
            else:
                parent_work_disambig.append('')

    def find_work(self, item, force):

        parent_work = []
        parent_work_disambig = []
        parent_composer = []
        parent_composer_sort = []
        parent_work_id = []
        composer_ids = set()
        work_ids = []

        recording_id = item.mb_trackid
        try:
            item.parent_work
            hasparent = True
        except AttributeError:
            hasparent = False
        hasawork = True
        if not item.work_id:
            if not item.mb_trackid:
                return
            rec_rels = musicbrainzngs.get_recording_by_id(recording_id,
                                                          includes=['work-' +
                                                                    'rels'])
            if 'work-relation-list' in rec_rels['recording']:
                for work_relation in \
                        rec_rels['recording']['work-relation-list']:
                    work_ids.append(work_relation['work']['id'])
                    hasawork = True
            else:
                self._log.info("No work attached, recording id: " +
                               recording_id)
                self._log.info(item.artist + ' - ' + item.title)
                self._log.info("add one at https://musicbrainz.org" +
                               "/recording/" + recording_id)
                hasawork = False
        else:
            work_ids = item.work_id.split(', ')
        found = False

        if (force or (not hasparent)) and hasawork:
            try:
                for w_id in work_ids:
                    work_info, work_date = find_parentwork(w_id)
                    self.get_info(item, work_info, parent_composer,
                                  parent_composer_sort, parent_work,
                                  parent_work_disambig,
                                  parent_work_id, composer_ids)
                found = True
            except musicbrainzngs.musicbrainz.WebServiceError:
                self._log.debug("Work unreachable")
                found = False
        elif parent_work:
            self._log.debug("Work already in library, not necessary fetching")
            return

        if found:
            self._log.debug("Finished searching work for: " +
                            item.artist + ' - ' + item.title)
            self._log.debug("Work fetched: " + u', '.join(parent_work) +
                            ' - ' + u', '.join(parent_composer))
            item['parent_work'] = u''
            item['parent_work'] = u', '.join(parent_work)
            if len(parent_work_disambig) > 0:
                item['parent_work_disambig'] = u''
                item['parent_work_disambig'] = u', '.join(parent_work_disambig)
            item['parent_work_id'] = u''
            item['parent_work_id'] = u', '.join(parent_work_id)
            item['parent_composer'] = u''
            item['parent_composer'] = u', '.join(parent_composer)
            item['parent_composer_sort'] = u''
            item['parent_composer_sort'] = u', '.join(parent_composer_sort)
            if not (work_date is None):
                item['work_date'] = work_date
            ui.show_model_changes(
                item, fields=['parent_work', 'parent_work_disambig',
                              'parent_work_id', 'parent_composer',
                              'parent_composer_sort', 'work_date'])

            item.store()
