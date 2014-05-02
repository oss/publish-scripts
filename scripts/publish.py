#!/usr/bin/env python

""" Top level control of the publishing """


import os
import shutil

import dep_problems
run_system_cmd = dep_problems.run_system_cmd
import mail_publish
import pending_scan
import rpm_config

class PublishOutcome:
    """ Represents the result of a publish """
    def __init__(self):
        self.pending_scans = []
        self.per_dist_outcomes = []
        self.usernames_with_pkgs = {}

    def add_scan(self, scan):
        """ @param scan pending_scan.PendingScan """
        import pwd
        self.pending_scans.append(scan)
        
        for pkg in scan.all_rpms():
            uid = os.stat("%s/%s" % (scan.pending_dir, pkg))[4]
            username = pwd.getpwuid(uid)[0]
            self.usernames_with_pkgs[username] = 1

    def add_pub_result(self, dist_tuple, outcome):
        """ @param dist_tuple tuple of (dist, sol_ver, bitness)
        @param outcome string message describing unmet depedency changes
        in repository """
        self.per_dist_outcomes.append((dist_tuple, outcome))

    def pending_results(self):
        """ @return list of PendingScan that happened during publish"""
        return self.pending_scans

    def publish_outcomes(self):
        """ @return list of tuple of (dist_tuple, message)
        dist_tuple is a tuple of (dist, sol_ver, bitness)"""
        return self.per_dist_outcomes

    def get_publishers(self):
        """ @return list of usernames that owned a file in the pending dir """
        return self.usernames_with_pkgs.keys()

class Publisher:
    """ Responsible for publishing the repository.  Makes decisions about
    what kinds of problems are acceptable for different distrobutions,
    where to put the results of a publish, whether or not to do a dry-
    run, etc.
    """
    def __init__(self, dists, fake_run):
        self.backed_release = None
        self.dists_to_publish = dists
        self.fake_run = fake_run
        self.dep_prob_accept_levels = {'unstable': dep_problems.NEW_PKG,
                                       'testing': dep_problems.NO_NEW,
                                       'stable': dep_problems.NO_NEW,
                                       'uranium': dep_problems.NEW_PKG
				       }

        self.pkg_ver_accept = {'unstable': pending_scan.ACCEPT_LESSER,
                               'testing': pending_scan.ACCEPT_GREATER,
                               'stable': pending_scan.ACCEPT_GREATER,
                               'uranium': pending_scan.ACCEPT_LESSER
			       }

        self.rpm_max_ver = {'unstable':'9.0.0', #accept everything in unstable
                            'testing': '4.0.2',
                            'stable': '4.0.2',
                            'uranium':'9.0.0'
			    }
        
        
    def get_result_dir(self):
        if self.fake_run:
            result_dir = "%s/testing_publish" % rpm_config.repository_dir
            run_system_cmd("rm -rf %s" % result_dir)
            run_system_cmd("mkdir -p %s" % result_dir)
        else:
            result_dir = rpm_config.repository_dir
        return result_dir

    def get_pending_dir(self, dist):
        if self.fake_run:
            return "test/PENDING.%s" % dist           
        else:
            return rpm_config.pending_dir(dist)

    def accept_depend_probs(self, dep_prob_code, dist):
        """ @return non-zero if a dep_prob_code represents a small enough
        problem that the publish should go into production for given dist
        """
        if dist in self.dep_prob_accept_levels:
            return self.dep_prob_accept_levels[dist] >= dep_prob_code
        print >> sys.stderr, "Warning, distrobution", dist, "unknown"
        return 0

    def get_pkg_ver_limit(self, dist):
        return self.pkg_ver_accept.get(dist,pending_scan.ACCEPT_GREATER)

    def do_accept_pub(self, dist_tup, scan, pub_report, msg):
        """ Called when a dist_tup has been deemed worthy of publishing """
        dist, vers, bitness = dist_tup
        report_msg = "Publish accepted: " + msg
        print report_msg
        pub_report.add_pub_result(dist_tup, report_msg)
        real_publish(scan, dist, vers, bitness, self.fake_run)

    def do_reject_pub(self, dist_tup, scan, pub_report, msg):
        """ Called when a dist_tup has problems too severe to publish """
        dist, vers, bitness = dist_tup
        pend = scan.pending_dir
        print "Badness in new repository", msg
        pub_report.add_pub_result(dist_tup, "Rejected: " + msg)
        accepted = scan.accepted_set(vers, bitness)
        move_bad_pkgs_to_error(pend, accepted)
            
    def publish_all(self):
        """ Check every pending directory for new packages.
        If there are new packages, see if a publish would cause too many
        problems, and if so, don't publish it for real

        @param fake_run option to publish to testing RPM directories, and
        look into different places for pending packages
        @return PublishOutcome showing what this did
        """
    
        pub_report = PublishOutcome()    
        result_dir = self.get_result_dir()

        for dist in self.dists_to_publish: 
            pend = self.get_pending_dir(dist)

            pkg_ver_lim = self.get_pkg_ver_limit(dist)
            rpm_ver = self.rpm_max_ver[dist]
            scan = pending_scan.PendingScan(dist, pending_dir=pend,
                                            rpm_ver = rpm_ver,
                                            accept_level=pkg_ver_lim)
            pub_report.add_scan(scan)

            move_pending_srpms(scan)
            move_pending_sources(scan)
            bad_packages = scan.bad_rpms()
            move_bad_pkgs_to_error(pend, bad_packages)

            for (vers, bitness) in rpm_config.ver_bit_pairs():
                print dist, vers, bitness
                this_dist = (dist, vers, bitness)

                if len(scan.accepted_set(vers, bitness)) > 0:
                    dest_prefix = "%s/%s" % (
                        result_dir, rpm_config.dist_suffix(*this_dist))

                    cur_unmet = dep_problems.unmet(*this_dist)
                    new_unmet = pseudo_publish(scan, dist, vers, bitness,
                                               pend, dest_prefix)

                    dep_problem_code, msg = dep_problems.unmet_compare(
                        cur_unmet, new_unmet)

                    if self.accept_depend_probs(dep_problem_code, dist):
                        self.do_accept_pub(this_dist, scan, pub_report, msg)
                    else:
                        self.do_reject_pub(this_dist, scan, pub_report, msg)
                else:
                    pub_report.add_pub_result(this_dist, "Nothing pending")
                    print "No pending packages"
    
        return pub_report

