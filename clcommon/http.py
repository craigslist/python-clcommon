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

'''craigslist common HTTP module.

This module provides a class to manage HTTP servers, a convenience request
handling class, and exception classes for HTTP error responses. This is
built on top of the gevent WSGI server and can call other WSGI handlers
within the request module. This module also provides some helper classes
for dealing with httplib request and response bodies.

The gevent setup for the server is delayed until it is actually being
started because gevent is not designed to handle being forked after it has
been initialized. The server object can be used to create multiple gevent
processes for the same listening socket by having a parent process create
the server object (which creates the listening socket), fork multiple
children, and call the server start method in each child.'''

import Cookie
import os
import socket
import traceback

import clcommon.log
import clcommon.server

DEFAULT_CONFIG = {
    'clcommon': {
        'http': {
            'backlog': 64,
            'host': '',
            'log_level': 'NOTSET',
            'port': 8080,
            'server_name': 'craigslist/%s' % clcommon.__version__}}}

JQUERY = os.path.join(os.path.dirname(__file__), 'jquery.js')
FAVICON = os.path.join(os.path.dirname(__file__), 'favicon.ico')


class Server(object):
    '''HTTP server class.'''

    def __init__(self, config, request):
        self.config = config
        self._request = request
        config = config['clcommon']['http']
        self.log = clcommon.log.get_log('clcommon_http_server',
            config['log_level'])
        self.env = {'SERVER_SOFTWARE': str(config['server_name'])}
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((config['host'], config['port']))
        self._socket.listen(config['backlog'])
        self._server = None

    def _start_server(self):
        '''Start server using listening socket created in __init__.'''
        log = {
            'access': self.log,
            'error': self.log}

        import gevent.pywsgi
        server_log = self.log

        class WSGIHandler(gevent.pywsgi.WSGIHandler):
            '''Wrapper to do custom logging in HTTP server.'''

            def log_request(self):
                '''Log a request.'''
                server_log.info(self.format_request())

            def log_error(self, msg, *args):
                '''Log an error.'''
                server_log.warning(msg, *args)

        self._socket = socket.fromfd(self._socket.fileno(),
            self._socket.family, self._socket.type, self._socket.proto)
        self._server = gevent.pywsgi.WSGIServer(self._socket, self, log=log,
            handler_class=WSGIHandler)
        self._server.set_environ(self.env)

    def start(self):
        '''Start the server. The first time this is called the listening
        socket is created and the WSGI server is setup.'''
        if self._server is None:
            self._start_server()
        self._server.start()
        self.log.info(_('Listening on %s:%d'), self._server.server_host,
            self._server.server_port)

    def stop(self, timeout=None):
        '''Stop the server.'''
        self._server.stop(timeout)

    def __call__(self, env, start):
        '''Entry point for all requests. Wrap all exceptions with an internal
        server error.'''
        try:
            return self._request(self, env, start).run()
        except StatusCode, exception:
            response = exception
        except Exception, exception:
            self.log.error(_('Uncaught exception in request: %s (%s)'),
                exception, ''.join(traceback.format_exc().split('\n')))
            response = InternalServerError()
        if not header_exists('Server', response.headers):
            response.headers.insert(0, ('Server', env['SERVER_SOFTWARE']))
        start(response.status, response.headers)
        return response.body


