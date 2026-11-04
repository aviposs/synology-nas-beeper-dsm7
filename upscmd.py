#!/usr/bin/env python2
import sys
import telnetlib

user = "<upsd_username>"
pwd = "<upsd_pwd>"

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
