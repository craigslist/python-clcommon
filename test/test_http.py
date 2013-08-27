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

'''Tests for craigslist common http module.'''

import httplib
import socket
import StringIO
import unittest

import clcommon.config
import clcommon.http

HOST = '127.0.0.1'
PORT = 8123
CONFIG = clcommon.config.update(clcommon.http.DEFAULT_CONFIG, {
    'clcommon': {
        'http': {
            'host': HOST,
            'port': PORT}}})


def request(method, url, *args, **kwargs):
    '''Perform the request and handle the response.'''
    connection = httplib.HTTPConnection(HOST, PORT)
    connection.request(method, url, *args, **kwargs)
    return connection.getresponse()


class TestFile(object):

    content_length = 0

    def __iter__(self):
        return self

    @staticmethod
    def read(_size=-1):
        '''Test read method.'''
        return ''

    @staticmethod
    def next():
        '''Test iterator.'''
        raise StopIteration()


class TestRequest(clcommon.http.Request):

    def run(self):
        if self.params.get('created'):
            return self.created()
        if self.params.get('no_content'):
            return self.no_content()
        if self.params.get('not_found'):
            raise clcommon.http.NotFound()
        if self.params.get('not_found_html'):
            raise clcommon.http.NotFound('<html><body>Oops</body></html>',
                [('Content-Type', 'text/html')])
        if self.params.get('error'):
            raise Exception('unknown')
        if self.params.get('set_content'):
            body = TestFile()
            return self.ok(self.set_content(self.params.get('name'), body))
        if self.params.get('set_content_json'):
            return self.ok(self.set_content(self.params.get('name'), {}))
        if self.params.get('parse_params'):
            self.parse_params(['str'], ['int'], ['bool'], ['list'])
        if 'test' in self.cookies:
            self.set_cookie('test', self.cookies['test'])
        if 'test_full' in self.cookies:
            self.set_cookie('test', 'found it', 100, '/', 'example.com')
        if self.body_data == '':
            return self.ok()
        return self.ok(self.body_data)


class ServerBase(unittest.TestCase):
    '''Base class for HTTP server testing.'''

    def __init__(self, *args, **kwargs):
        super(ServerBase, self).__init__(*args, **kwargs)
        self.server = None

    def setUp(self):
        self.server = clcommon.http.Server(CONFIG, TestRequest)
        self.server.start()

    def tearDown(self):
        self.server.stop()
        self.server = None


class TestServer(ServerBase):

    def test_ok(self):
        response = request('GET', '/')
        self.assertEquals(200, response.status)

    def test_created(self):
        response = request('GET', '/?created=1')
        self.assertEquals(201, response.status)

    def test_no_content(self):
        response = request('GET', '/?no_content=1')
        self.assertEquals(204, response.status)

    def test_not_found(self):
        response = request('GET', '/?not_found=1')
        self.assertEquals(404, response.status)
        self.assertEquals('text/plain', response.getheader('Content-Type'))

    def test_not_found_html(self):
        response = request('GET', '/?not_found_html=1')
        self.assertEquals(404, response.status)
        self.assertEquals('text/html', response.getheader('Content-Type'))

    def test_error(self):
        response = request('GET', '/?error=1')
        self.assertEquals(500, response.status)
        response = request('bad request line', '/?error=1')
        self.assertEquals(400, response.status)

    def test_cookie(self):
        response = request('GET', '/', headers={'Cookie': 'test=value'})
        self.assertEquals(200, response.status)
        self.assertEquals('test=value', response.getheader('Set-Cookie'))
        response = request('GET', '/', headers={'Cookie': 'test_full'})
        self.assertEquals(200, response.status)
        parts = ['test', 'expires', 'path', 'domain']
        for part in response.getheader('Set-Cookie').split(';'):
            key = part.strip().split('=')[0]
            parts.remove(key.lower())
        self.assertEquals([], parts)

    def test_content(self):
        response = request('GET', '/?set_content=1&name=test.html')
        self.assertEquals('0', response.getheader('Content-Length'))
        self.assertEquals('text/html', response.getheader('Content-Type'))
        self.assertEquals('', response.read())

        response = request('GET', '/?set_content=1&name=test.unknown')
        self.assertEquals('0', response.getheader('Content-Length'))
        self.assertEquals('application/octet-stream',
            response.getheader('Content-Type'))
        self.assertEquals('', response.read())

    def test_content_json(self):
        response = request('GET', '/?set_content_json=1&name=test.json')
        self.assertEquals('2', response.getheader('Content-Length'))
        self.assertEquals('{}', response.read())

    def test_body(self):
        response = request('PUT', '/', body='test body')
        self.assertEquals('test body', response.read())

    def test_header_exists(self):
        self.assertTrue(clcommon.http.header_exists('test', [('test', '1')]))

    def test_parse_params(self):
        response = request('PUT', '/?parse_params=1&str=test')
        self.assertEquals(200, response.status)
        response = request('PUT', '/?parse_params=1&int=0')
        self.assertEquals(200, response.status)
        response = request('PUT', '/?parse_params=1&int=100000')
        self.assertEquals(200, response.status)
        response = request('PUT', '/?parse_params=1&int=1.1')
        self.assertEquals(400, response.status)
        response = request('PUT', '/?parse_params=1&int=bad')
        self.assertEquals(400, response.status)
        response = request('PUT', '/?parse_params=1&bool=0')
        self.assertEquals(200, response.status)
        response = request('PUT', '/?parse_params=1&bool=false')
        self.assertEquals(200, response.status)
        response = request('PUT', '/?parse_params=1&bool=FALSE')
        self.assertEquals(200, response.status)
        response = request('PUT', '/?parse_params=1&bool=1')
        self.assertEquals(200, response.status)
        response = request('PUT', '/?parse_params=1&bool=true')
        self.assertEquals(200, response.status)
        response = request('PUT', '/?parse_params=1&bool=TRUE')
        self.assertEquals(200, response.status)
        response = request('PUT', '/?parse_params=1&bool=2')
        self.assertEquals(400, response.status)
        response = request('PUT', '/?parse_params=1&bool=bad')
        self.assertEquals(400, response.status)
        response = request('PUT', '/?parse_params=1&list=')
        self.assertEquals(200, response.status)
        response = request('PUT', '/?parse_params=1&list=a,b,c')
        self.assertEquals(200, response.status)

    def test_truncated_content_length(self):
        connection = httplib.HTTPConnection(HOST, PORT)
        connection.request('PUT', '/', 'test', {'Content-Length': 10})
        connection.sock.shutdown(socket.SHUT_WR)
        response = connection.getresponse()
        self.assertEquals(500, response.status)


class TestChunk(ServerBase):

    def test_chunk(self):
        headers = {'Transfer-Encoding': 'chunked'}
        body = clcommon.http.Chunk(StringIO.StringIO('test chunk'))
        response = request('PUT', '/', body, headers)
        self.assertEquals('test chunk', response.read())


class TestStream(ServerBase):

    def test_stream(self):
        response = request('PUT', '/', body='test body')
        stream = clcommon.http.Stream(response, 2)
        data = ''
        for chunk in stream:
            data += chunk
        self.assertEquals('test body', data)
        self.assertEquals(int(stream.content_length), len(data))
