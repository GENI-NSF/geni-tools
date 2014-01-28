#----------------------------------------------------------------------
# Copyright (c) 2014 Raytheon BBN Technologies
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

import datetime
from dateutil import parser as du_parser, tz as du_tz
import optparse
import os
import subprocess
import sys
import tempfile
from sfa.trust.certificate import Certificate
from sfa.trust.credential import Credential, signature_template
from sfa.trust.abac_credential import ABACCredential
from sfa.trust.credential_factory import CredentialFactory
from sfa.trust.gid import GID
from xml.dom.minidom import *

# Routine to validate that a speaks-for credential 
# says what it claims to say:
# It is a signed credential wherein the signer S is attesting to the
# ABAC statement:
# S.speaks_for(S)<-T Or "S says that T speaks for S"

# Simple XML helper functions

# Find the text associated with first child text node
def findTextChildValue(root):
    child = findChildNamed(root, '#text')
    if child: return str(child.nodeValue)
    return None

# Find first child with given name
def findChildNamed(root, name):
    for child in root.childNodes:
        if child.nodeName == name:
            return child
    return None

# Write a string to a tempfile, returning name of tempfile
def write_to_tempfile(str):
    str_fd, str_file = tempfile.mkstemp()
    if str:
        os.write(str_fd, str)
    os.close(str_fd)
    return str_file

# Run a subprocess and return output
def run_subprocess(cmd, stdout, stderr):
    proc = subprocess.Popen(cmd, stdout=stdout, stderr=stderr)
    proc.wait()
    if stdout:
        output = proc.stdout.read()
    else:
        output = proc.returncode
    return output

# Pull the keyid (sha1 hash of the bits of the cert public key) from given cert
def get_cert_keyid(gid):

    # Write cert to tempfile
    cert_file = write_to_tempfile(gid.save_to_string())

    # Pull the public key out as pem
    # openssl x509 -in cert.pem -pubkey -noout > key.pem
    cmd = ['openssl', 'x509', '-in', cert_file, '-pubkey', '-noout']
    pubkey = run_subprocess(cmd, subprocess.PIPE, None)
    pubkey_file = write_to_tempfile(pubkey)

    # Pull out the bits
    # openssl asn1parse -in key.pem -strparse 18 -out key.der
    derkey_file = write_to_tempfile(None)
    cmd = ['openssl', 'asn1parse', '-in', pubkey_file, '-strparse', \
               '18', '-out', derkey_file]
    run_subprocess(cmd, subprocess.PIPE, subprocess.PIPE)

    # Get the hash
    # openssl sha1 key.der
    cmd = ['openssl', 'sha1', derkey_file]
    output = run_subprocess(cmd, subprocess.PIPE, subprocess.PIPE)
    parts = output.split(' ')
    keyid = parts[1].strip()

    os.unlink(cert_file)
    os.unlink(pubkey_file)
    os.unlink(derkey_file)

    return keyid

# Pull the cert out of a list of certs in a PEM formatted cert string
def grab_toplevel_cert(cert):
    start_label = '-----BEGIN CERTIFICATE-----'
    start_index = cert.find(start_label) + len(start_label)
    end_label = '-----END CERTIFICATE-----'
    end_index = cert.find(end_label)
    first_cert = cert[start_index:end_index]
    pieces = first_cert.split('\n')
    first_cert = "".join(pieces)
    return first_cert

