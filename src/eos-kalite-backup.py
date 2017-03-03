#!/usr/bin/python3
#
# eos-kalite-backup: Backups management tool for KA Lite
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

import argparse
import flatpakutils
import logging
import os
import signal
import sys

from utils import die

KALITE_APP_ID = 'org.learningequality.KALite'
KALITE_APP_REMOTE_NAME = 'eos-apps'
KALITE_FLATPAK_BACKUP_SUBDIR = 'flatpak-repo'


def signal_handler(signal, frame):
    die('\nProcess interrupted!')


def backup_kalite_app(path, interactive=True):
    backup_path = os.path.join(path, KALITE_FLATPAK_BACKUP_SUBDIR)
    flatpakutils.backup_app(KALITE_APP_ID, KALITE_APP_REMOTE_NAME, backup_path, interactive)


def restore_kalite_app(path, interactive=True):
    backup_path = os.path.join(path, KALITE_FLATPAK_BACKUP_SUBDIR)
    flatpakutils.restore_app(KALITE_APP_ID, KALITE_APP_REMOTE_NAME, backup_path, interactive)


SUPPORTED_COMMANDS = {
    'backup-app' : backup_kalite_app,
    'restore-app' : restore_kalite_app
}


def run_command(command, path, interactive=True):
    logging.info("Running '{}' command...".format(command))

    func = SUPPORTED_COMMANDS.get(command)
    if func is None:
        die('Invalid command: {}'.format(command))
    func(path, interactive)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='eos-kalite-backup',
                                     description='Backups management for KA Lite (needs root access)')

    parser.add_argument('--no-interactive', dest='interactive', action='store_false',
                        help='Disables interactive prompts (accepts everything)')
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true',
                        help='Prints informative messages')
    parser.add_argument('--debug', dest='debug', action='store_true',
                        help='Prints informative plus debug messages')
    parser.add_argument('command', metavar='COMMAND', choices=SUPPORTED_COMMANDS.keys(),
                        help='<{}>'.format('|'.join(SUPPORTED_COMMANDS.keys())))
    parser.add_argument('path', metavar='PATH', action='store',
                        help='Path to the external location used to backup/restore KA Lite')

    parsed_args = parser.parse_args()
    if parsed_args.debug:
        logging.basicConfig(level=logging.DEBUG)
    elif parsed_args.verbose:
        logging.basicConfig(level=logging.INFO)

    # Most operations performed by this script require root
    # access (e.g. installing apps, restarting services...).
    if os.geteuid() != 0:
        die("This script needs to be run as the 'root' user!")

    # Make sure there's a way to interrupt progress even
    # when running long operations (e.g. restoring app).
    signal.signal(signal.SIGINT, signal_handler)

    run_command(parsed_args.command, parsed_args.path, parsed_args.interactive)
    sys.exit(0)
