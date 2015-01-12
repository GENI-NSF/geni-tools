#!/usr/bin/env python
#----------------------------------------------------------------------
# Copyright (c) 2011-2015 Raytheon BBN Technologies
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

""" The OMNI client
    This client is a GENI API client that is capable of connecting
    to multiple slice authorities (clearinghouses) for slice creation and deletion.
    See README-omni.txt

    Be sure to create an omni config file (typically ~/.gcf/omni_config)
    and supply valid paths to your per control framework user certs and keys.
    See gcf/omni_config.sample for an example, and src/omni-configure.py
    for a script to configure omni for you.

    Typical usage:
    omni.py sfa listresources
    
    The currently supported control frameworks (clearinghouse implementations)
    are SFA (i.e. PlanetLab), PG and GCF.

    Extending Omni to support additional frameworks with their own
    clearinghouse APIs requires adding a new Framework extension class.

    Return Values and Arguments of various omni commands:
      Aggregate functions:
       Most aggregate functions return 2 items: A string describing the result, and an object for tool use.
       In AM APIV3+ functions, that object is a dictionary by aggregate URL containing the full AM API v3+ return struct
       (code, value, output).
       [string dictionary] = omni.py getversion # dict is keyed by AM url
       [string dictionary] = omni.py listresources # dict is keyed by AM url,urn
       [string dictionary] = omni.py listresources SLICENAME # AM API V1&2 only; dict is keyed by AM url,urn
       [string dictionary] = omni.py describe SLICENAME # AM API V3+ only
       [string rspec] = omni.py createsliver SLICENAME RSPEC_FILENAME # AM API V1&2 only
       [string dictionary] = omni.py allocate SLICENAME RSPEC_FILENAME # AM API V3+ only
       [string dictionary] = omni.py provision SLICENAME # AM API V3+ only
       [string dictionary] = omni.py performoperationalaction SLICENAME ACTION # AM API V3+ only
       [string dictionary] = omni.py poa SLICENAME ACTION # AM API V3+ only; alias for performoperationalaction
       [string dictionary] = omni .py sliverstatus SLICENAME # AM API V1&2 only
       [string dictionary] = omni .py status SLICENAME # AM API V3+ only
       [string (successList of AM URLs, failList)] = omni.py renewsliver SLICENAME # AM API V1&2 only
       [string dictionary] = omni.py renew SLICENAME # AM API V3+ only
       [string (successList of AM URLs, failList)] = omni.py deletesliver SLICENAME # AM API V1&2 only
       [string dictionary] = omni.py delete SLICENAME # AM API V3+ only
       In AM API v1&2:
       [string (successList, failList)] = omni.py shutdown SLICENAME
       In AM API v3:
       [string dictionary] = omni.py shutdown SLICENAME
       [string dictionary] = omni.py update SLICENAME RSPEC_FILENAME # AM API V3+ only
       [string dictionary] = omni.py cancel SLICENAME # AM API V3+ only

       Non-AM API functions exported by aggregates, supported by Omni:
       From ProtoGENI/InstaGENI:
       [string dictionary] = omni.py createimage SLICENAME IMAGENAME [false] -u <SLIVER URN>
       [string dictionary] = omni.py snapshotimage SLICENAME IMAGENAME [false] -u <SLIVER URN> ; alias for createimage
       [string dictionary] = omni.py deleteimage IMAGEURN [CREATORURN]
       [string dictionary] = omni.py listimages [CREATORURN]


      Clearinghouse functions:
       [string dictionary] = omni.py get_ch_version # dict of CH specific version information
       [string dictionary urn->url] = omni.py listaggregates
       On success: [string sliceurnstring] = omni.py createslice SLICENAME
       On fail: [string None] = omni.py createslice SLICENAME
       [stringCred stringCred] = omni.py getslicecred SLICENAME
       On success: [string dateTimeRenewedTo] = omni.py renewslice SLICENAME
       On fail: [string None] = omni.py renewslice SLICENAME
       [string Boolean] = omni.py deleteslice SLICENAME
       [string listOfSliceURNs] = omni.py listslices USER
       [string listOfSliceURNs] = omni.py listmyslices USER
       [string listOfSSHPublicKeys] = omni.py listmykeys
       [string listOfSSHPublicKeys] = omni.py listkeys USER
       [string stringCred] = omni.py getusercred
       [string string] = omni.py print_slice_expiration SLICENAME
       [string dictionary AM URN->dict by sliver URN of silver info] = omni.py listslivers SLICENAME
       [string listOfMemberDictionaries (KEYS, URN, EMAIL, ROLE)] = omni.py listslicemembers SLICENAME
       [string Boolean] = omni.py addslicemember SLICENAME USER [ROLE]
       [string Boolean] = omni.py removeslicemember SLICENAME USER

      Other functions:
       [string dictionary] = omni.py nicknames # List aggregate and rspec nicknames    
       [string dictionary] = omni.py print_sliver_expirations SLICENAME
"""

# Explicitly import framework files so py2exe is happy
import gcf.omnilib.frameworks.framework_apg
import gcf.omnilib.frameworks.framework_base
import gcf.omnilib.frameworks.framework_gcf
import gcf.omnilib.frameworks.framework_gch
import gcf.omnilib.frameworks.framework_gib
import gcf.omnilib.frameworks.framework_of
import gcf.omnilib.frameworks.framework_pg
import gcf.omnilib.frameworks.framework_pgch
import gcf.omnilib.frameworks.framework_sfa
import gcf.omnilib.frameworks.framework_chapi

if __name__ == '__main__':
  import gcf.oscript
  import sys
  sys.exit(gcf.oscript.main())
