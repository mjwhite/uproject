#!/usr/bin/env python
# 
# uProject 
# Microscopic Gantt drawing tool
#
# Mark White <mark@celos.net> 
# November 2015
# 
# uProject is a Gantt drawing tool.  It's good for quickly creating
# and modifying timelines of simple projects. It's designed to be more
# efficient than doing the same thing in a graphics package, and to
# produce reasonably attractive output.  But it's purely a drawing
# tool, not a project management tool.  It understands activities with
# relative dates and dependencies, but it won't find the critical path
# or resolve dependency order.
# 
# See README.md and/or demo.yml for usage.
#
# Dependencies:
#     pyFPDF:    "pip install fpdf" (required)
#     pykwalify: "pip install pykwalify" (optional)
# 

import logging
logging.basicConfig()
logging.getLogger('pykwalify.core').setLevel('CRITICAL')

try:
    import pykwalify.core
    import pykwalify.errors
    HAVE_PYKWALIFY = True
except ImportError:
    HAVE_PYKWALIFY = False

from datetime import date, timedelta
from pprint import pprint
import collections
import yaml
import sys
import re
import os
import inspect

from fpdf import FPDF

Point = collections.namedtuple('Point',['x','y'])

# relative-date utilities

# -- week

def monday(d):
    wd = int(d.strftime("%w"))
    if wd == 0:
        wd = 6
    else:
        wd -= 1
    return d - timedelta(days=wd)

def prev_week(d):
    return monday(monday(d) - timedelta(days=7))

def next_week(d):
    return monday(monday(d) + timedelta(days=7))

def n_weeks(d1,d2):
    return float((d2 - d1).days) / 7.0

# -- month

def first(d):
    return d.replace(day=1)

def prev_month(d):
    return first(first(d) - timedelta(days=1))

def next_month(d):
    return first(first(d) + timedelta(days=32))

def n_months(d1,d2):
    return (d2.year - d1.year)*12 + d2.month - d1.month \
            + (d2.day - d1.day)/30.42

# utilities to merge overlapping line segments on a grid

def inline(axis,*lst):
    return len(set([getattr(e,axis) for e in lst])) == 1

def maybe_merge(axis,pair1,pair2):
    s1 = getattr(pair1[0], axis)
    s2 = getattr(pair2[0], axis)
    e1 = getattr(pair1[1], axis)
    e2 = getattr(pair2[1], axis)
    if s1 <= s2 and s2 <= e1:
        return (pair1[0], pair2[1])
    if s1 <= e2 and e2 <= e1:
        return (pair2[0], pair1[1])
    return None

def maybe_merge_both(pair1,pair2):
    if inline('x',pair1[0],pair1[1],pair2[0],pair2[1]):
        return maybe_merge('y',pair1,pair2)
    elif inline('y',pair1[0],pair1[1],pair2[0],pair2[1]):
        return maybe_merge('x',pair1,pair2)
    else:
        return None

def normalize_grid(lst):
    new_lst = []
    status = [True for e in lst]
    for i,e in enumerate(lst):
        if not status[i]:
            continue
        status[i] = False
        did_merge = False
        for j,f in enumerate(lst):
            if not status[j]:
                continue
            r = maybe_merge_both(e,f)
            if r:
                status[j] = False
                new_lst.append(r)
                did_merge = True
                break

        if not did_merge:
            new_lst.append(e)

    if len(lst) == len(new_lst):
        return new_lst
    else:
        return normalize_grid(new_lst)

# Gantt-drawing class

