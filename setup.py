#!/usr/bin/env python
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

from __future__ import division, absolute_import, print_function

import os
import sys
import subprocess
import shutil
from setuptools import setup


def _read(fn):
    path = os.path.join(os.path.dirname(__file__), fn)
    return open(path).read()


def build_manpages():
    # Go into the docs directory and build the manpage.
    docdir = os.path.join(os.path.dirname(__file__), 'docs')
    curdir = os.getcwd()
    os.chdir(docdir)
    try:
        subprocess.check_call(['make', 'man'])
    except OSError:
        print("Could not build manpages (make man failed)!", file=sys.stderr)
        return
    finally:
        os.chdir(curdir)

    # Copy resulting manpages.
    mandir = os.path.join(os.path.dirname(__file__), 'man')
    if os.path.exists(mandir):
        shutil.rmtree(mandir)
    shutil.copytree(os.path.join(docdir, '_build', 'man'), mandir)


# Build manpages if we're making a source distribution tarball.
if 'sdist' in sys.argv:
    build_manpages()


setup(
    name='beets',
    version='1.3.18',
    description='music tagger and library organizer',
    author='Adrian Sampson',
    author_email='adrian@radbox.org',
    url='http://beets.io/',
    license='MIT',
    platforms='ALL',
    long_description=_read('README.rst'),
    test_suite='test.testall.suite',
    include_package_data=True,  # Install plugin resources.

    packages=[
        'beets',
        'beets.ui',
        'beets.autotag',
        'beets.util',
        'beets.dbcore',
        'beetsplug',
        'beetsplug.bpd',
        'beetsplug.web',
        'beetsplug.lastgenre',
        'beetsplug.metasync',
    ],
    entry_points={
        'console_scripts': [
            'beet = beets.ui:main',
        ],
    },

    install_requires=[
        'enum34>=1.0.4',
        'mutagen>=1.27',
        'munkres',
        'unidecode',
        'musicbrainzngs>=0.4',
        'pyyaml',
        'jellyfish',
    ] + (['colorama'] if (sys.platform == 'win32') else []) +
        (['ordereddict'] if sys.version_info < (2, 7, 0) else []),

    tests_require=[
        'beautifulsoup4',
        'flask',
        'mock',
        'pyechonest',
        'pylast',
        'rarfile',
        'responses',
        'pyxdg',
        'pathlib',
        'python-mpd2',
    ],

    # Plugin (optional) dependencies:
    extras_require={
        'fetchart': ['requests'],
        'chroma': ['pyacoustid'],
        'discogs': ['discogs-client>=2.1.0'],
        'echonest': ['pyechonest'],
        'lastgenre': ['pylast'],
        'mpdstats': ['python-mpd2'],
        'web': ['flask', 'flask-cors'],
        'import': ['rarfile'],
        'thumbnails': ['pathlib', 'pyxdg'],
        'metasync': ['dbus-python'],
    },
    # Non-Python/non-PyPI plugin dependencies:
    # convert: ffmpeg
    # bpd: pygst

    classifiers=[
        'Topic :: Multimedia :: Sound/Audio',
        'Topic :: Multimedia :: Sound/Audio :: Players :: MP3',
        'License :: OSI Approved :: MIT License',
        'Environment :: Console',
        'Environment :: Web Environment',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
    ],
)
