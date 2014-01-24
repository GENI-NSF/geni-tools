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

from sfa.util.sfalogging import logger
from sfa.trust.credential import Credential
from sfa.trust.abac_credential import ABACCredential

# Factory for creating credentials of different sorts by type
class CredentialFactory:


    UNKNOWN_CREDENTIAL_TYPE = 'geni_unknown'

    # Static Credential class method to determine the type of a credential
    # string depending on its contents
    @staticmethod
    def getType(credString):
        credString_nowhitespace = credString.replace(" ", "")
        if credString_nowhitespace.find('<type>abac</type>') > -1:
            return ABACCredential.ABAC_CREDENTIAL_TYPE
        elif credString_nowhitespace.find('<type>privilege</type>') > -1:
            return Credential.SFA_CREDENTIAL_TYPE
        else:
            return CredentialFactory.UNKNOWN_CREDENTIAL_TYPE

    # Static Credential class method to create the appropriate credential
    # (SFA or ABAC) depending on its type
    @staticmethod
    def createCred(credString=None, credFile=None):
        if not credString and not credFile:
            raise Exception("CredentialFactory.createCred called with no argument")
        if credFile:
            try:
                credString = open(credFile).read()
            except:
                logger.info("Error opening credential file %s" % credFile)
                return None
        cred_type = CredentialFactory.getType(credString)
        if cred_type == Credential.SFA_CREDENTIAL_TYPE:
            return Credential(string=credString)
        elif cred_type == ABACCredential.ABAC_CREDENTIAL_TYPE:
            return ABACCredential(string=credString)
        else:
            raise Exception("Unknown credential type %s" % cred_type)

if __name__ == "__main__":
    c2 = open('/tmp/sfa.xml').read()
    cred1 = CredentialFactory.createCred(credFile='/tmp/cred.xml')
    cred2 = CredentialFactory.createCred(credString=c2)

    print "C1 = %s" % cred1
    print "C2 = %s" % cred2
    c1s = cred1.dump_string()
    print "C1 = %s" % c1s
#    print "C2 = %s" % cred2.dump_string()
