#----------------------------------------------------------------------
# Copyright (c) 2012-2013 Raytheon BBN Technologies
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
'''Misc utilities for use by chhandler and amhandler'''

import datetime
import json
import logging
import os
import string

from dossl import _do_ssl
import credparsing as credutils
from dates import naiveUTC
import json_encoding
from geni.util import rspec_util
from omnilib.util.files import *
from sfa.trust.gid import GID

def _derefAggNick(handler, aggregateNickname):
    """Check if the given aggregate string is a nickname defined
    in omni_config. If so, return the dereferenced URL,URN.
    Else return the input as the URL, and 'unspecified_AM_URN' as the URN."""

    if not aggregateNickname:
        return (None, None)
    aggregateNickname = aggregateNickname.strip()
    urn = "unspecified_AM_URN"
    url = aggregateNickname

    # ConfigParser.optionxform by default lowercases keys. So aggregate nicknames
    # are lowercased. Here we lowercase any -a argument before
    # checking the defined nicknames, to make sure
    # you can find your nickname
    amNick = aggregateNickname.lower()

    if handler.config['aggregate_nicknames'].has_key(amNick):
        url = handler.config['aggregate_nicknames'][amNick][1]
        tempurn = handler.config['aggregate_nicknames'][amNick][0]
        if tempurn.strip() != "":
            urn = tempurn
        handler.logger.info("Substituting AM nickname %s with URL %s, URN %s", aggregateNickname, url, urn)
    else:
        # if we got here, we are assuming amNick is actually a URL
        # Print a warning now if it doesn't look a URL
        if validate_url( amNick ):
            handler.logger.info("Failed to find an AM nickname '%s'.  If you think this is an error, try using --NoAggNickCache to force the AM nickname cache to update." % aggregateNickname)            

    return url,urn

def _derefRSpecNick( handler, rspecNickname ):
    contentstr = None
    try:
        contentstr = readFile( rspecNickname )
    except:
        pass
    if contentstr is None:
        handler.logger.debug("RSpec '%s' is not a filename or a url" % (rspecNickname))
        if handler.config['rspec_nicknames'].has_key(rspecNickname):
            handler.logger.info("Substituting RSpec nickname '%s' with '%s'" % (rspecNickname, handler.config['rspec_nicknames'][rspecNickname]))
            try:
                contentstr = readFile( handler.config['rspec_nicknames'][rspecNickname] )
            except:
                raise ValueError, "Could not read RSpec '%s' (from nickname '%s')" % (handler.config['rspec_nicknames'][rspecNickname], rspecNickname)
        elif handler.config.has_key('default_rspec_location') and handler.config.has_key('default_rspec_extension'):
            handler.logger.info("Looking for RSpec '%s' in the default rspec location" % (rspecNickname))
            try:
                remoteurl = os.path.join(handler.config['default_rspec_location'], rspecNickname+"."+handler.config['default_rspec_extension'])
                handler.logger.info("... which is '%s'" % (remoteurl))
                contentstr = readFile( remoteurl )            
            except:
                raise ValueError, "Unable to interpret RSpec '%s' as any of url, file, nickname, or in a default location" % (rspecNickname)
        else:
            raise ValueError, "Unable to interpret RSpec '%s' as any of url, file, nickname, or in a default location" % (rspecNickname)            
    return contentstr



