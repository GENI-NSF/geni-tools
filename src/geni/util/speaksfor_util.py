import datetime
from dateutil import parser as du_parser, tz as du_tz
import optparse
import os
import subprocess
import sys
import tempfile
import sfa.trust.certificate
from xml.dom.minidom import *

# Routine to validate that a speaks-for credential 
# says what it claims to say:
# It is a signed credential wherein the signer S is attesting to the
# ABAC statement:
# S.speaks_for(S)<-T
# Or "S says that T speaks for S"

# Simple XML helper functions

# Find the text associated with first child text node
def findTextChildValue(root):
    for child in root.childNodes:
        if child.nodeName == "#text":
            return str(child.nodeValue)
    return None

# Find first child with given name
def findChildNamed(root, name):
    for child in root.childNodes:
        if child.nodeName == name:
            return child
    return None

# Pull user URN from certificate object
def extract_urn_from_cert(cert):
    data = cert.get_data('subjectAltName')
    data_parts = data.split(', ')
    for data_part in data_parts:
        if data_part.startswith('URI:urn:publicid'):
            return data_part[4:]
    return None

# Write a string to a tempfile, returning name of tempfile
def write_to_tempfile(str):
    str_fd, str_file = tempfile.mkstemp()
    os.write(str_fd, str)
    os.close(str_fd)
    return str_file

# Get list of certs in given directory
def get_certs_in_directory(dir):
    files = os.listdir(dir)
    certs = [sfa.trust.certificate.Certificate(filename=os.path.join(dir, file)) \
                 for file in files]
    return certs

# Pull the keyid (sha1 hash of the bits of the cert public key) from given cert
def get_cert_keyid(cert):
    # Write cert to tempfile
    cert_file = write_to_tempfile(cert)

    # Pull the public key out as pem
    # openssl x509 -in cert.pem -pubkey -noout > key.pem
    cmd = ['openssl', 'x509', '-in', cert_file, '-pubkey', '-noout']
    pubkey_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    pubkey_proc.wait()
    pubkey = pubkey_proc.stdout.read()
    pubkey_fd, pubkey_file = tempfile.mkstemp()
    os.write(pubkey_fd, pubkey)
    os.close(pubkey_fd)
    
    # Pull out the bits
    # openssl asn1parse -in key.pem -strparse 18 -out key.der
    derkey_fd, derkey_file = tempfile.mkstemp()
    os.close(derkey_fd)
    cmd = ['openssl', 'asn1parse', '-in', pubkey_file, '-strparse', \
               '18', '-out', derkey_file]
    subprocess.call(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    

    # Get the hash
    # openssl sha1 key.der
    cmd = ['openssl', 'sha1', derkey_file]
    sha_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, 
                                stderr=subprocess.PIPE)
    sha_proc.wait()
    output = sha_proc.stdout.read()
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
def verify_speaks_for(cred, tool_cert, speaking_for_urn, \
                          trusted_roots):

    # Parse XML representation of credential
    cred_doc = parseString(cred)
    root = cred_doc.childNodes[0] # signedCredential

    # Extract signer cert from the credential
    cert_nodes = root.getElementsByTagName('X509Certificate')
    if len(cert_nodes) == 0:
        return False, None, "Invalid ABAC credential: No X509 cert"
    user_cert_text = findTextChildValue(cert_nodes[0])
    user_cert = \
        '-----BEGIN CERTIFICATE-----\n%s\n-----END CERTIFICATE-----\n' % \
        user_cert_text

    user_keyid = get_cert_keyid(user_cert)
    tool_keyid = get_cert_keyid(tool_cert)

    user_cert_object = sfa.trust.certificate.Certificate(string=user_cert)
    user_urn = extract_urn_from_cert(user_cert_object)

    head_elts = root.getElementsByTagName('head')
    if len(head_elts) != 1: 
        return False, None, "Invalid ABAC credential: No head element"
    head_elt = head_elts[0]

    principal_keyid_elts = head_elt.getElementsByTagName('keyid')
    if len(principal_keyid_elts) != 1: 
        return False, None, "Invalid ABAC credential: No head principal element"
    principal_keyid_elt = principal_keyid_elts[0]
    principal_keyid = findTextChildValue(principal_keyid_elt)

    role_elts = head_elt.getElementsByTagName('role')
    if len(role_elts) != 1: 
        return False, None, "Invalid ABAC credential: No role element"
    role = findTextChildValue(role_elts[0])

    tail_elts = root.getElementsByTagName('tail')
    if len(tail_elts) != 1: 
        return False, None, "Invalid ABAC credential: No tail element" 
    subject_keyid_elts = tail_elts[0].getElementsByTagName('keyid')
    if len(subject_keyid_elts) != 1: 
        return False, None, "Invalid ABAC credential: No tail subject element"
    subject_keyid = findTextChildValue(subject_keyid_elts[0])

    credential_elt = findChildNamed(root, 'credential')
    cred_type_elt = findChildNamed(credential_elt, 'type')
    cred_type = findTextChildValue(cred_type_elt)

    expiration = root.getElementsByTagName('expires')[0]
    expiration_value = expiration.childNodes[0].nodeValue
    expiration_time = du_parser.parse(expiration_value)
    current_time = datetime.datetime.now(du_tz.tzutc())

    # Now tests that this is a valid credential

    # Credential has not expired
    if expiration_time < current_time:
        return False, None, "ABAC Credential expired"

    # Credential must pass xmlsec1 verify
    cred_file = write_to_tempfile(cred)
    xmlsec1_args = ['xmlsec1', '--verify', cred_file]
    proc = subprocess.Popen(xmlsec1_args, stderr=subprocess.PIPE)
    proc.wait()
    output = proc.returncode
    os.unlink(cred_file)
    if output != 0:
        return False, None, "ABAC credentaial failed to xmlsec1 verify"

    # Must be ABAC
    if cred_type != 'abac':
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
        user_cert_object.verify_chain(trusted_roots)
    except Exception:
        return False, None, "User cert doesn't validaate against trusted roots"

    return True, user_cert, ""

