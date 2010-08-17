#!/usr/bin/env python
#
#       LocalTODOScreenlet
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

import datetime
import gtk
import gobject
import os
import pango
import screenlets
from screenlets.options import ColorOption, IntOption, BoolOption, StringOption
import sys
import time
from xml.sax.saxutils import escape

from simple_db.database import DataBase
from simple_db.dataobject import DataObject
import theme


def color_hex_rgba_to_float(color):
    if color[0] == '#':
        color = color[1:]
    (r, g, b, a) = (int(color[:2], 16),
                    int(color[2:4], 16), 
                    int(color[4:6], 16),
                    int(color[6:], 16))
    return (r / 255.0, g / 255.0, b / 255.0, a / 255.0)

def color_hex_to_float(color):
    if color[0] == '#':
        color = color[1:]
    (r, g, b) = (int(color[:2], 16),
                    int(color[2:4], 16), 
                    int(color[4:], 16))
    return (r / 255.0, g / 255.0, b / 255.0)

def color_rgba_to_hex(color):
    return color_float_to_hex((color[0], color[1], color[2]))
    
def color_float_to_hex((r, g, b)):
    r = hex(int(255 * r))[2:]
    g = hex(int(255 * g))[2:]
    b = hex(int(255 * b))[2:]
    if len(r) == 1: r = "0" + r
    if len(g) == 1: g = "0" + g
    if len(b) == 1: b = "0" + b
    return "#" + r + g + b

def get_timestamp_from_calendar(calendar):
    y, m, d = calendar.get_date()
    m += 1 #month starts at 0
    dt = datetime.datetime(y, m, d, 0, 0, 1)
    return int(time.mktime(dt.timetuple()))
        
def pixbuf_new_from_icon_name(name, size):
    theme = gtk.icon_theme_get_default()
    icon = theme.lookup_icon(name, size, gtk.ICON_LOOKUP_FORCE_SVG)
    return icon.load_icon()
    
def update_field_for_id(treeview, id, n, value):
    model = treeview.get_model()
    for i in range(0, len(model)):
        if model[i][0] == id:
            model[i][n] = value
            break
            
def rearrange_items(treeview):
    model = treeview.get_model()
    items = {}
    for i in range(0, len(model)):
        items[i] = model[i][3]
        
    keys = items.keys()
    keys.sort(lambda x, y: cmp(items[x], items[y]))
    new_order = []
    for x in keys:
        new_order.append(x)
    model.reorder(new_order)
    
def get_day_diff(timestamp):
    now = datetime.datetime.fromtimestamp(time.time())
    tmp = datetime.datetime.fromtimestamp(timestamp)
    
    now = datetime.datetime(now.year, now.month, now.day, 0, 0, 1)
    tmp = datetime.datetime(tmp.year, tmp.month, tmp.day, 0, 0, 1)
    delta = tmp - now
    return delta.days
    
def recolor_items(treeview, colors):
    offsets = colors.keys()
    offsets.sort()
    offsets.reverse()
    model = treeview.get_model()
    for i in range(0, len(model)):
        due = model[i][3]
        c = (0, 0, 0)
        if due != -1:
            days = get_day_diff(due)
            for offset in offsets:
                if days <= offset:
                    c = colors[offset]
        model[i][5] = color_rgba_to_hex(c)
    
class Task(DataObject):
    
    fields = ["title", "comment", "due_date", "done"]


class DataMenuItem(gtk.MenuItem):
    
    def __init__(self, label):
        gtk.MenuItem.__init__(self, label)
        self.data = None


class DataImageMenuItem(gtk.ImageMenuItem):
    
    def __init__(self, stock_id=None, accel_group=None):
        gtk.ImageMenuItem.__init__(self, stock_id, accel_group)
        self.data = None
        
        
