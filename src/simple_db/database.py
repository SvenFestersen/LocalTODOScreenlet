#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#       database.py
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
import os
from xml.dom.minidom import parseString

import threading
import time
import dataobject
from errors import *

STORAGE_FORMAT_NORMAL = 0
STORAGE_FORMAT_COMPACT = 1


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
    
    
def convert_type(t, value):
    conversions = {"str": str,
                    "int": int,
                    "float": float,
                    "bool": lambda x: x != "False",
                    "unicode": unicode}
    if t in conversions:
        return conversions[t](value)
    return str(value)
                    


class QueryResult(object):
    
    _data = {}
    _keys = []
    
    def __init__(self, data, sort_function):
        super(QueryResult, self).__init__()
        self._data = data
        self._keys = self._data.keys()
        self._keys.sort(lambda x,y: sort_function(self._data[x], self._data[y]))
        
    def __getitem__(self, id):
        if id in self._data:
            return self._data[id]
        else:
            raise ErrorUnknownDataObject
            
    def __iter__(self):
        for id in self._keys:
            yield self._data[id]
            
    def __len__(self):
        return len(self._data)
        
    def __contains__(self, id):
        return id in self._data
        
    def query(self, select_func=lambda x: x, sort_func=lambda x, y: 0):
        result_keys = filter(lambda x: select_func(self._data[x]), self._data.keys())
        result = {}
        for id in result_keys:
            result[id] = self._data[id]
            
        return QueryResult(result, sort_func)


