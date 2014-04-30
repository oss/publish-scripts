#!/bin/bash
# publish-agent: Handles the publishing when enabled

# Source the configuration file
source /usr/local/etc/publishscripts.conf

# Location of directories. Change these as appropriate
VARRUNDIR="/var/run/publish/"
ENABLED="$VARRUNDIR/enabled"
INPROGRESS="$VARRUNDIR/inprogress"
PENDING="/rpm/PENDING.*/*.rpm"
CHECKED_PENDING="/rpm/CHECK_PEND.*/*.rpm"

# Command for running the SPEC file check
SPEC_CHECK="/usr/local/bin/publish/checkspecfiles.py"

# The command to run the actual publish scripts
PUBLISH_COMMAND="/usr/local/bin/publish.sh ok"
CHECKED_PUBLISH_COMMAND="/usr/local/bin/publish/publish.py"

# apt-cache, GNU date and yum's createrepo must be in the path
PATH="/usr/local/bin:/usr/local/gnu/bin:$PATH"

echo "$0 called."

# Check if the agent is allowed to run
if [[ -f $ENABLED && `cat $ENABLED` == "1" ]]; then
    echo "Publish agent enabled."

    # Check if an instance of the agent is already running
    if [[ -f $INPROGRESS && `cat $INPROGRESS` == "0" ]] ; then
        echo "Agent is not currently running; starting."
        echo "Checking SPEC files..."
        $SPEC_CHECK

	# Check if there are files in the pending directory
	if [[ -n `ls $PENDING` ]] ; then
            # Begin running, but wait 2 minutes and files will (hopefully)
            # make it into the pending directory
            echo "Files exist in the pending directory."
	    echo "Unchecked files exist; running publish in 2 minutes..."
	    echo "1" > $INPROGRESS
	    sleep 120
	    $PUBLISH_COMMAND
            rebuild-apt
	else
	    echo "No files in pending directory."
	fi

	if [[ -n `ls $CHECKED_PENDING` ]] ; then
            echo "Checked files exist; running check publish in 2 mintes..."
	    echo "1" > $INPROGRESS
	    sleep 120
	    $CHECKED_PUBLISH_COMMAND
	fi

	# If we started a publish, update the rpmfind database
	if [[ -f $INPROGRESS && `cat $INPROGRESS` == "1" ]]  ; then
	    export LD_LIBRARY_PATH="/usr/local/mysql/lib/mysql/"
	    export MySQL_USER=$publish_mysql_user
	    export MySQL_PASS=$publish_mysql_passwd
	    rpm2html /etc/rpm2html.config
	    cleanup-rpm2html
	    checkrelease.sh
	    echo "0" > $INPROGRESS

	    # Update the yum database
            echo "Updating yum databases..."
	    for yumrepo in stable testing unstable; do
		echo "Updating $yumrepo yum database..."
		/usr/local/bin/createrepo --update \
		    /rpm/repository/solaris/solaris9-sparc64/$yumrepo/RPMS.main/ \
		    --outputdir=/rpm/repository/yum/solaris9-sparc64/$yumrepo/ \
		    --baseurl=ftp://rpm.rutgers.edu/solaris/solaris9-sparc64/$yumrepo/RPMS.main/
	    done
	    echo "Yum database update complete."
	fi
    else
	echo "The publish agent is alredy running."
    fi
else
    echo "The publish agent has not been enabled."
fi
