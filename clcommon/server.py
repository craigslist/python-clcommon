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

'''craigslist common server module.

This module provides a class to manage hybrid servers that fork a
fixed amount of children with their own event loop using gevent via
monkey patching. It does common setup and handles starting and restarting
children as needed. It provides graceful and forceful shutdown of children,
and children will also exit on their own if the managing parent process
disappears.'''

import errno
import grp
import os
import pwd
import signal
import time

import clcommon.config
import clcommon.log

DEFAULT_CONFIG = clcommon.config.update(clcommon.log.DEFAULT_CONFIG, {
    'clcommon': {
        'server': {
            'children': 1,
            'daemonize': False,
            'group': None,
            'log_level': 'NOTSET',
            'pid_file': None,
            'stop_timeout': 3,
            'user': None}}})


class Server(object):
    '''Server manager class. Managed objects are created by calling the
    given objects in the managed list of the constructor with the parsed
    config object. Managed objects can also be append to the managed
    attribute after the server manager has been initialized. All objects
    that are managed must provide a start and stop method that get called
    when the child process is starting and stopping.'''

    def __init__(self, config, config_files=None, config_dirs=None,
            managed=None):
        config = clcommon.config.update(DEFAULT_CONFIG, config)
        self.config, _args = clcommon.config.load(config, config_files,
            config_dirs, False)
        config = self.config['clcommon']['server']
        if config['daemonize']:
            if os.fork() > 0:
                exit(0)
            os.setsid()
            null = open('/dev/null')
            os.dup2(null.fileno(), 0)
            os.dup2(null.fileno(), 1)
            os.dup2(null.fileno(), 2)
        clcommon.log.setup(self.config)
        self._parent = os.getpid()
        if config['pid_file'] is not None:
            pid_file = open(config['pid_file'], 'w')
            pid_file.write('%d' % self._parent)
        if config['group'] is not None:
            os.setgid(grp.getgrnam(config['group']).gr_gid)
        if config['user'] is not None:
            os.setuid(pwd.getpwnam(config['user']).pw_uid)
        self.log = clcommon.log.get_log('clcommon_server', config['log_level'])
        self._children = {}
        self._stopping = False
        if managed is None:
            self.managed = []
        else:
            self.managed = [method(self.config) for method in managed]

    def start(self):
        '''Start the configured number of children and restart as needed.'''
        self._set_signals(self._stop_signal)
        for _child in xrange(self.config['clcommon']['server']['children']):
            self._start_child_wrapper()
        while len(self._children):
            try:
                pid, status = os.wait()
            except OSError, exception:
                if exception.errno == errno.EINTR:
                    continue
                raise
            if self._children.pop(pid, None) is None:
                self.log.error(_('Unmanaged child %d died with status %d'),
                    pid, os.WEXITSTATUS(status))
                continue
            if self._stopping:
                continue
            self._start_child_wrapper()
            self.log.error(_('Child %d died with status %d'), pid,
                os.WEXITSTATUS(status))
            time.sleep(1)
        self.log.info(_('All children stopped'))

    def stop(self):
        '''Stop the server by killing all children. Set a timeout for
        force kill limit in case they don't exit gracefully.'''
        self._stopping = True
        self._kill_children(signal.SIGTERM)
        signal.signal(signal.SIGALRM, self._alarm)
        signal.alarm(self.config['clcommon']['server']['stop_timeout'])

    def _stop_signal(self, _number, _frame):
        '''Signal handler for stopping the server.'''
        self.stop()

    def _kill_children(self, number):
        '''Send given signal to all running children.'''
        for pid in self._children:
            self.log.info(_('Killing child %d with %d'), pid, number)
            os.kill(pid, number)

    def _alarm(self, _number=0, _frame=0):
        '''Signal handler to forcefully kill children.'''
        self._kill_children(signal.SIGKILL)

    def _start_child_wrapper(self):
        '''Wrapper for starting a new child.'''
        pid = os.fork()
        if pid > 0:
            self._children[pid] = True
            self.log.info(_('Child %d started'), pid)
            return
        self._set_signals(self._stop_child_signal)
        import gevent.monkey
        gevent.monkey.patch_all()
        try:
            self._start_child()
        except:
            os.kill(self._parent, signal.SIGTERM)
            raise
        # Watch for parent death and die if detected.
        try:
            while not self._stopping:
                if os.getppid() != self._parent:
                    self.log.info(_('Parent %d gone, exiting'), self._parent)
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        self._stop_child()
        exit(0)

    def _stop_child_signal(self, _number, _frame):
        '''Signal handler for stopping children.'''
        self._stopping = True

    def _start_child(self):
        '''Start a new child.'''
        for managed in self.managed:
            managed.start()

    def _stop_child(self):
        '''Stop a child.'''
        for managed in self.managed:
            managed.stop(self.config['clcommon']['server']['stop_timeout'])

    @staticmethod
    def _set_signals(handler):
        '''Setup signal handlers for common signals.'''
        signal.signal(signal.SIGHUP, handler)
        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGQUIT, handler)
        signal.signal(signal.SIGTERM, handler)
