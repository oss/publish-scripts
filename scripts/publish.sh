#!/bin/bash
# publish.sh: Forced package publishing. Must be run as root.

export PATH="/usr/local/bin:$PATH"
export TEMPDIR="/tmp/"

chmod 644 /rpm/PENDING.*/*

if [[ "$1" != "ok" ]]; then
    echo You SHOULD NOT call this script directly.
    exit 1
fi

TIMEDATE=`date`

rm -rf /rpm/publish.logs/*

for user in `ls -l /rpm/PENDING*/* | cut -d' ' -f5 | uniq`; do
    rm -f /rpm/publish.logs/$user
    touch /rpm/publish.logs/$user

    echo "Subject: RPM: Your newly published packages" >> /rpm/publish.logs/$user
    echo "RPMs in !!!NOT CHECKED!!! PENDING were published $TIMEDATE" >> /rpm/publish.logs/$user
    echo >> /rpm/publish.logs/$user
    echo "This e-mail is from the FORCE PUBLISH script. The repository may be" >> /rpm/publish.logs/$user
    echo "broken following the use of this script. If there" >> /rpm/publish.logs/$user
    echo "are no errors below, the packages are now available" >> /rpm/publish.logs/$user
    echo "from the repository." >> /rpm/publish.logs/$user
    echo >> /rpm/publish.logs/$user
    echo >> /rpm/publish.logs/$user
done

mail_logs () {

if [ -e /rpm/publish.logs/root ]; then
 echo "Note: This is a log for packages owned by root." >> /rpm/publish.logs/root
 mv /rpm/publish.logs/root /rpm/publish.logs/oss
fi

# this used to be a for loop to go to each user, but now this is force publish
# so we don't care so much

cat /rpm/publish.logs/* | /usr/lib/sendmail -F "RPM Publish Script" oss-rpm@oss.rutgers.edu
}


echo_owner () {
    echo echo-ing to $OWNER: $*
    echo $* >> /rpm/publish.logs/$OWNER
}

verify_newer () {

# Returns 0 if $1 < $2, 1 if $1 > $2, and 2 if they are equal
if [[ "$1" = "$2" ]]; then
    return 2
fi

echo "$1
$2" | sort -rc --

if [ $? -eq 0 ]; then
    return 1
else
    return 0
fi
}


publish () {

EXISTING_NEWER=0
PACKAGENAME=`rpm -qp --queryformat="%{NAME}" $NEWPACKAGE`
NEWPACKAGEDESC=`rpm -qp $NEWPACKAGE`
CLEAN_UP_OLDER_FILES=`ls $REPLACES_OLD`
VERIFY_NEWER_FILES=`ls $MUST_BE_NEWER_THAN`
ENEW=0

if [ -z "$CLEAN_UP_OLDER_FILES $VERIFY_NEWER_FILES" ]; then
    echo_owner "-- No existing versions, moving into repository"
    mv $NEWPACKAGE $PUBLISH_TO/
    chmod 644 $PUBLISH_TO/$PACKAGENAME*.rpm

else 
 for j in $CLEAN_UP_OLDER_FILES; do

    OLDPACKAGENAME=`rpm -qp --queryformat="%{NAME}" $j`
    OLDPACKAGEDESC=`rpm -qp $j`

    if [[ "$PACKAGENAME" = "$OLDPACKAGENAME" ]]; then

	EXISTING_VERSION=`rpm -qp --queryformat="%{VERSION}" $j`
	NEW_VERSION=`rpm -qp --queryformat="%{VERSION}" $NEWPACKAGE`
	EXISTING_RELEASE=`rpm -qp --queryformat="%{RELEASE}" $j`
	NEW_RELEASE=`rpm -qp --queryformat="%{RELEASE}" $NEWPACKAGE`

	VERCMP=`perl /usr/local/bin/publish/rpmver.pl $NEW_VERSION $NEW_RELEASE $EXISTING_VERSION 
