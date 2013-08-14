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

'''craigslist common profile module.

This module allows application level profiling to be done by marking
various metrics and then saving the marks in some way (usually logging)
for later aggregation and analysis.

The Profile class should be used in application code, and getting the
string representation of an instance will yield a line of key=value
pairs. The report function (or clprofile tool, which calls this) can be
used to generate stats on lines of key=value pairs. The report function
will ignore other log lines without key=value pairs.

For example, if your application logs profile lines to /var/log/app,
you can run the following to get profile stats::

    clprofile < /var/log/app'''

import itertools
import math
import sys
import time

import clcommon.config
import clcommon.log
import clcommon.number

SI_PREFIXES_LARGE = ['', 'k', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y']
SI_PREFIXES_SMALL = ['', 'm', 'u', 'n', 'p', 'f', 'a', 'z', 'y']


class Profile(object):
    '''Class used to profile different metrics.'''

    def __init__(self):
        self._last_cpu = time.clock()
        self._last_time = time.time()
        self.marks = {}

    def reset_cpu(self):
        '''Set the CPU counter to the current value.'''
        self._last_cpu = time.clock()

    def reset_time(self):
        '''Set the time counter to the current value.'''
        self._last_time = time.time()

    def reset_all(self):
        '''Set all counters to the current values.'''
        self.reset_cpu()
        self.reset_time()

    def mark(self, name, value):
        '''Mark an arbitrary value.'''
        if name not in self.marks:
            self.marks[name] = 0.0
        self.marks[name] += value

    def mark_cpu(self, name, value=None):
        '''Mark the CPU time since the last call for the given name.'''
        if value is None:
            now = time.clock()
            value = now - self._last_cpu
            self._last_cpu = now
        self.mark('%s:cpu' % name, value)

    def mark_time(self, name, value=None):
        '''Mark the time since the last call for the given name.'''
        if value is None:
            now = time.time()
            value = now - self._last_time
            self._last_time = now
        self.mark('%s:time' % name, value)

    def mark_all(self, name):
        '''Mark all metrics with default values.'''
        self.mark_cpu(name)
        self.mark_time(name)

    def update(self, profile):
        '''Update this profile object with data from another.'''
        for name, value in profile.marks.iteritems():
            self.mark(name, value)

    def __repr__(self):
        output = []
        for name in sorted(self.marks.iterkeys()):
            value = clcommon.number.encode(self.marks[name], False)
            output.append('%s=%s' % (name, value))
        return ' '.join(output)


def report(log):
    '''Print a report of multiple timer outputs.'''
    data = report_data(log)
    print _('  Count    Mean     Min     Max  StdDev   Total')
    for name in sorted(data.keys()):
        formatted = dict(name=name)
        for key, value in data[name].iteritems():
            if isinstance(value, list):
                continue
            formatted[key] = clcommon.number.encode(value)
        print '%(count)7s %(average)7s %(min)7s %(max)7s %(stddev)7s ' \
            '%(total)7s  %(name)s' % formatted


def report_data(log):
    '''Collect and summarize the report data.'''
    data = {}
    while True:
        line = log.readline()
        if not line:
            break
        event_data = {}
        for part in line.split(' '):
            part = part.split('=')
            if part[0] == '' or len(part) != 2:
                continue
            name = part[0]
            try:
                value = float(part[1])
            except ValueError:
                continue
            update_event_data(event_data, name, value)
        for name, value in event_data.iteritems():
            _update_report_data(data, name, value)
    for name, name_data in data.iteritems():
        variance = 0
        average = data[name]['total'] / data[name]['count']
        for value in name_data['values']:
            variance += math.pow(value - average, 2)
        data[name]['average'] = average
        data[name]['variance'] = variance
        data[name]['stddev'] = math.sqrt(variance / data[name]['count'])
    return data


def update_event_data(data, name, value):
    '''Update event data struct with name and value.'''
    name_parts = name.split(':')
    name_type = name_parts.pop()
    if name_type in data:
        data[name_type] += value
    else:
        data[name_type] = value
    for length in xrange(len(name_parts)):
        for name in itertools.combinations(name_parts, length + 1):
            name = '%s:%s' % (':'.join(name), name_type)
            if name in data:
                data[name] += value
            else:
                data[name] = value


def _update_report_data(data, name, value):
    '''Update report data struct with name and value.'''
    if name not in data:
        data[name] = dict(count=1, values=[value], total=value, min=value,
            max=value)
        return
    data[name]['count'] += 1
    data[name]['values'].append(value)
    data[name]['total'] += value
    if value < data[name]['min']:
        data[name]['min'] = value
    if value > data[name]['max']:
        data[name]['max'] = value


def _main():
    '''Print report for data from logs or stdin.'''
    config, logs = clcommon.config.load(clcommon.log.DEFAULT_CONFIG)
    clcommon.log.setup(config)
    if len(logs) == 0:
        report(sys.stdin)
    else:
        for log in logs:
            report(open(log))


if __name__ == '__main__':
    _main()
