# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2015-2016, Ohm Patel.
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
"""Allows beets to create a mosaic from covers."""
from __future__ import division, absolute_import, print_function

import os.path

from beets.plugins import BeetsPlugin
from beets import ui
from beets.ui import decargs
from beets.util import syspath, normpath, displayable_path, bytestring_path
from beets.util.artresizer import ArtResizer
from beets import config
from beets import art

class MosaicCoverArtPlugin(BeetsPlugin):
	col_size = 4
	margin = 3

	def __init__(self):
		super(MosaicCoverArtPlugin, self).__init__()
		self.config.add({'widthcover': 300})

 	def commands(self):
		cmd = ui.Subcommand('mosaic', help=u"create mosaic from coverart")

		def func(lib, opts, args):
			self._generate_montage(lib, lib.albums(ui.decargs(args)), u'c:\\temp\mos.png')
		cmd.func = func
		return [cmd]

	def _generate_montage(self, lib, albums, output_fn):
		for album in albums:

			if not os.path.exists(album.artpath):
				continue
			self._log.info(u'Album: {}-{}', album,album.artpath)
			image = art.mediafile_image(album.artpath)

	

		#for image in images
		#	width += image.size[0]+ margin
		#width = max(image.size[0] + margin for image in images)*row_size
		#height = sum(image.size[1] + margin for image in images)
		#montage = Image.new(mode='RGBA', size=(width, height), color=(0,0,0,0))
		#max_x = 0
		#max_y = 0
		#offset_x = 0
		#offset_y = 0
		#for i,image in enumerate(images):
	#		montage.paste(image, (offset_x, offset_y))
	#		max_x = max(max_x, offset_x + image.size[0])
	#		max_y = max(max_y, offset_y + image.size[1])
	#		if i % row_size == row_size-1:
	#			offset_y = max_y + margin
	#			offset_x = 0
	#		else:
	#			offset_x += margin + image.size[0]
	#	montage = montage.crop((0, 0, max_x, max_y))
	#	montage.save(output_fn)