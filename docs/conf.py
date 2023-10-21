AUTHOR = "Adrian Sampson"

# General configuration

extensions = ["sphinx.ext.autodoc", "sphinx.ext.extlinks"]

exclude_patterns = ["_build"]
source_suffix = ".rst"
master_doc = "index"

project = "beets"
copyright = "2016, Adrian Sampson"

version = "1.6"
release = "1.6.1"

pygments_style = "sphinx"

# External links to the bug tracker and other sites.
extlinks = {
    "bug": ("https://github.com/beetbox/beets/issues/%s", "#%s"),
    "user": ("https://github.com/%s", "%s"),
    "pypi": ("https://pypi.org/project/%s/", "%s"),
    "stdlib": ("https://docs.python.org/3/library/%s.html", "%s"),
}

linkcheck_ignore = [
    r"https://github.com/beetbox/beets/issues/",
    r"https://github.com/[^/]+$",  # ignore user pages
    r".*localhost.*",
    r"https?://127\.0\.0\.1",
    r"https://www.musixmatch.com/",  # blocks requests
    r"https://genius.com/",  # blocks requests
]

# Options for HTML output
htmlhelp_basename = "beetsdoc"

# Options for LaTeX output
latex_documents = [
    ("index", "beets.tex", "beets Documentation", AUTHOR, "manual"),
]

# Options for manual page output
man_pages = [
    (
        "reference/cli",
        "beet",
        "music tagger and library organizer",
        [AUTHOR],
        1,
    ),
    (
        "reference/config",
        "beetsconfig",
        "beets configuration file",
        [AUTHOR],
        5,
    ),
]

# Options for rtd theme
html_theme = 'sphinx_rtd_theme'
html_theme_options = {
    'sticky_navigation': True,
    'collapse_navigation': True,
    "style_nav_header_background": "#ffffff",
    'logo_only': False,
    'display_version': True,
}
html_title = "beets"
html_logo = "assets/beets_logo.png"
