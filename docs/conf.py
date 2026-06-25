"""Sphinx configuration for the nexus-sync documentation."""

import os
import sys

# Make the package importable for autodoc (sources live under src/).
sys.path.insert(0, os.path.abspath("../src"))

project = "nexus-sync"
author = "nexus-sync"
copyright = "2026, nexus-sync"
release = "0.1.0"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

# Pull docstrings even from undocumented members so the API pages are useful
# while docstring coverage grows.
autosummary_generate = True
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}
autodoc_typehints = "description"
# Render default argument values as written in source (e.g. ``os.environ``)
# instead of evaluating them, which would dump the live environment into a signature.
autodoc_preserve_defaults = True

# MyST so the existing Markdown guides render as-is.
myst_enable_extensions = ["colon_fence", "deflist"]
source_suffix = {".md": "markdown", ".rst": "restructuredtext"}

exclude_patterns = ["_build", ".DS_Store", "Thumbs.db", "archive"]

html_theme = "furo"
html_title = "nexus-sync"
