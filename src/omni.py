#!/usr/bin/python

#----------------------------------------------------------------------
# Copyright (c) 2011 Raytheon BBN Technologies
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

""" The OMNI client
    This client is a GENI API client that is capable of connecting
    to the supported control frameworks for slice creation and deletion.
    It is also able to parse and create standard RSPECs of all supported 
    control frameworks.
    See README-omni.txt

    Be sure to create an omni config file (typically ~/.gcf/omni_config)
    and supply valid paths to your per control framework user certs and keys.

    Typical usage:
    omni.py -f sfa listresources 
    
    The currently supported control frameworks are SFA, PG and GCF.

    Extending Omni to support additional types of Aggregate Managers
    with different RSpec formats requires adding a new omnispec/rspec
    conversion file.

    Extending Omni to support additional frameworks with their own
    clearinghouse APIs requires adding a new Framework extension class.

    Return Values of various omni commands:
       [string dictionary] = omni.py getversion # dict is keyed by AM url
       [string dictionary] = omni.py listresources
       [string rspec] = omni.py createsliver SLICENAME RSPEC_FILENAME
       [string dictionary] = omni .py sliverstatus SLICENAME
       [string (successList, failList)] = omni.py renewsliver SLICENAME
       [string (successList, failList)] = omni.py deletesliver SLICENAME
       [string (successList, failList)] = omni.py shutdown SLICENAME
       [string dictionary] = omni.py listaggregates
       On success: [string sliceurnstring] = omni.py createslice SLICENAME
       On fail: [string None] = omni.py createslice SLICENAME
       On success: [string dateTimeRenewedTo] = omni.py renewslice SLICENAME
       On fail: [string None] = omni.py renewslice SLICENAME
       [string Boolean] = omni.py deleteslice SLICENAME
       [string listOfSliceNames] = omni.py listmyslices USER
       [stringCred stringCred] = omni.py getslicecred SLICENAME
       [string string] = omni.py print_slice_expiration SLICENAME
    
"""

import ConfigParser
from copy import copy, deepcopy
import datetime
import dateutil.parser
import json
import logging.config
import optparse
import os
import pprint
import string
import sys
import xml.dom.minidom as md
import zlib

from omnilib.omnispec.translation import rspec_to_omnispec, omnispec_to_rspec
from omnilib.omnispec.omnispec import OmniSpec
from omnilib.util import OmniError
from omnilib.util.dossl import _do_ssl
from omnilib.util.abac import get_abac_creds, save_abac_creds, save_proof, \
        is_ABAC_framework
import omnilib.util.credparsing as credutils
import omnilib.xmlrpc.client

from geni.util import rspec_util 

#import sfa.trust.gid as gid

OMNI_VERSION="1.5.1"

def naiveUTC(dt):
    """Converts dt to a naive datetime in UTC.

    if 'dt' has a timezone then
        convert to UTC
        strip off timezone (make it "naive" in Python parlance)
    """
    if dt.tzinfo:
        tz_utc = dateutil.tz.tzutc()
        dt = dt.astimezone(tz_utc)
        dt = dt.replace(tzinfo=None)
    return dt

