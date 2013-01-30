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

from omnilib.stitch.objects import Aggregate

class WorkflowParser(object):

    DEPENDENCIES_KEY = 'dependencies'
    HOP_URN_KEY = 'hop_urn'
    AGG_URL_KEY = 'aggregate_url'
    AGG_URN_KEY = 'aggregate_urn'
    IMP_VLANS_KEY = 'import_vlans'

    def __init__(self):
        self._aggs = dict()

    @property
    def aggs(self):
        return self._aggs.values()

    def _get_agg(self, agg_url, agg_urn):
        cache_key = (agg_url, agg_urn)
        if cache_key in self._aggs:
            print "cache hit"
            agg = self._aggs[cache_key]
        else:
            print "cache miss"
            agg = Aggregate(agg_urn, agg_url)
            self._aggs[cache_key] = agg
        return agg

    def parse(self, workflow, rspec):
        """Parse the workflow into the rspec data structure."""
        for link_id in workflow:
            path = rspec.find_path(link_id)
            if not path:
                msg = "No path found with id = %r" % (link_id)
                raise Exception(msg)
            deps = workflow[link_id][self.DEPENDENCIES_KEY]
            self._parse_deps(deps, path)
            # Post processing steps:
            self._add_agg_deps(path)

    def _add_hop_info(self, hop, info_dict):
        """Add the aggregate and import_vlans info to the hop if it
        doesn't already have it.
        """
        if not hop.aggregate:
            # Get info out of the dict
            agg_url = info_dict[self.AGG_URL_KEY]
            agg_urn = info_dict[self.AGG_URN_KEY]
            import_vlans = info_dict[self.IMP_VLANS_KEY]
            # Find the corresponding aggregate
            agg = self._get_agg(agg_url, agg_urn)
            # Add the info to the hop
            hop.aggregate = agg
            hop.import_vlans = import_vlans
            # Tell the aggregate about the hop
            agg.add_hop(hop)

    def _parse_deps(self, deps, path):
        # Cache aggregate objects
        for d in deps:
            # Each dependency has a hop URN. Use that to
            # find the relevant hop.
            hop_urn = d[self.HOP_URN_KEY]
            print "Hop URN = %r" % (hop_urn)
            hop = path.find_hop(hop_urn)
            if not hop:
                msg = "No hop found with id %r on path %r" % (hop_urn,
                                                              path.id)
                raise Exception(msg)
            print "Got hop %r (%r)" % (hop, hop.urn)
            self._add_hop_info(hop, d)
            hop_deps = d[self.DEPENDENCIES_KEY]
            self._parse_hop_deps(hop_deps, hop, path)

    def _parse_hop_deps(self, deps, hop, path):
        "Parse the hop dependencies in deps."
        for d in deps:
            hop_urn = d[self.HOP_URN_KEY]
            dep_hop = path.find_hop(hop_urn)
            if not dep_hop:
                msg = "No dependent hop found with id %r on path %r"
                msg = msg % (hop_urn, path.id)
                raise Exception(msg)
            self._add_hop_info(dep_hop, d)
            print "Hop %r adding dependency on hop %r" % (hop, dep_hop)
            hop.add_dependency(dep_hop)
            # TODO: Add a reverse pointer?

    def _add_agg_deps(self, path):
        """Follow the hop dependencies and generate aggregate to
        aggregate dependencies from them.
        """
        for hop in path.hops:
            hop_agg = hop.aggregate
            print "AAD: hop.aggregate: %s" % (hop_agg)
            for hd in hop.dependsOn:
                print "AAD:   dep.aggregate: %s" % (hd.aggregate)
                hop_agg.add_dependency(hd.aggregate)