class Request(object):
    '''Request class used by the server for each incoming request. This
    provides many helper methods for parsing requests and generating
    responses. Real request handlers should inherit from this and implement
    the run method.'''

    def __init__(self, server, env, start):
        self.server = server
        self.log = server.log
        self.env = env
        self._start = start
        self.method = env['REQUEST_METHOD'].upper()
        self._params = None
        self._cookies = None
        self.body = Input(self.env.get('wsgi.input'))
        self._body_data = None
        self.headers = [('Server', self.env['SERVER_SOFTWARE'])]

    def run(self):
        '''Run the request.'''
        raise NotImplementedError()

    @property
    def params(self):
        '''Parse the URL parameter list into a dictionary.'''
        if self._params is not None:
            return self._params
        self._params = {}
        params = self.env.get('QUERY_STRING')
        if params is None or params == '':
            return self.params
        for parameter in params.split('&'):
            parameter = parameter.split('=', 1)
            key = parameter[0].strip()
            if len(parameter) == 1:
                self._params[key] = None
            else:
                self._params[key] = parameter[1].strip()
        return self._params

    def parse_params(self, str_params=None, int_params=None, bool_params=None,
            list_params=None):
        '''Parse out different types of parameters.'''
        params = {}
        for param in str_params or []:
            if param in self.params:
                params[param] = self.params[param]
        for param in int_params or []:
            if param in self.params:
                params[param] = self.parse_int_param(param)
        for param in bool_params or []:
            if param in self.params:
                params[param] = self.parse_bool_param(param)
        for param in list_params or []:
            if param in self.params:
                params[param] = self.parse_list_param(param)
        return params

    def parse_int_param(self, param):
        '''Parse a parameter that is an integer.'''
        try:
            return int(self.params[param])
        except:
            raise BadRequest(_('Invalid int value for %s: %s') %
                (param, self.params[param]))

    def parse_bool_param(self, param):
        '''Parse a parameter that is a boolean.'''
        value = self.params[param].lower()
        if value == '1' or value == 'true':
            return True
        elif value == '0' or value == 'false':
            return False
        raise BadRequest(_('Invalid boolean value for %s: %s') %
            (param, value))

    def parse_list_param(self, param):
        '''Parse a parameter that is a comma separated list.'''
        if self.params[param] == '':
            return []
        return self.params[param].split(',')

    @property
    def cookies(self):
        '''Parse the cookie header into a dictionary.'''
        if self._cookies is not None:
            return self._cookies
        self._cookies = {}
        cookies = self.env.get('HTTP_COOKIE')
        if cookies is None:
            return self.cookies
        for cookie in cookies.split(';'):
            cookie = cookie.split('=', 1)
            key = cookie[0].strip()
            if len(cookie) == 1:
                self._cookies[key] = None
            else:
                self._cookies[key] = cookie[1].strip(' \t"')
        return self._cookies

    @property
    def body_data(self):
        '''Read and cache the request body.'''
        if self._body_data is not None:
            return self._body_data
        self._body_data = self.body.read()
        return self._body_data

    def set_cookie(self, name, value, expires=None, path=None, domain=None):
        '''Set a cookie in the response headers.'''
        cookie = Cookie.SimpleCookie()
        cookie[name] = value
        if expires is not None:
            cookie[name]['expires'] = expires
        if path is not None:
            cookie[name]['path'] = path
        if domain is not None:
            cookie[name]['domain'] = path
        self.headers.append(('Set-Cookie', cookie[name].OutputString()))

    def respond(self, status, body=None):
        '''Build a response.'''
        self._start(status, self.headers)
        if isinstance(body, basestring):
            body = [body]
        return body or ['']

    def ok(self, body=None):
        '''Build a 200 response.'''
        return self.respond(_('200 Ok'), body)

    def created(self, body=None):
        '''Build a 201 response.'''
        return self.respond(_('201 Created'), body)

    def no_content(self, body=None):
        '''Build a 204 response.'''
        return self.respond(_('204 No Content'), body)


class StatusCode(Exception):
    '''Base exception for HTTP response status codes.'''

    status = '000 Undefined'

    def __init__(self, body=None, headers=None):
        self.headers = headers or []
        self.body = body or self.status
        if isinstance(self.body, basestring):
            self.body = [self.body]
        if body is None and not header_exists('Content-Type', self.headers):
            self.headers.append(('Content-Type', 'text/plain'))
        super(StatusCode, self).__init__(_('status=%s headers=%s') %
            (self.status, headers))


class BadRequest(StatusCode):
    '''Exception for a 400 response.'''

    status = _('400 Bad Request')


class Unauthorized(StatusCode):
    '''Exception for a 401 response.'''

    status = _('401 Unauthorized')


class Forbidden(StatusCode):
    '''Exception for a 403 response.'''

    status = _('403 Forbidden')


class NotFound(StatusCode):
    '''Exception for a 404 response.'''

    status = _('404 Not Found')


class MethodNotAllowed(StatusCode):
    '''Exception for a 405 response.'''

    status = _('405 Method Not Allowed')


class UnsupportedMediaType(StatusCode):
    '''Exception for a 415 response.'''

    status = _('415 Unsupported Media Type')


class InternalServerError(StatusCode):
    '''Exception for a 500 response.'''

    status = _('500 Internal Server Error')


def header_exists(name, headers):
    '''Check to see if a header exists in a list of headers.'''
    for header in headers:
        if header[0] == name:
            return True
    return False


class Input(object):
    '''Wrapper around WSGI input objecst to ensure we've read the entire
    content length.'''

    def __init__(self, wsgi_input):
        self._input = wsgi_input
        self.content_length = wsgi_input.content_length
        self._read = 0

    def read(self, length=None):
        '''Read and return data, checking content length if this is the end.'''
        data = self._input.read(length)
        self._read += len(data)
        if (data == '' or length is None) and \
                self.content_length is not None and \
                self.content_length != self._read:
            raise IOError(_('Could not read the full content length (%d/%d)') %
                (self._read, self.content_length))
        return data


class Chunk(object):
    '''Wrapper around data streams that we don't know the length of so
    we can use a chunked encoding for httplib requests.'''

    def __init__(self, data):
        self._data = data
        self._done = False

    def read(self, size=-1):
        '''Read the next chunk of data and add the chunk size to it.'''
        if self._done:
            return ''
        data = self._data.read(size)
        if not data:
            self._done = True
            return '0\r\n\r\n'
        return '%x\r\n%s\r\n' % (len(data), data)


class Stream(object):
    '''Wrapper around httplib responses that adds an iterator interface.'''

    def __init__(self, response, buffer_size, complete=None):
        self._response = response
        self._buffer_size = buffer_size
        self._complete = complete
        content_length = response.getheader('Content-Length')
        if content_length is not None:
            self.content_length = content_length

    def read(self, size=None):
        '''Read wrapper that calls complete callback if needed when done.'''
        data = self._response.read(size)
        if (size is None or not data) and self._complete is not None:
            self._complete()
        return data

    def __iter__(self):
        return self

    def next(self):
        '''Return the next chunk of data when used as an iterator.'''
        data = self.read(self._buffer_size)
        if not data:
            raise StopIteration
        return data
