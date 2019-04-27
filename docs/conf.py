# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, print_function

AUTHOR = u'Adrian Sampson'

# General configuration

extensions = ['sphinx.ext.autodoc', 'sphinx.ext.extlinks']

exclude_patterns = ['_build']
source_suffix = '.rst'
master_doc = 'index'

project = u'beets'
copyright = u'2016, Adrian Sampson'

version = '1.4'
release = '1.4.8'

pygments_style = 'sphinx'

# External links to the bug tracker and other sites.
extlinks = {
    'bug': ('https://github.com/beetbox/beets/issues/%s', '#'),
    'user': ('https://github.com/%s', ''),
    'pypi': ('https://pypi.org/project/%s/', ''),
    'stdlib': ('https://docs.python.org/3/library/%s.html', ''),
}

# Options for HTML output
htmlhelp_basename = 'beetsdoc'

# Options for LaTeX output
latex_documents = [
    ('index', 'beets.tex', u'beets Documentation',
     AUTHOR, 'manual'),
]

# Options for manual page output
man_pages = [
    ('reference/cli', 'beet', u'music tagger and library organizer',
     [AUTHOR], 1),
    ('reference/config', 'beetsconfig', u'beets configuration file',
     [AUTHOR], 5),
]
