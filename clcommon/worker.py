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

'''craigslist common worker module.

This module provides thread worker pools to perform tasks. Real threads
or patched threads can be used for the pools, and jobs can be batched
together for easy management. Resource intensive tasks should use real
threads and call functions that release the global interpreter lock for
the best performance. This module must be imported before any monkey
patching happens if being used with gevent or other similar libs.

This module also provides a simple queue class similar to those in
the standard queue module that can be used to communicate between any
combination of real or patched threads (like those used in gevent).'''

import errno
import Queue
import socket
import sys
import thread

_UNPATCHED_SOCKETPAIR = socket.socketpair
_UNPATCHED_START_NEW_THREAD = thread.start_new_thread
_UNPATCHED_ALLOCATE_LOCK = thread.allocate_lock
_UNPATCHED_GET_IDENT = thread.get_ident
_PATCHED_THREAD = _UNPATCHED_GET_IDENT()
Empty = Queue.Empty  # pylint: disable=C0103


class HybridQueue(object):
    '''Queue object that can work both with and without monkey patching.'''

    def __init__(self):
        self._send, self._recv = _UNPATCHED_SOCKETPAIR()
        # Assume monkey patching if socket.socketpair is different.
        self._patched = socket.socketpair != _UNPATCHED_SOCKETPAIR
        if self._patched:
            self._send_patched_lock = thread.allocate_lock()
            self._send_patched = socket.fromfd(self._send.fileno(),
                self._send.family, self._send.type)
            self._send_patched.settimeout(None)
            self._recv_patched_lock = thread.allocate_lock()
            self._recv_patched = socket.fromfd(self._recv.fileno(),
                self._recv.family, self._recv.type)
        self._send.settimeout(None)
        self._recv_lock = _UNPATCHED_ALLOCATE_LOCK()
        self._items = []
        self._write_byte = True

    def qsize(self):
        '''Get the number of items in the queue.'''
        return len(self._items)

    def get(self, timeout=None):
        '''Get an item from the queue, blocking if needed.'''
        while True:
            self._recv_byte(timeout)
            self._write_byte = True
            try:
                item = self._items.pop(0)
                if len(self._items) > 0:
                    self._send_byte()
                return item
            except IndexError:
                continue

    def put(self, item):
        '''Put an item in the queue.'''
        self._items.append(item)
        if self._write_byte:
            self._write_byte = False
            self._send_byte()

    def _recv_byte(self, timeout):
        '''Wait until we get a byte on the socket pair, blocking if needed.'''
        patched = self._patched and _PATCHED_THREAD == _UNPATCHED_GET_IDENT()
        if patched:
            lock = self._recv_patched_lock
            recv = self._recv_patched
        else:
            lock = self._recv_lock
            recv = self._recv
        with lock:
            try:
                recv.settimeout(timeout)
                return recv.recv(1)
            except socket.timeout:
                raise Empty()
            except socket.error, exception:
                if exception.errno != errno.EAGAIN:
                    raise
                if timeout == 0:
                    raise Empty()

    def _send_byte(self):
        '''Send a byte to the blocking pair.'''
        if self._patched and _PATCHED_THREAD == _UNPATCHED_GET_IDENT():
            with self._send_patched_lock:
                return self._send_patched.sendall('.')
        return self._send.sendall('.')


