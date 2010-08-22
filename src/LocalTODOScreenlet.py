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
import time
from xml.sax.saxutils import escape

from simple_db.database import DataBase
from simple_db.dataobject import DataObject
import sync
import theme


def color_hex_rgba_to_float(color):
    """
    Convert a color in hex format #rrggbbaa to a color in float format
    (r, g, b, a) with r, g, b, a in [0, 1].
    """
    if color[0] == '#':
        color = color[1:]
    (r, g, b, a) = (int(color[:2], 16),
                    int(color[2:4], 16), 
                    int(color[4:6], 16),
                    int(color[6:], 16))
    return (r / 255.0, g / 255.0, b / 255.0, a / 255.0)

def color_rgba_to_hex(color):
    """
    Convert a float rgba (r, g, b, a) color to rgb hex format #rrggbb.
    The alpha value is omitted.
    """
    return color_float_to_hex((color[0], color[1], color[2]))
    
def color_float_to_hex((r, g, b)):
    """
    Convert a flot rgb color (r, g, b) to hex format #rrggbb.
    """
    r = hex(int(255 * r))[2:]
    g = hex(int(255 * g))[2:]
    b = hex(int(255 * b))[2:]
    if len(r) == 1: r = "0" + r
    if len(g) == 1: g = "0" + g
    if len(b) == 1: b = "0" + b
    return "#" + r + g + b

def get_timestamp_from_calendar(calendar):
    """
    Returns a timestamp from a selected day in gtk.Calendar.
    """
    y, m, d = calendar.get_date()
    m += 1 #month starts at 0
    dt = datetime.datetime(y, m, d, 0, 0, 1)
    return int(time.mktime(dt.timetuple()))
    
def update_field_for_id(treeview, id, n, value):
    """
    This updates the nth field with id in in a ListStore with value.
    """
    model = treeview.get_model()
    for i in range(0, len(model)):
        if model[i][0] == id:
            model[i][n] = value
            break
            
def rearrange_items(treeview):
    """
    Sorts task in a treeview by due date.
    """
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
    """
    Calculates the difference between timestamp and now in an integer number
    of days.
    """
    now = datetime.datetime.fromtimestamp(time.time())
    tmp = datetime.datetime.fromtimestamp(timestamp)
    
    now = datetime.datetime(now.year, now.month, now.day, 0, 0, 1)
    tmp = datetime.datetime(tmp.year, tmp.month, tmp.day, 0, 0, 1)
    delta = tmp - now
    return delta.days
    
def recolor_items(treeview, colors):
    """
    Colors tasks in treeview according to their due date.
    """
    offsets = colors.keys()
    offsets.sort()
    offsets.reverse()
    model = treeview.get_model()
    for i in range(0, len(model)):
        due = model[i][3]
        c = (0, 0, 0, 1)
        if due != -1:
            days = get_day_diff(due)
            for offset in offsets:
                if days <= offset:
                    c = colors[offset]
        model[i][5] = color_rgba_to_hex(c)
        
def get_due_string(due_date, date_format):
    """
    Makes the due date string for task tooltips.
    """
    dt = datetime.date.fromtimestamp(due_date)
    txt = "Due on %s." % dt.strftime(date_format)
    if get_day_diff(due_date) == 1:
        txt += " (tomorrow)"
    elif get_day_diff(due_date) == 0:
        txt += " (today)"
    return txt
    
    
class Task(DataObject):
    """
    The task prototype for the database.
    """
    fields = ["title", "comment", "due_date", "done"]


class DataMenuItem(gtk.MenuItem):
    """
    gtk.MenuItem with an extra data attribute.
    """
    
    def __init__(self, label):
        gtk.MenuItem.__init__(self, label)
        self.data = None


class DataImageMenuItem(gtk.ImageMenuItem):
    """
    gtk.ImageMenuItem with an extra data attribute.
    """
    
    def __init__(self, stock_id=None, accel_group=None):
        gtk.ImageMenuItem.__init__(self, stock_id, accel_group)
        self.data = None
        
        
