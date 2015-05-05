# Contributing to geni-tools

The GENI-NSF repositories are very much a community driven effort, and
your contributions are critical. A big thank you to all our [contributors](CONTRIBUTORS.md)!

## Mailing Lists
GENI developers discuss general GENI development on dev@geni.net. Subscribe here: http://lists.geni.net/mailman/listinfo/dev

GCF / geni-tools developers can subscribe to gcf-dev@geni.net here: http://lists.geni.net/mailman/listinfo/gcf-dev

Omni users may raise issues or get announcements on omni-users@geni.net (subscribe here: http://lists.geni.net/mailman/listinfo/omni-users), or on the general [GENI Users mailing list](https://groups.google.com/forum/#!forum/geni-users).

## Tracking Issues
GCF / geni-tools has numerous existing tickets on our old Trac system: http://trac.gpolab.bbn.com/gcf. Look there first to see if the issue is known, or if there are comments on a suggested solution.

## Guidelines
 - geni-nsf projects use the branching model found at
 http://nvie.com/posts/a-successful-git-branching-model/
  - All work happens in issue-specific branches off of the `develop`
  branch, and then is merged back into `develop` using `merge --no-ff`.
   - For example, a branch for Issue 123 might be named `tkt123-handlectrlc`.
 - Create a GitHub Issue for any bug, feature, or enhancement you
 intend to address. (See [Reporting Issues](#reporting-issues))
 - Fork the repository and try to mimic [our code style](#code-style)
 - Note that all `geni-nsf` code is released under the [GENI Public
 License](LICENSE.txt) and should include a copyright notice.
 - Reference the appropriate issue numbers in your commit messages
 - All changes should be listed in the [CHANGES](CHANGES) file, with an issue
 number.
  - Changes to Omni should additionally be listed in
 [README-omni.txt](README-omni.txt)
 - Where the options or command behavior has changed, document that in
 [README-omni.txt](README-omni.txt) or [README-stitching.txt](README-stitching.txt) as appropriate.
 - Test your changes!
  - Changes to gcf should be tested with [gcf-test.py](src/gcf-test.py) minimally, and
 preferably also with the included AM acceptance tests or equivalent.
  - Changes to Omni can also be tested against GCF minimally, but a
 more complete set of tests against production aggregates is expected.
 - When done, create a pull request against the `develop` branch of
 the project repository
 - In your pull request description, note what issue(s) your pull
 request fixes or resolves

## Reporting Issues ##
 - Please check [GitHub Issues](https://github.com/GENI-NSF/geni-tools/issues) and our old [Trac tickets](http://trac.gpolab.bbn.com/gcf/report) to see if the issue has already been reported.
 - Please give specific examples, sample outputs, etc
 - When reporting issues, please include the output of `omni --version` at least. Even better, include the complete `stitcher.log` or the output of running `omni --debug`.

## Code Style ##
 - Include the [GENI Public License](LICENSE.txt) in all files as a comment at the top
 - Document all files and key classes and methods
 - `geni-tools` attempts to be python2.6 compatible, and is not python3.0 compatible
 - Use relative imports (`from __future__ import absolute_import`).
 - Use 4 space indents
