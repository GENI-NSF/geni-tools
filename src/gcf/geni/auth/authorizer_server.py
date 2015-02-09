#----------------------------------------------------------------------
# Copyright (c) 2010-2015 Raytheon BBN Technologies
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

from __future__ import absolute_import

import optparse
import sys
import SocketServer
import SimpleXMLRPCServer

from util import getInstanceFromClassname

class AsyncXMLRPCServer(SocketServer.ThreadingMixIn,
                        SimpleXMLRPCServer.SimpleXMLRPCServer):
    pass

def parse_args(argv):
    parser = optparse.OptionParser()

    parser.add_option("--trusted_roots", 
                      help="directory of trusted root certs")
    parser.add_option("--port", help="Port number for server")
    parser.add_option("--authorizer_policy_map_file", 
                      help="JSON policy map file")
    parser.add_option("--authorizer", 
                      help="class name for authorizer", 
                      default="gcf.geni.auth.abac_authorizer.ABAC_Authorizer")
    parser.add_option("--argument_guard",
                      help="class name for argument guard",
                      default=None)

    opts = parser.parse_args()[0]
    if not opts.port and \
            not opts.authorizer_policy_map_file and \
            not opts.trusted_roots:
        parser.print_help()
        sys.exit()

    return opts


def main():
    opts = parse_args(sys.argv)

    server = AsyncXMLRPCServer(('localhost', int(opts.port)), allow_none=True)

    argument_guard = None
    if opts.argument_guard:
        argument_guard = getInstanceFromClassname(opts.argument_guard)

    authorizer = getInstanceFromClassname(opts.authorizer, 
                                          opts.trusted_roots, opts, 
                                          argument_guard)

#    authorizer._DEFAULT_RULES.dump()
#    for rules in authorizer._AUTHORITY_SPECIFIC_RULES.values():
#        rules.dump()

    server.register_instance(authorizer)
    print "Authorizer Server [%s] [%s] running on port %s..." % \
        (opts.authorizer, opts.authorizer_policy_map_file, opts.port)
    server.serve_forever()


if __name__ == "__main__":
    sys.exit(main())

