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

# AM authorizer class that uses policies to generate ABAC proofs 
# for authorization decisions

import gcf
import json
from .base_authorizer import *

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

    # Bind all bindings in current context
    # For all assertions, evaluate precondition and if True, 
    #   Generate corresponding ABAC assertions 
    # Try to prove all the positive queries and none of the negative queries
    def authorize(self, method, caller, creds, args, opts, agg_mgr):
        Base_Authorizer.authorize(self, method, caller, creds, args, 
                                  opts, agg_mgr)
        self._logger.info("In ABAC AUTHORIZER...")

        bindings = self._generate_bindings(method, caller, creds, args, 
                                           opts, agg_mgr)

        self._logger.info("BINDINGS = %s" % bindings)

        assertions = self._generate_assertions(bindings)

        self._logger.info("ASSERTIONS = %s" % assertions)

        success, msg = self._evaluate_queries(bindings, assertions)
        if not success:
            raise Exception(msg)

    # Get each binder to generate bindings
    def _generate_bindings(self, method, caller, creds, args, opts, agg_mgr):
        bindings = {}
        for binder in self._binders:
            new_bindings = binder.generate_bindings(method, caller, creds,
                                                    args, opts, agg_mgr)
            bindings = dict(bindings.items() + new_bindings.items())
        return bindings

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
            

    # Determine if all positive queries are proven and no negative
    # query is proven
    def _evaluate_queries(self, bindings, assertions):

        messages = []

        all_positive_proved = True
        for q in self._positive_queries:
            bound_q = self._bind_expression(q, bindings)
            if self._has_unbound_variables(bound_q): 
                raise Exception("Illegal query: unbound variable %s" % bound_q)
            if not self._prove_query(bound_q, assertions):
                all_positive_proved = False
                messages.append(self._query_message_map[q])

        all_negative_disproved = True
        for q in self._negative_queries:
            bound_q = self._bind_expression(q, bindings)
            if self._has_unbound_variables(bound_q): 
                raise Exception("Illegal query: unbound variable %s" % bound_q)
            if self._prove_query(bound_q, assertions):
                all_negative_disproved = False
                messages.append(self._query_message_map[q])

        result = (all_positive_proved and all_negative_disproved)
        return result, ", ".join(messages)

    # Replace bindings ($VAR) with bound value
    def _bind_expression(self, expr, bindings):
        for binding, value in bindings.items():
            if expr.find(binding) > -1:
                expr = expr.replace(binding, value)
        return expr

    # Are there any unbound variables in expression?
    def _has_unbound_variables(self, expr):
        return expr.find("$") > -1
        

    def _prove_query(self, query, assertions):

        # *** WRITE A REAL PROVER ***
        result = (query in assertions)
        self._logger.info("QUERY (%s) : %s" % (result, query))
        return result

    def _initialize_binder(self, binder_classname):
        binder_class_module = ".".join(binder_classname.split('.')[:-1])
        __import__(binder_class_module)
        binder_class = eval(binder_classname)
        binder = binder_class(self._root_cert)
        return binder

    # Hand the result of a success call to each binder to update
    # its internal state
    def handleResult(self, method, caller, args, opts, result, agg_mgr):
        for binder in self._binders:
            binder.handle_result(method, caller, args, opts, result, agg_mgr)



