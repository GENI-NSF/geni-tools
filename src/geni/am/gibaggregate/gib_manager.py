
import logging
import os
import os.path
import subprocess
import re

import resources
import rspec_handler
import config

experimentHosts = {}    # Map of container names (e.g. 101) to corresponding
                        #    VMNode objects
experimentLinks = []    # List of links specified by the experimenter 
experimentNICs = {}     # Map of client supplied network interface names to
                        #    corresponding NIC objects

# GENI-in-a-box specific createSliver
def createSliver(slice_urn, requestRspec, users) :
    """
        Create a sliver on this aggregate.
    """
    config.logger.info("createSliver called")

    # Get the slice name.  This is the last part of the URN.  For example,
    #    the slice name in the URN urn:publicid:IDN+geni:gpo:gcf+slice+myslice
    #    is myslice.
    sliceName = re.split(r'[:\+]+', slice_urn)[-1]

    # Parse the request rspec
    rspec_handler.parseRequestRspec(requestRspec, experimentHosts,
                                    experimentLinks, experimentNICs)

    # Provision the sliver i.e. assign resource as specifed in the request rspec
    #    The sliver isn't created yet.  The shell commands used to create
    #    the sliver are written into the file named in config.py
    resources.provisionSliver(experimentHosts, experimentLinks, experimentNICs,
                              users)

    # Generate the manifest rspec.  The manifest is written to the file named
    #    in config.py
    (rspec_handler.GeniManifest(sliceName, requestRspec, experimentHosts, 
                                experimentLinks, experimentNICs)).create()

    # Add commands to the bash script that create special files/directories
    #    in the containers.  They contain slice configuration information
    #    such as manifest rspec, slice name, etc.
    resources.specialFiles(sliceName, experimentHosts)

    ## Execute the shell script that create a new sliver
    pathToFile = config.sliceSpecificScriptsDir + '/' + config.shellScriptFile
    command = 'echo \"%s\" | sudo -S %s' % (config.rootPwd, pathToFile)
    print command
    # os.system(command)


def deleteSliver() :
    """
       Delete the sliver created on this aggregate.
    """
    config.logger.info("createSliver called")

    # Invoke the deleteSliver script in the standardScipts directory
    pathToFile = config.standardScriptsDir + '/' + config.deleteSliver
    command = 'echo \"%s\" | sudo -S %s' % (config.rootPwd, pathToFile)
    print command
    os.system(command)

    # Delete the file containing the manifest rspec
    pathToFile = config.sliceSpecificScriptsDir + '/' + config.manifestFile
    os.remove(pathToFile)
    

def get_manifest() :
    """
        Return the manifest rspec for the current slice.  The manifest
        is in a file created by rspec_handler.GeniManifest.
    """
    pathToFile = config.sliceSpecificScriptsDir + '/' + config.manifestFile
    config.logger.info('Reading manifest from %s' % pathToFile)
    try:
        f = open(pathToFile, 'r')
    except IOError:
        config.logger.error("Failed to open manifest rspec file %s" % 
                            pathToFile)
        return None

    manifest = f.read()
    f.close()
    return manifest


def get_advert() :
    """
         Return the advertisement rspect for this aggregate.  Get this manifest
         from a pre-created, static file.
    """
    pathToFile = config.standardScriptsDir + '/' +  config.advertRspecFile
    config.logger.info('Reading advert rspec from %s' % pathToFile)
    try:
        f = open(pathToFile, 'r')
    except IOError:
        config.logger.error("Failed to open advertisement rspec file %s" %
                             pathToFile)
        return None

    advert = f.read()
    f.close()

    return advert
    
