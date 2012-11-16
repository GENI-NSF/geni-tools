#----------------------------------------------------------------------
# Copyright (c) 2012 Raytheon BBN Technologies
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

from omnilib.frameworks.framework_pg import Framework as pg_framework
from geni.util.urn_util import is_valid_urn, URN, string_to_urn_format
from urlparse import urlparse

class Framework(pg_framework):
    """The a ProtoGENI CH shim for Omni.
    """

    def __init__(self, config, opts):
        pg_framework.__init__(self,config, opts)
        self.opts = opts
    
    def slice_name_to_urn(self, name):
        """Convert a slice name and project name to a slice urn."""
        #
        # Sample URNs:
        #   urn:publicid:IDN+portal:myproject+slice+myexperiment
        #

        if name is None or name.strip() == '':
            raise Exception('Empty slice name')


        if not self.config.has_key('sa'):
            raise Exception("Invalid configuration: no slice authority (sa) defined")

        if (not self.opts.project) and (not self.config.has_key('default_project')):
            raise Exception("Invalid configuration: no default project defined")

        if self.opts.project:
            # use the command line option --project
            project = self.opts.project
        else:
            # otherwise, default to 'default_project' in 'omni_config'
            project = self.config['default_project']

        # if config has an authority, make sure it matches
        if self.config.has_key('sa'):
            url = urlparse(self.config['sa'])
        sa_host = url.hostname
        try:
            sa_hostname, sa_domain = sa_host.split(".",1)
            auth = sa_hostname
        except:
            # Funny SA
            self.logger.debug("Found no . in sa hostname. Using whole hostname")
            auth = sa_host

        # Authority is of form: host:project
        auth = auth+":"+project

        # Could use is_valid_urn_bytype here, or just let the SA/AM do the check
        if is_valid_urn(name):
            urn = URN(None, None, None, urn=name)
            if not string_to_urn_format(urn.getType()) == "slice":
                raise Exception("Invalid Slice name: got a non Slice URN %s"% name)
            # if config has an authority, make sure it matches
            urn_auth = string_to_urn_format(urn.getAuthority())
            if urn_auth != auth:
                self.logger.warn("CAREFUL: slice' authority (%s) doesn't match current configured authority (%s)" % (urn_auth, auth))
                self.logger.info("This may be OK though if you are using delegated slice credentials...")
            return name

        return URN(auth, "slice", name).urn_string()
