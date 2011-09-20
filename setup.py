#!/usr/bin/env python

# This file is part of beets.
# Copyright 2011, Adrian Sampson.
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

import os
from setuptools import setup

def _read(fn):
    path = os.path.join(os.path.dirname(__file__), fn)
    return open(path).read()

setup(name='beets',
      version='1.0b10',
      description='music tagger and library organizer',
      author='Adrian Sampson',
      author_email='adrian@radbox.org',
      url='http://beets.radbox.org/',
      license='MIT',
      platforms='ALL',
      long_description=_read('README.rst'),
      test_suite='test.testall.suite',

      packages=[
          'beets',
          'beets.ui',
          'beets.autotag',
          'beets.util',
          'beetsplug',
          'beetsplug.bpd',
          'beetsplug.web',
      ],
      namespace_packages=['beetsplug'],
      entry_points={
          'console_scripts': [
              'beet = beets.ui:main',
          ],
      },

      install_requires=[
          'mutagen',
          'python-musicbrainz2 >= 0.7.2',
          'munkres',
          'unidecode',
      ],

      classifiers=[
          'Topic :: Multimedia :: Sound/Audio',
          'Topic :: Multimedia :: Sound/Audio :: Players :: MP3',
          'License :: OSI Approved :: MIT License',
          'Environment :: Console',
          'Development Status :: 4 - Beta',
      ],
)
