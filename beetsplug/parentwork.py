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

def work_father(work_id): 
    """ This function finds the id of the father work given its id"""
    work_info = musicbrainzngs.get_work_by_id(work_id,
        includes=["work-rels"])
    if 'work-relation-list' in work_info['work']:
        for work_father in work_info['work']['work-relation-list']:
            if work_father['type'] == 'parts' and work_father.get(
                'direction') == 'backward':
                father_id = work_father['work']['id']
                return(father_id)
        return(None)
                
    else: 
        return(None)

def work_parent(work_id):
    """This function finds the parentwork id of a work given its id. """
    while True: 
        new_work_id = work_parent(work_id)
        if not new_work_id:
            return work_id
        work_id = new_work_id
    return work_id
        
def find_parentwork(work_id):
    """This function gives the work relationships (dict) of a parent_work 
    given the id of the work"""
    parent_id=work_parent(work_id)
    work_info = musicbrainzngs.get_work_by_id(
        parent_id,includes = ["artist-rels"])
    return(work_info)

def get_info(work_info,parent_composer,parent_composer_sort,parent_work,
    parent_work_disambig,work_ids,composer_ids):
    """Given the parentwork info dict, this function updates parent_composer, 
    parent_composer_sort, parent_work, parent_work_disambig, work_ids and
    composer_ids"""
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
        self._log.info(
            "no composer, add one at https://musicbrainz.org/work/" + 
            work_info['work']['id']
            )
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
        self.config.add({
            u'bin': u'parentwork',
            u'auto': True,
            u'force': False,
            u'details': False
        })

        if self.config['auto'].get(bool):
            self.import_stages = [self.imported]

    def commands(self):
        cmd = ui.Subcommand('parentwork',
                            help=u'fetches parent works, composers \
                                and performers')
        cmd.func = self.command
        #cmd.parser.add_option(
        #    u'-f', u'--force', dest='force',
        #    action='store_true', default=False,
        #    help=u're-fetch parent works etc even if already present'
        #)
        
        return [cmd]

    def command(self, lib, opts, args):
        self.find_work(lib.items(ui.decargs(args)))

    def imported(self, session, task):
        self.find_work(task.items)

    def find_work(self, items):
        force = self.config['force'].get(bool)
        details = self.config['details'].get(bool)

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
            found = True
            self_log.debug(
                "Current recording id: " + recording_id
                )
            self_log.debug(
                item[artist] + " - " + item[title]
                )
            if 'parent_work' in item and not force:
                continue
            try:
                rec_rels = musicbrainzngs.get_recording_by_id(
                    recording_id, includes=['work-rels'])
                if 'work-relation-list' in rec_rels['recording']:
                    for work_relation in rec_rels['recording'][
                            'work-relation-list']:
                        hasawork=False
                        if work_relation['type'] != 'performance':
                            continue
                        hasawork=True
                        work_id = work_relation['work']['id']
                        work.append(work_relation['work']['title'])
                        if 'disambiguation' in work_relation['work']:
                            work_disambig.append(work_relation['work']
                                ['disambiguation'])
                        work_info = find_parentwork(work_id)
                        get_info(work_info,parent_composer,
                        parent_composer_sort,parent_work,parent_work_disambig,
                        work_ids,composer_ids)
                        if not hasawork and details: 
                            self._log.info(
                            "No work attached, recording id: " + recording_id
                            )
                            self._log.info(
                            "add one at https://musicbrainz.org/recording/" + 
                            recording_id
                            )

            except musicbrainzngs.musicbrainz.WebServiceError: 
                self._log.info(
                    "Work unreachable, recording id: " + recording_id
                    )
                found = False

            if found:
                item['parent_work']          = u', '.join(parent_work)
                item['parent_work_disambig'] = u', '.join(parent_work_disambig)
                item['work']                 = u', '.join(work)
                item['work_disambig']        = u', '.join(work_disambig)
                item['parent_composer']      = u', '.join(parent_composer)
                item['parent_composer_sort'] = u', '.join(parent_composer_sort)

                item.store()
