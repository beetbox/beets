#!/usr/bin/env python

# This file is part of beets.
# Copyright 2010, Adrian Sampson.
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

from distutils.core import setup

setup(name='beets',
      version='0.1',
      description='music library manager',
      author='Adrian Sampson',
      author_email='adrian@radbox.org',
      url='http://code.google.com/p/beets/',
      license='GPL',
      platforms='ALL',
      long_description="""Beets is a system for managing your music
      collection.
      
      It catalogs a collection in a sqlite database. This allows batch
      correction of file tags and reorganization into a custom
      directory structure.
      
      It also includes a music player that reimplements the
      `MPD <http://musicpd.org/>`_ protocol in order to play music from
      the database.
      """,

      packages=['beets',
                'beets.autotag',
                'beets.player',
      ],
      scripts=['bts'],

      provides=['beets'],
      requires=['sqlite3',
                'mutagen',
                'musicbrainz2 (>=0.7.0)',
                'munkres',
                'cmdln',
                'eventlet (>=0.8)',
      ],
)