def _listaggregates(handler):
    """List the aggregates that can be used for the current operation.
    If 1+ aggregates were specified on the command line, use only those.
    Else if aggregates are specified in the config file, use that set.
    Else ask the framework for the list of aggregates.
    Returns the aggregates as a dict of urn => url pairs.
    If URLs were given on the commandline, AM URN is 'unspecified_AM_URN', with '+'s tacked on for 2nd+ such.
    If multiple URLs were given in the omni config, URN is really the URL
    """
    # used by _getclients (above), createsliver, listaggregates
    if handler.opts.aggregate:
        ret = {}
        for agg in handler.opts.aggregate:
            # Try treating that as a nickname
            # otherwise it is the url directly
            # Either way, if we have no URN, we fill in 'unspecified_AM_URN'
            url, urn = _derefAggNick(handler, agg)
            url = url.strip()
            urn = urn.strip()
            if url != '':
                # Avoid duplicate aggregate entries
                if url in ret.values() and ((ret.has_key(urn) and ret[urn]==url) or urn == "unspecified_AM_URN"):
                    continue
                while urn in ret:
                    urn += "+"
                ret[urn] = url
        return (ret, "")
    elif not handler.omni_config.get('aggregates', '').strip() == '':
        aggs = {}
        for url in handler.omni_config['aggregates'].strip().split(','):
            url = url.strip()
            if url != '':
                aggs[url] = url
        return (aggs, "")
    else:
        (aggs, message) =  _do_ssl(handler.framework, None, "List Aggregates from control framework", handler.framework.list_aggregates)
        if aggs is None:
            # FIXME: Return the message?
            return ({}, message)
        # FIXME: Check that each agg has both a urn and url key?
        return (aggs, "")

def _load_cred(handler, filename):
    '''
    Load a credential from the given filename. Return None on error.
    Based on AM API version, returned cred will be a struct or raw XML.
    In dev mode, file contents are returned as is.
    '''
    if not filename:
        handler.logger.debug("No filename provided for credential")
        return None
    if not os.path.exists(filename) or not os.path.isfile(filename) or os.path.getsize(filename) <= 0:
        handler.logger.warn("Credential file %s missing or empty", filename)
        return None

    handler.logger.info("Getting credential from file %s", filename)
    cred = None
    isStruct = False
    with open(filename, 'r') as f:
        cred = f.read()

    try:
        cred = json.loads(cred, encoding='ascii', cls=json_encoding.DateTimeAwareJSONDecoder)
        isStruct = True
    except Exception, e:
        handler.logger.debug("Failed to get a JSON struct from cred in file %s. Treat as a string.", filename)
        #handler.logger.debug(e)

    if not handler.opts.devmode:
        if handler.opts.api_version >= 3 and credutils.is_cred_xml(cred) and not isStruct:
            handler.logger.debug("Using APIv3+ and got XML cred. Wrapping it.")
            cred = handler.framework.wrap_cred(cred)
        elif handler.opts.api_version < 3 and not credutils.is_cred_xml(cred) and isStruct:
            handler.logger.debug("Using APIv2 or 1 and got a struct cred. Unwrapping it.")
            cred = credutils.get_cred_xml(cred)
        else:
            handler.logger.debug("Using APIv%d and got cred seemingly in right form, return it", handler.opts.api_version)
    return cred

def _get_slice_cred(handler, urn):
    """Get a cred for the slice with the given urn.
    Try a couple times to get the given slice credential.
    Retry on wrong pass phrase.
    Return the slice credential, and a string message of any error.
    Returned credential will be a struct in AM API v3+.
    """

    cred = _load_cred(handler, handler.opts.slicecredfile)
    if cred is not None:
        msg = "Read slice cred from %s" % handler.opts.slicecredfile
        # We support reading cred from file without supplying a URN
        if not urn or urn.strip() == "":
            handler.logger.info("Got slice credential from file %s", handler.opts.slicecredfile)
        else:
            target_urn = credutils.get_cred_target_urn(handler.logger, cred)
            if target_urn != urn:
                msg += " - BUT it is for slice %s, not expected %s!" % (target_urn, urn)
                handler.logger.warn(msg)
                cred = None
            else:
                msg += " for slice %s" % urn
                handler.logger.info(msg)
        return (cred, msg)
    elif handler.opts.slicecredfile and urn:
            handler.logger.warn("Since supplied slicecred file not readable, falling back to re-downloading slice credential for slice %s", urn)

    # We support reading cred from file without supplying a URN
    if not urn or urn.strip() == "":
        msg = "No slice URN supplied and no credential read from a file"
        handler.logger.warn(msg)
        return (None, msg)

    # Check that the return is either None or a valid slice cred
    # Callers handle None - usually by raising an error
    (cred, message) = _do_ssl(handler.framework, None, "Get Slice Cred for slice %s" % urn, handler.framework.get_slice_cred, urn)
    if cred is not None and (not (type(cred) is str and cred.startswith("<"))):
        #elif slice_cred is not XML that looks like a credential, assume
        # assume it's an error message, and raise an omni_error
        handler.logger.error("Got invalid slice credential for slice %s: %s" % (urn, cred))
        cred = None
        message = "Invalid slice credential returned"
    if cred and handler.opts.api_version >= 3:
        cred = handler.framework.wrap_cred(cred)
    return (cred, message)

