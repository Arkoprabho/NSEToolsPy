"""
Contains the core APIs
"""
import ast
import re
import json
import os
import csv

from urllib.parse import urlencode
from functools import lru_cache
from datetime import  timedelta, datetime
from multiprocessing.pool import ThreadPool
from dateutil.parser import parse

from bs4 import BeautifulSoup

import pandas as pd

from nsetools.utils import js_adaptor
from nsetools.net_utils import read_url

class NseHolidays():
    """
    Contains methods to parse and extract data about the holidays of NSE
    """
    def get_holiday_list(self):
        """
        Cleans the holiday list
        """
        holiday_list = self.__parse_holiday_list__()
        clean_holiday_list = []
        for item in holiday_list:
            individual_data = []
            # Each row is separated by commas.
            reader = csv.reader(item, delimiter=',')
            for row in reader:
                individual_data.append(row)
            clean_holiday_list.append(individual_data[:2])

        previous = 0
        holiday_list = []
        # These are all the holidays excluding saturdays and sundays
        todays_date = datetime.now().date()
        for  series in clean_holiday_list:
            # We wish to extract only the trading holidays.
            # The serial number resets after trading holidays i.e when it moves to clearing holidays
            if previous < int(series[0][0]):
                # Convert to datetime format
                parsed_date = parse(series[1][0])
                if todays_date <= parsed_date.date():
                    holiday_list.append(parsed_date.date())
                previous += 1

        # We will now extract the saturdays and sundays
        date = todays_date
        date += timedelta(days=6-date.weekday())
        diff = date - timedelta(days=1)
        while date.year == todays_date.year:
            holiday_list.append(diff)
            holiday_list.append(date)
            date += timedelta(days=7)
            diff += timedelta(days=7)

        # This is the final holiday list from the current time.
        return holiday_list

    @lru_cache(maxsize=2)
    def __parse_holiday_list__(self):
        """
        :Returns: a list of all the holidays with the serial number, date and holiday name
        """
        # Parse the holiday url and extract useful details
        holiday_url = 'https://www.nseindia.com/products/content/equities/equities/mrkt_timing_holidays.htm'
        headers = {'Accept': '*/*',
                   'Accept-Language': 'en-US,en;q=0.5',
                   'Host': 'nseindia.com',
                   'Referer': "https://www.nseindia.com/live_market/dynaContent/live_watch/get_quote/GetQuote.jsp?symbol=INFY&illiquid=0&smeFlag=0&itpFlag=0",
                   'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:28.0) Gecko/20100101 Firefox/28.0',
                   'X-Requested-With': 'XMLHttpRequest'
                   }
        res = read_url(holiday_url, headers)
        res = res.read()
        
        soup = BeautifulSoup(res, 'html.parser')
        holiday_list = []
        # The data is stored in tables. Extract only the tabular data
        for row in soup.find_all('tr', recursive=False):
            record = [td.text.replace(',', '') for td in row.find_all('td')]
            holiday_list.append(record)

        return holiday_list

def conditional_decorator(decorator, condition):
    def res_decorator(f):
        if not condition:
            return f
        return decorator(f)
    return res_decorator

