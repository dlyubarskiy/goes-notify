#!/bin/bash

# Import env vars
printenv > /etc/environment 
# Setup a cron schedule
echo "* * * * * /app/run.sh >> /var/log/cron.log 2>&1
# This extra line makes it a valid cron" > scheduler.txt

crontab scheduler.txt
cron -f