class CallHandler(object):
    """Handle calls on the framework. Valid calls are all
    methods without an underscore: getversion, createslice, deleteslice, 
    getslicecred, listresources, createsliver, deletesliver,
    renewsliver, sliverstatus, shutdown, listmyslices, listaggregates, renewslice
    """

    def __init__(self, framework, config, opts):
        self.framework = framework
        self.logger = config['logger']
        self.omni_config = config['omni']
        self.config = config
        self.opts = opts
        if self.opts.abac:
            aconf = self.config['selected_framework']
            if 'abac' in aconf and 'abac_log' in aconf:
                self.abac_dir = aconf['abac']
                self.abac_log = aconf['abac_log']
            else:
                self.logger.error("ABAC requested (--abac) and no abac= or abac_log= in omni_config: disabling ABAC")
                self.opts.abac= False
                self.abac_dir = None
                self.abac_log = None

        
    def _raise_omni_error( self, msg ):
        self.logger.error( msg )
        raise OmniError, msg

    def _handle(self, args):
        if len(args) == 0:
            self._raise_omni_error('Insufficient number of arguments - Missing command to run')
        
        call = args[0].lower()
        # disallow calling private methods
        if call.startswith('_'):
            return
        if not hasattr(self,call):
            self._raise_omni_error('Unknown function: %s' % call)
        return getattr(self,call)(args[1:])

    def getversion(self, args):
        """AM API GetVersion

        Aggregates queried:
        - Single URL given in -a argument or URL listed under that given
        nickname in omni_config, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse

        -o Save result (JSON format) in per-Aggregate files
        -p (used with -o) Prefix for resulting version information files
        If not saving results to a file, they are logged.
        If --tostdout option, then instead of logging, print to STDOUT.

        """
        retVal = ""
        version = {}
        (clients, message) = self._getclients()
        successCnt = 0

        for client in clients:
            (thisVersion, message) = _do_ssl(self.framework, None, "GetVersion at %s" % (str(client.url)), client.GetVersion)
            version[ client.url ] = thisVersion
            if thisVersion is None:
                retVal = retVal + "Cannot GetVersion at %s: %s\n" % (client.url, message)
                self.logger.warn( "URN: %s (url:%s) call failed: %s\n" % (client.urn, client.url, message) )
            else:
                # FIXME only print 'peers' on verbose
                pp = pprint.PrettyPrinter(indent=4)
                prettyVersion = pp.pformat(thisVersion)
                successCnt += 1
                header = "AM URN: %s (url: %s) has version:" % (client.urn, client.url)
                filename = None
                if self.opts.output:
                    # Create HEADER
                    # But JSON cant have any
                    #header = None
                    # Create filename
                    server = self._filename_part_from_am_url(client.url)
                    filename = "getversion-"+server+".xml"
                    if self.opts.prefix and self.opts.prefix.strip() != "":
                        filename  = self.opts.prefix.strip() + "-" + filename
                    self.logger.info("Writing result of getversion at AM %s (%s) to file '%s'", client.urn, client.url, filename)
                # Create File
                # This logs or prints, depending on whether filename
                # is None
                self._printResults( header, prettyVersion, filename)

                # FIXME: include filename in summary: always? only if 1 aggregate?
                if filename:
                    retVal += "Saved getversion at AM %s (%s) to file '%s'.\n" % (client.urn, client.url, filename)

        if len(clients)==0:
            retVal += "No aggregates to query. %s\n\n" % message
        else:
            # FIXME: If I have a message from getclients, want it here?
            # FIXME: If it is 1 just return the getversion?
            retVal += "\nGot version for %d out of %d aggregates\n" % (successCnt,len(clients))

        return (retVal, version)

    def _get_advertised_rspecs(self, client):
        (thisVersion, message) = _do_ssl(self.framework, None, "GetVersion at %s" % (str(client.url)), client.GetVersion)
        ad_key = 'ad_rspec_versions'
        if self.opts.api_version == 2:
            if thisVersion['code']['geni_code'] == 0:
                thisVersion = thisVersion['value']
                ad_key = 'geni_ad_rspec_versions'
            else:
                return (None, 'Error code %s from AM %s: %s' % (client.url, thisVersion['output']))
        if thisVersion is None:
            self.logger.warning("Couldnt do GetVersion so won't do ListResources at %s [%s]", client.urn, client.url)
            return (None, 'AM %s did not respond to GetVersion: %s' % (client.url, message))
        if not thisVersion.has_key(ad_key):
            self.logger.warning("AM GetVersion has no ad_rspec_versions key for AM %s [%s]", client.urn, client.url)
            return (None, 'AM %s did not advertise RSpec versions' % (client.url))
        # Looks ok, return the 'ad_rspec_versions' value.
        return (thisVersion[ad_key], "")

    def _listresources(self, args):
        """Queries resources on various aggregates.
        
        Takes an optional slicename.
        Uses optional aggregate option or omni_config aggregate param.
        (See _listaggregates)

        Doesn't care about omnispec vs native.
        Doesn't care how many aggregates that you query.

        If you specify a required Ad RSpec type and version (both strings. Use the -t option)
        then it skips any AM that doesn't advertise (in GetVersion)
        that it supports that format.

        Returns a dictionary of rspecs with the following format:
           rspecs[(urn, url)] = decompressed native rspec
           AND a string describing the result.
        On error the dictionary is None and the message explains.
        """

        # rspecs[(urn, url)] = decompressed native rspec
        rspecs = {}
        options = {}

        options['geni_compressed'] = self.opts.geni_compressed
        options['geni_available'] = self.opts.geni_available

        # An optional slice name might be specified.
        slicename = None
        if len(args) > 0:
            slicename = args[0].strip()

        # Get the credential for this query
        if slicename is None or slicename == "":
            slicename = None
            cred = None
            (cred, message) = self.framework.get_user_cred()
            if cred is None:
                self.logger.error('Cannot list resources: Could not get user credential')
                return (None, "Could not get user credential: %s" % message)
        else:
            urn = self.framework.slice_name_to_urn(slicename)
            (cred, message) = self._get_slice_cred(urn)
            if cred is None:
                prstr = "Cannot list resources for slice %s: Could not get slice credential. " % urn
                if message != "":
                    prstr += message
                self.logger.error(prstr)
                return (None, prstr)

            self.logger.info('Gathering resources reserved for slice %s.' % slicename)

            options['geni_slice_urn'] = urn

        # We now have a credential

        # Query each aggregate for resources
        successCnt = 0
        mymessage = ""
        (clientList, message) = self._getclients()
        if len(clientList) == 0 and message != "":
            mymessage = "No aggregates available to query: %s" % message
        # FIXME: What if got a message and still got some aggs?

        # Connect to each available GENI AM to list their resources
        for client in clientList:
            if cred is None:
                self.logger.debug("Have null credential in call to ListResources!")
            self.logger.debug("Connecting to AM: %s at %s", client.urn, client.url)
            rspec = None

            # If the user specified a specific rspec type and version,
            # then we ONLY get rspecs from each AM that is capable
            # of talking that type&version.
            # Note an alternative would have been to let the AM just
            # do whatever it likes to do if
            # you ask it to give you something it doesnt understand.
            # Also note this is independent of whether you asked for omnispecs.
            # And that means you can request a format that can't be converted
            # to omnispecs properly.
            if self.opts.rspectype:
                rtype = self.opts.rspectype[0]
                rver = self.opts.rspectype[1]
                self.logger.debug("Will request RSpecs only of type %s and version %s", rtype, rver)

                (ad_rspec_version, message) = self._get_advertised_rspecs(client)
                if ad_rspec_version is None:
                    if mymessage != "":
                        mymessage += ". "
                    mymessage = mymessage + message
                    continue

                self.logger.debug("Got %d supported ad_rspec_versions", len(ad_rspec_version))
                # foreach item in the list that is the val
                match = False
                for availversion in ad_rspec_version:
                    if not availversion.has_key('type') and availversion.has_key('version'):
                        self.logger.warning("AM getversion ad_rspec_version entry malformed: no type or version")
                        continue

                    # version is also a string
                    if str(availversion['type']).lower().strip() == rtype.lower().strip() and str(availversion['version']).lower().strip() == str(rver).lower().strip():
                        # success
                        self.logger.debug("Found a matching supported type/ver: %s/%s", availversion['type'], availversion['version'])
                        match = True
                        rtype=availversion['type']
                        rver=availversion['version']
                        break
                # if no success
                if match == False:
                    #   return error showing ad_rspec_versions
                    pp = pprint.PrettyPrinter(indent=4)
                    self.logger.warning("AM cannot provide Ad Rspec in requested version (%s %s) at AM %s [%s]. This AM only supports: \n%s", rtype, rver, client.urn, client.url, pp.pformat(ad_rspec_version))
                    if mymessage != "":
                        mymessage += ". "
                    mymessage = mymessage + "Skipped AM %s that didnt support required RSpec format %s %s" % (client.url, rtype, rver)
                    continue
                if self.opts.api_version == 1:
                    options['rspec_version'] = dict(type=rtype, version=rver)
                else:
                    options['geni_rspec_version'] = dict(type=rtype, version=rver)
            elif self.opts.api_version == 2:
                # User did not specify an rspec type but did request version 2.
                # Make an attempt to do the right thing, othewise bail and tell the user.
                (ad_rspec_version, message) = self._get_advertised_rspecs(client)
                if ad_rspec_version is None:
                    if mymessage != "":
                        mymessage += ". "
                    mymessage = mymessage + message
                    continue
                if len(ad_rspec_version) == 1:
                    # there is only one advertisement, so use it.
                    options['geni_rspec_version'] = dict(type=ad_rspec_version[0]['type'],
                                                         version=ad_rspec_version[0]['version'])
                else:
                    # Inform the user that they have to pick.
                    ad_versions = [(x['type'], x['version']) for x in ad_rspec_version]
                    self.logger.warning("Please specify the desired RSpec type for AM %s as one of %r", client.url, ad_versions)
                    if mymessage != "":
                        mymessage += ". "
                    mymessage = mymessage + "AM %s supports multiple RSpec versions: %r" % (client.url, ad_versions)
                    continue

            self.logger.debug("Doing listresources with options %r", options)
            # If ABAC then creds are ABAC creds. Else Creds are the user cred or slice cred
            # as retrieved above, as normal
            if is_ABAC_framework(self.framework):
                creds = get_abac_creds(self.framework.abac_dir)
                creds.append(cred)
            else:
                creds = [cred]

            (resp, message) = _do_ssl(self.framework, None, ("List Resources at %s" % (client.url)), client.ListResources, creds, options)

            # If ABAC return is a dict with proof and the regular return
            if isinstance(resp, dict):
                if is_ABAC_framework(self.framework):
                    if 'proof' in resp:
                        save_proof(self.framework.abac_log, resp['proof'])
                if 'manifest' in resp:
                    rspec = resp['manifest']
                elif 'code' in resp:
                    # AM API v2
                    if resp['code']['geni_code'] == 0:
                        rspec = resp['value']
                    else:
                        message = resp['output']
                        resp = None
            else:
                rspec = resp

            if not rspec is None:
                successCnt += 1
                if options.get('geni_compressed', False):
                    rspec = zlib.decompress(rspec.decode('base64'))
                rspecs[(client.urn, client.url)] = rspec
            else:
                if mymessage != "":
                    mymessage += ". "
                mymessage += "No resources from AM %s: %s" % (client.url, message)

        self.logger.info( "Listed resources on %d out of %d possible aggregates." % (successCnt, len(clientList)))
        return (rspecs, mymessage)

    def _printResults(self, header, content, filename=None):
        """Print header string and content string to file of given
        name. If filename is none, then log to info.
        If --tostdout option, then instead of logging, print to STDOUT.
        """
        cstart = 0
        # if content starts with <?xml ..... ?> then put the header after that bit
        if content is not None and content.find("<?xml") > -1:
            cstart = content.find("?>", content.find("<?xml") + len("<?xml"))+2
        # used by listresources
        if filename is None:
            if header is not None:
                if cstart > 0:
                    if not self.opts.tostdout:
                        self.logger.info(content[:cstart])
                    else:
                        print content[:cstart] + "\n"
                if not self.opts.tostdout:
                    self.logger.info(header)
                else:
                    # If cstart is 0 maybe still log the header so it
                    # isn't written to STDOUT and non-machine-parsable
                    if cstart == 0:
                        self.logger.info(header)
                    else:
                        print header + "\n"
            elif content is not None:
                if not self.opts.tostdout:
                    self.logger.info(content[:cstart])
                else:
                    print content[:cstart] + "\n"
            if content is not None:
                if not self.opts.tostdout:
                    self.logger.info(content[cstart:])
                else:
                    print content[cstart:] + "\n"
        else:
            with open(filename,'w') as file:
                self.logger.info( "Writing to '%s'"%(filename))
                if header is not None:
                    if cstart > 0:
                        file.write (content[:cstart] + '\n')
                    # this will fail for JSON output. 
                    # only write header to file if have xml like
                    # above, else do log thing per above
                    if cstart > 0:
                        file.write( header )
                        file.write( "\n" )
                    else:
                        self.logger.info(header)
                elif cstart > 0:
                    file.write(content[:cstart] + '\n')
                if content is not None:
                    file.write( content[cstart:] )
                    file.write( "\n" )

    def _filename_part_from_am_url(self, url):
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

        # strip standard url endings that dont tell us anything
        if server.endswith("/xmlrpc/am"):
            server = server[:(server.index("/xmlrpc/am"))]
        elif server.endswith("/xmlrpc"):
            server = server[:(server.index("/xmlrpc"))]
        elif server.endswith("/openflow/gapi/"):
            server = server[:(server.index("/openflow/gapi/"))]
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
        return server

    def listresources(self, args):
        """Optional arg is a slice name limiting results. Call ListResources
        on 1+ aggregates and prints the omnispec/rspec to stdout or to file.
        
        -n gives native format; otherwise print omnispec in json format
           Note: omnispecs are deprecated. Native format is default.
        --omnispec Return Omnispec format rspecs. Deprecated
        -o writes Ad RSpec to file instead of stdout; omnispec written to 1 file,
           native format written to single file per aggregate.
        -p gives filename prefix for each output file
        If not saving results to a file, they are logged.
        If --tostdout option, then instead of logging, print to STDOUT.
        -t <type version>: Specify a required A RSpec type and version to return.
        It skips any AM that doesn't advertise (in GetVersion)
        that it supports that format.
        --slicecredfile says to use the given slicecredfile if it exists.

        File names will indicate the slice name, file format, and either
        the number of Aggregates represented (omnispecs), or
        which aggregate is represented (native format).
        e.g.: myprefix-myslice-rspec-localhost-8001.xml

        If a slice name is supplied, then resources for that slice only 
        will be displayed.  In this case, the slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        Aggregates queried:
        - Single URL given in -a argument or URL listed under that given
        nickname in omni_config, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse
        """

        # An optional slice name might be specified.
        slicename = None
        if len(args) > 0:
            slicename = args[0].strip()

        # check command line args
        if self.opts.output:
            self.logger.info("Saving output to a file.")

        # Query the various aggregates for resources
        # rspecs[(urn, url)] = decompressed native rspec
        (rspecs, message) = self._listresources( args )
        numAggs = 0
        if rspecs is not None:
            numAggs = len(rspecs.keys())
        
        # handle empty case
        if not rspecs or rspecs == {}:
            if slicename:
                prtStr = "Got no resources on slice %s"%slicename 
            else:
                prtStr = "Got no resources" 
            if message is not None:
                prtStr = prtStr + ". " + message
            self.logger.info( prtStr )
            return prtStr, None

 
        # Loop over RSpecs
        # Native mode: print them
        # Omnispec mode: convert them to omnispecs
        returnedRspecs = {}
        omnispecs = {}
        fileCtr = 0
        savedFileDesc = ""
        for ((urn,url), rspec) in rspecs.items():                        
            self.logger.debug("Getting RSpec items for AM urn %s (%s)", urn, url)

            if self.opts.native:
                # Create HEADER
                if slicename is not None:
                    header = "Resources for:\n\tSlice: %s\n\tat AM:\n\tURN: %s\n\tURL: %s\n" % (slicename, urn, url)
                else:
                    header = "Resources at AM:\n\tURN: %s\n\tURL: %s\n" % (urn, url)
                header = "<!-- "+header+" -->"

                # Create BODY
                returnedRspecs[(urn,url)] = rspec
                try:
                    newl = ''
                    if '\n' not in rspec:
                        newl = '\n'
                    content = md.parseString(rspec).toprettyxml(indent=' '*2, newl=newl)
                except:
                    content = rspec

                filename=None
                # Create FILENAME
                if self.opts.output:
                    fileCtr += 1 
                    # Instead of fileCtr: if have a urn, then use that to produce an HRN. Else
                    # remove all punctuation and use URL
                    server = str(fileCtr)
                    if urn and urn is not "unspecified_AM_URN" and (not urn.startswith("http")):
                        # construct hrn
                        # strip off any leading urn:publicid:IDN
                        if urn.find("IDN+") > -1:
                            urn = urn[(urn.find("IDN+") + 4):]
                        urnParts = urn.split("+")
                        server = urnParts.pop(0)
                        server = server.translate(string.maketrans(' .:', '---'))
                    else:
                        # remove all punctuation and use url
                        server = self._filename_part_from_am_url(url)
                    filename = "rspec-" + server+".xml"
                    if slicename:
                        filename = slicename+"-" + filename

                    if self.opts.prefix and self.opts.prefix.strip() != "":
                        filename  = self.opts.prefix.strip() + "-" + filename

                # Create FILE
                # This prints or logs results, depending on filename None
                self._printResults( header, content, filename)
                if filename:
                    savedFileDesc += "Saved listResources RSpec at %s to file %s. \n" % (urn, filename)

            else:
                # Convert RSpec to omnispec
                # Throws exception if unparsable
                try:
                    omnispecs[ url ] = rspec_to_omnispec(urn,rspec)
                    returnedRspecs[(urn,url)] = omnispecs[url]
                except Exception, e:
                    # FIXME: _raise_omni_error instead?
                    # FIXME: stuff the native Rspec into the returnedRspecs?
                    self.logger.error("Failed to parse RSpec from AM %s (%s): %s", urn, url, e)

        # Print omnispecs
        if not self.opts.native:
            # Create HEADER
            if slicename is not None:
                header = "Resources For Slice: %s" % (slicename)
            else:
                header = "Resources"

            # Create BODY
            content = json.dumps(omnispecs, indent=4)

            filename=None
            # Create FILENAME
            if self.opts.output:
                # if this is only 1 AM, use its URN/URL in the filename?
                # else use a count of AMs?
                server = str(numAggs) + "AMs"
                if numAggs == 1 and self.opts.aggregate:
                    # FIXME: We may have a URN or nickname here.
                    # Wouldn't that be better for a filename?
                    server = self._filename_part_from_am_url(self._derefAggNick(self.opts.aggregate)[0])
                filename = "omnispec-" + server + ".json"
                if slicename:
                    filename = slicename+"-" + filename
                if self.opts.prefix and self.opts.prefix.strip() != "":
                    filename  = self.opts.prefix.strip() + "-" + filename
                        
            # Create FILE
            if numAggs>0 and len(omnispecs.keys()) > 0:
                # log or print omnispecs, depending on if filename is None
                self._printResults( header, content, filename)

        # Create RETURNS
        # FIXME: If numAggs is 1 then retVal should just be the rspec?
        if slicename:
            retVal = "Retrieved resources for slice %s from %d aggregates."%(slicename, numAggs)
        else:
            retVal = "Retrieved resources from %d aggregates."%(numAggs)
        if numAggs > 0:
            retVal +="\n"
            if self.opts.native:
                if len(returnedRspecs.keys()) > 0:
                    retVal += "Wrote rspecs from %d aggregates" % numAggs
                    if self.opts.output:
                        retVal +=" to %d files"% fileCtr
                        retVal += "\n" + savedFileDesc
                else:
                    retVal +="No Rspecs succesfully parsed from %d aggregates" % numAggs
            elif len(omnispecs.keys()) > 0:
                retVal += "Wrote omnispecs from %d aggregates" % numAggs
                if self.opts.output:
                    retVal +=" to '%s' file"% filename
            else:
                retVal += "No omnispecs successfully parsed from %d aggregates" % numAggs
            retVal +="."

        retItem = returnedRspecs

        return retVal, retItem
            
    def _ospec_to_rspecs(self, specfile):
        """Convert the given omnispec file into a dict of url => rspec.
        Drop any listed aggregates with nothing marked allocate = True """
        # used by createsliver
        jspecs = {}

        try:
            jspecs = json.loads(file(specfile,'r').read())
        except Exception, exc:
            self._raise_omni_error("Parse error reading omnispec %s: %s" % (specfile, exc))

        # Extract the individual omnispecs from the JSON dict
        omnispecs = {}
        for url, spec_dict in jspecs.items():
            # json produces unicode strings.
            # some libraries like m2crypto can't handle unicode URLs
            url = str(url)
            omnispecs[url] = OmniSpec('', '', dictionary=spec_dict)

        # Only keep omnispecs that have a resource marked 'allocate'
        rspecs = {}
        for (url, ospec) in omnispecs.items():
            if url is None or url.strip() == "":
                self.logger.warn('omnispec format error: Empty URL')
                continue
            allocate = False
            for r in ospec.get_resources().values():
                if r.get_allocate():
                    allocate = True
                    break
            self.logger.debug( 'For %s allocate = %r' % (url, allocate))
            if allocate:
                rspecs[url] = omnispec_to_rspec(ospec, True)
            else:
                self.logger.info('Nothing to allocate at %r', url)
        return rspecs

    def createsliver(self, args):
        """AM API CreateSliver call
        CreateSliver <slicename> <rspec file>
        Return on success the manifest RSpec(s)

        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name>
        (e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

        -n Use native format rspec. Requires -a.
        Native RSpecs are the default, and omnispecs are deprecated.
        --omnispec Use Omnispec rspec format. Deprecated.
        -a Contact only the aggregate at the given URL, or with the given
         nickname that translates to a URL in your omni_config
        --slicecredfile Read slice credential from given file, if it exists
        -o Save result (manifest rspec) in per-Aggregate files
        -p (used with -o) Prefix for resulting manifest RSpec files
        If not saving results to a file, they are logged.
        If --tostdout option, then instead of logging, print to STDOUT.

        Slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        omni_config users section is used to get a set of SSH keys that
        should be loaded onto the remote node to allow SSH login, if the
        remote resource and aggregate support this.

        Note you likely want to check SliverStatus to ensure your resource
        comes up.
        And check the sliver expiration time: you may want to call RenewSliver.
        """

        retVal=''
        if len(args) < 2 or args[0] == None or args[0].strip() == "":
            self._raise_omni_error('createsliver requires 2 args: slicename and an omnispec or rspec filename')

        # check command line args
        if self.opts.native and not self.opts.aggregate:
            # If native is requested, the user must supply an aggregate.
            msg = 'Missing -a argument: Specifying a native RSpec requires specifying an aggregate where you want the reservation.'
            # Calling exit here is a bit of a hammer.
            # Maybe there's a gentler way.
            self._raise_omni_error(msg)

        name = args[0]
        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name.strip())
        (slice_cred, message) = self._get_slice_cred(urn)
        if slice_cred is None:
            self._raise_omni_error('Cannot create sliver %s: Could not get slice credential: %s' % (urn, message))

        expd, slice_exp = self._has_slice_expired(slice_cred)
        if expd:
            self._raise_omni_error('Cannot create sliver for slice %s: Slice has expired at %s' % (urn, slice_exp.isoformat()))

        retVal += self._print_slice_expiration(urn, slice_cred)+"\n"

        # Load up the user's edited omnispec
        specfile = args[1]
        if specfile is None or not os.path.isfile(specfile):
            self._raise_omni_error('File of resources to request missing: %s' % specfile)

        rspecs = None
        if self.opts.native:
            # read the native rspec into a string, and add it to the rspecs dict
            rspecs = {}
            try:
                rspec = file(specfile).read()
                rspecs[self._derefAggNick(self.opts.aggregate)[0]] = rspec
            except Exception, exc:
                self._raise_omni_error('Unable to read rspec file %s: %s'
                         % (specfile, str(exc)))
        else:
            # FIXME: Note this may throw an exception
            # if the omnispec is badly formatted
            # Also note that the resulting RSpecs are of particular
            # formats, that may no longer be supported by AMs
            rspecs = self._ospec_to_rspecs(specfile)

        result = None
        # Copy the user config and read the keys from the files into the structure
        slice_users = copy(self.config['users'])
        if len(slice_users) == 0:
            self.logger.warn("No users defined. No keys will be uploaded to support SSH access.")

        #slice_users = copy(self.omni_config['slice_users'])
        for user in slice_users:
            newkeys = []
            required = ['urn', 'keys']
            for req in required:
                if not req in user:
                    self._raise_omni_error("%s in omni_config is not specified for user %s" % (req,user))

            for key in user['keys'].split(','):        
                try:
                    newkeys.append(file(os.path.expanduser(key.strip())).read())
                except Exception, exc:
                    self.logger.error("Failed to read user key from %s: %s" %(user['keys'], exc))
            user['keys'] = newkeys
            if len(newkeys) == 0:
                self.logger.warn("Empty keys for user %s", user['urn'])
            else:
                self.logger.debug("Newkeys: %r", newkeys)

