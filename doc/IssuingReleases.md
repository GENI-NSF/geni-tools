# Creating a geni-tools Release
This document describes the typical process for creating a new release of geni-tools.

As a reminder, geni-tools follows the branching model found here: http://nvie.com/posts/a-successful-git-branching-model/, and follows the general [GitHub open source project guidelines](https://guides.github.com/activities/contributing-to-open-source/#contributing).

Creating a release involves:
 * Review Issues
 * Update Documentation
 * Create a release branch
 * Test and fix as needed
 * Create Windows and Mac binaries and test
 * Merge the release branch
 * Update develop for next release
 * Update wiki pages
 * Create release on Github
 * Send email announcing the release

## Review Issues and Pull Requests
* Ensure that there are no critical open issues or pull requests, particularly those targeted at the next release.
* Re target any remaining issues that will not be fixed for this release to the next release.

## Update Documentation
 1. `README-omni.txt` must document all options and commands. The top of the file must list recent Omni changes. Also confirm that the file displays nicely on a wiki page.
 2. `CHANGES` must document all recent changes in any of the tools, by version number. Also confirm that the file displays nicely on a wiki page.
 * Be sure all issues closed on Github with this milestone are listed, and closed issues are propertly targeted.
 4. `windows_install/LICENSE.txt` must properly reference all required 3rd party libraries used in the Mac and Windows binaries, with proper license text.
 5. Update others as needed. Check version numbers in these files:
  * `src/gcf/gcf_version.py`
  * `INSTALL.txt`
  * `windows_install/package_Builder.iss`
  * `mac_install/addAliases.command`
  * `mac_install/INSTALL.txt`
  * `mac_install/makeMacdmg.sh`
  * `agg_nick_cache.base`
  * `configure.ac`
  * `README-packaging.md`
 6. `agg_nick_cache.base` must use the new version number. The date will be wrong and fixed later.

## Create Release Branch
 1. `git fetch origin -p`
 2. `git checkout develop`
 3. `git merge origin/develop`
 4. `git checkout -b release-# develop`
 5. `git push origin release-#`

## Tag Release Candidates
Tag all release candidates (which creates a downloadable bundle on Github):
 1. `git fetch origin -p`
 2. `git checkout release-X`
 3. `git merge origin/release-X`
 4. `git tag -a -m "geni-tools 9.9-rc1" v9.9-rc1 release-9.9`
 5. `git push origin --tags`

## Test
Test and test some more. This is simply some suggestions. Bugs need issues and pull requests as usual, but fixes will be done on branches off of the release branch. Periodically create a new release candidate when bug fixes are made, to indicate it is time to redo release testing.

 1. Release candidates can be downloaded from Github: https://github.com/GENI-NSF/geni-tools/tags
 2. Confirm all fixes are listed in `CHANGES` and `README-omni`
 3. Test all new features (ideally as documented on the relevant pull request)
 4. Test all `amhandler` and `chhandler` commands, using the 'chapi' framework at least
  * In particular, create a reservation at multiple AM types, check status, list resources in slice, renew the reservation, mix APIv2 and APIv3
 where possible, (test scripts like `readyToLogin` here), then delete the reservation.
 5. Test key options (see Omni README), such as:
  * `-a`: test with `createsliver`, `listresources`
  * `--available`: test with `listresources` and `describe` at 2 different kinds of aggregates
  * `-c <omni config with non standard location>`
  * `-f <omni config framework, when have multiple in the omni_config>`
  * `-r <project>`: test with `listresources`
  * `--alap`: test with `renew` and `renewsliver` at 2 different kinds of aggregates and long expirations
  * `-V` to toggle between AM API v2 and v3 at least
  * `--useSliceAggregates`: test with `sliverstatus`
  * `--optionsfile <json file of options>`: Test that Omni correctly passes AM API options specified in this file. For example, do `poa geni_update_users` on an existing APIv3 reservation, and supply a JSON options file something like this:
