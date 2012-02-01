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

import inspect
import logging
from lxml import etree as ElementTree ##lxml instead
import os
import random
import re
import string
import threading
import time

import omni

from defs import *
import exception
import request
import rspec
#from rspec import AdRSpec

#   @param elemText - String as from the an element tree
#   @return String without enclosing whitespace or double-quote marks
def strifyEle(elemText):
    '''Return a string stripping enclosing whitespace or double-quote marks'''
    if elemText is None:
        return ""
    return str(elemText).strip('\n\r\t "')


## Tries to extract URN and URL from the given RSpec string using the 
# regular expression for parsing the XML comment at the top.
#     
#   @param rspecStr - XML String content of RSpec file
#   @return A dictionary containing information about the aggregate in the 
#   filehandle of the format {urn,url}. If no information is found, return 
#   False.
#
def stripHint(rspecStr): 

    result = re.search(rspecHintRegex,rspecStr)

    if result and result.group and result.groups>1:
        urn = result.group(1).strip()
        url = result.group(2).strip()
        return {"urn":urn, "url":url}
    return False


## Attempt to find the version of the given RSpec string
#     
#   @param rspecStr - XML String content of RSpec file
#   @param logger - The logger object to log output to
#   @return a string rspec type if found, None if not 
#
def findRSpecFormat(rspecStr, logger): 

    et = ElementTree.fromstring(rspecStr)

    #Is it a Geni V3 Request?
    if isGENIV3(et,logger):
        return 'geniv3'

    #Is it a Protogeni V2 Request?
    if isPGV2(et,logger):
        return 'pgv2'

    #Is it a MAX Request?
    if isMax(et,logger):

        #Special case because ION is a weird one. Hardcoded, hope we can kill
        #it altogether
        # Parse the 'resources at AM' XML comment
        # from the RSpec to get the URN/URL
        hints = stripHint(rspecStr)
        # Then compare that URL with the hard-coded ION URL below
        # FIXME: ugly hack here!
        if hints['url'] == getKnownAggregateData()['max']['aggregates'][1]['aggrURL']:
            return 'ion'

        return 'max'
   
    logger.error("Unable to detect rspec format")
    return None 


## Converts a string list of vlan integers to a list of explicit integers. 
# Converts a string such as: "3,4,7,8,5-15,7,40" i
# to [3,4,5,6,7,8,9,10,11,12,13,14,15,40]
#     
#   @param tmp - string vlan list 
#   @return A list of all integers described in the string
#
def vlanRangeToList(tmp):
    if tmp == "any" or tmp == "*":
        return ["*"]
    comSep = tmp.split(",")
    tmp = []
    for i in comSep:
        if '-' in i:
            rng = i.split("-")
            tmp.append(i)
            comSep.extend([str(j) for j in range(int(rng[0]),int(rng[1])+1)])
    for j in tmp:
        comSep.remove(j)

    comSep = list(set(comSep))
    comSep= [int(x) for x in comSep]
    comSep.sort()
    return comSep


## Determines whether or not a list of vlans is a subset of another. 
#     
#   @param subset - a list of strings/ints
#   @param mainset - a list of strings/ints
#   @return True if subset is a subset of mainset, False otherwise 
#
def vlanListIsSubsetOf(subset, mainset):
    if "*" in mainset:
        return True
    if "*" in subset:
        return False
    if set(subset).issubset(set(mainset)):
        return True
    return False


## Finds the intersection of two vlan lists. 
#     
#   @param listone - a list of strings/ints
#   @param listtwo - a list of strings/ints
#   @return a list corresponding with the intersection of the two sets 
#
def vlanListIntersection(listone, listtwo):
    if "*" in listone:
        return listtwo
    if "*" in listtwo:
        return listone
    inter = list(set(listone) & set(listtwo))
    inter.sort()
    return inter


## Determines which order a list of Aggregates should be contacted in so that 
# each RSpec is satisfied. This function uses pre-computed dependencies between 
# ReqRSpecs to determine a safe ordering. Does not guarantee a consistent 
# ordering between unrelated ReqRSpecs. 
#     
#   @param session - A reference to the session config object 
#   @return an ordered list of ReqRSpecs which corresponds with a safe sequence
#
def calculateExecuteSequence(session):
   
    seq = []
    # aggr is ReqRSpec
    for aggr in session.getAggregateList():
        if aggr not in seq:
            calculateSubSeq(aggr,seq)

    return seq 


