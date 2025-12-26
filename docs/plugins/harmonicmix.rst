#####################
 Harmonic Mix Plugin
#####################

The ``harmonicmix`` plugin is designed to help DJs and playlist curators find
songs that mix well together based on the Circle of Fifths. It checks for:

1. **Harmonic Compatibility:** Finds songs in the same key, the dominant,
   subdominant, or relative major/minor. It also handles common enharmonics
   (e.g., F# = Gb).
2. **BPM Matching:** Filters results to show tracks within a mixable BPM range
   (+/- 8% of the source track).

***************
 Configuration
***************

To use the plugin, enable it in your configuration file (``config.yaml``):

::

    plugins: harmonicmix

*******
 Usage
*******

To find songs compatible with a specific track, use the ``mix`` command followed
by a query:

::

    $ beet mix "Billie Jean"

The plugin will list tracks that match the harmonic criteria. For example:

::

    Source: Billie Jean | Key: F#m | BPM: 117
    ----------------------------------------
    MATCH: Stayin' Alive (F#m, 104 BPM)
    MATCH: Another One Bites the Dust (Em, 110 BPM)

Note that if the source song does not have a ``key`` tag, the plugin cannot find
matches. In addition, if a song does not have a ``bpm`` tag, then the matching
process only considers the key. Tags must be in the format: "C" instead of "C
major".

This plugin could also be paired with the ``xtractor`` or ``keyfinder`` plugins
for better results.
