#!/bin/bash
# Re-creates the upsd user entry that DSM updates remove / reset
# (followed by a ups-usb restart).
# Keep this repository on a data volume (e.g. /volume1/scripts/...) and run this
# script as root from a boot-up triggered task. Nothing is changed if everything
# is already in place. The scripts run directly from this repository.
#
# Usage: restore.sh [enable|disable|curtime]
#   The optional argument is passed to the adjacent ups_beeper_control.sh.
set -e

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF_FILE="$SRC_DIR/ups_beeper.conf"

if [ "$(id -u)" -ne 0 ]
then
	echo "This script must be run as root."
	exit 1
fi

if [ ! -f "$CONF_FILE" ]
then
	echo "Missing $CONF_FILE (copy ups_beeper.conf.example and edit it)."
	exit 1
fi
# shellcheck source=/dev/null
. "$CONF_FILE"

if [ -z "$UPSD_USER" ] || [ -z "$UPSD_PWD" ] || [[ "$UPSD_USER" == "<"* ]] || [[ "$UPSD_PWD" == "<"* ]]
then
	echo "UPSD_USER / UPSD_PWD are not configured in $CONF_FILE."
	exit 1
fi
case "$UPSD_USER$UPSD_PWD" in
	*[[:space:]]*|*\"*|*\'*|*\\*|*\[*|*\]*)
		echo "UPSD_USER / UPSD_PWD must not contain whitespace, quotes, backslashes or brackets."
		exit 1
		;;
esac

dsm_major=$(awk -F '"' '/^majorversion=/ { print $2 }' /etc.defaults/VERSION)
if ! [[ "$dsm_major" =~ ^[0-9]+$ ]]
then
	echo "Unable to determine DSM version."
	exit 1
fi

# 1. upsd user
users_changed=0
found_users_file=0
for users_file in /usr/syno/etc/ups/upsd.users /etc/ups/upsd.users
do
	[ -f "$users_file" ] || continue
	[ -L "$users_file" ] && continue
	found_users_file=1
	if UPSD_USER="$UPSD_USER" awk '
		{
			line = $0
			sub(/^[[:space:]]*/, "", line)
			sub(/[[:space:]]*$/, "", line)
			if (line == "[" ENVIRON["UPSD_USER"] "]") found = 1
		}
		END { exit !found }
	' "$users_file"
	then
		echo "upsd user '$UPSD_USER' already present in $users_file."
		continue
	fi
	cp -p "$users_file" "$users_file.bak"
	[ -n "$(tail -c 1 "$users_file")" ] && echo >> "$users_file"
	cat >> "$users_file" <<EOF
	[$UPSD_USER]
		password = $UPSD_PWD
		actions = SET
		instcmds = beeper.enable beeper.disable beeper.toggle ups.beeper.status
EOF
	echo "Added upsd user '$UPSD_USER' to $users_file (backup: $users_file.bak)."
	users_changed=1
done
if [ "$found_users_file" -eq 0 ]
then
	echo "upsd.users not found (is a USB UPS configured?)."
	exit 1
fi

if [ "$users_changed" -eq 1 ]
then
	echo "Restarting ups-usb service..."
	if [ "$dsm_major" -ge 7 ]
	then
		synosystemctl restart ups-usb
	else
		synoservice --restart ups-usb
	fi
fi

# 2. Optionally apply the beeper state (waits for upsd to be ready, e.g. at boot)
if [ -n "$1" ]
then
	for _ in $(seq 1 30)
	do
		upsc ups ups.beeper.status >/dev/null 2>&1 && break
		sleep 2
	done
	bash "$SRC_DIR/ups_beeper_control.sh" "$1"
fi
