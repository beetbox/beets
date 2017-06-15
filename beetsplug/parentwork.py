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

from beets import ui, logging
from beets.plugins import BeetsPlugin
from beets.dbcore import types

import musicbrainzngs

def find_parentwork(work_id):
    """This function finds the parentwork of a work given its id. """
    work_info = musicbrainzngs.get_work_by_id(work_id,
        includes=["work-rels", "artist-rels"])
    partof = True
    # The works a given work is related to are listed in
    # work_info['work']['work-relation-list']. The relations can be
    # diverse: arrangement of, later version of, part of etc. The
    # father work (i. e. the work the work is part of) is given by the
    # relationship 'type' to be 'part' and the relationship
    # 'direction' to be 'backwards'. First I assume the work doesn't
    # have a father work (i. e. it is its own parentwork), but if in
    # the works it is related to there is a work which is his father
    # work, then I assume the father work is the parent work and try
    # the same with it.
    while partof:
        partof = False
        if 'work-relation-list' in work_info['work']:
            for work_father in work_info['work']['work-relation-list']:
                if work_father['type'] == 'parts' and work_father.get(
                    'direction') == 'backward':
                    father_id = work_father['work']['id']
                    partof = True
                    work_info = musicbrainzngs.get_work_by_id(
                        father_id,includes = ["work-rels","artist-rels"])
    return work_info

def get_info(work_info,parent_composer,parent_composer_sort,parent_work,
    parent_work_disambig,work_ids,composer_ids):
    """Given the parentwork info dict, this function updates the 
    parent composer etc"""
    composer_exists=False
    if 'artist-relation-list' in work_info['work']:
        for artist in work_info['work']['artist-relation-list']:
            if artist['type'] == 'composer':
                composer_exists=True
                if artist['artist']['id'] not in composer_ids:
                    composer_ids.add(artist['artist']['id'])
                    parent_composer.append(artist['artist']['name'])
                    parent_composer_sort.append(artist['artist']['sort-name'])
    if not composer_exists:
        print('no composer')
        print('add one at')
        print('https://musicbrainz.org/work/' + 
            work_info['work']['id'])
    if work_info['work']['id'] in work_ids:
        pass
    else:
        parent_work.append(work_info['work']['title'])
        work_ids.add(work_info['work']['id'])
        if 'disambiguation' in work_info['work']:
            parent_work_disambig.append(work_info['work']['disambiguation'])

class ParentWorkPlugin(BeetsPlugin):

    def __init__(self):
        super(ParentWorkPlugin, self).__init__()
        self.import_stages = [self.imported]

    def commands(self):
        cmd = ui.Subcommand('parentwork',
                            help=u'fetches parent works, composers \
                                and performers')
        cmd.func = self.command
        return [cmd]

    def command(self, lib, opts, args):
        self.find_work(lib.items(ui.decargs(args)))

    def imported(self, session, task):
        self.find_work(task.items)

    def find_work(self, items):

        

        for item in items:
            work                 = []
            work_disambig        = []
            parent_work          = []
            parent_work_disambig = []
            parent_composer      = []
            parent_composer_sort = []
            work_ids             = set()
            composer_ids         = set()
            
            item.read()
            recording_id = item.mb_trackid
            performer_types = ['performer', 'instrument', 'vocal',
                'conductor', 'performing orchestra', 'chorus master', 
                    'concertmaster']
            found = True
            if 'parent_work' in item:
                continue
            try:
                rec_rels = musicbrainzngs.get_recording_by_id(
                    recording_id, includes=['work-rels'])
                if 'work-relation-list' in rec_rels['recording']:
                    for work_relation in rec_rels['recording'][
                            'work-relation-list']:
                        if work_relation['type'] != 'performance':
                            continue
                        work_id = work_relation['work']['id']
                        work.append(work_relation['work']['title'])
                        if 'disambiguation' in work_relation['work']:
                            work_disambig.append(work_relation['work']
                                ['disambiguation'])
                        work_info = find_parentwork(work_id)
                        get_info(work_info,parent_composer,
                        parent_composer_sort,parent_work,parent_work_disambig,
                        work_ids,composer_ids)

            except musicbrainzngs.musicbrainz.WebServiceError: 
                print('Work unreachable')
                print('recording id: ')
                print(recording_id)
                found = False

            if found:
                item['parent_work']          = u', '.join(parent_work)
                item['parent_work_disambig'] = u', '.join(parent_work_disambig)
                item['work']                 = u', '.join(work)
                item['work_disambig']        = u', '.join(work_disambig)
                item['parent_composer']      = u', '.join(parent_composer)
                item['parent_composer_sort'] = u', '.join(parent_composer_sort)

                item.store()