class DataBase(object):
    
    _version = "beta1"
    filename = None
    prototype = None
    
    def __init__(self, filename, prototype):
        self._lock = threading.Lock()
        self._data = {}
        self._sync_sources = {}
        self.storage_format = STORAGE_FORMAT_COMPACT
        super(DataBase, self).__init__()
        super(DataBase, self).__setattr__("filename", filename)
        super(DataBase, self).__setattr__("prototype", prototype)
        self._load()
        
    def _load(self):
        try:
            if not os.path.exists(self.filename): return
            f = open(self.filename, "r")
            data = f.read()
            if data.endswith("</database>"): self.storage_format = STORAGE_FORMAT_NORMAL
            f.close()
            dom = parseString(data)
            if self.storage_format == STORAGE_FORMAT_COMPACT:
                main_node = dom.getElementsByTagName("db")[0]
                #load sync sources
                sync_node_list = main_node.getElementsByTagName("sy")[0].getElementsByTagName("s")
                for sync_node in sync_node_list:
                    self._sync_sources[sync_node.getAttribute("id")] = float(sync_node.getAttribute("ls"))
                
                #load objects
                obj_node_list = main_node.getElementsByTagName("o")
                for obj_node in obj_node_list:
                    id = obj_node.getAttribute("id")
                    created = float(obj_node.getAttribute("tc"))
                    modified = float(obj_node.getAttribute("tm"))
                    obj = self.prototype(id, created, modified)
                    field_node_list = obj_node.getElementsByTagName("f")
                    for field_node in field_node_list:
                        fid = field_node.getAttribute("id")
                        ftype = field_node.getAttribute("t")
                        modified = float(field_node.getAttribute("tm"))
                        value = getText(field_node.childNodes)
                        value = convert_type(ftype, value)
                        obj[fid] = value
                        super(dataobject.DataField, obj.field(fid)).__setattr__("modified", modified)
                    obj.creation_finished = True
                    self._data[id] = obj
            else:
                main_node = dom.getElementsByTagName("database")[0]
                #load sync sources
                sync_node_list = main_node.getElementsByTagName("sync")[0].getElementsByTagName("source")
                for sync_node in sync_node_list:
                    self._sync_sources[sync_node.getAttribute("id")] = float(sync_node.getAttribute("lastSync"))
                
                #load objects
                obj_node_list = main_node.getElementsByTagName("object")
                for obj_node in obj_node_list:
                    id = obj_node.getAttribute("id")
                    created = float(obj_node.getAttribute("created"))
                    modified = float(obj_node.getAttribute("modified"))
                    obj = self.prototype(id, created, modified)
                    field_node_list = obj_node.getElementsByTagName("field")
                    for field_node in field_node_list:
                        fid = field_node.getAttribute("id")
                        ftype = field_node.getAttribute("type")
                        modified = float(field_node.getAttribute("modified"))
                        value = getText(field_node.childNodes)
                        value = convert_type(ftype, value)
                        obj[fid] = value
                        super(dataobject.DataField, obj.field(fid)).__setattr__("modified", modified)
                    obj.creation_finished = True
                    self._data[id] = obj
        except:
            raise ErrorUnableToReadFile
        
    def __setattr__(self, name, value):
        if name == "filename":
            raise ErrorReadOnly
        super(DataBase, self).__setattr__(name, value)
        
    def __len__(self):
        return len(self._data)
        
    def __delitem__(self, id):
        if id in self._data:
            self._lock.acquire()
            del self._data[id]
            self._lock.release()
        else:
            raise ErrorUnknownDataObject
            
    def __getitem__(self, id):
        if id in self._data:
            return self._data[id]
        else:
            raise ErrorUnknownDataObject
            
    def __setitem__(self, id, obj):
        self.add(obj)
        
    def __contains__(self, id):
        return id in self._data
            
    def add(self, obj):
        self._lock.acquire()
        self._data[obj.id] = obj
        obj.creation_finished = True
        self._lock.release()
        
    def commit(self):
        self._lock.acquire()
        xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        if self.storage_format == STORAGE_FORMAT_COMPACT:
            xml += '<db v="%s">' % self._version
            #write sync sources
            xml += '<sy>'
            for id, last_sync in self._sync_sources.iteritems():
                xml += '<s id="%s" ls="%s" />' % (id, last_sync)
            xml += '</sy>'
            #write objects
            for id, obj in self._data.iteritems():
                xml += obj.get_xml_compact()
            xml += '</db>'
        else:
            xml += '\n<database version="%s">\n' % self._version
             #write sync sources
            xml += '\t<sync>\n'
            for id, last_sync in self._sync_sources.iteritems():
                xml += '\t\t<source id="%s" lastSync="%s" />\n' % (id, last_sync)
            xml += '\t</sync>\n'
            #write objects
            for id, obj in self._data.iteritems():
                xml += obj.get_xml()
            xml += '</database>'
            
        f = open(self.filename, "w")
        f.write(xml)
        f.close()
        self._lock.release()
        
    def query(self, select_func=lambda x: x, sort_func=lambda x, y: 0):
        result_keys = filter(lambda x: select_func(self._data[x]), self._data.keys())
        result = {}
        for id in result_keys:
            result[id] = self._data[id]
            
        return QueryResult(result, sort_func)
        
    def sync(self, source_id, source):
        if not source_id in self._sync_sources:
            raise ErrorUnknownSyncSource
        else:
            sync_databases(self, source, self._sync_sources[source_id], self._lock)
            self._sync_sources[source_id] = time.time()
            
    def add_sync_source(self, id):
        self._lock.acquire()
        self._sync_sources[id] = -1
        self._lock.release()
        
    def has_sync_source(self, id):
        return id in self._sync_sources
        
    def remove_sync_source(self, id):
        if not source_id in self._sync_sources:
            raise ErrorUnknownSyncSource
        else:
            self._lock.acquire()
            del self._sync_sources[id]
            self._lock.release()
        
        
def sync_databases(local, remote, last_sync, lock):
    lock.acquire()
    in_both = local.query(lambda x: x.id in remote)
    in_local_only = local.query(lambda x: not x.id in remote)
    in_remote_only = remote.query(lambda x: not x.id in local)
    
    for local_obj in in_both:
        remote_obj = remote[local_obj.id]
        if local_obj.modified != remote_obj.modified:
            for id, field in local_obj:
                local_modified = field.modified
                remote_modified = remote_obj.field(id).modified
                if local_modified > remote_modified:
                    remote_obj.field(id).replace(local_obj.field(id))
                    #remote_obj[id] = local_obj[id]
                elif local_modified < remote_modified:
                    local_obj.field(id).replace(remote_obj.field(id))
                    #local_obj[id] = remote_obj[id]
    
    lock.release()
    
    local_delete = []
    for local_obj in in_local_only:
        local_modified = local_obj.modified
        if local_modified > last_sync:
            remote.add(local_obj)
        elif local_modified < last_sync:
            local_delete.append(local_obj.id)
            
    remote_delete = []
    for remote_obj in in_remote_only:
        remote_modified = remote_obj.modified
        if remote_modified > last_sync:
            local.add(remote_obj)
        elif remote_modified < last_sync:
            remote_delete.append(remote_obj.id)
            
    for id in local_delete: del local[id]
    for id in remote_delete: del remote[id]
    
    

