
""" Mail publish logs """

import pickle

import rpm_config
import rpm_util

def make_bit_ver(bit, ver):
    """ Used to 'Fill in' bit, if it's '', make it '32' """
    if bit == '': return str(ver) + ' 32'
    else: return str(ver) + ' 64'

def rpm_ver_str(rpmname):
    """ Get human readable package version-patchlevel string from rpmname """
    parsed = rpm_util.parse_rpmname(rpmname) 
    return '.'.join(parsed[1]) + '-' + parsed[2]

def split_into_ver_bit_name_pending_existing(pending, existing):
    """ Assumes pending and existing are packages with the same name,
    in the same solaris version, with the same bitness 
    Returns tuple of
    """
    sol_ver, bitness = rpm_util.sol_ver_and_bit(pending)
    if bitness == '': bitness = '32'
    pkg_name = rpm_util.extract_rpmname(pending)
    pending_vers = rpm_ver_str(pending)
    existing_vers = rpm_ver_str(existing)
    return (sol_ver, bitness, pkg_name, pending_vers, existing_vers)

def pending_outcome_summary(pub_result):
    msg_lines = []
    for (dist_tuple, outcome) in pub_result.publish_outcomes():
        dist, sol_ver, bitness = dist_tuple
        if bitness == '': bitness = '32'
        msg_for_dist = "%s %s %s: %s" % (dist, str(sol_ver), bitness, outcome)
        msg_lines.append(msg_for_dist)

    return '\n'.join(simple_compress(msg_lines))

def simple_compress(string_list, sep=':'):
    inverted_dict = {}
    
    for s in string_list:
        split_s = s.split(':', 1)
        if len(split_s) == 1:
            inverted_dict[s] = []
        elif len(split_s) == 2:
            head, tail = split_s
            if tail in inverted_dict:
                inverted_dict[tail].append(head)
            else:
                inverted_dict[tail] = [head]

    compressed_list = []

    for tail in inverted_dict:
        head_list = inverted_dict[tail]
        if len(head_list) == 0:
            compressed_list.append(tail)
        elif len(head_list) == 1:
            compressed_list.append('%s%s%s' % (head_list[0], sep, tail))
        else:
            concatted_heads = ' '.join(head_list)
            compressed_list.append('[%s]%s%s' % (concatted_heads, sep, tail))

    return compressed_list
                        
# because recipient is too hard to spell
def publish_receivers(publishers):
    """ @param usernames who published

    @return list of email address to mail the publish results to """
    publishers = map(lambda x: x + '@oss.rutgers.edu', publishers)
    if 'root@oss.rutgers.edu' in publishers:
        publishers.remove('root@oss.rutgers.edu')
        publishers.append('oss@oss.rutgers.edu')
    publishers.append('oss-rpm@oss.rutgers.edu')
    return publishers

def accept_table_text(acceptance_table, dist):
    """ @return string with newlines containing textual representation
    of the acceptance table data """
    if len(acceptance_table) == 0:
        return "Nothing pending for %s" % dist
    
    table_lines = []
    table_lines.append("VERSION CHECKING \n Pending scan for %s" % dist)

    max_name_len = max(map(lambda x: len(x[0]), acceptance_table))
    
    header = [make_bit_ver(bit, ver) for bit in rpm_config.bitnesses
              for ver in rpm_config.sol_versions]
    header = ' ' * max_name_len + ' '.join(header)
    table_lines.append(header)
        
    for pkg_name, accept_vec in acceptance_table:
        padding_space = max_name_len - len(pkg_name) + 1
        table_lines.append("%s:%s %s" % (
            pkg_name, ' ' * padding_space, '    '.join(accept_vec)))

    return '\n'.join(table_lines)

def accepted_rpm_text(pending_report):
    """ @return string with newlines containing information about accepted
    RPMs in the pending report """
    
    accepted_rpms = pending_report.accepted_rpms()
    accept_lines = []
    
    if len(accepted_rpms) > 0:
        accept_lines.append("Accepted RPMS")
            
        for accepted_rpm in accepted_rpms:
            replaced = pending_report.get_replaced(accepted_rpm)
            if replaced == None:
                ver, bitness = rpm_util.sol_ver_and_bit(accepted_rpm)
                ver_bit_str = make_bit_ver(bitness, ver) 
                accept_lines.append("%s: New package %s passed version check"%
                                    (ver_bit_str, accepted_rpm))
            else:
                sol_ver, bitness, pkg_name, new_vers, old_vers = (
                    split_into_ver_bit_name_pending_existing(
                    accepted_rpm, replaced))
                    
                if (pending_report.report_repo() == 'stable'):
                    repo = 'retired'
                else:
                    repo = 'attic'
                
                accept_lines.append("%s %s: %s: %s replaced %s (to %s)" % (
                    sol_ver, bitness, pkg_name, new_vers, old_vers, repo))
    
    return '\n'.join(accept_lines)

