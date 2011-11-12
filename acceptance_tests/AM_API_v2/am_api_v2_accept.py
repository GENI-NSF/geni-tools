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
""" Acceptance tests for AM API."""

import copy as docopy
import unittest
import omni_unittest as ut
import pprint

################################################################################
#
# Test scripts which test AM API calls on a CH where the running user
# has permission to create slices.  This script is built on the unittest module.
#
# Purpose of the tests is to determine that AM API is functioning properly.
#
# To run all tests:
# ./am_api_accept.py
#
# To run a single test:
# ./am_api_accept.py Test.test_getversion
#
# To add a new test:
# Create a new method with a name starting with 'test_".  It will
# automatically be run when am_api_accept.py is called.
#
################################################################################

# This is the acceptance test for AM API version 2
API_VERSION = 2

class Test(ut.OmniUnittest):
    """Acceptance tests for GENI AM API v1."""

    def amapiv2_return( self, ret_dict, amapi_command, agg ):
        """Validate the return value of an AM API v2 call.
        
        Input param:
            ret_dict: Return value of an AM API v2 call
            Should contain:
             { 
               'code' : {...}
               'output': ...
               'value': ...
             }
        Returns:
             success_fail, msg, (code, output, value)
             """

        success_fail = True
        code = None
        output = None
        value = None
        msg = ""
        if ret_dict.has_key('code'):
            code = ret_dict['code']
            # am_code, am_type, and geni_code are optional?
            # do we need to test for these

        else:
            msg = "code not returned by '%s' call from aggregate '%s'" % (amapi_command, agg)
            success_fail = False

        if ret_dict.has_key('output'):
            output = ret_dict['output']
        else:
            msg = "output not returned by '%s' call from aggregate '%s'" % (amapi_command, agg)
            success_fail = False

        if ret_dict.has_key('value'):
            value = ret_dict['value']
        else:
            msg = "value not returned by '%s' call from aggregate '%s'" % (amapi_command, agg)
            success_fail = False

        return success_fail, msg, (code, output, value)


    def geni_rspec_versions( self, value, geni_version, agg ):
        """Validate the value of 'geni_ad_rspec_versions' or 'geni_request_rspec_versions'.
        
        Input param:
            value
            Should contain:
             { 
               'type' : ...
               'version': ...
               'schema': ...
               'namespace': ...
             }
        Returns:
             success_fail, msg
             """

        success_fail = True
        msg = ""

        if value.has_key(geni_version):
            ver_list = value[ geni_version ]

            for ver_dict in ver_list:
                if not ver_dict.has_key('type'):
                    msg = "%s[ 'type' ] not returned as expected from aggregate '%s'" % (geni_version, agg)
                    success_fail = False
                    break
                if not ver_dict.has_key('version'):
                    msg = "%s[ 'version' ] not returned as expected from aggregate '%s'" % (geni_version, agg)
                    success_fail = False
                    break
                if not ver_dict.has_key('schema'):
                    msg = "%s[ 'schema' ] not returned as expected from aggregate '%s'" % (geni_version, agg)
                    success_fail = False
                    break
                if not ver_dict.has_key('namespace'):
                    msg = "%s[ 'namespace' ] not returned as expected from aggregate '%s'" % (geni_version, agg)
                    success_fail = False
                    break
        else:
            msg = '%s not returned as expected from aggregate "%s"' % (geni_version, agg)
            success_fail = False

        return success_fail, msg

    # def geni_api_versions( self, value, agg ):
    #     """Validate the value of 'geni_api_versions'.
        
    #     Input param:
    #         value
    #         Should contain:
    #          { 
    #            'API_VERSION' : <url>
    #          }
    #     Returns:
    #          success_fail, msg
    #          """

    #     success_fail = True
    #     msg = ""

    #     if value.has_key( 'geni_api_versions' ):
    #         api_versions = value[ 'geni_api_versions' ]
    #     else:
    #         msg = "geni_api_versions not returned as expected from aggregate '%s'" % (agg)
    #         success_fail = False
    #         return success_fail, msg

    #     # loop over version starting with current and working backwards
    #     if api_versions.has_key(str(API_VERSION)):
    #         location = api_versions[ str(API_VERSION) ]
    #         # Test whether location is a url
    #         if location not URL:
    #             msg = "geni_api_versions['%s'] not return a URL as expected from aggregate '%s'" % (str(API_VERSION),agg)
    #             success_fail = False
    #     else:
    #         msg = "geni_api_versions['%s'] not returned as expected from aggregate '%s'" % (str(API_VERSION),agg)
    #         success_fail = False
            
    #     for ver in range(API_VERSION-1,0,-1):
    #         if api_versions.has_key(str(ver)):
    #             location = api_versions[ str(ver) ]
    #             # Test whether location is a url
    #             if location not URL:
    #                 msg = "geni_api_versions['%s'] not return a URL as expected from aggregate '%s'" % (str(ver),agg)
    #             success_fail = False
    #             break
    #     else:
    #         msg = '%s not returned as expected from aggregate "%s"' % (geni_version, agg)
    #         success_fail = False

    #     return success_fail, msg


    def test_getversion(self):
        """Passes if a 'getversion' returns ....""" 

        self.section_break()
        options = docopy.deepcopy(self.options)
        # now modify options for this test as desired

        # now construct args
        omniargs = ["getversion"]
        (text, ret_dict) = self.call(omniargs, options)

        success_fail = True
        msg = "All aggregates returned a geni_api version of %s" % (str(API_VERSION))
        if type(ret_dict) == type({}):
            # loop through each aggregate
            for (agg, ver_dict) in ret_dict.items():
                if ver_dict is not None: 
                    if ver_dict.has_key('geni_api'):
                        # Fails if any aggs return geni_api != API_VERSION
                        if str(ver_dict['geni_api']) != str(API_VERSION):
                            msg = 'geni_api version returned "%s" not "%s" as expected from aggregate "%s"' % ( str(ver_dict['geni_api']), str(API_VERSION), agg)
                            success_fail = False
                            break
                    else:
                        pprinter = pprint.PrettyPrinter(indent=4)
                        msg = "No geni_api version listed in 'getversion' return from aggregate '%s': \n%s" % (agg, pprinter.pformat(ver_dict))
                        success_fail = False
                        break

                    # Fails if return does not contain code, output, and value
                    success_fail, msg, (code, output, value) = self.amapiv2_return( ver_dict, 'getversion', agg )
                    if success_fail is False:
                        break

                    if value.has_key('geni_api'):
                        # Fails if any aggs return geni_api != API_VERSION
                        if str(value['geni_api']) != str(API_VERSION):
                            msg = 'value["geni_api"] version returned "%s" not "%s" as expected from aggregate "%s"' % ( str(value['geni_api']), str(API_VERSION), agg)
                            success_fail = False
                            break
                    else:
                        msg = "No value['geni_api'] version listed in 'getversion' return from aggregate '%s'" % (agg)
                        success_fail = False
                        break
                    # Fails if any aggs not return 
                    # geni_request_rspec_versions                        
                    success_fail, msg = self.geni_rspec_versions( value, 
                                        'geni_request_rspec_versions', 
                                        agg )
                    if success_fail is False:
                        break

                    # Fails if any aggs not return 
                    # geni_ad_rspec_versions
                    success_fail, msg = self.geni_rspec_versions( value, 
                                        'geni_ad_rspec_versions', 
                                        agg )
                    if success_fail is False:
                        break
                    # TO DO
                    # Test for geni_api_versions?
                    # See start to method above

                else:
                    pprinter = pprint.PrettyPrinter(indent=4)
                    msg = '"getversion" fails to return an XMLRPC struct from aggregate "%s": \n%s' % (agg, pprinter.pformat(ver_dict))
                    success_fail = False
                    break
        else:
            # To end up here, means something went wrong in Omni
            pprinter = pprint.PrettyPrinter(indent=4)
            msg = 'Failure. Returned: \n%s' % (pprinter.pformat(ret_dict))
            success_fail = False

#        self.print_monitoring( success_fail )
        self.assertTrue(success_fail, msg)



if __name__ == '__main__':
    # Include default Omni command line options
    # Support unittest option by replacing -v and -q with --vv a --qq
    Test.unittest_parser()

    # Invoke unit tests as usual
    unittest.main()