## Recursive helper for calculateExecuteSequence 
#     
#   @param aggr - A ReqRSpec object
#   @param seq - An ordered list of ReqRSpecs which corresponds with a safe
#   sequence computed thus far. 
#
def calculateSubSeq(aggr, seq):
 
    if len(aggr.dependsOn)>0:
        for dep in aggr.dependsOn:
            if dep not in seq:
                calculateSubSeq(dep,seq)
    seq.append(aggr)


## 'Execute' a list of ReqRSpecs based on the order of the list. 
# This function executes in sequence, but double-checks at each execution
# that dependencies (if any) of the current ReqRSpec have been satisfied.
# It also pulls any new data assigned to dependencies by their aggregates into
# ths current ReqRSpec if required. eg. Vlan Tags
#
#   @param seq - An ordered list of ReqRSpecs which corresponds with a safe 
#   sequence 
#   @param options - Options for omni
#   @param logger - The logger object to log output to
#   @param pause - Boolean value, True if you want execution to pause when data
#   is being added to an Rspec automatically
#   @param real - Boolean value, True if you want to actually send rspecs off. 
#   False if you want to use the 'fake' response functions
#   @return A dictionary of interfaces->urns that were assigned during execution
#
def executeInSequence(seq, options, logger, pause=False, real=False):

    return_val = False
    assigned_vlans = {}

    for reqRSpec in seq:
        logger.info("Executing RSpec for: "+reqRSpec.aggrURL)
        
        vlan_map = {}
        #We can assume all dependencies have been finished already
        for dep in reqRSpec.dependsOn:
            if dep.completed:
                dep.manRSpec.collectInfo()
                vlan_map.update(dep.manRSpec.definedVlans)

            else:
                logger.error("%s: One of my dependencies (%s) was not complete! Undefined behaviour!", reqRSpec.aggrURL, dep.aggrURL)
                return None
        
        reqRSpec.insertVlanData(vlan_map)
        
        if len(reqRSpec.dependsOn)>0 and pause:
            pauseForInput() 

        return_val = executeReqRSpec(reqRSpec,options,logger,real)

        if reqRSpec.manRSpec is None or not return_val:
            logger.error("Failed submitting RSpec to: "+reqRSpec.aggrURL)
            return None

        assigned_vlans[reqRSpec.aggrURL] = reqRSpec.manRSpec.definedVlans
        reqRSpec.completed = True

    return assigned_vlans


## 'Execute' a list of ReqRSpecs in parallel where possible 
# This function executes the sequence in reverse, parallelizing where applicable
# and double-checks at each execution that dependencies (if any) of the current
# ReqRSpec have been satisfied. It also pulls any new data assigned to 
# dependencies by their aggregates into the current ReqRSpec if required. 
# eg. Vlan Tags
#
#   @param seq - An ordered list of ReqRSpecs which corresponds with a safe
#   sequence 
#   @param options - Options for omni
#   @param logger - The logger object to log output to
#   @param real - Boolean value, True if you want to actually send rspecs off.
#   False if you want to use the 'fake' response functions
#   @return A dictionary of interfaces->urns that were assigned during execution
#
def executeInParallel(seq, options, logger, real=False):

    return_val = False
    assigned_vlans = {}
    #logger.debug("Got a sequence of length %d", len(seq))
    for reqRSpec in reversed(seq): 
        #logger.debug("execPar doing req %s", reqRSpec.aggrURL)
        success = executeNode(reqRSpec,options,logger,real)
        if not success:
            logger.error("Abandoning execution")
            return None
        #logger.debug("execPar done for req %s of type %s with man of type %s", reqRSpec.aggrURL, reqRSpec.rspecType, reqRSpec.manRSpec.rspecType)
        assigned_vlans[reqRSpec.aggrURL] = reqRSpec.manRSpec.definedVlans
        reqRSpec.manRSpec.collectInfo()
        reqRSpec.completed = True
    return assigned_vlans
 