def abandoned_rpm_text(pending_report):
    """ @return string containing text about rpms that have no
    corresponding SRPMS """
    abandoned_rpms = pending_report.abandoned_rpms()
    aband_lines = []
    if len(abandoned_rpms) > 0:
        aband_lines.append("REJECTED: RPMs with missing SRPMS")
        aband_lines.extend(abandoned_rpms)
        return '\n'.join(aband_lines)
    return ''

def old_rpm_text(pending_report):
    old_rpms = pending_report.old_rpms()
    old_lines = []
    
    if len(old_rpms) > 0:
        old_lines.append("Old RPMS")
            
        for old_rpm in old_rpms:
            newer_existing = pending_report.get_denied(old_rpm)
            sol_ver, bitness, pkg_name, pend_vers, exist_vers = (
                split_into_ver_bit_name_pending_existing(
                old_rpm, newer_existing))

            old_lines.append("%s %s %s: %s denied due to existing %s" % (
                sol_ver, bitness, pkg_name, pend_vers, exist_vers))

    return '\n'.join(old_lines)

def rpmlib_prob_text(pending_report):
    rpmlib_prob_rpms = pending_report.rpmlib_prob_rpms()
    prob_lines = []

    if len(rpmlib_prob_rpms) > 0:
        prob_lines.append("REJECTED: RPM lib dependency problems")

        for prob_rpm in rpmlib_prob_rpms:
            missing_dep = ' '.join(pending_report.get_lib_dep(prob_rpm))
            prob_lines.append('%s: %s' % (prob_rpm, missing_dep))

    return '\n'.join(prob_lines)

def make_subject(pub_result):
    """ @return a suitable subject for publish result, try to make it
    not too long """
    seen_pkgs = {}
    for scan in pub_result.pending_results():
        for pkg_name in scan.all_rpms():
            seen_pkgs[rpm_util.parse_rpmname(pkg_name)[0]] = 1

    compressed_pkgs = {} # try to compress breakout packages
    for k in seen_pkgs:
        compressed_pkgs[k.split('-')[0]] = 1

    ret = ' '.join(compressed_pkgs.keys())
    if len(ret) > 50:
        return 'Result: %d packages pending' % len(seen_pkgs)
    return "Result: " + ret

def create_publish_text(pub_result, publisher_emails):
    """ @return one big string containing human readable output of publish """

#   pickle.dump(pub_result, open("/servants/u1/jmkacz/pub_result.p", "w"))

    msg_lines = ["From: RPM Publish Checker <root@samwise.rutgers.edu>\r\nTo:%s\r\nSubject: %s\r\n" %
                 (', '.join(publisher_emails), make_subject(pub_result))]

    msg_lines.append(pending_outcome_summary(pub_result))
    msg_lines.append('')
    
    for pending_report in pub_result.pending_results():
        acceptance_table = pending_report.acceptance_table()

        table_text = accept_table_text(acceptance_table, pending_report.dist)
        msg_lines.append(table_text)
        
        msg_lines.append(accepted_rpm_text(pending_report))
        msg_lines.append(old_rpm_text(pending_report))
        msg_lines.append(abandoned_rpm_text(pending_report))
        msg_lines.append(rpmlib_prob_text(pending_report))

    msg_lines.append('N - new, Space - empty, M - missing SRPM, A - accepted, O - old, D - missing rpmlib dpendency')
    return '\n'.join(msg_lines)
    
def mail_publish_results(pub_result):
    """ Send mail summerizing what publish did to everyone who owns
    package involved in the publish
    @param pub_result PublishOutcome representing outcome of the publish"""
    import smtplib

    publish_users = pub_result.get_publishers()
    if len(publish_users) == 0: return # no one to mail to
    
    publisher_emails = publish_receivers(publish_users)
    print publisher_emails

    msg = create_publish_text(pub_result, publisher_emails)
    
    print msg
    server = smtplib.SMTP('mx.nbcs.rutgers.edu.')
    server.sendmail('oss@oss.rutgers.edu', publisher_emails, msg)
    server.quit()
