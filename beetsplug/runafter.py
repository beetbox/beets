# -*- coding: UTF-8 -*-

# This file is part of beets.
# Copyright 2015, Manfred Urban.
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

"""Runs arbitrary commands after import has finished."""

from __future__ import (division, absolute_import, print_function,
												unicode_literals)

import os
import subprocess

from beets.plugins import BeetsPlugin


class RunAfterPlugin(BeetsPlugin):
	def __init__(self):
		super(RunAfterPlugin, self).__init__()

		self.config.add({
			"import": None
		})

		# Register callbacks
		self.register_listener("pluginload", self._loaded)
		self.register_listener("import", self._run_after_import)

	def _loaded(self):
		self._log.debug("runafter plugin enabled.")

	def _run_after_import(self, paths):
		if not self.config["import"].get():
			return

		arguments = self.config["import"].as_str_seq()
		expandedArguments = []
		for argument in arguments:
			argument = os.path.expanduser(argument)
			argument = os.path.expandvars(argument)
			expandedArguments.append(argument)
		subprocess.call(expandedArguments)