class Calendar(object):
    """
    Draw timeline rows onto an existing PDF object. The page will be
    broken as needed.
    """

    def __init__(self,pdf,
            first_date=date.today(),
            unit='week',
            length=10,
            label_width=50.0,
            show_year=True,
            one_based=False,
            ):
        self.pdf = pdf

        self.unit = unit
        if self.unit == 'week':
            self.normalize = monday
            self.prev = prev_week
            self.next = next_week
            self.fmt = '%d %b'
            self.dur = n_weeks
        elif self.unit == 'month':
            self.normalize = first
            self.prev = prev_month
            self.next = next_month
            self.fmt = '%b'
            self.dur = n_months

        self.first_date = self.normalize(first_date)
        self.show_year = show_year
        self.nunit = length
        self.label_width = label_width
        self.row_height = 6.0
        self.milestone_radius = 1.1
        self.one_based = one_based
        self.t_margin = 3.0
        self.r_margin = 15.0
        self.b_margin = 16.0
        self.unit_width = (self.pdf.w - self.label_width -
                self.pdf.get_x() -
                self.r_margin)/float(self.nunit)
        self.highlight = False
        self.next_row = 0
        self.dep_segments = []

    def _new_row(self):
        """
        Return co-ordinates of the start of the row: usually this will
        be the current position, but if we're too close to the bottom
        of the page this will dump out all current dependency lines
        then insert a page break.
        """
        p = Point(x=self.pdf.get_x(), y=self.pdf.get_y())
        if p.y > self.pdf.h - self.b_margin:
            self._really_draw_deps()
            self.dep_segments = []
            self.next_row = 0
            self.pdf.add_page()
            self.draw_time_axis()
            return self._new_row()
        else:
            return p

    def finish(self):
        """
        Draw any remaining things on the timeline chart.
        """
        self._really_draw_deps()
        self.dep_segments = []
    
    def _get_label_size(self,txt=None,size=7.0,width=None):
        if txt is None:
            if self.unit == 'week':
                txt = '30 May'
            else:
                txt = 'May'
        if width is None:
            width = self.unit_width
        while 1:
            self.pdf.set_font('Arial', '', size)
            if self.pdf.get_string_width(txt) > \
                    width - 2.0:
                size -= 0.1
            else:
                return size

    def draw_time_axis(self):
        """
        Draw a time axis along the top of the chart.
        """
        start = self._new_row()
        size = self._get_label_size()

        unit = self.first_date
        for i in range(0,self.nunit+1):
            self.pdf.set_draw_color(200)
            self.pdf.set_line_width(0.3)
            self.pdf.line(start.x+self.label_width+i*self.unit_width,
                    start.y+self.t_margin,
                    start.x+self.label_width+i*self.unit_width,
                    start.y+self.t_margin+6.0)
            if i < self.nunit:
                self.pdf.set_text_color(10.0)
                self.pdf.set_font('Arial', '', size)
                self.pdf.set_xy(
                        start.x+self.label_width+i*self.unit_width,
                        start.y+self.t_margin)
                self.pdf.write(3.0, unit.strftime(self.fmt))
                if self.show_year and \
                        ((unit.month == 1 and unit.day < 7) or i == 0):
                    self.pdf.set_xy(
                            start.x+self.label_width+i*self.unit_width,
                            start.y+self.t_margin-3.0)
                    self.pdf.set_font('Arial', 'B', 5.0)
                    self.pdf.write(3.0, unit.strftime('%Y'))
                self.pdf.set_xy(
                        start.x+self.label_width+i*self.unit_width,
                        start.y+self.t_margin+3.0)
                self.pdf.set_font('Arial', '', 5.0)
                if self.one_based:
                    number = "%d" % (i + 1,)
                else:
                    number = "%d" % i
                self.pdf.write(3.0, number)
                unit = self.next(unit)

        self.pdf.set_xy(start.x, start.y+self.t_margin*2.0+6.0)

    def next_highlight(self,val):
        """
        For the next row to have (or not have) a highlight. Normal
        alternating will resume with the row after.
        """
        self.highlight = val

    def _draw_highlight(self):
        """
        Draw highlight, if this row is due to have one.
        """
        if self.highlight:
            start = self._new_row()
            self.pdf.set_fill_color(240)
            self.pdf.rect(
                    start.x,
                    start.y,
                    self.pdf.w - start.x - self.r_margin + 1.5,
                    self.row_height,
                    'F')
        self.highlight = not self.highlight
        self.next_row += 1
        return
    
    def draw_key(self,label,color):
        """
        Draw a row to be used as a key: a label followed by a single
        fixed-width work block
        """
        start = self._new_row()
        self._draw_highlight()
        self.pdf.set_text_color(100)
        self.pdf.set_font('Arial', '', 10.0)
        self.pdf.cell(self.label_width,self.row_height,label,ln=0)
        if color is None:
            self.pdf.set_fill_color(150)
        else:
            self.pdf.set_fill_color(*color)
        self.pdf.rect(
                start.x + self.label_width,
                start.y + 1.0,
                40.0,
                self.row_height - 2.0,
                'F')
        self.pdf.set_xy(start.x, start.y+self.row_height)

    def draw_gap(self,label=None):
        """
        Draw a gap row: just a label in bold, nothing on the timeline.
        """
        start = self._new_row()
        self._draw_highlight()
        if label:
            self.pdf.set_text_color(0)
            self.pdf.set_font('Arial', 'B', 10.0)
            self.pdf.cell(self.label_width * 2.0,self.row_height,label,ln=0)
        self.pdf.set_y(self.pdf.get_y()+self.row_height)

    def draw_work(self,label,at,length,color=None,key=None):
        """
        Draw a work row: shaded block from unit at for length units,
        optionally with a given colour and key label.
        """
        start = self._new_row()
        self._draw_highlight()
        self.pdf.set_text_color(100)
        self.pdf.set_font('Arial', '', 10.0)
        self.pdf.cell(self.label_width,self.row_height,label,ln=0)
        if color is None:
            self.pdf.set_fill_color(150)
        else:
            self.pdf.set_fill_color(*color)
        self.pdf.rect(
                start.x + self.label_width + at * self.unit_width,
                start.y + 1.0,
                length * self.unit_width,
                self.row_height - 2.0,
                'F')

        if key is not None:
            self.pdf.set_text_color(240)
            if color is not None and (color[0] + color[1] + color[2])/3 > 200:
                self.pdf.set_text_color(100)
            self.pdf.set_font('Arial', '', 7.0)
            self.pdf.set_xy(
                    start.x + self.label_width + at * self.unit_width,
                    start.y
                    )
            if self.pdf.get_string_width(key) < length * self.unit_width:
                self.pdf.write(self.row_height,key)
            self.pdf.set_xy(start.x, start.y+self.row_height)
        
        self.pdf.set_xy(start.x, start.y+self.row_height)

    def draw_breaks(self,label,*lst):
        """
        Draw a row of breaks: outlined boxes conveying an period
        controlled by an external factor. lst consists of
        (label,at,length) tuples.
        """
        self._draw_multi(label,'breaks',*lst)
    
    def draw_phases(self,label,*lst):
        """
        Draw a row of phases: horizontal brackets conveying an
        overall period designated as a project phase.  lst consists of
        (label,at,length) tuples.
        """
        self._draw_multi(label,'phases',*lst)
        
    def _draw_multi(self,label,kind,*lst):
        """
        Common function for drawing breaks for phases.
        """
        start = self._new_row()
        self._draw_highlight()
        self.pdf.set_text_color(100)
        self.pdf.set_font('Arial', '', 10.0)
        self.pdf.cell(self.label_width,self.row_height,label,ln=0)
        for txt,at,length in lst:
            size = self._get_label_size(txt,7.0,length * self.unit_width)
            self.pdf.set_font('Arial', '', size)

            if kind == 'breaks':
                self.pdf.set_xy(
                        start.x + self.label_width + at * self.unit_width,
                        start.y
                        )
            elif kind == 'phases':
                self.pdf.set_xy(
                        start.x + self.label_width + at * self.unit_width + 1.0,
                        start.y
                        )

            self.pdf.write(
                    self.row_height,txt)
            self.pdf.set_draw_color(100)

            if kind == 'breaks':
                self.pdf.rect(
                        start.x + self.label_width + at * self.unit_width,
                        start.y + 1.0,
                        length * self.unit_width,
                        self.row_height - 2.0,
                        'D')
            elif kind == 'phases':
                self.pdf.line(
                        start.x + self.label_width + at * self.unit_width + 1.5,
                        start.y + 1.0,
                        start.x + self.label_width + (at+length) * self.unit_width - 1.5,
                        start.y + 1.0)
                self.pdf.line(
                        start.x + self.label_width + at * self.unit_width + 0.5,
                        start.y + 2.0,
                        start.x + self.label_width + at * self.unit_width + 1.5,
                        start.y + 1.0)
                self.pdf.line(
                        start.x + self.label_width + (at+length) * self.unit_width - 0.5,
                        start.y + 2.0,
                        start.x + self.label_width + (at+length) * self.unit_width - 1.5,
                        start.y + 1.0)
        
        self.pdf.set_xy(start.x, start.y+self.row_height)

    def draw_milestone(self,label,at):
        """
        Draw a milestone row: a dot at a given time unit.
        """
        start = self._new_row()
        self._draw_highlight()
        self.pdf.set_text_color(100)
        self.pdf.set_font('Arial', 'I', 10.0)
        self.pdf.cell(self.label_width,self.row_height,label,ln=0)
        self.pdf.set_fill_color(30)
        self.pdf.ellipse(
                start.x + self.label_width + at * self.unit_width - self.milestone_radius,
                start.y + self.row_height / 2.0 - self.milestone_radius,
                2.0 * self.milestone_radius,
                2.0 * self.milestone_radius,
                'F')
        self.pdf.set_xy(start.x, start.y+self.row_height)

    def draw_dep(self,frm,to,up):
        """
        Overlay a dependency starting at unit from on the row up rows
        above the last-drawn one, to unit to on the current row.
        (Actual drawing of dependency lines is deferred to
        _really_draw_deps(), to avoid overlayed dashed lines.)
        """
        if up >= self.next_row:
            up = float(self.next_row) - 0.5
        start = Point(x=self.pdf.get_x(), y=self.pdf.get_y()-self.row_height)
        self.pdf.set_draw_color(100)
        self.pdf.set_line_width(0.3)
        if to > frm:
            self.dep_segments.append(
                    (
                        Point(
                            start.x + self.label_width + frm * self.unit_width,
                            start.y + self.row_height / 2.0),
                        Point(
                            start.x + self.label_width + to * self.unit_width,
                            start.y + self.row_height / 2.0)
                    ))
        self.dep_segments.append(
                (
                    Point(
                        start.x + self.label_width + frm * self.unit_width,
                        start.y + self.row_height / 2.0 - self.row_height * up),
                    Point(
                        start.x + self.label_width + frm * self.unit_width,
                        start.y + self.row_height / 2.0)
                ))

    def _really_draw_deps(self):
        """
        Normalize and draw dependency lines on the current page.
        Normalization removes any duplicated segments so there is no
        interference between dash phase.
        """
        self.dep_segments = normalize_grid(self.dep_segments)
        for line in self.dep_segments:
            self.pdf.dashed_line(
                    line[0].x,
                    line[0].y,
                    line[1].x,
                    line[1].y,
                    0.6,0.8)

