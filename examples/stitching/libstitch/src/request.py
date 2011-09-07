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
'''Define RequestThread to manage submitting a request in a separate thread,
ensuring that dependencies are completed first.'''

import threading
import time
import util
import random
import logging

## Worker thread which wraps a request and all subsequent dependee requests
#
class RequestThread(threading.Thread):
    '''A Thread that manages submitting a ReqRSpec, ensuring that dependencies
    are completed first.'''

    ## The Constructor
    #
    #    @param reqRSpec - ReqRSpec object to be responsible for
    #    @param ready - Handle on a Semaphore
    #    @param num - Counter of which Aggregate request this is
    #    @param options - Omni options to use in making the request
    #    @param logger - The logger this and all children should log to 
    #    @param real - Boolean value, True if you want the thread to submit 
    #                  rspec to aggregate, False if you want it to use a cached 
    #                  manifest as a fake response
    # 
    def __init__(self, reqRSpec, ready, num, options, logger, real=False):
        threading.Thread.__init__(self)

        self.ready = ready
        self.ready.acquire()
        self.reqRSpec = reqRSpec
        self.num = num
        self.options = options
        self.logger = logger
        self.real = real
        self.term_start = util.getTermColorTag(num)
        self.term_end = util.getTermColorEndTag()

        reqRSpec.stitchSession.threads.append(self) 

    def run(self):

        if self.reqRSpec.completed: 
            self.ready.release()
            return

        if self.reqRSpec.started:
            # Another thread is running this one. Want to wait
            self.logger.info("Another thread submitting request to %s. Waiting...", self.reqRSpec.aggrURL)
            while not self.reqRSpec.completed:
                # FIXME
                time.sleep(1)
            self.ready.release()
            return

#        self.logger.debug("In thread %d for AM %s of type %s", self.num, self.reqRSpec.aggrURL, self.reqRSpec.rspecType)
        if len(self.reqRSpec.dependsOn)>0:

            self.logger.info(self.term_start+str(self.num)+"--> Aggregate: "+self.reqRSpec.aggrURL+" has %d children..." % len(self.reqRSpec.dependsOn)+self.term_end)
            subReady = threading.Semaphore(len(self.reqRSpec.dependsOn))
            count = self.num+1

            ##Hacky wait
            subsToWaitOn = 0

            # Start a thread for each dependency
            for dep in self.reqRSpec.dependsOn:
#                self.logger.debug("Spawning thread from %d: %s for dep %s", self.num, self.reqRSpec.aggrURL, dep.aggrURL)
                rspecReq = RequestThread(dep,subReady,count,self.options,self.logger,self.real)
                rspecReq.start()
                subsToWaitOn += 1
                count+=1

            # Wait for dependencies to finish
            while subsToWaitOn > 0:
                subReady.acquire()
                subsToWaitOn -= 1

            for dep in self.reqRSpec.dependsOn:
                if dep.manRSpec is None:
                    self.logger.error("Failed submitting RSpec to: "+self.reqRSpec.aggrURL)
                    self.ready.release()
                    return

                if dep.completed:
                    self.logger.debug(self.term_start + "   Dependency %s complete - do collectInfo and inserVlanData" % dep.aggrURL + self.term_end)
                    dep.manRSpec.collectInfo()
                    self.reqRSpec.insertVlanData(dep.manRSpec.definedVlans)

        self.logger.info(self.term_start+str(self.num)+"--> Aggregate: "+self.reqRSpec.aggrURL+self.term_end)
#        self.logger.debug(self.term_start + "      -- " + self.reqRSpec.rspecType + self.term_end)
        return_val = util.executeReqRSpec(self.reqRSpec,self.options,self.logger,self.real)

        if self.reqRSpec.manRSpec is None or not return_val:
            self.logger.error("Failed submitting RSpec to: "+self.reqRSpec.aggrURL)
            self.ready.release()
            return

        self.reqRSpec.completed = True
        self.logger.info(self.term_start+str(self.num)+"--> Done"+self.term_end)
#        self.logger.debug(self.term_start+self.reqRSpec.rspecType+self.term_end)
        self.ready.release()
