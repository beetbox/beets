Mosaic Plugin
=====================

The ``mosaic`` plugin generates a montage of a mosiac from cover art.

To use the ``mosaic`` plugin, first enable it in your configuration (see
:ref:`using-plugins`). Then, install the `Pillow`_ library by typing::

    pip install Pillow

The plugin uses `Pillow`_ to manipulate album art and create the mosiac.

.. _pillow: http://pillow.readthedocs.io/en/latest/


By default the ``mosaic`` generates a mosaic, as mosaic.png in the current directory, of cover art out of the whole library .

You can customize the output mosaic, overlay and blend a image as watermark and use a alternative filename as result picture ::

  -h, --help            			show this help message and exit
  -m FILE, --mosaic=file    		save final mosaic picture as FILE
  -w FILE, --watermark=FILE     	add FILE for a picture to blend over mosaic
  -a ALPHA, --alpha=ALPHA       	ALPHA value for blending 0.0-1.0
  -c HEXCOLOR, --color=HEXCOLOR 	background color as HEXCOLOR
  -g GEOMETRY, --geometry=GEOMETRY Geometry defined as <width>x<height>+<marginx>+<marginy>

Examples
--------
Create mosaic from all Album cover art::

    $ beet mosaic

Create mosaic from band Tool with a second picture as watermark::

    $ beet mosaic -w c:/temp/tool.png -a 0.4 Tool

Create mosaic from every Album out of year 2012, use background color red::

    $ beet mosaic -b ff0000 year:2012

Configuration
-------------

To configure the plugin, make a ``mosaic:`` section in your
configuration file. There is four option:

- **mosaic**: Use a different filename for the final mosaic picture,
  Default: ``mosaic.png``.
- **watermark**: Use a picture to blend over the mosiac picture,
  Default: ''None''.
- **alpha**: The factor as float, to blend the watermark over the mosaic. 0.0 - means no visible watermark. 1.0 - full visible watermark.  
  Default: ``0.4``
- **background**: The color of the background and the visible border of the mosaic as Hexcolor e.g. ffffff for white or 000000 as black 
  Default: ``ffffff``
- **geometry**: Define geometry of each cover defined as <width>x<height>+<marginx>+<marginy>
- Default: ``100x100+3+3``