def _print_slice_expiration(handler, urn, sliceCred=None):
    """Check when the slice expires. Print varying warning notices
    and the expiration date"""
    # FIXME: push this to config?
    shorthours = 3
    middays = 1

# This could be used to print user credential expiration info too...

    if sliceCred is None:
        (sliceCred, _) = _get_slice_cred(handler, urn)
    if sliceCred is None:
        # failed to get a slice string. Can't check
        return ""

    sliceexp = credutils.get_cred_exp(handler.logger, sliceCred)
    sliceexp = naiveUTC(sliceexp)
    now = datetime.datetime.utcnow()
    if sliceexp <= now:
        retVal = 'Slice %s has expired at %s UTC' % (urn, sliceexp)
        handler.logger.warn('Slice %s has expired at %s UTC' % (urn, sliceexp))
    elif sliceexp - datetime.timedelta(hours=shorthours) <= now:
        retVal = 'Slice %s expires in <= %d hours on %s UTC' % (urn, shorthours, sliceexp)
        handler.logger.warn('Slice %s expires in <= %d hours' % (urn, shorthours))
        handler.logger.info('Slice %s expires on %s UTC' % (urn, sliceexp))
        handler.logger.debug('It is now %s UTC' % (datetime.datetime.utcnow()))
    elif sliceexp - datetime.timedelta(days=middays) <= now:
        retVal = 'Slice %s expires within %d day(s) on %s UTC' % (urn, middays, sliceexp)
        handler.logger.info('Slice %s expires within %d day on %s UTC' % (urn, middays, sliceexp))
    else:
        retVal = 'Slice %s expires on %s UTC' % (urn, sliceexp)
        handler.logger.info('Slice %s expires on %s UTC' % (urn, sliceexp))
    return retVal

def validate_url(url):
    """Basic sanity checks on URLs before trying to use them.
    Return None on success, error string if there is a problem.
    If return starts with WARN: then just log a warning - not fatal."""

    import urlparse
    pieces = urlparse.urlparse(url)
    if not all([pieces.scheme, pieces.netloc]):
        return "Invalid URL: %s" % url
    if not pieces.scheme in ["http", "https"]:
        return "Invalid URL. URL should be http or https protocol: %s" % url
    if not set(pieces.netloc) <= set(string.letters+string.digits+'-.:'):
        return "Invalid URL. Host/port has invalid characters in url %s" % url

    # Look for common errors in contructing the urls

    # FIXME: check cache to find common URL typos?

# GCF Ticket #66: This check is just causing confusion. And will be OBE with FOAM.
#    # if the urn part of the urn is openflow/gapi (no trailing slash)
#    # then warn it needs a trailing slash for Expedient
#    if pieces.path.lower().find('/openflow/gapi') == 0 and pieces.path != '/openflow/gapi/':
#        return "WARN: Likely invalid Expedient URL %s. Expedient AM runs at /openflow/gapi/ - try url https://%s/openflow/gapi/" % (url, pieces.netloc)

# GCF ticket #66: Not sure these checks are helping either.
# Right thing may be to test the URL and see if an AM is running there, rather
# than this approach.

