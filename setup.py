#!/usr/bin/env python

# This file is part of beets.
# Copyright 2009, Adrian Sampson.
# 
# Beets is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Beets is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with beets.  If not, see <http://www.gnu.org/licenses/>.

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