## Helper function for executeInParallel
#
#   @param rspec - ReqRSpec object to take care of
#   @param options - Options for omni
#   @param logger - The logger object to log output to
#   @param real - Boolean value, True if you want to actually send rspecs off. 
#   False if you want to use the 'fake' response functions
#   @return A dictionary of interfaces->urns that were assigned during execution
#
def executeNode(rspec, options, logger, real=False):

    if rspec.completed:
        #logger.debug("Already did request to %s", rspec.aggrURL)
        return True
    elif rspec.started:
        logger.warn("Dont restart request %s", rspec.aggrURL)
        return True

    myReady = threading.Semaphore()
    rspecReq = request.RequestThread(rspec,myReady,1,options,logger,real)
    rspecReq.start()
    myReady.acquire()

    if rspec.manRSpec is None:
        logger.error("Failed submitting RSpec to: "+rspec.aggrURL)
        return False

#    logger.info("Done sequence item for req %s type %s with man type %s", rspec.aggrURL, rspec.rspecType, rspec.manRSpec.rspecType)
    logger.info("Done sequence item for request to %s", rspec.aggrURL)

    return True


## 'Execute' a single ReqRSpec. 
# This function writes out the given ReqRSpec dom to a tmp file and submits it
# to the
# aggregate by delegating to the correct Request function.
#
#   @param rspec - A ReqRSpec object to be executed
#   @param options - Options for omni
#   @param logger - The logger object to log output to
#   @param real - Boolean value, True if you want to actually send rspecs off.
#   False if you want to use the 'fake' response functions
#   @return True if got a properly formatted reponse, otherwise False
#
def executeReqRSpec(rspec, options, logger, real=False):
   
    if rspec.started:
        logger.warning("Do not restart submitting Request RSpec to %s", rspec.aggrURL)
        return True
    rspec.started = True

    file_prefix = randomASCIIStr(tmpfile_strlen)
    tmp_filename = file_prefix+"."+tmpfile_extension
   
    logger.debug("Creating request rspec for %s in temp file %s", rspec.aggrURL,tmp_filename)
   
    return_val = False
    with open(tmp_filename, mode='w') as rspec_file:
        rspec_file.write(rspec.toRSpec())

    logger.info("Sending "+rspec.rspecType+" format RSpec to "+rspec.aggrURL)
    ##Note: If you are confused about why this prints 'max' for the ion
    # aggregate, see 'IonReqRSpec special case' note in the README under
    # developer notes

    if real:
        return_val = rspec.doRequest(tmp_filename,options)
    else:
        logger.info("Faking it...")
        time.sleep(random.randint(1,2))
        return_val = rspec.doFakeRequest(tmp_filename,options)

    if return_val:
        try:
            logger.info("Removing %s temp file %s"%(rspec.aggrURL, tmp_filename))
            os.unlink(tmp_filename)
        except Exception as err:
            logger.warn("Couldn't remove tmpfile %s: "+str(err), tmp_filename)

    logger.info("RSpec submission complete to %s", rspec.aggrURL)

    return return_val


## Generate a string of length 'strlen' which consists of random lower/uppercase
# ascii characters. The string is used often for a tmp filename.
#
#   @param strlen - Integer length of desired random string
#   @return A string of length strlen which consists of random ascii chars
#
def randomASCIIStr(strlen):
    filename = ""
    for attempt in range(strlen):
        filename += random.choice(string.ascii_letters)
    return filename


## Generate a shell script containing variables to be used for other shell
# scripts associated with a single Node.
#
#   @param outputFolder - A string foldername to write the script into
#   @param node - A dictionary containing information about a single node
#   @param session - A reference to the session config object 
#   @return The name of the script that was created if successful, 
#   False otherwise.
#
def generateVarScript(outputFolder, node, session):

    scriptStr = "#!/bin/bash\n"
    scriptFH = None
    
    scriptStr+= "STITCH_HOSTNAME="+node['hostname']+"\n"
    scriptStr+= "STITCH_USERNAME="+node['username']+"\n"
    scriptStr+= "STITCH_KEYFILE="+session.getUserKeyFile()+"\n"
    scriptStr+= "STITCH_INTIP="+node['int_ip']+"\n"

    scriptName = os.path.join(outputFolder,"vars_"+node['hostname']+".sh")
    try:
        scriptFH = open(scriptName,"w")
        scriptFH.write(scriptStr)
        scriptFH.close()
    except Exception as e:
        session.logger.error("Unable to create var script %s for: "+node['hostname']+" :"+str(e), scriptName)
        return False

    return scriptName


