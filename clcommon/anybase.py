# Copyright 2013 craigslist
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

'''craigslist common anybase module.

This module provides functions to encode and decode numbers using any
base and character set given to it. By default it uses a 62 character
set to make URL-safe encodings. For example::

    >>> clcommon.anybase.encode(1234567890, 62)
    '1ly7vk'
    >>> clcommon.anybase.decode('1ly7vk', 62)
    1234567890

To use a custom character set, pass it as the last argument:

    >>> encoding = 'abcdefghij'
    >>> decoding = dict((char, index)
    ...     for index, char in enumerate(encoding))
    >>> clcommon.anybase.encode(1234567890, 10, encoding)
    'bcdefghija'
    >>> clcommon.anybase.decode('bcdefghija', 10, decoding)
    1234567890
'''

ENCODING = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
DECODING = dict((char, index) for index, char in enumerate(ENCODING))


def encode(number, base, encoding=None):
    '''Encode a number using the given base and optional encoding.'''
    encoding = encoding or ENCODING
    if number == 0:
        return encoding[0]
    encoded = []
    while number > 0:
        encoded.append(encoding[number % base])
        number = number // base
    return ''.join(reversed(encoded))


def decode(string, base, decoding=None):
    '''Decode a string using the given base and optional encoding.'''
    decoding = decoding or DECODING
    number = 0
    for char in string:
        number *= base
        number += decoding[char]
    return number
