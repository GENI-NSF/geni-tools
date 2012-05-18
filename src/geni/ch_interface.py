# Library of tools for communicating with GENI clearinghouse
# services via XML signed encrypted messages
# Receiving back a tuple with [code, value, output]
# if code = 0, value is the result
# if code is not 0, the output is additional info on the error

import json
import urllib2

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

def invokeCH(url, operation, logger, argsdict, mycert=None, mykey=None):
    # Invoke the real CH
    # for now, this should json encode the args and operation, do an http put
    # entry 1 in dict is named operation and is the operation, rest are args
    # json decode result, getting a dict
    # return the result
    if not operation or operation.strip() == '':
        raise Exception("missing operation")
    if not url or url.strip() == '':
        raise Exception("missing url")
    if not argsdict:
        raise Exception("missing argsdict")

    # Put operation in front of argsdict
    toencode = dict(operation=operation)
    for (k,v) in argsdict.items():
        toencode[k]=v
    argstr = json.dumps(toencode)

    logger.debug("Will do put of %s", argstr)
#    print ("Doing  put of %s" % argstr)

    # now http put this, grab result into putres
    # This is the most trivial put client. This appears to be harder to do / less common than you would expect.
    # See httplib2 for an alternative approach using another library.
    # This approach isn't very robust, may have other issues
    opener = urllib2.build_opener(urllib2.HTTPSHandler)
    req = urllib2.Request(url, data=argstr)
    req.add_header('Content-Type', 'application/json')
    req.get_method = lambda: 'PUT'

    putres = None
    putresHandle = None
    try:
        putresHandle = opener.open(req)
    except Exception, e:
        logger.error("invokeCH failed to open conn to %s: %s", url, e)
        raise Exception("invokeCH failed to open conn to %s: %s" % (url, e))

    if putresHandle:
        try:
            putres=putresHandle.read()
        except Exception, e:
            logger.error("invokeCH failed to read result of put to %s: %s", url, e)
            raise Exception("invokeCH failed to read result of put to %s: %s" % (url, e))

    resdict = None
    if putres:
        logger.debug("invokeCH Got result of %s" % putres)
        resdict = json.loads(putres, encoding='ascii', object_hook=_decode_dict)
    
    # FIXME: Check for code, value, output keys?
    return resdict

def getValueFromTriple(triple, logger, opname, unwrap=False):
    if not triple:
        logger.error("Got empty result triple after %s" % opname)
        raise Exception("Return struct was null for %s" % opname)
    if not triple.has_key('value'):
        logger.error("Malformed return from %s: %s" % (opname, triple))
        raise Exception("malformed return from %s: %s" % (opname, triple))
    if unwrap:
        return triple['value']
    else:
        return triple

# Wait for pyOpenSSL v0.13 which will let us get the client cert chain from the SSL connection
# for now, assume all experimenters are issued by the local MA
def addMACert(experimenter_cert, logger, macertpath):
#/usr/share/geni-ch/ma/ma-cert.pem
    if macertpath is None or macertpath.strip() == '':
        return experimenter_cert

    mc = ''
    add = False
    try:
        with open(macertpath) as macert:
            for line in macert:
                if add or ("BEGIN CERT" in line):
                    add = True
                    mc += line
#            mc = macert.read()
    except:
        logger.error("Failed to read MA cert: %s", traceback.format_exc())
    logger.debug("Resulting PEM: %s" % (experimenter_cert + mc))
    return experimenter_cert + mc
