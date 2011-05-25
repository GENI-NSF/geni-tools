class OmniError(Exception):
    """Simple Exception wrapper marking fatal but anticipated omni
    errors (EG missing arguments, error in input file).

    Omni function callers typically catch these, then print the
    message but not the stack trace.

    """
    pass
