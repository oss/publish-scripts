#!/usr/bin/env python

""" Remove an rpm from an active distrobution and copy it to the attic """

import os
import shutil
import sys

import cp_rpm
import rpm_config

def usage():
    print "%s: dist pkg_names" % sys.argv[0]
    print "dist must be in one of '%s'" % ' '.join(rpm_config.dist_list)
    return 1

def main(argv):
    if len(argv) < 2:
        return usage()
    dist = argv[1]

    if dist == 'attic' or dist not in rpm_config.dist_list:
        return usage()

    pkgs_to_move = argv[2:]
    hit_error = 0
    for pkg in pkgs_to_move:
        for vers in rpm_config.sol_versions:
            for bitness in rpm_config.bitnesses:
                try:
                    existing_name = cp_rpm.make_from(pkg, dist, vers, bitness)
                    attic_name = cp_rpm.make_to(pkg, 'attic', vers, bitness)

                    shutil.copy(existing_name, attic_name)
                    os.remove(existing_name)
                except IOError, e:
                    print >> sys.stderr, e
                    hit_error = 1

    return hit_error

if __name__ == '__main__':
    sys.exit(main(sys.argv))
