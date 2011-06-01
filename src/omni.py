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
from copy import copy
import datetime
import dateutil.parser
import json
import logging
import optparse
import os
import pprint
import ssl
import string
import sys
import traceback
import xml.dom.minidom as md
import xmlrpclib
import zlib

from omnilib.omnispec.translation import rspec_to_omnispec, omnispec_to_rspec
from omnilib.omnispec.omnispec import OmniSpec
from omnilib.util import OmniError
from omnilib.util.faultPrinting import cln_xmlrpclib_fault
from omnilib.util.dossl import _do_ssl
import omnilib.util.credparsing as credutils
import omnilib.xmlrpc.client

#import sfa.trust.gid as gid

OMNI_CONFIG_TEMPLATE='/etc/omni/templates/omni_config'

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
        - Single URL given in -a argument, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse

        -o Save result (JSON format) in per-Aggregate files
        -p (used with -o) Prefix for resulting version information files
        If not saving results to a file, they are logged.
        If --tostdout option, then instead of logging, print to STDOUT.

        """
        retVal = ""
        version = {}
        clients = self._getclients()
        successCnt = 0

        for client in clients:
            thisVersion = _do_ssl(self.framework, None, "GetVersion at %s" % (str(client.url)), client.GetVersion)
            version[ client.url ] = thisVersion
            if thisVersion is None:
                self.logger.warn( "URN: %s (url:%s) call failed.\n" % (client.urn, client.url) )
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
        if len(clients)==0:
            retVal += "No aggregates to query.\n\n"
        else:
            # FIXME: If it is 1 just return the getversion?
            retVal += "Got version for %d out of %d aggregates\n" % (successCnt,len(clients))

        return (retVal, version)

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
        """

        # rspecs[(urn, url)] = decompressed native rspec
        rspecs = {}
        options = {}

        options['geni_compressed'] = False;
        
        # An optional slice name might be specified.
        slicename = None
        if len(args) > 0:
            slicename = args[0].strip()

        # Get the credential for this query
        if slicename is None or slicename == "":
            slicename = None
            cred = None
            cred = _do_ssl(self.framework, None, "Get User Credential from control framework", self.framework.get_user_cred)

            if cred is None:
                self.logger.error('Cannot list resources: Could not get user credential')
                return None
        else:
            urn = self.framework.slice_name_to_urn(slicename)
            cred = self._get_slice_cred(urn)
            if cred is None:
                self.logger.error('Cannot list resources for slice %s: could not get slice credential' % (urn))
                return None
            self.logger.info('Gathering resources reserved for slice %s..' % slicename)

            options['geni_slice_urn'] = urn

        # We now have a credential

        # Query each aggregate for resources
        successCnt = 0
        clientList = self._getclients()
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
                # call getversion
                thisVersion = _do_ssl(self.framework, None, "GetVersion at %s" % (str(client.url)), client.GetVersion)
                if thisVersion is None:
                    self.logger.warning("Couldnt do GetVersion so won't do ListResources at %s [%s]", client.urn, client.url)
                    continue
                elif not thisVersion.has_key('ad_rspec_versions'):
                    self.logger.warning("AM getversion has no ad_rspec_versions key for AM %s [%s]", client.urn, client.url)
                    continue

                # get the ad_rspec_versions key
                ad_rspec_version = thisVersion['ad_rspec_versions']
                self.logger.debug("Got %d supported ad_rspec_versions", len(ad_rspec_version))
                # foreach item in the list that is the val
                match = False
                for availversion in ad_rspec_version:
                    if not availversion.has_key('type') and availversion.has_key('version'):
                        self.logger.warning("AM getversion ad_rspec_version entry malformed: no type or version")
                        continue
                    # Tony&Jonathon agreed that types are case sensitive. Still, that's ugly
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
                    continue
                # else
                options['rspec_version'] = dict(type=rtype, version=rver)

            # FIXME: Need to specify what rspec_version we want
            # For PG non native mode that should be
