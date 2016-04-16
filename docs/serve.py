#!/usr/bin/env python

from __future__ import absolute_import, print_function

from livereload import Server, shell

server = Server()
server.watch('*.rst', shell('make html'))
server.serve(root='_build/html')
