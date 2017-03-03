#!/usr/bin/python3
#
# eos-flatpak-utils: Helper utilities to handle flatpak apps in EOS
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
import logging
import os
import shutil
import subprocess
import sys
import tempfile

import gi
gi.require_version('Flatpak', '1.0')
from gi.repository import Flatpak
from gi.repository import Gio
from gi.repository import GLib
gi.require_version('OSTree', '1.0')
from gi.repository import OSTree

from utils import die

# Path to the flatpak system installation.
FLATPAK_SYSTEM_INSTALLATION = '/var/lib/flatpak'


def _look_up_ostree_ref_for_app_id(repo_path, app_id, remote_filter=None):
    ostree_repo = OSTree.Repo.new(Gio.File.new_for_path(repo_path))
    ostree_repo.open()

    target_ref = None
    _, refs = ostree_repo.list_refs()

    logging.info("Searching for {} ref in {}".format(app_id, str(refs)))
    for refspec in refs.keys():
        _, remote, ref = OSTree.parse_refspec(refspec)

        if remote_filter and remote != remote_filter:
            logging.info("{} != {}, skipping...".format(remote, remote_filter))
            continue

        if str.startswith(ref, 'app/{}/'.format(app_id)):
            target_ref = ref
            break

    return target_ref


def _delete_ostree_ref(repo_path, ref, remote=None):
    ostree_repo = OSTree.Repo.new(Gio.File.new_for_path(repo_path))
    ostree_repo.open()

    full_ref = '{}:{}'.format(remote, ref) if remote else '{}'.format(ref)
    logging.info("Deleting OSTree reference '{}'...".format(full_ref))

    ostree_repo.set_ref_immediate(remote, ref, None)


def _copy_ostree_ref(repo_path, from_ref, to_ref, from_remote=None, to_remote=None):
    ostree_repo = OSTree.Repo.new(Gio.File.new_for_path(repo_path))
    ostree_repo.open()

    from_param = '{}:{}'.format(from_remote, from_ref) if from_remote else '{}'.format(from_ref)
    to_param = '{}:{}'.format(to_remote, to_ref) if to_remote else '{}'.format(to_ref)

    logging.info("Copying OSTree reference '{}' to {}...".format(from_param, to_param))
    _, rev = ostree_repo.resolve_rev(from_param, False)
    ostree_repo.set_ref_immediate(to_remote, to_ref, rev)


def _pull_local_ref(repo_path, src_repo_path, ref):
    def _progress_callback(status, progress, estimating, user_data):
        # We rely on the progress status message from flatpak
        # here, no need to worry about the other parameters.
        print("Progress: {}".format(status), end='\r')

    logging.info("Pulling ref {} from repo at {} to repo at {}"
                 .format(ref, src_repo_path, repo_path))

    pull_args = {
        'flags': GLib.Variant('i', OSTree.RepoPullFlags.NONE),
        'refs': GLib.Variant('as', [ref]),
        'depth': GLib.Variant('i', 0),
        'disable-static-deltas': GLib.Variant('b', True),
    }
    pull_var = GLib.Variant('a{sv}', pull_args)

    repo = OSTree.Repo.new(Gio.File.new_for_path(repo_path))
    repo.open()

    progress = OSTree.AsyncProgress.new()
    progress.connect('changed', OSTree.Repo.pull_default_console_progress_changed, None)
    repo.pull_with_options(GLib.filename_to_uri(src_repo_path), pull_var, progress, None)


def backup_app(app_id, app_remote_name, target_repo_path, interactive=True):
    print("Backing {} app into {}'...".format(app_id, target_repo_path))

    # Search for the app in the system installation.
    system_repo_path = os.path.join(FLATPAK_SYSTEM_INSTALLATION, 'repo')
    target_ref = _look_up_ostree_ref_for_app_id(system_repo_path, app_id, app_remote_name)
    if not target_ref:
        die("{} is not installed. Can't back it up!".format(app_id))

    print("Found {} app with ref '{}'".format(app_id, target_ref))

    # We need to temporarily create a local reference to the app,
    # so that we can pull it into a temporary repo afterwards.
    _copy_ostree_ref(system_repo_path, target_ref, target_ref, app_remote_name, None)

    print("Looking for an already existing repository at {}...".format(target_repo_path))
    if os.path.exists(target_repo_path):
        print('An OSTree repository already exists in {}. Continuing will remove it'.format(target_repo_path))
        if interactive and input('Do you want to continue? (y/n) ') != 'y':
            print("Stopping...")
            sys.exit(0)

        print("Removing data from {}...".format(target_repo_path))
        shutil.rmtree(target_repo_path)

    try:
        logging.info("Creating temporary OSTree repository at {}".format(target_repo_path))
        os.makedirs(target_repo_path, exist_ok=True)

        ext_repo = OSTree.Repo.new(Gio.File.new_for_path(target_repo_path))
        ext_repo.create(OSTree.RepoMode.ARCHIVE_Z2, None)
    except OSError as e:
        die("Could create directory at {}: {}".format(target_repo_path, str(e)))
    except GLib.Error as e:
        die("Could not create OSTree repository at {}: {}".format(target_repo_path, e.message))

    # Now pull the local reference to the temporary repository, and
    # remove the temporary local reference, as it's no longer needed.
    print("Pulling {} app into external repository at {}...".format(app_id, target_repo_path))
    _pull_local_ref(target_repo_path, system_repo_path, target_ref)
    _delete_ostree_ref(system_repo_path, target_ref, None)

    # Finally, make sure the summary file in the temporary OSTree repository
    # is updated with the metadata from the flatpak app, for which we can't
    # simply use 'ostree summary', but 'flatpak build-update-repo' instead.
    logging.info("Updating summary file of temporary repository at {}...".format(target_repo_path))
    subprocess.check_call(['/usr/bin/flatpak', 'build-update-repo', target_repo_path])

    print("Successfully backed up {} app!".format(app_id))


