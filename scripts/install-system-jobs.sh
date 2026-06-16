#!/bin/bash
#
# Install systemd services for My Practice application
# Run this script with: sudo bash scripts/install-system-jobs.sh
#

set -e

INSTALL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL_USER="${SUDO_USER:-$(whoami)}"

echo "📦 Installing My Practice System Services"
echo "   Install directory : $INSTALL_DIR"
echo "   Running as user   : $INSTALL_USER"
echo ""
echo "This will install:"
echo "  - Backup timer (daily, randomized execution window)"
echo "  - Auto-start service (starts app during boot when network/docker are ready)"
echo "  - Calendar fetch timer (every 4h)"
echo ""

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run with sudo or as root:"
    echo "   sudo bash scripts/install-system-jobs.sh"
    exit 1
fi

# Substitute placeholders and copy service/timer files
echo "📋 Installing service files to /etc/systemd/system/..."
for f in scripts/my-practice-backup.service scripts/my-practice-backup.timer \
          scripts/my-practice-app.service \
          scripts/my-practice-fetch-calendar-events.service \
          scripts/my-practice-fetch-calendar-events.timer \
          scripts/my-practice-update-client-tags.service \
          scripts/my-practice-update-client-tags.timer; do
    sed \
        -e "s|/path/to/my-practice|${INSTALL_DIR}|g" \
        -e "s|YOUR_USERNAME|${INSTALL_USER}|g" \
        "$f" > "/etc/systemd/system/$(basename "$f")"
done

# Reload systemd
echo "🔄 Reloading systemd daemon..."
systemctl daemon-reload

# Enable and start backup timer
echo "⏰ Enabling and starting backup timer..."
systemctl enable my-practice-backup.timer
systemctl start my-practice-backup.timer

# Enable and start calendar fetch timer
echo "📅 Enabling and starting calendar fetch timer..."
systemctl enable my-practice-fetch-calendar-events.timer
systemctl start my-practice-fetch-calendar-events.timer

# Enable app auto-start service
echo "🚀 Enabling app auto-start service..."
systemctl enable my-practice-app.service

# Show status
echo ""
echo "✅ Services installed successfully!"
echo ""
echo "📊 Backup timer status:"
systemctl status my-practice-backup.timer --no-pager

echo ""
echo "📅 Next scheduled backup:"
systemctl list-timers my-practice-backup.timer --no-pager

echo ""
echo "🚀 App auto-start status:"
systemctl status my-practice-app.service --no-pager

echo ""
echo "💡 Useful commands:"
echo "   Backup timer:"
echo "     Check status:         systemctl status my-practice-backup.timer"
echo "     View logs:            journalctl -u my-practice-backup.service -f"
echo "     Run manually:         ./scripts/backup.sh"
echo "     Disable:              sudo systemctl disable my-practice-backup.timer"
echo ""
echo "   App auto-start:"
echo "     Check status:         systemctl status my-practice-app.service"
echo "     Start manually:       sudo systemctl start my-practice-app.service"
echo "     Stop:                 sudo systemctl stop my-practice-app.service"
echo "     Disable auto-start:   sudo systemctl disable my-practice-app.service"
