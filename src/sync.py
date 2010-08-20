#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#       sync.py
#       
#       Copyright 2010 Sven Festersen <sven@sven-festersen.de>
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
import threading
from simple_db.database import DataBase
import ftplib
import gtk
import gobject
import pygtk


class ErrorDialog(gtk.Dialog):
    
    def __init__(self, message):
        super(ErrorDialog, self).__init__("Error syncing tasks")
        self._msg = message
        
        table = gtk.Table(2, 2)
        table.set_row_spacings(6)
        table.set_col_spacings(6)
        table.set_border_width(12)
        self.vbox.pack_start(table, False, False)
        
        img = gtk.image_new_from_stock(gtk.STOCK_DIALOG_ERROR, gtk.ICON_SIZE_DIALOG)
        img.set_alignment(0.5, 0)
        table.attach(img, 0, 1, 0, 2, xoptions=gtk.FILL|gtk.SHRINK, yoptions=gtk.FILL|gtk.SHRINK)
        
        label = gtk.Label()
        label.set_alignment(0, 0.5)
        label.set_markup("<b>Error syncing tasks</b>")
        table.attach(label, 1, 2, 0, 1, xoptions=gtk.FILL|gtk.EXPAND, yoptions=gtk.SHRINK)
        
        label = gtk.Label()
        label.set_markup(message)
        label.set_alignment(0, 0)
        table.attach(label, 1, 2, 1, 2, xoptions=gtk.FILL|gtk.EXPAND, yoptions=gtk.SHRINK)
        
        self.add_button(gtk.STOCK_OK, gtk.RESPONSE_ACCEPT)
        
        self.show_all()
        
        
class RetryErrorDialog(ErrorDialog):
    
    def __init__(self, msg):
        super(RetryErrorDialog, self).__init__(msg)
        self.add_button("Retry", gtk.RESPONSE_REJECT)
        
        
class ForceErrorDialog(RetryErrorDialog):
    
    def __init__(self, msg):
        super(ForceErrorDialog, self).__init__(msg)
        self.add_button("Force sync", gtk.RESPONSE_CANCEL)
        

def show_error_dialog(msg):
    gtk.gdk.threads_enter()
    d = ErrorDialog(msg)
    d.run()
    d.destroy()
    gtk.gdk.threads_leave()
    
    
def show_retry_error_dialog(msg, cb_again):
    gtk.gdk.threads_enter()
    d = RetryErrorDialog(msg)
    resp = d.run()
    if resp == gtk.RESPONSE_REJECT:
        cb_again()
    d.destroy()
    gtk.gdk.threads_leave()
    
    
def show_force_error_dialog(msg, cb_again, cb_force):
    gtk.gdk.threads_enter()
    d = ForceErrorDialog(msg)
    resp = d.run()
    if resp == gtk.RESPONSE_REJECT:
        cb_again()
    elif resp == gtk.RESPONSE_CANCEL:
        cb_force()
    d.destroy()
    gtk.gdk.threads_leave()


def stor_callback(data):
    f = open("/tmp/.task_db.xml", "ab")
    f.write(data)
    f.close()
    

def sync_tasks(local_db, prototype, ftp_server, ftp_username, ftp_password, ftp_dir, cb_finish, force):
    #1. connect
    try:
        ftp = ftplib.FTP(ftp_server, ftp_username, ftp_password)
        print "connected"
    except:
        show_error_dialog("Can't connect to host <i>%s</i>.\nPlease check your connection settings." % ftp_server)
        return False
        
    #2. change to ftp_dir
    try:
        ftp.cwd(ftp_dir)
        print "changed dir"
    except:
        ftp.quit()
        show_error_dialog("It seems the directory <i>%s</i>\ndoes not exists on the server." % ftp_dir)
        return False
        
    #3. check whether sync lock can be acquired
    files = ftp.nlst()
    if ".task-lock" in files and not force:
        #can't acquire lock
        def try_again():
            t = SyncThread(local_db, prototype, ftp_server, ftp_username, ftp_password, ftp_dir, cb_finish)
            t.start()
        def force():
            t = SyncThread(local_db, prototype, ftp_server, ftp_username, ftp_password, ftp_dir, cb_finish, True)
            t.start()
        show_force_error_dialog("Can't acquire an exclusive lock on the remote data.\nEither another application is using the data\nor a previous synchronization attempt failed.\n\nYou can retry or force the sync. Forcing it may result in data loss!\nClick Ok to abort.", try_again, force)
        ftp.quit()
        return False
    
    #4. acquire lock
    try:
        f = open("/dev/null", "r")
        ftp.storlines("STOR .task-lock", f)
        f.close()
        print "lock acquired"
    except:
        ftp.quit()
        show_error_dialog("Error writing data to server. Please check permissions.")
        return False
    
    #5. download database file if it exists
    if ".task_db.xml" in files:
        f = open("/tmp/.task_db.xml", "w")
        f.write("")
        f.close()
        try:
            ftp.retrbinary("RETR .task_db.xml", stor_callback)
            print "file downloaded"
        except:
            ftp.quit()
            show_error_dialog("Error downloading data from server. Please check permissions.")
            return False
        
    #6. create database and sync
    try:
        remote_db = DataBase("/tmp/.task_db.xml", prototype)
        local_db.sync("ftp", remote_db)
        remote_db.commit()
        local_db.commit()
        print "synced"
    except:
        def try_again():
            t = SyncThread(local_db, prototype, ftp_server, ftp_username, ftp_password, ftp_dir, cb_finish)
            t.start()
        show_retry_error_dialog("Can't sync databases.", try_again)
        ftp.quit()
        return False
    
    #7. upload db
    try:
        f = open("/tmp/.task_db.xml", "r")
        ftp.storlines("STOR .task_db.xml", f)
        f.close()
        print "file uploaded"
    except:
        show_error_dialog("Error writing data to server. Please check permissions.")
        ftp.quit()
        return False
    
    #8. release lock
    try:
        ftp.delete(".task-lock")
        print "lock released"
    except:
        show_error_dialog("Error writing data to server. Please check permissions.")
        ftp.quit()
        return False

    ftp.quit()
    gobject.idle_add(cb_finish)
    return True


class SyncThread(threading.Thread):
    
    def __init__(self, local_db, prototype, ftp_server, ftp_username, ftp_password, ftp_dir, cb_finish, force=False):
        super(SyncThread, self).__init__()
        self._local_db = local_db
        self._prototype = prototype
        self._ftp_server = ftp_server
        self._ftp_username = ftp_username
        self._ftp_password = ftp_password
        self._ftp_dir = ftp_dir
        self._cb_finish = cb_finish
        self._force = force
        
    def run(self):
        res = sync_tasks(self._local_db, self._prototype, self._ftp_server, self._ftp_username, self._ftp_password, self._ftp_dir, self._cb_finish, self._force)
