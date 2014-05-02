#!/usr/bin/env python

""" Search repository for version differences among packages

This could be used to find out of date packages

We define an out of date package for a given software whose version in
the 'newer' repository (eg, testing is newer than stable, unstable is newer
than testing), is older than the version in the 'older' repository.
"""
import getopt
import glob
import operator
import os
import sys

import rpm_util
import rpm_config

func_mapping = {'lt': operator.lt, 'le': operator.le,
                'e': operator.eq,
                'ge': operator.gt, 'gt': operator.gt}

def usage(prog_name):
    sys.stdout = sys.stderr
    print "%s: [-c comp_type] dist_a dist_b" % prog_name
    print "Find packages in dist_b with corresponding comparision in dist_a"
    print "Each dist must be in list %s" % ' '.join(rpm_config.dist_list)
    print "comp_type is one of %s, defaults to le" % (', '.join(func_mapping))
    print "'%s -c le unstable testing' will versions of packages in"% prog_name
    print "unstable that are less than or equal to that of testing"
    return 1

def main(argv):
    try:
        opts, args = getopt.getopt(argv[1:], 'hc:')
    except getopt.GetoptError:
        return usage(argv[0])

    if len(args) < 2:
        return usage(argv[0])


    comp_func = operator.le

    for (opt, value) in opts:
        if opt == '-c':
            if not value in func_mapping:
                print >> sys.stderr, "invalid comparision: %s" % value
                return 1
            comp_func = func_mapping[value]
        if opt == '-h':
            return usage(argv[0])
    
    dist_list = rpm_config.dist_list
    newer_dist = args[0]
    older_dist = args[1]
    if (newer_dist not in dist_list) or (older_dist not in dist_list):
        print >> sys.stderr, "dists not in list"
        return usage(argv[0])
    
    for (ver, bitness) in rpm_config.ver_bit_pairs():
        new_main_dir = rpm_config.rpm_main_dir(newer_dist, ver, bitness)
        old_main_dir = rpm_config.rpm_main_dir(older_dist, ver, bitness)
        for fn in os.listdir(old_main_dir):
            mismatched_ver = find_comp_vers(fn, new_main_dir, comp_func)
            if mismatched_ver != None:
                print old_main_dir + '/' + fn, mismatched_ver

    return 0
            
def find_comp_vers(pkg_filename, newer_main_dir, comp_func):
    """ Find a comparable version of the package given by
    pkg_filename in newer_main_dir.

    @return a full path containing the name of the comparable package in
    newer_main_dir, or None if none exists
    """
    try:
        parsed_pkg_name = rpm_util.parse_rpmname(pkg_filename)
        pkg_ver_from_old_dist = rpm_util.extract_rpm_version(parsed_pkg_name)

        get_same_name_glob = '%s/%s*' % (newer_main_dir, parsed_pkg_name[0])
        for newer_dist_pkg_name in glob.glob(get_same_name_glob):
            basename = newer_dist_pkg_name.split('/')[-1]
            parsed_newer_name = rpm_util.parse_rpmname(basename)
            # prevent nastiness when one name is a prefix of another,
            # different package, eg rpm and rpm-devel, gc and gcc
            if parsed_newer_name[0] == parsed_pkg_name[0]:
                pkg_ver_from_new_dist = rpm_util.extract_rpm_version(
                    parsed_newer_name)
                if comp_func(pkg_ver_from_new_dist, pkg_ver_from_old_dist):
                    return newer_dist_pkg_name
            
    except (IndexError, TypeError), e:
        #print e
        print >> sys.stderr, "Warning: trouble finding existing versions for %s, malformatted filename?" % pkg_filename
        
    return None
    

if __name__ == '__main__':
    sys.exit(main(sys.argv))