# functions for parsing the project object

def find_item(regex,project):
    """
    Find an item by name in the project structure.
    """
    m = re.match('([+-])(.*)', regex)
    if m:
        regex = m.group(2)
    for item in project['rows']:
        if re.match(regex + r'\b', item['name'], re.I):
            return item
    return None

def find_at(spec,project):
    """
    Parse the 'at' element of a project item, following a reference
    chain as needed to get a concrete time value.
    """
    type_ = type(spec)

    if get_option('one_based',project):
        offset = 1.0
    else:
        offset = 0.0

    if type_ == date:
        if project['unit'] == 'month':
            return n_months(first(project['start']),spec)
        elif project['unit'] == 'week':
            return n_weeks(monday(project['start']),spec)

    if type_ == int or type_ == float:
        return spec - offset

    elif type_ == str:
        m = re.match(r'([+-])(.*)', spec)
        if m:
            end = m.group(1)
            regex = m.group(2)
        else:
            end = '+'
            regex = spec

        parent = find_item(regex,project)
        parent_at, parent_length = get_timing(parent,project)

        if end == '+':
            at = parent_at + parent_length
        elif end == '-':
            at = parent_at
        return at

    elif type_ == list:
        parent_at = find_at(spec[0],project)
        at = parent_at + spec[1]
        return at

