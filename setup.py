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
import shutil
import subprocess
import sys

from setuptools import setup


def _read(fn):
    path = os.path.join(os.path.dirname(__file__), fn)
    return open(path).read()


def build_manpages():
    # Go into the docs directory and build the manpage.
    docdir = os.path.join(os.path.dirname(__file__), "docs")
    curdir = os.getcwd()
    os.chdir(docdir)
    try:
        subprocess.check_call(["make", "man"])
    except OSError:
        print("Could not build manpages (make man failed)!", file=sys.stderr)
        return
    finally:
        os.chdir(curdir)

    # Copy resulting manpages.
    mandir = os.path.join(os.path.dirname(__file__), "man")
    if os.path.exists(mandir):
        shutil.rmtree(mandir)
    shutil.copytree(os.path.join(docdir, "_build", "man"), mandir)


# Build manpages if we're making a source distribution tarball.
if "sdist" in sys.argv:
    build_manpages()


setup(
    name="beets",
    version="1.6.1",
    description="music tagger and library organizer",
    author="Adrian Sampson",
    author_email="adrian@radbox.org",
    url="https://beets.io/",
    license="MIT",
    platforms="ALL",
    long_description=_read("README.rst"),
    test_suite="test.testall.suite",
    zip_safe=False,
    include_package_data=True,  # Install plugin resources.
    packages=[
        "beets",
        "beets.autotag",
        "beets.dbcore",
        "beets.test",
        "beets.ui",
        "beets.util",
        "beetsplug",
        "beetsplug.bpd",
        "beetsplug.lastgenre",
        "beetsplug.metasync",
        "beetsplug.web",
    ],
    entry_points={
        "console_scripts": [
            "beet = beets.ui:main",
        ],
    },
    install_requires=[
        "confuse>=1.5.0",
        "jellyfish",
        "mediafile>=0.12.0",
        "munkres>=1.0.0",
        "musicbrainzngs>=0.4",
        "pyyaml",
        "typing_extensions",
        "unidecode>=1.3.6",
    ]
    + (
        # Support for ANSI console colors on Windows.
        ["colorama"]
        if (sys.platform == "win32")
        else []
    ),
    extras_require={
        "test": [
            "beautifulsoup4",
            "flask",
            "mock",
            "pylast",
            "pytest",
            "pytest-cov",
            "python-mpd2",
            "python3-discogs-client>=2.3.15",
            "py7zr",
            "pyxdg",
            "rarfile",
            "reflink",
            "requests_oauthlib",
            "responses>=0.3.0",
        ],
        "lint": [
            "flake8",
            "flake8-docstrings",
            "pep8-naming",
        ],
        "mypy": [
            "mypy",
            "types-beautifulsoup4",
            "types-Flask-Cors",
            "types-Pillow",
            "types-PyYAML",
            "types-requests",
            "types-urllib3",
        ],
        "docs": [
            "pydata_sphinx_theme",
            "sphinx",
        ],
        # Plugin (optional) dependencies:
        "absubmit": ["requests"],
        "beatport": ["requests-oauthlib>=0.6.1"],
        "bpd": ["PyGObject"],
        "chroma": ["pyacoustid"],
        "discogs": ["python3-discogs-client>=2.3.15"],
        "embedart": ["Pillow"],
        "embyupdate": ["requests"],
        "fetchart": ["requests", "Pillow", "beautifulsoup4"],
        "import": ["rarfile", "py7zr"],
        "kodiupdate": ["requests"],
        "lastgenre": ["pylast"],
        "lastimport": ["pylast"],
        "lyrics": ["requests", "beautifulsoup4", "langdetect"],
        "metasync": ["dbus-python"],
        "mpdstats": ["python-mpd2>=0.4.2"],
        "plexupdate": ["requests"],
        "reflink": ["reflink"],
        "replaygain": ["PyGObject"],
        "scrub": ["mutagen>=1.33"],
        "sonosupdate": ["soco"],
        "thumbnails": ["pyxdg", "Pillow"],
        "web": ["flask", "flask-cors"],
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
        "Topic :: Multimedia :: Sound/Audio",
        "Topic :: Multimedia :: Sound/Audio :: Players :: MP3",
        "License :: OSI Approved :: MIT License",
        "Environment :: Console",
        "Environment :: Web Environment",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: Implementation :: CPython",
    ],
)
