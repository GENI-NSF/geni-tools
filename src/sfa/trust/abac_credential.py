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

from sfa.trust.credential import Credential
from sfa.util.sfalogging import logger
from xml.dom.minidom import Document, parseString

# This module defines a subtype of sfa.trust,credential.Credential
# called an ABACCredential. An ABAC credential is a signed statement
# asserting a role representing the relationship between a subject and target
# or between a subject and a class of targets (all those satisfying a role).
#
# An ABAC credential is like a normal SFA credential in that it is has
# a validated signature block and is checked for expiration. 
# It does not, however, hove 'privileges'. Rather it contains a 'head' and
# list of 'tails' of elements, each of which repersents a principal and
# role.

# A special case of an ABAC credential is a speaks_for credential. Such
# a credential is simply an ABAC credential in form, but has a single 
# tail and fixed role speaks_for. In ABAC notiation, it asserts
# AGENT.speaks_for(AGENT)<-CLIENT, or "AGENT asserts that CLIENT may speak
# for AGENT". The AGENT in this case is the head and the CLIENT is the
# tail and 'speaks_for_AGENT' is the role on the head. These speaks-for
# Credentials are used to allow a tool to 'speak as' itself but be recognized
# as speaking for an individual and be authorized to the rights of that
# individual and not to the rights of the tool itself.

# For more detail on the semantics and syntax and expected usage patterns
# of ABAC credentials, see http://groups.geni.net/geni/wiki/TIEDABACCredential.

# 

# An ABAC element contains a principal (keyid and optional mnemonic)
# and optional role and linking_role element
class ABACElement:
    def __init__(self, principal_keyid, principal_mnemonic=None, \
                     role=None, linking_role=None):
        self._principal_keyid = principal_keyid
        self._principal_mnemonic = principal_mnemonic
        self._role = role
        self._linking_role = linking_role

    def get_principal_keyid(self): return self._principal_keyid
    def get_principal_mnemonic(self): return self._principal_mnemonic
    def get_role(self): return self._role
    def get_linking_role(self): return self._linking_role

    def __str__(self):
        return "%s %s %s %s" % (self._principal_keyid, self._principal_mnemonic, \
                                    self._role, self._linking_role)

# Subclass of Credential for handling ABAC credentials
# They have a different cred_type (geni_abac vs. geni_sfa)
# and they have a head and tail and role (as opposed to privileges)
class ABACCredential(Credential):

    ABAC_CREDENTIAL_TYPE = 'geni_abac'

    def __init__(self, create=False, subject=None, 
                 string=None, filename=None):
        self.head = None # An ABACElemenet
        self.tails = [] # List of ABACElement
        super(ABACCredential, self).__init__(create=create, 
                                             subject=subject, 
                                             string=string, 
                                             filename=filename)
        self.cred_type = ABACCredential.ABAC_CREDENTIAL_TYPE

    def get_head(self) : 
        if not self.head: 
            self.decode()
        return self.head

    def get_tails(self) : 
        if not self.tails:
            self.decode()
        return self.tails


    def decode(self):
        super(ABACCredential, self).decode()
        # Pull out the ABAC-specific info
        doc = parseString(self.xml)
        rt0_root = doc.getElementsByTagName('rt0')[0]
        heads = self._get_abac_elements(rt0_root, 'head')
        self.head = heads[0]
        self.tails = self._get_abac_elements(rt0_root, 'tail')

    def _get_abac_elements(self, root, label):
        abac_elements = []
        elements = root.getElementsByTagName(label)
        for elt in elements:
            keyid_elt = elt.getElementsByTagName('keyid')[0]
            keyid = keyid_elt.childNodes[0].nodeValue

            mnemonic = None
            mnemonic_elts = elt.getElementsByTagName('mnemonic')
            if len(mnemonic_elts) > 0:
                mnemonic = mnemonic_elts[0].childNodes[0].nodeValue

            role = None
            role_elts = elt.getElementsByTagName('role')
            if len(role_elts) > 0:
                role = role_elts[0].childNodes[0].nodeValue

            linking_role = None
            linking_role_elts = elt.getElementsByTagName('linking_role')
            if len(linking_role_elts) > 0:
                linking_role = linking_role_elts[0].childNodes[0].nodeValue

            abac_element = ABACElement(keyid, mnemonic, role, linking_role)
            abac_elements.append(abac_element)

        return abac_elements

    def dump_string(self, dump_parents=False, show_xml=False):
        result = "ABAC Credential\n"
        if self.expiration:
            result +=  "\texpiration: %s \n" % self.expiration.isoformat()

        result += "\tHead: %s\n" % self.get_head() 
        for tail in self.get_tails():
            result += "\tTail: %s\n" % tail
        return result