## Generate a shell script for easy login to single Node.
# Uses a template script, copies it and uses a regex to insert information
#
#   @param outputFolder - A string foldername to write the script into
#   @param varScript - A string filename of a variable script
#   @param node - A dictionary containing information about a single node
#   @return The name of the script that was created if successful,
#   False otherwise.
#
def generateLoginScript(outputFolder, varScript, node):
 
    templateFH = None
    templateStr = ""
    templateFN = ""
    try:
        ##Find the path of this module
        mod = inspect.getmodule(generateLoginScript)
        path = os.path.dirname(mod.__file__)
        templateFN = os.path.join(os.path.join(os.path.join(path, ".."), templates_dir), template_login_script)
        templateFH = open(templateFN,'r')
        templateStr = templateFH.read()
        templateFH.close()
    except:
        logger.error("Couldn't find and read template script file %s", templateFN, exc_info=True)
        return False

    scriptStr = templateStr
    scriptFH = None

    tmp = re.sub(re.compile(template_source_regex,re.DOTALL),"\\1"+"source "+varScript+"\\3",scriptStr)
    if scriptStr == tmp:
        logger.error("unable to create login script for: "+node['hostname'])
        return False
    else:
        scriptStr = tmp

    scriptName = os.path.join(outputFolder,"login_"+node['hostname']+".sh")
    try:
        scriptFH = open(scriptName,"w")
        scriptFH.write(scriptStr)
        scriptFH.close()
        os.system("chmod +x "+scriptName) #hacky I know
    except Exception as e:
        logger.error("Unable to create/write login script %s for: "+node['hostname']+" :"+str(e), scriptName)
        return False

    return scriptName


## Generate a shell script for easy setup of single Node.
# Uses a template script, copies it and uses a regex to insert information
#
#   @param outputFolder - A string foldername to write the script into
#   @param varScript - A string filename of a variable script
#   @param node - A dictionary containing information about a single node
#   @return The name of the script that was created if successful,
#   False otherwise.
#
def generateSetupScript(outputFolder, varScript, node):
 
    templateFH = None
    templateFN = ""
    templateStr = ""
    try:
        ##Find the path of this module
        mod = inspect.getmodule(generateSetupScript)
        path = os.path.dirname(mod.__file__)
        templateFN = os.path.join(os.path.join(os.path.join(path, ".."), templates_dir), template_setup_script)
        templateFH = open(templateFN,'r')
        templateStr = templateFH.read()
        templateFH.close()
    except:
        logger.error("Couldn't find and read template script file %s", templateFN, exc_info=True)
        return False

    scriptStr = templateStr
    scriptFH = None
    
    tmp = re.sub(re.compile(template_source_regex,re.DOTALL),"\\1"+"source "+varScript+"\\3",scriptStr)
    if scriptStr == tmp:
        logger.error("Unable to create setup script for: "+node['hostname'])
        return False
    else:
        scriptStr = tmp

    scriptName = os.path.join(outputFolder,"setup_"+node['hostname']+".sh")
    try:
        scriptFH = open(scriptName,"w")
        scriptFH.write(scriptStr)
        scriptFH.close()
        os.system("chmod +x "+scriptName)#hacky I know
    except:
        logger.error("Unable to create setup script %s for: "+node['hostname'], scriptName, exc_info=True)
        return False

    #print "Created setup script: "+scriptName
    return scriptName


## Stop execution and prompt the user to hit a key to continue.
# Used for demos to allow people to see what is happening.
#
def pauseForInput():
    raw_input("Press return to continue...")