#    # If the url has no path part but a port that is 123?? and not 12346
#    # then warn and suggest SFA AMs typically run on 12346
#    if (pieces.path is None or pieces.path.strip() == "" or pieces.path.strip() == '/') and pieces.port >= 12300 and pieces.port < 12400 and pieces.port != 12346:
#        return "WARN: Likely invalid SFA URL %s. SFA AM typically runs on port 12346. Try AM URL https://%s:12346/" % (url, pieces.hostname)

#    # if the non host part has 'protogeni' and is not protogeni/xmlrpc/am
#    # then warn that PG AM interface is at protogeni/xmlrpc/am
#    if pieces.path.lower().find('/protogeni') == 0 and pieces.path != '/protogeni/xmlrpc/am' and pieces.path != '/protogeni/xmlrpc/am/':
#        return "WARN: Likely invalid PG URL %s: PG AMs typically run at /protogeni/xmlrpc/am - try url https://%s/protogeni/xmlrpc/am" % (url, pieces.netloc)

    return None

def _filename_part_from_am_url(url):
    """Strip uninteresting parts from an AM URL 
    to help construct part of a filename.
    """
    # see listresources and createsliver

    if url is None or url.strip() == "":
        return url

    # remove all punctuation and use url
    server = url
    # strip leading protocol bit
    if url.find('://') > -1:
        server = url[(url.find('://') + 3):]

    # protogeni often runs on port 12369 - pull that out if possible
    if ":12369/protogeni/" in server:
        server = server[:(server.index(":12369/"))] + server[(server.index(":12369/")+6):]

    if server.startswith("boss."):
        server = server[server.index("boss.")+len("boss."):]

    # strip standard url endings that dont tell us anything
    if server.endswith("/xmlrpc/am"):
        server = server[:(server.index("/xmlrpc/am"))]
    elif server.endswith("/xmlrpc"):
        server = server[:(server.index("/xmlrpc"))]
    elif server.endswith("/xmlrpc/am/1.0"):
        server = server[:(server.index("/xmlrpc/am/1.0"))] + "v1"
    elif server.endswith("/xmlrpc/am/2.0"):
        server = server[:(server.index("/xmlrpc/am/2.0"))] + "v2"
    elif server.endswith("/xmlrpc/am/3.0"):
        server = server[:(server.index("/xmlrpc/am/3.0"))] + "v3"
    elif server.endswith("/openflow/gapi/"):
        server = server[:(server.index("/openflow/gapi/"))]
    elif server.endswith(":3626/foam/gapi/1"):
        server = server[:(server.index(":3626/foam/gapi/1"))]
    elif server.endswith("/gapi"):
        server = server[:(server.index("/gapi"))]
    elif server.endswith(":12346"):
        server = server[:(server.index(":12346"))]

    # remove punctuation. Handle both unicode and ascii gracefully
    bad = u'!"#%\'()*+,-./:;<=>?@[\]^_`{|}~'
    if isinstance(server, unicode):
        table = dict((ord(char), unicode('-')) for char in bad)
    else:
        assert isinstance(server, str)
        table = string.maketrans(bad, '-' * len(bad))
    server = server.translate(table)
    if server.endswith('-'):
        server = server[:-1]
    return server

def _get_server_name(clienturl, clienturn):
    '''Construct a short server name from the AM URL and URN'''
    if clienturn and not clienturn.startswith("unspecified_AM_URN") and (not clienturn.startswith("http")):
        # construct hrn
        # strip off any leading urn:publicid:IDN
        if clienturn.find("IDN+") > -1:
            clienturn = clienturn[(clienturn.find("IDN+") + 4):]
        urnParts = clienturn.split("+")
        server = urnParts.pop(0)
        if isinstance(server, unicode):
            table = dict((ord(char), unicode('-')) for char in ' .:')
        else:
            table = string.maketrans(' .:', '---')
        server = server.translate(table)
    else:
        # remove all punctuation and use url
        server = _filename_part_from_am_url(clienturl)
    return server

