#!/bin/bash
# Year Plan Reminder Cron Job
# This script sends reminder emails to users based on their preferences
# 
# To set up as a cron job, add this line to your crontab:
# 0 9 * * * /Users/jidai/workspace1/yearplan/send_reminders.sh
# (This runs daily at 9 AM)

# Change to the project directory
cd /Users/jidai/workspace1/yearplan

# Check if the server is running
if ! curl -s http://127.0.0.1:8080 > /dev/null; then
    echo "$(date): Year Plan server is not running" >> /tmp/yearplan_cron.log
    exit 1
fi

# Send the reminder processing request
response=$(curl -s -X POST http://127.0.0.1:8080/api/process-reminders)

# Log the result
echo "$(date): Reminder processing result: $response" >> /tmp/yearplan_cron.log

# Check if there were any errors
if echo "$response" | grep -q "error"; then
    echo "$(date): ERROR in reminder processing: $response" >> /tmp/yearplan_cron.log
    exit 1
fi

echo "$(date): Reminders processed successfully" >> /tmp/yearplan_cron.log