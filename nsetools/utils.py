"""
Contains utility funtions to aid parsing
"""
import re
import sys
import io
import os
import pandas as pd


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

def save_file(dataframe, extension, **options):
    """
    Saves the dataframe to the specified location
    :Parameters:
        dataframe: Pandas DataFrame, the dataframe to store
        extension: the extension to store it as. Can be one of csv, xl
    :Returns: A represention in the form of the extension provided. If path is specified, then it is saved to the path with apt extension
    """
    path = options.get('path')
    file_name = options.get('name')
    if path and file_name:
        file_name += '.' + extension
        file_path = os.path.join(path, file_name)
        saving_function = {
            'CSV': pd.DataFrame.to_csv,
            'HDF': pd.DataFrame.to_hdf,
            'JSON': pd.DataFrame.to_json,
            'FEATHER': pd.DataFrame.to_feather,
            'HTML': pd.DataFrame.to_html,
            'TEX': pd.DataFrame.to_latex
        }
        function_to_call = saving_function.get(extension.upper())
        with open(file_path, 'w', encoding='utf8') as f:
            if function_to_call:
                if extension.upper() in ['CSV', 'TEX']:
                    f.write(function_to_call(dataframe, index=False))
                else:
                    f.write(function_to_call(dataframe))
    if function_to_call:
        return function_to_call(dataframe)