ParentWork Plugin
=================

The ``parentwork`` plugin fetches the work title, parent work title and
parent work composer from MusicBrainz.

In the MusicBrainz database, a recording can be associated with a work. A
work can itself be associated with another work, for example one being part
of the other (what we call the *direct parent*). This plugin looks the work id
from the library and then looks up the direct parent, then the direct parent
of the direct parent and so on until it reaches the top. The work at the top
is what we call the *parent work*.

This plugin is especially designed for
classical music. For classical music, just fetching the work title as in
MusicBrainz is not satisfying, because MusicBrainz has separate works for, for
example, all the movements of a symphony. This plugin aims to solve this
problem by also fetching the parent work, which would be the whole symphony in
this example.

The plugin can detect changes in ``mb_workid`` so it knows when to re-fetch
other metadata, such as ``parentwork``. To do this, when it runs, it stores a
copy of ``mb_workid`` in the bookkeeping field ``parentwork_workid_current``.
At any later run of ``beet parentwork`` it will check if the tags
``mb_workid`` and ``parentwork_workid_current`` are still identical. If it is
not the case, it means the work has changed and all the tags need to be
fetched again.

This plugin adds seven tags:

- **parentwork**: The title of the parent work.
- **mb_parentworkid**: The MusicBrainz id of the parent work.
- **parentwork_disambig**: The disambiguation of the parent work title.
- **parent_composer**: The composer of the parent work.
- **parent_composer_sort**: The sort name of the parent work composer.
- **work_date**: The composition date of the work, or the first parent work
  that has a composition date. Format: yyyy-mm-dd.
- **parentwork_workid_current**: The MusicBrainz id of the work as it was when
  the parentwork was retrieved. This tag exists only for internal bookkeeping,
  to keep track of recordings whose works have changed. 
- **parentwork_date**: The composition date of the parent work.

To use the ``parentwork`` plugin, enable it in your configuration (see
:ref:`using-plugins`).

Configuration
-------------

To configure the plugin, make a ``parentwork:`` section in your
configuration file. The available options are:

- **force**: As a default, ``parentwork`` only fetches work info for
  recordings that do not already have a ``parentwork`` tag or where 
  ``mb_workid`` differs from ``parentwork_workid_current``. If ``force``
  is enabled, it fetches it for all recordings.
  Default: ``no``

- **auto**: If enabled, automatically fetches works at import. It takes quite
  some time, because beets is restricted to one MusicBrainz query per second.
  Default: ``no``