#            options['rspec_version'] = dict(type="ProtoGENI", version=0.1)

            self.logger.debug("Doing listresources with options %r", options)
            rspec = _do_ssl(self.framework, None, ("List Resources at %s" % (client.url)), client.ListResources, [cred], options)

            if not rspec is None:
                successCnt += 1
                if options.get('geni_compressed', False):
                    rspec = zlib.decompress(rspec.decode('base64'))
                rspecs[(client.urn, client.url)] = rspec

        self.logger.info( "Listed resources on %d out of %d possible aggregates." % (successCnt, len(clientList)))
        return rspecs

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
        on all aggregates and prints the omnispec/rspec to stdout or to file.
        
        -n gives native format; otherwise print omnispec in json format
           Note: omnispecs are deprecated. Native format is preferred.
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
        EG: myprefix-myslice-rspec-localhost-8001.xml

        If a slice name is supplied, then resources for that slice only 
        will be displayed.  In this case, the slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        Aggregates queried:
        - Single URL given in -a argument, if provided, ELSE
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
        rspecs = self._listresources( args )
        numAggs = 0
        if rspecs is not None:
            numAggs = len(rspecs.keys())
        
        # handle empty case
        if not rspecs or rspecs == {}:
            if slicename:
                prtStr = "Got no resources on slice %s"%slicename 
            else:
                prtStr = "Got no resources" 
            self.logger.info( prtStr )
            return prtStr, None

 
        # Loop over RSpecs
        # Native mode: print them
        # Omnispec mode: convert them to omnispecs
        returnedRspecs = {}
        omnispecs = {}
        fileCtr = 0
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

            else:
                # Convert RSpec to omnispec
                # Throws exception if unparsable
                try:
                    omnispecs[ url ] = rspec_to_omnispec(urn,rspec)
                    returnedRspecs[(urn,url)] = omnispecs[url]
                except Exception, e:
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
                    server = self._filename_part_from_am_url(self.opts.aggregate)
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
        Note that PLC Web UI lists slices as <site name>_<slice name> (EG bbn_myslice), and we want
        only the slice name part here.

        -n Use native format rspec. Requires -a. Native RSpecs are preferred, and omnispecs are deprecated.
        -a Contact only the aggregate at the given URL
        --slicecredfile Read slice credential from given file, if it exists
        -o Save result (manifest rspec) in per-Aggregate files
        -p (used with -o) Prefix for resulting manifest RSpec files
        If not saving results to a file, they are logged.
        If --tostdout option, then instead of logging, print to STDOUT.

        Slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        omni_config users section is used to get a set of SSH keys that should be loaded onto the
        remote node to allow SSH login, if the remote resource and aggregate support this

        Note you likely want to check SliverStatus to ensure your resource comes up.
        And check the sliver expiration time: you may want to call RenewSliver
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
        slice_cred = self._get_slice_cred(urn)
        if slice_cred is None:
            self._raise_omni_error('Cannot create sliver %s: Could not get slice credential'
                     % (urn))
        elif not slice_cred.startswith("<"):
            #elif slice_cred is not XML that looks like a credential, assume
            # assume it's an error message, and raise an omni_error
            self._raise_omni_error("Cannot create sliver %s: not a slice credential: %s" % (urn, slice_cred))

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
                rspecs[self.opts.aggregate] = rspec
            except Exception, exc:
                self._raise_omni_error('Unable to read rspec file %s: %s'
                         % (specfile, str(exc)))
        else:
            rspecs = self._ospec_to_rspecs(specfile)

        result = None
        # Copy the user config and read the keys from the files into the structure
        slice_users = copy(self.config['users'])

        #slice_users = copy(self.omni_config['slice_users'])
        for user in slice_users:
            newkeys = []
            required = ['urn', 'keys']
            for req in required:
                if not req in user:
                    raise Exception("%s in omni_config is not specified for user %s" % (req,user))

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
        aggregate_urls = self._listaggregates().values()
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
            result = _do_ssl(self.framework, None, ("Create Sliver %s at %s" % (urn, url)), client.CreateSliver, urn, [slice_cred], rspec, slice_users)
            prettyresult = result

            if result != None and isinstance(result, str) and \
                    (result.lower().startswith('<rspec') or
                     result.lower().startswith('<resv_rspec') or
                     result.lower().startswith('<?xml ')):
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

            # FIXME: When Tony revises the rspec, fix this test
            if '<RSpec' in rspec and 'type="SFA"' in rspec:
                # Figure out the login name
                # We could of course do this for the user.
                self.logger.info("Please run the omni sliverstatus call on your slice to determine your login name to PL resources")

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
        """AM API RenewSliver <slicename> <new expiration time in UTC>
        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name> (EG bbn_myslice), and we want
        only the slice name part here.

        Slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        Aggregates queried:
        - Single URL given in -a argument, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse

        Note that the expiration time cannot be past your slice expiration time (see renewslice). Some aggregates will
        not allow you to _shorten_ your sliver expiration time.
        """
        if len(args) < 2 or args[0] == None or args[0].strip() == "":
            self._raise_omni_error('renewsliver requires arg of slice name and new expiration time in UTC')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        slice_cred = self._get_slice_cred(urn)
        if slice_cred is None:
            self._raise_omni_error('Cannot renew sliver %s: Could not get slice credential'
                     % (urn))

        time = None
        try:
            time = dateutil.parser.parse(args[1])
        except Exception, exc:
            self._raise_omni_error('renewsliver couldnt parse new expiration time from %s: %r' % (args[1], exc))

        retVal = ''

        # Compare requested time with slice expiration time
        slicecred_exp = credutils.get_cred_exp(self.logger, slice_cred)
        retVal += self._print_slice_expiration(urn, slice_cred) +"\n"
        if time > slicecred_exp:
            self._raise_omni_error('Cannot renew sliver %s until %s UTC because it is after the slice expiration time %s UTC' % (urn, time, slicecred_exp))
        elif time <= datetime.datetime.utcnow():
            self.logger.info('Sliver %s will be set to expire now' % urn)
            time = datetime.datetime.utcnow()
        else:
            self.logger.debug('Slice expires at %s UTC after requested time %s UTC' % (slicecred_exp, time))

        self.logger.info('Renewing Sliver %s until %s UTC' % (urn, time))

        if self.opts.orca_slice_id:
            self.logger.info('Using ORCA slice id %r', self.opts.orca_slice_id)
            urn = self.opts.orca_slice_id

        successCnt = 0
        successList = []
        failList = []
        clientList = self._getclients()
        for client in clientList:
            # Note that the time arg includes UTC offset as needed
            res = _do_ssl(self.framework, None, ("Renew Sliver %s on %s" % (urn, client.url)), client.RenewSliver, urn, [slice_cred], time.isoformat())
            if not res:
                prStr = "Failed to renew sliver %s on %s (%s)" % (urn, client.urn, client.url)
                if len(clientList) == 1:
                    retVal += prStr + "\n"
                self.logger.warn(prStr)
                failList.append( client.url )
            else:
                prStr = "Renewed sliver %s at %s (%s) until %s UTC" % (urn, client.urn, client.url, time.isoformat())
                self.logger.info(prStr)
                if len(clientList) == 1:
                    retVal += prStr + "\n"
                successCnt += 1
                successList.append( client.url )
        if len(clientList) == 0:
            retVal += "No aggregates on which to renew slivers for slice %s\n" % urn
        elif len(clientList) > 1:
            retVal += "Renewed slivers on %d out of %d aggregates for slice %s until %s UTC\n" % (successCnt, len(clientList), urn, time)
        return retVal, (successList, failList)

    def sliverstatus(self, args):
        """AM API SliverStatus  <slice name>
        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name> (EG bbn_myslice), and we want
        only the slice name part here.

        Slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        Aggregates queried:
        - Single URL given in -a argument, if provided, ELSE
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
        slice_cred = self._get_slice_cred(urn)
        if slice_cred is None:
            self._raise_omni_error('Cannot get sliver status for %s: Could not get slice credential'
                     % (urn))

        retVal = self._print_slice_expiration(urn, slice_cred) + "\n"

        if self.opts.orca_slice_id:
            self.logger.info('Using ORCA slice id %r', self.opts.orca_slice_id)
            urn = self.opts.orca_slice_id

        successCnt = 0
        retItem = {}
        # Query status at each client
        clientList = self._getclients()
        if len(clientList) > 0:
            self.logger.info('Status of Slice %s:' % urn)
        else:
            self.logger.warn("No aggregates available")
        for client in clientList:
            status = _do_ssl(self.framework, None, "Sliver status of %s at %s" % (urn, client.url), client.SliverStatus, urn, [slice_cred])
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
                retItem[ client.url ] = status
                successCnt+=1
            else:
                retItem[ client.url ] = False
        # FIXME: Return the status if there was only 1 client?
        retVal += "Returned status of slivers on %d of %d possible aggregates." % (successCnt, len(clientList))
        return retVal, retItem
                
    def deletesliver(self, args):
        """AM API DeleteSliver <slicename>
        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name> (EG bbn_myslice), and we want
        only the slice name part here.

        Slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        Aggregates queried:
        - Single URL given in -a argument, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse
        """
        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            self._raise_omni_error('deletesliver requires arg of slice name')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        slice_cred = self._get_slice_cred(urn)
        if slice_cred is None:
            self._raise_omni_error('Cannot delete sliver %s: Could not get slice credential'
                     % (urn))

        if self.opts.orca_slice_id:
            self.logger.info('Using ORCA slice id %r', self.opts.orca_slice_id)
            urn = self.opts.orca_slice_id

        retVal = ""
        successList = []
        failList = []
        successCnt = 0
        clientList = self._getclients()

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
            if _do_ssl(self.framework, None, ("Delete Sliver %s on %s" % (urn, client.url)), client.DeleteSliver, urn, [slice_cred]):
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
                self.logger.warn(prStr)
                if len(clientList) == 1:
                    retVal = prStr
                failList.append( client.url )
        if len(clientList) == 0:
            retVal = "No aggregates specified on which to delete slivers"
        elif len(clientList) > 1:
            retVal = "Deleted slivers on %d out of a possible %d aggregates" % (successCnt, len(clientList))
        return retVal, (successList, failList)

    def shutdown(self, args):
        """AM API Shutdown <slicename>
        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name> (EG bbn_myslice), and we want
        only the slice name part here.

        Slice credential is usually retrieved from the Slice Authority. But
        with the --slicecredfile option it is read from that file, if it exists.

        Aggregates queried:
        - Single URL given in -a argument, if provided, ELSE
        - List of URLs given in omni_config aggregates option, if provided, ELSE
        - List of URNs and URLs provided by the selected clearinghouse
        """
        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            self._raise_omni_error('shutdown requires arg of slice name')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        slice_cred = self._get_slice_cred(urn)
        if slice_cred is None:
            self._raise_omni_error('Cannot shutdown slice %s: Could not get slice credential'
                     % (urn))
        if self.opts.orca_slice_id:
            self.logger.info('Using ORCA slice id %r', self.opts.orca_slice_id)
            urn = self.opts.orca_slice_id

        #Call shutdown on each AM
        retVal = ""
        successCnt = 0
        successList = []
        failList = []
        clientList = self._getclients()
        for client in clientList:
            if _do_ssl(self.framework, None, "Shutdown %s on %s" %
                       (urn, client.url), client.Shutdown, urn, [slice_cred]):
                prStr = "Shutdown Sliver %s on AM %s at %s" % (urn, client.urn, client.url)
                self.logger.info(prStr)
                if len(clientList) == 1:
                    retVal = prStr
                successCnt+=1
                successList.append( client.url )
            else:
                prStr = "Failed to shutdown sliver %s on AM %s at %s" % (urn, client.urn, client.url) 
                self.logger.warn(prStr)
                if len(clientList) == 1:
                    retVal = prStr
                failList.append( client.url )
        if len(clientList) == 0:
            retVal = "No aggregates specified on which to shutdown slice %s" % urn
        elif len(clientList) > 1:
            retVal = "Shutdown slivers of slice %s on %d of %d possible aggregates" % (urn, successCnt, len(clientList))
        return retVal, (successList, failList)

    # End of AM API operations
    #########################################
    # Start of control framework operations

    def listaggregates(self, args):
        """Print the known aggregates URN and URL
        Gets aggregates from:
        - command line (one, no URN available), OR
        - omni config (1+, no URNs available), OR
        - Specified control framework (via remote query). This is the aggregates that registered with the framework.
        """
        retStr = ""
        retVal = {}
        aggList = self._listaggregates().items()
        self.logger.info("Listing %d aggregates..."%len(aggList))
        aggCnt = 0
        for (urn, url) in aggList:
            aggCnt += 1
            self.logger.info( "  Aggregate %d:\n \t%s \n \t%s" % (aggCnt, urn, url) )
#            retStr += "%s: %s\n" % (urn, url)
            retVal[urn] = url
        if len(aggList)==0:
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
        Note that PLC Web UI lists slices as <site name>_<slice name> (EG bbn_myslice), and we want
        only the slice name part here.

        To create the slice and save off the slice credential:
     	   omni.py -o createslice myslice
        To create the slice and save off the slice credential to a specific file:
     	   omni.py -o --slicecredfile mySpecificfile-myslice-credfile.xml createslice myslice

        Note that Slice Authorities typically limit this call to privileged users. EG PIs.

        Note also that typical slice lifetimes are short. See RenewSlice.
        """
        retVal = ""
        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            self._raise_omni_error('createslice requires arg of slice name')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        
        slice_cred = _do_ssl(self.framework, None, "Create Slice %s" % urn, self.framework.create_slice, urn)
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
        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name> (EG bbn_myslice), and we want
        only the slice name part here.

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
        out_expiration = _do_ssl(self.framework, None, "Renew Slice %s" % urn, self.framework.renew_slice, urn, in_expiration)

        if out_expiration:
            prtStr = "Slice %s now expires at %s UTC" % (name, out_expiration)
            self.logger.info( prtStr )
            retVal = prtStr+"\n"
            retTime = out_expiration
        else:
            prtStr = "Failed to renew slice %s" % (name)
            self.logger.warn( prtStr )
            retVal = prtStr+"\n"
            retTime = None
        retVal +=self._print_slice_expiration(urn)
        return retVal, retTime

    def deleteslice(self, args):
        """Framework specific DeleteSlice call at the given Slice Authority
        Arg: slice name
        Slice name could be a full URN, but is usually just the slice name portion.
        Note that PLC Web UI lists slices as <site name>_<slice name> (EG bbn_myslice), and we want
        only the slice name part here.

        Delete all your slivers first! This does not free up resources at various aggregates.
        """
        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            self._raise_omni_error('deleteslice requires arg of slice name')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)

        res = _do_ssl(self.framework, None, "Delete Slice %s" % urn, self.framework.delete_slice, urn)
        # return True if successfully deleted slice, else False
        if (res is None) or (res is False):
            retVal = False
        else:
            retVal = True
        prtStr = "Delete Slice %s result: %r" % (name, res)
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
        slices=None
        slices = _do_ssl(self.framework, None, "List Slices from Slice Authority", self.framework.list_my_slices, username)
        if slices is None:
            # only end up here if call to _do_ssl failed
            slices = []
            self.logger.error("Failed to list slices for user '%s'"%(username))
            retStr += "Server error: "
        elif len(slices) > 0:
            self.logger.info("User '%s' has slices: \n\t%s"%(username,"\n\t".join(slices)))
        else:
            self.logger.info("User '%s' has NO slices."%username)

        # summary
        retStr += "Found %d slices for user '%s'.\n"%(len(slices), username)

        return retStr, slices

    def getslicecred(self, args):
        """Get the AM API compliant slice credential (signed XML document).

        If you specify the -o option, the credential is saved to a file.
        The filename is <slicename>-cred.xml
        But if you specify the --slicecredfile option then that is the filename used.

        Additionally, if you specify the --slicecredfile option and that references a file that is
        not empty, then we do not query the Slice Authority for this credential, but instead
        read it from this file.

        EG:
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
        Note that PLC Web UI lists slices as <site name>_<slice name> (EG bbn_myslice), and we want
        only the slice name part here.
        """

        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            # could print help here but that's verbose
            #parse_args(None)
            self._raise_omni_error('getslicecred requires arg of slice name')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        cred = self._get_slice_cred(urn)

        if cred is None:
            retVal = "No slice credential returned for slice %s"%urn
            return retVal, None

        # Log if the slice expires soon
        strWithSliceExp = self._print_slice_expiration(urn, cred)

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
        Note that PLC Web UI lists slices as <site name>_<slice name> (EG bbn_myslice), and we want
        only the slice name part here.
        """

        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            # could print help here but that's verbose
            #parse_args(None)
            self._raise_omni_error('print_slice_expiration requires arg of slice name')

        name = args[0]

        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)
        cred = self._get_slice_cred(urn)

        retVal = None
        if cred is None:
            retVal = "No slice credential returned for slice %s"%urn
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
            sliceCred = self._get_slice_cred(urn)
        if sliceCred is None:
            # failed to get a slice string. Can't check
            return ""

        sliceexp = credutils.get_cred_exp(self.logger, sliceCred)
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
        Retry on wrong pass phrase."""

        if self.opts.slicecredfile and os.path.exists(self.opts.slicecredfile) and os.path.isfile(self.opts.slicecredfile) and os.path.getsize(self.opts.slicecredfile) > 0:
            # read the slice cred from the given file
            self.logger.info("Getting slice %s credential from file %s", urn, self.opts.slicecredfile)
            cred = None
            with open(self.opts.slicecredfile, 'r') as f:
                cred = f.read()
            return cred

        return _do_ssl(self.framework, None, "Get Slice Cred for slice %s" % urn, self.framework.get_slice_cred, urn)

    def _getclients(self, ams=None):
        """Create XML-RPC clients for each aggregate (from commandline, else from config file, else from framework)
        Return them as a sequence.
        Each client has a urn and url. See _listaggregates for details.
        """
        clients = []
        for (urn, url) in self._listaggregates().items():
            client = make_client(url, self.framework, self.opts)
            client.urn = urn
            client.url = url
            clients.append(client)
        if clients == []:
            self.logger.warn( 'No aggregates found' )
        return clients

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
            # No URN is specified, so put in 'unspecified_AM_URN'
            return dict(unspecified_AM_URN=self.opts.aggregate.strip())
        elif not self.omni_config.get('aggregates', '').strip() == '':
            aggs = {}
            for url in self.omni_config['aggregates'].strip().split(','):
                url = url.strip()
                if url != '':
                    aggs[url] = url
            return aggs
        else:
            aggs =  _do_ssl(self.framework, None, "List Aggregates from control framework", self.framework.list_aggregates)
            if aggs is  None:
                return {}
            return aggs

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


