"""
Contains the core APIs
"""
import ast, re, json, os, sys, inspect

from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.parse import urlencode
from http.cookiejar import CookieJar
from tempfile import gettempdir
from functools import lru_cache

import pandas as pd

from nsetools.utils import js_adaptor, save_file
from nsetools.net_utils import read_url
from nsetools.cache_handling import CacheHandler


class Nse():
    """
    class which implements all the functionality for
    National Stock Exchange
    """
    __CODECACHE__ = None
    __cache_size__ = 64

    def __init__(self, cache_size=64):
        """
        Initializes a new instance of the Nse class.
        :Parameters:
            file_caching: (optional) bool variable to indicate whether to use files for caching of non changing data
        """
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

        self.__cache_size__ = cache_size

    @lru_cache(maxsize=__cache_size__)
    def get_stock_codes(self, cached=True):
        """
        Retreives the equity list from NSE, and stores it in a dataframe.
        
        :Parameters:
        cached: bool
            Whether to cache the data or not. Prefer keeping this true unless you are running into OOM issues.
        as_json = 
        :return: pandas DataFrame
        """
        res_dataframe = pd.DataFrame()
        url = self.stocks_csv_url
        res = read_url(url, self.headers)
        column_dict = {
            0: 'Symbol',
            1: 'Name',
            2: 'Series',
            3: 'Date of Listing',
            4: 'Paid up Value',
            5: 'Market Lot',
            6: 'ISIN Number',
            7: 'Face Value'
            }
        for i, line in enumerate(res.read().split('\n')):
            if i == 0:
                # This contains the column names
                pass
            elif line != '' and re.search(',', line):
                split_line = line.split(',')
                for index, items in enumerate(split_line):
                    res_dataframe.set_value(i, column_dict[index], items)

            # else just skip the evaluation, line may not be a valid csv
        return res_dataframe
            

    @lru_cache(maxsize=__cache_size__)
    def is_valid_code(self, code):
        """
        :param code: a string stock code
        :return: bool
        """
        if code:
            stock_codes = self.get_stock_codes()
            search_result = stock_codes[stock_codes['Symbol'] == code.upper()]
            if not search_result.empty:
                return True
            return False

    def get_quote(self, *codes, as_json=False):
        """
        gets the quote for a given stock code
        :param codes: 
        :return: list of dicts with quotes of all companies codes passed.
        :raises: HTTPError, URLError
        """
        quotes = []
        for code in codes:
            code = code.upper()
            if self.is_valid_code(code):
                url = self.build_url_for_quote(code)
                res = read_url(url, self.headers)

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

                    if as_json:
                        if json.loads(rendered_response)['closePrice'] == 0:
                            self.is_market_open = (True, 1)
                    elif rendered_response['closePrice'] == 0.0:
                        self.is_market_open = (True, 1)
                    else:
                        self.is_market_open = (False, 1)
                    quotes.append(rendered_response)
        return quotes

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

    @lru_cache(maxsize=__cache_size__)
    def get_peer_companies(self, code, as_json=False):
        """
        :Parameters:
        code: str
            The code of the company to find peers of
        as_json: bool
            Whether to render the response as json
        :returns: a list of peer companies
        """
        code = code.upper()
        if self.is_valid_code(code):
            url = self.peer_companies_url + code
            res = read_url(url, self.headers)

            # We need to filter the data from this. The data is at an offset of 39 from the beginning and 8 at the end
            res = res.read()
            string_index = re.search('data:', res).span()[1]
            # Everything under 'data'
            res = res[string_index+1:]
            # Now comes the tricky batshit crazy part.
            # We will iteratively filter each company and append them to a list
            # HACK: the solution is very messy. Would be nice if a better cleaner solution can be found.
            start = 0
            data = pd.DataFrame()
            for item in re.finditer(r'({*})', res):
                # The second item. We want the curly brace for json parsing
                end = item.span()[1]
                # This is the actual data we are interested in
                string = res[start:end]
                try:
                    company_info = json.loads(string)
                    del(company_info['industry'])
                    data = data.append(company_info, ignore_index=True)
                except :
                    pass
                # We dont care about this. Throw it out
                start = end + 1

            return data

    @lru_cache(maxsize=__cache_size__)
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

    @lru_cache(maxsize=__cache_size__)
    def __get_top_gainers__(self, as_json=False):
        """
        :return: a list of dictionaries containing top gainers of the day
        """
        url = self.top_gainer_url
        res = read_url(url, self.headers)
        res_dict = json.load(res)
        # clean the output and make appropriate type conversions
        res_list = [self.clean_server_response(
            item) for item in res_dict['data']]
        return self.render_response(res_list, as_json)

    @lru_cache(maxsize=__cache_size__)
    def __get_top_losers__(self, as_json=False):
        """
        :return: a list of dictionaries containing top losers of the day
        """
        url = self.top_loser_url
        res = read_url(url, self.headers)
        res_dict = json.load(res)
        # clean the output and make appropriate type conversions
        res_list = [self.clean_server_response(item)
                    for item in res_dict['data']]
        return self.render_response(res_list, as_json)

    @lru_cache(maxsize=__cache_size__)
    def __get_top_volume__(self, as_json=False):
        """
        :return: a lis of dictionaries containing top volume gainers of the day
        """
        url = self.top_volume_url
        res = read_url(url, self.headers)
        res_dict = json.load(res)
        # clean the output and make appropriate type conversions
        res_list = [self.clean_server_response(
            item) for item in res_dict['data']]
        return self.render_response(res_list, as_json)

    @lru_cache(maxsize=__cache_size__)
    def __get_most_active__(self, as_json=False):
        """
        :return: a lis of dictionaries containing most active equites of the day
        """
        url = self.most_active_url
        res = read_url(url, self.headers)
        res_dict = json.load(res)
        # clean the output and make appropriate type conversions
        res_list = [self.clean_server_response(
            item) for item in res_dict['data']]
        return self.render_response(res_list, as_json)

    @lru_cache(maxsize=__cache_size__)
    def __get_advances_declines__(self, as_json=False):
        """
        :return: a list of dictionaries with advance decline data
        :raises: URLError, HTTPError
        """
        url = self.advances_declines_url
        resp = read_url(url, self.headers)
        resp_dict = json.load(resp)
        resp_list = [self.clean_server_response(item)
                     for item in resp_dict['data']]
        return self.render_response(resp_list, as_json)

    @lru_cache(maxsize=__cache_size__)
    def __get_index_list__(self, as_json=False):
        """
        get list of indices and codes
        params: as_json: True | False
        returns: a list | json of index codes
        """
        url = self.index_url
        resp = read_url(url, self.headers)
        resp_list = json.load(resp)['data']
        index_list = [str(item['name']) for item in resp_list]
        return self.render_response(index_list, as_json)

    @lru_cache(maxsize=__cache_size__)
    def is_valid_index(self, code):
        """
        returns: True | Flase , based on whether code is valid
        """
        index_list = self.__get_index_list__()
        return True if code.upper() in index_list else False

    @lru_cache(maxsize=__cache_size__)
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
            resp = read_url(url, self.headers)
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

# TODO: Cache using file handling. Add option in each method call to use files as cache.
# This will act as a more reliable cache. Also, we can cache market data if the market is closed.
# TODO: get quotes for a series of codes rather than just one.
# This is IO bound, lets find a way to optimize this, so that mutliple requests can be made at the same time.
# CHECK: Whether this works in Linux. Last i checked it wasnt passing all the tests
# TODO: concept of portfolio for fetching price in a batch and field which should be captured
# TODO: Concept of session, just like as in sqlalchemy
