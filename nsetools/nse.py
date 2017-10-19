"""
Contains the core APIs
"""
import ast
import re
import json

from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.parse import urlencode
from http.cookiejar import CookieJar

from nsetools.utils import byte_adaptor
from nsetools.utils import js_adaptor


class Nse():
    """
    class which implements all the functionality for
    National Stock Exchange
    """
    __CODECACHE__ = None

    def __init__(self):
        self.opener = self.nse_opener()
        self.headers = self.nse_headers()
        # URL list
        self.get_quote_url = 'https://www.nseindia.com/live_market/dynaContent/live_watch/get_quote/GetQuote.jsp?'
        self.stocks_csv_url = 'http://www.nseindia.com/content/equities/EQUITY_L.csv'
        self.top_gainer_url = 'http://www.nseindia.com/live_market/dynaContent/live_analysis/gainers/niftyGainers1.json'
        self.top_loser_url = 'http://www.nseindia.com/live_market/dynaContent/live_analysis/losers/niftyLosers1.json'
        self.top_volume_url = 'http://www.nseindia.com/live_market/dynaContent/live_analysis/volume_spurts/volume_spurts.json'
        self.most_active_url = 'https://nseindia.com/live_market/dynaContent/live_analysis/most_active/allTopValue1.json'
        self.advances_declines_url = 'http://www.nseindia.com/common/json/indicesAdvanceDeclines.json'
        self.index_url = "http://www.nseindia.com/homepage/Indices1.json"
        self.peer_companies_url = 'https://nseindia.com/live_market/dynaContent/live_watch/get_quote/ajaxPeerCompanies.jsp?symbol='
        # None indicates that the default value is stored and we havent checked for it.
        self.is_market_open = (False, None)

    def get_stock_codes(self, cached=True, as_json=False):
        """
        returns a dictionary with key as stock code and value as stock name.
        It also implements cache functionality and hits the server only
        if user insists or cache is empty
        :return: dict
        """
        url = self.stocks_csv_url
        req = Request(url, None, self.headers)
        res_dict = {}
        if cached is not True or self.__CODECACHE__ is None:
            # raises HTTPError and URLError
            res = self.opener.open(req)
            if res is not None:
                # string file like object
                res = byte_adaptor(res)
                for line in res.read().split('\n'):
                    if line != '' and re.search(',', line):
                        (code, name) = line.split(',')[0:2]
                        res_dict[code] = name
                    # else just skip the evaluation, line may not be a valid csv
            else:
                raise Exception('no response received')
            self.__CODECACHE__ = res_dict
        return self.render_response(self.__CODECACHE__, as_json)

    def is_valid_code(self, code):
        """
        :param code: a string stock code
        :return: Boolean
        """
        if code:
            stock_codes = self.get_stock_codes()
            if code.upper() in stock_codes.keys():
                return True
            return False

    def get_quote(self, code, as_json=False):
        """
        gets the quote for a given stock code
        :param code:
        :return: dict or None
        :raises: HTTPError, URLError
        """
        code = code.upper()
        if self.is_valid_code(code):
            url = self.build_url_for_quote(code)
            req = Request(url, None, self.headers)
            # this can raise HTTPError and URLError, but we are not handling it
            # north bound APIs should use it for exception handling
            res = self.opener.open(req)

            res = byte_adaptor(res)

            # Now parse the response to get the relevant data
            match = re.search(
                r'\{<div\s+id="responseDiv"\s+style="display:none">\s+(\{.*?\{.*?\}.*?\})',
                res.read(), re.S
            )
            # ast can raise SyntaxError, let's catch only this error
            try:
                buffer = match.group(1)
                buffer = js_adaptor(buffer)
                response = self.clean_server_response(
                    ast.literal_eval(buffer)['data'][0])
            except SyntaxError as err:
                raise Exception('ill formatted response')
            else:
                rendered_response = self.render_response(response, as_json)
                # Check if the market is open (to avoid repeated network computation)
                if not as_json and rendered_response['closePrice'] != 0.0:
                    self.is_market_open = (False, 1)
                return rendered_response
        else:
            return None

    def market_status(self):
        """
        Checks whether the market is open or not
        :returns: bool variable indicating status of market. True -> Open, False -> Closed
        """
        if self.is_market_open[1] is not None:
            return self.is_market_open[0]
        else:
            # Get a random quote to set the market status
            self.get_quote('infy')
        return self.is_market_open[0]
    def get_peer_companies(self, code, as_json=False):
        """
        :returns: a list of peer companies
        """
        code = code.upper()
        if self.is_valid_code(code):
            url = self.peer_companies_url + code
            req = Request(url, None, self.headers)
            res = self.opener.open(req)

            res = byte_adaptor(res)

            # We need to filter the data from this. The data is at an offset of 39 from the beginning and 8 at the end
            res = res.read()[39:-8]

            # Now comes the tricky batshit crazy part.
            # We will iteratively filter each company and append them to a list
            # HACK: the solution is very messy. Would be nice if a better cleaner solution can be found.
            start = 0
            data = []
            for item in re.finditer(r'({*})', res):
                # The second item. We want the curly brace for json parsing
                end = item.span()[1]
                # This is the actual data we are interested in
                string = res[start:end]
                company_info = json.loads(string)
                # We dont care about this. Throw it out
                del(company_info['industry'])
                data.append(company_info)
                start = end + 1

            return data


    def get_top(self, *options, as_json=False):
        """
        Gets the top list of the argument specified.

        :Parameters:
        as_json: bool
            Whether to return a json like string, or dict.
        option: string
            What to get top of. Possible values: gainers, losers, volume, active, advances decline, index list

        :Returns: generator that can be used to iterate over the data requested

        """
        possible_options = {
            'GAINERS': self.__get_top_gainers__,
            'LOSERS': self.__get_top_losers__,
            'VOLUME': self.__get_top_volume__,
            'ACTIVE': self.__get_most_active__,
            'ADVANCES DECLINE': self.__get_advances_declines__,
            'INDEX LIST': self.__get_index_list__
            }
        for item in options:
            function_to_call = possible_options.get(item.upper())
            if function_to_call is not None:
                yield function_to_call(as_json)

    def __get_top_gainers__(self, as_json=False):
        """
        :return: a list of dictionaries containing top gainers of the day
        """
        url = self.top_gainer_url
        req = Request(url, None, self.headers)
        # this can raise HTTPError and URLError
        res = self.opener.open(req)
        res = byte_adaptor(res)
        res_dict = json.load(res)
        # clean the output and make appropriate type conversions
        res_list = [self.clean_server_response(
            item) for item in res_dict['data']]
        return self.render_response(res_list, as_json)

    def __get_top_losers__(self, as_json=False):
        """
        :return: a list of dictionaries containing top losers of the day
        """
        url = self.top_loser_url
        req = Request(url, None, self.headers)
        # this can raise HTTPError and URLError
        res = self.opener.open(req)
        # string file like object
        res = byte_adaptor(res)
        res_dict = json.load(res)
        # clean the output and make appropriate type conversions
        res_list = [self.clean_server_response(item)
                    for item in res_dict['data']]
        return self.render_response(res_list, as_json)

    def __get_top_volume__(self, as_json=False):
        """
        :return: a lis of dictionaries containing top volume gainers of the day
        """
        url = self.top_volume_url
        req = Request(url, None, self.headers)
        # this can raise HTTPError and URLError
        res = self.opener.open(req)
        res = byte_adaptor(res)
        res_dict = json.load(res)
        # clean the output and make appropriate type conversions
        res_list = [self.clean_server_response(
            item) for item in res_dict['data']]
        return self.render_response(res_list, as_json)

    def __get_most_active__(self, as_json=False):
        """
        :return: a lis of dictionaries containing most active equites of the day
        """
        url = self.most_active_url
        req = Request(url, None, self.headers)
        # this can raise HTTPError and URLError
        res = self.opener.open(req)
        res = byte_adaptor(res)
        res_dict = json.load(res)
        # clean the output and make appropriate type conversions
        res_list = [self.clean_server_response(
            item) for item in res_dict['data']]
        return self.render_response(res_list, as_json)

    def __get_advances_declines__(self, as_json=False):
        """
        :return: a list of dictionaries with advance decline data
        :raises: URLError, HTTPError
        """
        url = self.advances_declines_url
        req = Request(url, None, self.headers)
        # raises URLError or HTTPError
        resp = self.opener.open(req)
        # string file like object
        resp = byte_adaptor(resp)
        resp_dict = json.load(resp)
        resp_list = [self.clean_server_response(item)
                     for item in resp_dict['data']]
        return self.render_response(resp_list, as_json)

    def __get_index_list__(self, as_json=False):
        """
        get list of indices and codes
        params: as_json: True | False
        returns: a list | json of index codes
        """
        url = self.index_url
        req = Request(url, None, self.headers)
        # raises URLError or HTTPError
        resp = self.opener.open(req)
        resp = byte_adaptor(resp)
        resp_list = json.load(resp)['data']
        index_list = [str(item['name']) for item in resp_list]
        return self.render_response(index_list, as_json)

    def is_valid_index(self, code):
        """
        returns: True | Flase , based on whether code is valid
        """
        index_list = self.__get_index_list__()
        return True if code.upper() in index_list else False

    def get_index_quote(self, code, as_json=False):
        """
        params:
            code : string index code
            as_json: True|False
        returns:
            a dict | json quote for the given index
        """
        url = self.index_url
        if self.is_valid_index(code):
            req = Request(url, None, self.headers)
            # raises HTTPError and URLError
            resp = self.opener.open(req)
            resp = byte_adaptor(resp)
            resp_list = json.load(resp)['data']
            # this is list of dictionaries
            resp_list = [self.clean_server_response(item)
                         for item in resp_list]
            # search the right list element to return
            search_flag = False
            for item in resp_list:
                if item['name'] == code.upper():
                    search_flag = True
                    break
            return self.render_response(item, as_json) if search_flag else None

    def nse_headers(self):
        """
        Builds right set of headers for requesting http://nseindia.com
        :return: a dict with http headers
        """
        return {'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.5',
                'Host': 'nseindia.com',
                'Referer': "https://www.nseindia.com/live_market/dynaContent/live_watch/get_quote/GetQuote.jsp?symbol=INFY&illiquid=0&smeFlag=0&itpFlag=0",
                'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:28.0) Gecko/20100101 Firefox/28.0',
                'X-Requested-With': 'XMLHttpRequest'
                }

    def nse_opener(self):
        """
        builds opener for urllib2
        :return: opener object
        """
        cj = CookieJar()
        return build_opener(HTTPCookieProcessor(cj))

    def build_url_for_quote(self, code):
        """
        builds a url which can be requested for a given stock code
        :param code: string containing stock code.
        :return: a url object
        """
        if code is not None and type(code) is str:
            encoded_args = urlencode(
                [('symbol', code), ('illiquid', '0'), ('smeFlag', '0'), ('itpFlag', '0')])
            return self.get_quote_url + encoded_args
        else:
            raise Exception('code must be string')

    def clean_server_response(self, resp_dict):
        """
        cleans the server reponse by replacing:
            '-'     -> None\n
            '1,000' -> 1000\n
        :param resp_dict:
        :return: dict with all above substitution
        """
        # change all the keys from unicode to string
        d = {}
        for key, value in resp_dict.items():
            d[str(key)] = value
        resp_dict = d
        for key, value in resp_dict.items():
            if type(value) is str:
                if '-' == value:
                    resp_dict[key] = None
                elif re.search(r'^[-]?[0-9,.]+$', value):
                    # replace , to '', and type cast to int
                    resp_dict[key] = float(re.sub(',', '', value))
                else:
                    resp_dict[key] = str(value)
        return resp_dict

    def render_response(self, data, as_json=False):
        if as_json is True:
            return json.dumps(data)
        else:
            return data

    def __str__(self):
        """
        string representation of object
        :return: string
        """
        return 'Driver Class for National Stock Exchange (NSE)'

# TODO: Use pandas dataframes
# TODO: concept of portfolio for fetching price in a batch and field which should be captured
# TODO: Concept of session, just like as in sqlalchemy
