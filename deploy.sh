#!/bin/bash

# Define variables
SERVICE_NAME="pricetracker-job"
LOCATION=$LOCATION

# Create the systemd service unit file
cat <<EOF | sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null
[Unit]
Description=Pricetracker Job

[Service]
ExecStart=/usr/bin/docker run --name=pricetracker --env-file $LOCATION/.env --rm pricetracker:0.0.1
EOF

# Create the systemd timer unit file
cat <<EOF | sudo tee /etc/systemd/system/$SERVICE_NAME.timer > /dev/null
[Unit]
Description=Pricetracker Job Timer

[Timer]
OnCalendar=Mon-Sun 08:00:00
Unit=$SERVICE_NAME.service

[Install]
WantedBy=timers.target
EOF

# Reload systemd manager
sudo systemctl daemon-reload

# Enable and start the timer
sudo systemctl enable --now $SERVICE_NAME.timer

# Display status and logs
sudo systemctl status $SERVICE_NAME.timer
journalctl -u $SERVICE_NAME.timer