#            # Now error check the URN. It has to match that in the cert
#            # for AMs of type pg with tag < Tag v4.240? or stable-20110420?
#            # FIXME: Complain if NO urn is that in the cert?
#            # Only do the complaint if there is a PG AM that is old?
#            # Or somehow hold of complaining until per AM we have an issue?
#            certurn = ''
#            try:
#                certurn = gid.GID(filename=self.framework.cert).get_urn()
#            except Exception, exc:
#                self.logger.warn("Failed to get URN from cert %s: %s", self.framework.cert, exc)
#            if certurn != user['urn']:
#                self.logger.warn("Keys MAY not be installed for user %s. In PG prior to stable-20110420, the user URN must match that in your certificate. Your cert has urn %s but you specified that user %s has URN %s. Try making your omni_config user have a matching URN.", user, certurn, user, user['urn'])
#                # FIXME: if len(slice_users) == 1 then use the certurn?

#        if len(slice_users) < 1:
#            self.logger.warn("No user keys found to be uploaded")
        
        # Perform the allocations
        (aggs, message) = self._listaggregates()
        if aggs == {} and message != "":
            retVal += "No aggregates to reserve on: %s" % message

        aggregate_urls = aggs.values()
        for (url, rspec) in rspecs.items():
            # Is this AM listed in the CH or our list of aggregates?
            # If not we won't be able to check its status and delete it later
            if not url in aggregate_urls:
                self.logger.info("""Be sure to remember (write down) AM URL:
             %s. 
             You are reserving resources there, and your clearinghouse
             and config file won't remind you to check that sliver later. 
             Future listresources/sliverstatus/deletesliver calls need to 
             include the arguments 
                   '-a %s'
             arguments again to act on this sliver.""" % (url, url))

            # On Debug print the native version of omnispecs
            if not self.opts.native:
                try:
                    newl = ''
                    if '\n' not in rspec:
                        newl = '\n'
                    self.logger.debug("Native RSpec for %s is:\n%s", url, md.parseString(rspec).toprettyxml(indent=' '*2, newl=newl))
                except:
                    self.logger.debug("Native RSpec for %s is:\n%s", url, rspec)

            # Okay, send a message to the AM this resource came from
            result = None
            client = make_client(url, self.framework, self.opts)
            self.logger.info("Creating sliver(s) from rspec file %s for slice %s", specfile, urn)

            # If ABAC then creds are ABAC creds, else creds are slice_cred
            if is_ABAC_framework(self.framework):
                creds = get_abac_creds(self.framework.abac_dir)
                creds.append(slice_cred)
            else:
                creds = [slice_cred]

            args = [urn, creds, rspec, slice_users]
            if self.opts.api_version == 2:
                # Add the options dict
                args.append(dict())
            (result, message) = _do_ssl(self.framework,
                                        None,
                                        ("Create Sliver %s at %s" % (urn, url)),
                                        client.CreateSliver,
                                        *args)

            # If ABAC then return is a dict with abac_credentials, proof, and normal return
            if isinstance(result, dict):
                if is_ABAC_framework(self.framework):
                    if 'abac_credentials' in result:
                        save_abac_creds(result['abac_credentials'],
                                self.framework.abac_dir)
                    if 'proof' in result:
                        save_proof(self.framework.abac_log, result['proof'])
                if 'manifest' in result:
                    result = result['manifest']
                elif 'code' in result:
                    # Probably V2 API
                    if result['code']['geni_code'] == 0:
                        result = result['value']
                    else:
                        message = result['output']
                        result = None

            prettyresult = result
            
            if rspec_util.is_rspec_string( result ):
                try:
                    newl = ''
                    if '\n' not in result:
                        newl = '\n'
                    prettyresult = md.parseString(result).toprettyxml(indent=' '*2, newl=newl)
                except:
                    pass
                # summary
                retVal += 'Reserved resources on %s. ' % (url)

            else:
                # summary
                retVal += 'Asked %s to reserve resources. No manifest Rspec returned. ' % (url)
                if result is None and message != "":
                    retVal += message

            # FIXME: When Tony revises the rspec, fix this test
            if '<RSpec' in rspec and 'type="SFA"' in rspec:
                # Figure out the login name
                # We could of course do this for the user.
                prstr = "Please run the omni sliverstatus call on your slice %s to determine your login name to PL resources." % name
                self.logger.info(prstr)
                retVal += ". " + prstr

            # If the user specified -o then we save the return from
            # each AM as though it is a native manifest RSpec in a
            # separate file
            # Create HEADER
            header = "<!-- Reserved resources for:\n\tSlice: %s\n\tAt AM:\n\tURL: %s\n -->" % (name, url)
            filename = None
            if self.opts.output:
                # create filename
                # remove all punctuation and use url
                server = self._filename_part_from_am_url(url)
                filename = name+"-manifest-rspec-"+server+".xml"
                if self.opts.prefix and self.opts.prefix.strip() != "":
                    filename  = self.opts.prefix.strip() + "-" + filename
                        
                self.logger.info("Writing result of createsliver for slice: %s at AM: %s to file %s", name, url, filename)
                retVal += '\n   Saved createsliver results to %s. ' % (filename)
            else:
                self.logger.info('Asked %s to reserve resources. Result:' % (url))

            # Print or log results, putting header first
            self._printResults( header, prettyresult, filename)

        return retVal, result

    def renewsliver(self, args):
        """AM API RenewSliver <slicename> <new expiration time in UTC
        or with a timezone>
        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name>
        (e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

        Slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        Aggregates queried:
        - Single URL given in -a argument or URL listed under that given
        nickname in omni_config, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse

        Note that per the AM API expiration times will be timezone aware.
        Unqualified times are assumed to be in UTC.
        Note that the expiration time cannot be past your slice expiration
        time (see renewslice). Some aggregates will
        not allow you to _shorten_ your sliver expiration time.
        """
        if len(args) < 2 or args[0] == None or args[0].strip() == "":
            self._raise_omni_error('renewsliver requires arg of slice name and new expiration time in UTC')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        (slice_cred, message) = self._get_slice_cred(urn)
        if slice_cred is None:
            self._raise_omni_error('Cannot renew sliver %s: Could not get slice credential: %s' % (urn, message))

        expd, slice_exp = self._has_slice_expired(slice_cred)
        if expd:
            self._raise_omni_error('Cannot get renewsliver for slice %s: Slice has expired at %s' % (urn, slice_exp.isoformat()))

        time = None
        try:
            time = dateutil.parser.parse(args[1])
        except Exception, exc:
            self._raise_omni_error('renewsliver couldnt parse new expiration time from %s: %r' % (args[1], exc))

        # Convert to naive UTC time if necessary for ease of comparison
        time = naiveUTC(time)

        retVal = ''

        # Compare requested time with slice expiration time
        retVal += self._print_slice_expiration(urn, slice_cred) +"\n"
        if time > slice_exp:
            self._raise_omni_error('Cannot renew sliver %s until %s UTC because it is after the slice expiration time %s UTC' % (urn, time, slice_exp))
        elif time <= datetime.datetime.utcnow():
            self.logger.info('Sliver %s will be set to expire now' % urn)
            time = datetime.datetime.utcnow()
        else:
            self.logger.debug('Slice expires at %s UTC after requested time %s UTC' % (slice_exp, time))

        # Add UTC TZ, to have an RFC3339 compliant datetime, per the AM API
        time_with_tz = time.replace(tzinfo=dateutil.tz.tzutc())

        self.logger.info('Renewing Sliver %s until %s (UTC)' % (urn, time_with_tz))

        if self.opts.orca_slice_id:
            self.logger.info('Using ORCA slice id %r', self.opts.orca_slice_id)
            urn = self.opts.orca_slice_id

        successCnt = 0
        successList = []
        failList = []
        (clientList, message) = self._getclients()
        for client in clientList:
            # Add ABAC Creds if necessary, else it is just the slice_cred
            if is_ABAC_framework(self.framework):
                creds = get_abac_creds(self.framework.abac_dir)
                creds.append(slice_cred)
            else:
                creds = [slice_cred]
            # Note that the time arg includes UTC offset as needed
            time_string = time_with_tz.isoformat()
            if self.opts.no_tz:
                # The timezone causes an error in older sfa
                # implementations as deployed in mesoscale GENI. Strip
                # off the timezone if the user specfies --no-tz
                self.logger.info('Removing timezone at user request (--no-tz)')
                time_string = time_with_tz.replace(tzinfo=None).isoformat()

            args = [urn, creds, time_string]
            if self.opts.api_version == 2:
                # Add the options dict
                args.append(dict())
            (res, message) = _do_ssl(self.framework,
                                     None,
                                     ("Renew Sliver %s on %s" % (urn, client.url)),
                                     client.RenewSliver,
                                     *args)
            # Unpack ABAC results: A dict with abac_credentials, proof, and the normal return
            if isinstance(res, dict):
                if is_ABAC_framework(self.framework):
                    if 'abac_credentials' in res:
                        save_abac_creds(res['abac_credentials'],
                                self.framework.abac_dir)
                    if 'proof' in res:
                        save_proof(self.framework.abac_log, res['proof'])
                if 'success' in res:
                    res = res['success']
                if 'code' in res:
                    # AM API v2
                    if res['code']['geni_code'] == 0:
                        res = res['value']
                    else:
                        message = res['output']
                        res = None

            if not res:
                prStr = "Failed to renew sliver %s on %s (%s)" % (urn, client.urn, client.url)
                if message != "":
                    prStr += " " + message
                if len(clientList) == 1:
                    retVal += prStr + "\n"
                self.logger.warn(prStr)
                failList.append( client.url )
            else:
                prStr = "Renewed sliver %s at %s (%s) until %s (UTC)" % (urn, client.urn, client.url, time_with_tz.isoformat())
                self.logger.info(prStr)
                if len(clientList) == 1:
                    retVal += prStr + "\n"
                successCnt += 1
                successList.append( client.url )
        if len(clientList) == 0:
            retVal += "No aggregates on which to renew slivers for slice %s. %s\n" % (urn, message)
        elif len(clientList) > 1:
            retVal += "Renewed slivers on %d out of %d aggregates for slice %s until %s (UTC)\n" % (successCnt, len(clientList), urn, time_with_tz)
        return retVal, (successList, failList)

    def sliverstatus(self, args):
        """AM API SliverStatus  <slice name>
        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name>
        (e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

        Slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        Aggregates queried:
        - Single URL given in -a argument or URL listed under that given
        nickname in omni_config, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse

        -o Save result in per-Aggregate files
        -p (used with -o) Prefix for resulting files
        If not saving results to a file, they are logged.
        If --tostdout option, then instead of logging, print to STDOUT.
        """
        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            self._raise_omni_error('sliverstatus requires arg of slice name')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        (slice_cred, message) = self._get_slice_cred(urn)
        if slice_cred is None:
            self._raise_omni_error('Cannot get sliver status for %s: Could not get slice credential: %s' % (urn, message))

        expd, slice_exp = self._has_slice_expired(slice_cred)
        if expd:
            self._raise_omni_error('Cannot get sliverstatus for slice %s: Slice has expired at %s' % (urn, slice_exp.isoformat()))

        retVal = self._print_slice_expiration(urn, slice_cred) + "\n"

        if self.opts.orca_slice_id:
            self.logger.info('Using ORCA slice id %r', self.opts.orca_slice_id)
            urn = self.opts.orca_slice_id

        successCnt = 0
        retItem = {}
        # Query status at each client
        (clientList, message) = self._getclients()
        if len(clientList) > 0:
            self.logger.info('Status of Slice %s:' % urn)
        else:
            prstr = "No aggregates available to get slice status at: %s" % message
            retVal += prstr + "\n"
            self.logger.warn(prstr)

        for client in clientList:
            # Add ABAC Creds if necessary to the normal slice_cred
            if is_ABAC_framework(self.framework):
                creds = get_abac_creds(self.framework.abac_dir)
                creds.append(slice_cred)
            else:
                creds = [slice_cred]

            args = [urn, creds]
            if self.opts.api_version == 2:
                # Add the options dict
                args.append(dict())
            (status, message) = _do_ssl(self.framework,
                                        None,
                                        "Sliver status of %s at %s" % (urn, client.url),
                                        client.SliverStatus, *args)
            # Unpack ABAC results from a dict that includes proof
            if status and 'proof' in status:
                if is_ABAC_framework(self.framework):
                    save_proof(self.framework.abac_log, status['proof'])
                    # XXX: may not need to do delete the proof dict entry
                    del status['proof']
            if status and 'code' in status:
                # AM API v2
                if status['code']['geni_code'] == 0:
                    status = status['value']
                else:
                    message = status['output']
                    status = None
            if status:
                prettyResult = pprint.pformat(status)
                header="Sliver status for Slice %s at AM URL %s" % (urn, client.url)
                filename = None
                if self.opts.output:
                    # better filename
                    # remove all punctuation and use url
                    server = self._filename_part_from_am_url(client.url)
                    filename = name+"-sliverstatus-"+server+".json"
                    if self.opts.prefix and self.opts.prefix.strip() != "":
                        filename  = self.opts.prefix.strip() + "-" + filename
                        
                    #self.logger.info("Writing result of sliverstatus for slice: %s at AM: %s to file %s", name, client.url, filename)
                    
                self._printResults(header, prettyResult, filename)
                if filename:
                    retVal += "Saved sliverstatus on %s at AM %s to file %s. \n" % (name, client.url, filename)
                retItem[ client.url ] = status
                successCnt+=1
            else:
                # FIXME: Put the message error in retVal?
                retItem[ client.url ] = False
                retVal += "\nFailed to get SliverStatus on %s at AM %s: %s\n" % (name, client.url, message)

        # FIXME: Return the status if there was only 1 client?
        retVal += "Returned status of slivers on %d of %d possible aggregates." % (successCnt, len(clientList))
        return retVal, retItem
                
    def deletesliver(self, args):
        """AM API DeleteSliver <slicename>
        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name>
        (e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

        Slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        Aggregates queried:
        - Single URL given in -a argument or URL listed under that given
        nickname in omni_config, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse
        """
        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            self._raise_omni_error('deletesliver requires arg of slice name')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        (slice_cred, message) = self._get_slice_cred(urn)
        if slice_cred is None:
            self._raise_omni_error('Cannot delete sliver %s: Could not get slice credential: %s' % (urn, message))

        # Here we would abort if the slice has expired
        # But perhaps we should keep going so if there are resources
        # at the aggregate, it can use this cue to free them?
        expd, slice_exp = self._has_slice_expired(slice_cred)
        if expd:
            self._raise_omni_error('Cannot delete sliver for slice %s: Slice has expired at %s' % (urn, slice_exp.isoformat()))

        if self.opts.orca_slice_id:
            self.logger.info('Using ORCA slice id %r', self.opts.orca_slice_id)
            urn = self.opts.orca_slice_id

        retVal = ""
        successList = []
        failList = []
        successCnt = 0
        (clientList, message) = self._getclients()

        # Connect to each available GENI AM
        ## The AM API does not cleanly state how to deal with
        ## aggregates which do not have a sliver in this slice.  We
        ## know at least one aggregate (PG) returns an Exception in
        ## this case.
        ## FIX ME: May need to look at handling of this more in the future.
        ## Also, if the user supplied the aggregate list, a failure is
        ## more interesting.  We can figure out what the error strings
        ## are at the various aggregates if they don't know about the
        ## slice and make those more quiet.  Finally, we can try
        ## sliverstatus at places where it fails to indicate places
        ## where you still have resources.
        for client in clientList:
            #Gather ABAC certs if we need them to add to the slice_cred
            if is_ABAC_framework(self.framework):
                creds = get_abac_creds(self.framework.abac_dir)
                creds.append(slice_cred)
            else:
                creds = [slice_cred]

            args = [urn, creds]
            if self.opts.api_version == 2:
                # Add the options dict
                args.append(dict())
            (res, message) = _do_ssl(self.framework,
                                     None,
                                     ("Delete Sliver %s on %s" % (urn, client.url)),
                                     client.DeleteSliver,
                                     *args)
            # Unpack ABAC results from a dict with proof and normal result
            if isinstance(res, dict):
                if is_ABAC_framework(self.framework):
                    if 'proof' in res:
                        save_proof(self.framework.abac_log, res['proof'])
                if 'success' in res:
                    res = res['success']
                if 'code' in res:
                    # AM API v2
                    if res['code']['geni_code'] == 0:
                        res = res['value']
                    else:
                        message = res['output']
                        res = None

            if res:
                prStr = "Deleted sliver %s on %s at %s" % (urn,
                                                           client.urn,
                                                           client.url)
                if len(clientList) == 1:
                    retVal = prStr
                self.logger.info(prStr)
                successCnt += 1
                successList.append( client.url )
            else:
                prStr = "Failed to delete sliver %s on %s at %s" % (urn, client.urn, client.url)
                if message != "":
                    prStr += " " + message
                self.logger.warn(prStr)
                if len(clientList) == 1:
                    retVal = prStr
                failList.append( client.url )
        if len(clientList) == 0:
            retVal = "No aggregates specified on which to delete slivers. %s" % message
        elif len(clientList) > 1:
            retVal = "Deleted slivers on %d out of a possible %d aggregates" % (successCnt, len(clientList))
        return retVal, (successList, failList)

    def shutdown(self, args):
        """AM API Shutdown <slicename>
        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name>
        (e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

        Slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        Aggregates queried:
        - Single URL given in -a argument or URL listed under that given
        nickname in omni_config, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse
        """
        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            self._raise_omni_error('shutdown requires arg of slice name')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        (slice_cred, message) = self._get_slice_cred(urn)
        if slice_cred is None:
            self._raise_omni_error('Cannot shutdown slice %s: Could not get slice credential: %s' % (urn, message))

        expd, slice_exp = self._has_slice_expired(slice_cred)
        if expd:
            self._raise_omni_error('Cannot shutdown slice %s: Slice has expired at %s' % (urn, slice_exp.isoformat()))

        if self.opts.orca_slice_id:
            self.logger.info('Using ORCA slice id %r', self.opts.orca_slice_id)
            urn = self.opts.orca_slice_id

        #Call shutdown on each AM
        retVal = ""
        successCnt = 0
        successList = []
        failList = []
        (clientList, message) = self._getclients()
        for client in clientList:
            # Add ABAC Creds if necessary to the slice_cred
            if is_ABAC_framework(self.framework):
                creds = get_abac_creds(self.framework.abac_dir)
                creds.append(slice_cred)
            else:
                creds = [slice_cred]

            args = [urn, creds]
            if self.opts.api_version == 2:
                # Add the options dict
                args.append(dict())
            (res, message) = _do_ssl(self.framework,
                                     None,
                                     "Shutdown %s on %s" % (urn, client.url),
                                     client.Shutdown,
                                     *args)
            # Unpack ABAC results from a dict with proof, normal result
            if isinstance(res, dict):
                if is_ABAC_framework(self.framework):
                    if 'proof' in res:
                        save_proof(self.abac_log, res['proof'])
                if 'success' in res:
                    res = res['success']
                if 'code' in res:
                    # AM API v2
                    if res['code']['geni_code'] == 0:
                        res = res['value']
                    else:
                        message = res['output']
                        res = None
            if res:
                prStr = "Shutdown Sliver %s on AM %s at %s" % (urn, client.urn, client.url)
                self.logger.info(prStr)
                if len(clientList) == 1:
                    retVal = prStr
                successCnt+=1
                successList.append( client.url )
            else:
                prStr = "Failed to shutdown sliver %s on AM %s at %s" % (urn, client.urn, client.url) 
                if message != "":
                    prStr += ". " + message
                self.logger.warn(prStr)
                if len(clientList) == 1:
                    retVal = prStr
                failList.append( client.url )
        if len(clientList) == 0:
            retVal = "No aggregates specified on which to shutdown slice %s. %s" % (urn, message)
        elif len(clientList) > 1:
            retVal = "Shutdown slivers of slice %s on %d of %d possible aggregates" % (urn, successCnt, len(clientList))
        return retVal, (successList, failList)

    # End of AM API operations
    #########################################
    # Start of control framework operations

    def listaggregates(self, args):
        """Print the known aggregates' URN and URL
        Gets aggregates from:
        - command line (one, no URN available), OR
        - command line nickname (one, URN may be supplied), OR
        - omni_config (1+, no URNs available), OR
        - Specified control framework (via remote query).
        This is the aggregates that registered with the framework.
        """
        retStr = ""
        retVal = {}
        (aggs, message) = self._listaggregates()
        aggList = aggs.items()
        self.logger.info("Listing %d aggregates..."%len(aggList))
        aggCnt = 0
        for (urn, url) in aggList:
            aggCnt += 1
            self.logger.info( "  Aggregate %d:\n \t%s \n \t%s" % (aggCnt, urn, url) )
