"""
Contains methods to handle and monitor the cache.
"""
import os

from tempfile import gettempdir

class CacheHandler():
    """
    Handles the cache for all stock codes, quotes and others
    """
    # Points to note:
    # The stock codes file (the file that stores all the stock codes) will be refreshed every week.
    # Individual quotes will be cached only if the market is closed and will be refreshed every day.
    # All cache will be in the temporary folder.
    def __init__(self, **kwargs):
        self.nse = Nse()
    @staticmethod
    def get_cache_directory():
        """
        :Returns: str, the cache directory to store the files in.
        """
        directory = os.path.join(gettempdir(), 'nsetools')
        if not os.path.exists(directory):
            os.makedirs(directory)
        return directory

    @staticmethod
    def get_cache_file(func):
        """
        :Returns: str, the cache file associated with the function.
        Each function is associated with a cache file.
        """
        # The  file names associated with each method
        file_name = {
            '__get_advances_declines__': 'advances_decline.csv',
            '__get_index_list__': 'index_list.csv',
            '__get_most_active__': 'active.csv',
            '__get_top_gainers__': 'gainers.csv',
            '__get_top_losers__': 'losers.csv',
            '__get_top_volume__': 'volume.csv',
            'get_index_quote': 'index_quote.csv',
            'get_peer_companies': 'peers.csv',
            'get_quote': 'quotes.csv',
            'get_stock_codes': 'stock_codes.csv'
            }
        file_path = os.path.join(CacheHandler.get_cache_directory(), file_name.get(func))
        return file_path

    def cache_peers(self):
        """
        Caches all the peer companies of all the companies listed in NSE
        """
        # We are concerned only with the symbols.
        pass