def make_client(url, framework, opts):
    """ Create an xmlrpc client, skipping the client cert if not opts.ssl"""
    if opts.ssl:
        return omnilib.xmlrpc.client.make_client(url, framework.ssl_context())
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
                     An example config file can be found in the source tarball or in /etc/omni/templates/"""
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

def load_framework(config):
    """Select the Control Framework to use from the config, and instantiate the proper class."""

    cf_type = config['selected_framework']['type']

    framework_mod = __import__('omnilib.frameworks.framework_%s' % cf_type, fromlist=['omnilib.frameworks'])
    config['selected_framework']['logger'] = config['logger']
    framework = framework_mod.Framework(config['selected_framework'])
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
    framework = load_framework(config)
    return framework, config, args, opts

def call(argv, options=None, verbose=False):
    """Method to use when calling omni as a library

    argv is a list ala sys.argv
    options is an optional optparse.Values structure like you get from parser.parse_args
      Use this to pre-set certain values, or allow your caller to get omni options from its commandline

    Can call functions like this:
     User does:    myscript.py -f my_sfa --myScriptPrivateOption doNativeList slicename

     Your myscript.py code does:
      import omni
      # Get a parser from omni that understands omni options
      parser = omni.getParser()
      # Add additional optparse.OptionParser style options for your script as needed
      # Be sure not to re-use options already in use by omni for different meanings
      # otherwise you'll raise an OptionConflictError
      parser.add_option("--myScriptPrivateOption")
      # options is an optparse.Values object, and args is a list
      options, args = parser.parse_args(sys.argv[1:])
      if options.myScriptPrivateOption:
          # do something special for your private script's options
      # figure out doNativeList means to do listresources with the -n argument and parse out slicename arg
      omniargs = ["-n", 'listresources', slicename]
      # And now call omni, and omni sees your parsed options and arguments
      text, dict = omni.call(omniargs, options)
    This is equivalent to: ./omni.py -n listresources slicename.

    Verbose option allows printing the command and summary, or suppressing it.
    Callers can control omni logs (suppressing console printing for example) using python logging.
    """

    if options is not None and not options.__class__==optparse.Values:
        raise OmniError("Invalid options argument to call: must be an optparse.Values object")

    if argv is None or not type(argv) == list:
        raise OmniError("Invalid arv argument to call: must be a list")

    framework, config, args, opts = initialize(argv, options)
    # process the user's call
    return API_call( framework, config, args, opts, verbose=verbose )

def API_call( framework, config, args, opts, verbose=False ):
    """Call the function from the given args list. 
    Apply the options from the given optparse.Values opts argument
    If verbose, print the command and the summary.
    Return the summary and the result object.
    """
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

        logger = config['logger']
        logger.info( " " + "-"*60 )
        logger.info( header )
        # printed not logged so can redirect output to a file
        #logger.info(retVal)
#        logger.info( " " + "="*60 )
#        print retItem
        logger.info( " " + "="*60 )
    
    return retVal, retItem

def configure_logging(opts):
    """Configure logging. INFO level by defult, DEBUG level if opts.debug"""
    level = logging.INFO
    logging.basicConfig(level=level)
    if opts.debug:
        level = logging.DEBUG
    logger = logging.getLogger("omni")
    logger.setLevel(level)
    return logger

def getParser():
    """Construct an Options Parser for parsing omni arguments.
    Do not actually parse anything"""

    usage = "omni.py [options] <command and arguments> \n\
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
 \t\t\t getslicecred <slicename> \n\
 \t\t\t print_slice_expiration <slicename> \n\
\n\t See README-omni.txt for details."

    parser = optparse.OptionParser(usage)
    parser.add_option("-c", "--configfile",
                      help="Config file name", metavar="FILE")
    parser.add_option("-f", "--framework", default="",
                      help="Control framework to use for creation/deletion of slices")
    parser.add_option("-n", "--native", default=False, action="store_true",
                      help="Use native RSpecs (preferred)")
    parser.add_option("--omnispec", default=False, action="store_true",
                      help="Use OmniSpec RSpecs (default, will be deprecated soon)")
    parser.add_option("-a", "--aggregate", metavar="AGGREGATE_URL",
                      help="Communicate with a specific aggregate")
    parser.add_option("--debug", action="store_true", default=False,
                       help="Enable debugging output")
    parser.add_option("--no-ssl", dest="ssl", action="store_false",
                      default=True, help="do not use ssl")
    parser.add_option("--orca-slice-id",
                      help="Use the given Orca slice id")
    parser.add_option("-o", "--output",  default=False, action="store_true",
                      help="Write output of getversion, listresources, createsliver, sliverstatus, getslicecred to a file")
    parser.add_option("-p", "--prefix", default=None, metavar="FILENAME_PREFIX",
                      help="Filename prefix (used with -o)")
    parser.add_option("--slicecredfile", default=None, metavar="SLICE_CRED_FILENAME",
                      help="Name of slice credential file to read from if it exists, or save to with -o getslicecred")
    # Note that type and version are strings. Nominally case-sensitive.
    parser.add_option("-t", "--rspectype", nargs=2, default=None, metavar="AD-RSPEC-TYPE AD-RSPEC-VERSION",
                      help="Ad RSpec type and version to return, EG 'ProtoGENI 2'")
    parser.add_option("-v", "--verbose", default=True, action="store_true",
                      help="Turn on verbose command summary for omni commandline tool")
    parser.add_option("-q", "--quiet", default=True, action="store_false", dest="verbose",
                      help="Turn off verbose command summary for omni commandline tool")
    parser.add_option("--tostdout", default=False, action="store_true",
                      help="Print results like rspecs to STDOUT instead of to log stream")
    return parser

def parse_args(argv, options=None):
    """Parse the given argv list using the Omni optparse.OptionParser.
    Fill options into the given option optparse.Values object
    """
    if options is not None and not options.__class__==optparse.Values:
        raise OmniError("Invalid options argument to parse_args: must be an optparse.Values object")

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
        options.omnispec = True

    return options, args

def main(argv=None):
    # do initial setup & process the user's call
    if argv is None:
        argv = sys.argv[1:]
    try:
        framework, config, args, opts = initialize(argv)
        retVal = API_call(framework, config, args, opts, verbose=opts.verbose)
    except OmniError, exc:
        sys.exit()

        
if __name__ == "__main__":
    sys.exit(main())
