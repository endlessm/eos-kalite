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
import pwd
import shutil
import signal
import subprocess
import sys

from utils import die

KALITE_APP_ID = 'org.learningequality.KALite'
KALITE_APP_REMOTE_NAME = 'eos-apps'
KALITE_HOME_DIR = '/var/lib/kalite'
KALITE_USER_ID = pwd.getpwnam('kalite')[2]
KALITE_GROUP_ID = pwd.getpwnam('kalite')[3]
KALITE_FLATPAK_BACKUP_SUBDIR = 'flatpak-repo'
KALITE_DATA_BACKUP_SUBDIR = 'kalite-data'
KALITE_SYSTEMD_UNIT_NAME = 'eos-kalite-system-helper'


def signal_handler(signal, frame):
    die('\nProcess interrupted!')


def backup_kalite_app(path, interactive=True):
    backup_path = os.path.join(path, KALITE_FLATPAK_BACKUP_SUBDIR)
    flatpakutils.backup_app(KALITE_APP_ID, KALITE_APP_REMOTE_NAME, backup_path, interactive)


def restore_kalite_app(path, interactive=True):
    backup_path = os.path.join(path, KALITE_FLATPAK_BACKUP_SUBDIR)
    flatpakutils.restore_app(KALITE_APP_ID, KALITE_APP_REMOTE_NAME, backup_path, interactive)


def stop_kalite_server():
    print("Stopping the KA Lite server...")
    kalite_pids = []
    try:
        kalite_pids = subprocess.check_output(['/usr/bin/pgrep', '-f', 'kalite-start']).split()
    except subprocess.CalledProcessError:
        print("The KA Lite server is not running. Nothing to do.")
        return

    for pid in kalite_pids:
        logging.info("Terminating process with PID {}...".format(pid))
        os.kill(int(pid), signal.SIGTERM)


def manage_kalite_services(command, types=['socket', 'service']):
    if command != 'start' and command != 'stop':
        die("Invalid command: systemctl {}".format(command))

    for service_type in types:
        logging.info("Trying to {} systemd {} unit: '{}'..."
                     .format(command, service_type, KALITE_SYSTEMD_UNIT_NAME))
        subprocess.check_call(['/usr/bin/systemctl', command, '{}.{}'
                               .format(KALITE_SYSTEMD_UNIT_NAME, service_type)])


def stop_kalite_services():
    print("Stopping KA Lite system services...")
    manage_kalite_services('stop')


def start_kalite_services():
    print("Starting KA Lite system services...")
    manage_kalite_services('start', ['socket'])


def recursive_chown(path, uid, gid):
    # Make sure permissions are properly set.
    for root, dirs, files in os.walk(path):
        for d in dirs:
            os.chown(os.path.join(root, d), uid, gid)

        # Use os.lchown(), not to follow symlinks.
        for f in files:
            os.lchown(os.path.join(root, f), uid, gid)

    os.chown(path, uid, gid)


def backup_kalite_data(path, interactive=True):
    print("Backing app KA Lite data into {}...".format(path))

    # Stop local KA Lite services and daemon, if running.
    stop_kalite_services()
    stop_kalite_server()

    # Backup all data into the external PATH.
    backup_path = os.path.join(path, KALITE_DATA_BACKUP_SUBDIR)
    if os.path.exists(backup_path):
        print('A previous backup already exists in {}. Continuing will remove it'.format(backup_path))
        if interactive and input('Do you want to continue? (y/n) ') != 'y':
            print("Stopping...")
            sys.exit(0)

        print("Removing data backup from {}...".format(backup_path))
        shutil.rmtree(backup_path)

    os.makedirs(backup_path)

    try:
        for data_path in ['content', 'database', 'httpsrv', 'locale', 'settings.py']:
            src_path = os.path.join(KALITE_HOME_DIR, data_path)
            dest_path = os.path.join(backup_path, data_path)

            print("Backing up {} to {}...".format(src_path, dest_path))
            if os.path.isdir(src_path):
                shutil.copytree(src_path, dest_path, symlinks=True)
            else:
                shutil.copy2(src_path, dest_path, follow_symlinks=True)

            # Make sure permissions are properly set.
            recursive_chown(dest_path, KALITE_USER_ID, KALITE_GROUP_ID)

    except OSError as e:
        die("Error backing up KA Lite data: {}".format(str(e)))

    # Restart the KA Lite socket service.
    start_kalite_services()

    print("Successfully backed up KA Lite data into {}!".format(backup_path))


def restore_kalite_data(path, interactive=True):
    print("Restoring app KA Lite data from {}...".format(path))

    backup_path = os.path.join(path, KALITE_DATA_BACKUP_SUBDIR)
    if not os.path.exists(backup_path):
        print('No backup found in {}. Nothing to do'.format(backup_path))
        sys.exit(0)

    # Stop local KA Lite services and daemon, if running.
    stop_kalite_services()
    stop_kalite_server()

    # Reset the local installation (removes all local data)
    print("Restoring KA Lite data to defaults **THIS WILL REMOVE ALL YOUR KA LITE DATA**")
    if interactive and input('Do you want to continue? (y/n) ') != 'y':
        print("Stopping...")
        sys.exit(0)

    # Remove and recreate KA Lite's home directory (/var/lib/kalite)
    if os.path.exists(KALITE_HOME_DIR):
        print("Found {} directory. Removing...".format(KALITE_HOME_DIR))
        shutil.rmtree(KALITE_HOME_DIR)

    # Re-create the home directory if it does not exist for some reason.
    try:
        print("Creating a new home directory at {}...".format(KALITE_HOME_DIR))
        os.makedirs(KALITE_HOME_DIR)
        os.chown(KALITE_HOME_DIR, KALITE_USER_ID, KALITE_GROUP_ID)

        local_user_data = os.path.expanduser('~/.var/app/{}'.format(KALITE_APP_ID))
        if os.path.exists(local_user_data):
            shutil.rmtree(local_user_data)

    except OSError as e:
        die("Error backing up KA Lite data: {}".format(str(e)))

    # Copy backed-up data from external PATH into place.
    try:
        for data_path in os.listdir(backup_path):
            src_path = os.path.join(backup_path, data_path)
            dest_path = os.path.join(KALITE_HOME_DIR, data_path)

            print("Restoring {} from {}...".format(dest_path, src_path))
            if os.path.isdir(src_path):
                shutil.copytree(src_path, dest_path, symlinks=True)
            else:
                shutil.copy2(src_path, dest_path, follow_symlinks=True)

        # Make sure permissions are properly set.
        recursive_chown(KALITE_HOME_DIR, KALITE_USER_ID, KALITE_GROUP_ID)

    except OSError as e:
        die("Error backing up KA Lite data: {}".format(str(e)))

    # Restart the KA Lite socket service.
    start_kalite_services()

    print("Successfully restored KA Lite data from {}!".format(backup_path))
SUPPORTED_COMMANDS = {
    'backup-app' : backup_kalite_app,
    'backup-data' : backup_kalite_data,
    'restore-app' : restore_kalite_app,
    'restore-data' : restore_kalite_data
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
