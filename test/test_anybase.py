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

'''Tests for craigslist common anybase module.'''

import unittest

import clcommon.anybase


class TestAnybase(unittest.TestCase):

    def test_all(self):
        encoded = clcommon.anybase.encode(0, 2)
        self.assertEquals('0', encoded)
        encoded = clcommon.anybase.encode(100, 2)
        self.assertEquals('1100100', encoded)

        decoded = clcommon.anybase.decode('0', 2)
        self.assertEquals(0, decoded)
        decoded = clcommon.anybase.decode('1100100', 2)
        self.assertEquals(100, decoded)

        encoded = clcommon.anybase.encode(100, 2, 'OX')
        self.assertEquals('XXOOXOO', encoded)
        decoded = clcommon.anybase.decode('XXOOXOO', 2, {'O': 0, 'X': 1})
        self.assertEquals(100, decoded)

        encoded = clcommon.anybase.encode(0, 62)
        self.assertEquals('0', encoded)
        encoded = clcommon.anybase.encode(1, 62)
        self.assertEquals('1', encoded)
        encoded = clcommon.anybase.encode(61, 62)
        self.assertEquals('Z', encoded)
        encoded = clcommon.anybase.encode(62, 62)
        self.assertEquals('10', encoded)

        decoded = clcommon.anybase.decode('0', 62)
        self.assertEquals(0, decoded)
        decoded = clcommon.anybase.decode('1', 62)
        self.assertEquals(1, decoded)
        decoded = clcommon.anybase.decode('Z', 62)
        self.assertEquals(61, decoded)
        decoded = clcommon.anybase.decode('10', 62)
        self.assertEquals(62, decoded)

        for number in xrange(10000):
            encoded = clcommon.anybase.encode(number, 62)
            decoded = clcommon.anybase.decode(encoded, 62)
            self.assertEquals(number, decoded)
