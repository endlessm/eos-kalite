# eos-kalite

Collection of EOS-specific system helpers and tools for KA Lite

# Description

This package currently contains two main components

  * eos-kalite-system-helper: Socket-activated systemd unit (required)
  * eos-kalite-tools: Tools to manage KA Lite installations (optional)

## eos-kalite-system-helper

This provides the necessary hooks and service files needed to integrate
the KA Lite flatpak with the OS: creation of the home directory for the
'kalite' user, installation of the systemd unit files to enable
socket-activation for the server and any other bit that could be needed.

## eos-kalite-tools

At the moment, this package provides a tool to allow backing up and restoring
installations of the KA Lite flatpak app as well as its data (content), so that
one base installation can be used as the base "template" to restore either that
same machine in the future or as many other machines as needed.

This tool (`eos-kalite-backup`) allows "copying" any pre-installed data (videos,
language packs..) from the source machine into the target ones, so that it is
possible to prepare a specific configuration and curate a selection of content
in one place, and then have all of that easily replicated in other places.

Note that this is a custom tool only supported on EndlessOS, as it expects
certain components to be available in both the target machines, such as the
eos-kalite-system-helper package, certain flatpak runtimes, and so on.
