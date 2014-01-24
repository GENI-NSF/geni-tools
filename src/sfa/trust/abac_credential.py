from sfa.trust.credential import Credential
from sfa.util.sfalogging import logger
from xml.dom.minidom import Document, parseString

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

    def get_head(self) : return self.head
    def get_tails(self) : return self.tails


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
        result = ""
        result += "Head: %s" % self.get_head() + "\n"
        for tail in self.get_tails():
            result += "Tail: %s" % tail
        return result

