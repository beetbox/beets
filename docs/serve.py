#!/usr/bin/env python
from livereload import Server, shell
server = Server()
server.watch('*.rst', shell('make html'))
server.serve(root='_build/html')
