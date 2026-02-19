# UniFi Doorbell → Slack Snapshot Integration

Automatically posts a camera snapshot to Slack when someone rings your UniFi G4 Doorbell. No public URL required — the image is uploaded directly to Slack using a bot token.

## How It Works

```
Doorbell Ring
     ↓
Home Assistant detects ring (binary_sensor)
     ↓
HA takes snapshot from doorbell camera
     ↓
HA copies snapshot to Mac Mini via SCP
     ↓
HA triggers Python script on Mac Mini via SSH
     ↓
Python uploads image directly to Slack
```

## Infrastructure

| Component | Details |
|-----------|---------|
| Doorbell | UniFi G4 Doorbell with UniFi Protect |
| Hub | Mac Mini (always on, macOS) |
| Home Automation | Home Assistant OS in UTM VM |
| Remote Access | Tailscale + socat |
| Notification | Slack (bot token, direct file upload) |

---

## Prerequisites

- UniFi G4 Doorbell with UniFi Protect active
- Mac Mini running macOS (always on)
- Home Assistant OS running in UTM VM on the Mac Mini
- UniFi Protect integration configured in Home Assistant
- Python 3 with Miniconda (or any Python 3 install)
- Tailscale installed on Mac Mini
- Slack workspace with admin access

---

## Setup

### Step 1: Create the Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**
2. Name it (e.g. `Doorbell`) and select your workspace
3. Under **OAuth & Permissions** → **Bot Token Scopes**, add:
   - `chat:write`
   - `files:write`
4. Click **Install to Workspace** → **Allow**
5. Copy the **Bot User OAuth Token** (starts with `xoxb-`)
6. In Slack, open your target channel → **Integrations** → **Add an App** → add your bot
7. Right-click the channel → **View channel details** → scroll to bottom → copy the **Channel ID** (starts with `C`)

---

### Step 2: Set Up the Python Upload Script (Mac Mini)

**Install the Slack SDK:**

```bash
pip install slack_sdk
```

**Create the snapshot directory:**

```bash
mkdir -p ~/ha_snapshots
```

**Copy the upload script:**

```bash
cp scripts/slack_doorbell_uploader.py ~/slack_doorbell_uploader.py
```

**Edit the script with your values:**

```bash
vim ~/slack_doorbell_uploader.py
```

Update these variables:

```python
SLACK_BOT_TOKEN = "xoxb-your-token-here"
CHANNEL_ID = "C-your-channel-id-here"
FILE_PATH = "/Users/yourusername/ha_snapshots/doorbell_latest.jpg"
```

**Test the script:**

```bash
# Copy any .jpg as a test image
cp /path/to/any/test.jpg ~/ha_snapshots/doorbell_latest.jpg
python3 ~/slack_doorbell_uploader.py
```

You should see the image appear in your Slack channel.

---

### Step 3: Set Up SSH Key Auth (HA → Mac Mini)

Home Assistant needs passwordless SSH access to the Mac Mini to copy the snapshot and run the script.

**In the Home Assistant Terminal add-on** (Settings → Add-ons → Terminal & SSH → Open Web UI):

```bash
mkdir -p /config/ssh
ssh-keygen -t ed25519 -f /config/ssh/id_ed25519 -N ""
cat /config/ssh/id_ed25519.pub
```

Copy the full output (starts with `ssh-ed25519`, ends with `root@core-ssh`).

**On the Mac Mini:**

```bash
echo "ssh-ed25519 AAAA...your-full-key... root@core-ssh" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

**Verify it works (from the HA Terminal):**

```bash
ssh -i /config/ssh/id_ed25519 -o StrictHostKeyChecking=no yourusername@YOUR_MAC_MINI_IP echo "test"
```

You should see `test` with no password prompt.

---

### Step 4: Configure Home Assistant

**Edit `/homeassistant/configuration.yaml`** (via Settings → Add-ons → File Editor):

Add the `http` block if not present:

```yaml
http:
  use_x_forwarded_for: true
  trusted_proxies:
    - 127.0.0.1
    - 192.168.1.x  # Your HA VM's local IP
