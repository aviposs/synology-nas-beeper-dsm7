#!/usr/bin/env python2
import os
import sys
import telnetlib

user = os.environ.get("UPSD_USER", "")
pwd = os.environ.get("UPSD_PWD", "")

if not user or not pwd or user.startswith("<") or pwd.startswith("<"):
    print("UPSD_USER / UPSD_PWD are not configured (use ups_beeper_control.sh with ups_beeper.conf).")
    sys.exit(1)
if any(char.isspace() or char in "\"'\\[]" for char in user + pwd):
    print("UPSD_USER / UPSD_PWD must not contain whitespace, quotes, backslashes or brackets.")
    sys.exit(1)

if len(sys.argv) == 2:
    cmd = sys.argv[1]
else:
    print("the ups command to issue is missing.")
    print("example: upscmd.py beeper.enable")
    exit(1)


def list_commands(connection):
    connection.write(b"LIST CMD ups\n")
    response = connection.read_until(b"END LIST CMD ups\n", timeout=2).decode("utf-8")
    lines = response.strip().splitlines()
    if not lines or lines[0] != "BEGIN LIST CMD ups" or lines[-1] != "END LIST CMD ups":
        raise ValueError("Unable to list UPS commands: {0}".format(response.strip()))
    if any(not line.startswith("CMD ups ") for line in lines[1:-1]):
        raise ValueError("Invalid UPS command list: {0}".format(response.strip()))
    return [line[len("CMD ups "):] for line in lines[1:-1]]


tn = telnetlib.Telnet("127.0.0.1", 3493)

if cmd == "--list-commands":
    try:
        for available_cmd in list_commands(tn):
            print(available_cmd)
    except ValueError as error:
        sys.stderr.write(str(error) + "\n")
        sys.exit(1)
    finally:
        tn.close()
    sys.exit(0)

tn.write("USERNAME {0}\n".format(user).encode("utf-8"))
response = tn.read_until(b"OK", timeout=2).decode("utf-8")
print("USERNAME: {0}".format(response.strip()))

tn.write("PASSWORD {0}\n".format(pwd).encode("utf-8"))
response = tn.read_until(b"OK", timeout=2).decode("utf-8")
print("PASSWORD: {0}".format(response.strip()))

tn.write("INSTCMD ups {0}\n".format(cmd).encode("utf-8"))
response = tn.read_until(b"OK", timeout=2).decode("utf-8")
print("INSTCMD ups {0}: {1}".format(cmd, response.strip()))

command_ok = response.strip() == "OK"
if not command_ok:
    try:
        cmds = list_commands(tn)
        print("\n>> AVAILABLE CMDS:")
        for available_cmd in cmds:
            print("- " + available_cmd)
    except ValueError as error:
        sys.stderr.write(str(error) + "\n")

tn.write(b"LOGOUT\n")
print(tn.read_all().decode("utf-8").rstrip("\n"))
tn.close()

if not command_ok:
    sys.exit(1)