class DialogDueDate(gtk.Dialog):
    """
    Dialog to set a task's due date.
    """
    
    def __init__(self, title, date):
        gtk.Dialog.__init__(self, "Choose a due date")
        self._date = date
        
        vbox = gtk.VBox()
        vbox.set_border_width(12)
        vbox.set_spacing(6)
        self.vbox.pack_start(vbox, False, False)
        
        txt = "The task <i>%s</i> is due on:" % title
        l = gtk.Label()
        l.set_markup(txt)
        l.set_alignment(0.0, 0.5)
        vbox.pack_start(l, False, False)
        
        self._radio_never = gtk.RadioButton(label="never")
        self._radio_never.connect("toggled", self._cb_toggle_radio, "never")
        vbox.pack_start(self._radio_never, False, False)
        
        self._radio_date = gtk.RadioButton(group=self._radio_never, \
                                            label="this date:")
        self._radio_date.connect("toggled", self._cb_toggle_radio, "date")
        vbox.pack_start(self._radio_date, False, False)
        
        self._calendar = gtk.Calendar()
        self._calendar.set_sensitive(False)
        vbox.pack_start(self._calendar, False, False)
        
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
    """
    Dialog to edit a task's comment.
    """
    
    def __init__(self, title, comment):
        gtk.Dialog.__init__(self, "Edit comment")
        self.set_default_size(300, 0)
        
        vbox = gtk.VBox()
        vbox.set_border_width(12)
        vbox.set_spacing(6)
        self.vbox.pack_start(vbox, False, False)
        
        txt = "Comment for task <i>%s</i>:" % title
        l = gtk.Label()
        l.set_markup(txt)
        l.set_alignment(0.0, 0.5)
        vbox.pack_start(l, False, False)
        
        self._textview = gtk.TextView()
        self._textview.set_wrap_mode(gtk.WRAP_WORD)
        self._textview.get_buffer().set_text(comment)
        
        sw = gtk.ScrolledWindow()
        sw.set_shadow_type(gtk.SHADOW_IN)
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.add(self._textview)
        
        vbox.pack_start(sw)
        
        self.vbox.show_all()
        
        self.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT)
        self.add_button(gtk.STOCK_OK, gtk.RESPONSE_ACCEPT)
        
    def get_comment(self):
        buffer = self._textview.get_buffer()
        start = buffer.get_start_iter()
        end = buffer.get_end_iter()
        return buffer.get_text(start, end)


