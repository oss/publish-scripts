#!/usr/bin/env python

import rpm_config
import rpm_util
import commands
import os


def parent_srpm(rpmname):
    # stolen and hushed from rpm_util.py
    """ @return name of source rpm that built rpmname """
    # need to actually query rpm in case of 'breakout' package
    query_string = "rpm -qp --queryformat '%{SOURCERPM}' " + rpmname + " 2>/dev/null"
    return commands.getoutput(query_string)

def main():
    for (vers, bitness) in rpm_config.ver_bit_pairs():
        for dist in rpm_config.fixed_to_floating.values():
            # only hit each dist once...
            rpm_list_dir = rpm_config.rpm_main_dir(dist, vers, bitness)
            for filename in os.listdir(rpm_list_dir):
                srpm_name = parent_srpm(rpm_list_dir + '/' + filename)
                srpm_loc = rpm_config.srpms_dir + '/' + srpm_name
                if not os.access(srpm_loc, os.F_OK):
                    print dist, filename, srpm_name

                    
    

if __name__ == '__main__':
    main()
