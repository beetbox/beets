Waveform Plugin
==============

The ``waveform`` plugin uses the Librosa_ and Matplotlib_ libraries to generate
waveform images from its audio data. It does so automatically when importing
music or through the ``beet waveform [QUERY]``
command.

Install
-------

To use the ``waveform`` plugin, first enable it in your configuration (see
:ref:`using-plugins`). Then, install ``beets`` with ``waveform`` extra

.. code-block:: bash

    pip install "beets[waveform]"

Configuration
-------------

To configure the plugin, make a ``waveform:`` section in your configuration file.

Default
~~~~~~~

.. code-block:: yaml

    waveform:
        auto: yes
        width: 800
        height: 300
        transparent: no
        color: black

.. conf:: auto
    :default: yes

    Analyze every file on import. Otherwise, you need to use the ``beet
    waveform`` command explicitly.

.. conf:: width
    :default: 800

    Sets the image width dimension in pixels. Can also be set
    using the ``--width`` flag.

.. conf:: height
    :default: 300

    Sets the image height dimension in pixels. Can also be set
    using the ``--height`` flag.

.. conf:: transparent
    :default: no

    Sets the image background transparency. Can also be set
    using the ``-t`` or ``--transparent`` flag.

.. conf:: color
    :default: black

    Sets the waveform color. Can also be set
    using the ``-c`` or ``--color`` flag.

Further information
~~~~~~~~~~~~~~~~~~~

A list of colors can be found
`here <https://matplotlib.org/stable/gallery/color/named_colors.html#css-colors>`_.



.. _librosa: https://github.com/librosa/librosa/

.. _Matplotlib: https://github.com/matplotlib/matplotlib