class LocalTODOScreenlet(screenlets.Screenlet):
    """
    This Screenlet shows a simple todo list. Tasks are stored in the file
    ~/.task_db.xml.
    Synchronization of the tasks with a file on a ftp server is possible.
    """

    __name__    = 'LocalTODOScreenlet'
    __version__ = 'Beta'
    __author__  = 'Sven Festersen'
    __desc__    = __doc__

    default_width = 200
    default_height = 250
    color_overdue = color_hex_rgba_to_float("#a40000ff")
    color_today = color_hex_rgba_to_float("#4e9a06ff")
    color_tomorrow = color_hex_rgba_to_float("#204a87ff")
    date_format = "%a, %d. %b %Y"
    ftp_server = ""
    ftp_dir = "/"
    ftp_username = ""
    ftp_password = ""
    ftp_interval = 15
    ftp_auto_sync = True
    _last_sync = 0

    def __init__ (self, **keyword_args):
        screenlets.Screenlet.__init__(self, width=self.default_width, \
                                        height=self.default_height, \
                                        uses_theme=True, is_widget=False, \
                                        is_sticky=True, **keyword_args)
        self.theme_name = "BlackSquared"
        
        self._colors = {-1: self.color_overdue,
                        0: self.color_today,
                        1: self.color_tomorrow}
        
        self.add_options_group("TODO", "TODO list settings")
        
        opt_color_overdue = ColorOption("TODO", "color_overdue", \
                                        self.color_overdue, \
                                        "Color of overdue tasks", \
                                        "The color that overdue tasks should \
                                        have.")
        self.add_option(opt_color_overdue)
        
        opt_color_today = ColorOption("TODO", "color_today", self.color_today, \
                                        "Color of tasks due today", \
                                        "The color that tasks which are due \
                                        today should have.")
        self.add_option(opt_color_today)
        
        opt_color_tomorrow = ColorOption("TODO", "color_tomorrow", \
                                            self.color_tomorrow, \
                                            "Color of tasks due tomorrow", \
                                            "The color that tasks which are \
                                            due tomorrow should have.")
        self.add_option(opt_color_tomorrow)
        
        opt_date_format = StringOption("TODO", "date_format", \
                                        self.date_format, "Due date format", \
                                        "The format of the due date shown on \
                                        hovering a task.")
        self.add_option(opt_date_format)
        
        self.add_options_group("Synchronization", "Settings for \
                                synchronization via FTP")
        
        opt_ftp_server = StringOption("Synchronization", "ftp_server", \
                                        self.ftp_server, "FTP server", \
                                        "The host name or the host address of \
                                        the ftp server.")
        self.add_option(opt_ftp_server)
        
        opt_ftp_username = StringOption("Synchronization", "ftp_username", \
                                        self.ftp_username, "Username", \
                                        "Username for ftp login.")
        self.add_option(opt_ftp_username)
        
        opt_ftp_password = StringOption("Synchronization", "ftp_password", \
                                        self.ftp_password, "Password", \
                                        "Password for ftp login.", \
                                        password=True)
        self.add_option(opt_ftp_password)
                        
        opt_ftp_dir = StringOption("Synchronization", "ftp_dir", self.ftp_dir, \
                                    "Directory", "Directory on the server in \
                                    which the tasks should be stored.")
        self.add_option(opt_ftp_dir)
        
        opt_ftp_auto = BoolOption("Synchronization", "ftp_auto_sync", self.ftp_auto_sync, "Sync automatically", "Set whether to sync automatically.")
        self.add_option(opt_ftp_auto)
        
        opt_ftp_interval = IntOption("Synchronization", "ftp_interval", self.ftp_interval, "Sync interval (minutes)", "Synchronization interval in minutes.", min=1, max=120)
        self.add_option(opt_ftp_interval)
        
        self._init_tree()
        
        self._tasks_init()
        
        self.window.show_all()
        self._check_sync()
        gobject.timeout_add(60000, self._check_sync)
    
    def on_init(self):
        self.add_default_menuitems()
    
    def on_after_set_atribute(self, name, value):
        if name.startswith("color"):
            self._colors = {-1: self.color_overdue,
                        0: self.color_today,
                        1: self.color_tomorrow}
            recolor_items(self.treeview, self._colors)
    
    #theming stuff
    def on_load_theme(self):
        self.theme["info"] = theme.ThemeInfo(self.theme.path + "/theme.conf")
        
    def on_scale (self):
        try:
            self._renderer_title.set_property("wrap-width", \
                                                self.scale * self.width - 60)
            self._renderer_title.set_property("wrap-mode", pango.WRAP_WORD)
        except:
            pass
            
    def on_draw (self, ctx):
        if self.theme == None:
            return
        ctx.scale(self.scale, self.scale)
        self.theme["info"].draw_background(ctx, self.default_width, \
                                            self.default_height, self.scale)

    def on_draw_shape (self, ctx):
        if self.theme:
            self.on_draw(ctx)

    #treeview stuff
    def _init_tree(self):
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.set_border_width(10)
        #init data model: id, title, done, date, comment, title color
        model = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING, \
                                gobject.TYPE_BOOLEAN, gobject.TYPE_INT, \
                                gobject.TYPE_STRING, gobject.TYPE_STRING) 
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
        col = gtk.TreeViewColumn("Task", self._renderer_title, text=1, \
                                    strikethrough=2, foreground=5)
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
        self.menu_item_add.set_image(gtk.image_new_from_stock(gtk.STOCK_ADD, \
                                        gtk.ICON_SIZE_MENU))
        self.menu_item_add.connect("activate", self._cb_new_task)
        self.popup_menu.append(self.menu_item_add)
        
        self.popup_menu.append(gtk.SeparatorMenuItem())
        
        self.menu_item_del = DataImageMenuItem()
        self.menu_item_del.set_label("Delete Task")
        img = gtk.image_new_from_stock(gtk.STOCK_DELETE, gtk.ICON_SIZE_MENU)
        self.menu_item_del.set_image(img)
        self.menu_item_del.connect("activate", self._cb_del_task)
        self.popup_menu.append(self.menu_item_del)
        
        self.menu_item_due = DataMenuItem("Set due date")
        self.menu_item_due.connect("activate", self._cb_due_date)
        self.popup_menu.append(self.menu_item_due)
        
        self.menu_item_comment = DataImageMenuItem()
        self.menu_item_comment.set_label("Edit comment")
        img = gtk.image_new_from_stock(gtk.STOCK_EDIT, gtk.ICON_SIZE_MENU)
        self.menu_item_comment.set_image(img)
        self.menu_item_comment.connect("activate", self._cb_comment_task)
        self.popup_menu.append(self.menu_item_comment)
        
        self.popup_menu.append(gtk.SeparatorMenuItem())
    
        self.menu_item_sync = gtk.ImageMenuItem()
        self.menu_item_sync.set_label("Sync tasks")
        img = gtk.image_new_from_stock(gtk.STOCK_REFRESH, gtk.ICON_SIZE_MENU)
        self.menu_item_sync.set_image(img)
        self.menu_item_sync.set_sensitive(False)
        self.menu_item_sync.connect("activate", self._cb_sync)
        self.popup_menu.append(self.menu_item_sync)
        
        self.popup_menu.append(gtk.SeparatorMenuItem())
    
        self.menu_item_settings = gtk.ImageMenuItem()
        self.menu_item_settings.set_label("Settings")
        img = gtk.image_new_from_stock(gtk.STOCK_PREFERENCES, \
                                        gtk.ICON_SIZE_MENU)
        self.menu_item_settings.set_image(img)
        self.menu_item_settings.connect("activate", self._cb_settings)
        self.popup_menu.append(self.menu_item_settings)
        
        self.popup_menu.show_all()
        
    #task stuff
    def _tasks_init(self):
        self.db = DataBase(os.path.expanduser("~/.task_db.xml"), Task)
        if not self.db.has_sync_source("ftp"):
            self.db.add_sync_source("ftp")
        self._tasks_load()
        
    def _tasks_load(self):
        tasks = self.db.query(sort_func=lambda x,y: cmp(x["due_date"], \
                                                    y["due_date"]))
        model = self.treeview.get_model()
        model.clear()
        for task in tasks:
            model.set(model.append(None), 0, task.id, 1, task["title"], 2, \
                        task["done"], 3, task["due_date"], 4, task["comment"])
        recolor_items(self.treeview, self._colors)
        
    def _tasks_add(self):
        id = str(time.time())
        t = Task(id)
        t["done"] = False
        t["due_date"] = -1
        t["comment"] = ""
        self.db.add(t)
        model = self.treeview.get_model()
        model.set(model.append(None), 0, id, 1, "New task", 2, False, 3, -1, \
                    4, "")
        self.db.commit()
        
    #callbacks
    def on_after_set_atribute(self, name, value):
        if name == "ftp_server" and value != "":
            self.menu_item_sync.set_sensitive(True)
    
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
        
    def _cb_settings(self, widget):
        self.show_settings_dialog()
        
    def _cb_sync(self, widget):
        t = sync.SyncThread(self.db, Task, self.ftp_server, self.ftp_username, \
                            self.ftp_password, self.ftp_dir, \
                            self._cb_sync_finished)
        t.start()
        
    def _cb_sync_finished(self):
        self._tasks_load()
        self._last_sync = time.time()
        
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
                tooltip.set_text(get_due_string(due_date, self.date_format))
                return True
            elif comment != "" and due_date == -1:
                tooltip.set_markup('<b>Comment:</b>\n%s' % comment)
                return True
            elif comment != "" and due_date != -1:
                due_str = get_due_string(due_date, self.date_format)
                tooltip.set_markup('%s\n\n<b>Comment:</b>\n%s' % (due_str, \
                                                                    comment))
                return True
                
    def _check_sync(self):
        if time.time() - self._last_sync >= self.ftp_interval * 60 and \
            self.ftp_auto_sync and self.ftp_server != "":
            self._cb_sync(None)
        return True
            

if __name__ == '__main__':
    gtk.gdk.threads_init()
    import screenlets.session
    screenlets.session.create_session(LocalTODOScreenlet)
