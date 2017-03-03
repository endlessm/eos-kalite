bin_SCRIPTS = eos-kalite-backup

dist_pkgdata_SCRIPTS = \
	eos-kalite-backup.py \
	$(NULL)

do_edit = sed \
	-e "s|\@prefix\@|$(prefix)|" \
	-e "s|\@pkgdatadir\@|$(pkgdatadir)|"

eos-kalite-backup: eos-kalite-backup.in Makefile
	$(AM_V_GEN) $(do_edit) $<> $@

EXTRA_DIST = \
        eos-kalite-backup.in \
        $(NULL)

CLEANFILES = \
        eos-kalite-backup \
        $(NULL)
