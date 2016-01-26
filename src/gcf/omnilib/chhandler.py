#!/usr/bin/python

from __future__ import absolute_import

#----------------------------------------------------------------------
# Copyright (c) 2012-2016 Raytheon BBN Technologies
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
"""
Omni Clearinghouse call handler
Handle calls to clearinghouse functions, dispatching to the right
framework as necessary.
Also based on invocation mode, skip experimenter checks of inputs/outputs.
"""

import dateutil.parser
import json
import logging
import os
import pprint
import re
import string

from ..geni.util.tz_util import tzd
from ..geni.util.urn_util import nameFromURN, is_valid_urn_bytype
from ..sfa.util.xrn import get_leaf
from .util import OmniError
from .util.dossl import _do_ssl
from .util import credparsing as credutils
from .util.handler_utils import _get_slice_cred, _listaggregates, _print_slice_expiration, _maybe_save_slicecred, _save_cred, _get_user_urn, _lookupAggNick, \
    _construct_output_filename, _printResults

class CHCallHandler(object):
    """
    Omni Clearinghouse call handler
    Handle calls to clearinghouse functions, dispatching to the right
    framework as necessary.
    Also based on invocation mode, skip experimenter checks of inputs/outputs.
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

    def _raise_omni_error( self, msg, err=OmniError ):
        self.logger.error( msg )
        raise err, msg

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

    def get_ch_version(self, args):
        '''Call GetVersion at the Clearinghouse (if implemented).
        Output directing options:
        -o Save result in a file
        -p (used with -o) Prefix for resulting filename
        --outputfile If supplied, use this output file name
        If not saving results to a file, they are logged.
        If intead of -o you specify the --tostdout option, then instead of logging, print to STDOUT.

        File names will indicate the CH name from the omni config
        e.g.: myprefix-portal-chversion.txt
        '''
        retVal = ""
        (ver, message) = self.framework.get_version()
        if ver and ver != dict():
            pp = pprint.PrettyPrinter(indent=4)
            prettyVersion = pp.pformat(ver)

            # Save/print out result
            header=None
            filename = None
            if self.opts.output:
                filename = _construct_output_filename(self.opts, self.opts.framework, None, None, "chversion", ".json", 0)

            if filename is None:
                self.logger.info("Printing clearinghouse %s version", self.opts.framework)

            _printResults(self.opts, self.logger, header, prettyVersion, filename)
            if filename:
                retVal += "Saved Clearinghouse %s Version to file %s. \n" % (self.opts.framework, filename)
            else:
                retVal += "Printed Clearinghouse %s version" % self.opts.framework

        else:
            printStr = "GetVersion failed at CH %s: %s" % (self.opts.framework, message)
            retVal += printStr + "\n"
            self.logger.error(printStr)
            if not self.logger.isEnabledFor(logging.DEBUG):
                self.logger.warn( "   Try re-running with --debug for more information." )
        return retVal, ver

    def listaggregates(self, args):
        """Print the known aggregates' URN and URL.
        Gets aggregates from:
        - command line (one per -a arg, no URN available), OR
        - command line nickname (one per -a arg, URN may be supplied), OR
        - omni_config (1+, no URNs available), OR
        - Specified control framework (via remote query).
           This is the aggregates that registered with the framework.

        Output directing options:
        -o Save result in a file
        -p (used with -o) Prefix for resulting filename
        --outputfile If supplied, use this output file name
        If not saving results to a file, they are logged.
        If intead of -o you specify the --tostdout option, then instead of logging, print to STDOUT.

        File names will indicate the CH name from the omni config
        e.g.: myprefix-portal-aggregates.txt

        """
        retStr = ""
        retVal = {}
        (aggs, message) = _listaggregates(self)
        aggList = aggs.items()
        aggCnt = 0
        pretty_result = "%d aggregates listed at the %s clearinghouse:\n" % (len(aggList), self.opts.framework)
        for (urn, url) in aggList:
            aggCnt += 1
            agg_nickname = _lookupAggNick(self, urn)
            if agg_nickname:
                pretty_result += "  Aggregate %d:\n \t%s \n \t%s \n \t%s\n" % (aggCnt, agg_nickname, urn, url) 
            else:
                pretty_result += "  Aggregate %d:\n \t%s \n \t%s\n" % (aggCnt, urn, url) 
            retVal[urn] = url

        # Save/print out result
        header=None
        filename = None
        if self.opts.output:
            filename = _construct_output_filename(self.opts, self.opts.framework, None, None, "aggregates", ".txt", 0)

        _printResults(self.opts, self.logger, header, pretty_result, filename)

        if aggs == {} and message != "":
            retStr += ("No aggregates found: %s" % message)
        elif len(aggList)==0:
            retStr = "No aggregates found."
        elif len(aggList) == 1:
            retStr = "Found 1 aggregate. URN: %s; URL: %s" % (retVal.keys()[0], retVal[retVal.keys()[0]])
        else:
            retStr = "Found %d aggregates. " % len(aggList)
            if filename:
                retStr += "Saved Aggregate List to file %s." % (filename)
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
        if not is_valid_urn_bytype(urn, 'slice', self.logger):
            msg = "Invalid slice URN: ensure your slice name uses only letters, numbers, and hyphens (no hyphen in first character), and is <= 19 characters long"
            if self.opts.devmode:
                self.logger.warn(msg + " - but continuing...")
            else:
                self._raise_omni_error(msg)
        
        (slice_cred, message) = _do_ssl(self.framework, None, "Create Slice %s" % urn, self.framework.create_slice, urn)
        if slice_cred:
            slice_exp = credutils.get_cred_exp(self.logger, slice_cred)
            printStr = "Created slice with Name %s, URN %s, Expiration %s" % (name, urn, slice_exp) 
            retVal += printStr+"\n"
            self.logger.info( printStr )
            if self.opts.api_version >= 3:
                slice_cred = self.framework.wrap_cred(slice_cred)
            filename = _maybe_save_slicecred(self, name, slice_cred)
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
            self._raise_omni_error('renewslice missing args or too many args: Supply <slice name> <expiration date>')
        name = args[0]
        expire_str = args[1]

        # convert the slice name to a framework urn
        # FIXME: catch errors getting slice URN to give prettier error msg?
        urn = self.framework.slice_name_to_urn(name)

        # convert the desired expiration to a python datetime
        # FIXME: See amhandler._datetimeFromString: converts to naive UTC, adds UTC TZ
        try:
            in_expiration = dateutil.parser.parse(expire_str, tzinfos=tzd)
            self.logger.debug("From '%s' parsed requested new expiration %s", expire_str, in_expiration)
            in_expiration2 = in_expiration.replace(microsecond=0)
            if (in_expiration2 != in_expiration):
                self.logger.debug("Trimmed fractional seconds from parsed time.")
                in_expiration = in_expiration2
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
            if self.opts.slicecredfile and os.path.exists(self.opts.slicecredfile):
                scwarn = "Saved slice credential %s is now wrong; will replace with new slice credential. " % (self.opts.slicecredfile)
                self.logger.info(scwarn)
                retVal += scwarn +"\n"
                sf = self.opts.slicecredfile
                self.opts.slicecredfile = None
                (cred, _) = _get_slice_cred(self, urn)
                self.opts.slicecredfile = sf
                if cred:
                    self.opts.slicecredfile = _save_cred(self, self.opts.slicecredfile, cred)
        else:
            prtStr = "Failed to renew slice %s" % (name)
            if message != "":
                prtStr += ". " + message
            self.logger.warn( prtStr )
            retVal = prtStr+"\n"
            retTime = None
        retVal +=_print_slice_expiration(self, urn)
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

    def listslices(self, args):
        """Alias for listmyslices.
        Provides a list of slices of user provided as first
        argument, or current user if no username supplied.
        Not supported by all frameworks."""
        return self.listmyslices(args)

    def listmyslices(self, args):
        """Provides a list of slices of user provided as first
        argument, or current user if no username supplied.
        Not supported by all frameworks.

        Output directing options:
        -o Save result in a file
        -p (used with -o) Prefix for resulting filename
        --outputfile If supplied, use this output file name
        If not saving results to a file, they are logged.
        If intead of -o you specify the --tostdout option, then instead of logging, print to STDOUT.

        File names will indicate the username whose slices are listed and the configuration
        file name of the framework
        e.g.: myprefix-jsmith-slices-portal.txt
        """
        if len(args) > 0:
            username = args[0].strip()
        elif self.opts.speaksfor:
            username = get_leaf(self.opts.speaksfor)
        else:
            username = get_leaf(_get_user_urn(self.logger, self.framework.config))
            if not username:
                self._raise_omni_error("listmyslices failed to find your username")

        retStr = ""
        (slices, message) = _do_ssl(self.framework, None, "List Slices from Slice Authority", self.framework.list_my_slices, username)
        if slices is None:
            # only end up here if call to _do_ssl failed
            slices = []
            self.logger.error("Failed to list slices for user '%s'"%(username))
            retStr += "Server error: %s. " % message
        elif len(slices) > 0:
            slices = sorted(slices)
            result="User '%s' has %d slice(s): \n" % (username, len(slices))
            result += "\t%s" % ("\n\t".join(slices))
            # Save/print out result
            header = None
            filename = None
            if self.opts.output:
                filename = _construct_output_filename(self.opts, username, self.opts.framework, None, "slices", ".txt", 0)

            _printResults(self.opts, self.logger, header, result, filename)
            if filename:
                retStr += "Saved user %s slices to file %s. " % (username, filename)
            else:
                retStr += "Printed user %s slices. " % username
        else:
            self.logger.info("User '%s' has NO slices."%username)

        # summary
        retStr += "Found %d slice(s) for user '%s'. "%(len(slices), username)

        return retStr, slices

    def listprojects(self, args):
        """Alias for listmyprojects.
        Provides a list of projects of user provided as first
        argument, or current user if no username supplied.
        Not supported by all frameworks."""
        return self.listmyprojects(args)

    def listmyprojects(self, args):
        """Provides a list of projects of user provided as first
        argument, or current user if no username supplied.
        Not supported by all frameworks.

        Return object is a list of structs, containing
        PROJECT_URN, PROJECT_UID, EXPIRED, and PROJECT_ROLE. EXPIRED is a boolean.

        Output directing options:
        -o Save result in a file
        -p (used with -o) Prefix for resulting filename
        --outputfile If supplied, use this output file name
        If not saving results to a file, they are logged.
        If intead of -o you specify the --tostdout option, then instead of logging, print to STDOUT.

        File names will indicate the username whose projects are listed and the configuration
        file name of the framework
        e.g.: myprefix-jsmith-projects-portal.txt
        """
        if len(args) > 0:
            username = args[0].strip()
        elif self.opts.speaksfor:
            username = get_leaf(self.opts.speaksfor)
        else:
            username = get_leaf(_get_user_urn(self.logger, self.framework.config))
            if not username:
                self._raise_omni_error("listmyprojects failed to find your username")

        retStr = ""
        projectnames = list()
        projects = None
        samsg = None
#        ((projects, samsg), message) = _do_ssl(self.framework, None, "List Projects from Slice Authority", self.framework.list_my_projects, username)
        (res, message) = _do_ssl(self.framework, None, "List Projects from Slice Authority", self.framework.list_my_projects, username)
        if res is not None:
            (projects, samsg) = res
        if res is None or projects is None:
            # only end up here if call to _do_ssl failed
            projects = []
            self.logger.error("Failed to list projects for user '%s'"%(username))
            if samsg:
                retStr += "Server error: %s. " % samsg
                if message:
                    retStr += "(%s) " % message
            else:
                retStr += "Server error: %s. " % message
        elif len(projects) > 0:
            expiredprojects = list()
            for tup in projects:
                expired = False
                project = tup['PROJECT_URN']
                projectlower = string.lower(project)
                if not string.find(projectlower, "+project+"):
                    self.logger.debug("Skipping non project URN '%s'", project)
                    continue

                # Use the project name, not URN, for the pretty result
#                projectname = project
                projectname = nameFromURN(project)

                # Returning this key is non-standard..
                if tup.has_key('EXPIRED'):
                    exp = tup['EXPIRED']
                    if exp == True:
                        expired = True
                if tup.has_key('PROJECT_ROLE'):
                    role = tup['PROJECT_ROLE']
                    projectname += " \t(%s)" % role.lower()
                if expired:
                    expiredprojects.append(projectname)
                else:
                    projectnames.append(projectname)

            # FIXME: Need a custom sort that accounts for role?
            projectnames = sorted(projectnames)
            expiredprojects = sorted(expiredprojects)

            if len(expiredprojects) > 0:
                result="User '%s' has %d project(s) and %d expired project(s). \n" % (username, len(projectnames), len(expiredprojects))
            else:
                result="User '%s' has %d project(s) \n" % (username, len(projectnames))
            if len(projectnames) > 0:
                result += "User's active project(s): \n"
                result += "\t%s" % ("\n\t".join(projectnames))

            # Suppress expired projects by default
            if self.opts.debug or self.opts.devmode:
                if len(expiredprojects) > 0:
                    result += "\n\nUser's expired project(s): \n"
                    result += "\t%s" % ("\n\t".join(expiredprojects))

            # Save/print out result
            header = None
            filename = None
            if self.opts.output:
                filename = _construct_output_filename(self.opts, username, self.opts.framework, None, "projects", ".txt", 0)

            # FIXME: Is it better if we are writing to a file to write out the full projects struct?
            _printResults(self.opts, self.logger, header, result, filename)
            if filename:
                retStr += "Saved user %s projects to file %s. " % (username, filename)
            else:
                retStr += "Printed user %s projects. " % username
        else:
            self.logger.info("User '%s' has NO projects."%username)

        # summary
        retStr += "Found %d project(s) for user '%s'. "%(len(projectnames), username)

        return retStr, projects

    def listkeys(self, args):
        """Provides a list of SSH public keys registered at the CH for the specified user,
        or the current user if not specified.
        Not supported by all frameworks, and some frameworks insist on only the current user.
        At some frameworks will return the caller's private SSH key if known.

        Output directing options:
        -o Save result in a file
        -p (used with -o) Prefix for resulting filename
        --outputfile If supplied, use this output file name
        If not saving results to a file, they are logged.
        If intead of -o you specify the --tostdout option, then instead of logging, print to STDOUT.

        File names will indicate the username whose keys are listed and the configuration
        file name of the framework
        e.g.: myprefix-jsmith-keys-portal.txt
        """
        username = None
        if len(args) > 0:
            username = args[0].strip()
            if username == "":
                username = None
        if username is None and self.opts.speaksfor:
            username = get_leaf(self.opts.speaksfor)
        if username is None:
            printusername = get_leaf(_get_user_urn(self.logger, self.framework.config))
            if not printusername:
                self._raise_omni_error("listkeys failed to find your username")
        else:
            printusername = username

        retStr = ""
        (keys, message) = self.framework.list_ssh_keys(username)
        if keys is None or (len(keys) == 0 and message is not None):
            keys = []
            self.logger.error("Failed to list keys for you")
            if message and message.strip() != "":
                retStr += "Failed to list keys - Server error: %s. " % message
            else:
                retStr += "Failed to list keys - Server error. "

        elif len(keys) > 0:
            result="User '%s' has %d key(s): \n" % (printusername, len(keys))
            i = 0
            for key in keys:
                if not key.has_key("public_key"):
                    continue
                i += 1
                result += "    Key pair %d:\n" % i
                result += "\tPublic key %d: %s\n" % (i, key["public_key"])
                if key.has_key("private_key"):
                    result += "\tPrivate key %d: \n%s\n" % (i, key["private_key"])
#            result += "\t%s" % ("\n\t".join(keys))
            # Save/print out result
            header = None
            filename = None
            if self.opts.output:
                filename = _construct_output_filename(self.opts, printusername, self.opts.framework, None, "keys", ".txt", 0)

            _printResults(self.opts, self.logger, header, result, filename)
            if filename:
                retStr += "Saved user %s keys to file %s. " % (printusername, filename)
            else:
                retStr += "Printed user %s keys. " % printusername

        else:
            self.logger.info("User %s has NO keys.", printusername)

        # summary
        retStr += "Found %d key(s) for user %s.\n"%(len(keys), printusername)

        return retStr, keys


    def listmykeys(self, args):
        """Provides a list of SSH public keys registered at the CH for the specified user,
        or the current user if not specified.
        Not supported by all frameworks, and some frameworks insist on
        only the current user.
        Really just an alias for listkeys."""

        return self.listkeys(args)

    def getusercred(self, args):
        """Retrieve your user credential. Useful for debugging.

        If you specify the -o option, the credential is saved to a file.
        If you specify --usercredfile:
           First, it tries to read the user cred from that file.
           Second, it saves the user cred to a file by that name (but with the appropriate extension)
        Otherwise, the filename is <username>-<framework nickname from config file>-usercred.[xml or json, depending on AM API version].
        If you specify the --prefix option then that string starts the filename.

        If instead of the -o option, you supply the --tostdout option, then the usercred is printed to STDOUT.
        Otherwise the usercred is logged.

        The usercred is returned for use by calling scripts.

        e.g.:
          Get user credential, save to a file:
            omni.py -o getusercred

          Get user credential, save to a file with filename prefix mystuff:
            omni.py -o -p mystuff getusercred
