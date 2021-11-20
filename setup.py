#!/usr/bin/env python

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
    version='1.6.1',
    description='music tagger and library organizer',
    author='Adrian Sampson',
    author_email='adrian@radbox.org',
    url='https://beets.io/',
    license='MIT',
    platforms='ALL',
    long_description=_read('README.rst'),
    test_suite='test.testall.suite',
    zip_safe=False,
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
        'unidecode',
        'musicbrainzngs>=0.4',
        'pyyaml',
        'mediafile>=0.9.0',
        'confuse>=1.5.0',
        'munkres>=1.0.0',
        'jellyfish',
    ] + (
        # Support for ANSI console colors on Windows.
        ['colorama'] if (sys.platform == 'win32') else []
    ),

    extras_require={
        'test': [
            'beautifulsoup4',
            'coverage',
            'flask',
            'mock',
            'pylast',
            'pytest',
            'python-mpd2',
            'pyxdg',
            'responses>=0.3.0',
            'requests_oauthlib',
            'reflink',
            'rarfile',
            'python3-discogs-client',
            'py7zr',
        ],
        'lint': [
            'flake8',
            'flake8-docstrings',
            'pep8-naming',
        ],

        # Plugin (optional) dependencies:
        'absubmit': ['requests'],
        'fetchart': ['requests', 'Pillow'],
        'embedart': ['Pillow'],
        'embyupdate': ['requests'],
        'chroma': ['pyacoustid'],
        'discogs': ['python3-discogs-client>=2.3.10'],
        'beatport': ['requests-oauthlib>=0.6.1'],
        'kodiupdate': ['requests'],
        'lastgenre': ['pylast'],
        'lastimport': ['pylast'],
        'lyrics': ['requests', 'beautifulsoup4', 'langdetect'],
        'mpdstats': ['python-mpd2>=0.4.2'],
        'plexupdate': ['requests'],
        'web': ['flask', 'flask-cors'],
        'import': ['rarfile', 'py7zr'],
        'thumbnails': ['pyxdg', 'Pillow'],
        'metasync': ['dbus-python'],
        'sonosupdate': ['soco'],
        'scrub': ['mutagen>=1.33'],
        'bpd': ['PyGObject'],
        'replaygain': ['PyGObject'],
        'reflink': ['reflink'],
    },
    # Non-Python/non-PyPI plugin dependencies:
    #   chroma: chromaprint or fpcalc
    #   convert: ffmpeg
    #   badfiles: mp3val and flac
    #   bpd: python-gi and GStreamer 1.0+
    #   embedart: ImageMagick
    #   absubmit: extractor binary from https://acousticbrainz.org/download
    #   keyfinder: KeyFinder
    #   replaygain: python-gi and GStreamer 1.0+
    #               or mp3gain/aacgain
    #               or Python Audio Tools
    #               or ffmpeg
    #   ipfs: go-ipfs

    classifiers=[
        'Topic :: Multimedia :: Sound/Audio',
        'Topic :: Multimedia :: Sound/Audio :: Players :: MP3',
        'License :: OSI Approved :: MIT License',
        'Environment :: Console',
        'Environment :: Web Environment',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: Implementation :: CPython',
    ],
)
