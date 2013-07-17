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

'''Tests for craigslist common worker module.'''

import time
import unittest

import clcommon.worker


class TestPool(unittest.TestCase):

    patched = False
    size = 8

    @staticmethod
    def _run_thread(data, kwdata=None):
        '''Method that runs in worker threads.'''
        data['threads'] += 1
        if kwdata is not None:
            kwdata['kwdata'] += 1
        return True

    @staticmethod
    def _run_thread_error():
        '''Method that runs in worker threads.'''
        raise Exception('test')

    def test_start(self):
        data = dict(threads=0, kwdata=0)
        pool = clcommon.worker.Pool(self.size, self.patched)
        pool.start(self._run_thread, data).wait()
        pool.start(self._run_thread, data, data).wait()
        pool.start(self._run_thread, data, kwdata=data).wait()
        self.assertEquals(data['threads'], 3)
        self.assertEquals(data['kwdata'], 2)
        job = pool.start(self._run_thread_error)
        self.assertRaises(Exception, job.wait)
        pool.stop()

    def test_batch(self):
        data = dict(threads=0, kwdata=0)
        pool = clcommon.worker.Pool(self.size, self.patched)
        batch = pool.batch()
        batch.start(self._run_thread, data)
        batch.start(self._run_thread, data, data)
        batch.start(self._run_thread, data, kwdata=data)
        batch.wait_all()
        self.assertEquals(data['threads'], 3)
        self.assertEquals(data['kwdata'], 2)
        pool.stop()

    def test_qsize(self):
        pool = clcommon.worker.Pool(self.size, self.patched)
        batch = pool.batch()
        wait_queue = clcommon.worker.HybridQueue()
        for _count in xrange(self.size + 2):
            batch.start(wait_queue.get)
        time.sleep(0.1)
        self.assertEquals(2, pool.qsize())
        for _count in xrange(self.size + 2):
            wait_queue.put(1)
        batch.wait_all()
        pool.stop()

    def test_timeout(self):
        pool = clcommon.worker.Pool(self.size, self.patched)
        wait_queue = clcommon.worker.HybridQueue()
        wait_queue.put('test')
        self.assertEquals('test', pool.start(wait_queue.get, 0.1).wait())

        job = pool.start(wait_queue.get, 0.1)
        time.sleep(0.2)
        self.assertRaises(clcommon.worker.Empty, job.wait)
        pool.stop()

    def test_stop_in_job(self):
        pool = clcommon.worker.Pool(1, self.patched)
        job = pool.start(pool.stop)
        job.wait()

    def test_job_after_stop(self):
        pool = clcommon.worker.Pool(1, self.patched)
        pool.stop()
        self.assertRaises(clcommon.worker.PoolStopped, pool.start,
            lambda: True)


class TestPoolPatched(TestPool):

    patched = True


class TestPoolOne(TestPool):

    size = 1

    def test_group(self):
        operations = []
        pool = clcommon.worker.Pool(1, self.patched)
        pool.set_group_begin(operations.append, 'begin')
        pool.set_group_end(operations.append, 'end')
        wait_queue = clcommon.worker.HybridQueue()
        batch = pool.batch()
        batch.start(wait_queue.get)
        batch.start(operations.append, 'run')
        batch.start(operations.append, 'run')
        batch.start(operations.append, 'run')
        wait_queue.put('go')
        batch.wait_all()
        time.sleep(0.1)
        self.assertEquals(operations, ['begin'] + ['run'] * 3 + ['end'])
        pool.stop()

    def test_group_begin_exception(self):
        pool = clcommon.worker.Pool(1, self.patched)
        pool.set_group_begin(self._run_thread_error)
        job = pool.start(lambda: True)
        self.assertRaises(Exception, job.wait)
        pool.stop()

    def test_group_end_exception(self):
        pool = clcommon.worker.Pool(1, self.patched)
        pool.set_group_end(self._run_thread_error)
        job = pool.start(lambda: True)
        self.assertRaises(Exception, job.wait)
        pool.stop()


class TestPoolPatchedOne(TestPoolOne):

    patched = True


class TestPoolZero(TestPool):

    size = 0

    def test_qsize(self):
        pool = clcommon.worker.Pool(0)
        self.assertEquals(0, pool.qsize())
        pool.stop()

    def test_group(self):
        operations = []
        pool = clcommon.worker.Pool(0, self.patched)
        pool.set_group_begin(operations.append, 'begin')
        pool.set_group_end(operations.append, 'end')
        batch = pool.batch()
        batch.start(operations.append, 'run')
        batch.start(operations.append, 'run')
        batch.start(operations.append, 'run')
        batch.wait_all()
        self.assertEquals(operations, ['begin', 'run', 'end'] * 3)
        pool.stop()

    def test_group_begin_exception(self):
        pool = clcommon.worker.Pool(0, self.patched)
        pool.set_group_begin(self._run_thread_error)
        job = pool.start(lambda: True)
        self.assertRaises(Exception, job.wait)
        pool.stop()

    def test_group_end_exception(self):
        pool = clcommon.worker.Pool(0, self.patched)
        pool.set_group_end(self._run_thread_error)
        job = pool.start(lambda: True)
        self.assertRaises(Exception, job.wait)
        pool.stop()
