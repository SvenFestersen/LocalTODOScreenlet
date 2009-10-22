#!/usr/bin/env python
#
#       backend_xml.py
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
import hashlib
import os
import time
from xml.dom.minidom import parse

import backend


def getText(nodelist):
    """
    From minidom example at
    http://docs.python.org/library/xml.dom.minidom.html
    """
    rc = ""
    for node in nodelist:
        if node.nodeType == node.TEXT_NODE:
            rc = rc + node.data
    return rc
    

class XMLTaskBackend(backend.TaskBackend):
    
    supported_features = (backend.FEATURE_COMMENT, backend.FEATURE_DUE_DATE)
    
    def __init__(self, filename, cb_tasks_loaded, cb_task_added, cb_task_removed, cb_task_updated, cb_task_error):
        backend.TaskBackend.__init__(self, cb_tasks_loaded, cb_task_added, cb_task_removed, cb_task_updated, cb_task_error)
        self._filename = filename
        self._tasks = {}
        if not os.path.exists(filename):
            f = open(filename, "w")
            f.write('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<tasklist>\n</tasklist>')
            f.close()
        
    def load_tasks(self):
        self._tasks = {}
        dom = parse(self._filename)
        node_tasklist = dom.getElementsByTagName("tasklist")[0]
        for node_task in node_tasklist.getElementsByTagName("task"):
            id = node_task.getAttribute("id")
            done = (node_task.getAttribute("done") == "1")
            date = int(node_task.getAttribute("date"))
            title = getText(node_task.getElementsByTagName("title")[0].childNodes).strip()
            comment = getText(node_task.getElementsByTagName("comment")[0].childNodes).strip()
            self._tasks[id] = (title, done, date, comment)
        self._cb_tl(self._tasks)
    
    def add_task(self, title):
        id = hashlib.md5(str(time.time())).hexdigest()
        self._tasks[id] = (title, False, -1, "")
        self.save_tasks()
        self._cb_ta(id, title)
        
    def remove_task(self, id):
        del self._tasks[id]
        self.save_tasks()
        self._cb_tr(id)
        
    def update_task(self, id, title, done, date, comment):
        self._tasks[id] = (title, done, date, comment)
        self.save_tasks()
        self._cb_tu(id, title, done, date, comment)
    
    def save_tasks(self):
        xmldata = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<tasklist>\n'
        for id, t in self._tasks.iteritems():
            title, done, date, comment = t
            if done:
                done = "1"
            else:
                done = "0"
            taskdata = '\t<task id="%s" done="%s" date="%s">\n' % (id, done, date)
            taskdata += '\t\t<title>%s</title>\n' % title
            taskdata += '\t\t<comment>\n%s\n\t\t</comment>\n' % comment
            taskdata += '\t</task>\n'
            xmldata += taskdata
        xmldata += '</tasklist>'
        f = open(self._filename, "w")
        f.write(xmldata)
        f.close()