#            retStr += "%s: %s\n" % (urn, url)
            retVal[urn] = url
        if aggs == {} and message != "":
            retStr += "No aggregates found: %s"
        elif len(aggList)==0:
            retStr = "No aggregates found."
        elif len(aggList) == 1:
            retStr = "Found 1 aggregate. URN: %s; URL: %s" % (retVal.keys()[0], retVal[retVal.keys()[0]])
        else:
            retStr = "Found %d aggregates." % len(aggList)
        return retStr, retVal

    def createslice(self, args):
        """Create a Slice at the given Slice Authority.
        Arg: slice name
        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name>
        (e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

        To create the slice and save off the slice credential:
           omni.py -o createslice myslice
        To create the slice and save off the slice credential to a specific file:
           omni.py -o --slicecredfile mySpecificfile-myslice-credfile.xml
                   createslice myslice

        Note that Slice Authorities typically limit this call to privileged
        users, e.g. PIs.

        Note also that typical slice lifetimes are short. See RenewSlice.
        """
        retVal = ""
        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            self._raise_omni_error('createslice requires arg of slice name')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        
        (slice_cred, message) = _do_ssl(self.framework, None, "Create Slice %s" % urn, self.framework.create_slice, urn)
        if slice_cred:
            slice_exp = credutils.get_cred_exp(self.logger, slice_cred)
            printStr = "Created slice with Name %s, URN %s, Expiration %s" % (name, urn, slice_exp) 
            retVal += printStr+"\n"
            self.logger.info( printStr )
            filename = self._maybe_save_slicecred(name, slice_cred)
            if filename is not None:
                prstr = "Wrote slice %s credential to file '%s'" % (name, filename)
                retVal += prstr + "\n"
                self.logger.info(prstr)

            success = urn

        else:
            printStr = "Create Slice Failed for slice name %s." % (name) 
            if message != "":
                printStr += " " + message
            retVal += printStr+"\n"
            self.logger.error( printStr )
            success = None
            if not self.logger.isEnabledFor(logging.DEBUG):
                self.logger.warn( "   Try re-running with --debug for more information." )
        return retVal, success
        
    def renewslice(self, args):
        """Renew the slice at the clearinghouse so that the slivers can be
        renewed.
        Args: slicename, and expirationdate
          Note that Slice Authorities may interpret dates differently if you do not
          specify a timezone. SFA drops any timezone information though.
        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name>
        (e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

        Return summary string, new slice expiration (string)
        """
        if len(args) != 2 or args[0] == None or args[0].strip() == "":
            self._raise_omni_error('renewslice missing args: Supply <slice name> <expiration date>')
        name = args[0]
        expire_str = args[1]

        # convert the slice name to a framework urn
        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)

        # convert the desired expiration to a python datetime
        try:
            in_expiration = dateutil.parser.parse(expire_str)
        except:
            msg = 'Unable to parse date "%s".\nTry "YYYYMMDDTHH:MM:SSZ" format'
            msg = msg % (expire_str)
            self._raise_omni_error(msg)

        # Try to renew the slice
        (out_expiration, message) = _do_ssl(self.framework, None, "Renew Slice %s" % urn, self.framework.renew_slice, urn, in_expiration)

        if out_expiration:
            prtStr = "Slice %s now expires at %s UTC" % (name, out_expiration)
            self.logger.info( prtStr )
            retVal = prtStr+"\n"
            retTime = out_expiration
        else:
            prtStr = "Failed to renew slice %s" % (name)
            if message != "":
                prtStr += ". " + message
            self.logger.warn( prtStr )
            retVal = prtStr+"\n"
            retTime = None
        retVal +=self._print_slice_expiration(urn)
        return retVal, retTime

    def deleteslice(self, args):
        """Framework specific DeleteSlice call at the given Slice Authority
        Arg: slice name
        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name>
        (e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).

        Delete all your slivers first!
        This does not free up resources at various aggregates.
        """
        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            self._raise_omni_error('deleteslice requires arg of slice name')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)

        (res, message) = _do_ssl(self.framework, None, "Delete Slice %s" % urn, self.framework.delete_slice, urn)
        # return True if successfully deleted slice, else False
        if (res is None) or (res is False):
            retVal = False
        else:
            retVal = True
        prtStr = "Delete Slice %s result: %r" % (name, res)
        if res is None and message != "":
            prtStr += ". " + message
        self.logger.info(prtStr)
        return prtStr, retVal

    def listmyslices(self, args):
        """Provides a list of slices of user provided as first argument.
        Not supported by all frameworks."""
        if len(args) > 0:
            username = args[0].strip()
        else:
            self._raise_omni_error('listmyslices requires 1 arg: user')

        retStr = ""
        (slices, message) = _do_ssl(self.framework, None, "List Slices from Slice Authority", self.framework.list_my_slices, username)
        if slices is None:
            # only end up here if call to _do_ssl failed
            slices = []
            self.logger.error("Failed to list slices for user '%s'"%(username))
            retStr += "Server error: %s. " % message
        elif len(slices) > 0:
            self.logger.info("User '%s' has slices: \n\t%s"%(username,"\n\t".join(slices)))
        else:
            self.logger.info("User '%s' has NO slices."%username)

        # summary
        retStr += "Found %d slices for user '%s'.\n"%(len(slices), username)

        return retStr, slices

    def getusercred(self, args):
        """Save your user credential to <framework nickname>-usercred.xml
        Useful for debugging."""
        (cred, message) = self.framework.get_user_cred()
        
        if cred is None:
            self._raise_omni_error("Got no user credential from framework: %s" % message)
        fname = self.opts.framework + "-usercred.xml"
        self.logger.info("Writing your user credential to %s" % fname)
        with open(fname, "wb") as file:
            file.write(cred)
        self.logger.info("User credential:\n%r", cred)
        return "Saved user credential to %s" % fname, cred

    def getslicecred(self, args):
        """Get the AM API compliant slice credential (signed XML document).

        If you specify the -o option, the credential is saved to a file.
        The filename is <slicename>-cred.xml
        But if you specify the --slicecredfile option then that is the
        filename used.

        Additionally, if you specify the --slicecredfile option and that
        references a file that is not empty, then we do not query the Slice
        Authority for this credential, but instead read it from this file.

        e.g.:
          Get slice mytest credential from slice authority, save to a file:
            omni.py -o getslicecred mytest
          
          Get slice mytest credential from slice authority, save to a file with prefix mystuff:
            omni.py -o -p mystuff getslicecred mytest

          Get slice mytest credential from slice authority, save to a file with name mycred.xml:
            omni.py -o --slicecredfile mycred.xml getslicecred mytest

          Get slice mytest credential from saved file (perhaps a delegated credential?) delegated-mytest-slicecred.xml:
            omni.py --slicecredfile delegated-mytest-slicecred.xml getslicecred mytest

        Arg: slice name
        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name>
        (e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).
        """

        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            # could print help here but that's verbose
            #parse_args(None)
            self._raise_omni_error('getslicecred requires arg of slice name')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        (cred, message) = self._get_slice_cred(urn)

        if cred is None:
            retVal = "No slice credential returned for slice %s: %s"%(urn, message)
            return retVal, None

        # Log if the slice expires soon
        self._print_slice_expiration(urn, cred)

        # Print the non slice cred bit to log stream so
        # capturing just stdout gives just the cred hopefully
        self.logger.info("Retrieved slice cred for slice %s", urn)
