'''
    Copyright 2018-2020 DeNova
    Last modified: 2020-10-07
'''

class BitcoinException(Exception):
    '''
        Exception while running bitcoin core app.

        >>> be = BitcoinException()
        >>> isinstance(be, Exception)
        True
    '''

    # pass needed so when we strip comments, the code is still valid
    pass