def real_publish(scan, dist, vers, bitness, testing_run=None):
    """ Actually run genbasedir on the given distrobution.
    Note, this could be done without another genbasedir,
    but it would require a bit of magic.

    @param scan PendingScan for this dist
    @param dist floating dist, eg, stable
    """
    pending = scan.pending_dir
    publish_dir = rpm_config.rpm_main_dir(dist, vers, bitness)

    will_be_gone = scan.replaced_set(vers, bitness)
    accepted_set = scan.accepted_set(vers, bitness)
    
    copy_accepted_to_publish(publish_dir, pending, accepted_set)

    if (dist != 'retired'):
        # This shouldn't happen since retired is a "special" dist
        dist_dir = rpm_config.rpm_dist_dir(dist, vers, bitness)
        genbasedir_cmd = "genbasedir %s main" % dist_dir
        run_system_cmd(genbasedir_cmd, fake_it = testing_run)
        remove_accepted_pending_rpms(scan, vers, bitness)

    if ((dist == 'uranium') or (dist == 'unstable') or (dist == 'testing')):
        # follow convention, only atticize old packages if the dist
        # is not stable
        atticize_old_rpms(publish_dir, will_be_gone, testing_run)
    if (dist == 'stable'):
        retire_old_rpms(publish_dir, will_be_gone, testing_run)

def time_now():
    """ @return current time as string in YYYYMMDDHHMM format """
    import time
    time_tup = time.localtime()
    return  time.strftime("%G%m%d%H%M",time_tup)
    
def pseudo_publish(scan, dist, vers, bitness, pending, dest_prefix=None):
    """ Make a new rpm distrobution in order to check its consistancy.

    @param scan PendingScan for pending
    @param pending prefix to the place to look for incoming packages
    @param dest_prefix optional prefix to dist directory, defaults to
    rpm_config.rpm_dist_dir.

    @return unmet dependencies in newly published packages
    """
    if dest_prefix == None:
        dest_prefix = rpm_config.rpm_dist_dir(dist, vers, bitness)

    pub_time = time_now()
    pseudo_publish_dir = "%s/%s/RPMS.main" % (dest_prefix, pub_time)
    # current_dist_dir is the real repository to do an overlay to
    current_dist_dir = rpm_config.rpm_main_dir(dist, vers, bitness)

    run_system_cmd('mkdir -p %s' % pseudo_publish_dir)
    run_system_cmd('mkdir -p %s/%s/base' % (dest_prefix, pub_time))

    if dist == 'retired':
        will_be_gone = [] # don't remove old packages from retired
    else:
        will_be_gone = scan.replaced_set(vers, bitness)
    accepted_set = scan.accepted_set(vers, bitness)

    
    link_unchanged_existing(current_dist_dir, pseudo_publish_dir,will_be_gone)
    copy_accepted_to_publish(pseudo_publish_dir, pending, accepted_set)

    dest_munged_for_apt = '%s %s' % (dest_prefix, pub_time)

    # should look like
    # rpm file://rpm/repository/solaris/solaris9-sparc64/stable date main
    apt_contents = "rpm file:%s main\n" % dest_munged_for_apt
    
    run_system_cmd("genbasedir %s/%s main" % (dest_prefix, pub_time), silence=1)
    new_dep_probs = dep_problems.unmet(dist, vers, bitness,
                                       src_list_contents = apt_contents)
    
    return new_dep_probs 

