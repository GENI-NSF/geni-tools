#----------------------------------------------------------------------
# Copyright (c) 2010-2015 Raytheon BBN Technologies
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

import gcf
import json
import logging
from .base_authorizer import *
from ...sfa.trust.credential_factory import CredentialFactory
from ...sfa.trust.credential import Credential
from ...sfa.trust.certificate import Certificate
from ...sfa.trust.abac_credential import ABACCredential
from ..util.speaksfor_util import get_cert_keyid
from .util import *

# AM authorizer class that uses policies to generate ABAC proofs 
# for authorization decisions

class ABAC_Authorizer(Base_Authorizer):

    # Rules for ABAC Authorizer
    # Rules consist of:
    # List of identities (name => cert)
    # List of binders
    # List of constants
    # List of policies (unconditional  ABAC assertions)
    # List of conditional ABAC assertions
    # List of queries (positive and negative)

    def __init__(self, root_cert, opts, argument_guard=None):
        Base_Authorizer.__init__(self, root_cert, opts)

        self._argument_guard = argument_guard

        self._logger = logging.getLogger('gcf.abac_auth')
        logging.basicConfig(level=logging.INFO)

        if not hasattr(opts, 'authorizer_policy_map_file'):
            raise Exception("authorizer_policy_map_file not specified")

        policy_map_file = opts.authorizer_policy_map_file

        policy_map_raw = open(policy_map_file).read()
        policy_map = json.loads(policy_map_raw)

        if "default" not in policy_map:
            raise Exception("No default specified in authorizer policy map file: %s" %\
                                policy_map_file)

        self._AUTHORITY_SPECIFIC_RULES = {}
        for label, filenames in policy_map.items():
            rules = self.generate_rules(label, filenames)
#            rules.dump()
            if label == 'default' : 
                self._DEFAULT_RULES = rules
            else:
                self._AUTHORITY_SPECIFIC_RULES[label] = rules

    # Generate a rule set (identities, biners, constants
    # conditional_assertions, policies, queries)
    # from a set of files. These are ordered and thus later files add to or
    # replace previous entries
    def generate_rules(self, label, filenames):
        rule_set = ABAC_Authorizer_Rule_Set(label, self._root_cert)
        for filename in filenames:
            rule_set.parse(filename)
        return rule_set

    # Find the correct set of rules for the given caller based on authority
    def lookup_rules_for_caller(self, caller):
        caller_urn = gid.GID(string=caller).get_urn()
        caller_authority = convert_user_urn_to_authority_urn(caller_urn)
        caller_authority_name = caller_authority.split('+')[1]
        rules = self._DEFAULT_RULES
        if caller_authority_name in self._AUTHORITY_SPECIFIC_RULES:
            rules = self._AUTHORITY_SPECIFIC_RULES[caller_authority_name]
        self._logger.debug("Rules for %s : %s" % (caller_urn, rules.getLabel()))
        return rules

    # Bind all bindings in current context
    # For all assertions, evaluate precondition and if True, 
    #   Generate corresponding ABAC assertions 
    # Try to prove all the positive queries and none of the negative queries
    def authorize(self, method, caller, creds, args, opts,
                  requested_allocation_state):
        Base_Authorizer.authorize(self, method, caller, creds, args, opts,
                                  requested_allocation_state)
#        self._logger.info("RAS = %s" % requested_allocation_state)
#        self._logger.info("In ABAC AUTHORIZER...")

        rules = self.lookup_rules_for_caller(caller)

        caller_keyid = self._compute_keyid(cert_string=caller)
        key_id_name_map = rules.getKeyIdNameMap()
        key_id_name_map[caller_keyid] = "$CALLER"

        bindings = self._generate_bindings(method, caller, creds, args, opts,
                                           requested_allocation_state, rules)

        # Add 'constants' to bindings
        bindings = dict(bindings.items() + rules.getConstants().items())

#        self._logger.info("BINDINGS = %s" % bindings)

        assertions = self._generate_assertions(bindings, rules)

        credential_assertions = \
            self._generate_credential_assertions(caller, creds, bindings, rules)

        fixed_policies = rules.getPolicies()

        assertions = \
            assertions + credential_assertions + fixed_policies

