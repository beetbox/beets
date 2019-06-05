Music Importer
==============

The importer component is responsible for the user-centric workflow that adds
music to a library. This is one of the first aspects that a user experiences
when using beets: it finds music in the filesystem, groups it into albums,
finds corresponding metadata in MusicBrainz, asks the user for intervention,
applies changes, and moves/copies files. A description of its user interface is
given in :doc:`/guides/tagger`.

The workflow is implemented in the ``beets.importer`` module and is
distinct from the core logic for matching MusicBrainz metadata (in the
``beets.autotag`` module). The workflow is also decoupled from the command-line
interface with the hope that, eventually, other (graphical) interfaces can be
bolted onto the same importer implementation.

The importer is multithreaded and follows the pipeline pattern. Each pipeline
stage is a Python coroutine. The ``beets.util.pipeline`` module houses
a generic, reusable implementation of a multithreaded pipeline.
