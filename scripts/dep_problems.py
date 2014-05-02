#!/usr/bin/env python

""" Use "apt-cache unmet" to find dependency problems.

Note, init must be called before any of this will work.
"""

import commands
import os
import sys

import rpm_config

config_dict = {"TEMPDIR":"/var/local/dep_problems",
               "RPM_ROOT":"/var/local/lib/vpkgs_only"}
apt_conf_template = """
Dir
{
    State "%(TEMPDIR)s/state";
    State
    {
        status "/usr/local/var/lib/rpm/status";
        lists "lists";
    }
    Cache "%(TEMPDIR)s/cache";
    Etc "%(TEMPDIR)s";
    Bin
    {
        Methods "/usr/local/lib/apt/methods";
        rpm "/usr/local/bin/rpm";
        dpkg "/usr/local/bin/dpkg";
    }
}
APT
{
    RootDir "/usr/local";
    Get
    {
        Show-Upgraded "true";
    }
}
Debug
{
    pkgRPMPM "false";
}
RPM
{
   DBPath "/var/local/lib/rpm/";
   RootDir "/";
   Options "-vv";
}
"""
apt_conf_contents = apt_conf_template % config_dict

def run_system_cmd(cmd, verbose = 1, critical=1, silence = 0, fake_it=0):
    if silence: cmd = cmd + ' 2>/dev/null >/dev/null'
    if verbose: print cmd
    if fake_it: return 0

    ret_val = os.system(cmd)
    if ret_val > 0 and critical:
        import traceback
        traceback.print_stack()
        sys.exit(1)

    return ret_val

def write_file(filename, data):
    """ writes and flushes data string into filename """
    fp = open(filename, 'w')
    fp.write(data)
    fp.close()
    
def init():
    run_system_cmd("rm -rf %(TEMPDIR)s" % config_dict)
    run_system_cmd("mkdir -p %(TEMPDIR)s" % config_dict)

    write_file("%(TEMPDIR)s/apt.conf" % config_dict, apt_conf_contents)

    cmds = ("""
    touch %(TEMPDIR)s/vendors.list; chmod 644 %(TEMPDIR)s/vendors.list      
    ln -s /usr/local/etc/apt/rpmpriorities %(TEMPDIR)s/rpmpriorities
    mkdir -p %(TEMPDIR)s/cache/archives/partial
    mkdir -p %(TEMPDIR)s/lists/partial
    mkdir -p %(TEMPDIR)s/state/lists/partial
    """ % config_dict).split('\n')

    map(run_system_cmd, cmds)

NO_NEW, PKG_TRADED_UNMET, PKG_NEW_UNMET, TRADED_PKG, NEW_PKG = range(5)

def unmet_compare(cur, new):
    """ See changes in the dependency problems between the current and new

    @param cur dependency problem info formatted like return of unmet
    @param new same format as current
    @return (code, description) where code is and integer of increasing
    value for increasing dependency badness, and description is a string
    containing some message about the problem

    Values for code, in increasing badness order

    NO_NEW for no new dependency problems
    PKG_TRADED_UNMET for when a package with a dependency problem in
    current also has a dependency problem in new, except that it is a
    different dependency
    PKG_NEW_UNMET for when a package with a dependency problem in current
    gains a new unmet dependency
    TRADED_PKG for when a package that used to be a dependency problem in
    current is now gone, but a package that did not have a problem in
    current has one in new
    NEW_PKG for when there are more packages with dependency problems in new
    than in current
    """
    def set_dif_msg(n, c):
        return ' '.join([pkg for pkg in n if not pkg in c])

    def stringify_unmet_entry(pkg, unmet):
        depended_upon_things = ', '.join(unmet[pkg])
        return "%s depends on %s " % (pkg, depended_upon_things)

    def list_new_entries(new, cur):
        return [stringify_unmet_entry(pkg, new)
                for pkg in new if not pkg in cur]
    
    if len(new) > len(cur):
        new_prob_msg = 'New packages with dependency problems \n\t ' \
                       + '\n\t'.join(list_new_entries(new, cur))
        return (NEW_PKG, new_prob_msg)
    elif len(new) == len(cur):
        for new_problem in new:
            if not new_problem in cur:
                new_probs = set_dif_msg(new, cur)
                gone_probs = set_dif_msg(cur, new)
                msg = "Solved some dependency problems, but created others\nNew problems are \n\t%s\nOld problems were \n\t%s" % (
                    '\n\t'.join(list_new_entries(new, cur)),
                    '\n\t'.join(list_new_entries(cur, new)))
                                
                return (TRADED_PKG, msg)

        for new_problem in new:
            if len(new[new_problem]) > len(cur[new_problem]):
                msg = "Package %s gained new dependency %s " % (
                    new_problem,set_dif_msg(new[new_problem],cur[new_problem]))
                return (PKG_NEW_UNMET, msg)

        for new_problem in new:
            for new_unmet_dep in new[new_problem]:
                if not new_unmet_dep in cur[new_problem]:
                    new_prob_list = new[new_problem]
                    cur_prob_list = cur[new_problem]
                    new_probs = set_dif_msg(new_prob_list, cur_prob_list)
                    gone_probs = set_dif_msg(cur_prob_list, new_prob_list)
                    msg = "%s swapped unmet dependencies\n\tgained %s\n\tlost %s" % (
                        new_problem, new_probs, gone_probs)
                    return (PKG_TRADED_UNMET, msg)

    return (NO_NEW, 'No new dependency problems')

def unmet(dist, vers, bitness, src_list_contents = None):
    """ Find unmet dependencies of given vers, bitness, and dist """

    if src_list_contents == None:
        src_list_contents = "rpm file:%s/solaris%s-sparc%s %s main\n" % (
            rpm_config.repository_dir, vers, bitness, dist)
    
    write_file("%(TEMPDIR)s/sources.list" % config_dict, src_list_contents)
    
    apt_args = "-c %(TEMPDIR)s/apt.conf -o Dir::etc=%(TEMPDIR)s -o RPM::RootDir=%(RPM_ROOT)s" % config_dict
    run_system_cmd("apt-get %s update" % apt_args)

    probs = commands.getoutput("apt-cache %s unmet" % apt_args).split('\n')    
    probs = parse_unmet(probs)

    return probs

def parse_unmet(unmet_lines):
    """ Parse the output of apt-cache dump

    @param unmet_lines new-line delimited list of strings
    @return dict keyed by package name yielding list of strings or tuples
    """
    unmet = {}
    cur_pkg = None
    cur_unmet_list = []
    
    for line in unmet_lines:
        splitline = line.split()
        if len(splitline) < 1: continue
        start_word = splitline[0].strip()

        if start_word == 'Package':
            if cur_pkg != None:
                assert len(cur_unmet_list) > 0, "something should be unmet"
                unmet[cur_pkg] = cur_unmet_list
                cur_unmet_list = []
            cur_pkg = "%s-%s" % (splitline[1], splitline[3])
        elif start_word == 'Depends:' or start_word == 'PreDepends:':
            cur_unmet_list.append(' '.join(splitline[1:]))
        else:
            raise ValueError, "Unparsed line: %s" % line

    if cur_pkg != None:
        unmet[cur_pkg] = cur_unmet_list

    return unmet            

