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
'''
Define the Stitch class, a helper for managing the libstitch library.

This helper primarily has helpers to loop through the request RSpecs for
each step in the process:
- initialize ReqRSpec objects
- calculateRestrictions
- calculateDeps
Then it helps with arguments to and returns from:
- calculateExecuteSequence
- executeInSequence or executeInParallel
Then it supplies the helper result functions
- generateGraph
- generateScripts
'''

import os
import logging
import signal
import sys

import omni

# Import libstitch files
from src.defs import *
from src.exception import *
from src.rspec import ReqRSpec,ManRSpec
from src.stitchsession import StitchSession
from src import util


## Helper class to make the API simpler to use. Basically acts as a Facade 
# object. You don't have to use this class, but it will make things easier. 
#
class Stitch(object):
    
    ## The Constructor
    # 
    #    @param sliceNameStr - The name of the slice to be created
    #    @param rspecStrList - A list of string request rspec XML strings
    #    @param verbose - Boolean value, True if you want verbose output
    #    @param options - optparse.Values object containing options
    # as pre-parsed by Omni, if any
    # 
    def __init__(self, sliceNameStr, rspecStrList, verbose=False, options=None):

        # Create a single logger for libstitch, used throughout
        self.logger = logging.getLogger(logger_name)
        if verbose:
            self.logger.setLevel(verbose_loglevel)

        #if nothing passed in for omni options, just create empty struct
        if options is None:
            parser = omni.getParser()
            options, self.args = parser.parse_args()
        self.options = options 

        # The list of XML strings representing request RSpecs
        self.rspecStrList = rspecStrList
        self.session = None

        ################################################
        # OMNI Config
        ################################################

        #Check if the omni configuration is valid and can be found
        self.user = ""
        self.keyfile = ""
        try:
            self.user, self.keyfile = util.getOmniConf(self.options,self.logger) 
        except:
            raise Exception("Something is missing from your omni config")

        ################################################
        # Slice Name
        ################################################

        self.slicename = ""
        if len(sliceNameStr)>0:
            self.slicename = str(sliceNameStr).strip()
        else:
            raise InvalidSliceNameException

        ##Register thread killer
        signal.signal(signal.SIGINT, self.killThreads)


    ## Starts the stitching session by beginning to parse input RSpecs
    #    
    #   @ return True if successful, False otherwise
    # 
    def startSession(self):
        
        ################################################
        # Stitch Session
        ################################################       

        # Create the stitchsession object, which holds state for our use
        self.session = StitchSession(self.slicename, self.user, self.keyfile, self.logger)

        # startSession parses the Ad RSpecs to get topology info
        if not self.session.startSession():
            return False

        ################################################
        # Parse Request RSpecs
        ################################################       
        
        self.logger.info("Generating RSpec objects based on %d input XML files...", len(self.rspecStrList))

        # Create ReqRSpec objects, parsing the XML, and filling in a 
        # few bits of information. When done, the session knows all the RSpecs.
        for rspecStr in self.rspecStrList:
            # ReqRSpecs call session.addAggregate(themselves)
            tmpRSpec = ReqRSpec(rspecStr,self.session,self.logger)
            self.logger.debug("Created rspec for AM %s of type %s, class %s", tmpRSpec.aggrURL, tmpRSpec.rspecType, tmpRSpec.__class__.__name__)

        return True


    ## Kill any threads that might be running in the background
    # Called by signal handler as needed.
    #    
    def killThreads(self, signal, frame):
        #for thread in self.session.threads:
        #    kill thread
        # This version of python doesn't support 'killing threads'
        # normally you'd loop on a signal in the thread, but the
        # threads in this case do not perform ongoing, repetitive 
        # tasks and so you'd need to sprinkle checks for a kill 
        # request throughout the RequestThread class in order to
        # get some desired behaviour. But that's just gross.
        sys.exit(0)


    ## Calculates and returns a sequence of request rspec objects in which they can be 
    # safely executed.
    #
    #   @return A python list of ReqRSpec objects in a safe execution order
    # 
    def calculateSequence(self):

        ################################################
        # Calculate Restrictions
        ################################################    

        self.logger.info("Calculating restrictions on each Aggregate...")

        # loop over Request RSpecs
        for aggr in self.session.getAggregateList():
            # Figure out which aggregate interfaces do VLAN translation, for example
            # This updates structures on the aggregate / RSpec object.
            aggr.calculateRestrictions()

        ################################################
        # Calculate Dependencies
        ################################################    
   
        self.logger.info("Calculating dependencies between Aggregates...")

        for aggr in self.session.getAggregateList():
            # Figure out which aggregates depend on information from others.
            # EG an aggregate that does VLAN translation depends on the VLAN ID
            # from a neighbor that does not do VLAN translation.
            aggr.calculateDeps()

        ################################################
        # Calculate Sequence
        ################################################  

        self.logger.info("Calculating sequence of aggregates...")

        # Having determined the dependencies, find an order to do reservations
        # at aggregates that satisfies the dependencies. Return an ordered list
        # of ReqRSpec objects.
        sequence = util.calculateExecuteSequence(self.session)

        return sequence


    ## Executes a given sequence of rspec objects in the order they are passed
    #
    #    @param sequence - A python list of ReqRSpec objects to be executed in 
    #    order
    #    @param real - Boolean value, True if you want to actually send rspecs off.
    #    False if you want to use the 'fake' response functions
    #    @return A dictionary of the format: {aggrURL->{interface_urn->vlan_id}}
    #    for which interfaces in which aggregates were assigned which Vlan tags
    # 
    def executeSequence(self, sequence, pause=False, real=False):

        if not real:
            self.logger.info("Faking Sending RSpecs...")
        else:
            self.logger.info("Sending RSpecs...")

        return_val = util.executeInSequence(sequence,self.options,self.logger,pause,real)
        if not return_val:
            self.logger.error("Sequence aborted")
            return {}
        
        if not real:
            self.logger.info("Succesfully faked reserving slivers")
        else:
            self.logger.info("Succesfully reserved slivers")

        return return_val


    ## Executes a given sequence of rspec objects in reverse-order and attempts
    # to parallelize execution of dependencies where possible. This will
    # typically be faster. It spawns a RequestThread for each ReqRSpec. 
    #
    # Note: It is not particularly clever in finding potential items to be
    # parallelized, and only sees the very simplest cases. There is a lot of
    # room here for improvement.
    #
    #    @param sequence - A python list of ReqRSpec objects to be executed in 
    #    order
    #    @param real - Boolean value, True if you want to actually send rspecs off.
    #    False if you want to use the 'fake' response functions
    #    @return A dictionary of the format: {aggrURL->{interface_urn->vlan_id}}
    #    for which interfaces in which aggregates were assigned which Vlan tags
    # 
    def executeSequenceP(self, sequence, real=False):

        if not real:
            self.logger.info("Faking Sending RSpecs in parallel...")
        else:
            self.logger.info("Sending RSpecs in parallel...")

        return_val = util.executeInParallel(sequence,self.options,self.logger,real)
        if not return_val:
            self.logger.error("Sequence aborted")
            return {}

        if not real:
            self.logger.info("Succesfully faked reserving slivers")
        else:
            self.logger.info("Succesfully reserved slivers")

        return return_val


    ## Creates the default output folder and returns its name
    #
    #    @return The default output folder that was created. None if failure
    # 
    def defaultOutputFolder(self):

        outputFolder = self.session.createOutputFolder()

        if not outputFolder:
            self.logger.error("Unable to create output Folder")
            return None

        self.logger.info("Created slice output folder: "+outputFolder)

        return outputFolder


    ## Generates a graph called graph.png of the created topology in the given
    # folder.
    #
    #    @param outputFolder - The folder to put the graph in
    # 
    def generateGraph(self, outputFolder):
       
        if not os.path.exists(outputFolder):
            self.logger.error("Specified output folder %s did not exist, unable to generate graph", outputFolder)
            return

        if self.session.generateGraph(outputFolder,graph_filename):
            self.logger.info(" ---> Created graph file: "+outputFolder+"/"+graph_filename)


    ## Generate set of default shell scripts for setup, login, etc. for
    # allocated nodes
    # in the given folder.
    #
    #   @param outputFolder - A string foldername to write the scripts into
    #
    def generateScripts(self, outputFolder):

        if not os.path.exists(outputFolder):
            self.logger.error("Specified output folder %s did not exist, unable to generate scripts", outputFolder)
            return

        # Loop over request RSpecs
        for rspec in self.session.getAggregateList():
