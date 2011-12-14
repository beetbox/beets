AUTHOR = u'Adrian Sampson'

# -- General configuration -----------------------------------------------------

extensions = []

#templates_path = ['_templates']
exclude_patterns = ['_build']
source_suffix = '.rst'
master_doc = 'index'

project = u'beets'
copyright = u'2011, Adrian Sampson'

version = '1.0b12'
release = '1.0b12'

pygments_style = 'sphinx'

# -- Options for HTML output ---------------------------------------------------

html_theme = 'default'
#html_static_path = ['_static']
htmlhelp_basename = 'beetsdoc'

# -- Options for LaTeX output --------------------------------------------------

latex_documents = [
  ('index', 'beets.tex', u'beets Documentation',
   AUTHOR, 'manual'),
]

# -- Options for manual page output --------------------------------------------

man_pages = [
    ('reference/cli', 'beet', u'music tagger and library organizer',
     [AUTHOR], 1),
    ('reference/config', 'beetsconfig', u'beets configuration file',
     [AUTHOR], 5),
]
