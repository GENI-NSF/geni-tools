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

    def __init__(self, aggs=[], logger=None):
        self.aggs = aggs
        self.logger = logger or logging.getLogger('stitch.launcher')

    def launch(self, rspec):
        while not self._complete():
            # Are there AMs to Delete? Or did that already happen?

            # Are there AMs to redo? Or does that fall intio the ready_aggregates bundle?

            ready_aggs = self._ready_aggregates()
            self.logger.debug("There are %d ready aggregates: %s",
                              len(ready_aggs), ready_aggs)
            for agg in ready_aggs:
                agg.allocate(rspec.dom.toxml())

            # Do we need to sleep?

        self.logger.info("All aggregates are complete.")


    # FIXME: Ensure ready implies not in process and not completed
    def _ready_aggregates(self):
        return [a for a in self.aggs if a.ready]

    # FIXME: Ensure agg.completed implies not in process and not ready
    def _complete(self, aggs=None):
        """Determine if the launch is complete. The launch is
        complete if all aggregates are complete.
        """
        if not aggs:
            aggs = self.aggs
        return aggs and reduce(lambda a, b: a and b,
                               [agg.completed for agg in aggs])
