#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#       dataobject.py
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
import time
from xml.sax.saxutils import escape
from errors import *


class DataField(object):
    
    modified = 0
    value = None
    data_object = None
    
    def __init__(self, value="", modified=0):
        self._lock = threading.Lock()
        super(DataField, self).__init__()
        super(DataField, self).__setattr__("value", value)
        super(DataField, self).__setattr__("modified", modified)
        
    def __setattr__(self, name, value):
        if name != "_lock": self._lock.acquire()
        if name == "value":
            if self.data_object.creation_finished:
                super(DataField, self).__setattr__("modified", time.time())
            if self.data_object != None:
                if self.data_object.creation_finished:
                    super(DataObject, self.data_object).__setattr__("modified", self.modified)
                    self.data_object.needs_commit = True
        elif name == "modified":
            self._lock.release()
            raise ErrorReadOnly
        super(DataField, self).__setattr__(name, value)
        if name != "_lock": self._lock.release()
        
    def get_xml(self, id):
        val = self.value
        if type(val) == str:
            val = escape(val)
        return '\t\t<field id="%s" type="%s" modified="%s">%s</field>\n' % (id, type(self.value).__name__, self.modified, val)
        
    def get_xml_compact(self, id):
        val = self.value
        if type(val) == str:
            val = escape(val)
        return '<f id="%s" t="%s" tm="%s">%s</f>' % (id, type(self.value).__name__, self.modified, val)
        
    def replace(self, obj):
        super(DataField, self).__setattr__("value", obj.value)
        super(DataField, self).__setattr__("modified", obj.modified)


class DataObject(object):
    
    id = None
    modified = 0
    created = 0
    fields = {}
    needs_commit = False
    creation_finished = False
    
    def __init__(self, id, created=time.time(), modified=time.time()):
        super(DataObject, self).__init__()
        super(DataObject, self).__setattr__("id", id)
        super(DataObject, self).__setattr__("created", created)
        super(DataObject, self).__setattr__("modified", modified)
        
        if type(self.fields) == list:
            nfields = {}
            for id in self.fields:
                nfields[id] = DataField()
            super(DataObject, self).__setattr__("fields", nfields)
        
        for id, field in self.fields.iteritems():
            field.data_object = self
        
    def __setattr__(self, name, value):
        if name in ["modified", "created", "fields"]:
            raise ErrorReadOnly
        elif name == "id":
            super(DataObject, self).__setattr__("modified", time.time())
        super(DataObject, self).__setattr__(name, value)
            
    def __getitem__(self, field_name):
        if field_name in self.fields:
            return self.fields[field_name].value
        else:
            raise ErrorUnknownField
            
    def __setitem__(self, field_name, value):
        if field_name in self.fields:
            self.fields[field_name].value = value
        else:
            raise ErrorUnknownField
            
    def __iter__(self):
        for id, field in self.fields.iteritems():
            yield (id, field)
            
    def field(self, field_name):
        if field_name in self.fields:
            return self.fields[field_name]
        else:
            raise ErrorUnknownField
            
    def get_xml(self):
        xml = '\t<object id="%s" created="%s" modified="%s">\n' % (self.id, self.created, self.modified)
        for id, field in self.fields.iteritems():
            xml += field.get_xml(id)
        xml += '\t</object>\n'
        return xml
        
    def get_xml_compact(self):
        xml = '<o id="%s" tc="%s" tm="%s">' % (self.id, self.created, self.modified)
        for id, field in self.fields.iteritems():
            xml += field.get_xml_compact(id)
        xml += '</o>'
        return xml
