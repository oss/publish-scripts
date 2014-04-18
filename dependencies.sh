#!/bin/bash
# Tests whether or not all dependencies are satisfied.

# Required executables
for FILE in ; do
    if [ ! -f "$FILE" ]; then
        echo "Missing dependency: $FILE"
    fi
done

# Configuration files
for CONF in ; do
    if [ ! -f "$CONF" ]; then
        echo "Config file missing: $CONF"
    fi
done

# Directories
for DIR in ; do
    if [ ! -d "$DIR" ]; then
        echo "Directory missing: $DIR"
    fi
done
