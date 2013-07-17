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

'''Tests for craigslist common log module.'''

import logging
import unittest

import clcommon.config
import clcommon.log


class TestLog(unittest.TestCase):

    def test_setup(self):
        config = clcommon.config.update(clcommon.log.DEFAULT_CONFIG, {
            'clcommon': {
                'log': {
                    'console': True,
                    'level': 'ERROR',
                    'syslog_ident': 'test'}}})
        clcommon.log.setup(config)
        self.assertEquals(logging.ERROR, logging.getLogger().level)

    def test_get_log(self):
        logger = clcommon.log.get_log('test', logging.DEBUG)
        self.assertEquals(logging.DEBUG, logger.level)