def _create_temporary_remote(installation, source_repo_path, app_id):
    tmp_remote_name = 'tmp-{}'.format(app_id)
    tmp_remote_url = GLib.filename_to_uri(source_repo_path, None)

    tmp_remote = Flatpak.Remote.new(tmp_remote_name)
    tmp_remote.set_url(tmp_remote_url)
    tmp_remote.set_gpg_verify(False)
    logging.info("Created temporary repository {} with URL {}"
                 .format(tmp_remote_name, tmp_remote_url))

    try:
        installation.modify_remote(tmp_remote)
    except GLib.Error as e:
        die("Could not update configuration for remote '{}': {}".format(tmp_remote_name, e.message))

    return tmp_remote_name


def _install_app_from_ostree_ref(installation, source_repo_path, ostree_ref, remote_name):
    def _progress_callback(status, progress, estimating, user_data):
        # We rely on the progress status message from flatpak
        # here, no need to worry about the other parameters.
        print("Progress: {}".format(status), end='\r')

    # Install the app from the temporary repository.
    target_ref_parts = ostree_ref.split('/')
    if len(target_ref_parts) < 4:
        die("Could not determine branch of {} app".format(app_id))

    app_id = target_ref_parts[1]
    app_arch = target_ref_parts[2]
    app_branch = target_ref_parts[3]
    logging.debug("App ID: {} / Arch: {} / Branch: {}".format(app_id, app_arch, app_branch))

    try:
        print("Restoring {} app from {}...".format(app_id, source_repo_path))
        installation.install(remote_name,
                             Flatpak.RefKind.APP,
                             app_id, app_arch, app_branch,
                             _progress_callback,
                             None,
                             None)
        print("\nFinished restoring {}".format(app_id))
    except GLib.Error as e:
        die("Could not restore {} app': {}".format(app_id, e.message))


def _update_deploy_file_for_app_and_remote(app_id, old_remote_name, new_remote_name):
    deploy_file_path = os.path.join(FLATPAK_SYSTEM_INSTALLATION,
                                    'app', app_id, 'current', 'active', 'deploy')
    logging.debug("Reading data from the deploy file at {}...".format(deploy_file_path))

    src_file_contents = None
    with open(deploy_file_path, 'rb') as f:
        src_file_contents = GLib.Bytes.new(f.read())

    # We need to read the GVariant in the deploy file and generate a
    # new one with all the same content but the right remote set.
    variant_type = GLib.VariantType.new('(ssasta{sv})')
    orig_variant = GLib.Variant.new_from_bytes(variant_type, src_file_contents, False)
    logging.debug("Original variant: {}".format(str(orig_variant)))

    builder = GLib.VariantBuilder.new(variant_type)
    for idx, val in enumerate(orig_variant):
        # We just need to replace the first element in the Variant.
        if idx == 0:
            builder.add_value(GLib.Variant.new_string(new_remote_name))
        else:
            builder.add_value(orig_variant.get_child_value(idx))

    new_variant = builder.end()
    logging.debug("New variant: {}".format(str(new_variant)))

    # Write the new GVariant to a temporary file and replace the original one.
    with tempfile.NamedTemporaryFile() as tmp_deploy_file:
        logging.info("Building new deploy file at {}, pointing to remote '{}'..."
                     .format(tmp_deploy_file.name, old_remote_name))

        # Write temporary file to disk and overwrite the original one with it.
        dest_file = Gio.File.new_for_path(tmp_deploy_file.name)
        out_stream = dest_file.append_to(Gio.FileCreateFlags.NONE, None)
        out_stream.write_bytes(new_variant.get_data_as_bytes())

        os.chmod(tmp_deploy_file.name, 0o644)
        shutil.copy(tmp_deploy_file.name, deploy_file_path, follow_symlinks=True)