"""
        if self.opts.api_version >= 3:
            (cred, message) = self.framework.get_user_cred_struct()
        else:
            (cred, message) = self.framework.get_user_cred()
        credxml = credutils.get_cred_xml(cred)
        if cred is None or credxml is None or credxml == "":
            msg = "Got no valid user credential from clearinghouse: %s" % message
            if self.opts.devmode:
                self.logger.warn(msg + " ... but continuing")
                credxml = cred
            else:
                self._raise_omni_error(msg)
#        target = credutils.get_cred_target_urn(self.logger, cred)
        # pull the username out of the cred
        # <owner_urn>urn:publicid:IDN+geni:gpo:gcf+user+alice</owner_urn>
        user = ""
        usermatch = re.search(r"\<owner_urn>urn:publicid:IDN\+.+\+user\+(\w+)\<\/owner_urn\>", credxml)
        if usermatch:
            user = usermatch.group(1)
        if self.opts.output:
            if self.opts.usercredfile and self.opts.usercredfile.strip() != "":
                fname = self.opts.usercredfile
            else:
                fname = self.opts.framework + "-usercred"
                if user != "":
                    fname = user + "-" + fname
                if self.opts.prefix and self.opts.prefix.strip() != "":
                    fname = self.opts.prefix.strip() + "-" + fname
            filename = _save_cred(self, fname, cred)
            self.logger.info("Wrote %s user credential to %s" % (user, filename))
            self.logger.debug("User credential:\n%r", cred)
            return "Saved user %s credential to %s" % (user, filename), cred
        elif self.opts.tostdout:
            if user != "":
                self.logger.info("Writing user %s usercred to STDOUT per options", user)
            else:
                self.logger.info("Writing usercred to STDOUT per options")
            # pprint does bad on XML, but OK on JSON
            print cred
            if user:
                return "Printed user %s credential to stdout" % user, cred
            else:
                return "Printed user credential to stdout", cred
        else:
            self.logger.info("User %s user credential:\n%s", user, cred)

        return "Retrieved %s user credential" % user, cred

    def getslicecred(self, args):
        """Get the AM API compliant slice credential (signed XML document).

        If you specify the -o option, the credential is saved to a file.
        The filename is <slicename>-cred.xml
        But if you specify the --slicecredfile option then that is the
        filename used.

        NOTE: If you specify the --slicecredfile option and that
        references a file that is not empty, then that file will be ignored, and replaced if you specify `-o`.

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
        retVal = ""
        sf = None
        if self.opts.slicecredfile and os.path.exists(self.opts.slicecredfile):
            if self.opts.output:
                scwarn = "Ignoring and replacing saved slice credential %s. " % (self.opts.slicecredfile)
            else:
                scwarn = "Ignoring saved slice credential %s. " % (self.opts.slicecredfile)
            self.logger.info(scwarn)
            retVal += scwarn +"\n"
            sf = self.opts.slicecredfile
            self.opts.slicecredfile = None
        (cred, message) = _get_slice_cred(self, urn)

        if cred is None:
            retVal = "No slice credential returned for slice %s: %s"%(urn, message)
            return retVal, None
        if sf:
            self.opts.slicecredfile = sf

        # Log if the slice expires soon
        _print_slice_expiration(self, urn, cred)

        # Print the non slice cred bit to log stream so
        # capturing just stdout gives just the cred hopefully
        self.logger.info("Retrieved slice cred for slice %s", urn)
