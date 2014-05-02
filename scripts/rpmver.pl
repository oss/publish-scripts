#!/usr/local/bin/perl -w

use Sort::Versions;

# results are:
#  a < b  = -1
#  a == b =  0
#  a > b  =  1
#ver
$verresults = versioncmp($ARGV[0],$ARGV[2]);

#   printf $verresults;

#rev

if ($verresults == "0") {
    $finalresults = versioncmp($ARGV[1],$ARGV[3]);
} else {
    $finalresults = $verresults;
}

if ($finalresults == "-1") {
    print "older";
} elsif ($finalresults == "0") {
    print "same";
} elsif ($finalresults == "1"){
    print "newer";
} else {
    print "duh";
}