#VERBOSE ONLY        self.logger.info("Slice cred for slice %s", urn)
#VERBOSE ONLY        self.logger.info(cred)
#        print cred

        retVal = cred
        retItem = cred
        filename = self._maybe_save_slicecred(name, cred)
        if filename is not None:
            self.logger.info("Wrote slice %s credential to file '%s'" % (name, filename))
            retVal = "Saved slice %s cred to file %s" % (name, filename)

        return retVal, retItem

    def print_slice_expiration(self, args):
        """Print the expiration time of the given slice, and a warning
        if it is soon.
        Arg: slice name
        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name>
        (e.g. bbn_myslice), and we want only the slice name part here (e.g. myslice).
        """

        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            # could print help here but that's verbose
            #parse_args(None)
            self._raise_omni_error('print_slice_expiration requires arg of slice name')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        (cred, message) = self._get_slice_cred(urn)

        retVal = None
        if cred is None:
            retVal = "No slice credential returned for slice %s: %s"%(urn, message)
            return retVal, None

        # Log if the slice expires soon
        retVal = self._print_slice_expiration(urn, cred)
        return retVal, retVal

    ####################
    ## Various helper functions follow
        
    def _maybe_save_slicecred(self, name, slicecred):
        """Save slice credential to a file, returning the filename or
        None on error or config not specifying -o

        Only saves if self.opts.output and non-empty credential

        If you didn't specify -o but do specify --tostdout, then write
        the slice credential to STDOUT

        Filename is:
        --slicecredfile if supplied
        else [<--p value>-]-<slicename>-cred.xml
        """
        if name is None or name.strip() == "" or slicecred is None or slicecred.strip() is None:
            return None

        filename = None
        if self.opts.output:
            if self.opts.slicecredfile:
                filename = self.opts.slicecredfile
            else:
                filename = name + "-cred.xml"
                if self.opts.prefix and self.opts.prefix.strip() != "":
                    filename = self.opts.prefix.strip() + "-" + filename
            with open(filename, 'w') as file:
                file.write(slicecred + "\n")
        elif self.opts.tostdout:
            self.logger.info("Writing slice %s cred to STDOUT per options", name)
            print slicecred
        return filename

    def _has_slice_expired(self, sliceCred):
        """Return (boolean, expiration datetime) whether given slicecred (string) has expired)"""
        if sliceCred is None:
            return (True, None)
        sliceexp = credutils.get_cred_exp(self.logger, sliceCred)
        sliceexp = naiveUTC(sliceexp)
        now = datetime.datetime.utcnow()
        if sliceexp <= now:
            return (True, sliceexp)
        return (False, sliceexp)

    def _print_slice_expiration(self, urn, sliceCred=None):
        """Check when the slice expires. Print varying warning notices
        and the expiration date"""
        # FIXME: push this to config?
        shorthours = 3
        middays = 1

        # This could be used to print user credential expiration info too...

        if sliceCred is None:
            if urn is None or urn == '':
                return ""
            (sliceCred, _) = self._get_slice_cred(urn)
        if sliceCred is None:
            # failed to get a slice string. Can't check
            return ""

        sliceexp = credutils.get_cred_exp(self.logger, sliceCred)
        sliceexp = naiveUTC(sliceexp)
        now = datetime.datetime.utcnow()
        if sliceexp <= now:
            retVal = 'Slice %s has expired at %s UTC' % (urn, sliceexp)
            self.logger.warn('Slice %s has expired at %s UTC' % (urn, sliceexp))
        elif sliceexp - datetime.timedelta(hours=shorthours) <= now:
            retVal = 'Slice %s expires in <= %d hours on %s UTC' % (urn, shorthours, sliceexp)
            self.logger.warn('Slice %s expires in <= %d hours' % (urn, shorthours))
            self.logger.info('Slice %s expires on %s UTC' % (urn, sliceexp))
            self.logger.debug('It is now %s UTC' % (datetime.datetime.utcnow()))
        elif sliceexp - datetime.timedelta(days=middays) <= now:
            retVal = 'Slice %s expires within %d day(s) on %s UTC' % (urn, middays, sliceexp)
            self.logger.info('Slice %s expires within %d day on %s UTC' % (urn, middays, sliceexp))
        else:
            retVal = 'Slice %s expires on %s UTC' % (urn, sliceexp)
            self.logger.info('Slice %s expires on %s UTC' % (urn, sliceexp))
        return retVal

    def _get_slice_cred(self, urn):
        """Try a couple times to get the given slice credential.
        Retry on wrong pass phrase.
        Return the slice credential, and a string message of any error.
        """

        if self.opts.slicecredfile and os.path.exists(self.opts.slicecredfile) and os.path.isfile(self.opts.slicecredfile) and os.path.getsize(self.opts.slicecredfile) > 0:
            # read the slice cred from the given file
            self.logger.info("Getting slice %s credential from file %s", urn, self.opts.slicecredfile)
            cred = None
            with open(self.opts.slicecredfile, 'r') as f:
                cred = f.read()
            return (cred, "")

        # Check that the return is either None or a valid slice cred
        # Callers handle None - usually by raising an error
        (cred, message) = _do_ssl(self.framework, None, "Get Slice Cred for slice %s" % urn, self.framework.get_slice_cred, urn)
        if cred is not None and (not (type(cred) is str and cred.startswith("<"))):
            #elif slice_cred is not XML that looks like a credential, assume
            # assume it's an error message, and raise an omni_error
            self.logger.error("Got invalid slice credential for slice %s: %s" % (urn, cred))
            cred = None
            message = "Invalid slice credential returned"
        return (cred, message)

    def _getclients(self, ams=None):
        """Create XML-RPC clients for each aggregate (from commandline,
        else from config file, else from framework)
        Return them as a sequence.
        Each client has a urn and url. See _listaggregates for details.
        """
        clients = []
        (aggs, message) = self._listaggregates()
        if aggs == {} and message != "":
            self.logger.warn('No aggregates found: %s', message)
            return (clients, message)

        for (urn, url) in aggs.items():
            client = make_client(url, self.framework, self.opts)
            client.urn = urn
            client.url = url
            clients.append(client)

        return (clients, message)

    def _derefAggNick(self, aggregateNickname):
        """Check if the given aggregate string is a nickname defined
        in omni_config. If so, return the dereferenced URL,URN.
        Else return the input as the URL, and 'unspecified_AM_URN' as the URN."""

        if not aggregateNickname:
            return (None, None)
        aggregateNickname = aggregateNickname.strip()
        urn = "unspecified_AM_URN"
        url = aggregateNickname

        if self.config['aggregate_nicknames'].has_key(aggregateNickname):
            url = self.config['aggregate_nicknames'][aggregateNickname][1]
            tempurn = self.config['aggregate_nicknames'][aggregateNickname][0]
            if tempurn.strip() != "":
                urn = tempurn
            self.logger.info("Substituting AM nickname %s with URL %s, URN %s", aggregateNickname, url, urn)

        return url,urn


    def _listaggregates(self):
        """List the aggregates that can be used for the current operation.
        If an aggregate was specified on the command line, use only that one.
        Else if aggregates are specified in the config file, use that set.
        Else ask the framework for the list of aggregates.
        Returns the aggregates as a dict of urn => url pairs.
           If one URL was given on the commandline, AM URN is a constant
           If multiple URLs were given in the omni config, URN is really the URL
        """
        # used by _getclients (above), createsliver, listaggregates
        if self.opts.aggregate:
            # Try treating that as a nickname
            # otherwise it is the url directly
            # Either way, if we have no URN, we fill in 'unspecified_AM_URN'
            url, urn = self._derefAggNick(self.opts.aggregate)
            _ = urn # appease eclipse
            ret = {}
            url = url.strip()
            if url != '':
                ret[urn] = url
            return (ret, "")
        elif not self.omni_config.get('aggregates', '').strip() == '':
            aggs = {}
            for url in self.omni_config['aggregates'].strip().split(','):
                url = url.strip()
                if url != '':
                    aggs[url] = url
            return (aggs, "")
        else:
            (aggs, message) =  _do_ssl(self.framework, None, "List Aggregates from control framework", self.framework.list_aggregates)
            if aggs is None:
                # FIXME: Return the message?
                return ({}, message)
            return (aggs, "")

