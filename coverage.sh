#!/bin/sh
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

echo "+++ Preparing to run coverage"
coverage=`which coverage`
if [ -z $coverage ]; then
    coverage=`which python-coverage`
    if [ -z $coverage ]; then
        echo 'Python coverage not found'
        exit 1
    fi
fi

cd `dirname "$0"`
export PYTHONPATH=".:$PYTHONPATH"
rm -rf coverage.html .coverage*
echo

echo "+++ Running test suite"
$coverage run -p setup.py nosetests
echo

echo "+++ Running commands"
echo "a=1 a=2 a=3 a:b=2 a:b=10000" | $coverage run -p clcommon/profile.py
echo "a=1 a=2 a=3 a:b=2 a:b=10000" > test_profile
$coverage run -p clcommon/profile.py test_profile
rm test_profile
echo

echo "+++ Generating coverage report"
$coverage combine
$coverage html -d coverage.html --include='clcommon/*'
$coverage report --include='clcommon/*'
