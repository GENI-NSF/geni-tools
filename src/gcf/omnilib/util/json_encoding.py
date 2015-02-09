#!/usr/bin/python

#----------------------------------------------------------------------
# Copyright (c) 2012-2015 Raytheon BBN Technologies
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and/or hardware specification (the "Work") to
# deal in the Work without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Work, and to permit persons to whom the Work
# is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Work.
#
# THE WORK IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE WORK OR THE USE OR OTHER DEALINGS
# IN THE WORK.
#----------------------------------------------------------------------
'''
Utilities for serializing (encoding) and deserializing (decoding) objects as JSON
'''

import datetime
import json

# Force the unicode strings python creates to be ascii
def _decode_list(data):
    rv = []
    for item in data:
        if isinstance(item, unicode):
            item = item.encode('utf-8')
        elif isinstance(item, list):
            item = _decode_list(item)
        elif isinstance(item, dict):
            item = _decode_dict(item)
        rv.append(item)
    return rv

# Force the unicode strings python creates to be ascii
def _decode_dict(data):
    rv = {}
    for key, value in data.iteritems():
        if isinstance(key, unicode):
           key = key.encode('utf-8')
        if isinstance(value, unicode):
           value = value.encode('utf-8')
        elif isinstance(value, list):
           value = _decode_list(value)
        elif isinstance(value, dict):
           value = _decode_dict(value)
        rv[key] = value
    return rv

class DateTimeAwareJSONEncoder(json.JSONEncoder):
    """
    Converts a python object, where datetime and timedelta objects are converted
    into objects that can be decoded using the DateTimeAwareJSONDecoder.
    Sample usage:
        with open(self.opts.getversionCacheName, 'w') as file:
            json.dump(self.GetVersionCache, file, cls=DateTimeAwareJSONEncoder)
    """
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return {
                '__type__' : 'datetime',
                'year' : obj.year,
                'month' : obj.month,
                'day' : obj.day,
                'hour' : obj.hour,
                'minute' : obj.minute,
                'second' : obj.second,
                'microsecond' : obj.microsecond,
            }

        elif isinstance(obj, datetime.timedelta):
            return {
                '__type__' : 'timedelta',
                'days' : obj.days,
                'seconds' : obj.seconds,
                'microseconds' : obj.microseconds,
            }   

        else:
            return json.JSONEncoder.default(self, obj)

class DateTimeAwareJSONDecoder(json.JSONDecoder):
    """
    Converts a json string, where datetime and timedelta objects were converted
    into objects using the DateTimeAwareJSONEncoder, back into a python object.
    Sample usage:
        with open(self.opts.getversionCacheName, 'r') as f:
            self.GetVersionCache = json.load(f, encoding='ascii', cls=DateTimeAwareJSONDecoder)
    """

    def __init__(self, **kw):
            json.JSONDecoder.__init__(self, object_hook=self.dict_to_object, **kw)

    def dict_to_object(self, d):
        if '__type__' not in d:
            return _decode_dict(d)

        type = d.pop('__type__')
        if type == 'datetime':
            return datetime.datetime(**d)
        elif type == 'timedelta':
            return datetime.timedelta(**d)
        else:
            # Oops... better put this back together.
            d['__type__'] = type
            return d

