"""
Contains utility funtions to aid parsing
"""
import re
import sys
import io

def byte_adaptor(fbuffer):
    """
    provides py3 compatibility by converting byte based
    file stream to string based file stream

    Arguments:
        fbuffer: file like objects containing bytes

    Returns:
        string buffer
    """
    strings = fbuffer.read().decode('latin-1')
    fbuffer = io.StringIO(strings)
    return fbuffer


def js_adaptor(buffer):
    """
    convert javascript objects like true, none, NaN etc. to
    quoted word.

    Arguments:
        buffer: string to be converted

    Returns:
        string after conversion
    """
    buffer = re.sub('true', 'True', buffer)
    buffer = re.sub('false', 'False', buffer)
    buffer = re.sub('none', 'None', buffer)
    buffer = re.sub('NaN', '"NaN"', buffer)
    return buffer