#            self.logger.debug("Doing genScripts for agg %s with %d nodes", rspec.aggrURL, len(rspec.manRSpec.nodes))
            if rspec.manRSpec is None:
                continue
            for node in rspec.manRSpec.nodes:
                varScriptName = util.generateVarScript(outputFolder,node,self.session)

                if not varScriptName:
                    self.logger.warn("Unable to create var script for node: "+node['hostname'])
                    continue
                if util.generateLoginScript(outputFolder,varScriptName,node) and \
                        util.generateSetupScript(outputFolder,varScriptName,node):
                    self.logger.info(" ------> Created scripts for node: "+node['hostname'])
                else:
                    self.logger.warn("Failed creating login/setup scripts for node: " + node['hostname'])


    ## Ends the stitchsession. 
    #
    #   Note: This does nothing right now. It is here though to offer cleanup if
    # needed.
    # 
    def endSession(self):
        pass


    ## Gets a dictionary of dependencies between aggregates that were calculated
    #
    #   @return Dictionary of str(aggr1)->[str(aggr2),str(aggr3),str(aggr4)] 
    # 
    def getDependencies(self):
        deps = {}
        # Loop over request RSpecs
        for aggr in self.session.getAggregateList():
            deps[aggr.aggrURL] = aggr.getDependencies()
        return deps
