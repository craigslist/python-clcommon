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

'''craigslist common log module.

This modules provides a few helper functions around the standard Python
logging module to setup console and syslog logging. Most applications will
want to call setup() with the parsed log config to setup logging. Modules
that need to log can use get_log() to get a logging object with the
appropriate level set. If no logging is enabled, console logging will be
enabled by default.

Only console and syslog logging is supported now, but others can easily
be added by adding options to setup more handlers from the standard
logging.handlers module or other custom handlers.'''

import errno
import logging.handlers
import os
import signal
import socket

DEFAULT_CONFIG = {
    'clcommon': {
        'log': {
            'console': False,
            'format': ' %(process)d %(levelname)s %(name)s %(message)s',
            'level': 'WARNING',
            'syslog_ident': None,
            'syslog_stdio': True}}}


def setup(config):
    '''Enable console and/or syslog logging. Also setup the stdio log
    forwarder process if enabled.'''
    config = config['clcommon']['log']
    level = _get_level(config['level'])
    logger = logging.getLogger()
    logger.setLevel(level)

    if config['syslog_ident'] is not None:
        handler = _SysLogHandler(address='/dev/log')
        format_string = str(config['syslog_ident'] + config['format'])
        handler.setFormatter(logging.Formatter(format_string))
        handler.setLevel(level)
        logger.addHandler(handler)

    if config['console'] or config['syslog_ident'] is None:
        handler = logging.StreamHandler()
        format_string = '%(asctime)s' + str(config['format'])
        handler.setFormatter(logging.Formatter(format_string))
        handler.setLevel(level)
        logger.addHandler(handler)
    elif config['syslog_stdio']:
        stdio_read, stdio_write = os.pipe()
        os.dup2(stdio_write, 1)
        os.dup2(stdio_write, 2)
        parent = os.getpid()
        if os.fork() == 0:
            _ParentWatcher(logger, parent)
            stdio_read = os.fdopen(stdio_read)
            while True:
                try:
                    logger.error(stdio_read.readline().strip())
                except Exception, exception:
                    if getattr(exception, 'errno', 0) == errno.EINTR:
                        continue
                    logger.error(_('Could not log stdio error: %s'), exception)


def _get_level(level):
    '''Get level, converting from string if needed.'''
    if isinstance(level, basestring):
        return logging.getLevelName(level)
    return level


def get_log(name, level='NOTSET'):
    '''Get a logger and set the appropriate level.'''
    logger = logging.getLogger(name)
    logger.setLevel(_get_level(level))
    return logger


class _ParentWatcher(object):
    '''Watch if parent process is still around using SIGALRM. This is
    used by the stdio log forwarder process if enabled.'''

    def __init__(self, log, parent):
        self.log = log
        self.parent = parent
        signal.signal(signal.SIGALRM, self._alarm)
        signal.alarm(1)

    def _alarm(self, _number, _frame):
        '''Alarm signal handler to make sure parent is still around.'''
        if self.parent != os.getppid():
            self.log.info(_('Parent %d gone, exiting (log)'), self.parent)
            exit(0)
        signal.signal(signal.SIGALRM, self._alarm)
        signal.alarm(1)


class _SysLogHandler(logging.handlers.SysLogHandler):
    '''Wrapper for SysLogHandler that does not prefix UTF-8 log
    messages with byte order mark (BOM). This was broken in Python
    2.6.6 and fixed by 2.7, so this entire class can be removed and use
    logging.handlers.SysLogHandler directly once we're on 2.7.'''

    def emit(self, record):
        '''Emit a record without .'''
        msg = self.format(record)
        priority = self.encodePriority(self.facility,
            self.mapPriority(record.levelname))
        msg = self.log_format_string % (priority, msg)
        if type(msg) is unicode:
            msg = msg.encode('utf-8')
        try:
            if self.unixsocket:
                try:
                    self.socket.send(msg)
                except socket.error:
                    self._connect_unixsocket(self.address)
                    self.socket.send(msg)
            else:
                self.socket.sendto(msg, self.address)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)
