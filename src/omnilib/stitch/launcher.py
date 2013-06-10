#----------------------------------------------------------------------
# Copyright (c) 2013 Raytheon BBN Technologies
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
'''Launch each aggregate when it is ready, and detect when all are done.'''

import logging
import time

from utils import StitchingRetryAggregateNewVlanError
from objects import Aggregate

class Launcher(object):

    def __init__(self, options, slicename, aggs=[], logger=None):
        self.aggs = aggs # Aggregate objects
        self.opts = options # Omni options
        self.slicename = slicename
        self.logger = logger or logging.getLogger('stitch.launcher')

    def launch(self, rspec, scsCallCount):
        '''The main loop for stitching: keep looking for AMs that are not complete, then 
        make a reservation there.'''
        lastAM = None
        while not self._complete():
            ready_aggs = self._ready_aggregates()
            self.logger.debug("\nThere are %d ready aggregates: %s",
                              len(ready_aggs), ready_aggs)
            for agg in ready_aggs:
                lastAM = agg
                # FIXME: Need a timeout mechanism on AM calls
                try:
                    agg.allocate(self.opts, self.slicename, rspec.dom, scsCallCount)
                except StitchingRetryAggregateNewVlanError, se:
                    self.logger.info("Will put %s back in the pool to allocate. Got %s", agg, se)

                    # Aggregate.BUSY_POLL_INTERVAL_SEC = 10 # dossl does 10
                    # Aggregate.PAUSE_FOR_AM_TO_FREE_RESOURCES_SECS = 30
                    # Aggregate.PAUSE_FOR_DCN_AM_TO_FREE_RESOURCES_SECS = 10 * 60 # Xi and Chad say ION routers take a long time to reset
                    secs = Aggregate.PAUSE_FOR_AM_TO_FREE_RESOURCES_SECS
                    if agg.dcn:
                        secs = Aggregate.PAUSE_FOR_DCN_AM_TO_FREE_RESOURCES_SECS
                    self.logger.info("Pausing for %d seconds for Aggregates to free up resources...\n\n", secs)
                    time.sleep(secs)

            # FIXME: Do we need to sleep?

        self.logger.info("All aggregates are complete.")
        return lastAM

    # ready implies not in process and not completed
    def _ready_aggregates(self):
        return [a for a in self.aggs if a.ready]

    # agg.completed implies not in process and not ready
    def _complete(self, aggs=None):
        """Determine if the launch is complete. The launch is
        complete if all aggregates are complete.
        """
        if not aggs:
            aggs = self.aggs
        return aggs and reduce(lambda a, b: a and b,
                               [agg.completed for agg in aggs])