def restore_app(app_id, app_remote_name, source_repo_path, interactive=True):
    print("Restoring {} app from {}'...".format(app_id, source_repo_path))

    print("Looking for an existing source repository at {}...".format(source_repo_path))
    if not os.path.exists(source_repo_path):
        die('Could not find any flatpak repository in {}'.format(source_repo_path))

    # Search for the app in the external repository.
    target_ref = _look_up_ostree_ref_for_app_id(source_repo_path, app_id)
    if not target_ref:
        die("{} is not present in the external repository. Can't restore!".format(app_id))

    print("Found {} app in external repository with ref '{}'".format(app_id, target_ref))

    try:
        installation = Flatpak.Installation.new_system()
        logging.info("Found Flatpak system installation")
    except GLib.Error as e:
        die("Couldn't find system flatpak installation: {}".format(e.message))

    try:
        remote = installation.get_remote_by_name(app_remote_name)
        logging.info("Found {} remote in Flatpak system installation".format(app_remote_name))
    except GLib.Error as e:
        die("Could not find remote '{}': {}".format(app_remote_name, e.message))

    # Create a temporary remote and installed the backed up application from there.
    tmp_remote_name = _create_temporary_remote(installation, source_repo_path, app_id)
    _install_app_from_ostree_ref(installation, source_repo_path, target_ref, tmp_remote_name)

    # Update the deploy file to pretend the app has been installed
    # from the remote it has been initially backed up from.
    _update_deploy_file_for_app_and_remote(app_id, tmp_remote_name, app_remote_name)

    # Backup the OSTree reference created for the temporary remote
    # into the eos-apps remote, before removing that remote.
    system_repo_path = os.path.join(FLATPAK_SYSTEM_INSTALLATION, 'repo')
    _copy_ostree_ref(system_repo_path, target_ref, target_ref, tmp_remote_name, app_remote_name)

    # Remove temporary repository and finish.
    try:
        installation.remove_remote(tmp_remote_name)
        logging.info("Removed  temporary remote '{}'".format(tmp_remote_name))
    except GLib.Error as e:
        die("Could not remove temporary remote '{}': {}".format(tmp_remote_name, e.message))

    print("Successfully restored {} app!".format(app_id))


if __name__ == '__main__':
    def _progress_callback(status, progress, estimating, unused):
        print("Progress: {}".format(status), end='\r')

    parser = argparse.ArgumentParser(description='Offline installation tool for KA Lite (needs root access)')
    parser.add_argument('--no-interactive', dest='interactive', action='store_false',
                        help='Disables interactive prompts (accepts everything)')
    parser.add_argument('--debug', dest='debug', action='store_true',
                        help='Prints informative plus debug messages')

    parsed_args = parser.parse_args()
    if parsed_args.debug:
        logging.basicConfig(level=logging.DEBUG)

    test_app_id = 'com.endlessm.videonet'
    test_remote = 'eos-apps'
    test_branch = 'eos3'
    test_backup_dir = os.path.expanduser('~/BACKUP')

    installation = Flatpak.Installation.new_system()

    # Make sure the target app is installed first.
    print("\n1. Making sure {} is installed before backing up...".format(test_app_id))
    try:
        installation.install(test_remote,
                             Flatpak.RefKind.APP,
                             test_app_id, None, test_branch,
                             _progress_callback,
                             None,
                             None)
        print("\n{} successfully installed".format(test_app_id))
    except GLib.Error as e:
        print("Could not install {}: {}".format(test_app_id, e.message))

    # Backup the app now.
    print("\n2. Backing up app {} to {}...".format(test_app_id, test_backup_dir))
    backup_app(test_app_id, test_remote, test_backup_dir, parsed_args.interactive)

    # Can't restore and app if it's installed!
    try:
        print("\n3. Making sure {} is NOT installed before restoring...".format(test_app_id))
        installation.uninstall(Flatpak.RefKind.APP,
                               test_app_id, Flatpak.get_default_arch(), test_branch,
                               _progress_callback,
                               None,
                               None)
        print("\n{} successfully uninstalled".format(test_app_id))
    except GLib.Error as e:
        print("Could not uninstall {}: {}".format(test_app_id, e.message))

    # Finally, restore the app.
    print("\n4. Restoring app {} from {}...".format(test_app_id, test_backup_dir))
    restore_app(test_app_id, test_remote, test_backup_dir, parsed_args.interactive)
    sys.exit(0)
