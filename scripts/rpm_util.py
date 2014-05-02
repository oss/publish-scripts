import re
import sys
import commands
import subprocess

version = '.1'
_dash_before_num = re.compile('-\d')
_dash_after_num = re.compile('\d+-')
_leading_numbers = re.compile('\d+') 

def dict_from_list(l):
	return dict([(key, None) for key in l])

def parent_srpm(rpmname):
	""" @return name of source rpm that built rpmname """
	# need to actually query rpm in case of 'breakout' package
	query_string = "rpm -qp --queryformat '%{SOURCERPM}' " + rpmname

	# this is ugly
#	out = subprocess.Popen(query_string.split(),stdout=subprocess.PIPE).communicate()[0].strip() 
#	print out
#
	return commands.getoutput(query_string)

def parse_rpmname(full_rpmname):
	""" Parse as much of an rpmname as is given.
	@param full_rpmname fullname like gtk2-2.2.2-0.solaris2.7-sparc.rpm
	@return (name, (major, minor, rel), internal_rel, dist)
	eg, in ('gtk2', ('2', '2', '2'), '0', 'solaris2.7-sparc')
	"""
	match_name = _dash_before_num.search(full_rpmname)
	if match_name == None: return None
	
	name = full_rpmname[:match_name.start()]
	version_and_dist = full_rpmname[match_name.start()+1:]

	match_version = _dash_before_num.search(version_and_dist)
	if match_version == None: return (name,)

	vers = version_and_dist[:match_version.start()]
	int_rel_and_dist = version_and_dist[match_version.start()+1:]
	vers = tuple(vers.split('.'))

	first_dot_index = int_rel_and_dist.find('.')
	if first_dot_index == -1: return (name, vers)

	int_rel = int_rel_and_dist[:first_dot_index]
	dist = int_rel_and_dist[first_dot_index+1:len(int_rel_and_dist)-4]
	return (name, vers, int_rel, dist)

def extract_rpmname(fullname):
	""" @param fullname string containing rpm filename """
	parsed = parse_rpmname(fullname)
	if parsed == None:				
		print >> sys.stderr, "warning [ %s ] didn't parse" % fullname
		return ''
	return parsed[0]

def sol_ver_and_bit(rpmname):
	""" Find out the solaris version and bitness of given rpmname

	@param rpmname either string containing full rpm filename, or
	format of the return value of parse_rpmname
	@return tuple of strings containing version and bitness
	(eg ('8', '64') or ('9', '')) or None if rpmname is unparseable
	"""
	if isinstance(rpmname, type('')):
		rpmname = parse_rpmname(rpmname)
	try:
		dist_str = rpmname[3]

		match_vers = _dash_after_num.search(dist_str)
		if match_vers == None:
			return None
		ver = dist_str[match_vers.start():match_vers.end()-1]

		if dist_str.endswith('64'):
			bit = '64'
		else:
			bit = ''
		
		return (ver, bit)
		
	except (IndexError, TypeError):
		return None
		

def _split_num_str(s):
	""" @return tuple of (int, string) from s, with the int being the
	leading numeral part of s, (or 0 if none is found) and the string
	being the rest of s"""
	match_leading_num = _leading_numbers.match(s)
	
	if match_leading_num:
		boundry = match_leading_num.end()
		num_begin = int(s[:boundry])
		str_end = s[boundry:]
	else:
		num_begin = 0
		str_end = s

	return (num_begin, str_end)

def extract_rpm_version(parsed_rpm_name):
	""" @param parsed_rpm_name tuple formatted like output
	of parse_rpmname
	
	@return tuple of (version, revision), which should order as expected
	"""
# whitespace sensitive ridiculous tab pkg_vers if in try
#	try:
	pkg_vers = parsed_rpm_name[1]
#	except IndexError, i:
#		print parsed_rpm_name, " is poorly formatted"
	split_pkg_vers = tuple(map(_split_num_str, pkg_vers))
	return (split_pkg_vers, _split_num_str(parsed_rpm_name[2]))
