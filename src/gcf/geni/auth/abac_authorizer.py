#----------------------------------------------------------------------       
# Copyright (c) 2010-2014 Raytheon BBN Technologi
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

import gcf
import json
from .base_authorizer import *
from gcf.sfa.trust.credential_factory import CredentialFactory
from gcf.sfa.trust.credential import Credential
from gcf.sfa.trust.certificate import Certificate
from gcf.sfa.trust.abac_credential import ABACCredential
from gcf.geni.util.speaksfor_util import get_cert_keyid
from .util import *
from .resource_binder import ResourceBinder

# AM authorizer class that uses policies to generate ABAC proofs 
# for authorization decisions

class ABAC_Authorizer(Base_Authorizer):

    # Hard code some test rules for ABAC Authorizer
    # Rules consist of
    # List of binders
    # List of conditional assertions
    # List of queries (positive and negative)
    RULES = {}

    def __init__(self, root_cert, opts):
        Base_Authorizer.__init__(self, root_cert, opts)
        if not hasattr(opts, 'authorizer_policy_file'):
            raise Exception("authorizer_policy_file not specified")

        policy_file = opts.authorizer_policy_file

        self._resource_manager = None
        if hasattr(opts, 'authorizer_resource_manager'):
            resource_manager_classname = opts.authorizer_resource_manager
            resource_manager_class_module = \
                ".".join(resource_manager_classname.split('.')[:-1])
            __import__(resource_manager_class_module)
            resource_manager_class = eval(resource_manager_classname)
            self._resource_manager = resource_manager_class()

        RULES_RAW = open(policy_file).read()
        self.RULES = json.loads(RULES_RAW)

        self._binders = \
            [self._initialize_binder(b) for b in self.RULES['binders']]
        self._conditional_assertions = self.RULES['conditional_assertions']

        self._positive_queries = \
            [q['statement'] for q in self.RULES['queries'] \
                 if q['is_positive']]
        self._negative_queries = \
            [q['statement'] for q in self.RULES['queries']\
                 if not q['is_positive']]

        self._query_message_map = {}
        for q in self.RULES['queries']:
            self._query_message_map[q['statement']] = q['message']

        self._query_condition_map = {}
        for q in self.RULES['queries']:
            if 'condition' in q:
                self._query_condition_map[q['statement']] = q['condition']

        self._keyid_name_map = {}
        for id_name, id_pem in self.RULES['identities'].items():
            id_keyid = self._compute_keyid(cert_filename=id_pem)
            if id_keyid:
                self._keyid_name_map[id_keyid] = id_name

    # Bind all bindings in current context
    # For all assertions, evaluate precondition and if True, 
    #   Generate corresponding ABAC assertions 
    # Try to prove all the positive queries and none of the negative queries
    def authorize(self, method, caller, creds, args, opts,
                  current_allocations, requested_allocations):
        Base_Authorizer.authorize(self, method, caller, creds, args, opts,
                                  current_allocations, requested_allocations)
        self._logger.info("In ABAC AUTHORIZER...")

        caller_keyid = self._compute_keyid(cert_string=caller)
        self._keyid_name_map[caller_keyid] = "$CALLER"

        bindings = self._generate_bindings(method, caller, creds, args, opts)

        # Add 'constants' to bindings
        if 'constants' in self.RULES:
            bindings = dict(bindings.items() + self.RULES['constants'].items())

        resource_bindings = \
            self._generate_resource_bindings(caller, args,
                                             current_allocations, 
                                             requested_allocations)
        bindings = dict(bindings.items() + resource_bindings.items())

        self._logger.info("BINDINGS = %s" % bindings)

        assertions = self._generate_assertions(bindings)

        credential_assertions = \
            self._generate_credential_assertions(caller, creds, bindings)

        fixed_policies = self.RULES['policies']

        assertions = \
            assertions + credential_assertions + fixed_policies

        self._logger.info("ASSERTIONS = %s" % assertions)

        success, msg = self._evaluate_queries(bindings, assertions)
        
        del self._keyid_name_map[caller_keyid]

        if not success:
            raise Exception(msg)

    # Get each binder to generate bindings
    def _generate_bindings(self, method, caller, creds, args, opts):
        bindings = {}
        for binder in self._binders:
            new_bindings = binder.generate_bindings(method, caller, creds,
                                                    args, opts)
            bindings = dict(bindings.items() + new_bindings.items())
        return bindings

    # For each conditional assertion, evaluate the condition
    # If true and if the associated assertion is completely bound,
    # generate the assertion
    def _generate_assertions(self, bindings):
        assertions = []
        for ca in self._conditional_assertions:
            condition = ca['condition']
            assertion = ca['assertion']
            bound_condition = self._bind_expression(condition, bindings)
            if self._has_unbound_variables(bound_condition): continue
            self._logger.info("EVAL : %s" % bound_condition)
            if not eval(bound_condition): continue
            bound_assertion = self._bind_expression(assertion, bindings)
            if self._has_unbound_variables(bound_assertion): continue
            assertions.append(bound_assertion)
        return assertions

    # If provided a set of ABAC assertions, import them into our set
    # of assertions
    def _generate_credential_assertions(self, caller, creds, bindings):
        assertions = []
        abac_cred_objects = [CredentialFactory.createCred(credString=cred) \
                                 for cred in creds \
                                 if CredentialFactory.getType(cred) == \
                                 ABACCredential.ABAC_CREDENTIAL_TYPE]
        for abac_cred in abac_cred_objects:
            head_principal = abac_cred.head.get_principal_keyid()
            head_principal_name = self._lookup_name_from_keyid(head_principal)
            head_role = abac_cred.head.get_role()
            tail = abac_cred.tails[0] # Only take the first one
            tail_principal = tail.get_principal_keyid()
            tail_principal_name = self._lookup_name_from_keyid(tail_principal)
            tail_role = tail.get_role()
            if tail_role:
                assertion = "%s.%s<-%s.%s" % (head_principal_name, head_role, 
                                              tail_principal_name, tail_role)
            else:
                assertion = "%s.%s<-%s" % (head_principal_name, head_role, 
                                              tail_principal_name)
            bound_assertion = self._bind_expression(assertion, bindings)
            assertions.append(bound_assertion)

        return assertions

    # Generate bindings based on current and requested resource allocations
    def _generate_resource_bindings(self, caller, args, 
                                    current_allocations, 
                                    requested_allocations):

        print "CURRENT = %s" % current_allocations
        print "REQUESTED = %s" % requested_allocations

        bindings = {}

        if 'slice_urn' not in args: return bindings

        caller_urn = gid.GID(string=caller).get_urn()
        slice_urn = args['slice_urn']
        project_urn = convert_slice_urn_to_project_urn(slice_urn)
        authority_urn = convert_user_urn_to_authority_urn(caller_urn)


        resource_binder = ResourceBinder(caller_urn, slice_urn, 
                                           project_urn, authority_urn)
        for sliver_info in (current_allocations + requested_allocations):
            resource_binder.updateForSliver(sliver_info)

        bindings = resource_binder.getBindings()

        return bindings

    # Determine if all positive queries are proven and no negative
    # query is proven
    def _evaluate_queries(self, bindings, assertions):

        messages = []

        all_positive_proved = True
        for q in self._positive_queries:
            evaluated, proven, msg = \
                self._evaluate_query(bindings, assertions, q)
            if not evaluated: continue
            if not proven:
                all_positive_proved = False
                messages.append(msg)

        all_negative_disproved = True
        for q in self._negative_queries:
            evaluated, proven, msg = \
                self._evaluate_query(bindings, assertions, q)
            if not evaluated: continue
            if proven:
                all_negative_disproved = False
                messages.append(msg)

        result = (all_positive_proved and all_negative_disproved)
        return result, ", ".join(messages)

    # Evaluate a single query
    # If there is a condition, it must be true to considered
    # Return evaluated, evaluation, failure_message
    def _evaluate_query(self, bindings, assertions, query):
        # If there is a condition on this query, only evaluate if 
        # condition is satisfied
        if query in self._query_condition_map:
            condition = self._query_condition_map[query]
            bound_condition = self._bind_expression(condition, bindings)
            if self._has_unbound_variables(bound_condition):
                raise Exception("Illegal query condition: unbound variable %s"\
                                    % bound_condition)
            if not eval(bound_condition): 
                return False, False, ""

        # If no condition or condition  succeeded, evaluate bound query
        bound_q = self._bind_expression(query, bindings)
        if self._has_unbound_variables(bound_q): 
            raise Exception("Illegal query: unbound variable %s" % bound_q)

        evaluation = self._prove_query(bound_q, assertions)
        msg = self._query_message_map[query]
        return True, evaluation, msg
        

    # Replace bindings ($VAR) with bound value
    def _bind_expression(self, expr, bindings):
        for binding, value in bindings.items():
            if expr.find(binding) > -1:
                expr = expr.replace(binding, value)
        return expr

    # Are there any unbound variables in expression?
    def _has_unbound_variables(self, expr):
        return expr.find("$") > -1
        

    # Prove (or fail to prove) an ABAC query based on a set of assertions
    # We use a simple recursive chaining to see if we can find a path
    # from the query LHS to the query RHS
    def _prove_query(self, query, assertions):

        query_parts = query.split('<-')
        query_lhs = query_parts[0].strip()
        query_rhs = query_parts[1].strip()

        parsed_assertions = {}
        for assertion in assertions:
            assertion_parts = assertion.split('<-')
            assert_lhs = assertion_parts[0].strip()
            assert_rhs = assertion_parts[1].strip()
            if assert_lhs not in parsed_assertions:
                parsed_assertions[assert_lhs] = []
            parsed_assertions[assert_lhs].append(assert_rhs)

        result = \
            self._prove_query_internal(query_lhs, query_rhs, parsed_assertions)

        self._logger.info("QUERY (%s) : %s" % (result, query))
        return result

    # Internal method supporting _prove_query as a recursive call
    def _prove_query_internal(self, lhs, target, parsed_assertions):
        if lhs not in parsed_assertions: return False
        if target in parsed_assertions[lhs]: return True
        for new_lhs in parsed_assertions[lhs]:
            if self._prove_query_internal(new_lhs, target, parsed_assertions):
                return True
        return False

    # Initialize a binder from its classname
    def _initialize_binder(self, binder_classname):
        binder_class_module = ".".join(binder_classname.split('.')[:-1])
        __import__(binder_class_module)
        binder_class = eval(binder_classname)
        binder = binder_class(self._root_cert)
        return binder

    # Compute keyid from a cert
    def _compute_keyid(self, cert_string=None, cert_filename=None):
        if cert_string:
            cert_gid = gid.GID(string=cert_string)
        else:
            cert_gid = gid.GID(filename=cert_filename)
        extension_names = [ext[0] for ext in cert_gid.get_extensions()]
        if 'subjectKeyIdentifier' not in extension_names:
            return None
        return get_cert_keyid(cert_gid)

    # Find the name assocaited to a given keyid
    def _lookup_name_from_keyid(self, keyid):
        if keyid not in self._keyid_name_map:
            raise Exception("Unknown keyid : %s" % keyid)
        return self._keyid_name_map[keyid]




