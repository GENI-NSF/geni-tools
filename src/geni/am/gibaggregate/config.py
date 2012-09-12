# Configuration information used by multiple modules of the gibaggregate
#    package.

import sys
import logging
import os.path

logger = logging.getLogger('gcf.am2.gib')

# Find the name of the directory in which this script resides
gibDirectory = os.path.dirname(os.path.realpath(__file__))

# Files in the standardScrips subdirectory
standardScriptsDir = gibDirectory + '/standardScripts'
advertRspecFile = 'gib-advert.rspec'  # File containing the advertisement
                                      #     rspec for the aggregate
initAggregate = 'initAggregate.sh'    # shell script that initializes aggregate
deleteSliver = 'deleteSliver.sh'      # shell script that deletes sliver

# Files in the sliceSpecificScripts subdirectory
sliceSpecificScriptsDir = gibDirectory + '/sliceSpecificScripts'
manifestFile = 'gib-manifest.rspec'   # Slice manifest is written to this file
shellScriptFile = 'createSliver.sh'   # Shell script generated to create and
                                      #     configure the sliver

# Figure out the Linux distribution: Red Hat Fedora or Ubuntu
_version = open('/proc/version').read()
if _version.find('Ubuntu') != -1 :
    distro = 'UBUNTU10-STD'
elif _version.find('Red Hat') != -1 :
    distro = 'FEDORA15-STD'
else :
    _exitMsg = 'Running on an unsupported Linux distribution: %s' % _version 
    logger.error(_exitMsg)
    sys.exit(_exitMsg)

rootPwd = 'gib2012'     # No comment  :-)
