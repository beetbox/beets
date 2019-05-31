Parentwork Plugin
=================

The ``parentwork`` plugin fetches the work title, parentwork title and 
parentwork composer. 

In the MusicBrainz database, a recording can be associated with a work. A 
work can itself be associated with another work, for example one being part 
of the other (what I call the father work). This plugin looks the work id 
from the library and then looks up the father, then the father of the father 
and so on until it reaches the top. The work at the top is what I call the 
parentwork. This plugin is especially designed for classical music. For 
classical music, just fetching the work title as in MusicBrainz is not 
satisfying, because MusicBrainz has separate works for, for example, all the 
movements of a symphony. This plugin aims to solve this problem by not only 
fetching the work itself from MusicBrainz but also its parentwork which would 
be, in this case, the whole symphony. 

This plugin adds five tags: 

- **parentwork**: The title of the parentwork.  
- **mb_parentworkid**: The musicbrainz id of the parentwork. 
- **parentwork_disambig**: The disambiguation of the parentwork title. 
- **parent_composer**: The composer of the parentwork. 
- **parent_composer_sort**: The sort name of the parentwork composer. 
- **work_date**: THe composition date of the work, or the first parent work 
  that has a composition date. Format: yyyy-mm-dd. 

To fill in the parentwork tag and the associated parent** tags, in case there 
are several works on the recording, it fills it with the results of the first 
work and then appends the results of the second work only if they differ from 
the ones already there. This is to care for cases of, for example, an opera 
recording that contains several scenes of the opera: neither the parentwork 
nor all the associated tags will be duplicated. 
If there are several works linked to a recording, they all get a 
disambiguation (empty as default) and if all disambiguations are empty, the 
disambiguation field is left empty, else the disambiguation field can look 
like ``,disambig,,`` (if there are four works and only the second has a 
disambiguation) if only the second work has a disambiguation. This may 
seem clumsy but it allows to identify which of the four works the 
disambiguation belongs to. 

To use the ``parentwork`` plugin, enable it in your configuration (see
:ref:`using-plugins`).

Configuration
-------------

To configure the plugin, make a ``parentwork:`` section in your
configuration file. The available options are:

- **force**: As a default, ``parentwork`` only fetches work info for 
  recordings that do not already have a ``parentwork`` tag. If ``force`` 
  is enabled, it fetches it for all recordings. 
  Default: ``no``
  
- **auto**: If enabled, automatically fetches works at import. It takes quite 
  some time, because beets is restricted to one musicbrainz query per second. 
  Default: ``no``

