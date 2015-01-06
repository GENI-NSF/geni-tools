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

from __future__ import absolute_import

import logging

from ...geni.util.urn_util import is_valid_urn, URN, string_to_urn_format
from .framework_pg import Framework as pg_framework

class Framework(pg_framework):
    """Framework to talk to a PG-style clearinghouse implemented using
    GCF, for use by GENI-in-a-Box"""

    def __init__(self, config, opts):
        pg_framework.__init__(self, config, opts)
        self.logger = logging.getLogger("omni.gib")

    def list_my_slices(self, user):
        '''List slices owned by the user (name or hrn or URN) provided, returning a list of slice URNs.'''
        userhrn = self.user_name_to_hrn(user)
        return self._list_my_slices(userhrn)

    def user_name_to_hrn(self, name):
        '''Convert a username to an HRN. Accept an HRN or URN though. Authority
        is taken from the SA hostname.'''

        if name is None or name.strip() == '':
            raise Exception('Empty user name')

        # If the name is a URN, convert it
        if is_valid_urn(name):
            (hrn, type) = urn_to_hrn(name)
            if type != 'user':
                raise Exception("Not a user! %s is of type %s" % (name, type))
            name = hrn
            self.logger.debug("Treating name %s as a URN, with hrn %s", name, hrn)

        # Otherwise, construct the hrn (or maybe this is one)

        if not self.config.has_key('authority'):
            raise Exception("Invalid configuration: no authority name defined")

        auth = self.config['authority']

        # Assume for now that if the name looks like auth.name, then it is a valid hrn
        if name.startswith(auth + '.'):
            self.logger.debug("Treating %s as an hrn", name)
            return name

        hrn = auth + '.' + name
        self.logger.debug("Treating %s as just the name, with full hrn %s", name, hrn)

        return hrn

    # Use an 'authority' field from the omni_config to set the
    # authority part of the URN
    def slice_name_to_urn(self, name):
        """Convert a slice name to a slice urn."""

        if name is None or name.strip() == '':
            raise Exception('Empty slice name')

        if is_valid_urn(name):
            urn = URN(None, None, None, name)
            if not urn.getType() == "slice":
                raise Exception("Invalid Slice name: got a non Slice URN %s", name)
            # if config has an authority, make sure it matches
            if self.config.has_key('authority'):
                auth = self.config['authority']
                urn_fmt_auth = string_to_urn_format(urn.getAuthority())
                if urn_fmt_auth != auth:
                    self.logger.warn("CAREFUL: slice' authority (%s) doesn't match current configured authority (%s)" % (urn_fmt_auth, auth))
                    self.logger.info("This may be OK though if you are using delegated slice credentials...")
#                    raise Exception("Invalid slice name: slice' authority (%s) doesn't match current configured authority (%s)" % (urn_fmt_auth, auth))
            return name

        if not self.config.has_key('authority'):
            raise Exception("Invalid configuration: no authority defined")

        auth = self.config['authority']
        return URN(auth, "slice", name).urn_string()

    # Auto recreate slices whenever the user asks for a slice
    # Note any slice renewal from last time will be gone
    def get_slice_cred(self, urn):
        return self.create_slice(urn)
