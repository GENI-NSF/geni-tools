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
'''Sample script that uses Omni as a library, to 'stitch' together
resources from multiple aggregates.
See README-stitch for details.
Basic usage:
sample.py [omni options] <slicename> <1+ request RSpec files>
Where libstitch/cache should contain 1+ advertisement RSpecs, covering at 
least the aggregates from which you are requesting resources.
'''

import logging
import os
import sys

import libstitch
import omni

# Sample script that uses Omni as a library, to 'stitch' together
# resources from multiple aggregates.
#
# See README-stitch.txt for details.
#
# Basic usage:
# sample.py [omni options] <slicename> <1+ request RSpec files>
# Where libstitch/cache should contain 1+ advertisement RSpecs, covering at 
# least the aggregates from which you are requesting resources.
def main(argv=None):

    parser = omni.getParser()
    omni_usage = parser.get_usage()
    parser.set_usage("\n\nsample.py [omni options] [--real] [--outFolder <foldername>] <slicename> <rspec> [<rspec> ...]")

    # Add custom options for this script
    parser.add_option("--real",
                    help="Really do sliver requests, don't fake it",
                    action="store_true", default=False)
    parser.add_option("--outFolder",
                    help="Folder for graph and script output files",
                    metavar="FOLDER", default=None)

    # Let Omni parse its options as usual. This also parses out our
    # custom options, if provided.
    # options is an optparse.Values object, and args is a list
    options, args = parser.parse_args(sys.argv[1:])

    if options.real:
        print "\nWill do real sliver requests"
    else:
        print "\nWill simulate sliver requests"

    ######################################################
    # BEGIN SEQUENCE 
    ######################################################

    print "\n\n#######################################"
    print "                STARTING "
    print "#######################################\n"
    
    if args and len(args)>1:

        slice_name = str(args[0]).strip()

        verbose=False
        if options.debug:
            verbose=True
 
        # Open the request rspec files as strings
        rspecs = openFiles(args[1:]) #Throws Exception on read errors

        raw_input("\nPress return to continue...\n")

        # Apply your -l and --debug logging parameters before calling libstitch,
        # to make your options apply.
        # Using omni to configure python logging does not disable existing loggers,
        # but also does not apply configurations to existing loggers, unless they
        # are named explicitly in the logging config file (or their ancestors, not 'root').
        # Note that calls to omni.call will re-configure logging.
        omni.configure_logging(options)

        # Create libstitch session
        s = libstitch.Stitch(slice_name,rspecs,verbose,options)

        # Start the sessions: parses the request RSpec strings
        if not s.startSession(): 
            print "Session failed to start"
            return

        if verbose:
            print "\nPreset Routes:"
            for aggr in s.session.getPresetRouteAggrURLList():
                print aggr + ":"
                presetDict = s.session.getPresetRouteDictForAggrURL(aggr)
                cnt = 1
                for (local, remote) in presetDict.items():
                    print "  " + str(cnt) + ": [" + local + "] -> " + remote
                    cnt += 1
                print '\n'

        raw_input("\nPress return to continue...\n")

        print "\n\n#######################################"
        print "               DEPENDENCIES "
        print "#######################################\n"

        # Calculate the dependencies among aggregate requests
        sequence = s.calculateSequence()

        print "\nDependencies:"
        deps = s.getDependencies() #Get the dependencies
        for aggr in deps: #Display the dependencies
            print aggr
            for dep in deps[aggr]:
                print " --> "+dep

        # Sequence is the order we reserve at aggregates.
        # It is an ordered set of ReqRSpec objects.
        print "\nSequence:"
        cnt = 1
        for aggr in sequence: #Display the sequence
            print str(cnt) + ": " + aggr.aggrURL #+ " of type " + aggr.rspecType + ", class " + aggr.__class__.__name__
            cnt += 1

        if verbose:
            print '\nRequested interfaces:'
            for aggr in sequence:
                print aggr.aggrURL
                cnt = 1
                for iface in aggr.requestedInterfaces.keys():
                    if iface is None:
                        continue
                    print "  " + str(cnt) + ": " + iface + ' -> ' + str(aggr.requestedInterfaces[iface]['remoteIface']) + ' (on ' + str(aggr.requestedInterfaces[iface]['remoteAggrURL']) + ')'
                    cnt += 1
                print '\n'
            
        raw_input("\nPress return to continue...\n")

        print "\n\n#######################################"
        print "               EXECUTION "
        print "#######################################\n"

        ## Use fake responses, or real ones
        # Fake responses make no Omni calls, but use canned responses
        # from libstitch/sample. See doFakeRequest methods in libstitch/rspec.py.
        # Real responses invoke createSliver on aggregates.
        real = options.real
        pause = False ## Pause when inserting vlans into rspecs

        # Two ways to make reservations: in sequence, or in parallel.
        # executeSequenceP uses python threads to try to parallelize
        # reservation requests at aggregates that don't depend on each other.

        #assigned_vlans = s.executeSequence(sequence,pause,real) #Execute
        assigned_vlans = s.executeSequenceP(sequence,real) #Execute

        # Note that on error in execution, assigned_vlans is empty.

        print "\nSummary of assigned vlans:"
        for aggr in assigned_vlans: #Display the resulting VLANs
            print " ---> "+aggr
            if len(assigned_vlans[aggr]) < 1:
                print " ------> None! (Error?)"
            for iface,vlan in assigned_vlans[aggr].iteritems():
                print " ------> "+iface+" : "+vlan

        raw_input("\nPress return to continue...\n")


        print "\n\n#######################################"
        print "               OUTPUT "
        print "#######################################\n"

        # Get an output folder. Try to use any commandline option, else use a default
        folder = None
        if options.outFolder:
            if not os.path.exists(options.outFolder):
                # try creating it. If that fails, use the default
                try:
                    os.mkdir(options.outFolder)
                    folder = options.outFolder
                    print "Using output folder %s" % folder
                except Exception, e:
                    print "Failed creating requested output folder %s: %s" % (options.outFolder, e)
            else:
                folder = options.outFolder
                print "Using output folder %s" % folder

        if not folder:
            folder = s.defaultOutputFolder() #Optional, can use any path you like

        if folder is not None:
            s.generateGraph(folder) 
            s.generateScripts(folder)
        else:
            print "I couldn't create the output folder. Check permissions."

        print "\n\n#######################################"
        print "                FINISHED "
        print "#######################################\n"

        s.endSession() #Finish - which leaves your resources allocated.

    else:
        print "Please give at least one rspec as parameter."
        print "Usage: sample.py [omni options] <slice name> <1+ request RSpecs>"
        return


## Static helper function to open and read from multiple request RSpec files.
# Opens a list of filenames and returns a list of string filecontents. This is 
# intended to fail immediately (raise Exception) if we encounter an issue with 
# any of the input files.
#     
#   @param rspecs - List of input filenames to be opened
#   @return List of xml strings if success, False if failure
#
def openFiles(rspecs=[]):

    fileHandles=[]
    rspecStrList=[]
    valid = True
    if len(rspecs)<1:
        return False

    for i in rspecs:
        output = "Opening Rspec: "+str(i)
        # Intentionally not catching exceptions,
        # so we exit early if requests not readable
        with open(i) as fh:
            rspecStrList.append(fh.read())
            fileHandles.append(fh)
            output+=", Success."
        print output

    if len(fileHandles)<1:
        return False

    return rspecStrList


if __name__ == "__main__":
    sys.exit(main())