#VERBOSE ONLY        self.logger.info("Slice cred for slice %s", urn)
#VERBOSE ONLY        self.logger.info(cred)
#        print cred

        retVal = credutils.get_cred_xml(cred)
        retItem = cred
        filename = _maybe_save_slicecred(self, name, cred)
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
        slice name arg may be omitted if you supply the --slicecredfile arg instead.

        --slicecredfile: optional name of saved slice credential file to read from, and from which to get slice expiration
        """

        cred = None
        if self.opts.slicecredfile:
            (cred, message) = _get_slice_cred(self, None)
        urn = ""
        name = ""
        if cred is not None and cred != "":
            urn = credutils.get_cred_target_urn(self.logger, cred)
            if urn:
                name = nameFromURN(urn)

        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            if name != "":
                self.logger.info("No slice name arg provided: retrieved slice name %s from cred", name)
            else:
                # could print help here but that's verbose
                #parse_args(None)
                self._raise_omni_error('print_slice_expiration requires arg of slice name')
        else:
            if name != "" and name != args[0]:
                self.logger.warn("Supplied slice name (%s) doesn't match supplied slice credential (target %s). Using supplied slice name.", args[0], name)
                name = ""
                cred = None
                urn = ""
                self.opts.slicecredfile = None

        if cred is None or cred == "":
            name = args[0]

            # FIXME: catch errors getting slice URN to give prettier error msg?
            urn = self.framework.slice_name_to_urn(name)
            (cred, message) = _get_slice_cred(self, urn)

        retVal = None
        if cred is None:
            retVal = "No slice credential returned for slice %s: %s"%(urn, message)
            return retVal, None

        # Log if the slice expires soon
        retVal = _print_slice_expiration(self, urn, cred)
        return retVal, retVal

    def listslivers(self, args):
        """List all slivers of the given slice by aggregate, as recorded
        at the clearinghouse. Note this is non-authoritative information.
        Argument: slice name or URN
        Return: String printout of slivers by aggregate, with the sliver expiration if known, AND
        A dictionary by aggregate URN of a dictionary by sliver URN of the sliver info records, 
        each of which is a dictionary possibly containing:
         - SLIVER_INFO_URN
         - SLIVER_INFO_SLICE_URN
         - SLIVER_INFO_AGGREGATE_URN
         - SLIVER_INFO_CREATOR_URN
         - SLIVER_INFO_EXPIRATION
         - SLIVER_INFO_CREATION

        Output directing options:
        -o Save result in a file
        -p (used with -o) Prefix for resulting filename
        --outputfile If supplied, use this output file name: substitute slicename for any %s.
        If not saving results to a file, they are logged.
        If intead of -o you specify the --tostdout option, then instead of logging, print to STDOUT.

        File names will indicate the slice name
        e.g.: myprefix-myslice-slivers.txt

         """
        if len(args) == 0 or args[0] is None or args[0].strip() == "":
            self._raise_omni_error("listslivers requires a slice name argument")
        slice_name = args[0]
        slice_urn = self.framework.slice_name_to_urn(slice_name)

        try:
            slivers_by_agg = self.framework.list_sliver_infos_for_slice(slice_urn)
        except NotImplementedError, nie:
            self._raise_omni_error("listslivers is not supported at this clearinghouse using framework type %s" % self.config['selected_framework']['type'])

        if len(slivers_by_agg) == 0:
            result_string = "No slivers found for slice %s" % slice_urn
        else:
            pretty_result = "Slivers by aggregate for slice %s:\n\n" % slice_urn
            for agg_urn in slivers_by_agg:
                pretty_result += "Aggregate: " + agg_urn
                agg_nickname = _lookupAggNick(self, agg_urn)
                if agg_nickname:
                    pretty_result += " ( %s )" % agg_nickname
                pretty_result += "\n"
                for sliver_urn in slivers_by_agg[agg_urn].keys():
                    pretty_result += "    Sliver: " + sliver_urn + "\n"
                    if slivers_by_agg[agg_urn][sliver_urn] is not None and slivers_by_agg[agg_urn][sliver_urn].has_key('SLIVER_INFO_EXPIRATION') and \
                            slivers_by_agg[agg_urn][sliver_urn]['SLIVER_INFO_EXPIRATION'] is not None and \
                            slivers_by_agg[agg_urn][sliver_urn]['SLIVER_INFO_EXPIRATION'].strip() != "" and \
                            slivers_by_agg[agg_urn][sliver_urn]['SLIVER_INFO_EXPIRATION'].strip() != "None":
                        pretty_result += "\tExpires at: " + slivers_by_agg[agg_urn][sliver_urn]['SLIVER_INFO_EXPIRATION'] + " (UTC)\n"
                    else:
                        pretty_result += "\n"
                pretty_result += "\n"

            header=None
            filename = None
            if self.opts.output:
                filename = _construct_output_filename(self.opts, slice_name, None, None, "slivers", ".txt", 0)

            if filename is None and self.opts.tostdout:
                self.logger.info("Printing list of slivers in slice %s", slice_name)

            if filename is not None or self.opts.tostdout:
                _printResults(self.opts, self.logger, header, pretty_result, filename)

            if filename is not None:
                result_string = "Saved list of slivers/aggregates in slice %s to file %s. \n" % (slice_name, filename)
            elif self.opts.tostdout:
                result_string = "Printed list of slivers in slice %s" % slice_name
            else:
                result_string = pretty_result

        return result_string, slivers_by_agg

    def listprojectmembers(self, args):
        """List all the members of a project
        Args: projectname
        Return summary string and list of member dictionaries
        containing PROJECT_MEMBER (URN), EMAIL, [optional: PROJECT_MEMBER_UID], and PROJECT_ROLE.

        Output directing options:
        -o Save result in a file
        -p (used with -o) Prefix for resulting filename
        --outputfile If supplied, use this output file name: substitute projectname for any %s.
        If not saving results to a file, they are logged.
        If intead of -o you specify the --tostdout option, then instead of logging, print to STDOUT.

        File names will indicate the project name
        e.g.: myprefix-myproject-projectmembers.txt

        """
        if len(args) < 1 or args[0] is None or args[0].strip() == "":
            if self.opts.project and self.opts.project.strip() != "":
                project_name = self.opts.project
            else:
                self._raise_omni_error('listprojectmembers missing args: Supply <project name>')
        else:
            project_name = args[0]

        try:
            # Try to get all the members of this project
            members, message = self.framework.get_members_of_project(project_name)
        except NotImplementedError, nie:
            self._raise_omni_error("listprojectmembers is not supported at this clearinghouse using framework type %s" % self.config['selected_framework']['type'])

        if members and len(members) > 0:
            # Save/print out result
            prettyResult = "Project %s has %d members:\n" % (project_name, len(members))
            for i, member in enumerate(members):
                prettyResult += 'Member ' + str(i + 1) + ':\n'
                prettyResult += '   URN = ' + member['PROJECT_MEMBER'] + '\n'
                prettyResult += '   Email = ' + str(member['EMAIL']) + '\n'
                if member.has_key('PROJECT_ROLE'):
                    prettyResult += '   Role = ' + str(member['PROJECT_ROLE']) + '\n'
                if (self.opts.debug or self.opts.devmode) and member.has_key('PROJECT_MEMBER_UID'):
                    prettyResult += '   UID = ' + member['PROJECT_MEMBER_UID'] + '\n'

            header=None
            filename = None
            if self.opts.output:
                filename = _construct_output_filename(self.opts, project_name, None, None, "projectmembers", ".txt", 0)

            if filename is None and self.opts.tostdout:
                self.logger.info("Printing members of project %s", project_name)

            if filename is not None or self.opts.tostdout:
                _printResults(self.opts, self.logger, header, prettyResult, filename)

            if filename is not None:
                prtStr = "Saved list of %d members of project %s to file %s. \n" % (len(members), project_name, filename)
            elif self.opts.tostdout:
                prtStr = "Printed list of %d members in project %s" % (len(members), project_name)
            else:
                prtStr = prettyResult

        else:
            prtStr = "Failed to find members of project %s" % (project_name)
            if message != "":
                prtStr += ". " + message
            self.logger.warn(prtStr)
        return prtStr + '\n', members

    def listslicemembers(self, args):
        """List all the members of a slice
        Args: slicename
        Return summary string and list of member dictionaries
        containing KEYS (list), URN, EMAIL, and ROLE

        Output directing options:
        -o Save result in a file
        -p (used with -o) Prefix for resulting filename
        --outputfile If supplied, use this output file name: substitute slicename for any %s.
        If not saving results to a file, they are logged.
        If intead of -o you specify the --tostdout option, then instead of logging, print to STDOUT.

        File names will indicate the slice name
        e.g.: myprefix-myslice-slicemembers.txt

        """
        if len(args) < 1 or args[0] is None or args[0].strip() == "":
            self._raise_omni_error('listslicemembers missing args: Supply <slice name>')
        slice_name = args[0]

        # convert the slice name to a framework urn
        # FIXME: catch errors getting URN's to give prettier error msg?
        slice_urn = self.framework.slice_name_to_urn(slice_name)

        try:
            # Try to get all the members of this slice
            members, message = self.framework.get_members_of_slice(slice_urn)
        except NotImplementedError, nie:
            self._raise_omni_error("listslicemembers is not supported at this clearinghouse using framework type %s" % self.config['selected_framework']['type'])

        if members and len(members) > 0:
            # Save/print out result
            prettyResult = "Members of slice %s are:\n" % (slice_name)
            for i, member in enumerate(members):
                prettyResult += 'Member ' + str(i + 1) + ':\n'
                prettyResult += '   URN = ' + member['URN'] + '\n'
                prettyResult += '   Email = ' + str(member['EMAIL']) + '\n'
                if member.has_key('ROLE'):
                    prettyResult += '   Role = ' + str(member['ROLE']) + '\n'
                prettyResult += '   Keys = ' + str(member['KEYS']) + '\n'

            header=None
            filename = None
            if self.opts.output:
                filename = _construct_output_filename(self.opts, slice_name, None, None, "slicemembers", ".txt", 0)

            if filename is None and self.opts.tostdout:
                self.logger.info("Printing members of slice %s", slice_name)

            if filename is not None or self.opts.tostdout:
                _printResults(self.opts, self.logger, header, prettyResult, filename)

            if filename is not None:
                prtStr = "Saved members of slice %s to file %s. \n" % (slice_name, filename)
            elif self.opts.tostdout:
                prtStr = "Printed list of members in slice %s" % slice_name
            else:
                prtStr = prettyResult

        else:
            prtStr = "Failed to find members of slice %s" % (slice_name)
            if message != "":
                prtStr += ". " + message
            self.logger.warn(prtStr)
        return prtStr + '\n', members

    def addslicemember(self, args):
        """Add a user to a slice
        Args: slicename username [optional: role name, default 'MEMBER']
        Return summary string and whether successful
        """
        if len(args) != 2 and len(args) != 3:
            self._raise_omni_error('addslicemember missing args: Supply <slice name> <username> [role = MEMBER]')
        slice_name = args[0].strip()
        member_name = args[1].strip()
        if len(args) == 3:
            role = args[2].strip()
        else:
            role = 'MEMBER'

        # convert the slice and member name to a framework urn
        # FIXME: catch errors getting URN's to give prettier error msg?
        slice_urn = self.framework.slice_name_to_urn(slice_name)

        # Try to add the member to the slice
        (res, m2) = _do_ssl(self.framework, None, "Add user %s to slice %s" % (member_name, slice_name), self.framework.add_member_to_slice, slice_urn, member_name, role)
        if res is None:
            success = False
            message = None
        else:
            (success, message) = res

        if success:
            prtStr = "User %s is now a %s in slice %s" % (member_name, role, slice_name)
            self.logger.info(prtStr)
        else:
            prtStr = "Failed to add user %s to slice %s" % (member_name, slice_name)
            if message and message.strip() != "":
                prtStr += ". " + message
            if m2 and m2.strip() != "":
                if "NotImplementedError" in m2:
                    prtStr += ". Framework type %s does not support add_member_to_slice." % self.config['selected_framework']['type']
                else:
                    prtStr += ". " + m2
            self.logger.warn(prtStr)
        return prtStr + '\n', success

    def removeslicemember(self, args):
        """Remove a user from a slice.
        Args: slicename username 
        Return summary string and whether successful
        """
        if len(args) != 2 and len(args) != 3:
            self._raise_omni_error('removeslicemember missing args: Supply <slice name> <username>')
        slice_name = args[0].strip()
        member_name = args[1].strip()

        # convert the slice and member name to a framework urn
        # FIXME: catch errors getting URN's to give prettier error msg?
        slice_urn = self.framework.slice_name_to_urn(slice_name)

        # Try to remove the member from the slice
        (res, m2) = _do_ssl(self.framework, None, "Remove user %s from slice %s" % (member_name, slice_name), self.framework.remove_member_from_slice, slice_urn, member_name)
        if res is None:
            success = False
            message = None
        else:
            (success, message) = res

        if success:
            prtStr = "User %s has been removed from slice %s" % (member_name, slice_name)
            self.logger.info(prtStr)
        else:
            prtStr = "Failed to remove user %s from slice %s" % (member_name, slice_name)
            if message and message.strip() != "":
                prtStr += ". " + message
            if m2 and m2.strip() != "":
                if "NotImplementedError" in m2:
                    prtStr += ". Framework type %s does not support 'removeslicemember'." % self.config['selected_framework']['type']
                else:
                    prtStr += ". " + m2
            self.logger.warn(prtStr)
        return prtStr + '\n', success


#########
## Helper functions follow

#######################
#### GD Additions #####
#######################

    def listkeys_gdstyle(self, args):
        """Provides a list of SSH public keys registered at the CH for the specified user,
        or the current user if not specified.
        Not supported by all frameworks, and some frameworks insist on only the current user.
        At some frameworks will return the caller's private SSH key if known.

        Output directing options:
        -o Save result in a file
        -p (used with -o) Prefix for resulting filename
        --outputfile If supplied, use this output file name
        If not saving results to a file, they are logged.
        If intead of -o you specify the --tostdout option, then instead of logging, print to STDOUT.

        File names will indicate the username whose keys are listed and the configuration
        file name of the framework
        e.g.: myprefix-jsmith-keys-portal.txt
        """
        username = None
        if len(args) > 0:
            username = args[0].strip()
            if username == "":
                username = None
        if username is None and self.opts.speaksfor:
            username = get_leaf(self.opts.speaksfor)
        if username is None:
            printusername = get_leaf(_get_user_urn(self.logger, self.framework.config))
            if not printusername:
                self._raise_omni_error("listkeys failed to find your username")
        else:
            printusername = username

        retStr = ""
        (keys, message) = self.framework.list_ssh_keys(username)
        if keys is None or (len(keys) == 0 and message is not None):
            keys = []
            self.logger.error("Failed to list keys for you")
            if message and message.strip() != "":
                retStr += "Failed to list keys - Server error: %s. " % message
            else:
                retStr += "Failed to list keys - Server error. "

        elif len(keys) > 0:
            result="User '%s' has %d key(s): \n" % (printusername, len(keys))
            i = 0
            for key in keys:
                if not key.has_key("public_key"):
                    continue
                i += 1
                result += "    Key pair %d:\n" % i
                result += "\tPublic key %d: %s\n" % (i, key["public_key"])
                if key.has_key("private_key"):
                    result += "\tPrivate key %d: \n%s\n" % (i, key["private_key"])
#            result += "\t%s" % ("\n\t".join(keys))
            # Save/print out result
            header = None
            filename = None
            if self.opts.output:
                filename = _construct_output_filename(self.opts, printusername, self.opts.framework, None, "keys", ".txt", 0)

            _printResults(self.opts, self.logger, header, result, filename)
            if filename:
                retStr += "Saved user %s keys to file %s. " % (printusername, filename)
            else:
                retStr += "Printed user %s keys. " % printusername

        else:
            self.logger.info("User %s has NO keys.", printusername)

        # summary
        retStr += "Found %d key(s) for user %s.\n"%(len(keys), printusername)

        return retStr, keys

    def lookupuser (self, args):
        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            self._raise_omni_error('lookupuser requires arg of userurn')

        user_urn = args[0]
        (user_details, msg) = self.framework.user_lookup_by_urn(user_urn)
        return msg,user_details


    def slice_uid_to_urn (self, args):
        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            self._raise_omni_error('lookupslice_by_uid requires arg of slice uuid')

        slice_uuid = args[0]
        slice_urn = self.framework.slice_lookup_by_uuid(slice_uuid)
        return slice_urn

    def list_slice_details (self, args):
        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            self._raise_omni_error('lookupslice_by_urn requires arg of slice urn')

        slice_urn = args[0]
        sliceDetails = self.framework.slice_lookup_by_urn(slice_urn)
        return sliceDetails



    def modifyslicemembership (self, args):
        if len(args) == 0 or args[0] == None or args[0].strip() == "":
            self._raise_omni_error('modifyslicemembership requires arg of userurn and membership json file of the format \
"{\
    "<UserURN>": "<Action> <Role>",\
    "<UserURN>": "<Action> <Role>",\
    "<UserURN>": "<Action> <Role>"\
}"\
where <Action>  = "Change to" | "Add to" | "Remove from Slice"\
and <Role> = "Lead" | "Admin" | "Member" | "Auditor" except where the action is to "Remove from Slice" no role is required.\
')

        sliceurn = args[0]
        memerbship_json_file = args[1]
        (details, msg) = self.framework.modify_slice_membership(sliceurn,memerbship_json_file)
        return msg,details

    def listmyslices_with_role(self, args):
        """Provides a list of slices of user provided as first
        argument, or current user if no username supplied.
        Not supported by all frameworks.

        Output directing options:
        -o Save result in a file
        -p (used with -o) Prefix for resulting filename
        --outputfile If supplied, use this output file name
        If not saving results to a file, they are logged.
        If intead of -o you specify the --tostdout option, then instead of logging, print to STDOUT.

        File names will indicate the username whose slices are listed and the configuration
        file name of the framework
        e.g.: myprefix-jsmith-slices-portal.txt
        """
        if len(args) > 0:
            username = args[0].strip()
        elif self.opts.speaksfor:
            username = get_leaf(self.opts.speaksfor)
        else:
            username = get_leaf(_get_user_urn(self.logger, self.framework.config))
            if not username:
                self._raise_omni_error("listmyslices_with_role failed to find your username")

        retStr = ""
        (slices, message) = _do_ssl(self.framework, None, "List Slices from Slice Authority", self.framework.list_my_slices_with_role, username)
        if slices is None:
            # only end up here if call to _do_ssl failed
            slices = {}
            self.logger.error("Failed to list slices for user '%s'"%(username))
            retStr += "Server error: %s. " % message
        elif len(slices.keys()) > 0:
            #slices = sorted(slices)
            result="User '%s' has %d slice(s): \n" % (username, len(slices.keys()))
            result += "\t%s" % ("\n\t".join(slices.keys()))
            # Save/print out result
            header = None
            filename = None
            if self.opts.output:
                filename = _construct_output_filename(self.opts, username, self.opts.framework, None, "slices", ".txt", 0)

            _printResults(self.opts, self.logger, header, result, filename)
            if filename:
                retStr += "Saved user %s slices to file %s. " % (username, filename)
            else:
                retStr += "Printed user %s slices. " % username
        else:
            self.logger.info("User '%s' has NO slices."%username)

        # summary
        retStr += "Found %d slice(s) for user '%s'. "%(len(slices.keys()), username)

        return retStr, slices




