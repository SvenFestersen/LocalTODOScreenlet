#!/usr/bin/env python
#
#       backend.py
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
FEATURE_DUE_DATE = 0
FEATURE_COMMENT = 1

class TaskBackend:
    
    supported_features = (FEATURE_COMMENT, FEATURE_DUE_DATE)
    
    def __init__(self, cb_tasks_loaded, cb_task_added, cb_task_removed, cb_task_updated, cb_task_error):
        self._cb_tl = cb_tasks_loaded
        self._cb_ta = cb_task_added
        self._cb_tr = cb_task_removed
        self._cb_tu = cb_task_updated
        self._cb_te = cb_task_error
        
    def load_tasks(self):
        self._cb_te("Feature not implemented.")
        
    def add_task(self, title):
        self._cb_te("Feature not implemented.")
        
    def remove_task(self, id):
        self._cb_te("Feature not implemented.")
        
    def update_task(self, id, title, done, date, comment):
        self._cb_te("Feature not implemented.")
        
    def save_tasks(self):
        pass
        
    def close(self):
        self.save_tasks()
        
    