$EXISTING_RELEASE`
	
	if [ $VERCMP == "newer" ]; then
	    echo_owner "     -   Cleaning up OLD $OLDPACKAGEDESC: moved to attic"
	    mv $j /rpm/repository/solaris/.attic/
	elif [ $VERCMP == "same" ]; then
	    echo_owner "     -   Cleaning up EXISTING $OLDPACKAGEDESC: moved to attic"
	    mv $j /rpm/repository/solaris/.attic/
	elif [ $VERCMP == "older" ]; then
	    #ENEW=1
	    echo_owner "     -   Newer version $OLDPACKAGEDESC in repository"
	    echo inner existing newer: $ENEW
	else
	    echo "I'm confused"
	fi
    fi
 done
 for j in $VERIFY_NEWER_FILES; do

    OLDPACKAGENAME=`rpm -qp --queryformat="%{NAME}" $j`
    OLDPACKAGEDESC=`rpm -qp $j`

    if [[ "$PACKAGENAME" = "$OLDPACKAGENAME" ]]; then

	EXISTING_VERSION=`rpm -qp --queryformat="%{VERSION}" $j`
	NEW_VERSION=`rpm -qp --queryformat="%{VERSION}" $NEWPACKAGE`
	EXISTING_RELEASE=`rpm -qp --queryformat="%{RELEASE}" $j`
	NEW_RELEASE=`rpm -qp --queryformat="%{RELEASE}" $NEWPACKAGE`

	VERCMP=`perl /usr/local/bin/publish/rpmver.pl $NEW_VERSION $NEW_RELEASE $EXISTING_VERSION 
$EXISTING_RELEASE`
	
	if [ $VERCMP == "older" ]; then
	    ENEW=1
	    echo_owner "     -   Newer version $OLDPACKAGEDESC in repository"
	    echo inner existing newer: $ENEW
	fi
    fi
 done


 #if this one isn't newest, move to error, else, move into repository
 if [ "$ENEW" -eq "1" ]; then
     echo_owner "   -   NOT PUBLISHING ${NEWPACKAGEDESC} DUE TO NEWER VERSION(S) IN"
     echo_owner "   -   THE REPOSITORY: moving to /rpm/pending.error/"
     mv $NEWPACKAGE /rpm/pending.error/
else
     echo_owner "   -   Publishing NEW $NEWPACKAGEDESC to repository"
     mv $NEWPACKAGE $PUBLISH_TO
     chmod 644 $PUBLISH_TO/$PACKAGENAME*.rpm
 fi

	echo_owner

fi
}


main () {

OSLIST="7 8 9"
ARCHLIST="sparc64 sparc"
RELEASELIST="uranium unstable testing stable"

lsof | grep rpm > $TEMPDIR/openfiles
find /rpm/PENDING*/*.rpm > $TEMPDIR/pendingfiles
for RELEASE in $RELEASELIST; do
    for ARCH in $ARCHLIST; do
	for OS in $OSLIST; do
	    echo
	    echo "-- Processing $OS $ARCH $RELEASE --"
	    for NEWPACKAGE in `cat $TEMPDIR/pendingfiles | grep $RELEASE | grep solaris2.$OS-$ARCH`; do
		OWNER=`ls -l $NEWPACKAGE | cut -d' ' -f5`
		echo_owner "-- `basename $NEWPACKAGE` : $RELEASE --"
		grep $NEWPACKAGE $TEMPDIR/openfiles > /dev/null
		if [ $? -eq 0 ]; then
		    echo_owner "file in use, skipping"
		else
		    echo_owner "file not in use, processing further..."
		    /usr/local/bin/rpmverify -p --nodeps --noscript --nofiles $NEWPACKAGE
		    if [ $? -eq 1 ]; then
			echo_owner ERROR: FILE FAILS VERIFY CHECK!! MOVING TO ERROR!!
			mv $NEWPACKAGE /rpm/pending.error
		    else
			echo_owner "file passes verify, publishing..."
			PACKAGENAME=`rpm -qp --queryformat="%{NAME}" $NEWPACKAGE`
			REPLACES_OLD="/rpm/repository/solaris/solaris$OS-$ARCH/$RELEASE/RPMS.main/$PACKAGENAME*"
			MUST_BE_NEWER_THAN="/rpm/repository/solaris/solaris$OS-$ARCH/$RELEASE/RPMS.main/$PACKAGENAME*"
			PUBLISH_TO="/rpm/repository/solaris/solaris$OS-$ARCH/$RELEASE/RPMS.main/"
			publish
		    fi #rpmverify
		fi #grep return
	    done
	done
    done
done

#move non-rpm and non-spec files to SOURCES
for i in `find /rpm/PENDING.* \( ! -name '*.rpm' ! -name '*.spec' ! -type d \)`; do
    mv $i /rpm/repository/solaris/SOURCES/
done

#move source rpms to SRPMS
for i in `find /rpm/PENDING.* -name '*.src.rpm'`; do
    mv $i /rpm/repository/solaris/SRPMS/
done

#remove specs
rm `find /rpm/PENDING.* -name '*.spec'`

mail_logs

}

# Run the main function
main
