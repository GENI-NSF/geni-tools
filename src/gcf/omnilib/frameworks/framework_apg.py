#----------------------------------------------------------------------
# Copyright (c) 2011 USC/ISI
# Portions Copyright (c) 2011-2015 Raytheon BBN Technologies
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and/or hardware specification (the
# "Work") to deal in the Work without restriction, including without
# limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Work, and to
# permit persons to whom the Work is furnished to do so, subject to
# the following conditions:
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


from ..util.dossl import _do_ssl
from .framework_pg import Framework as pg_framework
from ..util.abac import save_abac_creds



class Framework(pg_framework):
    """The ProtoGENI backend for Omni. This class defines the
    interface to the Protogeni Control Framework.
    """

    def __init__(self, config):
        pg_framework.__init__(self,config)
        if 'abac' in config and 'abac_log' in config:
            self.abac = True
            self.abac_dir = config['abac']
            self.abac_log = config['abac_log']
        else:
            self.abac = False
            self.abac_dir = None
            self.abac_log = None
            self.logger.error("No abac directory or abac_log specified.  Reverting to ProtoGENI behavior")

    def get_user_cred(self):
        (pg_response, message) = _do_ssl(self, None, ("Get ABAC credentials from SA %s using cert %s" % (self.config['sa'], self.config['cert'])), self.sa.GetABACCredentials)
        _ = message #Appease eclipse
        if pg_response is None:
            self.logger.error("Failed to get your ABAC credentials: %s", message)
            return None, message
        else:
            code = pg_response.get('code', -1)
            if code == 0:
                if 'value' in pg_response:
                    value = pg_response['value']
                    if 'abac_credentials' in value:
                        creds = value['abac_credentials']
                        save_abac_creds(creds, self.abac_dir)
                else:
                    self.logger.error('Code is 0 but response had no value')
            else:
                self.logger.error("Failed to get a ABAC credentials: Received error code: %d", code)
                output = pg_response['output']
                self.logger.error("Received error message: %s", output)
                self.logger.error("Failed to get your ABAC credentials: %s", message)
                return None, message

        return pg_framework.get_user_cred(self)

    # At some point in future, this might do something interesting....