#        self._logger.info("ASSERTIONS = %s" % assertions)

        success, msg = self._evaluate_queries(bindings, assertions, rules)

        del key_id_name_map[caller_keyid]

        if not success:
            raise Exception(msg)

    # Get each binder to generate bindings
    def _generate_bindings(self, method, caller, creds, args, opts,
                           requested_state, rules):
        bindings = {}
        for binder in rules.getBinders():
            new_bindings = binder.generate_bindings(method, caller, creds,
                                                    args, opts,
                                                    requested_state)
            bindings = dict(bindings.items() + new_bindings.items())
        return bindings

    # For each conditional assertion, evaluate the condition
    # If true and if the associated assertion is completely bound,
    # generate the assertion
    def _generate_assertions(self, bindings, rules):
        assertions = []
        conditional_assertions = rules.getConditionalAssertions()

        # Handle old format of policies that are list of condition/assertion
        # rather than list of precondition/exclusive and then a list
        # of condition/assertion clauses
        if len(conditional_assertions) > 0 and \
                'precondition' not in conditional_assertions[0]:
            conditional_assertions = [{'precondition' : 'True',
                                      'clauses' : conditional_assertions}]

        for clause_set in conditional_assertions:
            precondition = clause_set['precondition']
            bound_precondition = self._bind_expression(precondition, bindings)
            if self._has_unbound_variables(bound_precondition): continue
            if not eval(bound_precondition): continue
            exclusive = 'exclusive' in clause_set and clause_set['exclusive']
            clauses = clause_set['clauses']
            for ca in clauses:
                condition = ca['condition']
                assertion = ca['assertion']
                bound_condition = self._bind_expression(condition, bindings)
                if self._has_unbound_variables(bound_condition): continue
                self._logger.info("EVAL : %s" % bound_condition)
                if not eval(bound_condition): continue
                bound_assertion = self._bind_expression(assertion, bindings)
                if self._has_unbound_variables(bound_assertion): continue
                assertions.append(bound_assertion)
            # If this is an exclusive clause set whose precondition matched
            # Don't look at any other clause sets
            if exclusive: break 
        return assertions

    # If provided a set of ABAC assertions, import them into our set
    # of assertions
    def _generate_credential_assertions(self, caller, creds, bindings, rules):
        assertions = []
        abac_cred_objects = [CredentialFactory.createCred(credString=cred) \
                                 for cred in creds \
                                 if CredentialFactory.getType(cred) == \
                                 ABACCredential.ABAC_CREDENTIAL_TYPE]
        for abac_cred in abac_cred_objects:
            head_principal = abac_cred.head.get_principal_keyid()
            head_principal_name = rules._lookup_name_from_keyid(head_principal)
            head_role = abac_cred.head.get_role()
            tail = abac_cred.tails[0] # Only take the first one
            tail_principal = tail.get_principal_keyid()
            tail_principal_name = rules._lookup_name_from_keyid(tail_principal)
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

    # Determine if all positive queries are proven and no negative
    # query is proven
    def _evaluate_queries(self, bindings, assertions, rules):

        messages = []

        all_positive_proved = True
        for q in rules.getPositiveQueries():
            evaluated, proven, msg = \
                self._evaluate_query(bindings, assertions, q, rules)
            if not evaluated: continue
            if not proven:
                all_positive_proved = False
                messages.append(msg)

        all_negative_disproved = True
        for q in rules.getNegativeQueries():
            evaluated, proven, msg = \
                self._evaluate_query(bindings, assertions, q, rules)
            if not evaluated: continue
            if proven:
                all_negative_disproved = False
                messages.append(msg)

        result = (all_positive_proved and all_negative_disproved)
        return result, ", ".join(messages)

    # Evaluate a single query
    # If there is a condition, it must be true to considered
    # Return evaluated, evaluation, failure_message
    def _evaluate_query(self, bindings, assertions, query, rules):
        # If there is a condition on this query, only evaluate if 
        # condition is satisfied
        if query in rules.getQueryConditionMap():
            condition = rules.getQueryConditionMap()[query]
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
        msg = rules.getQueryMessageMap()[query]
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
            assertion_info = {'rhs' : assert_rhs, 'assertion' : assertion}
            parsed_assertions[assert_lhs].append(assertion_info)

        result, chain = \
            self._prove_query_internal(query_lhs, query_rhs, parsed_assertions)

        self._logger.info("QUERY (%s) : %s" % (result, query))
        if result:
            self._logger.info("PROOF_CHAIN : %s" % chain)
        return result

    # Internal method supporting _prove_query as a recursive call
    # Return the proof chain if success
    def _prove_query_internal(self, lhs, target, parsed_assertions):
        if lhs not in parsed_assertions: return False, None

        found_direct_link = False
        for pa in parsed_assertions[lhs]:
            rhs = pa['rhs']
            assertion = pa['assertion']
            if rhs == target:
                found_direct_link = True
                break
        if found_direct_link:
            return True, [assertion]


        found_indrect_link = False
        for pa in parsed_assertions[lhs]:
            new_lhs = pa['rhs']
            assertion = pa['assertion']
            result, chain = \
                self._prove_query_internal(new_lhs, target, parsed_assertions)
            if result:
                new_chain = list(chain)
                new_chain.insert(0, assertion)
                return True, new_chain
        return False, None

    # Compute keyid from a cert
    @staticmethod
    def _compute_keyid(cert_string=None, cert_filename=None):
        if cert_string:
            cert_gid = gid.GID(string=cert_string)
        else:
            cert_gid = gid.GID(filename=cert_filename)
        extension_names = [ext[0] for ext in cert_gid.get_extensions()]
        if 'subjectKeyIdentifier' not in extension_names:
            return None
        return get_cert_keyid(cert_gid)

    def validate_arguments(self, method_name, arguments, options):
        if self._argument_guard:
            return self._argument_guard.validate_arguments(method_name, 
                                                           arguments, options)
        else:
            return arguments, options