## Collect information from the omni_config file
#
#   @param options - The options dictionary from the omni parser
#   @param logger - The logger object to log output to
#   @return - A tuple containing (username,keyfile,sitename) extracted from omni config
#
def getOmniConf(options, logger):

    #Sneaky hack to get at user information FIXME
    omni_logger = omni.configure_logging(options)
    config = omni.load_config(options,omni_logger)

    if not config.has_key('users') or len(config['users'])<1:
        logger.error("No user information found")
        return None

    if len(config['users']) > 1:
        logger.warn("Found %d users in config, taking first", len(config['users']))

    user = config['users'][0] ##Just take the first one #FIXME
        
    if not user.has_key('urn') or not user.has_key('keys'):
        logger.error("Incomplete user information found")
        return None

    keys = user['keys'].split(",")

    if len(keys)<1:
        logger.error("No user keys found")
        return None

    if len(keys) > 1:
        logger.warn("Found %d login keys, taking first", len(keys))

    key = keys[0] #Use the first key #FIXME
    user_name = user['urn'][user['urn'].rfind("+"):].strip("+ ") 
    #Take the username off the URN

    if len(user_name)<1:
        logger.error("Unable to find username")
        return None
    site_name = getSiteNamePrefix(config, logger)
    logger.info("Found username "+user_name+" and keyfile: "+key+" and sitenamePrefix: " + site_name + " in omni_config")

    return (user_name,key, site_name)


## Determines whether the given elementtree document is in Protogeni V2 format
#
#   @param et - elementtree document 
#   @param logger - The logging object to log output to
#   @return True if et is in Protogeni V2 format, False otherwise 
#
def isPGV2(et, logger):

    elemList = list(et.iter())
    if elemList < 1:
        logger.info("No elements found")
        return False

    tag = str(elemList[0].tag)
    if '{' not in tag or '}' not in tag:
        logger.info("Missing namespace prefix - looked in tag " + tag)
        return False

    namespaceStr = ""
    try:
        namespaceStr = tag[1:tag.rfind('}')]
    except:
        logger.info("Missing namespace prefix from tag " + tag)
        return False

    domains = getKnownAggregateData()

    if domains['pgv2']['namespace'] != namespaceStr:
        #logger.debug("The extracted namespace did not match the one I needed: %s != %s", namespaceStr, domains['pgv2']['namespace'])
        return False

#    typeStr = strifyEle(elemList[0].get('type'))
#    if typeStr is None or typeStr != 'request':
#        logger.debug("This rspec is not a Request type: %s", typeStr)
#        return False

    return True


## Determines whether the given elementtree document is in Geni V3 format
#
#   @param et - elementtree document
#   @param logger - The logging object to log output to
#   @return True if et is in Geni V3 format, False otherwise
#
def isGENIV3(et, logger):

    elemList = list(et.iter())
    if elemList < 1:
        #logger.info("No elements found")
        return False

    tag = str(elemList[0].tag)
    if '{' not in tag or '}' not in tag:
        #logger.info("Missing namespace prefix - looked in tag " + tag)
        return False

    namespaceStr = ""
    try:
        namespaceStr = tag[1:tag.rfind('}')]
    except:
        #logger.info("Missing namespace prefix from tag " + tag)
        return False

    domains = getKnownAggregateData()

    if domains['geniv3']['namespace'] != namespaceStr:
        #logger.debug("The extracted namespace did not match the one I needed: %s != %s", namespaceStr, domains['geniv3']['namespace'])
        return False

    typeStr = strifyEle(elemList[0].get('type'))
    if typeStr is None or typeStr != 'request':
        #logger.debug("This rspec is not a Request type: %s", typeStr)
        return False

    return True


## Determines whether the given elementtree document is in Max native format
#
#   @param et - elementtree document 
#   @param logger - The logging object to log output to
#   @return True if et is in Max native V2 format, False otherwise 
#
def isMax(et, logger):

    elemList = list(et.iter())
    if elemList < 1:
        #logger.info("No elements found")
        return False

    # Elem0 is RSpec type="SFA"
    # Elem1 is rspec id="foo" xmlns="something", so tag="{namespace}rspec"
    tag = ""
    try:
        tag = str(elemList[1].tag)
    except:
        logger.info("No rspec tag found in " + tag)
        return False

    if '{' not in tag or '}' not in tag:
        l ogger.info("Missing namespace prefix in " + tag)
        return False

    namespaceStr = ""
    try:
        namespaceStr = tag[1:tag.rfind('}')]
    except:
        logger.info("Missing namespace prefix in " + tag)
        return False

    domains = getKnownAggregateData()
    
    if domains['max']['namespace'] != namespaceStr:
        logger.info("Not MAX: The extracted namespace did not match the one I needed: %s != %s", namespaceStr, domains['max']['namespace'])
        return False

    return True


