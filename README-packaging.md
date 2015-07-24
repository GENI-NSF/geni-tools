# Building a package for Debian/Ubuntu

The geni-tools distribution includes the information needed to build a
debian package. In order to build the package you must first install
the debian packaging tools. On Ubuntu 14.04, the tools can be
installed with the following command:

```
apt-get install -y build-essential devscripts ubuntu-dev-tools \
    debhelper dh-make diffutils patch cdbs quilt gnupg fakeroot \
    lintian pbuilder piuparts
```

Next, download the tar file. Check for the file on the releases tag at
the [GitHub project page](https://github.com/GENI-NSF/geni-tools).

The debian packaging tools are a bit finicky about file names. It is
necessary to rename the downloaded tar file to conform to the
expectations of the packaging tools. The rename can be done before or
after unpacking the tar file. Once the tar file has been downloaded,
follow these steps to build the package:

```
VERSION=2.10
mv geni-tools-${VERSION}.tar.gz geni-tools_${VERSION}.orig.tar.gz
tar zxf geni-tools_${VERSION}.orig.tar.gz
cd geni-tools-${VERSION}
debuild -us -uc
```

The resulting package files will now be in the parent directory
alongside the renamed tar file.

# Installing .deb file manually
Installation of the geni-tools debian package requires two
commands. The first attempts to install the package but is likely to
result in unfulfilled dependency errors. The apt-get command that
follows resolves the dependency errors and finishes the installation
of the geni-tools package.

If the package is stored in a debian package repository it would
install like any other debian package, with automatic dependency
handling. The extra step is only necessary when installing the debian
package manually.

```
dpkg -i geni-tools_2.10-1_all.deb
apt-get -f install
```

# Building a package for RedHat/CentOS

The geni-tools distribution includes the information needed to build an
rpm package. In order to build the package you must first install
the rpm packaging tools. On CentOS 6.6, the tools can be
installed with the following commands:

```
yum install rpm-build rpmdevtools rpmlint
yum groupinstall "Development Tools"
```

As a regular user (not root), set up an rpm build area:

```
rpmdev-setuptree
```

Download the geni-tools tar file. Check for the file on the releases tab at
the [GitHub project page](https://github.com/GENI-NSF/geni-tools).

Once the tar file has been downloaded,
follow these steps to build the package:

```
VERSION=2.10
tar zxf geni-tools-${VERSION}.tar.gz
mv geni-tools-${VERSION}.tar.gz "${HOME}"/rpmbuild/SOURCES
mv geni-tools-${VERSION}/geni-tools.spec "${HOME}"/rpmbuild/SPECS
cd "${HOME}"/rpmbuild/SPECS
rpmbuild -ba geni-tools.spec
```

This will generate the following files:
 * The rpm: `"${HOME}"/rpmbuild/RPMS/noarch/geni-tools-2.10-1.el6.noarch.rpm`
 * The source rpm: `"${HOME}"/rpmbuild/SRPMS/geni-tools-2.10-1.el6.src.rpm`

# Creating a yum repository

Install the `createrepo` tool:

```
yum install createrepo
```

Create a repository directory and move the files into it:

```
mkdir repo
cd repo
mv "${HOME}"/rpmbuild/RPMS/noarch/geni-tools-2.10-1.el6.noarch.rpm .
mv "${HOME}"/rpmbuild/SRPMS/geni-tools-2.10-1.el6.src.rpm .
mv "${HOME}"/rpmbuild/SOURCES/geni-tools-2.10.tar.gz .
mv "${HOME}"/rpmbuild/SPECS/geni-tools.spec .

```

Generate the repository metadata:

```
createrepo --database .
```

Copy this entire directory to the repository server
(update the host and path as needed):

```
scp -r * repo.example.com:/path/centos/6/os/x86_64
```

Configure yum for the new repository by creating a file
in `/etc/yum.repos.d` named geni.repo with the following
contents (updating the host and path as needed):

```
[geni]
name = GENI software repository
baseurl = http://repo.example.com/path/centos/$releasever/os/$basearch/
```