class DialogDueDate(gtk.Dialog):
    
    def __init__(self, title, date):
        gtk.Dialog.__init__(self, "Choose a due date")
        self._date = date
        
        txt = "The task <i>%s</i> is due on:" % title
        l = gtk.Label()
        l.set_markup(txt)
        l.set_alignment(0.0, 0.5)
        self.vbox.pack_start(l, False, False)
        
        self._radio_never = gtk.RadioButton(label="never")
        self._radio_never.connect("toggled", self._cb_toggle_radio, "never")
        self.vbox.pack_start(self._radio_never, False, False)
        
        self._radio_date = gtk.RadioButton(group=self._radio_never, label="this date:")
        self._radio_date.connect("toggled", self._cb_toggle_radio, "date")
        self.vbox.pack_start(self._radio_date, False, False)
        
        self._calendar = gtk.Calendar()
        self._calendar.set_sensitive(False)
        self.vbox.pack_start(self._calendar, False, False)
        
        if date != -1:
            dt = datetime.datetime.fromtimestamp(date)
            self._calendar.select_month(dt.month - 1, dt.year)
            self._calendar.select_day(dt.day)
            self._radio_date.set_active(True)
        
        self.vbox.show_all()
        
        self._calendar.connect("day-selected", self._cb_day_selected)
        self.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT)
        self.add_button(gtk.STOCK_OK, gtk.RESPONSE_ACCEPT)
        
    def _cb_toggle_radio(self, radio, type):
        if self._radio_never.get_active():
            self._date = -1
            self._calendar.set_sensitive(False)
        elif self._radio_date.get_active():
            self._calendar.set_sensitive(True)
            self._date = get_timestamp_from_calendar(self._calendar)
            
    def _cb_day_selected(self, calendar):
        if self._radio_date.get_active():
            self._date = get_timestamp_from_calendar(calendar)
            
    def get_date(self):
        return self._date
        
        
class DialogComment(gtk.Dialog):
    
    def __init__(self, title, comment):
        gtk.Dialog.__init__(self, "Edit comment")
        
        txt = "Comment for task <i>%s</i>:" % title
        l = gtk.Label()
        l.set_markup(txt)
        l.set_alignment(0.0, 0.5)
        self.vbox.pack_start(l, False, False)
        
        self._textview = gtk.TextView()
        self._textview.set_wrap_mode(gtk.WRAP_WORD)
        self._textview.get_buffer().set_text(comment)
        
        sw = gtk.ScrolledWindow()
        sw.set_shadow_type(gtk.SHADOW_IN)
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.add(self._textview)
        
        self.vbox.pack_start(sw)
        
        self.vbox.show_all()
        
        self.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT)
        self.add_button(gtk.STOCK_OK, gtk.RESPONSE_ACCEPT)
        
    def get_comment(self):
        buffer = self._textview.get_buffer()
        start = buffer.get_start_iter()
        end = buffer.get_end_iter()
        return buffer.get_text(start, end)