# Class to hold the rules to be invoked for members of a given authority
# We have per-authority rule sets and a default rule set
class ABAC_Authorizer_Rule_Set:

    def __init__(self, label, root_cert):
        self._label = label
        self._root_cert = root_cert
        self._identities = {}
        self._binders = []
        self._constants = {}
        self._conditional_assertions = []
        self._policies = []
        self._queries = []
        self._positive_queries = []
        self._negative_queries = []
        self._query_message_map = {}
        self._query_condition_map = {}
        self._keyid_name_map = {}

    # Parse rule content from a file and add to existing rule content (if any)
    # That is, we may parse multiple files in sequence, thus adding to lists
    # and adding/replacing elements in dictionaries
    def parse(self, filename):
        data = open(filename).read()
        raw_rules = json.loads(data)

        if 'binders' in raw_rules:
            for b in raw_rules['binders']:
                binder = self._initialize_binder(b)
                self._binders.append(binder)

        if 'constants' in raw_rules:
            self._constants = \
                dict(self._constants.items() + raw_rules['constants'].items())

        if 'conditional_assertions' in raw_rules:
            self._conditional_assertions = \
                self._conditional_assertions + raw_rules['conditional_assertions']

        if 'policies' in raw_rules:
            self._policies = self._policies + raw_rules['policies']

        if 'queries' in raw_rules:
            new_positive_queries = \
                [q['statement'] for q in raw_rules['queries'] \
                     if q['is_positive']]
            self._positive_queries = self._positive_queries + new_positive_queries

            new_negative_queries = \
                [q['statement'] for q in raw_rules['queries']\
                     if not q['is_positive']]
            self._negative_queries = self._negative_queries + new_negative_queries

            for q in raw_rules['queries']:
                self._query_message_map[q['statement']] = q['message']

            for q in raw_rules['queries']:
                if 'condition' in q:
                    self._query_condition_map[q['statement']] = q['condition']

        if 'identities' in raw_rules:
            for id_name, id_pem in raw_rules['identities'].items():
                id_keyid = ABAC_Authorizer._compute_keyid(cert_filename=id_pem)
                if id_keyid:
                    self._keyid_name_map[id_keyid] = id_name

    # Dump contents to stdout
    def dump(self):
        print "RULE SET : %s" % self._label
        print 'BINDERS:'
        for binder in self._binders:
            print "   %s" % binder
        print "CONSTANTS:"
        print "   %s" % self._constants
        print "CONDITIONAL ASSERTIONS:"
        print "   %s" % self._conditional_assertions
        print "POLICIES:"
        for policy in self._policies:
            print "   %s" % policy
        print "POSITIVE QUERIES:"
        for pos in self._positive_queries:
            print "   %s" % pos
        print "NEGATIVE QUERIES:"
        for neg in self._negative_queries:
            print "   %s" % neg
        print "QUERY_MESSAGE_MAP:"
        print "   %s" % self._query_message_map
        print "QUERY_CONDITION_MAP:"
        print "   %s" % self._query_condition_map
        print "KEYID_NAME_MAP:"
        print "   %s" % self._keyid_name_map

    # Find the name assocaited to a given keyid
    def _lookup_name_from_keyid(self, keyid):
        if keyid not in self._keyid_name_map:
            raise Exception("Unknown keyid : %s" % keyid)
        return self._keyid_name_map[keyid]

    # Initialize a binder from its classname
    def _initialize_binder(self, binder_classname):
        return getInstanceFromClassname(binder_classname, self._root_cert)

    # Accessors to rule content
    def getIdentities(self) : return self._identities
    def getBinders(self) : return self._binders
    def getConstants(self) : return self._constants
    def getConditionalAssertions(self) : return self._conditional_assertions
    def getPolicies(self) : return self._policies
    def getPositiveQueries(self) : return self._positive_queries
    def getNegativeQueries(self) : return self._negative_queries
    def getLabel(self) : return self._label
    def getQueryMessageMap(self): return self._query_message_map
    def getQueryConditionMap(self): return self._query_condition_map
    def getKeyIdNameMap(self) : return self._keyid_name_map