# End of CallHandler


def countSuccess( successList, failList ):
    """Intended to be used with 'renewsliver', 'deletesliver', and
    'shutdown' which return a two item tuple as their second
    arguement.  The first item is a list of urns/urls for which it
    successfully performed the operation.  The second item is a
    list of the urns/urls for which it did not successfully
    perform the operation.  Failure could be due to an actual
    error or just simply that there were no such resources
    allocated to this sliver at that aggregates.  In this context
    this method returns a tuple containing the number of items
    which succeeded and the number of items attempted.
    """
    succNum = len( successList )
    return (succNum, succNum + len( failList ) )

def validate_url(url):
    """Basic sanity checks on URLS before trying to use them.
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

def make_client(url, framework, opts):
    """ Create an xmlrpc client, skipping the client cert if not opts.ssl"""

    warnprefix = "WARN: "
    err = validate_url(url)
    if err is not None:
        if hasattr(framework, 'logger'):
            logger = framework.logger
        else:
            logger = logging.getLogger("omni")
        if err.find(warnprefix) == 0:
            err = err[len(warnprefix):]
            logger.warn(err)
        else:
            logger.error(err)
            raise OmniError(err)

    if opts.ssl:
        return omnilib.xmlrpc.client.make_client(url, framework.key, framework.cert)
    else:
        return omnilib.xmlrpc.client.make_client(url, None, None)

def load_config(opts, logger):
    """Load the omni config file.
    Search path:
    - filename from commandline
      - in current directory
      - in ~/.gcf
    - omni_config in current directory
    - omni_config in ~/.gcf
    """

    # Load up the config file
    configfiles = ['omni_config','~/.gcf/omni_config']

    if opts.configfile:
        # if configfile defined on commandline does not exist, fail
        if os.path.exists( opts.configfile ):
            configfiles.insert(0, opts.configfile)
        else:
            # Check maybe the default directory for the file
            configfile = os.path.join( '~/.gcf', opts.configfile )
            configfile = os.path.expanduser( configfile )
            if os.path.exists( configfile ):
                configfiles.insert(0, configfile)
            else:
                logger.error("Config file '%s'or '%s' does not exist"
                     % (opts.configfile, configfile))
                raise (OmniError, "Config file '%s'or '%s' does not exist"
                     % (opts.configfile, configfile))

    # Find the first valid config file
    for cf in configfiles:         
        filename = os.path.expanduser(cf)
        if os.path.exists(filename):
            break
    
    # Did we find a valid config file?
    if not os.path.exists(filename):
        prtStr = """ Could not find an omni configuration file in local directory or in ~/.gcf/omni_config
     An example config file can be found in the source tarball or on the wiki"""
        logger.error( prtStr )
        raise OmniError, prtStr

    logger.info("Loading config file %s", filename)
    
    confparser = ConfigParser.RawConfigParser()
    try:
        confparser.read(filename)
    except ConfigParser.Error as exc:
        logger.error("Config file %s could not be parsed: %s"% (filename, str(exc)))
        raise OmniError, "Config file %s could not be parsed: %s"% (filename, str(exc))

    # Load up the omni options
    config = {}
    config['logger'] = logger
    config['omni'] = {}
    for (key,val) in confparser.items('omni'):
        config['omni'][key] = val
        
    # Load up the users the user wants us to see        
    config['users'] = []
    if 'users' in config['omni']:
        for user in config['omni']['users'].split(','):
            d = {}
            for (key,val) in confparser.items(user.strip()):
                d[key] = val
            config['users'].append(d)

    # Find aggregate nicknames
    config['aggregate_nicknames'] = {}
    if confparser.has_section('aggregate_nicknames'):
        for (key,val) in confparser.items('aggregate_nicknames'):
            temp = val.split(',')
            for i in range(len(temp)):
                temp[i] = temp[i].strip()
            if len(temp) != 2:
                logger.warn("Malformed definition of aggregate nickname %s. Should be <URN>,<URL> where URN may be empty. Got: %s", key, val)
            if len(temp) == 0:
                continue
            if len(temp) == 1:
                # Got 1 entry - if its a valid URL, use it
                res = validate_url(temp[0])
                if res is None or res.startswith("WARN:"):
                    t = temp[0]
                    temp = ["",t]
                else:
                    # not a valid URL. Skip it
                    logger.warn("Skipping aggregate nickname %s: %s doesn't look like a URL", key, temp[0])
                    continue

            # If temp len > 2: try to use it as is

            config['aggregate_nicknames'][key] = temp

    # Load up the framework section
    if not opts.framework:
        opts.framework = config['omni']['default_cf']

    logger.info("Using control framework %s" % opts.framework)

    # Find the control framework
    cf = opts.framework.strip()
    if not confparser.has_section(cf):
        logger.error( 'Missing framework %s in configuration file' % cf )
        raise OmniError, 'Missing framework %s in configuration file' % cf
    
    # Copy the control framework into a dictionary
    config['selected_framework'] = {}
    for (key,val) in confparser.items(cf):
        config['selected_framework'][key] = val
    
    return config

def load_framework(config, opts):
    """Select the Control Framework to use from the config, and instantiate the proper class."""

    cf_type = config['selected_framework']['type']
    config['logger'].debug('Using framework type %s', cf_type)

    framework_mod = __import__('omnilib.frameworks.framework_%s' % cf_type, fromlist=['omnilib.frameworks'])
    config['selected_framework']['logger'] = config['logger']
    framework = framework_mod.Framework(config['selected_framework'], opts)
    return framework    

def initialize(argv, options=None ):
    """Parse argv (list) into the given optional optparse.Values object options.
    (Supplying an existing options object allows pre-setting certain values not in argv.)
    Then configure logging per those options.
    Then load the omni_config file
    Then initialize the control framework.
    Return the framework, config, args list, and optparse.Values struct."""

    opts, args = parse_args(argv, options)
    logger = configure_logging(opts)
    config = load_config(opts, logger)
    framework = load_framework(config, opts)
    logger.debug('User Cert File: %s', framework.cert)
    return framework, config, args, opts

def call(argv, options=None, verbose=False):
    """Method to use when calling omni as a library

    argv is a list ala sys.argv
    options is an optional optparse.Values structure like you get from parser.parse_args
      Use this to pre-set certain values, or allow your caller to get omni options from its commandline

    Can call functions like this:
     User does:    myscript.py -f my_sfa --myScriptPrivateOption doNonNativeList slicename

     Your myscript.py code does:
      import sys
      import omni

      ################################################################################
      # Requires that you have omni installed or the path to gcf/src in your
      # PYTHONPATH.
      #
      # For example put the following in your bashrc:
      #     export PYTHONPATH=${PYTHONPATH}:path/to/gcf/src
      #
      ################################################################################

      def main(argv=None):
        ##############################################################################
        # Get a parser from omni that understands omni options
        ##############################################################################
        parser = omni.getParser()
        # update usage for help message
        omni_usage = parser.get_usage()
        parser.set_usage(omni_usage+"\nmyscript.py supports additional commands.\n\n\tCommands and their arguments are:\n\t\t\tdoNonNativeList [optional: slicename]")

        ##############################################################################
        # Add additional optparse.OptionParser style options for your
        # script as needed.
        # Be sure not to re-use options already in use by omni for
        # different meanings, otherwise you'll raise an OptionConflictError
        ##############################################################################
        parser.add_option("--myScriptPrivateOption",
                          help="A non-omni option added by %s"%sys.argv[0],
                          action="store_true", default=False)
        # options is an optparse.Values object, and args is a list
        options, args = parser.parse_args(sys.argv[1:])
        if options.myScriptPrivateOption:
          # do something special for your private script's options
          print "Got myScriptOption"



        ##############################################################################
        # figure out that doNonNativeList means to do listresources with the
        # --omnispec argument and parse out slicename arg
        ##############################################################################
        omniargs = []
        if args and len(args)>0:
          if args[0] == "doNonNativeList":
            print "Doing omnispec listing"
            omniargs.append("--omnispec")
            omniargs.append("listresources")
            if len(args)>1:
              print "Got slice name %s" % args[1]
              slicename=args[1]
              omniargs.append(slicename)
          else:
            omniargs = args
        else:
          print "Got no command. Run '%s -h' for more information."%sys.argv[0]
          return

        ##############################################################################
        # And now call omni, and omni sees your parsed options and arguments
        ##############################################################################
        text, retItem = omni.call(omniargs, options)

        # Give the text back to the user
        print text

        # Process the dictionary returned in some way
        if type(retItem) == type({}):
          numItems = len(retItem.keys())
        elif type(retItem) == type([]):
          numItems = len(retItem)
        if numItems:
          print "\nThere were %d items returned." % numItems

      if __name__ == "__main__":
          sys.exit(main())

    This is equivalent to: ./omni.py --omnispec listresources <slicename>

    Verbose option allows printing the command and summary, or suppressing it.
    Callers can control omni logs (suppressing console printing for example) using python logging.
    """

    if options is not None and not options.__class__==optparse.Values:
        raise OmniError("Invalid options argument to call: must be an optparse.Values object")

    if argv is None or not type(argv) == list:
        raise OmniError("Invalid argv argument to call: must be a list")

    framework, config, args, opts = initialize(argv, options)
    # process the user's call
    return API_call( framework, config, args, opts, verbose=verbose )

def API_call( framework, config, args, opts, verbose=False ):
    """Call the function from the given args list. 
    Apply the options from the given optparse.Values opts argument
    If verbose, print the command and the summary.
    Return the summary and the result object.
    """

    logger = config['logger']

    if opts.debug:
        logger.info(getSystemInfo() + "\nOmni: " + getOmniVersion())

    # Process the user's call
    handler = CallHandler(framework, config, opts)    
#    Returns string, item
    result = handler._handle(args)
    if result is None:
        retVal = None
        retItem = None
    elif len(result)==2:
        retVal, retItem = result
    else:
        retVal = result
        retItem = None

    # Print the summary of the command result
    if verbose:
        #sys.argv when called as a library is
        # uninteresting/misleading. So args is better, but this misses
        # the options.
        # We print here all non-default options
        parser = getParser()
        nondef = ""
        for attr in dir(opts):
            import types
            if attr.startswith("_"):
                continue
            if isinstance(getattr(opts, attr), types.MethodType):
                continue
            # if the parser has no option with a dest==attr,
            # then continue
            # This means that the user supplied an option the parser didn't
            # handle, and typically there would have been an error,
            # but lets not complain here
            has = False
            for opt in parser.option_list:
                if opt.dest == attr:
                    has=True
            if has == False:
                continue
            if (not parser.defaults.has_key(attr)) or (parser.defaults[attr] != getattr(opts, attr)):
                # non-default value
                nondef += "\n\t\t" + attr + ": " + str(getattr(opts, attr))

        if nondef != "":
            nondef = "\n  Options as run:" + nondef + "\n\n  "

        cmd = None
        if len(args) > 0:
            cmd = args[0]
        s = "Completed " + cmd + ":\n" + nondef + "Args: "+" ".join(args)+"\n\n  Result Summary: " + retVal
        headerLen = (70 - (len(s) + 2)) / 4
        header = "- "*headerLen+" "+s+" "+"- "*headerLen

        logger.info( " " + "-"*60 )
        logger.info( header )
        # printed not logged so can redirect output to a file
        #logger.info(retVal)
#        logger.info( " " + "="*60 )
#        print retItem
        logger.info( " " + "="*60 )
    
    return retVal, retItem

def configure_logging(opts):
    """Configure logging. If a log config filename is supplied with the -l option,
    and the file is non-empty, configure logging from that file. For details on this,
    see the applyLogConfig documentation.

    Otherwise, use a basic config, with INFO level by default,
    DEBUG level if opts.debug.

    Return a logger for 'omni'."""

    level = logging.INFO
    optlevel = 'INFO'
    if opts.debug:
        level = logging.DEBUG
        optlevel = 'DEBUG'
    if opts.logconfig:
        applyLogConfig(opts.logconfig, defaults={'optlevel': optlevel})
    else:
        logging.basicConfig(level=level)

    logger = logging.getLogger("omni")
    return logger

def applyLogConfig(logConfigFilename, defaults={'optlevel': 'INFO'}):
    """Change the logging configuration to that in the specified file, if found.
    Effects all uses of python logging in this process.

    Existing loggers are not modified, unless they are explicitly named
    in the logging config file (they or their ancestor, not 'root').

    Tries hard to find the file, and does nothing if not found.

    'defaults' is a dictionary in ConfigParser format, that sets variables
    for use in the config files. Specifically,
    use this to set 'optlevel' to the basic logging level desired: INFO is the default.

    For help creating a logging config file,
    see http://docs.python.org/library/logging.config.html#configuration-file-format
    and see the sample 'omni_log_conf_sample.conf'

    From a script, you can over-ride the -l argument to change the log level.
    Alternatively, you can call this function during omni operations.
    Sample usage from a script:
      # Configure logging based on command line options, using any -l specified file
      framework, config, args, opts = omni.initialize(omniargs, options)
      text, retItem = omni.API_call( framework, config, args, opts )

      # Without changing commandline args, reset the logging config
      omni.applyLogConfig("examples/myLogConfig.conf")

      # <Here your script resets 'args' to give a different command>

      # Then make the call for the new command, using the new log level
      text, retItem = omni.API_call( framework, config, args, opts )
