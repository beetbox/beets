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

from setuptools import setup

setup(name='beets',
      version='1.0b2',
      description='music tagger and library organizer',
      author='Adrian Sampson',
      author_email='adrian@radbox.org',
      url='http://beets.radbox.org/',
      license='MIT',
      platforms='ALL',
      long_description="""Beets is a media library management system
      for obsessive-compulsive music geeks.

      The purpose of beets is to get your music collection right once
      and for all. It catalogs your collection, automatically
      improving its metadata as it goes using the MusicBrainz database.
      It then provides a set of tools for manipulating and accessing
      your music.
      
      Beets also includes a music player that implements the MPD
      protocol, so you can play music in your beets library using any
      MPD client.
      """,

      packages=[
          'beets',
          'beets.autotag',
          'beets.player',
      ],
      scripts=['beet'],

      install_requires=[
          'mutagen',
          'python-musicbrainz2 >= 0.7.0',
          'munkres',
          'eventlet >= 0.9.3',
      ],
)

