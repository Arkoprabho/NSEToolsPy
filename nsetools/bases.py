"""
The base class for all implementation
"""

from abc import ABCMeta, abstractmethod


class AbstractBaseExchange(metaclass=ABCMeta):

    @abstractmethod
    def get_stock_codes(self, cached, as_json):
        """
        :return: list of tuples with stock code and stock name
        """
        raise NotImplementedError

    @abstractmethod
    def is_valid_code(self, code):
        """
        :return: True, if it is a valid stock code, else False
        """
        raise NotImplementedError

    @abstractmethod
    def get_quote(self, code):
        """
        :param code: a stock code
        :return: a dictionary which contain detailed stock code.
        """
        raise NotImplementedError

    @abstractmethod
    def get_top_gainers(self):
        """
        :return: a sorted list of codes of top gainers
        """
        raise NotImplementedError

    @abstractmethod
    def get_top_losers(self):
        """
        :return: a sorted list of codes of top losers
        """
        raise NotImplementedError

    @abstractmethod
    def __str__(self):
        """
        :return: market name
        """
        raise NotImplementedError