"""

    fns = [logConfigFilename, os.path.join('src', logConfigFilename), os.path.expanduser(logConfigFilename), os.path.join('.', logConfigFilename), os.path.abspath(logConfigFilename)]
    found = False
    for fn in fns:
        if os.path.exists(fn) and os.path.getsize(fn) > 0:
            # Only new loggers get the parameters in the config file.
            # If disable_existing is True(default), then existing loggers are disabled,
            # unless they (or ancestors, not 'root') are explicitly listed in the config file.
            logging.config.fileConfig(fn, defaults=defaults, disable_existing_loggers=False)
            logging.info("Configured logging from file %s", fn)
            found = True
            break

    if not found:
        logging.warn("Failed to find log config file %s", logConfigFilename)

def getSystemInfo():
    import platform
    pver = platform.python_implementation() + " " + platform.python_version()
    osinfo = platform.platform()
    return "Python: " + pver + "\nOS: " + osinfo

def getOmniVersion():
    version ="GENI Omni Command Line Aggregate Manager Tool Version %s" % OMNI_VERSION
    version +="\nCopyright (c) 2011 Raytheon BBN Technologies"
    return version

def getParser():
    """Construct an Options Parser for parsing omni arguments.
    Do not actually parse anything"""

    usage = "\n" + getOmniVersion() + "\n\n%prog [options] <command and arguments> \n\
\n \t Commands and their arguments are: \n\
 \t\tAM API functions: \n\
 \t\t\t getversion \n\
 \t\t\t listresources [optional: slicename] \n\
 \t\t\t createsliver <slicename> <rspec file> \n\
 \t\t\t sliverstatus <slicename> \n\
 \t\t\t renewsliver <slicename> <new expiration time in UTC> \n\
 \t\t\t deletesliver <slicename> \n\
 \t\t\t shutdown <slicename> \n\
 \t\tClearinghouse / Slice Authority functions: \n\
 \t\t\t listaggregates \n\
 \t\t\t createslice <slicename> \n\
 \t\t\t getslicecred <slicename> \n\
 \t\t\t renewslice <slicename> <new expiration time in UTC> \n\
 \t\t\t deleteslice <slicename> \n\
 \t\t\t listmyslices <username> \n\
 \t\t\t getusercred \n\
 \t\t\t print_slice_expiration <slicename> \n\
\n\t See README-omni.txt for details.\n\
\t And see the Omni website at http://trac.gpolab.bbn.com/gcf"

    parser = optparse.OptionParser(usage=usage, version="%prog: " + getOmniVersion())
    parser.add_option("-c", "--configfile",
                      help="Config file name", metavar="FILE")
    parser.add_option("-f", "--framework", default="",
                      help="Control framework to use for creation/deletion of slices")
    parser.add_option("-n", "--native", default=False, action="store_true",
                      help="Use native RSpecs (default)")
    parser.add_option("--omnispec", default=False, action="store_true",
                      help="Use Omnispecs (deprecated)")
    parser.add_option("-a", "--aggregate", metavar="AGGREGATE_URL",
                      help="Communicate with a specific aggregate")
    parser.add_option("--debug", action="store_true", default=False,
                       help="Enable debugging output")
    parser.add_option("--no-ssl", dest="ssl", action="store_false",
                      default=True, help="do not use ssl")
    parser.add_option("--orca-slice-id",
                      help="Use the given Orca slice id")
    parser.add_option("-o", "--output",  default=False, action="store_true",
                      help="Write output of getversion, listresources, createsliver, sliverstatus, getslicecred to a file (Omni picks the name)")
    parser.add_option("-p", "--prefix", default=None, metavar="FILENAME_PREFIX",
                      help="Filename prefix when saving results (used with -o)")
    parser.add_option("--usercredfile", default=None, metavar="USER_CRED_FILENAME",
                      help="Name of user credential file to read from if it exists, or save to when running like '--usercredfile myUserCred.xml -o getusercred'")
    parser.add_option("--slicecredfile", default=None, metavar="SLICE_CRED_FILENAME",
                      help="Name of slice credential file to read from if it exists, or save to when running like '--slicecredfile mySliceCred.xml -o getslicecred mySliceName'")
    # Note that type and version are case in-sensitive strings.
    parser.add_option("-t", "--rspectype", nargs=2, default=None, metavar="AD-RSPEC-TYPE AD-RSPEC-VERSION",
                      help="Ad RSpec type and version to return, e.g. 'GENI 3'")
    parser.add_option("-v", "--verbose", default=True, action="store_true",
                      help="Turn on verbose command summary for omni commandline tool")
    parser.add_option("-q", "--quiet", default=True, action="store_false", dest="verbose",
                      help="Turn off verbose command summary for omni commandline tool")
    parser.add_option("--tostdout", default=False, action="store_true",
                      help="Print results like rspecs to STDOUT instead of to log stream")
    parser.add_option("--abac", default=False, action="store_true",
                      help="Use ABAC authorization")
    parser.add_option("-l", "--logconfig", default=None,
                      help="Python logging config file")
    parser.add_option("--no-tz", default=False, action="store_true",
                      help="Do not send timezone on RenewSliver")
    parser.add_option("-V", "--api-version", type="int", default=1,
                      help="Specify version of AM API to use (1, 2, etc.)")
    parser.add_option("--no-compress", dest='geni_compressed', 
                      default=True, action="store_false",
                      help="Do not compress returned values")
    parser.add_option("--available", dest='geni_available',
                      default=False, action="store_true",
                      help="Only return available resources")
    return parser

def parse_args(argv, options=None):
    """Parse the given argv list using the Omni optparse.OptionParser.
    Fill options into the given option optparse.Values object
    """
    if options is not None and not options.__class__==optparse.Values:
        raise OmniError("Invalid options argument to parse_args: must be an optparse.Values object")
    elif options is not None:
        # The caller, presumably a script, gave us an optparse.Values storage object.
        # Passing this object to parser.parse_args replaces the storage - it is pass
        # by reference. Callers may not expect that. In particular, multiple calls in
        # separate threads will conflict.
        # Make a deep copy
        options = deepcopy(options)

    parser = getParser()
    if argv is None:
        # prints to stderr
        parser.print_help()
        return

    (options, args) = parser.parse_args(argv, options)

    # Validate options here if we want to be careful that options are of the right types...
    # particularly if the user passed in an options argument

    if options.native and options.omnispec:
        #does sys.exit - should we catch this and raise OmniError instead?
        parser.error("Select either native (-n) OR OmniSpecs (--omnispec) RSpecs")
    elif not options.native and not options.omnispec:
        options.native = True

    return options, args

def main(argv=None):
    # do initial setup & process the user's call
    if argv is None:
        argv = sys.argv[1:]
    try:
        framework, config, args, opts = initialize(argv)
        API_call(framework, config, args, opts, verbose=opts.verbose)
    except OmniError:
        sys.exit()

        
if __name__ == "__main__":
    sys.exit(main())
