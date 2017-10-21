# Objective

This project is a fork of [nsetools](https://github.com/vsjha18/nsetools). The main objective of this project is to modify the API to a more data centric approach and to fix the flaws already existing.

Planned functionalities

1. Using pandas to aid management of data
2. Add proper caching facility wherever possible

While implementing these changes we will try to keep the usage method as close to original as possible

To achieve this we will have to make a few breaking changes.

1. **Python 2 compatibility.** We cannot ensure python 2 compatibility. Although this project will work with python 3+
2. **DataFrames instead of dictionaries.** We will be using pandas dataframes wherever possible instead of dictionaries and lists. This will allow us to add complicated functionalities.

nsetools
========

Python library for extracting realtime data from National Stock Exchange (India)

Introduction.
============

nsetools is a library for collecting real time data from National Stock Exchange (India). It can be used in various types of projects which requires getting live quotes for a given stock or index or build large data sets for further data analytics. You can also build cli applications which can provide you live market details at a blazing fast speeds, much faster that the browsers. The accuracy of data is only as correct as provided on www.nseindia.com.

Main Features:
=============

* Getting live quotes for stocks using stock codes.
* Return data in both json and python dict and list formats.
* Getting quotes for all the indices traded in NSE, e.g CNX NIFTY, BANKNIFTY etc.
* Getting list of top losers.
* Getting list of top gainers.
* Helper APIs to check whether a given stock code or index code is correct.
* Getting list of all indices and stocks.
* Cent percent unittest coverage.

Dependencies
=============
It is advised to use [Anaconda python 3.6](https://www.anaconda.com/download/) as there is extensive use of pandas along with other libraries.

Note: To use the API you will need an active internet connection

Detailed Documenation 
=====================

For complete documentation of this project refer to https://arkoprabho.github.io/nsetools3/