#----------------------------------------------------------------------
# Copyright (c) 2011 USC/ISI
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and/or hardware specification (the
# "Work") to deal in the Work without restriction, including without
# limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Work, and to
# permit persons to whom the Work is furnished to do so, subject to
# the following conditions:
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

import sys

import os.path
import tempfile
import re
import zipfile
import datetime

try:
    import ABAC
except:
    # ABAC is not for general use yet. To avoid confusion, silently continue.
    # In the future, issue a warning and/or fail outright.
    pass

try:
    import Creddy
except:
    # ABAC is not for general use yet. To avoid confusion, silently continue.
    # In the future, issue a warning and/or fail outright.
    pass

from xmlrpclib import Binary
from hashlib import sha256

def is_ABAC_framework(f):
    '''
    Return true if the framework uses ABAC.  Such a framework should signal it
    by having an 'abac' attribute set to True and 'abac_dir' and 'abac_log'
    attributes set to those directories'
    '''
    return getattr(f, 'abac', False)

def get_abac_creds(root):
    '''
    Reas a directory of ABAC certs and return them ready for an XMLRPC call.
    Technically this reads all the files in root into a list of xmlrpc Binary
    objects and return them.
    '''
    creds = []
    for r, d, f in os.walk(os.path.expanduser(root)):
        _ = d # appease eclipse
        for fn in f:
            try:
                ff = open(os.path.join(r, fn), 'r')
                c = ff.read()
                ff.close()
                creds.append(Binary(c))
            except EnvironmentError, e:
                # XXX logger??
                print sys.stderr, "Error on %s: %s" % (e.filename, e.strerror)
    return creds

def save_abac_creds(creds, dir="~/.abac"):
    '''
    Save the list of creds into the given directory.  Credentials that are
    already in the directory are mot saved again.  Collisions are detected by a
    sha256 hash.  creds can contain either strings or xmlrpclib.Binary objects.
    '''
    credhashes = set()
    # Walk the existing dir and save hashes of the creds
    for r, d, fns in os.walk(os.path.expanduser(dir)):
        _ = d # appease eclipse
        for fn in fns:
            h = sha256();
            f = open(os.path.join(r, fn))
            h.update(f.read())
            f.close()
            credhashes.add(h.hexdigest())

    # If the cred has nor been seen, save it, using the tempfile library to
    # pick a unique name w/o collision.
    for c in creds:
        if isinstance(c, Binary): c = c.data
        h = sha256()
        h.update(c)
        if h.hexdigest() not in credhashes:
            if c.startswith('-----BEGIN'): suffix = '.pem'
            else: suffix='.der'
            f = tempfile.NamedTemporaryFile(dir=os.path.expanduser(dir),
                                            suffix=suffix, delete=False);
            f.write(c)
            f.close()

def creddy_from_chunk(chunk):
    '''
    Get a Creddy.ID from a chunk.  This version of libcreddy only reads from
    files, so we write a tempfile and import. (The tempfile module deletes the
    temp file when the tempfile.NamedTemporaryFile goes out of scope.)
    '''
    f = tempfile.NamedTemporaryFile(suffix='.pem')
    f.write(chunk)
    f.flush()
    try:
        return Creddy.ID(f.name)
    except:
        return None


def print_proof(proof, out=sys.stdout):
    '''
    Print the given proof to out.  Proof can be a list of strings or
    xmlrpc.Binary objects.
    '''
    a = ABAC.Context()

    names = [ ]
    attrs = [ ]
    # Find the IDs and keep track of the map from name to keyid
    # IDs get loaded into teh context here
    for c in proof:
        if isinstance(c, Binary): c = c.data
        i = creddy_from_chunk(c)
        if i is None:
            attrs.append(c)
        else:
            names.append((re.compile(i.keyid()), i.cert_filename()[:-7]))
            a.load_id_chunk(i.cert_chunk())

    # Add the attributes
    for c in attrs:
        a.load_attribute_chunk(c)

    # Print 'em
    for c in a.credentials():
        s = "%s <- %s" % (c.head().string(), c.tail().string())
        for r, n in names:
            s = r.sub(n, s)
        print >>out, s

def save_proof(d, proof):
    '''
    Save proof into directory d as a zipfile, named after the current time.
    proof can be a list of strings or contain xmlrpc.Binary objects.
    '''
    zname = os.path.join(os.path.expanduser(d),
            '%s.zip' % datetime.datetime.now().isoformat())
    zf = zipfile.ZipFile(zname, 'w')
    for i, c in enumerate(proof):
        if isinstance(c, Binary): c = c.data
        zf.writestr('proof/cred%03d' % i, c)
    zf.close()
