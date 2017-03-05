SUBDIRS = data src

# Set systemd unit directory that follows $prefix too for distcheck.
AM_DISTCHECK_CONFIGURE_FLAGS = \
	--with-systemdsystemunitdir='$${libdir}/systemd/system' \
	$(NULL)

-include $(top_srcdir)/git.mk
