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

""" The omni-configure.py script.
    This script is meant to help new users setup their omni config in 
    a standard way. Although many of the parameters can be customized using
    command line options, the user should be able to run the script
    with the default configuration and configure Omni. This script should be
    used by new user that want a default configuration of Omni. If advanced
    configuration is needed (multiple users, etc) this should still be done
    manually by editing the omni configuration file. 
"""

import string
import sys, os
from subprocess import Popen, PIPE
import ConfigParser
import optparse
from sfa.trust.certificate import Certificate, Keypair

def parseArgs(argv, options=None):
    """Construct an Options Parser for parsing omni-configure command line
    arguments, and parse them.
    """

    parser = optparse.OptionParser()
    parser.add_option("-c", "--configfile", default="~/.gcf/omni_config",
                      help="Config file location", metavar="FILE")
    parser.add_option("-p", "--cert", default="~/.ssl/geni_cert",
                      help="User certificate file location", metavar="FILE")
    parser.add_option("-k", "--plkey", default="~/.ssh/geni_pl_key",
                      help="PlanetLab private key file location", metavar="FILE")
    parser.add_option("-f", "--framework", default="pg", type='choice',
                      choices=['pg', 'pl'],
                      help="Control framework that you have an account with")
    parser.add_option("-v", "--verbose", default=False, action="store_true",
                      help="Turn on verbose command summary for omni-configure script")

    if argv is None:
        # prints to stderr
        parser.print_help()
        return

    (opts, args) = parser.parse_args(argv, options)
    print opts
    return opts, args

def initialize(opts):

    #Check if directory for config file exists
    # Expand the configfile to a full path
    opts.configfile= os.path.expanduser(opts.configfile)
    configdir = os.path.dirname(opts.configfile)
    if not os.path.exists(configdir):
      # If the directory does not exist but it is the 
      # default directory, create it, if not print an error
      if not cmp(os.path.expanduser('~/.gcf'), configdir):
        os.makedirs(configdir)
      else:
        sys.exit('Directory '+ configdir + ' does not exist!')

    # If the value is the default add the appropriate file extention
    # based on the framework
    if not cmp(opts.cert, "~/.ssl/geni_cert") : 
        if not cmp(opts.framework,'pg'):
            opts.cert += ".pem"
        else : 
            if not cmp(opts.framework,'pl'):
                opts.cert += ".gid"
            
    # Expand the cert file to a full path
    opts.cert= os.path.expanduser(opts.cert)

    # Expand the plkey file to a full path
    opts.plkey = os.path.expanduser(opts.plkey)

    # If framework is pgeni, check that the cert file is in the right place
    if not cmp(opts.framework,'pg'):
        if not os.path.exists(opts.cert):
            sys.exit("Geni certificate not in '"+opts.cert+"'. \nMake sure you\
place the .pem file that you downloaded from the Web UI there,\nor\
use the '-p' option to specify a custom location of the certificate.\n")

    # If framework is planetlab, check that the key are in the right place
    if not cmp(opts.framework,'pl'):
        if not os.path.exists(opts.cert):
            sys.exit("\nScript currently does not support automatic download of \
PlanetLab cert.\nIf you have a copy place it at '"+opts.cert+"', \nor \
use the '-p' option to specify a custom location of the certificate.\n")
        if not os.path.exists(opts.plkey) :
            sys.exit("\nPlanetLab private key not in '"+opts.plkey+"'. \nMake sure\
you place the private key registered with PlanetLab there or use\n\
the '-k' option to specify a custom location for the key.\n")
    

def createSSHKeypair(opts):
    if not cmp(opts.framework,'pg'):
      pkey = opts.cert
    else :
      if not cmp(opts.framework,'pl'):
        pkey = opts.plkey

    k = Keypair()
    k.load_from_file(pkey)

    # Figure out where to place the private key
    private_key_file = os.path.expanduser('~/.ssh/geni_key')

    if os.path.exists(private_key_file):
        k_exist = Keypair()
        k_exist.load_from_file(private_key_file)
        # If the file exists and it is not the same as the existing key ask the
        # user to replace it or not
        if not k_exist.is_same(k) : 
            valid_ans=['','y', 'n']
            replace_flag = raw_input("File " + private_key_file + " exists, do you want to replace it [Y,n]?").lower()
            while replace_flag not in valid_ans:
                replace_flag = raw_input("Your input has to be 'y' or <ENTER> for yes, 'n' for no:").lower()
            if replace_flag == 'n' :
                i = 1
                tmp_pk_file = private_key_file + '_' + str(i)
                while os.path.exists(tmp_pk_file):
                    i = i+1
                    tmp_pk_file = private_key_file + '_' + str(i)
                print tmp_pk_file
                private_key_file = tmp_pk_file

    k.save_to_file(private_key_file)
    # Change the permission to something appropriate for keys
    os.chmod(private_key_file, 0600)

    args = ['ssh-keygen', '-y', '-f']
    args.append(private_key_file)
    p = Popen(args, stdout=PIPE)
    public_key = p.communicate()[0]
    if p.returncode != 0:
        raise Exception("Error creating public key")
    public_key_file = private_key_file + '.pub'
    f = open(public_key_file,'w')
    f.write("%s" % public_key)
    f.close()

    return private_key_file, public_key_file

