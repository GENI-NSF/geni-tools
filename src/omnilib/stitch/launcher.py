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

import time
import logging

class Launcher(object):

    def __init__(self, options, aggs=[], logger=None):
        self.aggs = aggs
        self.opts = options
        self.logger = logger or logging.getLogger('stitch.launcher')

    def launch(self, rspec):
        '''The main loop for stitching: keep looking for AMs that are not complete, then 
        make a reservation there.'''
        while not self._complete():
            # FIXME: Are there AMs to Delete? Or did that already happen?

            ready_aggs = self._ready_aggregates()
            self.logger.debug("There are %d ready aggregates: %s",
                              len(ready_aggs), ready_aggs)
            for agg in ready_aggs:
                # FIXME: Need a timeout mechanism on AM calls
                agg.allocate(self.opts, rspec.dom.toxml())

            # FIXME: Do we need to sleep?

        self.logger.info("All aggregates are complete.")


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
