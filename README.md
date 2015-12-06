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

You might also want **pykwalify** to validate input a bit better:

    pip install pykwalify

## Usage

Download this repository and run the standalong script
`uproject.py`. There's a demo included in the repository:

    uproject.py demo.yml

This will produce output `demo.pdf`.

Most current features are shown in demo.yml, which is fairly
self-explanatory, but also described briefly below.

## Input format

The timeline is defined in YAML. If you install `pykwalify` the script
will be checked against a schema and you'll get reasonably helpful
messages about missing or invalid keys.

Otherwise (or if you make a content error that falls within the
schema) you will probably just get an exception during drawing.

### Project metadata (required)

The file should begin with these mandatory keys:

```yaml
project: MyProject      # name of project, used in title/footer
version: 1.4            # timeline version, used in footer
unit: week              # time unit: 'week' or 'month'
length: 20              # timeline length in units
start: 2015-11-30       # start date of first unit
```

The 'week' unit starts on Monday. The 'month' unit starts on the first
of each calendar month.

### Options (optional)

You may define `options` to control formatting. Defaults for each
value within this are shown in parentheses.

```yaml
options:
    key_legend: true    # add a legend under the timeline (false)
    key_in_block: true  # also put key names inside blocks (false)
    show_year: true     # put year above first unit in January (true)
    title: 'Text'       # override title ('MyProject timeline')
    footer: 'Text'      # override footer (title + version)
    label_width: 40.0   # label column width (50.0mm)
    one_based: true     # number weeks/months from 1, not 0 (false)
```

You may set `title` or `footer` to `false` to disable them entirely.

If you set `one_based` to `true`, both the time axis labels and the
interpretation of activity timings are affected: so you should decide
whether you wnat this before writing the detail of your project.

### Keys (optional)

You may define `keys` for a set of label-colour pairs to be
associated with categories of activity:

```yaml
keys:
  - name: Dev team
    color: [150,70,70]
  - name: Ops team
    color: [80,150,80]
```

Note American spelling (color, not colour).

### Rows (required)

The actual timeline is defined as a list within the `rows` key, one
element per row.

```yaml
rows:
  - name: A1 activity
    at: 2015-11-30
    length: 2
  - name: A2 milestone
    at: A1
    dep: A1
```

The following keys are valid. Each row must have `name` and at least
one of `at`, `phases`, `breaks`, or `gap`.

  - `name` is shown in the label column. May be empty string.

  - `at` is start time. May be a unit index (eg 2), date (eg
    2015-11-30), or a reference (eg A1; see below).

  - `length` is duration in time units. May be fractional. Omit
    length to define a milestone.

  - `stripe` overrides alternating row highlight for this row only;
    boolean.

  - `dep` is a dependency, or list of dependencies; same syntax as
    references in start time, see below.

  - `key` matches the block to a name in the keys section.

  - `breaks` defines a list of blocks to appear on one row, eg to show
    holidays. Each item must define `name`, `at`, and `length`.

  - `phases` defines a list of time periods, eg to show 'Phase 1' and
    'Phase 2'. Each item must define `name`, `at`, and `length`.

  - `gap` is true to add a blank/heading row.

### Time references

Time references (in `at` or `dep`) are regex matches to row names.
Matches are case insensitive and match from the start of the name to a
word boundary.

Prefix `-` matches the start, prefix `+` matches the end.

The the reference is a 2-tuple instead of a string, the first value is
the regex to match and the second is an offset in time units.

The first matching row is always used.

Given two activity blocks named:

    A10 specification
    A1 development

The following matches work:

    A10         End of block 1
    -A10        Start of block 1
    [A10,2]     2 units after the end of block 1
    A1          End of block 2
    [A1,-1.5]   1.5 units before the end of block 2

Prefixing row names with codes like A1 is optional; you could just use
descriptive names, and retype them as references.

If `dep` is a list, it is assumed to be a list of multiple
dependencies; so to define a single dependency with an offset, use:

    [[A1,-1.5]]

## Author

uProject was written by Mark White, <mark@celos.net>.
