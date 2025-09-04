# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information


project = "beets"
AUTHOR = "Adrian Sampson"
copyright = "2016, Adrian Sampson"

master_doc = "index"
language = "en"
version = "2.3"
release = "2.3.1"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.extlinks",
]
autosummary_generate = True
exclude_patterns = ["_build"]
templates_path = ["_templates"]
source_suffix = {".rst": "restructuredtext", ".md": "markdown"}


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

# Global substitutions that can be used anywhere in the documentation.
rst_epilog = """
.. |Album| replace:: :class:`~beets.library.models.Album`
.. |AlbumInfo| replace:: :class:`beets.autotag.hooks.AlbumInfo`
.. |ImportSession| replace:: :class:`~beets.importer.session.ImportSession`
.. |ImportTask| replace:: :class:`~beets.importer.tasks.ImportTask`
.. |Item| replace:: :class:`~beets.library.models.Item`
.. |Library| replace:: :class:`~beets.library.library.Library`
.. |Model| replace:: :class:`~beets.dbcore.db.Model`
.. |TrackInfo| replace:: :class:`beets.autotag.hooks.TrackInfo`
"""

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output


html_theme = "pydata_sphinx_theme"
html_theme_options = {
    "collapse_navigation": False,
    "logo": {"text": "beets"},
    "show_nav_level": 3,  # How many levels in left sidebar to show automatically
    "navigation_depth": 4,  # How many levels of navigation to expand
}
html_title = "beets"
html_logo = "_static/beets_logo_nobg.png"
html_static_path = ["_static"]
html_css_files = ["beets.css"]


def skip_member(app, what, name, obj, skip, options):
    if name.startswith("_"):
        return True
    return skip


def setup(app):
    app.connect("autodoc-skip-member", skip_member)