class Pool(object):
    '''Class to manage a pool of thread workers. Threads have the ability
    to group jobs together to enable any optimizations. For example, if
    a pool is created to access a SQL database, the group begin method
    could issue a BEGIN statement, and group end could issue a COMMIT,
    allowing any jobs in between to be grouped together in one large
    commit. Another example is to use a pool to aggregate messages being
    sent to a remote server. In this case the job method passed to start
    would buffer the messages and then the group end function would
    actually send the buffered messages to the remote server.'''

    def __init__(self, size, patched=False):
        self._size = size
        self._group_begin = None
        self._group_end = None
        self._stopped = False
        if size > 0:
            self._queue = HybridQueue()
        for _count in xrange(size):
            if patched:
                thread.start_new_thread(self._thread, tuple())
            else:
                _UNPATCHED_START_NEW_THREAD(self._thread, tuple())

    def set_group_begin(self, function, *args, **kwargs):
        '''Set a function to be run before a group of jobs.'''
        if function is None:
            self._group_begin = None
        else:
            self._group_begin = _Job(function, args, kwargs)

    def set_group_end(self, function, *args, **kwargs):
        '''Set a function to be run after a group of jobs.'''
        if function is None:
            self._group_end = None
        else:
            self._group_end = _Job(function, args, kwargs)

    def stop(self):
        '''Stop the pool by stopping all threads running for it.'''
        self._stopped = True
        for _count in xrange(self._size):
            self._queue.put(None)
        if self._size == 0:
            self.set_group_begin(None)
            self.set_group_end(None)

    def start(self, function, *args, **kwargs):
        '''Start a function in thread and return a job handle. The wait
        method of the returned handle should be called to wait for it to
        be completed. The return value of the wait method is the return
        value of the given function. For example::

            >>> pool = clcommon.worker.Pool(10)
            >>> job = pool.start(max, 1, 2)
            >>> job.wait()
            2
        '''
        if self._stopped:
            raise PoolStopped()
        job = _Job(function, args, kwargs)
        if self._size == 0:
            if self._check_group_result(self._group_begin, job):
                return job
            job.run()
            if self._check_group_result(self._group_end, job):
                return job
            job.finish()
        else:
            self._queue.put(job)
        return job

    @staticmethod
    def _check_group_result(group, job):
        '''Run a group function and set the job result on error.'''
        if group is None:
            return False
        group.run()
        if not group.raised:
            return False
        job.result = group.result
        job.raised = group.raised
        job.finish()
        return True

    def qsize(self):
        '''Get the number of jobs in the queue.'''
        if self._size == 0:
            return 0
        return self._queue.qsize()

    def batch(self):
        '''Create a batch object for this pool. Batch objects can start
        multiple jobs and the wait for them to finish all at once. For
        example::

            >>> pool = clcommon.worker.Pool(10)
            >>> batch = pool.batch()
            >>> batch.start(max, 1, 2)
            >>> batch.start(min, 1, 2)
            >>> batch.wait_all()
            [2, 1]

        '''
        return _Batch(self)

    def _thread(self):
        '''Thread worker to run queued functions. This supports grouping
        by running the _group_begin method once it gets a job after
        blocking on the queue, and then runs as many jobs as it can
        without blocking. Once the queue is empty, the _group_end method is
        called and then each job that was run is marked as finished. It's
        important to wait to send any response back to the caller until
        after _group_end is called in case the caller depends on it being
        run before the job is complete (database commit, etc).'''
        while True:
            job = None
            jobs = []
            job = self._queue.get()
            if job is None:
                break
            if self._check_group_result(self._group_begin, job):
                continue
            while job is not None:
                job.run()
                if self._group_end is None:
                    job.finish()
                else:
                    jobs.append(job)
                try:
                    job = self._queue.get(0)
                except Empty:
                    break
            if self._group_end is not None:
                self._group_end.run()
                for completed_job in jobs:
                    if self._group_end.raised:
                        completed_job.result = self._group_end.result
                        completed_job.raised = self._group_end.raised
                    completed_job.finish()
            if job is None:
                break
        if self.qsize() == 0:
            self.set_group_begin(None)
            self.set_group_end(None)


class _Job(object):
    '''Class to manage jobs through their lifecycle.'''

    def __init__(self, function, args, kwargs):
        self._function = function
        self._args = args
        self._kwargs = kwargs
        self._queue = HybridQueue()
        self.result = None
        self.raised = None

    def wait(self):
        '''Wait for the result, even if it has not been started yet.'''
        self._queue.get()
        if self.raised:
            raise self.result[0], self.result[1], self.result[2]
        return self.result

    def run(self):
        '''Run the job, this should only be called from a thread.'''
        try:
            self.result = self._function(*self._args, **self._kwargs)
            self.raised = False
        except Exception:
            self.result = sys.exc_info()
            self.raised = True

    def finish(self):
        '''Send the response back to the caller.'''
        self._queue.put(None)


class _Batch(object):
    '''Class to manage batches of functions being run in parallel.'''

    def __init__(self, pool):
        self._pool = pool
        self._jobs = []

    def start(self, function, *args, **kwargs):
        '''Start a function in a thread for this batch.'''
        self._jobs.append(self._pool.start(function, *args, **kwargs))

    def wait(self):
        '''Wait for result from oldest function run.'''
        return self._jobs.pop(0).wait()

    def wait_all(self):
        '''Wait for results from all outstanding threads.'''
        results = []
        while len(self._jobs) > 0:
            results.append(self.wait())
        return results


class PoolStopped(Exception):
    '''Exception for when jobs are run after the pool has been stopped.'''

    pass