def atticize_old_rpms(publish_dir, will_be_gone, testing_run = None):
    """ Move each package both in directory publish_dir and also in
    will_be_gone to the attic

    @param testing_run option to just print the move command, and not
    actually execute it.
    """ 
    attic_dir = rpm_config.attic_dir
    for gone_pkg in will_be_gone:
        mv_cmd = 'mv %s/%s %s' % (publish_dir, gone_pkg, attic_dir)
        run_system_cmd(mv_cmd, fake_it=testing_run)

def retire_old_rpms(publish_dir, will_be_gone, testing_run = None):
    """ Move each package both in directory publish dir (the stable
    directory) and also in will_be_gone to the retired directory

    @param testing_run option to just print the move command, and not
    actually execute it.
    """
    retired_dir = rpm_config.retired_dir
    for retired_pkg in will_be_gone:
        mv_cmd = 'mv %s/%s %s' % (publish_dir, retired_pkg, retired_dir)
        run_system_cmd(mv_cmd, fake_it=testing_run)

def move_bad_pkgs_to_error(pending_dir, bad_packages):
    error_dir = rpm_config.error_dir
    for bad_pkg in bad_packages:
        run_system_cmd('mv %s/%s %s' % (pending_dir, bad_pkg, error_dir))

def link_unchanged_existing(current_dist_dir, publish_dir, will_be_gone):
    """ Link each file in current_dist_dir to the publish_dir, if
    the file is not in will_be_gone
    """
    for existing_rpm in os.listdir(current_dist_dir):
        if not existing_rpm in will_be_gone:
            full_path_to_existing = "%s/%s" % (current_dist_dir, existing_rpm)
            dest_path = "%s/%s" % (publish_dir, existing_rpm)
            os.link(full_path_to_existing, dest_path)

def copy_accepted_to_publish(publish_dir, pending, accepted):
    """ Copy each package in accepted from the pending to publish_dir """
    for new_rpm in accepted:
        full_path_to_new = "%s/%s" % (pending, new_rpm)
        dest_path = "%s/%s" % (publish_dir, new_rpm)
        os.chmod(full_path_to_new, 0644)
        shutil.copy(full_path_to_new, dest_path)

def move_pending_sources(scan):
    """ Move all the sources from the scan into the main sources directory """
    for src in scan.sources():
        mv_from = '%s/%s' % (scan.pending_dir, src)
        os.chmod(mv_from, 0644)
        mv_to = '%s/%s' % (rpm_config.sources_dir, src)
        run_system_cmd('mv %s %s' % (mv_from, mv_to))

def move_pending_srpms(scan):
    """ Move all the source rpms from the scan into the srpms directory """
    for srpm in scan.srpms():
        mv_from = '%s/%s' % (scan.pending_dir, srpm)
        os.chmod(mv_from, 0644)
        mv_to = '%s/%s' % (rpm_config.srpms_dir, srpm)
        run_system_cmd('mv %s %s' % (mv_from, mv_to))

def remove_accepted_pending_rpms(scan, vers, bitness):
    """ Remove all accepted rpms from the pending directory.
    Caller should be sure the RPMs in pending aren't the only copies"""
    for rpm in scan.accepted_set(vers, bitness):
        full_path_to_rpm = '%s/%s' % (scan.pending_dir, rpm)
        # need to check existance incase of evil republishing of equal  
        # package numbers which causes an accepted package to be moved
        # to the attic
        if os.access(full_path_to_rpm, os.O_RDONLY):
            os.remove(full_path_to_rpm)     

def usage(argv):
    print "%s [-p] [dist1 [, dist2]]" % argv[0]
    print "Eg. %s unstable testing : publishes only testing and unstable" % argv[0]
    print "If not dists given, it is assumed you want to publish them all"
    print "-p : pseudo run, no changes to production repositories"
    print "-h : print this message"

def main(argv):
    import getopt
    fake_run = 0
    pending_dists = []

    try:
        opts, args = getopt.getopt(argv[1:], 'hf')
    except getopt.GetoptError:
        usage(argv)
        return 1

    for opt, val in opts:
        if opt == '-h':
            usage(argv)
            return 1
        elif opt == '-f':
            fake_run = 1
    
    if len(args) == 0:
        pending_dists = rpm_config.fixed_to_floating.values()
    else:
        for dist in args:
            if not dist in rpm_config.standard_dists:
                usage(argv)
                print "Error:", dist, "not a publishable dist"
                return 1
        pending_dists = args

    dep_problems.init()
    publisher = Publisher(pending_dists, fake_run)
    pub_result = publisher.publish_all()

    mail_publish.mail_publish_results(pub_result)
    return 0
        
if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv))