def market_status():
    """
    Checks whether the market is open or not
    :returns: bool variable indicating status of market. True -> Open, False -> Closed
    """
    nse_holidays = NseHolidays()
    holiday_list = nse_holidays.get_holiday_list()

    # Check if today is a holiday according to the holiday list.
    if datetime.now().date() in holiday_list:
        return False

    current_time = datetime.now().time()
    # Check if the current time is in the time bracket in which NSE operates.
    # The market opens at 9:15 am
    start_time = datetime.now().time().replace(hour=9, minute=15, second=0, microsecond=0)
    # And ends at 3:30 = 15:30
    end_time = datetime.now().time().replace(hour=15, minute=30, second=0, microsecond=0)

    if current_time > start_time and current_time < end_time:
        return True

    # In case the above condition does not satisfy, the default value (False) is returned
    return False

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
            file_caching: (optional) bool variable to indicate whether to use files
            for caching of non changing data
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
        self.get_history_url = 'https://www.nseindia.com/products/dynaContent/common/productsSymbolMapping.jsp?'

        self.__cache_size__ = cache_size

    @lru_cache(maxsize=__cache_size__)
    def get_stock_codes(self):
        """
        Retreives the equity list from NSE, and stores it in a dataframe.
        
        :Parameters:
        cached: bool
            Whether to cache the data or not. Prefer keeping this true unless you are running into OOM issues.
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

    @conditional_decorator(lru_cache(maxsize=__cache_size__), not market_status())
    def get_quote(self, *codes, as_json=False):
        """
        gets the quote for a given stock code
        :param codes: 
        :return: pandas DataFrame with quotes of all companies codes passed.
        :raises: HTTPError, URLError
        """
        def __get_quote__(code):
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
                except Exception:
                    raise Exception('Symbol Not Traded today')
                else:
                    rendered_response = self.render_response(response, as_json)
                    # Check if the market is open (to avoid repeated network computation)
                return rendered_response
        with ThreadPool(os.cpu_count()*2) as pool:
            quotes = pool.map(__get_quote__, codes)
        if as_json:
            return quotes
        # Filter out all the Nones from the list
        quotes = [x for x in quotes if x is not None]
        if quotes:
            return pd.DataFrame(quotes).set_index('symbol')
    
    @conditional_decorator(lru_cache(maxsize=__cache_size__), not market_status())
    def get_history(self, *codes_dates, as_json=False):
        """
        Gets the historical data between the given date range (inclusive of both).
        One can pass tuples of code, from_date and to_date to retreive multiple codes at once
        :param: (codes_dates): should be a tuple containing 3 items as following
        code: the symbol of the company you want to get the history of
        from_date: the date from which history is to be retreived (can be a string in the format DD MM YYYY or a datetime.date object)
        to_date: the last date upto which the history is to be retreived (can be a string in the format DD MM YYYY or a datetime.date object)

        :returns: a pandas dataframe indexed by date containing the history of the symbol in the given date range
        """
        # Can we not get data for more than 100 days.
        # To get data for 365 days, we got to download the csv. The csv does not seem to be downloading from a url
        # So currently we get the data in batches of 100
        @conditional_decorator(lru_cache(maxsize=self.__cache_size__), not market_status())
        def __get_history__(code_date):
            code = code_date[0].upper()
            history_df = pd.DataFrame()
            if self.is_valid_code(code):
                # Parse the dates in the correct format
                if not isinstance(code_date[1], datetime):
                    start = parse(code_date[1], dayfirst=True)
                if not isinstance(code_date[2], datetime):
                    end = parse(code_date[2], dayfirst=True)
                # Find the difference between the dates and generate batches of 100 days till the end date
                difference = (end - start).days
                if difference > 100:
                    curr_end = start + timedelta(days=100)
                    while curr_end < end:
                        url = self.build_url_for_history(code_date[0], datetime.strftime(start, '%d-%m-%Y'), datetime.strftime(curr_end, '%d-%m-%Y'))
                        res = read_url(url, self.headers)
                        res = res.read()
                        history_df = history_df.append(pd.read_html(res, header=0, index_col='Date')[0])
                        start = curr_end + timedelta(days=1)
                        curr_end += timedelta(days=100)
                    url = self.build_url_for_history(code_date[0], datetime.strftime(start, '%d-%m-%Y'), datetime.strftime(end, '%d-%m-%Y'))
                    res = read_url(url, self.headers)
                    res = res.read()
                    history_df = history_df.append(pd.read_html(res, header=0, index_col='Date')[0])
                if as_json:
                    return history_df.to_json()
                return history_df
        
        with ThreadPool(os.cpu_count() * 2) as pool:
            quotes = pool.map(__get_history__, codes_dates)
            if len(quotes) == 1:
                return quotes[0]
            return quotes

            
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
                except Exception:
                    pass
                # We dont care about this. Throw it out
                start = end + 1

            return data.to_json() if as_json else data

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
            'GAINERS': self.get_top_gainers,
            'LOSERS': self.get_top_losers,
            'VOLUME': self.get_top_volume,
            'ACTIVE': self.get_most_active,
            'ADVANCES DECLINE': self.get_advances_declines,
            'INDEX LIST': self.get_index_list
        }
        for item in options:
            function_to_call = possible_options.get(item.upper())
            if function_to_call is not None:
                yield function_to_call(as_json)

    @conditional_decorator(lru_cache(maxsize=__cache_size__), not market_status())
    def get_top_gainers(self, as_json=False):
        """
        :return: pandas DataFrame | JSON containing top gainers of the day
        """
        url = self.top_gainer_url
        res = read_url(url, self.headers)
        res_dict = json.load(res)
        # clean the output and make appropriate type conversions
        res_list = [self.clean_server_response(
            item) for item in res_dict['data']]
        response = self.render_response(res_list, as_json)
        if as_json:
            return response
        else:
            return pd.DataFrame(response).set_index('symbol')

    @conditional_decorator(lru_cache(maxsize=__cache_size__), not market_status())
    def get_top_losers(self, as_json=False):
        """
        :return: pandas DataFrame | JSON containing top losers of the day
        """
        url = self.top_loser_url
        res = read_url(url, self.headers)
        res_dict = json.load(res)
        # clean the output and make appropriate type conversions
        res_list = [self.clean_server_response(item)
                    for item in res_dict['data']]
        response = self.render_response(res_list, as_json)
        if as_json:
            return response
        else:
            return pd.DataFrame(response).set_index('symbol')

    @conditional_decorator(lru_cache(maxsize=__cache_size__), not market_status())
    def get_top_volume(self, as_json=False):
        """
        :return: pandas DataFrame | JSON containing top volume gainers of the day
        """
        url = self.top_volume_url
        res = read_url(url, self.headers)
        res_dict = json.load(res)
        # clean the output and make appropriate type conversions
        res_list = [self.clean_server_response(
            item) for item in res_dict['data']]
        response = self.render_response(res_list, as_json)
        if as_json:
            return response
        else:
            return pd.DataFrame(response).set_index('sym')

    @conditional_decorator(lru_cache(maxsize=__cache_size__), not market_status())
    def get_most_active(self, as_json=False):
        """
        :return: pandas DataFrame | JSON containing most active equites of the day
        """
        url = self.most_active_url
        res = read_url(url, self.headers)
        res_dict = json.load(res)
        # clean the output and make appropriate type conversions
        res_list = [self.clean_server_response(
            item) for item in res_dict['data']]
        response = self.render_response(res_list, as_json)
        if as_json:
            return response
        else:
            return pd.DataFrame(response).set_index('symbol')

    @conditional_decorator(lru_cache(maxsize=__cache_size__), not market_status())
    def get_advances_declines(self, as_json=False):
        """
        :return: pandas DataFrame | JSON with advance decline data
        :raises: URLError, HTTPError
        """
        url = self.advances_declines_url
        resp = read_url(url, self.headers)
        resp_dict = json.load(resp)
        resp_list = [self.clean_server_response(item)
                     for item in resp_dict['data']]
        response = self.render_response(resp_list, as_json)
        if as_json:
            return response
        else:
            return pd.DataFrame(response).set_index('indice')

    @lru_cache(maxsize=__cache_size__)
    def get_index_list(self, as_json=False):
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
        index_list = self.get_index_list()
        return True if code.upper() in index_list else False

    @conditional_decorator(lru_cache(maxsize=__cache_size__), not market_status())
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

    def build_url_for_history(self, code, from_date, to_date):
        """
        builds a url which can be requested for a given stock code
        :param: code: string containing the stock code
        :return: a string containing the url
        """
        'https://www.nseindia.com/products/dynaContent/common/productsSymbolMapping.jsp?symbol=INFY&segmentLink=3&symbolCount=1&series=ALL&dateRange=+&fromDate=04-01-2017&toDate=05-04-2017&dataType=PRICEVOLUMEDELIVERABLE'
        if code is not None and isinstance(code, str):
            encoded_args = urlencode(
                [
                    ('symbol', code), ('segmentLink', 3), ('symbolCount', 1), ('series', 'ALL'),
                    ('dateRange', '+'), ('fromDate', from_date), ('toDate', to_date), ('dataType', 'PRICEVOLUMEDELIVERABLE')
                ]
            )
            return self.get_history_url + encoded_args
        else:
            raise Exception('Code must be string')

    def build_url_for_quote(self, code):
        """
        builds a url which can be requested for a given stock code
        :param code: string containing stock code.
        :return: a url object
        """
        if code is not None and isinstance(code, str):
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

# TODO: This is IO bound, lets find a way to optimize this, so that mutliple requests can be made at the same time.
# CHECK: Whether this works in Linux. Last i checked it wasnt passing all the tests
# TODO: concept of portfolio for fetching price in a batch and field which should be captured
# TODO: Concept of session, just like as in sqlalchemy
