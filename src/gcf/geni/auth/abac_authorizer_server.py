#----------------------------------------------------------------------       
# Copyright (c) 2010-2014 Raytheon BBN Technologi
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

import optparse
import sys
import SocketServer
import SimpleXMLRPCServer
from gcf.geni.auth.abac_authorizer import ABAC_Authorizer

class AsyncXMLRPCServer(SocketServer.ThreadingMixIn,
                        SimpleXMLRPCServer.SimpleXMLRPCServer):
    pass

def parse_args(argv):
    parser = optparse.OptionParser()

    parser.add_option("--trusted_roots", 
                      help="directory of trusted root certs")
    parser.add_option("--port", help="Port number for server")
    parser.add_option("--authorizer_policy_file", help="JSON policy file")
    parser.add_option("--authorizer_resource_manager", 
                      help="class name for abac resource manager", 
                      default="gcf.geni.auth.abac_resource_manager.GCFAM_Resource_Manager")

    opts = parser.parse_args()[0]
    if not opts.port and \
            not opts.authorizer_policy_file and \
            not opts.trusted_roots:
        parser.print_help()
        sys.exit()

    return opts


def main():
    opts = parse_args(sys.argv)

    server = AsyncXMLRPCServer(('localhost', int(opts.port)), allow_none=True)

    abac_auth = ABAC_Authorizer(opts.trusted_roots, opts)
    server.register_instance(abac_auth)
    print "ABAC Authorizer Server [%s] running on port %s..." % \
        (opts.authorizer_policy_file, opts.port)
    server.serve_forever()


if __name__ == "__main__":
    sys.exit(main())