def get_timing(item,project):
    """
    Find the duration of an item, returning 0 for milestones.
    """
    at = find_at(item['at'],project)
    if 'length' in item:
        length = item['length']
    else:
        length = 0
    return (at, length)

def get_key(key,project):
    """
    Find a key (colour and label) to apply to a work block.
    """
    for try_key in project['keys']:
        if re.match(key+r'\b',try_key['name'],re.I):
            return try_key
    return None

def get_option(name,project,default=None):
    """
    Get an option flag from the project structure, returning None if
    the flag is not defined.
    """
    if 'options' not in project:
        return default
    if name not in project['options']:
        return default
    return project['options'][name]

# main function to read filename (.yml) and draw corresponding .pdf

def draw(filename):

    if HAVE_PYKWALIFY:
        srcdir = \
            os.path.dirname(
                    os.path.abspath(
                        inspect.getfile(inspect.currentframe())))

        validator = pykwalify.core.Core(source_file=filename,
                schema_files=[
                    os.path.join(srcdir,"schema.yml")])
        try:
            validator.validate(raise_exception=True)
        except pykwalify.errors.SchemaError, e:
            print "Error: input schema validation error"
            print e.msg
            sys.exit(1)
        
        with file(filename,'r') as fh:
            project = yaml.load(fh.read())

    n = 0
    for item in project['rows']:
        item['n'] = n
        n += 1

    pdf = FPDF('L','mm','A4')
    pdf.set_auto_page_break(False)
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    title = get_option('title',project,'%s timeline' % project['project'])
    if title:
        pdf.cell(80,10,'%s timeline' % (project['project'],),ln=2)

    cal = Calendar(pdf,
            unit=project['unit'],
            length=project['length'],
            first_date=project['start'],
            show_year=get_option('show_year',project),
            label_width=get_option('label_width',project,50.0),
            one_based=get_option('one_based',project),
            )
    cal.draw_time_axis()

    n = -1
    for item in project['rows']:
        n += 1

        if 'stripe' in item:
            cal.next_highlight(item['stripe'])

        if 'gap' in item and item['gap']:
            cal.draw_gap(item['name'])
            continue

        if 'breaks' in item:
            breaks = []
            for b in item['breaks']:
                tup = (b['name'], find_at(b['at'],project), b['length'])
                breaks.append(tup)
            cal.draw_breaks(item['name'], *breaks)
            continue

        if 'phases' in item:
            phases = []
            for b in item['phases']:
                tup = (b['name'], find_at(b['at'],project), b['length'])
                phases.append(tup)
            cal.draw_phases(item['name'], *phases)
            continue

        at, length = get_timing(item,project)

        if 'length' in item:
            if 'key' in item:
                key = get_key(item['key'], project)
                color = key['color']
                key_name = key['name']
            else:
                color = None
                key_name = None
            if not get_option('key_in_block',project):
                key_name = None
            cal.draw_work(item['name'], at, length, color, key_name)
        else:
            cal.draw_milestone(item['name'], at)

        if 'dep' in item:
            if type(item['dep']) != list:
                deps = [item['dep']]
            else:
                deps = item['dep']
            for dep in deps:
                dep_start = find_at(dep,project)
                dep_item  = find_item(dep,project)
                dep_up = n - dep_item['n']
                if dep_start > at:
                    print "Warning: '%s' before its dependency '%s'" % (
                        item['name'], dep_item['name'])
                cal.draw_dep(dep_start, at, dep_up)
   
    cal.finish()

    if 'keys' in project and get_option('key_legend',project):
        if pdf.h - pdf.get_y()  < (10.0 + 10.0 + 
                cal.row_height * len(project['keys']) + cal.b_margin):
            pdf.add_page()
        pdf.set_y(pdf.get_y() + 10.0)
        pdf.set_text_color(0)
        pdf.set_font('Arial', '', 14)
        pdf.cell(80,10,'Key',ln=2)
        cal.highlight = False

        for key in project['keys']:
            cal.draw_key(key['name'], key['color'])

    footer = get_option('footer', project,
        '%s timeline / version %s / built %s' %
            (project['project'],
                project['version'],
                date.today().strftime("%d %b %Y")))
    if footer:
        pdf.set_text_color(100)
        pdf.set_font('Arial', '', 8.0)
        pdf.set_y(pdf.h-15.0)
        pdf.write(10,footer)

    pdf.output(re.sub(r'\.yml$','.pdf',sys.argv[1]))

# toplevel

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "Usage: uproject.py [input.yml]"
        sys.exit(1)
    draw(sys.argv[1])