## Gets a list of Advertisement RSspec objects collected from what it finds in
# the cache folder. Parses the XML, producing the set of presetRoutes as listed
# in the stitching element of the RSpec
#     
#   @param logger - The logger object to log output to
#   @return A list of AdRSpec objects
#
def getCachedAdvertisements(logger):
   
    logger.info("Collecting all known Advertisements")


    # Find the directory with cached Advertisements
    # FIXME: Use this as the default, but accept a path on the commandline
    ##Find the path of this module
    mod = inspect.getmodule(getCachedAdvertisements)
    path = os.path.dirname(mod.__file__)
    cachepath = path+"/../"+cache_dir

    adFileNames = []
    try:
        adFileNames = os.listdir(cachepath)
    except:
        logger.error("Unable to find cache directory %s", cachepath, exc_info=True)
        return None

    adverts = []

    if len(adFileNames)<1:
        logger.error("No advertisements in cache directory %s", cachepath)
        return None

    for adfileName in adFileNames:
        fullAdPath = os.path.join(cachepath, adfileName)
        if not os.path.isfile(fullAdPath):
            continue

        ##Get the cached advert rspec
        adStr = ""
        try:
            fh = open(fullAdPath)
            adStr = fh.read()
            fh.close()
        except:
            raise exception.TopologyCalculationException("Trouble accessing file %s in cache", fullAdPath, exc_info=True)

        # Initialize the AdRSpec object - which parses the XML and
        # produces a set of presetroutes: link and remotelink URN pairs as listed
        # in the stitching element in the various nodes
        adverts.append(rspec.AdRSpec(adStr,logger))

    if len(adverts) < 1:
        logger.error("No advertisements in cache directory %s", cachepath)
        return None

    return adverts


