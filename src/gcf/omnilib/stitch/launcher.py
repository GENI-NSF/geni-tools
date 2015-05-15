#----------------------------------------------------------------------
# Copyright (c) 2013-2015 Raytheon BBN Technologies
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

from __future__ import absolute_import

import datetime
import logging
import time

from .utils import StitchingRetryAggregateNewVlanError, StitchingRetryAggregateNewVlanImmediatelyError, StitchingError, StitchingStoppedError
from .objects import Aggregate

class Launcher(object):

    def __init__(self, options, slicename, aggs=[], timeoutTime=datetime.datetime.max, logger=None):
        self.aggs = aggs # Aggregate objects
        self.opts = options # Omni options
        self.slicename = slicename
        self.timeoutTime = timeoutTime
        self.logger = logger or logging.getLogger('stitch.launcher')

    def launch(self, rspec, scsCallCount):
        '''The main loop for stitching: keep looking for AMs that are not complete, then 
        make a reservation there.'''
        lastAM = None
        while not self._complete():
            if datetime.datetime.utcnow() >= self.timeoutTime:
                msg = "Reservation attempt timed out after %d minutes." % self.opts.timeout
                raise StitchingError(msg)
            ready_aggs = self._ready_aggregates()
            if len(ready_aggs) == 0 and not self._complete():
                self.logger.debug("Error! No ready aggregates and not all complete!")
                for agg in self.aggs:
                    if not agg.completed:
                        self.logger.debug("%s is not complete but also not ready. inProcess=%s, depsComplete=%s", agg, agg.inProcess, agg.dependencies_complete)
                raise StitchingError("Internal stitcher error: No aggregates are ready to allocate but not all are complete?")

            if self.opts.noTransitAMs:
                allTransit = True
                for agg in ready_aggs:
                    if agg.userRequested:
                        allTransit = False
                        break
                if allTransit:
                    self.logger.debug("Only transit AMs are now ready to allocate - will stop")
                    incompleteAMs = 0
                    for agg in self.aggs:
                        if not agg.completed:
                            incompleteAMs += 1
                        if agg.userRequested and agg.manifestDom is None:
                            self.logger.debug("WARN: Some non transit AMs not done, like %s", agg)
                    raise StitchingStoppedError("Per commandline option, stopping reservation before doing transit AMs. %d AM(s) not reserved." % incompleteAMs)

            self.logger.debug("\nThere are %d ready aggregates: %s",
                              len(ready_aggs), ready_aggs)
            for agg in ready_aggs:
                if datetime.datetime.utcnow() >= self.timeoutTime:
                    msg = "Reservation attempt timed out after %d minutes." % self.opts.timeout
                    raise StitchingError(msg)

                lastAM = agg
                # FIXME: Need a timeout mechanism on AM calls
                try:
                    agg.allocate(self.opts, self.slicename, rspec.dom, scsCallCount)
                except StitchingRetryAggregateNewVlanError, se:
                    self.logger.info("Will put %s back in the pool to allocate. Got: %s", agg, se)

                    # Aggregate.BUSY_POLL_INTERVAL_SEC = 10 # dossl does 10
                    # Aggregate.PAUSE_FOR_AM_TO_FREE_RESOURCES_SECS = 30
                    # Use the v3 AM sleep by default.
                    # But if any v2 AMs have (or have had) reservations, then use that sleep
                    secs = Aggregate.PAUSE_FOR_V3_AM_TO_FREE_RESOURCES_SECS
                    for agg2 in self.aggs:
                        if agg2.api_version == 2 and secs < Aggregate.PAUSE_FOR_AM_TO_FREE_RESOURCES_SECS and agg2.triedRes:
                            secs = Aggregate.PAUSE_FOR_AM_TO_FREE_RESOURCES_SECS
                    if not isinstance(se, StitchingRetryAggregateNewVlanImmediatelyError):
                        if agg.dcn:
                            secs = Aggregate.PAUSE_FOR_DCN_AM_TO_FREE_RESOURCES_SECS

                    if datetime.datetime.utcnow() + datetime.timedelta(seconds=secs) >= self.timeoutTime:
                        # We'll time out. So quit now.
                        self.logger.debug("After planned sleep for %d seconds we will time out", secs)
                        msg = "Reservation attempt timing out after %d minutes." % self.opts.timeout
                        raise StitchingError(msg)

                    self.logger.info("Pausing for %d seconds for Aggregates to free up resources...\n\n", secs)
                    time.sleep(secs)

                    # After this exception/retry, the list of ready aggregates may have changed
                    # For example, when we locally work back a bit to handle vlan unavailable
                    # So break out of this for loop, to make the while re-calculate the list of ready_aggs
                    break

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
