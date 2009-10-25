#!/usr/bin/env python
#
#       theme.py
#
#       Copyright 2009 Sven Festersen <sven@sven-festersen.de>
#
#       This program is free software; you can redistribute it and/or modify
#       it under the terms of the GNU General Public License as published by
#       the Free Software Foundation; either version 2 of the License, or
#       (at your option) any later version.
#
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#       GNU General Public License for more details.
#
#       You should have received a copy of the GNU General Public License
#       along with this program; if not, write to the Free Software
#       Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#       MA 02110-1301, USA.
import cairo
import ConfigParser
import math


def parse_color_rgba(color):
    if color[0] == '#':
        color = color[1:]
    (r, g, b, a) = (int(color[:2], 16),
                    int(color[2:4], 16),
                    int(color[4:6], 16),
                    int(color[6:], 16))
    return (r / 255.0, g / 255.0, b / 255.0, a / 255.0)
    
def draw_rectangle(ctx, x, y, w, h, r):
    ctx.move_to(x, y + r)
    ctx.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    ctx.rel_line_to(w - 2 * r, 0)
    ctx.arc(x + w - r, y + r, r, 1.5 * math.pi, 2 * math.pi)
    ctx.rel_line_to(0, h - 2 * r)
    ctx.arc(x + w - r, y + h - r, r, 0, 0.5 * math.pi)
    ctx.rel_line_to(- (w - 2 * r), 0)
    ctx.arc(x + r, y + h - r, r, 0.5 * math.pi, math.pi)
    #ctx.rel_line_to(0, - (h - 2 * r))
    ctx.close_path()


class ThemeInfo:

    cornerRadius = 0
    borderWidth = 0
    borderColor = parse_color_rgba("#2e3436ff")
    backgroundColor = parse_color_rgba("#2e3436ff")
    foregroundColor = parse_color_rgba("#ffffffff")
    scaleBorder = True
    scaleCorners = True

    def __init__(self, filename):
        conf = ConfigParser.SafeConfigParser()
        conf.read(filename)

        if not conf.has_section("Colors"):
            conf.add_section("Colors")
        if not conf.has_section("Layout"):
            conf.add_section("Layout")

        if conf.has_option("Colors", "backgroundColor"):
            self.backgroundColor = parse_color_rgba(conf.get("Colors", "backgroundColor"))
        if conf.has_option("Colors", "borderColor"):
            self.borderColor = parse_color_rgba(conf.get("Colors", "borderColor"))
        if conf.has_option("Colors", "foregroundColor"):
            self.foregroundColor = parse_color_rgba(conf.get("Colors", "foregroundColor"))
        if conf.has_option("Layout", "cornerRadius"):
            self.cornerRadius = conf.getint("Layout", "cornerRadius")
        if conf.has_option("Layout", "borderWidth"):
            self.borderWidth = conf.getint("Layout", "borderWidth")
        if conf.has_option("Layout", "scaleBorder"):
            self.scaleBorder = conf.getboolean("Layout", "scaleBorder")
        if conf.has_option("Layout", "scaleCorners"):
            self.scaleCorners = conf.getboolean("Layout", "scaleCorners")
            
    def draw_background(self, ctx, width, height, scale=1.0):
        bscale = scale
        cscale = scale
        if self.scaleBorder:
            bscale = 1.0
        if self.scaleCorners:
            cscale = 1.0
            
        outerCornerRadius = min(self.cornerRadius / cscale, min(width / 2, height / 2))
            
        innerCornerRadius = max(0, outerCornerRadius - self.borderWidth / bscale)
        ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        ctx.set_source_rgba(*self.borderColor)
        draw_rectangle(ctx, 0, 0, width, height, outerCornerRadius)
        draw_rectangle(ctx, self.borderWidth / bscale, self.borderWidth / bscale, width - 2 * self.borderWidth / bscale, height - 2 * self.borderWidth / bscale, innerCornerRadius)
        ctx.fill()
        ctx.set_source_rgba(*self.backgroundColor)
        draw_rectangle(ctx, self.borderWidth / bscale, self.borderWidth / bscale, width - 2 * self.borderWidth / bscale, height - 2 * self.borderWidth / bscale, innerCornerRadius)
        ctx.fill()
