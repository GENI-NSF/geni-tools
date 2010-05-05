URN_PREFIX = "urn:publicid:IDN+"

def short_urn(urn):
    return urn[len(URN_PREFIX):]

def long_urn(urn):
    if not urn.startswith(URN_PREFIX):
        return URN_PREFIX + urn
    else:
        return urn
    