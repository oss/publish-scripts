publish-scripts
===============
Rutgers package publishing scripts for Solaris 9. These take built RPM packages
and store their data in a database.

These must be run on a bootstrapped Solaris machine as it requires both yum and
apt-get.

Configuration Files
-------------------
The main config file is `publishscripts.conf`, which holds information about the
MySQL package database. This should typically be installed at `/usr/local/etc`.

The scripts use `rpm2html` and its configuration file, which is typically at
`/etc/rpm2html.config`.

Dependencies
------------
The scripts are extremely particular about its dependencies and requires that
most of them are in `/usr/local/bin`:

- GNU find
- checkrelease.sh
- cleanup-rpm2html
- createrepo (from yum)
- rebuild-apt
- rpm
- rpm2html
- rpmverify
- sendmail