```

Add the `shell_command` block:

```yaml
shell_command:
  copy_snapshot_to_mac: >
    scp -i /config/ssh/id_ed25519 -o StrictHostKeyChecking=no
    /config/www/doorbell_latest.jpg
    yourusername@YOUR_MAC_MINI_IP:/Users/yourusername/ha_snapshots/doorbell_latest.jpg
  run_doorbell_uploader: >
    ssh -i /config/ssh/id_ed25519 -o StrictHostKeyChecking=no yourusername@YOUR_MAC_MINI_IP
    /Users/yourusername/miniconda3/bin/python3
    /Users/yourusername/slack_doorbell_uploader.py
```

> **Note:** Replace `YOUR_MAC_MINI_IP` with your Mac Mini's local IP and `yourusername` with your macOS username. To find the Mac Mini's IP: `ipconfig getifaddr en0`

**Do a full HA restart** (Settings → System → Restart → Restart Home Assistant).

> A full restart is required — Quick Reload will not pick up new `shell_command` entries.

---

### Step 5: Create the Doorbell Automation

1. Go to **Settings → Automations & Scenes → Create Automation → Create new automation**
2. Click the three-dot menu → **Edit in YAML**
3. Paste the contents of [`ha_automation.yaml`](ha_automation.yaml)
4. Click **Save**

> Verify your entity IDs match your setup. Go to **Settings → Devices & Services → UniFi Protect** to find the exact entity names for your doorbell sensor and camera.

---

### Step 6: Set Up Tailscale + socat (Remote Access)

This enables the Home Assistant app to connect when you're away from home WiFi.

**Install Tailscale:**

```bash
brew install tailscale
sudo brew services start tailscale
sudo tailscale up
```

Authenticate via the URL printed in the output.

**Install socat:**

```bash
brew install socat
```

**Make socat persistent:**

```bash
cp scripts/com.socat.ha-proxy.plist ~/Library/LaunchAgents/
```

Edit the plist and replace `192.168.1.x` with your HA VM's local IP:

```bash
vim ~/Library/LaunchAgents/com.socat.ha-proxy.plist
```

Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.socat.ha-proxy.plist
launchctl list | grep socat
```

**Configure Tailscale serve:**

```bash
tailscale serve --bg --http=80 http://127.0.0.1:8123
tailscale serve status
```

**Configure the HA iOS app:**

In the app go to **Settings → Companion App → Server** and set:
- **Internal URL:** `http://192.168.1.x:8123` (HA VM local IP)
- **External URL:** `http://your-mac-name.tail8939a2.ts.net` (from `tailscale serve status`)

---

## Testing

1. Ring the doorbell
2. In HA go to **Settings → Automations → Doorbell Snapshot to Slack → Traces**
3. Confirm each step completed without errors
4. Check your Slack channel for the notification with image

### Troubleshooting

| Error | Fix |
|-------|-----|
| `shell_command.run_doorbell_uploader not found` | Do a full HA restart, not Quick Reload |
| SSH exit code 255 | Verify the public key is in `~/.ssh/authorized_keys` and `-o StrictHostKeyChecking=no` is in both shell commands |
| Slack upload fails | Verify bot token is correct and bot has been added to the channel |
| No snapshot / blank image | Increase the `delay` after `camera.snapshot` (try 3–4 seconds) |

---

## Cleanup

Once working, remove legacy Slack integrations to avoid duplicate notifications:

1. In Slack → Manage Apps → remove any legacy Incoming Webhooks for the doorbell channel
2. In `configuration.yaml`, remove any unused `rest_command` entries for old webhook URLs
3. Do a Quick Reload after cleanup

---

## File Reference

```
doorbell-slack-integration/
├── README.md
├── ha_automation.yaml              # Home Assistant automation
├── scripts/
│   ├── slack_doorbell_uploader.py  # Python upload script (runs on Mac Mini)
│   └── com.socat.ha-proxy.plist   # launchd plist for persistent socat
```

---

## Values to Replace

| Placeholder | Replace With |
|-------------|-------------|
| `xoxb-your-token-here` | Slack bot token from api.slack.com/apps |
| `C-your-channel-id-here` | Slack channel ID (starts with C) |
| `YOUR_MAC_MINI_IP` | Mac Mini's local IP (`ipconfig getifaddr en0`) |
| `YOUR_HA_VM_IP` | HA VM's local IP (`utmctl ip-address <vm-uuid>`) |
| `yourusername` | Your macOS username |
| `/Users/yourusername/miniconda3/bin/python3` | Output of `which python3` on Mac Mini |
| `your-mac-name.tail8939a2.ts.net` | Your Tailscale hostname (`tailscale serve status`) |
