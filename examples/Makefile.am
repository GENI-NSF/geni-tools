addMemberToSliceAndSlivers: $(srcdir)/addMemberToSliceAndSlivers.py
	cp addMemberToSliceAndSlivers.py addMemberToSliceAndSlivers

readyToLogin: $(srcdir)/readyToLogin.py
	cp readyToLogin.py readyToLogin

remote-execute: $(srcdir)/remote-execute.py
	cp remote-execute.py remote-execute

# Distribute but do not install
EXTRA_DIST =  \
	addMemberToSliceAndSlivers.py \
	readyToLogin.py \
	remote-execute.py

CLEANFILES =  \
	addMemberToSliceAndSlivers \
	readyToLogin \
	remote-execute

bin_SCRIPTS = \
	addMemberToSliceAndSlivers \
	readyToLogin \
	remote-execute

EXTRA_DIST += \
	example_am_policies.json \
	example_am_policy_map.json \
	expirationofmyslices.py \
	myscript.py \
	renewSliceAndSlivers.py
