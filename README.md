# eos-kalite-system-helper

This package provides the necessary hooks and service files needed to
integrate the KA Lite flatpak with the OS: creation of the home directory
for the 'kalite' user, installation of the systemd unit files to enable
socket-activation for the server and any other bit that could be needed.

This package uses dh_systemd to automate creation and registration of the
service and socket file, if it looks misty check the docs.
