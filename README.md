publish-scripts
===============
Rutgers package publishing scripts for Solaris 9. These take built RPM packages
and store their data in a database.

These must be run on a bootstrapped Solaris machine as it requires both yum and
apt-get.

Overview
--------
The new publish script ensures that published packages have their dependencies
met in the repository.  It accomplishes this by publishing a psuedo repository,
which is the union of a set of pending packages and an existing repository. It
then checks the relative consistence of the psuedo repository against current
repository.  If the changes caused by publishing the pending packages are deemed
too problematic, the psuedo-publish is rejected, and no changes happen.
Otherwise, the changes are kept by running a publish on the actual repository.

The checker is made up of the following files:

- `publish.py` - Controls the man flow of the program, builds the repository
  with `genbasedir`, and determines what is acceptable.
- `dep_problems.py` - Munges the output of apt-cache dump unmet and is capable
  of qualifying differences between runs of apt-cache dump unmet.
- `pending_scan.py` - Sees what is in the pending directories, does version
  compares on RPMs in pending directories against RPMs of the same name in the
  existing repositories.
- `rpm_util.py` - Parses RPM names for package names, versions, mostly just
  string manipulation of rpm file names.
- `rpm_config.py` - Contains most of the "magic constants", like the repository
  structure, distribution names, and Solaris versions.
- `mail_publish.py` - Produces a summary of what publish did, and mails it to
  anyone owning a package in the pending directory.
- `test_*.py` - contain various sanity tests to make sure things are working as
  expected internally.

### Program Flow
`publish` iterates over the floating distributions, using `pending_scan` to see
what is in the corresponding pending directories.  If there are RPMs pending for
a given repository, publish will use `dep_problems` to find existing unmet
dependencies in the repository, then it will publish a non-production
repository.  It will again use `dep_problems` to see the differences in unmet
dependencies warrant throwing away the non-production repository; for example,
if there is a new package with unmet dependencies.  If all is well, it will then
call on `mail_publish` to mail the results of the publish to people owning files
in the pending directories.

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
