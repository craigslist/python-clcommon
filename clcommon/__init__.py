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

'''craigslist common package.

This is a collection of modules used by other packages or to be used
independently. See the documentation for each module for specifics on
how it should be used.'''

# Install the _(...) function as a built-in so all other modules don't need to.
import gettext
gettext.install('clcommon')

__version__ = '0'
