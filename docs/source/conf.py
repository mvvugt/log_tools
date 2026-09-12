"""Sphinx configuration for log_tools.

Scaffolding only -- no content pages have been written yet.
"""
from __future__ import annotations

import log_tools

project = "log_tools"
author = "Marion van Vugt"
copyright = '2026, Marion van Vugt'
release = log_tools.__version__

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

# Intersphinx, links into the STD python library
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None)
}
