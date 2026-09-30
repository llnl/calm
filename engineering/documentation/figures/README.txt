CALM documentation figure tools
=================================

The greenfield Learn section publishes three tutorial-owned SVG figures. Their
single source of truth is:

    engineering/documentation/figures/generate_tutorial_figures.py

Regenerate or validate the committed tutorial figures:

    python engineering/documentation/figures/generate_tutorial_figures.py
    python engineering/documentation/figures/generate_tutorial_figures.py --check

Write the same figures to an explicit preview directory:

    python engineering/documentation/figures/generate_tutorial_figures.py \
      --output-dir /tmp/calm-tutorial-figures

The greenfield Understand section publishes eight concept-owned SVG figures.
Their public inventory and page ownership are defined by:

    engineering/documentation/figures/generate_understand_figures.py

Regenerate or validate the committed Understand figures:

    python engineering/documentation/figures/generate_understand_figures.py
    python engineering/documentation/figures/generate_understand_figures.py --check

Write the same figures to an explicit preview directory:

    python engineering/documentation/figures/generate_understand_figures.py \
      --output-dir /tmp/calm-understand-figures

The lower-level scientific and lattice generators remain reusable source
recipes. They write to the ignored `build/documentation-figures/` tree by
default; the dedicated tutorial, Understand, and site generators are the only
owners of committed MkDocs figure assets.

Preview the complete scientific recipe set:

    python engineering/documentation/figures/generate_scientific_figures.py

Generate or validate candidate lattice recipes in the build tree:

    python engineering/documentation/figures/generate_lattice_figures.py
    python engineering/documentation/figures/generate_lattice_figures.py --check

Generate a specific lattice recipe into an explicit directory:

    python engineering/documentation/figures/generate_lattice_figures.py \
      --only coupled-common-cell \
      --output-dir /tmp/calm-lattice-figures

List all maintained lattice recipes:

    python engineering/documentation/figures/generate_lattice_figures.py --list

The figure tools use repository-owned Python code and do not add runtime
requirements to CALM's public package.

The documentation home publishes one workflow-map SVG. Its single source of
truth is:

    engineering/documentation/figures/generate_site_figures.py

Regenerate or validate the committed site figure:

    python engineering/documentation/figures/generate_site_figures.py
    python engineering/documentation/figures/generate_site_figures.py --check

Write the same figure to an explicit preview directory:

    python engineering/documentation/figures/generate_site_figures.py \
      --output-dir /tmp/calm-site-figures