# Validate that the given speaks-for credential represents the
# statement User.speaks_for(User)<-Tool for the given user and tool certs
# and was signed by the user
# Return: 
#   Boolean indicating whether the given credential 
#      is not expired 
#      is verified by xmlsec1
#      is trusted by given set of trusted roots
#      is an ABAC credential
#      was signed by the user associated with the speaking_for_urn
#      must say U.speaks_for(U)<-T ("user says that T may speak for user")
#  String user certificate of speaking_for user if the above tests succeed
#      (None otherwise)
#  Error message indicating why the speaks_for call failed ("" otherwise)
def verify_speaks_for(cred, tool_gid, speaking_for_urn, \
                          trusted_roots):

    user_gid = cred.signature.gid
    user_urn = user_gid.get_urn()

    user_keyid = get_cert_keyid(user_gid)
    tool_keyid = get_cert_keyid(tool_gid)

    head = cred.get_head()
    principal_keyid = head.get_principal_keyid()
    role = head.get_role()

    tails = cred.get_tails()
    if len(tails) != 1: 
        return False, None, "Invalid ABAC-SF credential: Need 1 tail element" 
    subject_keyid = tails[0].get_principal_keyid()

    # Now tests that this is a valid credential

    # Credential has not expired
    if cred.expiration and cred.expiration < datetime.datetime.utcnow():
        return False, None, "ABAC Credential expired"

    # Credential must pass xmlsec1 verify
    cred_file = write_to_tempfile(cred.save_to_string())
    xmlsec1_args = ['xmlsec1', '--verify', cred_file]
    output = run_subprocess(xmlsec1_args, stdout=None, stderr=subprocess.PIPE)
    os.unlink(cred_file)
    if output != 0:
        return False, None, "ABAC credentaial failed to xmlsec1 verify"

    # Must be ABAC
    if cred.get_cred_type() != 'geni_abac':
        return False, None, "Credential not of type ABAC"
    # Must say U.speaks_for(U)<-T
    if user_keyid != principal_keyid or \
            tool_keyid != subject_keyid or \
            role != ('speaks_for_%s' % user_keyid):
        return False, None, "ABAC statement doesn't assert U.speaks_for(U)<-T"

    # URN of signer from cert must match URN of 'speaking-for' argument
    if user_urn != speaking_for_urn:
        return False, None, "User URN doesn't match speaking_for URN"

    # User certificate must validate against trusted roots
    try:
        user_gid.verify_chain(trusted_roots)
    except Exception:
        return False, None, "User cert doesn't validate against trusted roots"

    # Tool certificate must validate against trusted roots
    try:
        tool_gid.verify_chain(trusted_roots)
    except Exception:
        return False, None, "Tool cert doesn't validate against trusted roots"

    return True, user_gid, ""

# Determine if this is a speaks-for context. If so, validate
# And return either the tool_cert (not speaks-for or not validated)
# or the user cert (validated speaks-for)
# credentials is a list of GENI-style credentials:
# Either a cred string xml string, or Credential object of a tuple
#    [{'geni_type' : geni_type, 'geni_value : cred_value, 
#      'geni_version' : version}]
# caller_gid is the raw X509 cert gid
# options is the dictionary of API-provided options
# trusted_roots is a list of Certificate objects from the system
#   trusted_root directory
def determine_speaks_for(credentials, caller_gid, options, \
                             trusted_roots):
    if 'geni_speaking_for' in options:
        speaking_for_urn = options['geni_speaking_for']
        for cred in credentials:
            if type(cred) == dict:
                if cred['geni_type'] != 'geni_abac': continue
                cred_value = cred['geni_value']
            elif isinstance(cred, Credential):
                if isinstance(cred, ABACCredential):
                    cred_value = cred.get_xml()
                else:
                    continue
            else:
                if cred.find('abac') < 0: continue
                cred_value = cred
            is_valid_speaks_for, user_gid, msg = \
                verify_speaks_for(cred_value,
                                  caller_gid, speaking_for_urn, \
                                      trusted_roots)
            if is_valid_speaks_for:
                return user_gid # speaks-for
    return caller_gid # Not speaks-for