def _construct_output_filename(opts, slicename, clienturl, clienturn, methodname, filetype, clientcount):
    '''Construct a file name for omni command outputs; return that name.
    If --outputfile specified, use that.
    Else, overall form is [prefix-][slicename-]methodname-server.filetype
    filetype should be .xml or .json'''

    # Construct server bit. Get HRN from URN, else use url
    # FIXME: Use sfa.util.xrn.get_authority or urn_to_hrn?
    server = _get_server_name(clienturl, clienturn)
    if opts and opts.outputfile:
        filename = opts.outputfile
        if "%a" in opts.outputfile:
            # replace %a with server
            filename = string.replace(filename, "%a", server)
        elif clientcount > 1:
            # FIXME: How do we distinguish? Let's just prefix server
            filename = server + "-" + filename
        if "%s" in opts.outputfile:
            # replace %s with slicename
            if not slicename:
                slicename = 'noslice'
            filename = string.replace(filename, "%s", slicename)
        return filename

    filename = methodname + "-" + server + filetype
#--- AM API specific
    if slicename:
        filename = slicename+"-" + filename
#--- 
    if opts and opts.prefix and opts.prefix.strip() != "":
        filename  = opts.prefix.strip() + "-" + filename
    return filename

def _getRSpecOutput(logger, rspec, slicename, urn, url, message, slivers=None):
    '''Get the header, rspec content, and retVal for writing the given RSpec to a file'''
    # Create HEADER
    if slicename:
        if slivers and len(slivers) > 0:
            header = "Reserved resources for:\n\tSlice: %s\n\tSlivers: %s\n\tat AM:\n\tURN: %s\n\tURL: %s\n" % (slicename, slivers, urn, url)
        else:
            header = "Reserved resources for:\n\tSlice: %s\n\tat AM:\n\tURN: %s\n\tURL: %s\n" % (slicename, urn, url)
    else:
        header = "Resources at AM:\n\tURN: %s\n\tURL: %s\n" % (urn, url)
    header = "<!-- "+header+" -->"

    server = _get_server_name(url, urn)

    # Create BODY
    if rspec and rspec_util.is_rspec_string( rspec, None, None, logger=logger ):
        # This line seems to insert extra \ns - GCF ticket #202
#        content = rspec_util.getPrettyRSpec(rspec)
        content = string.replace(rspec, "\\n", '\n')
#        content = rspec
        if slicename:
            retVal = "Got Reserved resources RSpec from %s" % server
        else:
            retVal = "Got RSpec from %s" % server
    else:
        content = "<!-- No valid RSpec returned. -->"
        if rspec is not None:
            # FIXME: Diff for dev here?
            logger.warn("No valid RSpec returned: Invalid RSpec? Starts: %s...", str(rspec)[:min(40, len(rspec))])
            content += "\n<!-- \n" + rspec + "\n -->"
            if slicename:
                retVal = "Invalid RSpec returned for slice %s from %s that starts: %s..." % (slicename, server, str(rspec)[:min(40, len(rspec))])
            else:
                retVal = "Invalid RSpec returned from %s that starts: %s..." % (server, str(rspec)[:min(40, len(rspec))])
            if message:
                logger.warn("Server said: %s", message)
                retVal += "; Server said: %s" % message

        else:
            forslice = ""
            if slicename:
                forslice = "for slice %s " % slicename
            serversaid = ""
            if message:
                serversaid = ": %s" % message

            retVal = "No RSpec returned %sfrom %s%s" % (forslice, server, serversaid)
            logger.warn(retVal)
    return header, content, retVal