class LocalTODOScreenlet(screenlets.Screenlet):
    """This Screenlet shows a simple todo list. A local file (~/.tasks.xml) is used to store the list."""

    __name__    = 'LocalTODOScreenlet'
    __version__ = 'Beta'
    __author__  = 'Sven Festersen'
    __desc__    = __doc__

    default_width = 250
    default_height = 300
    color_overdue = color_hex_rgba_to_float("#a40000ff")#(0.64313725490196083, 0.0, 0.0, 1.0)
    color_today = color_hex_rgba_to_float("#204a87ff")#(0.12549019607843137, 0.29019607843137257, 0.52941176470588236, 1.0)
    color_tomorrow = color_hex_rgba_to_float("#4e9a06ff")
    show_comment_bubble = True
    date_format = "%a, %d. %b %Y"

    def __init__ (self, **keyword_args):
        screenlets.Screenlet.__init__(self, width=self.default_width, height=self.default_height, uses_theme=True, is_widget=False, is_sticky=True, **keyword_args)
        self.theme_name = "BlackSquared"
        
        self.add_options_group("TODO", "TODO list settings")
        
        opt_color_overdue = ColorOption("TODO", "color_overdue", self.color_overdue, "Color of overdue tasks", "The color that overdue tasks should have.")
        self.add_option(opt_color_overdue)
        
        opt_color_today = ColorOption("TODO", "color_today", self.color_today, "Color of tasks due today", "The color that tasks which are due today should have.")
        self.add_option(opt_color_today)
        
        opt_comment_bubble = BoolOption("TODO", "show_comment_bubble", self.show_comment_bubble, "Show comment bubble", "Show a speech bubble next to the checkbox if the task has a comment. Hover the bubble with your mouse to see the comment.")
        self.add_option(opt_comment_bubble)
        
        opt_date_format = StringOption("TODO", "date_format", self.date_format, "Due date format", "The format of the due date shown on hovering a task.")
        self.add_option(opt_date_format)
        
        self._colors = {-1: self.color_overdue,
                        0: self.color_today,
                        1: self.color_tomorrow}
                        
        
        self._init_tree()
        
        self._tasks_init()
        
        self.window.show_all()
    
    def on_init(self):
        self.add_default_menuitems()
    
    #theming stuff
    def on_load_theme(self):
        self.theme["info"] = theme.ThemeInfo(self.theme.path + "/theme.conf")
        
    def on_scale (self):
        try:
            self._renderer_title.set_property("wrap-width", self.scale * self.width - 60)
            self._renderer_title.set_property("wrap-mode", pango.WRAP_WORD)
        except:
            pass
            
    def on_draw (self, ctx):
        if self.theme == None:
            return
        ctx.scale(self.scale, self.scale)
        self.theme["info"].draw_background(ctx, self.default_width, self.default_height, self.scale)

    def on_draw_shape (self, ctx):
        if self.theme:
            self.on_draw(ctx)

    #treeview stuff
    def _init_tree(self):
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.set_border_width(10)
        model = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_BOOLEAN, gobject.TYPE_INT, gobject.TYPE_STRING, gobject.TYPE_STRING, gtk.gdk.Pixbuf) #id, title, done, date, comment, title color, comment bubble
        self.treeview = gtk.TreeView(model)
        self.treeview.set_headers_visible(False)
        
        renderer = gtk.CellRendererToggle()
        renderer.connect("toggled", self._cb_task_done_toggled)
        col = gtk.TreeViewColumn("", renderer, active=2)
        col.set_resizable(False)
        col.set_min_width(22)
        col.set_max_width(22)
        self.treeview.append_column(col)
        
        self._renderer_title = gtk.CellRendererText()
        self._renderer_title.set_property("editable", True)
        self._renderer_title.connect("edited", self._cb_task_title_edited)
        col = gtk.TreeViewColumn("Task", self._renderer_title, text=1, strikethrough=2, foreground=5)
        self.treeview.append_column(col)
        
        self.treeview.set_has_tooltip(True)
        
        sw.add(self.treeview)
        self.window.add(sw)
        
        self._init_tree_popup()
        
        self.treeview.connect("event", self._cb_treeview_event)
        self.treeview.connect("query-tooltip", self._cb_treeview_query_tooltip)
        
    def _init_tree_popup(self):
        self.popup_menu = gtk.Menu()
        
        self.menu_item_add = gtk.ImageMenuItem()
        self.menu_item_add.set_label("New Task")
        self.menu_item_add.set_image(gtk.image_new_from_stock(gtk.STOCK_ADD, gtk.ICON_SIZE_MENU))
        self.menu_item_add.connect("activate", self._cb_new_task)
        self.popup_menu.append(self.menu_item_add)
        
        self.popup_menu.append(gtk.SeparatorMenuItem())
        
        self.menu_item_del = DataImageMenuItem()
        self.menu_item_del.set_label("Delete Task")
        self.menu_item_del.set_image(gtk.image_new_from_stock(gtk.STOCK_DELETE, gtk.ICON_SIZE_MENU))
        self.menu_item_del.connect("activate", self._cb_del_task)
        self.popup_menu.append(self.menu_item_del)
        
        self.menu_item_due = DataMenuItem("Set due date")
        self.menu_item_due.connect("activate", self._cb_due_date)
        self.popup_menu.append(self.menu_item_due)
        
        self.menu_item_comment = DataImageMenuItem()
        self.menu_item_comment.set_label("Edit comment")
        self.menu_item_comment.set_image(gtk.image_new_from_stock(gtk.STOCK_EDIT, gtk.ICON_SIZE_MENU))
        self.menu_item_comment.connect("activate", self._cb_comment_task)
        self.popup_menu.append(self.menu_item_comment)
        
        self.popup_menu.show_all()
        
    #task stuff
    def _tasks_init(self):
        self.db = DataBase(os.path.expanduser("~/.task_db.xml"), Task)
        self._tasks_load()
        
    def _tasks_load(self):
        tasks = self.db.query(sort_func=lambda x,y: cmp(x["due_date"], y["due_date"]))
        model = self.treeview.get_model()
        for task in tasks:
            model.set(model.append(None), 0, task.id, 1, task["title"], 2, task["done"], 3, task["due_date"], 4, task["comment"])
        recolor_items(self.treeview, self._colors)
        
    def _tasks_add(self):
        id = str(time.time())
        t = Task(id)
        t["done"] = False
        t["due_date"] = -1
        self.db.add(t)
        model = self.treeview.get_model()
        model.set(model.append(None), 0, id, 1, "New task")
        self.db.commit()
        
    #callbacks
    def _cb_new_task(self, widget):
        self._tasks_add()
        
    def _cb_del_task(self, widget):
        id = widget.data
        del self.db[id]
        self.db.commit()
        model = self.treeview.get_model()
        for i in range(0, len(model)):
            if model[i][0] == id:
                del model[i]
                break
                
    def _cb_due_date(self, widget):
        id = widget.data
        d = DialogDueDate(self.db[id]["title"], self.db[id]["due_date"])
        response = d.run()
        if response == gtk.RESPONSE_ACCEPT:
            due_date = d.get_date()
            self.db[id]["due_date"] = due_date
            self.db.commit()
            update_field_for_id(self.treeview, id, 3, due_date)
            rearrange_items(self.treeview)
            recolor_items(self.treeview, self._colors)
        d.destroy()
        
    def _cb_comment_task(self, widget):
        id = widget.data
        d = DialogComment(self.db[id]["title"], self.db[id]["comment"])
        response = d.run()
        if response == gtk.RESPONSE_ACCEPT:
            comment = d.get_comment()
            self.db[id]["comment"] = comment
            self.db.commit()
            update_field_for_id(self.treeview, id, 4, comment)
        d.destroy()
        
    def _cb_treeview_event(self, treeview, event):
        if event.type == gtk.gdk.BUTTON_PRESS and event.button == 3:
            self.popup_menu.popup(None, None, None, event.button, event.time)
            treedata = self.treeview.get_path_at_pos(int(event.x), int(event.y))
            if treedata != None:
                #right click on a task
                p = treedata[0]
                model = treeview.get_model()
                iter = model.get_iter(p)
                id = model.get_value(iter, 0)
                self.menu_item_del.data = id
                self.menu_item_due.data = id
                self.menu_item_comment.data = id
                self.menu_item_del.set_sensitive(True)
                self.menu_item_due.set_sensitive(True)
                self.menu_item_comment.set_sensitive(True)
            else:
                #right click on empty list
                self.menu_item_del.set_sensitive(False)
                self.menu_item_due.set_sensitive(False)
                self.menu_item_comment.set_sensitive(False)
                
    def _cb_task_done_toggled(self, renderer, path):
        model = self.treeview.get_model()
        iter = model.get_iter(path)
        done = not model.get_value(iter, 2)
        model.set(iter, 2, done)
        self.db[model.get_value(iter, 0)]["done"] = done
        self.db.commit()
        
    def _cb_task_title_edited(self, renderer, path, title):
        model = self.treeview.get_model()
        iter = model.get_iter(path)
        model.set(iter, 1, title)
        self.db[model.get_value(iter, 0)]["title"] = title
        self.db.commit()
        
    def _cb_treeview_query_tooltip(self, widget, x, y, kb, tooltip):
        treedata = self.treeview.get_path_at_pos(x, y)
        if treedata != None:
            p = treedata[0]
            model = self.treeview.get_model()
            iter = model.get_iter(p)
            due_date = model.get_value(iter, 3)
            comment = escape(model.get_value(iter, 4).strip())
            if comment == "" and due_date == -1:
                return False
            elif comment == "" and due_date != -1:
                tooltip.set_text("Due on %s." % datetime.date.fromtimestamp(due_date).strftime(self.date_format))
                return True
            elif comment != "" and due_date == -1:
                tooltip.set_markup('<b>Comment:</b>\n%s' % comment)
                return True
            elif comment != "" and due_date != -1:
                tooltip.set_markup('Due on %s.\n\n<b>Comment:</b>\n%s' % (datetime.date.fromtimestamp(due_date).strftime(self.date_format), comment))
                return True

if __name__ == '__main__':
    import screenlets.session
    screenlets.session.create_session(LocalTODOScreenlet)