def create_speaks_for(tool_gid, user_gid, ma_gid, \
                          user_key_file, cred_filename):
    tool_urn = tool_gid.get_urn()
    user_urn = user_gid.get_urn()

    header = '<?xml version="1.0" encoding="UTF-8"?>'
    reference = "ref0"
    signature_block = \
        '<signatures>\n' + \
        signature_template + \
        '</signatures>'
    template = header + '\n' + \
        '<signed-credential>\n' + \
        '<credential xml:id="%s">\n' + \
        '<type>abac</type>\n' + \
        '<serial/>\n' +\
        '<owner_gid/>\n' + \
        '<target_gid/>\n' + \
        '<uuid/>\n' + \
        '<expires>%s</expires>' +\
        '<abac>\n' + \
        '<rt0>\n' + \
        '<version>%s</version>\n' + \
        '<head>\n' + \
        '<ABACprincipal><keyid>%s</keyid></ABACprincipal>\n' +\
        '<role>speaks_for_%s</role>\n' + \
        '</head>\n' + \
        '<tail>\n' +\
        '<ABACprincipal><keyid>%s</keyid></ABACprincipal>\n' +\
        '</tail>\n' +\
        '</rt0>\n' + \
        '</abac>\n' + \
        '</credential>\n' + \
        signature_block + \
        '</signed-credential>\n'


    credential_duration = datetime.timedelta(days=365)
    expiration = datetime.datetime.now(du_tz.tzutc()) + credential_duration
    version = "1.1"

    user_keyid = get_cert_keyid(user_gid)
    tool_keyid = get_cert_keyid(tool_gid)
    unsigned_cred = template % (reference, expiration, version, \
                                    user_keyid, user_keyid, tool_keyid, \
                                    reference, reference)
    unsigned_cred_filename = write_to_tempfile(unsigned_cred)

    # Now sign the file with xmlsec1
    # xmlsec1 --sign --privkey-pem privkey.pem,cert.pem 
    # --output signed.xml tosign.xml
    pems = "%s,%s,%s" % (user_key_file, user_gid.get_filename(),
                         ma_gid.get_filename())
    cmd = ['xmlsec1',  '--sign',  '--privkey-pem', pems, 
           '--output', cred_filename, unsigned_cred_filename]

#    print " ".join(cmd)
    sign_proc_output = run_subprocess(cmd, stdout=subprocess.PIPE, stderr=None)
    if sign_proc_output == None:
        print "OUTPUT = %s" % sign_proc_output
    else:
        print "Created ABAC creadential %s speaks_for %s in file %s" % \
            (tool_urn, user_urn, cred_filename)
    os.unlink(unsigned_cred_filename)

# Test procedure
if __name__ == "__main__":

    parser = optparse.OptionParser()
    parser.add_option('--cred_file', 
                      help='Name of credential file')
    parser.add_option('--tool_cert_file', 
                      help='Name of file containing tool certificate')
    parser.add_option('--user_urn', 
                      help='URN of speaks-for user')
    parser.add_option('--user_cert_file', 
                      help="filename of x509 certificate of signing user")
    parser.add_option('--ma_cert_file', 
                      help="filename of x509 cert of MA that signed user cert")
    parser.add_option('--user_key_file', 
                      help="filename of private key of signing user")
    parser.add_option('--trusted_roots_directory', 
                      help='Directory of trusted root certs')
    parser.add_option('--create',
                      help="name of file of ABAC speaksfor cred to create")
                      
    options, args = parser.parse_args(sys.argv)

    tool_gid = GID(filename=options.tool_cert_file)

    if options.create:
        if options.user_cert_file and options.user_key_file \
            and options.ma_cert_file:
            user_gid = GID(filename=options.user_cert_file)
            ma_gid = GID(filename=options.ma_cert_file)
            create_speaks_for(tool_gid, user_gid, ma_gid, \
                                  options.user_key_file,  \
                                  options.create)
        else:
            print "Usage: --create cred_file " + \
                "--user_cert_file user_cert_file" + \
                " --user_key_file user_key_file --ma_cert_file ma_cert_file"
        sys.exit()

    user_urn = options.user_urn

    # Get list of trusted rootcerts
    trusted_roots_directory = options.trusted_roots_directory
    trusted_roots = \
        [Certificate(filename=os.path.join(trusted_roots_directory, file)) \
             for file in os.listdir(trusted_roots_directory) \
             if file.endswith('.pem') and file != 'CATedCACerts.pem']

    cred = CredentialFactory.createCred(credFile=options.cred_file)

    vsf, user_cert,msg = verify_speaks_for(cred, tool_gid, user_urn, \
                                trusted_roots)
    print 'VERIFY_SPEAKS_FOR = %s' % vsf
    creds = [{'geni_type' : 'geni_abac', 'geni_value' : cred, 
              'geni_version' : '1'}]
    gid = determine_speaks_for(creds, tool_gid, \
                                   {'geni_speaking_for' : user_urn}, \
                                   trusted_roots)
    print "CERT URN = %s" % gid.get_urn()

                                 



