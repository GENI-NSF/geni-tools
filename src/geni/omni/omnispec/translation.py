""" Translate between RSpecs and OmniSpecs

    OmniSpecs are generalized RSpecs, capable of representing
    RSpecs from many types of aggregates.  OmniSpecs contain
    the data necessary to be translated back into a native RSpec.
"""


mod_name = 'geni.omni.omnispec'


def rspec_to_omnispec(urn, rspec):        
    trans_mod = __import__(mod_name,fromlist=[mod_name])
    translators = trans_mod.all
    
    mod = None
    for translator in translators:
        mod = __import__(mod_name + '.' + translator, fromlist=[mod_name])
        if mod.can_translate(urn, rspec):
            break
        else:
            mod = None
    
    if mod:
        return mod.rspec_to_omnispec(urn, rspec)
    
    raise Exception('Unknown RSpec Type')
    
    

def omnispec_to_rspec(omnispec, filter_allocated):
    mod = __import__(mod_name + '.' + omnispec.get_type(), fromlist=[mod_name])
    return mod.omnispec_to_rspec(omnispec, filter_allocated)

