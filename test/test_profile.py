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

'''Tests for craigslist common profile module.'''

import StringIO
import unittest

import clcommon.profile


class TestProfile(unittest.TestCase):

    def test_profile(self):
        profile = clcommon.profile.Profile()
        profile.mark_cpu('a')
        profile.mark_time('b')
        profile.reset_all()
        profile.mark_all('c')
        profile.mark('d', 1000000)
        profile.mark('e', 99.999)
        profile.mark('f', 9.9999)
        profile.mark('g', 0.99999)
        profile.mark('h', 0.099999)
        result = str(profile).split(' ')
        result.sort()
        expected = ['a:cpu=0', 'b:time=0', 'c:cpu=0', 'c:time=0', 'd=1000000',
            'e=100', 'f=10', 'g=1', 'h=0.1']
        self.assertEquals(expected, result)

    def test_report(self):
        data_file = StringIO.StringIO('one=2.1\none=1 two:cpu=2\nthree:cpu=3')
        data = dict(count=2, values=[2.1, 1], total=3.1, min=1.0, max=2.1,
            average=1.55, variance=0.6050000000000001, stddev=0.55)
        self.assertEquals(data, clcommon.profile.report_data(data_file)['one'])

        data_file.seek(0)
        data = dict(count=1, values=[3.0], total=3.0, min=3.0, max=3.0,
            average=3.0, variance=0.0, stddev=0.0)
        self.assertEquals(data,
            clcommon.profile.report_data(data_file)['three:cpu'])

        data_file.seek(0)
        data = dict(count=2, values=[2.0, 3.0], total=5.0, min=2.0, max=3.0,
            average=2.5, variance=0.5, stddev=0.5)
        self.assertEquals(data, clcommon.profile.report_data(data_file)['cpu'])

        data_file.seek(0)
        clcommon.profile.report(data_file)

        data_file = StringIO.StringIO('test bad=not_a_float')
        self.assertEquals({}, clcommon.profile.report_data(data_file))

    def test_significant(self):
        self.assertEquals('100k', clcommon.profile.significant(99960))
        self.assertEquals('99.9k', clcommon.profile.significant(99930))
        self.assertEquals('100', clcommon.profile.significant(99.96))
        self.assertEquals('99.9', clcommon.profile.significant(99.93))
        self.assertEquals('10', clcommon.profile.significant(9.996))
        self.assertEquals('9.99', clcommon.profile.significant(9.993))
        self.assertEquals('1', clcommon.profile.significant(0.9996))
        self.assertEquals('999m', clcommon.profile.significant(0.9993))
        self.assertEquals('100m', clcommon.profile.significant(0.09996))
        self.assertEquals('99.9m', clcommon.profile.significant(0.09993))

        self.assertEquals('0.001', clcommon.profile.significant(0.001, False))
        self.assertEquals('0.01', clcommon.profile.significant(0.01, False))
        self.assertEquals('0.1', clcommon.profile.significant(0.1, False))
        self.assertEquals('1', clcommon.profile.significant(1.0001, False))
