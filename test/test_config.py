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

'''Tests for craigslist common config module.'''

import StringIO
import sys
import unittest

import clcommon.config


class TestConfig(unittest.TestCase):

    def test_load(self):
        config, args = clcommon.config.load({}, args=[])
        self.assertEquals({}, config)
        self.assertEquals([], args)
        config, args = clcommon.config.load({}, args=['-d'])
        self.assertEquals('DEBUG', config['clcommon']['log']['level'])
        self.assertEquals([], args)
        config, args = clcommon.config.load({}, args=['-v'])
        self.assertEquals('INFO', config['clcommon']['log']['level'])
        self.assertEquals([], args)
        config, args = clcommon.config.load(dict(a=dict(b='', d=1, e=False)),
            args=['--a.b=c', '--a.d=4', '--a.e=true'])
        self.assertEquals('c', config['a']['b'])
        self.assertEquals(4, config['a']['d'])
        self.assertEquals(True, config['a']['e'])
        self.assertEquals([], args)
        self.assertRaises(SystemExit, clcommon.config.load, {},
            expect_args=False, args=['test'])

    def test_load_files(self):
        config, args = clcommon.config.load({},
            args=['-c', 'test/test_config.d/test_config.json'])
        self.assertEquals('test', config['clcommon']['log']['syslog_ident'])
        self.assertEquals([], args)
        config, args = clcommon.config.load({},
            config_files=['not_found', 'test/test_config.d/test_config.json'],
            args=[])
        self.assertEquals('test', config['clcommon']['log']['syslog_ident'])
        self.assertEquals([], args)

    def test_load_dirs(self):
        config, args = clcommon.config.load({},
            args=['-C', 'test/test_config.d'])
        self.assertEquals('test', config['clcommon']['log']['syslog_ident'])
        self.assertEquals([], args)
        config, args = clcommon.config.load({},
            config_dirs=['not_found', 'test/test_config.d'], args=[])
        self.assertEquals('test', config['clcommon']['log']['syslog_ident'])
        self.assertEquals([], args)

    def test_parse_value(self):
        self.assertEquals('', clcommon.config.parse_value(''))
        self.assertEquals([1, 2, 'three'],
            clcommon.config.parse_value('[1, 2, "three"]'))
        self.assertEquals({"test": False},
            clcommon.config.parse_value('{"test": false}'))
        self.assertEquals('test string',
            clcommon.config.parse_value('test string'))
        self.assertEquals('10.0.0.1', clcommon.config.parse_value('10.0.0.1'))
        self.assertEquals(5, clcommon.config.parse_value('5'))
        self.assertEquals(-1.2, clcommon.config.parse_value('-1.2'))
        self.assertEquals(True, clcommon.config.parse_value('true'))
        self.assertEquals(None, clcommon.config.parse_value('null'))
        old_stdin = sys.stdin
        sys.stdin = StringIO.StringIO('test')
        self.assertEquals('test', clcommon.config.parse_value('-'))
        sys.stdin = old_stdin

    def test_help(self):
        self.assertRaises(SystemExit, clcommon.config.load, {}, args=['-h'])

    def test_version(self):
        self.assertRaises(SystemExit, clcommon.config.load, {}, args=['-V'])

    def test_bad_file(self):
        self.assertRaises(SystemExit, clcommon.config.load, {},
            args=['-c', 'xx'])
        self.assertRaises(SystemExit, clcommon.config.load, {},
            args=['-c', 'README.rst'])

    def test_bad_option(self):
        self.assertRaises(SystemExit, clcommon.config.load, dict(a=1),
            args=['--a={'])

    def test_update(self):
        original = dict(a=0, b=0)
        config = clcommon.config.update(original, dict(a=1, b=1), dict(a=2))
        self.assertEquals(config, dict(a=2, b=1))
        self.assertEquals(original, dict(a=0, b=0))

    def test_method_help(self):
        self.assertEquals('test_method_help',
            clcommon.config.method_help(self.test_method_help))

        def _test(one, two, three=None):
            '''Test function for method_help.'''
            return one, two, three

        self.assertEquals('_test <one> <two> [three=null]',
            clcommon.config.method_help(_test))
