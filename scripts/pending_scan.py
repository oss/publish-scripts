#!/usr/bin/env python

""" Holds the logic for scanning of pending directories

This includes per-RPM dependency checks.  IE, things that can be checked
without needing a massive repository wide dependency check.  It does
version check against the repository, but it is relatively simple"""

import commands
import glob
import os
import sys

import rpm_config
import rpm_util


ACCEPT_LESSER, ACCEPT_EQUAL, ACCEPT_GREATER = (-1, 0, 1)

def sorted_list_of_keys(d):
    keys = d.keys()
    keys.sort()
    return keys

class PendingScan:
    """ Holds information about a scan of a pending directory

    It includes information like the publishability of RPMs based on
    their version in the repository against their version in pending.
    """
    def __init__(self, dist, pending_dir=None, accept_level=None,
                 rpm_ver='4.0.2', prefix=None):
        """ Create a report, perform scan

        @param dist distrobution to check for pending packages (eg, 'stable')
        
        @param pending_dir optional pending directory, if not given, will
        default to rpm_config.pending_dir(dist)
        
        @param accept_level strictness with which to accept pending packages
        based on their versions, @see categorize_pending
        
        @param rpm_ver maximum rpmlib capability allowed
        
        @param prefix optional place to pretend where repository lives
        when checking against existing packages
        """
        
        categories = categorize_pending(dist,pending_dir, accept_level,
                                        rpm_ver, prefix)
        accepted_tuples, old_tuples, missing_rpmlib_dep_tups, abandoned_rpms,\
                         srpms, sources = categories
                     
        self.pending_dir = pending_dir
        self.dist = dist        
        self._accepted_dict = dict(accepted_tuples)
        self._old_dict = dict(old_tuples)
        self._missing_deps = dict(missing_rpmlib_dep_tups)
        self._abandoned_rpms = abandoned_rpms
        self._srpms = srpms
        self._sources = sources

        for accepted in self._accepted_dict:
            assert not (accepted in self._missing_deps)
        for missing in self._missing_deps:
            assert not (missing in self._accepted_dict)

        self._abandoned_rpms.sort()

    def report_repo(self):
        """ @return repository that the report is about """
        return self.dist

    def accepted_rpms(self):
        """ @return sorted list of rpms accepted by the scan """
        return sorted_list_of_keys(self._accepted_dict)

    def old_rpms(self):
        """ @return sorted list of rpms that are too old by the scan """
        return sorted_list_of_keys(self._old_dict)
        
    def rpmlib_prob_rpms(self):
        """ @return sorted list of rpms that have missing dependencies
        on rpmlib"""
        return sorted_list_of_keys(self._missing_deps)

    def abandoned_rpms(self):
        """ @return sorted list of rpms that have no corresponding SRPM"""
        return self._abandoned_rpms

    def bad_rpms(self):
        """ @ return a list of packages would should not be accepted
        by the scan """
        return self.old_rpms() + self.abandoned_rpms() + \
               self.rpmlib_prob_rpms()

    def all_rpms(self):
        """ @return a list containing all the RPMs found in the scan """
        return self.accepted_rpms() + self.bad_rpms()
        
    def get_replaced(self, accepted_rpm):
        """ @return name of rpm in current repository that is being
        replaced by accepted_rpm in the pending directory """
        return self._accepted_dict[accepted_rpm]

    def get_denied(self, old_rpm):
        """ @return name rpm in the current repository that is of newer
        or equal to version than the old_rpm in pending directory """
        return self._old_dict[old_rpm]

    def get_lib_dep(self, dep_prob_rpm):
        """ @return the missing rpmlib dependency for the given
        dep_prob_rpm"""
        return self._missing_deps[dep_prob_rpm]

    def replaced_set(self, vers, bitness):
        """ @return dict keyed by rpms in with given vers and bitness
        in the existing repository that are being replaced by rpms
        in the pending directory
        """
        replaced = self._accepted_dict.values()
        return self._matching_ver_bit(vers, bitness, replaced)

    def accepted_set(self, vers, bitness):
        """ @return dict keyed by rpms with the given vers and bitness
        in the pending directory which should be sent to the published
        repository
        """
        return self._matching_ver_bit(vers, bitness, self._accepted_dict)

    def get_overridden(self, old_rpm):
        """ @return name of rpm that is staying in the repository,
        overriding the old_rpm from the publish """
        return self._old_dict[old_rpm]

    def acceptance_table(self):
        """ @return table that is easy to turn into textual representation

        The table is itself a list of (pkg_name, acceptance_list)
        where every item in acceptance list is a single character, either

        N for new
        E for empty
        O for too old
        A for accepted
        M for missing SRPM
        D for missing depdendency
        """
        table = {}
        indicies = {}
        count = 0
        for bitness in rpm_config.bitnesses:
            for vers in rpm_config.sol_versions:
                indicies[(str(vers), str(bitness))] = count
                count = count + 1

        for rpm in self.all_rpms():
            rpmname = rpm_util.extract_rpmname(rpm)
            num_dists = len(rpm_config.bitnesses)*len(rpm_config.sol_versions)
            table[rpmname] = [' '] * num_dists

        for accepted in self._accepted_dict:
            parsed = rpm_util.parse_rpmname(accepted)
            name, ver_bit = parsed[0], rpm_util.sol_ver_and_bit(parsed)

            if self.get_replaced(accepted) == None: status = 'N'
            else: status = 'A'

            table[name][indicies[ver_bit]] = status

        # should factor this crap out, it's basically all the same...
        for old in self._old_dict:
            parsed = rpm_util.parse_rpmname(old)
            name, ver_bit = parsed[0], rpm_util.sol_ver_and_bit(parsed)

            table[name][indicies[ver_bit]] = 'O'

        for dep_prob in self._missing_deps:
            parsed = rpm_util.parse_rpmname(dep_prob)
            name, ver_bit = parsed[0], rpm_util.sol_ver_and_bit(parsed)

            table[name][indicies[ver_bit]] = 'D'

        for abandoned in self._abandoned_rpms:
            parsed = rpm_util.parse_rpmname(abandoned)
            name, ver_bit = parsed[0], rpm_util.sol_ver_and_bit(parsed)

            table[name][indicies[ver_bit]] = 'M'
                        
        table = table.items()
        table.sort()
        return table
        
    def srpms(self):
        """ @return list of source rpms in the pending directory """
        return self._srpms

    def sources(self):
        """ @return list of all stuff that is not an rpm in the pending dir """
        return self._sources

    def _matching_ver_bit(self, vers, bitness, rpm_seq):
        vers, bitness = str(vers), str(bitness)
        ret = {}
        for rpm in rpm_seq:
            ver_bit = rpm_util.sol_ver_and_bit(rpm)
            if ver_bit == (vers, bitness) and rpm != None:
                ret[rpm] = 1
        return ret

