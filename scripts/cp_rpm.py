#!/usr/bin/env python

""" Make brute force copying of RPMs from dist to dist easier.

This module contains a few functions that make it easier to rollback 
changes. Although it should be less and less neccesary (don't break things 
in the first place, and there is nothing to fix), it's a lot easier to say
than to do.

cp_rpm.py attic testing openssl-0.96g-1ru

than it is to go and grab all the things you want and put them in the 
correct places.

Throughout these docs, vers and version means solaris version (eg, 9) and
bitness means either '64' or ''
"""

import shutil
import sys
import rpm_config

def concat_rpm(pkg, vers, bitness):
    """ @return name pkg would have if it were an rpm with given version
    and bitness """
    return '%s.solaris2.%i-sparc%s.rpm' % (pkg, vers, bitness)

def make_from(pkg, dist, vers, bitness):
    """ @return path to file in given dist with package name pkg

    assumes dist in dist_list """
    rpm = concat_rpm(pkg, vers, bitness)
    if dist in rpm_config.special_dists:        
        return '%s/%s' % (rpm_config.rpm_special_dir(dist), rpm)
    return '%s/%s' % (rpm_config.rpm_main_dir(dist, vers, bitness), rpm)

def make_to(pkg, dist, vers, bitness):
    """ @return path to copy a package with given dist, vers, and bitness """
    rpm = concat_rpm(pkg, vers, bitness)
    if dist in rpm_config.special_dists:
        return '%s/%s' % (rpm_config.rpm_special_dir(dist), rpm)
    return '%s/%s' % (rpm_config.pending_dir(dist), rpm)
        
def usage():
    print "%s: from_distribution to_distribution pkg_names" % sys.argv[0]
    print 'distributions must be in one of "%s"' % ' '.join(
        rpm_config.dist_list)
    return 1

def main(argv):
    """ see usage() """
    err_occured = 0
    if len(argv) < 3:
        return usage()

    dist_list = rpm_config.dist_list
    from_dist, to_dist = argv[1:3]
    pkgs_to_move = tuple(argv[3:])

    if (from_dist not in dist_list) or (to_dist not in dist_list):
        return usage()
    
    for pkg in pkgs_to_move:
        for vers in rpm_config.sol_versions:
            for bitness in rpm_config.bitnesses:
                try:
                    from_name = make_from(pkg, from_dist, vers, bitness)
                    to_name = make_to(pkg, to_dist, vers, bitness)
                    shutil.copy(from_name, to_name)
                except IOError, e:
                    err_occured = 1
                    print >> sys.stderr, e

    return err_occured
                    
if __name__ == '__main__':
    sys.exit(main(sys.argv))
