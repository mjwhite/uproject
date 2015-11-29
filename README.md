# uProject

uProject draws a simple Gantt chart PDF from a YAML description.

It's good for quickly creating and modifying timelines of simple
projects. It's designed to be more efficient than doing the same thing
in a graphics package, and to produce reasonably attractive output.
But it's purely a drawing tool, not a project management tool.  It
understands activities with relative dates and dependencies, but it
won't find the critical path or resolve dependency order.

## Dependencies

Requires **Python 2.7** and **pyfpdf**; the latter can be installed
easily with:

    pip install fpdf

## Usage

Download this repository and run the standalong script
`uproject.py`. There's a demo included in the repository:

    uproject.py demo.yml

All current features are shown in demo.yml, which is fairly
self-explanatory. The header comment in `uproject.py` explains some of
the details of specifying dependencies and relative timings.

## Author

uProject was written by Mark White <mark@celos.net>.
