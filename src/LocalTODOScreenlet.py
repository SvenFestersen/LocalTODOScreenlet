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

import backend
import backend_xml
import theme


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
    
def cmp_dates(x, y):
    if (x >= 0 and y >= 0) or x == y:
        return cmp(x, y)
    elif x >= 0 and y == -1:
        return -1
    elif x == -1 and y >= 0:
        return 1
        
def get_color_for_date(timestamp, colors):
    now = time.time()
    if (now - timestamp) <= 0 or timestamp == -1:
        return colors["other"]
    elif (3600 * 24) >= (now - timestamp) > 0:
        return colors["today"]
    elif (now - timestamp) > (3600 * 24):
        return colors["overdue"]
        
def pixbuf_new_from_icon_name(name, size):
    theme = gtk.icon_theme_get_default()
    icon = theme.lookup_icon(name, size, gtk.ICON_LOOKUP_FORCE_SVG)
    return icon.load_icon()


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
    color_overdue = (0.64313725490196083, 0.0, 0.0, 1.0)
    color_today = (0.12549019607843137, 0.29019607843137257, 0.52941176470588236, 1.0)
    auto_refresh = 60
    show_comment_bubble = True
    date_format = "%a, %d. %b %Y"
    _last_update = 0
    _comment_pb = None

    def __init__ (self, **keyword_args):
        screenlets.Screenlet.__init__(self, width=self.default_width, height=self.default_height, uses_theme=True, is_widget=False, is_sticky=True, **keyword_args)
        self.theme_name = "BlackSquared"
        
        self._backend = backend_xml.XMLTaskBackend(os.path.expanduser("~/.tasks.xml"), self._cb_backend_tasks_loaded, self._cb_backend_task_added, self._cb_backend_task_removed, self._cb_backend_task_updated, self._cb_backend_task_error)
        
        self.add_options_group("TODO", "TODO list settings")
        
        opt_color_overdue = ColorOption("TODO", "color_overdue", self.color_overdue, "Color of overdue tasks", "The color that overdue tasks should have.")
        self.add_option(opt_color_overdue)
        
        opt_color_today = ColorOption("TODO", "color_today", self.color_today, "Color of tasks due today", "The color that tasks which are due today should have.")
        self.add_option(opt_color_today)
        
        opt_auto_refresh = IntOption("TODO", "auto_refresh", self.auto_refresh, "Reload tasks after (seconds)", "The interval length in seconds after that task should be reloaded. 0 means no automatic reload.", 0, 3600)
        self.add_option(opt_auto_refresh)
        
        opt_comment_bubble = BoolOption("TODO", "show_comment_bubble", self.show_comment_bubble, "Show comment bubble", "Show a speech bubble next to the checkbox if the task has a comment. Hover the bubble with your mouse to see the comment.")
        self.add_option(opt_comment_bubble)
        
        opt_date_format = StringOption("TODO", "date_format", self.date_format, "Due date format", "The format of the due date shown on hovering a task.")
        self.add_option(opt_date_format)
        
        vbox = gtk.VBox()
        vbox.set_border_width(10)
        self._init_tree(vbox)
        self._init_popup_menu()
        self.window.add(vbox)
        self.window.show_all()
        
        self._load_tasks()
        gobject.timeout_add(1000, self._cb_update)
    
    def on_init(self):
        self.add_default_menuitems()
        
    def on_load_theme(self):
        self.theme["info"] = theme.ThemeInfo(self.theme.path + "/theme.conf")
        if os.path.exists(self.theme.path + "/comment.png"):
            self._comment_pb = gtk.gdk.pixbuf_new_from_file(self.theme.path + "/comment.png")
        else:
            self._comment_pb = pixbuf_new_from_icon_name("gtk-info", 16)
            
        #update the comment icons:
        try:
            model = self.treeview.get_model()
            for row in model:
                if row[6] != None:
                    row[6] = self._comment_pb
        except:
            #gui was not created yet...
            pass
        
    def on_scale (self):
        try:
            self._renderer_title.set_property("wrap-width", self.scale * self.width - 60)
            self._renderer_title.set_property("wrap-mode", pango.WRAP_WORD)
        except:
            pass
            
    def on_after_set_atribute(self,name, value):
        if name == "show_comment_bubble":
            self._set_show_comment_bubble(value)

    def _init_tree(self, vbox):
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        model = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_BOOLEAN, gobject.TYPE_INT, gobject.TYPE_STRING, gobject.TYPE_STRING, gtk.gdk.Pixbuf) #id, title, done, date, comment, title color, comment bubble
        self.treeview = gtk.TreeView(model)
        self.treeview.set_headers_visible(False)
        self.treeview.connect("event", self._cb_treeview_event)
        self.treeview.connect("query-tooltip", self._cb_treeview_query_tooltip)
        
        renderer = gtk.CellRendererToggle()
        renderer.connect("toggled", self._cb_update_task_done)
        col = gtk.TreeViewColumn("", renderer, active=2)
        col.set_resizable(False)
        col.set_min_width(22)
        col.set_max_width(22)
        self.treeview.append_column(col)
        
        self._renderer_title = gtk.CellRendererText()
        self._renderer_title.set_property("editable", True)
        self._renderer_title.connect("edited", self._cb_update_task_title)
        col = gtk.TreeViewColumn("Task", self._renderer_title, text=1, strikethrough=2, foreground=5)
        self.treeview.append_column(col)
        
        self.treeview.set_has_tooltip(True)
        
        sw.add(self.treeview)
        vbox.pack_start(sw)
        
        self._set_show_comment_bubble(self.show_comment_bubble)
        
    def _set_show_comment_bubble(self, show):
        current_cols = self.treeview.get_columns()
        if show and len(current_cols) == 2:
            renderer = gtk.CellRendererPixbuf()
            col = gtk.TreeViewColumn("", renderer, pixbuf=6)
            col.set_resizable(False)
            col.set_min_width(22)
            col.set_max_width(22)
            self.treeview.insert_column(col, 1)
        elif not show and len(current_cols) == 3:
            self.treeview.remove_column(self.treeview.get_column(1))
            
    def _init_popup_menu(self):
        self._popup_menu = gtk.Menu()
    
        self._popup_item_new = gtk.ImageMenuItem(gtk.STOCK_ADD)
        self._popup_item_new.get_children()[0].set_text("Add task")
        self._popup_item_new.connect("activate", self._cb_add_task)
        self._popup_menu.append(self._popup_item_new)
        
        self._popup_item_reload = gtk.ImageMenuItem(gtk.STOCK_REFRESH)
        self._popup_item_reload.get_children()[0].set_text("Reload tasks")
        self._popup_item_reload.connect("activate", self._cb_reload_tasks)
        self._popup_menu.append(self._popup_item_reload)
        
        self._popup_menu.append(gtk.SeparatorMenuItem())
        
        if backend.FEATURE_DUE_DATE in self._backend.supported_features:
            #backend supports due dates => add due date menu item
            self._popup_item_due_date = DataMenuItem("Set due date")
            self._popup_item_due_date.connect("activate", self._cb_choose_due_date)
            self._popup_menu.append(self._popup_item_due_date)
        
        if backend.FEATURE_COMMENT in self._backend.supported_features:
            #backend supports comments => add comment menu item
            self._popup_item_comment = DataImageMenuItem(gtk.STOCK_EDIT)
            self._popup_item_comment.get_children()[0].set_text("Edit comment")
            self._popup_item_comment.connect("activate", self._cb_edit_comment)
            self._popup_menu.append(self._popup_item_comment)
        
        if backend.FEATURE_COMMENT in self._backend.supported_features or backend.FEATURE_DUE_DATE in self._backend.supported_features:
            #backend supports due dates or comments => add extra separator
            self._popup_menu.append(gtk.SeparatorMenuItem())
        
        self._popup_item_clear = DataImageMenuItem(gtk.STOCK_CLEAR)
        self._popup_item_clear.get_children()[0].set_text("Remove done tasks")
        self._popup_item_clear.connect("activate", self._cb_remove_done_tasks)
        self._popup_menu.append(self._popup_item_clear)
        
        self._popup_item_remove = DataImageMenuItem(gtk.STOCK_REMOVE)
        self._popup_item_remove.get_children()[0].set_text("Remove task")
        self._popup_item_remove.connect("activate", self._cb_remove_task)
        self._popup_menu.append(self._popup_item_remove)
        
    def _load_tasks(self):
        model = self.treeview.get_model()
        model.clear()
        self._backend.load_tasks()
        self._last_update = time.time()

    def on_draw (self, ctx):
        if self.theme == None:
            return
        ctx.scale(self.scale, self.scale)
        self.theme["info"].draw_background(ctx, self.default_width, self.default_height, self.scale)

    def on_draw_shape (self, ctx):
        if self.theme:
            self.on_draw(ctx)
            
    def _cb_treeview_event(self, widget, event):
        if event.type == gtk.gdk.BUTTON_PRESS and event.button == 3:
            info = self.treeview.get_path_at_pos(int(event.x), int(event.y))
            if info:
                #task at (event.x, event.y) => activate task specific menu items
                self._popup_item_remove.set_sensitive(True)
                self._popup_item_remove.data = info[0]
                if backend.FEATURE_DUE_DATE in self._backend.supported_features:
                    #backend supports due dates
                    self._popup_item_due_date.set_sensitive(True)
                    self._popup_item_due_date.data = info[0]
                if backend.FEATURE_COMMENT in self._backend.supported_features:
                    #backend supports comments
                    self._popup_item_comment.set_sensitive(True)
                    self._popup_item_comment.data = info[0]
            else:
                #no task at (event.x, event.y) => deactivate task specific menu items
                self._popup_item_remove.set_sensitive(False)
                if backend.FEATURE_DUE_DATE in self._backend.supported_features:
                    #backend supports due dates
                    self._popup_item_due_date.set_sensitive(False)
                if backend.FEATURE_COMMENT in self._backend.supported_features:
                    #backend supports comments
                    self._popup_item_comment.set_sensitive(False)
            self._popup_menu.popup(None, None, None, event.button, event.time)
            self._popup_menu.show_all()
            
    def _cb_treeview_query_tooltip(self, widget, x, y, kb, tooltip):
        pos = widget.get_path_at_pos(x, y)
        if pos:
            model = widget.get_model()
            iter = model.get_iter(pos[0])
            col = pos[1]
            markup = ""
            if self.show_comment_bubble and col == widget.get_column(1):
                comment = model.get_value(iter, 4)
                if comment.strip():
                    markup = "<b>Comment:</b>\n%s" % escape(comment.strip())
            elif self.show_comment_bubble and col == widget.get_column(2):
                due_date = model.get_value(iter, 3)
                if due_date != -1:
                    d = datetime.date.fromtimestamp(due_date)
                    markup = "Due on %s." % d.strftime(self.date_format)
            elif not self.show_comment_bubble and col == widget.get_column(1):
                due_date = model.get_value(iter, 3)
                if due_date != -1:
                    d = datetime.date.fromtimestamp(due_date)
                    markup = "Due on %s." % d.strftime(self.date_format)
                comment = model.get_value(iter, 4)
                if comment.strip():
                    if markup: markup += "\n\n"
                    markup += "<b>Comment:</b>\n%s" % escape(comment.strip())
                
            if markup:
                tooltip.set_markup(markup)
                return True
                    
        return False
            
    def _cb_update(self):
        now = time.time()
        if now - self._last_update >= self.auto_refresh and self.auto_refresh != 0:
            self._load_tasks()
        return True
            
    #Treeview callbacks
    def _cb_add_task(self, widget):
        self._backend.add_task("New task")
        
    def _cb_reload_tasks(self, menuitem):
        self._load_tasks()
        
    def _cb_update_task_title(self, renderer, path, title):
        model = self.treeview.get_model()
        iter = model.get_iter(path)
        id = model.get_value(iter, 0)
        done = model.get_value(iter, 2)
        date = model.get_value(iter, 3)
        comment = model.get_value(iter, 4)
        self._backend.update_task(id, title, done, date, comment)
        
    def _cb_update_task_done(self, renderer, path):
        model = self.treeview.get_model()
        iter = model.get_iter(path)
        id = model.get_value(iter, 0)
        title = model.get_value(iter, 1)
        done = not model.get_value(iter, 2)
        date = model.get_value(iter, 3)
        comment = model.get_value(iter, 4)
        self._backend.update_task(id, title, done, date, comment)
        
    def _cb_remove_task(self, dataimagemenuitem):
        path = dataimagemenuitem.data
        model = self.treeview.get_model()
        iter = model.get_iter(path)
        id = model.get_value(iter, 0)
        self._backend.remove_task(id)
        
    def _cb_remove_done_tasks(self, menuitem):
        remove = []
        model = self.treeview.get_model()
        for row in model:
            if row[2]:
                remove.append(row[0])
        for id in remove:
            self._backend.remove_task(id)
            
    def _cb_choose_due_date(self, datamenuitem):
        path = datamenuitem.data
        model = self.treeview.get_model()
        iter = model.get_iter(path)
        id = model.get_value(iter, 0)
        title = model.get_value(iter, 1)
        done = model.get_value(iter, 2)
        date = model.get_value(iter, 3)
        comment = model.get_value(iter, 4)
        
        d = DialogDueDate(title, date)
        response = d.run()
        date = d.get_date()
        d.destroy()
        if response == gtk.RESPONSE_ACCEPT:
            self._backend.update_task(id, title, done, date, comment)
            
    def _cb_edit_comment(self, dataimagemenuitem):
        path = dataimagemenuitem.data
        model = self.treeview.get_model()
        iter = model.get_iter(path)
        id = model.get_value(iter, 0)
        title = model.get_value(iter, 1)
        done = model.get_value(iter, 2)
        date = model.get_value(iter, 3)
        comment = model.get_value(iter, 4)
        
        d = DialogComment(title, comment)
        response = d.run()
        comment = d.get_comment()
        d.destroy()
        if response == gtk.RESPONSE_ACCEPT:
            self._backend.update_task(id, title, done, date, comment)
            
    #Backend callbacks
    def _cb_backend_tasks_loaded(self, tasks):
        gobject.idle_add(self._async_backend_tasks_loaded, tasks)
        
    def _cb_backend_task_added(self, id, title):
        gobject.idle_add(self._async_backend_task_added, id, title)
        
    def _cb_backend_task_removed(self, id):
        gobject.idle_add(self._async_backend_task_removed, id)
        
    def _cb_backend_task_updated(self, id, title, done, date, comment):
        gobject.idle_add(self._async_backend_task_updated, id, title, done, date, comment)
        
    def _cb_backend_task_error(self, msg):
        print "Backend error:", msg
        
    #Asynchronous handlers for backend callbacks
    def _async_backend_tasks_loaded(self, tasks):
        k = tasks.keys()
        
        k.sort(lambda x, y: cmp(tasks[x][0].lower(), tasks[y][0].lower()))
        k.sort(lambda x, y: cmp_dates(tasks[x][2], tasks[y][2]))
        
        model = self.treeview.get_model()
        for id in k:
            title, done, date, comment = tasks[id]
            color = get_color_for_date(date, {"overdue": color_rgba_to_hex(self.color_overdue), "today": color_rgba_to_hex(self.color_today), "other": self.window.get_style().fg[gtk.STATE_NORMAL].to_string()})
            comment_pb = None
            if comment.strip():
                comment_pb = self._comment_pb
            model.set(model.append(None), 0, id, 1, title, 2, done, 3, date, 4, comment, 5, color, 6, comment_pb)
            
    def _async_backend_task_added(self, id, title):
        model = self.treeview.get_model()
        iter = model.append(None)
        model.set(iter, 0, id, 1, title, 2, False, 3, -1, 4, "", 5, self.window.get_style().fg[gtk.STATE_NORMAL].to_string())
        path = model.get_path(iter)
        self.treeview.set_cursor_on_cell(path, self.treeview.get_column(1), None, True)
        
    def _async_backend_task_removed(self, id):
        model = self.treeview.get_model()
        rem = -1
        for i, row in enumerate(model):
            if row[0] == id:
                rem = i
                break
        if rem != -1:
            del model[rem]
        
    def _async_backend_task_updated(self, id, title, done, date, comment):
        model = self.treeview.get_model()
        for row in model:
            if row[0] == id:
                row[1] = title
                row[2] = done
                row[3] = date
                row[4] = comment
                row[5] = get_color_for_date(date, {"overdue": color_rgba_to_hex(self.color_overdue), "today": color_rgba_to_hex(self.color_today), "other": self.window.get_style().fg[gtk.STATE_NORMAL].to_string()})
                if comment.strip():
                    row[6] = self._comment_pb
                else:
                    row[6] = None
                break

if __name__ == '__main__':
    import screenlets.session
    screenlets.session.create_session(LocalTODOScreenlet)
