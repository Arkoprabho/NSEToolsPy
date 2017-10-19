"""
Contains utility functions related to the internet
"""

from nsetools.utils import byte_adaptor

from urllib.request import build_opener, HTTPCookieProcessor, Request
from http.cookiejar import CookieJar

def __opener__():
    """
    Builds the opener for the url
    :returns: opener object
    """

    cookie_jar = CookieJar()
    return build_opener(HTTPCookieProcessor(cookie_jar))


def read_url(url, headers):
    """
    Reads the url, processes it and returns a StringIO object to aid reading
    :Parameters:
    url: str
        the url to request and read from
    headers: dict
        The right set of headers for requesting from http://nseindia.com
    :returns: _io.StringIO object of the response
    """
    request = Request(url, None, headers)
    response = __opener__().open(request)

    if response is not None:
        return byte_adaptor(response)
    else:
        raise Exception('No response received')

