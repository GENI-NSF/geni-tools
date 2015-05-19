addMemberToSliceAndSlivers: $(srcdir)/addMemberToSliceAndSlivers.py
	cp addMemberToSliceAndSlivers.py addMemberToSliceAndSlivers

readyToLogin: $(srcdir)/readyToLogin.py
	cp readyToLogin.py readyToLogin

# Distribute but do not install
EXTRA_DIST =  \
	addMemberToSliceAndSlivers.py \
	readyToLogin.py

CLEANFILES =  \
	addMemberToSliceAndSlivers \
	readyToLogin

bin_SCRIPTS = \
	addMemberToSliceAndSlivers \
	readyToLogin

dist_pkgdata_SCRIPTS = \
	expirationofmyslices.py \
	myscript.py \
	remote-execute.py \
	renewSliceAndSlivers.py

EXTRA_DIST += \
	example_am_policies.json \
	example_am_policy_map.json
