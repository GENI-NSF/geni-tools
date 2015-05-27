# Contributing to geni-tools

The GENI-NSF repositories are very much a community driven effort, and
your contributions are critical. A big thank you to all our [contributors](CONTRIBUTORS.md)!

## Mailing Lists
 * GENI developers discuss general GENI development on dev@geni.net. Subscribe here: http://lists.geni.net/mailman/listinfo/dev.
 * GCF / geni-tools developers can subscribe to gcf-dev@geni.net here: http://lists.geni.net/mailman/listinfo/gcf-dev.
 * Omni users may raise issues or get announcements on the general [GENI Users mailing list](https://groups.google.com/forum/#!forum/geni-users).

## General Guidelines
 - GENI-NSF projects are open source GitHub repositories, and as such follow the general [GitHub open source project guidelines](https://guides.github.com/activities/contributing-to-open-source/#contributing).
 - [Create a GitHub Issue](#reporting-issues) for any bug, feature, or enhancement you find or intend to address.
 - Submit enhancements or bug fixes using pull requests (see the [sample workflow below](#sample-contribution-workflow)).
 - GENI-NSF projects use the branching model found at
 http://nvie.com/posts/a-successful-git-branching-model/
  - All work happens in issue-specific branches off of the `develop`
  branch.
   - For example, a branch for Issue 123 might be named `tkt123-handlectrlc`.
 - Note that all `GENI-NSF` code is released under the [GENI Public License](LICENSE.txt) and should include that license.

## Tracking Issues
GCF / geni-tools has numerous existing tickets on [GitHub](https://github.com/GENI-NSF/geni-tools/issues). Look there first to see if the issue is known, or if there are comments on a suggested solution.

## Reporting Issues ##
 - Check [existing issues](https://github.com/GENI-NSF/geni-tools/issues) first to see if the issue has already been reported.
 - Review the general [GitHub guidlines on isssues](https://guides.github.com/features/issues/).
 - Give specific examples, sample outputs, etc
 - Do not include any passwords, private keys, your `omni.bundle`, or any information you don't want public.
 - When reporting issues, please include the output of `omni --version` at least. Even better, include the complete `stitcher.log` or the output of running `omni --debug`.
 - To attach your `stitcher.log` or test case RSpecs or other large output, upload the file to some web server and provide a pointer. For example, use Gist:
  - Copy & paste your log/patch/file attachment to http://gist.github.com/, hit the `Create Public` button and link to it from your issue by copying & pasting its URL.

## Getting the Source
GCF / geni-tools source code is available on [GitHub](https://github.com/GENI-NSF/geni-tools).

## Sample Contribution Workflow ##
 1. [Report the issue](#reporting-issues)
 2. Create an issue-specific branch off of the `develop` branch in your [fork of the repository](http://guides.github.com/activities/forking/)
  - Per the [branching model](http://nvie.com/posts/a-successful-git-branching-model/)
  - E.G. `git checkout develop` and then `git checkout -b tkt1234-addnewfeature`
 3. Develop your fix
  - Follow the [code guidelines below](#code-style).
  - Reference the appropriate issue numbers in your commit messages.
  - Include the [GENI Public License](LICENSE.txt) and a copyright notice in any new source files.
  - All changes should be listed in the [CHANGES](CHANGES) file, with an issue number.
   - Changes to Omni should additionally be listed in [README-omni.txt](README-omni.txt).
  - Where the options or command behavior has changed, document that in
 [README-omni.txt](README-omni.txt) or [README-stitching.txt](README-stitching.txt) as appropriate.
 4. Test your fix
  - Test your Omni/Stitcher fix against multiple aggregate types and varying situations.
  - Changes to gcf should be tested with [gcf-test.py](src/gcf-test.py) minimally, and
 preferably also with the included [AM acceptance tests](acceptance_tests/AM_API) or equivalent.
 5. [Pull in any new changes](https://help.github.com/articles/syncing-a-fork) from the main repository ('upstream' repository).
 6. [Submit a pull request](https://help.github.com/articles/using-pull-requests/) against the `develop` branch of the project repository.
 - In your pull request description, note what issue(s) your pull request addresses.

## Code Style ##
 - Include the [GENI Public License](LICENSE.txt) as a comment at the top of all source files.
 - Document all files and key classes and methods.
 - `geni-tools` attempts to be python2.6 compatible, and is not python3 compatible.
 - Use relative imports (`from __future__ import absolute_import`).
 - Use 4 space indents.
 - Name classes, methods, arguments and variables to describe their use.
 - Follow the [Python Style Guide](https://www.python.org/dev/peps/pep-0008/).

_Thank you for your contributions!_
