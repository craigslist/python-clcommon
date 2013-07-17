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

'''craigslist common config module.

This module provides functions to handle loading and working with
configuration from various sources. Configuration objects are nested
dictionaries that can be updated to provide multiple versions if
needed. All configuration should start with some default dictionary.

Most applications will want to call load() with a default config and
use the resulting configuration, but other functions are available for
custom config handling. Modules that need configuration should define
a DEFAULT_CONFIG dict with available options that can be composed into
an application config and passed to load(). For example, a HTTP server
config could look like::

    DEFAULT_CONFIG = {
        'clcommon': {
            'http': {
                'backlog': 64,
                'port': 8080}}}

And the fully parsed config would be generated with::

    config, args = clcommon.config.load(DEFAULT_CONFIG)

This returns a config dictionary updated from options and config files,
along with any arguments that were passed on the command line. Multiple
config files and directories containing config files can be loaded with
the last one overriding previous options. Command line options override
values in configuration files.

All config files are JSON files for ease to use across languages and via
HTTP. Any lines in configuration files that begin with any whitespace
and then a '#' will be removed during parsing to allow for comments.'''

import json
import inspect
import optparse
import os.path
import sys

import clcommon

VALID_JSON_BYTES = dict((str(byte), None)
    for byte in range(10) + ['-', '[', '{', '"'])
VALID_JSON_WORDS = dict((word, None) for word in ['true', 'false', 'null'])


def load(config, config_files=None, config_dirs=None, expect_args=True,
        args=None):
    '''Load config from files, directories, and command line options. This
    adds options based on the config structure that is passed in. This
    function will exit with success (0) if the version, help, or print
    config options are given, and exit with failure (1) if any errors
    are encountered.'''
    parser = optparse.OptionParser(add_help_option=False)
    parser.add_option('-c', '--config', action='append', default=[],
        help=_('Config file to use, can use this option more than once'))
    parser.add_option('-C', '--config_dir', action='append', default=[],
        help=_('Config directory to use, can use this option more than once'))
    parser.add_option('-d', '--debug', action='store_true',
        help=_('Show debugging output'))
    parser.add_option('-h', '--help', action='store_true',
        help=_('Show this help message and exit'))
    parser.add_option('-n', '--no_config', action='store_true',
        help=_('Do not load any default config files'))
    parser.add_option('-p', '--print_config', action='store_true',
        help=_('Print parsed config and exit'))
    parser.add_option('-v', '--verbose', action='store_true',
        help=_('Show more verbose output'))
    parser.add_option('-V', '--version', action='store_true',
        help=_('Print version and exit'))
    for option in get_options(config):
        parser.add_option('', '--%s' % option, metavar='VALUE')
    (options, args) = parser.parse_args(args)

    try:
        config = _load_files(config, options, config_files, config_dirs)
    except Exception, exception:
        print str(exception)
        exit(1)

    for option in get_options(config):
        value = getattr(options, option, None)
        if value is not None:
            try:
                config = update_option(config, option, value)
            except Exception, exception:
                print _('Error parsing option: %s (%s)') % (option, exception)
                exit(1)
    if options.debug:
        config = update(config,
            dict(clcommon=dict(log=dict(console=True, level='DEBUG'))))
    elif options.verbose:
        config = update(config,
            dict(clcommon=dict(log=dict(console=True, level='INFO'))))
    if options.version:
        print clcommon.__version__
        exit(0)
    if options.help:
        parser.print_help()
        print _('\nCurrent config:')
    if options.help or options.print_config:
        print json.dumps(config, indent=4, sort_keys=True)
        exit(0)
    if not expect_args and len(args) > 0:
        print _('Unexpected args: %s') % args
        exit(1)

    return config, args


def _load_files(config, options, config_files, config_dirs):
    '''Load all config files from default and user given locations.'''
    if not options.no_config and config_dirs is not None:
        for config_dir in config_dirs:
            if os.path.exists(config_dir):
                config = load_dir(config, config_dir)
    if not options.no_config and config_files is not None:
        for config_file in config_files:
            if os.path.exists(config_file):
                config = load_file(config, config_file)
    for config_dir in options.config_dir:
        config = load_dir(config, config_dir)
    for config_file in options.config:
        config = load_file(config, config_file)
    return config


def parse_value(value):
    '''Convert a string value to a native type. We don't use raw JSON so
    we can pass unquoted strings and read from standard input.'''
    if not isinstance(value, basestring):
        return value
    if value == '-':
        value = sys.stdin.read()
    if value == '':
        return value
    if value[0] in VALID_JSON_BYTES or value in VALID_JSON_WORDS:
        return json.loads(value)
    return value


def load_file(config, config_file):
    '''Load a JSON file into the given config, stripping out comments.'''
    config_fd = open(os.path.expanduser(config_file))
    config_data = ''
    while True:
        line = config_fd.readline()
        if line == '':
            break
        if line.lstrip()[:1] == '#':
            line = '\n'
        config_data += line
    try:
        config = update(config, json.loads(config_data))
    except Exception, exception:
        raise ConfigError(_('Could not parse config file: %s (%s)') %
            (config_file, exception))
    return config


def load_dir(config, config_dir):
    '''Load a directory of JSON files in sorted order into the given config.'''
    config_files = os.listdir(os.path.expanduser(config_dir))
    config_files.sort()
    for config_file in config_files:
        config = load_file(config, os.path.join(config_dir, config_file))
    return config


def update(config, *new_configs):
    '''Update the given config with a new one, copying if needed to ensure
    the original config dict passed in is not modified.'''
    copied = False
    for new_config in new_configs:
        for key, value in new_config.iteritems():
            if isinstance(value, dict) and key in config:
                value = update(config[key], value)
            if not copied:
                config = config.copy()
                copied = True
            config[key] = value
    return config


def get_options(config, prefix=None):
    '''Get a flat list of options in the given config using dot notation
    (a.b.c) to separate nested dict keys.'''
    prefix = prefix or []
    for key in sorted(config):
        parts = prefix + [key]
        if isinstance(config[key], dict) and config[key] != {}:
            for option in get_options(config[key], parts):
                yield option
        else:
            yield '.'.join(parts)


def update_option(config, name, value):
    '''Update a single value in the given config using dot notation (a.b.c)
    for the name, where each part in the name becomes a nested dict key.'''
    option = parse_value(value)
    for part in reversed(name.split('.')):
        option = {part: option}
    return update(config, option)


def method_help(method):
    '''Generate a method help string of name, arguments, and default values.'''
    argspec = inspect.getargspec(method)
    if len(argspec.args) > 0 and argspec.args[0] == 'self':
        args = argspec.args[1:]
    else:
        args = argspec.args
    required = len(args)
    if argspec.defaults is not None:
        required -= len(argspec.defaults)
    optional = args[required:]
    required = args[:required]
    args = ' '.join(['<%s>' % arg for arg in required])
    for arg in xrange(len(optional)):
        args += ' [%s=%s]' % (optional[arg], json.dumps(argspec.defaults[arg]))
    if args != '' and args[0] != ' ':
        args = ' ' + args
    return '%s%s' % (method.__name__, args)


class ConfigError(Exception):
    '''Exception raised when an error is encountered while checking config.'''

    pass
