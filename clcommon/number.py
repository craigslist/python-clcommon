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

'''craigslist common number module.

This module provides a few convenience functions for working with numbers.'''

import random
import re
import time

SI_PREFIX_LARGE = ['', 'k', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y']
SI_PREFIX_SMALL = ['', 'm', 'u', 'n', 'p', 'f', 'a', 'z', 'y']
SI_PREFIX_MULTIPLIER = dict((prefix, index)
    for index, prefix in enumerate(SI_PREFIX_LARGE))
SI_PREFIX_MULTIPLIER.update(dict((prefix, -index)
    for index, prefix in enumerate(SI_PREFIX_SMALL)))
SI_PREFIX_REGEX = re.compile('^(-)?([0-9]+)(\.[0-9]+)?([%s])?$' %
    ''.join(SI_PREFIX_LARGE + SI_PREFIX_SMALL))
TIME_ABBREVIATIONS = {
    's': 1,
    'm': 60,
    'h': 3600,
    'd': 86400,
    'w': 604800,
    'y': 31536000}


def encode(value, si_prefix=True, digits=3, factor=1000):
    '''Format value to some number of significant digits, adding an SI
    prefix if needed.'''
    if si_prefix:
        si_prefix = 0
        if value > 1:
            factor = float(factor)
            while value >= factor and si_prefix < (len(SI_PREFIX_LARGE) - 1):
                value /= factor
                si_prefix += 1
            si_prefix = SI_PREFIX_LARGE[si_prefix]
        elif value > 0:
            while round(value, digits) < 1 and \
                    si_prefix < (len(SI_PREFIX_LARGE) - 1):
                value *= factor
                si_prefix += 1
            si_prefix = SI_PREFIX_SMALL[si_prefix]
        else:
            si_prefix = ''
    else:
        si_prefix = ''

    for digit in xrange(digits, 0, -1):
        value = round(value, digit)
        if value < (10 ** (digits - digit)) and \
                value != round(value, digit - 1):
            return ('%%.%df%%s' % digit) % (value, si_prefix)
    value = round(value, 0)
    if value == 0:
        return '0'
    return '%d%s' % (value, si_prefix)


def decode(value, time_value=False, relative_time=True, factor=1000, now=None):
    '''Decode a SI prefix encoded value.'''
    if isinstance(value, (int, float)):
        return value
    if not isinstance(value, basestring):
        raise ValueError(_('Cannot decode value: %s') % value)
    if time_value and value[-1:] in TIME_ABBREVIATIONS:
        multiplier = TIME_ABBREVIATIONS[value[-1]]
        value = value[:-1]
    else:
        multiplier = 1
        time_value = False
    match = SI_PREFIX_REGEX.match(value)
    if match is None:
        raise ValueError(_('Cannot decode value: %s') % value)
    if match.group(4) is not None:
        multiplier *= factor ** SI_PREFIX_MULTIPLIER[match.group(4)]
    value = int(match.group(2))
    if match.group(3) is not None:
        value += float(match.group(3))
    if match.group(1) is not None:
        value = -value
    value = value * multiplier
    if time_value and not relative_time:
        now = now or time.time()
        if isinstance(value, int):
            value = int(now) + value
        else:
            value = now + value
    return value


def unique64(now=None):
    '''Generate a unique time-based 64 bit integer ID.'''
    if now is None:
        now = time.time()
    elif isinstance(now, int):
        now += time.time() % 1
    seconds = int(now)
    micros = int((now % 1) * 1000000)
    return (seconds << 32) + (micros << 12) + random.randrange(4096)
