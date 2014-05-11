AUTHOR = u'Adrian Sampson'

# General configuration

extensions = ['sphinx.ext.autodoc']

exclude_patterns = ['_build']
source_suffix = '.rst'
master_doc = 'index'

project = u'beets'
copyright = u'2012, Adrian Sampson'

version = '1.3'
release = '1.3.7'

pygments_style = 'sphinx'

# Options for HTML output

html_theme = 'default'
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