def _writeRSpec(opts, logger, rspec, slicename, urn, url, message=None, clientcount=1):
    '''Write the given RSpec using _printResults.
    If given a slicename, label the output as a manifest.
    Use rspec_util to check if this is a valid RSpec, and to format the RSpec nicely if so.
    Do much of this using _getRSpecOutput
    Use _construct_output_filename to build the output filename.
    '''
    # return just filename? retVal?
    # Does this do logging? Or return what it would log? I think it logs, but....

    (header, content, retVal) = _getRSpecOutput(logger, rspec, slicename, urn, url, message)

    filename=None
    # Create FILENAME
    if opts.output:
        mname = "rspec"
        if slicename:
            mname = "manifest-rspec"
        filename = _construct_output_filename(opts, slicename, url, urn, mname, ".xml", clientcount)
        # FIXME: Could add note to retVal here about file it was saved to? For now, caller does that.

    if filename or (rspec is not None and str(rspec).strip() != ''):
        # Create FILE
        # This prints or logs results, depending on whether filename is None
        _printResults(opts, logger, header, content, filename)
    return retVal, filename
# End of _writeRSpec

def _printResults(opts, logger, header, content, filename=None):
    """Print header string and content string to file of given
    name. If filename is none, then log to info.
    If --tostdout option, then instead of logging, print to STDOUT.
    """
    cstart = 0
    # if content starts with <?xml ..... ?> then put the header after that bit
    if content is not None and content.find("<?xml") > -1:
        cstart = content.find("?>", content.find("<?xml") + len("<?xml"))+2
        # push past any trailing \n
        if content[cstart:cstart+2] == "\\n":
            cstart += 2
    # used by listresources
    if filename is None:
        if header is not None:
            if cstart > 0:
                if not opts.tostdout:
                    logger.info(content[:cstart])
                else:
                    print content[:cstart] + "\n"
            if not opts.tostdout:
                # indent header a bit if there was something first
                pre = ""
                if cstart > 0:
                    pre = "  "
                logger.info(pre + header)
            else:
                # If cstart is 0 maybe still log the header so it
                # isn't written to STDOUT and non-machine-parsable
                if cstart == 0:
                    logger.info(header)
                else:
                    print header + "\n"
        elif content is not None:
            if not opts.tostdout:
                logger.info(content[:cstart])
            else:
                print content[:cstart] + "\n"
        if content is not None:
            if not opts.tostdout:
                # indent a bit if there was something first
                pre = ""
                if cstart > 0:
                    pre += "  "
                logger.info(pre + content[cstart:])
            else:
                print content[cstart:] + "\n"
    else:
        fdir = os.path.dirname(filename)
        if fdir and fdir != "":
            if not os.path.exists(fdir):
                os.makedirs(fdir)
        with open(filename,'w') as file:
            logger.info( "Writing to '%s'"%(filename))
            if header is not None:
                if cstart > 0:
                    file.write (content[:cstart] + '\n')
                # this will fail for JSON output. 
                # only write header to file if have xml like
                # above, else do log thing per above
                # FIXME: XML file without the <?xml also ends up logging the header this way
                if cstart > 0:
                    file.write("  " + header )
                    file.write( "\n" )
                else:
                    logger.info(header)
            elif cstart > 0:
                file.write(content[:cstart] + '\n')
            if content is not None:
                pre = ""
                if cstart > 0:
                    pre += "  "
                file.write( pre + content[cstart:] )
                file.write( "\n" )
# End of _printResults

def _maybe_save_slicecred(handler, name, slicecred):
    """Save slice credential to a file, returning the filename or
    None on error or config not specifying -o
    
    Only saves if handler.opts.output and non-empty credential
    
    If you didn't specify -o but do specify --tostdout, then write
    the slice credential to STDOUT
    
    Filename is:
    --slicecredfile if supplied
    else [<--p value>-]-<slicename>-cred.[xml or json, depending on credential format]
    """
    if name is None or name.strip() == "" or slicecred is None or (credutils.is_cred_xml(slicecred) and slicecred.strip() is None):
        return None

    filename = None
    if handler.opts.output:
        if handler.opts.slicecredfile:
            filename = handler.opts.slicecredfile
        else:
            filename = name + "-cred"
            if handler.opts.prefix and handler.opts.prefix.strip() != "":
                filename = handler.opts.prefix.strip() + "-" + filename
        filename = _save_cred(handler, filename, slicecred)
    elif handler.opts.tostdout:
        handler.logger.info("Writing slice %s cred to STDOUT per options", name)
        # pprint does bad on XML, but OK on JSON
        print slicecred
    return filename