# copied from /usr/local/bin/check_bootstrap.py, copying the code was
# dirty, should set up actual installer and such
class RpmDependencies:
    """ Extracts and stores the dependencies of an RPM """
    
    def __init__(self, filename):
        """  Ideally, this should work if filename is a direct path to an rpm
        or just an rpm name but for now, only works with direct paths
        """
        if not os.access(filename, os.O_RDONLY):
            raise IOError, '%s does not exist' % filename

        self._name = filename
        self._rpm_deps = []
        self._prog_deps = []
        self._cap_deps = []
        self._lib_deps = []

        self._parse_deps('rpm -qpR %s' % filename)

    def get_name(self):
        return self._name

    def get_cap_deps(self):
        return self._cap_deps

    def get_lib_deps(self):
        return self._lib_deps

    def get_prog_deps(self):
        return self._prog_deps

    def get_rpm_deps(self):
        return self._rpm_deps

    def _parse_deps(self, cmd):
        deps = commands.getoutput(cmd).split('\n')

        for depline in deps:
            if depline.startswith('warning:') or  \
               depline.startswith('error:'): continue
            dep = self._split_dep(depline)
            dep_name = dep[0]
            if dep_name.startswith('/'):
                self._prog_deps.append(dep)
            elif dep_name.startswith('rpmlib('):
                self._cap_deps.append(dep)
            elif dep_name.find('.so') != -1:
                self._lib_deps.append(dep)
            else:
                self._rpm_deps.append(dep)

    def _split_dep(self, depline):
        """ Break up dependency line from rpm output 

        @param depline single line from output of rpm dependency list
        @return 3-tuple containing (name, operator, version) from depline.
        operator and version will be '' if depline contains no spaces
        """
        split_depline = depline.split(' ')
        if len(split_depline) == 1:
            return (split_depline[0], '', '')
        elif len(split_depline) == 3:
            return tuple(split_depline)
        raise ValueError("%s confused me" % depline)