```
{
 "geni_users": [
  {
   "urn": "urn:publicid:IDN+ch.geni.net+user+username",
   "keys": ["ssh-rsa AAAASSH-publi-key-goes-here==== keyID@machine"]
  }
 ]
}
```
  * `--speaksfor` with `--cred`: Test that Omni correctly passes the credential supplied in the file specified by `--cred` saying that the Omni user `--speaksfor` the user whose URN is given. See `src/gcf/geni/util/speaksfor_util.py`
  * `-u <sliver_urn>`: Test e.g. with `status`
  * `--warn`
  * `--tostdout`: Test with `listresource`
  * `-o`: Test e.g. with `getusercred`
  * `--outputfile`: Test e.g. with `listresources`
  * `--slicecredfile`: Test e.g. with `listresources`
  * `--NoGetVersionCache`: Test with listresources and ensure Omni does GetVersion first.

 6. Test key stitcher functions
  * Test stitch across AL2S using APIv2 to InstaGENI endpoint(s)
  * Test using APIv3
  * Try `delete`
  * Try `listresources`
  * Stitch to ExoGENI
  * Try a stitch to CloudLab, InstaGENI Utah
  * Test key stitcher options, like:
   * `--fileDir <new dir for stitcher output>`: Ensure all output goes in new directory
   * `--noReservation`: Stitcher should calculate the request but not do it
   * `--useExoSM` (with a reservation that uses ExoGENI resources)
 
 7. Test other experimenter scripts:
  * `readyToLogin`
  * `omni-configure` using a GENI Portal bundle
  * `clear-passphrases`
  * `remote-execute`
  * `addMemberToSliceAndSlivers`

 8. Test GCF tools
  * Run `gcf-am`, `gcf-ch` with both `-V2` and `-V3`.
  * Test using `gcf-test -V2` and `-V3` respectively.
  * See running instructions in `README-gcf.txt`.
 
## Create and test Windows and MAC Binaries
We create installers for geni-tools for Windows and MAC. Each of these must be created and separately tested.

See the [instructions on creating these binaries](CreatingBinaries.md).

To test these installers:
* Try each on the most recent version(s) of the OS, starting from a clean install of the OS
* Test each included executable

# Merge the release branch
When testing and bug fixes are complete, you can start making this release official.

Tag the new release
* `git fetch origin -p`
* `git checkout release-2.10`
* `git merge origin/release-2.10`
* `git tag -a -m "Release 2.10" v2.10 release-2.10`
* `git push origin --tags`

Merge in the release branch
* `git checkout master`
* `git merge origin/master`
* `git merge --no-ff release-2.10`
* `git push origin master`
* `git checkout develop`
* `git merge origin/develop`
* `git merge --no-ff release-2.10`
* `git push origin develop`

Delete the release branch
* `git push origin :release-2.10`
* `git branch -D release-2.10`

# Update develop for next release
Bump up the version number listed on develop to be the next release.

See EG: https://github.com/GENI-NSF/geni-tools/commit/f757f53e20451194438b1b7d32450dc9e1fca1cc

* `git checkout develop`
* `src/gcf/gcf_version.py`: edit `GCF_VERSION`
* Add a section in `CHANGES`
* Add a section in `README-omni.txt` for release notes
* `INSTALL.txt`: 3 sample commandlines
* `windows_install/package_builder.iss` (7 places)
* `mac_install/addAliases.command` (6 places)
* `mac_install/INSTALL.txt` (2 places)
* `mac_install/makeMacdmg.sh` (1 place)
* `agg_nick_cache.base` - update the date at the top and the current release number
* `configure.ac`
* `README-packaging.md`
* `agg_nick_cache.base`: This should reference the just-released version# and date

# Update wiki pages
Update the geni-tools wiki pages to describe the new release, and point to the new release for downloads. These instructions reference the old trac wiki pages. New pages are at https://github.com/GENI-NSF/geni-tools/wiki and should be similarly named and edited.

(Old) Docs are at http://trac.gpolab.bbn.com/gcf/

* Home page: Update release number and date, and the browse source link, and links to downloading the release
* `GettingGcf`: Update 2 links for downloading the release
* `QuickStart`: Update 1 link, including the label, plus 3 sections with sample text with version #s
* `ReleaseNotes`: Update to show the latest content from `CHANGES`
* `OmniOverview`: Update with new `README-omni.txt`, saving old copy as `Omni##Overview`
* `Omni`: Update version numbers, putting prior version in prior release section, referencing old Omni Overview
* `AmApiAcceptanceTests`: Update with `acceptance_Tests/AM_API/README-accept-AMAPI.txt`
* `Stitcher`: Update with `README-stitching.txt`
* `GcfQuickStart`: Update with `README-gcf.txt
* `Windows`: Update version numbers, download links
* `MacOS`: Update version numbers, download links
* `agg_nick_cache`: This file lives on Github now (see https://raw.githubusercontent.com/GENI-NSF/geni-tools/master/agg_nick_cache.base). After the release, update the version on the master branch in git to list the current Omni version / release date.
* Close existing milestone
* Create new milestone
* Re target any remaining issues that were not be fixed for this release to the next release.

# Create release on Github
* https://github.com/GENI-NSF/geni-tools/releases
* Hit `Draft a new release`
* Pick the proper tag
* Title release something like `Stitcher / Omni version 2.10`
* Give the release a nice description
* Attach the Windows and Mac binaries
* `Preview`, then `Publish`

# Email announcing the release
Announce the release to the community. Indicate if there are key reasons experimenters must update.

Email goes to:
`geni-users@googlegroups.com`, `gcf-developers@googlegroups.com`, `geni-developers@googlegroups.com`, `experimenters@geni.net`
