#!/bin/bash
# ═══════════════════════════════════════════════════════════
#  3100 Pearl Monitor — Quick Setup
# ═══════════════════════════════════════════════════════════
#
#  Run:  chmod +x setup.sh && ./setup.sh
#

set -e

echo ""
echo "🏠 3100 Pearl Availability Monitor — Setup"
echo "═══════════════════════════════════════════"
echo ""

# ── Python deps ──
echo "📦 Installing Python dependencies..."
pip3 install requests beautifulsoup4 playwright --break-system-packages -q 2>/dev/null || \
pip3 install requests beautifulsoup4 playwright -q

echo "🌐 Installing Chromium for Playwright..."
python3 -m playwright install chromium

echo ""
echo "✅ Dependencies installed!"
echo ""

# ── ntfy setup ──
echo "═══════════════════════════════════════════"
echo "📱 NOTIFICATION SETUP (ntfy.sh — recommended)"
echo "═══════════════════════════════════════════"
echo ""
echo "ntfy.sh is FREE — no account needed."
echo ""
echo "  1. Install the ntfy app on your phone:"
echo "     iOS:     https://apps.apple.com/app/ntfy/id1625396347"
echo "     Android: https://play.google.com/store/apps/details?id=io.heckel.ntfy"
echo ""
echo "  2. Open the app → tap '+' → subscribe to topic:"
echo "     ben-3100pearl"
echo "     (or change ntfy_topic in the script to your own secret name)"
echo ""
echo "  3. That's it. You'll get push notifications."
echo ""

# ── Test ──
echo "═══════════════════════════════════════════"
echo "🧪 Test notification?"
echo "═══════════════════════════════════════════"
read -p "Send a test push notification? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python3 3100pearl_monitor_v2.py --test-notify
fi

echo ""
echo "═══════════════════════════════════════════"
echo "🚀 USAGE"
echo "═══════════════════════════════════════════"
echo ""
echo "  # Single scan"
echo "  python3 3100pearl_monitor_v2.py"
echo ""
echo "  # Watch mode (polls every 30 min)"
echo "  python3 3100pearl_monitor_v2.py --watch"
echo ""
echo "  # Custom interval (every 15 min)"
echo "  python3 3100pearl_monitor_v2.py --watch 15"
echo ""
echo "  # Test notifications"
echo "  python3 3100pearl_monitor_v2.py --test-notify"
echo ""

# ── Cron setup ──
echo "═══════════════════════════════════════════"
echo "⏰ OPTIONAL: Auto-run with cron"
echo "═══════════════════════════════════════════"
echo ""
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "  To run every 30 min automatically, add this to crontab:"
echo "    crontab -e"
echo ""
echo "  */30 * * * * cd ${SCRIPT_DIR} && /usr/bin/python3 3100pearl_monitor_v2.py >> ~/.3100pearl/cron.log 2>&1"
echo ""

# ── launchd for macOS ──
if [[ "$(uname)" == "Darwin" ]]; then
    echo "═══════════════════════════════════════════"
    echo "🍎 macOS: launchd (alternative to cron)"
    echo "═══════════════════════════════════════════"
    echo ""

    PLIST_PATH="$HOME/Library/LaunchAgents/com.ben.3100pearl.plist"
    cat > /tmp/com.ben.3100pearl.plist << PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ben.3100pearl</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>${SCRIPT_DIR}/3100pearl_monitor_v2.py</string>
    </array>
    <key>StartInterval</key>
    <integer>1800</integer>
    <key>StandardOutPath</key>
    <string>${HOME}/.3100pearl/launchd.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/.3100pearl/launchd_err.log</string>
    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>
</dict>
</plist>
PLISTEOF

    echo "  A launchd plist has been generated at /tmp/com.ben.3100pearl.plist"
    echo ""
    echo "  To install it (runs every 30 min, survives reboots):"
    echo "    cp /tmp/com.ben.3100pearl.plist ~/Library/LaunchAgents/"
    echo "    launchctl load ~/Library/LaunchAgents/com.ben.3100pearl.plist"
    echo ""
    echo "  To stop:"
    echo "    launchctl unload ~/Library/LaunchAgents/com.ben.3100pearl.plist"
    echo ""
fi

echo "═══════════════════════════════════════════"
echo "✅ Setup complete! Run your first scan:"
echo "   python3 3100pearl_monitor_v2.py"
echo "═══════════════════════════════════════════"
echo ""
