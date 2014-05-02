""" This tries to be the central place for all RPM-the-machine config issues.

Adding a new version of solaris to the repository should be as easy
as changing some variables here, and then everything will work.
Invariably, this will fail.

By convention, all functions returning directories will not end with a
trailing /
"""

special_dists = ['attic', 'error', 'retired']
standard_dists = ['hydrogen', 'helium', 'lithium',
                  'stable', 'testing','unstable','uranium']
dist_list = standard_dists + special_dists
fixed_to_floating = {'hydrogen':'stable',
                     'helium':'testing',
                     'lithium':'unstable',
		     'uranium':'uranium'}

repository_dir = '/rpm/repository/solaris'
error_dir = '/rpm/pending.error'
attic_dir = '/rpm/repository/solaris/.attic'
retired_dir = '/rpm/repository/solaris/.retired'
srpms_dir = '/rpm/repository/solaris/SRPMS'
sources_dir = '/rpm/repository/solaris/SOURCES'
sol_versions = (9,)
bitnesses = ('64',)

def ver_bit_pairs():
    return [(9, '64'),]

def rpm_dist_dir(dist, vers, bitness):
    assert int(vers) in sol_versions
    assert dist in dist_list and not dist in special_dists
    return '%s/%s' % (repository_dir, dist_suffix(dist, vers, bitness))

def rpm_special_dir(dist):
    if dist == 'attic': return attic_dir
    elif dist == 'error': return error_dir
    elif dist == 'retired': return retired_dir
    raise ValueError, "%s is not a special dist" % dist

def rpm_main_dir(dist, vers, bitness):
    return "%s/%s" % (rpm_dist_dir(dist, vers, bitness), 'RPMS.main')

def dist_suffix(dist, vers, bitness):
    return 'solaris%s-sparc%s/%s' % (vers, bitness, dist)

def pending_dir(dist):
    """ dist is either a floating or fixed dist, either works """
    assert dist in dist_list and dist != 'attic'
    if dist in fixed_to_floating:
        floating_dist = fixed_to_floating[dist]
    else:
        floating_dist = dist

    return "/rpm/CHECK_PEND.%s" % floating_dist
