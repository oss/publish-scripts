#!/bin/bash
# Tests whether or not all dependencies are satisfied.

# Required executables
while read -r FILE; do
    if ! which "$FILE" > /dev/null 2>&1 ; then
        echo "Missing executable: $FILE"
    fi
done < "$1"

# Configuration files
while read -r CONF; do
    if [ ! -f "$CONF" ]; then
        echo "Config file missing: $CONF"
    fi
done < "$2"

# Directories
while read -r DIR; do
    if [ ! -d "$DIR" ]; then
        echo "Directory missing: $DIR"
    fi
done < "$3"
