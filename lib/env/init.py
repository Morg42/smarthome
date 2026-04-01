# lib/env/init.py

import psutil
import socket

# version of SmartHomeNG and start time
sh.env.core.version(sh.version, logic.lname)
sh.env.core.start(shtime.now(), logic.lname)

# hostname
hostname=socket.gethostname()
sh.env.system.name(hostname, logic.lname)

# operating system start
sh.env.system.start(psutil.boot_time(), logic.lname)
