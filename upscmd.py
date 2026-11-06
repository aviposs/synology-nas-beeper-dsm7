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

tn = telnetlib.Telnet("127.0.0.1", 3493)

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
  tn.write(b"LIST CMD ups\n")
  response = tn.read_until(b"END LIST CMD ups", timeout=2).decode("utf-8")
  print("\n>> AVAILABLE CMDS:")
  cmds = response.splitlines()[1:-1]
  for cmd in cmds:
    print(cmd.replace("CMD ups ", "- "))

tn.write(b"LOGOUT\n")
print(tn.read_all().decode("utf-8").rstrip("\n"))
tn.close()

if not command_ok:
    sys.exit(1)
