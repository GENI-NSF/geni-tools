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

import urllib2
import os

URL_PREFIXES = ("http://", "https://", "ftp://")

def readFile( filestr ):
    contentstr = None
    if filestr.startswith(URL_PREFIXES):
        contentstr = readFromURL(filestr)
    else:
        contentstr = readFromLocalFile(filestr)
    return contentstr

def readFromLocalFile( filename ):
    readstr = None
    filename = os.path.expanduser( filename )
    with open(filename, 'r') as f:
        readstr = f.read()
    return readstr

def readFromURL( url ):
    readstr = None
    u = urllib2.urlopen(url) 
    readstr = u.read()
    return readstr
 