## Generates the topology and adjacency data based on all available
# advertisements RSpecs.
#
# Parse all the cached Ad Rspecs, collecting the preset routes (links)
# defined within the stitching element in each.
# Aggregates are adjacent if they both define a route that connects them.
# Note this depends on exact string matches on interface URNs.
#
#   @param logger - The logging object to log output to
#   @return A tuple of  (presetRoutes, aggrAdjMap)
#       Where:  - presetRoutes defines which interfaces connect between 
#                 aggregates
#               - aggrAdjMap contains info describing which aggregates are
#                 adjacent to each other
#
#
# TODO: Re-implement supporting querying aggregates for advertisment
# RSpecs, or querying a service that supplies this data.
def getTopologyData(logger):

    aggrAdjMap = {}
    presetRoutes = {}

    logger.info("Learning topology")
    # Read cached Ad RSpecs in the local cache dir,
    # filling out a presetRoutes hash, parsing the link/remotelink pairs
    # from all the nodes in the stitching element
    adverts = getCachedAdvertisements(logger)

    if adverts is None:
        logger.error("Unable to get cached advertisements")
        return (None,None)

    for advert in adverts:
        presetRoutes.update(advert.getRoutes())

    # Find which aggregates are adjacent
    # Aggregates are adjacent if they BOTH define a route that connects them
    # Note this depends on exact string matches on interface URNs.
    # Warn if there is a mismatch: 2 ads that don't both define the same route.
    for aggr_url,iface_dict in presetRoutes.iteritems():
        for link_id,remote_id in iface_dict.iteritems():

            for aggr_url_inner,iface_dict_inner in presetRoutes.iteritems():
                if aggr_url==aggr_url_inner:
                    continue

                if iface_dict_inner.has_key(remote_id) and iface_dict_inner[remote_id]==link_id:
                    # A useful debug printout, but too verbose for most users:
                    #logger.debug("%s has route %s=%s and AM %s has the inverse", aggr_url, link_id, remote_id, aggr_url_inner)
                    if not aggrAdjMap.has_key(aggr_url):
                        aggrAdjMap[aggr_url] = []
                    if not aggr_url_inner in aggrAdjMap[aggr_url]:
                        logger.debug("AM %s has %s adjacent", aggr_url, aggr_url_inner)

                        aggrAdjMap[aggr_url].append(aggr_url_inner)
                    #aggrAdjMap[aggr_url] = list(set(aggrAdjMap[aggr_url]))
                else:
                    if iface_dict_inner.has_key(remote_id):
                        logger.warn("%s has route %s=%s BUT AM %s says %s = diff %s", aggr_url, link_id, remote_id, aggr_url_inner, remote_id, iface_dict_inner[remote_id])
                    if link_id in iface_dict_inner.values():
                        for key in iface_dict_inner.keys():
                            if iface_dict_inner[key] == link_id:
                                logger.warn("%s has route %s=%s BUT AM %s says a diff %s = %s", aggr_url, link_id, remote_id, aggr_url_inner, key, link_id)
                                break

    #Tells us which interfaces are attached
    '''
    presetRoutes2 = {
        rspecInfo['pgv2']['aggregates'][0]['aggrURL']:{ #Utah
            'urn:publicid:IDN+emulab.net+interface+*:*':None,
            'urn:publicid:IDN+emulab.net+interface+procurve-pgeni-salt:*':None,
            'urn:publicid:IDN+emulab.net+interface+procurve-pgeni-salt:eth0:ion':'urn:ogf:network:domain=ion.internet2.edu:node=rtr.salt:port=ge-7/1/2:link=*'
        },
        rspecInfo['pgv2']['aggregates'][1]['aggrURL']:{ #Kentucky
            'urn:publicid:IDN+uky.emulab.net+interface+*:*':None,
            'urn:publicid:IDN+uky.emulab.net+interface+cisco1:*':None, 
            'urn:publicid:IDN+uky.emulab.net+interface+cisco1-12:*':None, 
            'urn:publicid:IDN+uky.emulab.net+interface+cisco1-12:ion':None,
            'urn:publicid:IDN+uky.emulab.net+interface+cisco1:eth0:ion':'urn:ogf:network:domain=ion.internet2.edu:node=rtr.atla:port=xe-0/1/1:link=*'
        },
        rspecInfo['ion']['aggregates'][0]['aggrURL']:{ #Ion
            'urn:ogf:network:domain=ion.internet2.edu:node=rtr.salt:port=ge-7/1/2:link=*':'urn:publicid:IDN+emulab.net+interface+procurve-pgeni-salt:eth0:ion',
            'urn:ogf:network:domain=ion.internet2.edu:node=rtr.atla:port=xe-0/1/1:link=*':'urn:publicid:IDN+uky.emulab.net+interface+cisco1:eth0:ion',
            'urn:ogf:network:domain=ion.internet2.edu:node=rtr.newy:port=xe-0/0/3:link=*':'urn:ogf:network:domain=dragon.maxgigapop.net:node=CLPK:port=1-2-3:link=*'
        },
        rspecInfo['max']['aggregates'][0]['aggrURL']:{ #Max
            'urn:ogf:network:domain=dragon.maxgigapop.net:node=CLPK:port=1-2-3:link=*':'urn:ogf:network:domain=ion.internet2.edu:node=rtr.newy:port=xe-0/0/3:link=*',
            'urn:publicid:IDN+dragon.maxgigapop.net+interface+clpk:1/2/3:*':None,
            'urn:publicid:IDN+dragon.maxgigapop.net+interface+clpk:(null):*':None,
            'urn:publicid:IDN+dragon.maxgigapop.net+interface+planetlab2:eth1':None
        }
    }


    #Tells us which aggregates are next to each other
    aggrAdjMap2 = { rspecInfo['ion']['aggregates'][0]['aggrURL']:[
                        rspecInfo['max']['aggregates'][0]['aggrURL'],
                        rspecInfo['pgv2']['aggregates'][0]['aggrURL'],
                        rspecInfo['pgv2']['aggregates'][1]['aggrURL']
                    ], #Ion
                    rspecInfo['max']['aggregates'][0]['aggrURL']:[
                        rspecInfo['ion']['aggregates'][0]['aggrURL']
                    ], #Max
                    rspecInfo['pgv2']['aggregates'][0]['aggrURL']:[
                        rspecInfo['ion']['aggregates'][0]['aggrURL']
                    ], #Utah
                    rspecInfo['pgv2']['aggregates'][1]['aggrURL']:[
                        rspecInfo['ion']['aggregates'][0]['aggrURL']
                    ] #Kentucky
    }'''


    return (presetRoutes,aggrAdjMap)