def createConfigFile(opts, public_key_file):

    cert = Certificate(filename=opts.cert)
    # We need to get the issuer and the subject for SFA frameworks
    # issuer -> authority
    # subject -> user
    issuer = cert.get_issuer()
    subject = cert.get_subject()

    # The user URN is in the Alternate Subject Data
    cert_alt_data = cert.get_data()
    data = cert_alt_data.split(',')
    user_urn_list = [o for o in data if o.find('+user+') != -1]

    # If there is no data that has the string '+user+' this probably means that 
    # the provided cert is not a user cert
    if len(user_urn_list) == 0:
      sys.exit("The certificate is probably not a user cert")

    # XXX If there are more data with the '+user+' string probably more than one
    # user URNs in the cert. For now exit, but maybe the right thing would be to
    # pick one?
    if len(user_urn_list) > 1:
      sys.exit("There are more than one user URNs in the cert. Exit!")

    urn = user_urn_list[0].lstrip('URI:')
    user = urn.split('+')[-1]

    if not cmp(opts.framework,'pg'):
        cf_section = """
[%s]
type = pg
ch = https://www.emulab.net:443/protogeni/xmlrpc/ch
sa = https://www.pgeni.gpolab.bbn.com:443/protogeni/xmlrpc/sa
cert = %s
key = %s
""" %(opts.framework, opts.cert, opts.cert)

    else:
      if not cmp(opts.framework, 'pl'):
        cf_section = """
[%s]
type = sfa
authority=%s
user=%s
cert=%s
key=%s
registry=http://www.planet-lab.org:12345
slicemgr=http://www.planet-lab.org:12347
""" %(opts.framework, issuer, subject, opts.cert, opts.plkey)

    omni_config_dict = {
                        'cf' : opts.framework,
                        'user' : user, 
                        'urn' : urn,
                        'pkey' : public_key_file,
                        'cf_section' : cf_section,
                       }

    omni_config_file="""
[omni]
default_cf = %(cf)s 
users = %(user)s

# ---------- Users ----------
[%(user)s]
urn = %(urn)s
keys = %(pkey)s

# ---------- Frameworks ----------
%(cf_section)s

#------AM nicknames
# Format :
# Nickname=URN, URL
# URN is optional
[aggregate_nicknames]
pg-gpo=,https://pgeni.gpolab.bbn.com/protogeni/xmlrpc/am
pg-utah=,https://www.emulab.net/protogeni/xmlrpc/am
plc=,https://www.planet-lab.org:12346
pg-ky=,https://www.uky.emulab.net/protogeni/xmlrpc/am

# Private myplc installations
plc-gpo=,http://myplc.gpolab.bbn.com:12346/
plc-clemson=,http://myplc.clemson.edu:12346/
plc-stanford=,https://myplc.stanford.edu:12346/
plc-wisconsin=,https://wings-openflow-1.wail.wisc.edu:12346/
plc-washington=,https://of.cs.washington.edu:12346/
plc-rutgers=,https://plc.orbit-lab.org:12346/ 
plc-indiana=,https://myplc.grnoc.iu.edu:12346/
plc-gatech=,https://myplc.cip.gatech.edu:12346/
 
# OpenFlow AMs
of-gpo=,https://foam.gpolab.bbn.com:3626/foam/gapi/1
of-stanford=,https://openflow4.stanford.edu:3626/foam/gapi/1
of-clemson=,https://foam.clemson.edu:3626/foam/gapi/1
of-wisconsin=,https://foam.wail.wisc.edu:3626/foam/gapi/1
of-rutgers=,https://foam.oflow.cip.gatech.edu:3626/foam/gapi/1
of-indiana=,https://foam.noc.iu.edu:3626/foam/gapi/1
of-gatech=,https://nox.orbit-lab.org:3626/foam/gapi/1
of-nlr=,https://foam.nlr.net:3626/foam/gapi/1
of-i2=,https://foam.net.internet2.edu:3626/foam/gapi/1


""" % omni_config_dict

    f = open(opts.configfile, 'w')
    print >>f, omni_config_file
    f.close()
   

def main(argv=None):
    # do initial setup & process the user's call
    if argv is None:
        argv = sys.argv[1:]
        (opts, args) = parseArgs(argv)
        initialize(opts)
        (pr_key_file, pub_key_file) = createSSHKeypair(opts)
        createConfigFile(opts,pub_key_file)

        
if __name__ == "__main__":
    sys.exit(main())
