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

'''Tests for craigslist common number module.'''

import unittest

import clcommon.number


class TestNumber(unittest.TestCase):

    def test_encode(self):
        self.assertEquals('1000', clcommon.number.encode(1000, False))
        self.assertEquals('1', clcommon.number.encode(1.0001, False))
        self.assertEquals('0.1', clcommon.number.encode(0.1, False))
        self.assertEquals('0.01', clcommon.number.encode(0.01, False))
        self.assertEquals('0.001', clcommon.number.encode(0.001, False))
        self.assertEquals('0', clcommon.number.encode(0.0001, False))
        self.assertEquals('0', clcommon.number.encode(0, False))

    def test_encode_si_prefix(self):
        self.assertEquals('100M', clcommon.number.encode(99960000))
        self.assertEquals('100k', clcommon.number.encode(99960))
        self.assertEquals('99.9k', clcommon.number.encode(99930))
        self.assertEquals('100', clcommon.number.encode(99.96))
        self.assertEquals('99.9', clcommon.number.encode(99.93))
        self.assertEquals('10', clcommon.number.encode(9.996))
        self.assertEquals('9.99', clcommon.number.encode(9.993))
        self.assertEquals('1', clcommon.number.encode(0.9996))
        self.assertEquals('999m', clcommon.number.encode(0.9993))
        self.assertEquals('100m', clcommon.number.encode(0.09996))
        self.assertEquals('99.9m', clcommon.number.encode(0.09993))
        self.assertEquals('99.9u', clcommon.number.encode(0.00009993))

    def test_decode(self):
        self.assertEquals(1000, clcommon.number.decode('1000'))
        self.assertEquals(1.0001, clcommon.number.decode('1.0001'))
        self.assertEquals(0.1, clcommon.number.decode('0.1'))
        self.assertEquals(0.01, clcommon.number.decode('0.01'))
        self.assertEquals(0.001, clcommon.number.decode('0.001'))
        self.assertEquals(0.0001, clcommon.number.decode('0.0001'))
        self.assertEquals(0, clcommon.number.decode('0'))

    def test_decode_si_prefix(self):
        self.assertEquals(100000000, clcommon.number.decode('100M'))
        self.assertEquals(100000, clcommon.number.decode('100k'))
        self.assertEquals(99900, clcommon.number.decode('99.9k'))
        self.assertEquals(100, clcommon.number.decode('100'))
        self.assertEquals(99.9, clcommon.number.decode('99.9'))
        self.assertEquals(10, clcommon.number.decode('10'))
        self.assertEquals(9.99, clcommon.number.decode('9.99'))
        self.assertEquals(1, clcommon.number.decode('1'))
        self.assertEquals(0.999, clcommon.number.decode('999m'))
        self.assertEquals(0.100, clcommon.number.decode('100m'))
        self.assertEquals(0.0999, clcommon.number.decode('99.9m'))
        self.assertEquals(0.0000999, clcommon.number.decode('99.9u'))

    def test_decode_time(self):
        self.assertEquals(10, clcommon.number.decode('10s', True))
        self.assertEquals(600, clcommon.number.decode('10m', True))
        self.assertEquals(36000, clcommon.number.decode('10h', True))
        self.assertEquals(864000, clcommon.number.decode('10d', True))
        self.assertEquals(6048000, clcommon.number.decode('10w', True))
        self.assertEquals(315360000, clcommon.number.decode('10y', True))
        self.assertEquals(864000000, clcommon.number.decode('10kd', True))

    def test_unique64(self):
        uniques = [clcommon.number.unique64() for _count in xrange(100)]
        last = uniques.pop(0)
        while len(uniques) > 0:
            self.assertTrue(uniques[0] > last)
            last = uniques.pop(0)