def _save_cred(handler, name, cred):
    '''
    Save the given credential to a file of the given name.
    Infer an appropriate file extension from the file type.
    If we are using APIv3+ and the credential is not a struct, wrap it before saving.
    '''
    ftype = ".xml"
    # FIXME: Do this?
    if credutils.is_cred_xml(cred) and handler.opts.api_version >= 3:
        handler.logger.debug("V3 requested, got unwrapped cred. Wrapping before saving")
        cred = handler.framework.wrap_cred(cred)

    if not credutils.is_cred_xml(cred):
        ftype = ".json"
        credout = json.dumps(cred, cls=json_encoding.DateTimeAwareJSONEncoder)
        # then read:                 cred = json.load(f, encoding='ascii', cls=DateTimeAwareJSONDecoder)
    else:
        credout = cred

    if not name.endswith(ftype):
        filename = name + ftype
    else:
        filename = name
# usercred did this:
#        with open(fname, "wb") as file:
#            file.write(cred)
    with open(filename, 'w') as file:
        file.write(credout + "\n")

    return filename

def _is_user_cert_expired(handler):
    # create a gid
    usergid = None
    try:
        usergid = GID(filename=handler.framework.config['cert'])
    except Exception, e:
        handler.logger.debug("Failed to create GID from %s: %s",
                             handler.framework.config['cert'], e)
    if usergid and usergid.cert.has_expired():
        return True
    return False

def _get_user_urn(handler):
    # create a gid
    usergid = None
    try:
        usergid = GID(filename=handler.framework.config['cert'])
    except Exception, e:
        handler.logger.debug("Failed to create GID from %s: %s",
                             handler.framework.config['cert'], e)
    # do get_urn
    if usergid:
        return usergid.get_urn()
    else:
        return None

def printNicknames(config, opts):
    '''Get the known aggregate and rspec nicknames and return them as a string and a struct'''
    retStruct = dict()
    retStruct['aggregate_nicknames'] = config['aggregate_nicknames']
    retString = "Omni knows the following Aggregate Nicknames:\n\n"
    retString += "%16s | %s | %s\n" % ("Nickname", string.ljust("URL", 70), "URN")
    retString += "=============================================================================================================\n"
    for nick in sorted(config['aggregate_nicknames'].keys()):
        (urn, url) = config['aggregate_nicknames'][nick]
        retString += "%16s | %s | %s\n" % (nick, string.ljust(url, 70), urn)

    retStruct['rspec_nicknames'] = config['rspec_nicknames']
    if len(config['rspec_nicknames']) > 0:
        retString += "\nOmni knows the following RSpec Nicknames:\n\n"
        retString += "%14s | %s\n" % ("Nickname", "Location")
        retString += "====================================================================================\n"
        for nick in sorted(config['rspec_nicknames'].keys()):
            location = config['rspec_nicknames'][nick]
            retString += "%14s | %s\n" % (nick, location)

    if config.has_key("default_rspec_location"):
        retString += "\n(Default RSpec location: %s )\n" % config["default_rspec_location"]
    if config.has_key("default_rspec_extension"):
        retString += "\n(Default RSpec extension: %s )\n" % config["default_rspec_extension"]

    if opts.aggregate and len(opts.aggregate) > 0:
        retString += "\nRequested aggregate nicknames:\n"
        for nick in opts.aggregate:
            if nick in config['aggregate_nicknames'].keys():
                (urn, url) = config['aggregate_nicknames'][nick]
                retString += "\t%s = %s (%s)\n" % (nick, url, urn)
            else:
                retString += "\t%s = Not a known aggregate nickname\n" % nick

    return retString, retStruct
