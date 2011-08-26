#!/usr/bin/python
import sys

import os
import os.path
import tempfile
import re
import time
import zipfile
import datetime
import shutil

import ABAC
import Creddy

from xmlrpclib import Binary


def get_abac_creds(root):
    '''
    Read all the files in ~/.abac into a list and return it
    '''
    creds = []
    for r, d, f in os.walk(os.path.expanduser(root)):
	for fn in f:
	    try:
		ff = open(os.path.join(r, fn), 'r')
		c = ''
		for l in ff:
		    c += l
		ff.close()
		creds.append(Binary(c))
	    except EnvironmentError, e:
		print sys.stderr, "Error on %s: %s" % (e.filename, e.strerror)
    return creds

def save_abac_creds(creds, dir):
    d = os.path.expanduser(dir)
    for c in creds:
	if isinstance(c, Binary): c = c.data
	cf = tempfile.NamedTemporaryFile(prefix='cred', suffix='.der',
		dir=d, delete=False)
	cf.write(c)
	cf.close()

def creddy_from_chunk(chunk):
    f = tempfile.NamedTemporaryFile(suffix='.pem')
    f.write(chunk)
    f.flush()
    try:
	return Creddy.ID(f.name)
    except:
	return None


def print_proof(proof, out=sys.stdout):
    a = ABAC.Context()

    names = [ ]
    attrs = [ ]
    for c in proof:
	if isinstance(c, Binary): c = c.data
	i = creddy_from_chunk(c)
	if i is None:
	    attrs.append(c)
	else:
	    names.append((re.compile(i.keyid()), i.cert_filename()[:-7]))
	    a.load_id_chunk(i.cert_chunk())

    for c in attrs:
	a.load_attribute_chunk(c)

    for c in a.credentials():
	s = "%s <- %s" % (c.head().string(), c.tail().string())
	for r, n in names:
	    s = r.sub(n, s)
	print >>out, s

def save_proof(d, proof):
    zname = os.path.join(os.path.expanduser(d),
	    '%s.zip' % datetime.datetime.now().isoformat())
    zf = zipfile.ZipFile(zname, 'w')
    for i, c in enumerate(proof):
	if isinstance(c, Binary): c = c.data
	zf.writestr('proof/cred%03d' % i, c)
    zf.close()