## Gets information regarding namespaces, which aggregates we know about and 
# which formats they support.
#
#   @return A dictionary of type to dict(namespec, ext_namespaces, aggregates}
#
#       Note: see code for structure of dictionary
#
#  FIXME: Derive namespaces, schemas from XML, and find URL in XML
# Or maybe get some of this from getVersion.
#
def getKnownAggregateData():
    #Maps aggregate to other stuff
    rspecInfo = {
        'max':{'namespace':'http://geni.maxgigapop.net/aggregate/rspec/20100412/',
            'ext_namespaces':{
                'ctrlplane':'http://ogf.org/schema/network/topology/ctrlPlane/20080828/'
                },
            'aggregates':[
                {'name':'geni.maxgigapop.net',
                'aggrURL':'http://max-myplc.dragon.maxgigapop.net:12346'
                },
                {'name':'ion.internet2.edu',
                'aggrURL':'http://alpha.east.isi.edu:12346',
                }
            ]
        },
        'pgv2':{'namespace':'http://www.protogeni.net/resources/rspec/2',
            'ext_namespaces':{
                'stitch':'http://hpn.east.isi.edu/rspec/ext/stitch/0.1/'
                },
            'aggregates':[
                {'name':'emulab.net', #not really used
                'aggrURL':'http://www.emulab.net/protogeni/xmlrpc/am/2.0'
                },
                {'name':'uky.emulab.net', #not really used
                'aggrURL':'https://www.uky.emulab.net/protogeni/xmlrpc/am/2.0'
                }
            ]
        },
        'geniv3':{'namespace':'http://www.geni.net/resources/rspec/3',
            'ext_namespaces':{
                'stitch':'http://hpn.east.isi.edu/rspec/ext/stitch/0.1/'
                },
            'aggregates':[
                {'name':'emulab.net', #not really used
                'aggrURL':'http://www.emulab.net/protogeni/xmlrpc/am/2.0'
                },
                {'name':'uky.emulab.net', #not really used
                'aggrURL':'https://www.uky.emulab.net/protogeni/xmlrpc/am/2.0'
                }
            ]
        },
        # Chris didn't have this next. But without it
        # we end up with MAX manifest class for ION manifests.
        # Now, I don't actually know if that is a problem...
        'ion':{'namespace':'http://geni.maxgigapop.net/aggregate/rspec/20100412/',
            'ext_namespaces':{
                'ctrlplane':'http://ogf.org/schema/network/topology/ctrlPlane/20080828/'
                },
            'aggregates':[
                {'name':'ion.internet2.edu',
                'aggrURL':'http://alpha.east.isi.edu:12346',
                }
            ]
        }
    }
    return rspecInfo


## Gets a terminal color code to be used in changing the output color
# Takes an integer (likely a thread number) so we can try and get separate
# colors
#
#   @param num - Any integer >0.
#   @return String color code
#
def getTermColorTag(num):
    if num < 1:
        raise Exception("Invalid thread number given")
    tmp = num % len(term_colors) -1
    return term_colors[tmp]


## Gets a terminal color code to be used in changing the output color back to
# default
#
#   @return String color code
#
def getTermColorEndTag():
    return term_end

# getSiteNamePrefix
# If omni config has framework type=sfa,
# then get the authority element, get part after last '.'
# and prepend sitestr_ to front of slicename for various things
# IE within SFA slice foo is known as site_foo
def getSiteNamePrefix(config, logger):
    # Make sure this is an SFA SA so has a site name
    if not (config \
       and config.has_key('selected_framework') \
       and config['selected_framework'].has_key('type') \
       and config['selected_framework']['type'] == 'sfa'):
        logger.debug("Not an SFA framework so no site name")
        return ""

    # Need to add site name. Make sure there is an authority
    if not config['selected_framework'].has_key('authority'):
        logger.warn('Missing authority key from omni_config')
        return ""

    auth = config['selected_framework']['authority'].strip()
    # see sfa/util/xrn/XRN.hrn_leaf()
    site = [ x.replace('--sep--','\\.') for x in auth.replace('\\.','--sep--').split('.') ][-1].strip()
    logger.debug("From authority %s derived sitename %s", auth, site)

    if site and len(site) > 0:
        return site + '_'
    else:
        logger.debug("Since site was empty, returning empty string")
        return ""

    # Note that there is also a username tag - which we could use too....
