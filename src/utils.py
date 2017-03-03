#!/usr/bin/python3
#
# utils: General utility functions
#
# Copyright (C) 2017 Endless Mobile, Inc.
# Authors:
#  Mario Sanchez Prada <mario@endlessm.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import os
import sys


def die(message):
    print(message, file=sys.stderr)
    sys.exit(1)


def filesystem_for_path(path):
    basedir = path
    while not os.path.exists(basedir):
        basedir = os.path.dirname(basedir)

    dev = os.stat(basedir).st_dev
    major_minor = '{}:{}'.format(os.major(dev), os.minor(dev))
    with open('/proc/self/mountinfo') as mountinfo:
        for line in mountinfo:
            fields = line.split()
            if fields[2] == major_minor:
                return fields[8]

    return None
