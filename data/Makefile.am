# systemd files for socket activated service
systemdsystemunit_DATA = \
	eos-kalite-system-helper.service \
	eos-kalite-system-helper.socket \
	$(NULL)

%.service: %.service.in Makefile
	$(AM_V_GEN) sed -e "s|\@bindir\@|$(bindir)|" $<> $@

# systemd tmpfiles.d
tmpfilesdir = $(prefix)/lib/tmpfiles.d
tmpfiles_DATA = eos-kalite-system-helper.conf

EXTRA_DIST = \
	eos-kalite-system-helper.service.in \
	eos-kalite-system-helper.socket \
	$(tmpfiles_DATA) \
	$(NULL)

CLEANFILES = \
	eos-kalite-system-helper.service \
	$(NULL)