def partition(f, l):
    return (filter(f, l), filter(lambda x: not f(x), l))        
        
def categorize_pending(dist, pending_dir = None,
                       accept_level = ACCEPT_EQUAL,
                       rpm_ver = '4.0.2', repository_prefix = None):
    """ Categorize the files in the pending directory of given dist.

    @param dist distrobution to check for pending packages
    @param pending_dir optional place to check for pending packages, if 
    not given, it will just use dist to find the mapping.
    @param repository_prefix optional prefix for where to check for
    existing packages.
    
    @param accept_level leniency for which to accept RPMs when there are
    others in the existing repository of the same or greater versions.

    accept_level == ACCEPT_LESSER, all rpms will be published, even if 
    there is a newer version already in the repository.

    accept_level == ACCEPT_EQUAL, rpms in the pending directory will
    overwrite existing RPMs of lesser or equal versions.

    accept_level == ACCEPT_GREATER, the pending RPM version must be
    greater than the existing RPM.
    
    @return tuple of (accepted_rpms, too_old, srpms, sources)
    """
    def ends_with_rpm(fname): return fname.endswith('.rpm')
    def ends_with_src_rpm(fname): return fname.endswith('src.rpm')

    if pending_dir == None:        
        pending_dir = rpm_config.pending_dir(dist)

    rpms, sources = partition(ends_with_rpm, os.listdir(pending_dir))
    srpms, rpms = partition(ends_with_src_rpm, rpms)
    
    has_srpm, lacks_srpm = ensure_has_srpm(rpms, srpms, pending_dir)
    meets_rpmlib_dep, missing_rpmlib_dep = rpmlib_probs(has_srpm, rpm_ver,
                                                        pending_dir)
    
    pub_result = new_enough_rpms(meets_rpmlib_dep, dist, accept_level,
                                 repository_prefix)
    new_enough, too_old = pub_result

    return new_enough, too_old, missing_rpmlib_dep, lacks_srpm, srpms, sources

def rpmlib_probs(rpms_to_check, rpm_version_no_greater_than, pending_dir):
    """ Find problems with rpmlib dependencies being greater than
    rpm_version_no_greater_than

    @return (satisified, unsatisified)
    satisfied is a flatlist of accepted rpms
    unsatisfied is a list of tuples of (unsatisfied rpm, required_feature)
    """
    satisfied, unsatisfied = [], []
    comparable_max_ver = rpm_version_no_greater_than.split('.')
    
    for rpm in rpms_to_check:
        rpm_lib_reqs = RpmDependencies(pending_dir + '/' + rpm).get_cap_deps()
        this_one_is_unsat = 0
        for rpmlib_req in rpm_lib_reqs:
            comparable_req = rpmlib_req[2][:-2].split('.')
            if comparable_req > comparable_max_ver:
                unsatisfied.append((rpm, rpmlib_req))
                this_one_is_unsat = 1
                break
        if not this_one_is_unsat:
            satisfied.append(rpm)

    return satisfied, unsatisfied
            
