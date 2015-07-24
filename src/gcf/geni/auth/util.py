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

import importlib

# Some helper functions to manage conversions between URN types

# Convert a slice urn to a project urn (noting that there may not be one)
def convert_slice_urn_to_project_urn(slice_urn):
    project_auth_token = slice_urn.split('+')[1]
    project_auth_parts = project_auth_token.split(':')
    if len(project_auth_parts) < 2: return None # No project
    project_auth = project_auth_parts[0]
    project_name = project_auth_parts[1]
    project_urn = _convert_urn(project_auth, 'project', project_name)
    return project_urn

# Convert user urn to authority urn
def convert_user_urn_to_authority_urn(user_urn):
    user_auth_token = user_urn.split('+')[1]
    user_authority = _convert_urn(user_auth_token,'authority', 'ca')
    return user_authority

# Generic URN constructor for given value, obj_type and name
def _convert_urn(value, obj_type, obj_name):
    return 'urn:publicid:IDN+%s+%s+%s' % (value, obj_type, obj_name)

# Return an instance of a class given by fully qualified name 
# (module_path.classname) with variable constructor args
def getInstanceFromClassname(class_name, *argv, **kwargs):
    class_module_name = ".".join(class_name.split('.')[:-1])
    class_base_name = class_name.split('.')[-1]
    class_module = importlib.import_module(class_module_name)
    class_instance = eval("class_module.%s" % class_base_name)
    object_instance = class_instance(*argv,**kwargs)
    return object_instance