# Determine if this is a speaks-for context. If so, validate
# And return either the tool_cert (not speaks-for or not validated)
# or the user cert (validated speaks-for)
# credentials is a list of GENI-style credentials:
#    [{'geni_type' : geni_type, 
#      'geni_value : cred_value, 
#      'geni_version' : version}]
# caller_cert is the raw X509 cert string
# options is the dictionary of API-provided options
# trusted_roots is a list of Certificate objects from the system
#   trusted_root directory
def determine_speaks_for(credentials, caller_cert, options, \
                             trusted_roots):
    if 'speaking_for' in options:
        speaking_for_urn = options['speaking_for']
        for cred in credentials:
            if type(cred) == 'dict':
                if cred['geni_type'] != 'geni_abac': continue
                cred_value = cred['geni_value']
            else:
                if cred.find('abac') < 0: continue
                cred_value = cred
            is_valid_speaks_for, user_cert, msg = \
                verify_speaks_for(cred_value,
                                  caller_cert, speaking_for_urn, \
                                      trusted_roots)
            if is_valid_speaks_for:
                return user_cert # speaks-for
    return caller_cert # Not speaks-for

# Test procedure
if __name__ == "__main__":

    parser = optparse.OptionParser()
    parser.add_option('--cred_file', 
                      help='Name of credential file')
    parser.add_option('--tool_cert_file', 
                      help='Name of file containing tool certificate')
    parser.add_option('--user_urn', 
                      help='URN of speaks-for user')
    parser.add_option('--trusted_roots_directory', 
                      help='Directory of trusted root certs')
    options, args = parser.parse_args(sys.argv)
    cred_file = options.cred_file
    tool_cert_file = options.tool_cert_file
    user_urn = options.user_urn
    trusted_roots_directory = options.trusted_roots_directory
    trusted_roots = [sfa.trust.certificate.Certificate(filename=os.path.join(trusted_roots_directory, file)) \
                         for file in os.listdir(trusted_roots_directory) \
                         if file.endswith('.pem') and file != 'CATedCACerts.pem']

    cred = open(cred_file).read()
    tool_cert = open(tool_cert_file).read()

    vsf, user_cert,msg = verify_speaks_for(cred, tool_cert, user_urn, \
                                trusted_roots)
    print 'VERIFY_SPEAKS_FOR = %s' % vsf
    if vsf:
        print "USER_CERT = %s" % user_cert

    creds = [{'geni_type' : 'geni_abac', 
              'geni_value' : cred, 
              'geni_version' : '1'}]
    cert = determine_speaks_for(creds, \
                                    tool_cert, \
                                    {'speaking_for' : user_urn}, \
                                    trusted_roots)
    print "CERT URN = %s" % extract_urn_from_cert(sfa.trust.certificate.Certificate(string=cert))

                                 



