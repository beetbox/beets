#!/usr/bin/env python
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

      packages=['beets'],
      scripts=['bts'],

      requires=['sqlite3', 'mutagen', 'eventlet (>=0.8)'],
     )

