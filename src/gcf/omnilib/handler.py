#!/usr/bin/python

from __future__ import absolute_import

#----------------------------------------------------------------------
# Copyright (c) 2012-2015 Raytheon BBN Technologies
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
""" 
Omni Call Handler
Takes Omni commandline calls and dispatches them as appropriate.
Calls generally go to the ch-handler or the am-handler as appropriate.
""" 

from .util import OmniError
from .amhandler import AMCallHandler
from .chhandler import CHCallHandler

class CallHandler(object):
    """Handle calls on the framework. Valid calls are all
    methods without an underscore: getversion, createslice, deleteslice, 
    getslicecred, listresources, createsliver, deletesliver,
    renewsliver, sliverstatus, shutdown, listmyslices, listaggregates, renewslice, etc
    """

    def __init__(self, framework, config, opts):
        self.framework = framework
        self.logger = config['logger']
        self.omni_config = config['omni']
        self.config = config
        self.opts = opts
        if self.opts.abac:
            aconf = self.config['selected_framework']
            if 'abac' in aconf and 'abac_log' in aconf:
                self.abac_dir = aconf['abac']
                self.abac_log = aconf['abac_log']
            else:
                self.logger.error("ABAC requested (--abac) and no abac= or abac_log= in omni_config: disabling ABAC")
                self.opts.abac= False
                self.abac_dir = None
                self.abac_log = None
        self.amhandler = AMCallHandler(framework, config, opts);
        self.chhandler = CHCallHandler(framework, config, opts);

        
    def _raise_omni_error( self, msg, err=OmniError ):
        self.logger.error( msg )
        raise err, msg

    def _handle(self, args):
        if len(args) == 0:
            self._raise_omni_error('Insufficient number of arguments - Missing command to run')
        
        call = args[0].lower()
        # disallow calling private methods
        if call.startswith('_'):
            return
    
        if hasattr(self, call):
            return getattr(self, call)(args[1:])
        elif hasattr(self.chhandler, call):
            return getattr(self.chhandler, call)(args[1:])
        elif hasattr(self.amhandler, call):
            # Extract the slice name arg and put it in an option
            self.amhandler.opts.sliceName = self.amhandler._extractSliceArg(args)

            # Try to auto-correct API version
            msg = self.amhandler._correctAPIVersion(args)
            if msg is None:
                msg = ""

            (message, val) = getattr(self.amhandler,call)(args[1:])
            if message is None:
                message = ""
            return (msg+message, val)
        else:
            self._raise_omni_error('Unknown function: %s' % call)

# End of CallHandler
