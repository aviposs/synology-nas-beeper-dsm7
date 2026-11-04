#!/bin/bash -e
# https://moshib.in/2019/02/08/disable-ups-beeper-synology.html
if [ "$1" == "curtime" ]
then
	echo "Using current time to set UPS beeper status"
	H=$(date "+%k")
	if (( "$H" >= 9 )) 
	then
		goal="enable"
	else
		goal="disable"
	fi
else
	goal=$1
fi

if [ "$goal" == "enable" ] || [ "$goal" == "disable" ]
then
	dsm_major=$(awk -F '"' '/^majorversion=/ { print $2 }' /etc.defaults/VERSION)
	if ! [[ "$dsm_major" =~ ^[0-9]+$ ]]
	then
		echo "Unable to determine DSM version."
		exit 1
	fi

	python_cmd="python"
	beeper_cmd="beeper.${goal}"
	if [ "$dsm_major" -ge 7 ]
	then
		python_cmd="python3"
		current_status=$(upsc ups ups.beeper.status) || exit 1
		if [ "$current_status" == "${goal}d" ]
		then
			echo "Beeper already ${goal}d."
			exit 0
		fi
		if [ "$current_status" != "enabled" ] && [ "$current_status" != "disabled" ]
		then
			echo "Unknown / unsupported beeper status: $current_status"
			exit 1
		fi
		beeper_cmd="beeper.toggle"
	fi

	echo "$goal beeper..."
	"$python_cmd" /root/upscmd.py "$beeper_cmd" || exit 1
	echo "Waiting 5 seconds for UPS to update state..."
	sleep 5
	if [[ "$(upsc ups ups.beeper.status)" == "${goal}d" ]]
	then
		echo "Beeper ${goal}d."
	else
		echo "Unable to $goal beeper. Status = $(upsc ups ups.beeper.status)."
		exit 1
	fi
else
	echo "Unknown / unsupported argument: $1"
	exit 1
fi

