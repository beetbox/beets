Parentwork Plugin
=================

The `parentwork` plugin fetches the work title, parentwork title and 
parentwork composer. 

In the MusicBrainz database, a recording can be associated with a work. A 
work can itself be associated with another work, for example one being part 
of the other (what I call the father work). This plugin fetches the work and 
then looks up the father, then the father of the father and so on until it 
reaches the top. The work at the top is what I call the parentwork. This 
plugin is especially designed for classical music. For classical music, just 
fetching the work title as in MusicBrainz is not satisfying, because 
MusicBrainz has separate works for, for example, all the movements of a 
symphony. This plugin aims to solve this problem by not only fetching the 
work as in MusicBrainz but also his parentwork which would be, in this case, 
the whole symphony. 

This plugin adds six tags: 

- **work**: The title of the work. 
- **work_disambig**: The disambiguation of the work title (useful expecially 
  to distinguish arrangements). 
- **parent_work**: The title of the parentwork.  
- **parent_work_disambig**: The disambiguation of the parentwork title. 
- **parent_composer**: The composer of the parentwork. 
- **parent_composer_sort**: The sort name of the parentwork composer. 

To fill in the parentwork tag and the associated parent** tags, in case there 
are several works on the recording, it fills it with the results of the first 
work and then appends the results of the second work only if they differ from 
the ones already there. This is to care for cases of, for example, an opera 
recording that contains several scenes of the opera: neither the parentwork 
nor all the associated tags will be duplicated. 

To use the ``parentwork`` plugin, enable it in your configuration (see
:ref:`using-plugins`).

Configuration
-------------

To configure the plugin, make a ``parentwork:`` section in your
configuration file. The available options are:

- **auto**: Analyze every file on
  import. Otherwise, you need to use the ``beet parentwork`` command
  explicitly.
  Default: ``yes``
- **force**: As a default, ``parentwork`` only fetches work info for 
  recordings that do not already have a ``parent_work`` tag. If ``force`` 
  is enabled, it fetches it for all recordings. 
  Default: ``no``