def new_enough_rpms(rpm_list, dist, accept_level, prefix=None):
    """ @return tuple of (accepted_list, old_list) rpms.
    Each list is a tuple of (target, other), where target is the rpm in
    pending, and other is either None, or the rpm in the current repository

    @praram accept_level @see categorize_pending
    """
    accepted_rpms, old_rpms = [], []
    
    for rpm in rpm_list:
        parsed_rpm = rpm_util.parse_rpmname(rpm)
        
        vers_bitness = rpm_util.sol_ver_and_bit(parsed_rpm)
        if vers_bitness == None:
            print >> sys.stderr, "Warning, no vers/bitness for", rpm
            continue
        vers, bitness = vers_bitness

        if prefix == None:
            place_to_look = rpm_config.rpm_main_dir(dist, vers, bitness)
        else:
            unprefixed = rpm_config.rpm_main_dir(dist, vers, bitness)
            unprefixed = unprefixed[len(rpm_config.repository_dir):]
            place_to_look = prefix + unprefixed

        glob_same_name = "%s/%s*" % (place_to_look, parsed_rpm[0])
        rpms_with_same_name = glob.glob(glob_same_name)

        accepted, compared = version_order(parsed_rpm, rpms_with_same_name)
        if accepted >= accept_level:
            accepted_rpms.append((rpm, compared))
        else:
            old_rpms.append((rpm, compared))

    return accepted_rpms, old_rpms

def version_order(parsed_rpmname, existing_list):
    """ Determine the relative ordering of parsed_rpmname.

    @return tuple containing (code, other_rpmname), where code is -1 if
    parsed_rpmname is lesser in version than other_rpmname, 0 if it is
    the same, and 1 otherwise.  If there are no other rpms, other_rpmname
    will be None.
    """
    def remove_path(x):
        return x.split('/')[-1]
    existing_list = map(remove_path, existing_list)

    this_name = parsed_rpmname[0]
    this_version = rpm_util.extract_rpm_version(parsed_rpmname)
    found_eq_version = 0
    counted_others = 0
    compared_rpm = None
    
    for other_rpm in existing_list:
        parsed_other_rpm = rpm_util.parse_rpmname(other_rpm)
        try:
            other_name = parsed_other_rpm[0]
        except TypeError:
            print "Trouble parsing with ", other_rpm, " ... parsed as ", parsed_other_rpm
            continue
        if this_name == other_name:            
            other_version = rpm_util.extract_rpm_version(parsed_other_rpm)
            counted_others += 1
            compared_rpm = other_rpm
            if counted_others > 1:
                warning = "Warning, more than one %s in repo " % this_name
                print >> sys.stderr, warning
            if this_version < other_version:
                return (-1, compared_rpm)
            if this_version == other_version:
                found_eq_version = 1

    if found_eq_version:
        return (0, compared_rpm)
    return (1, compared_rpm)

def ensure_has_srpm(rpmlist, srpmlist, pending_dir):
    """ Make sure rpms in rpmlist have a corresponding srpm in srpmlist

    @return tuple of (has_srpm_list, lacks_srpm_list) based on the presense
    of an srpm of the same name in pending or in the SRPM directory
    """
    has_srpm, lacks_srpm = [], []

    srpm_dict = rpm_util.dict_from_list(srpmlist)
    for srpm in os.listdir(rpm_config.srpms_dir):
        srpm_dict[srpm] = 1

    for rpm_filename in rpmlist:
        full_path = pending_dir + '/' + rpm_filename
        srpm_which_built_rpm = rpm_util.parent_srpm(full_path)
        if srpm_which_built_rpm in srpm_dict:
            has_srpm.append(rpm_filename)
        else:
            lacks_srpm.append(rpm_filename)
            
    return (has_srpm, lacks_srpm)
