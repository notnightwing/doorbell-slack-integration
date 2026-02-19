# UniFi Doorbell → Slack Snapshot Integration

Automatically posts a camera snapshot to Slack when someone rings your UniFi G4 Doorbell. No public URL required — the image is uploaded directly to Slack using a bot token, keeping everything on your local network.

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
| Notification | Slack (bot token, direct file upload) |

---

## Prerequisites

- UniFi G4 Doorbell with UniFi Protect active
- Mac Mini running macOS (always on)
- Home Assistant OS running in UTM VM on the Mac Mini
- UniFi Protect integration configured in Home Assistant
- Python 3 (Miniconda or any Python 3 install)
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

Update these three variables:

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

Home Assistant needs passwordless SSH access to the Mac Mini to copy the snapshot and run the Python script.

**In the Home Assistant Terminal add-on** (Settings → Add-ons → Terminal & SSH → Open Web UI):

```bash
mkdir -p /config/ssh
ssh-keygen -t ed25519 -f /config/ssh/id_ed25519 -N ""
cat /config/ssh/id_ed25519.pub
```

Copy the full output — it starts with `ssh-ed25519` and ends with `root@core-ssh`.

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

**Edit `/homeassistant/configuration.yaml`** via Settings → Add-ons → File Editor.

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

> Replace `YOUR_MAC_MINI_IP` with your Mac Mini's local IP (`ipconfig getifaddr en0`) and `yourusername` with your macOS username.

**Do a full HA restart** — Settings → System → Restart → Restart Home Assistant.

> A full restart is required. Quick Reload will not pick up new `shell_command` entries.

---

### Step 5: Create the Doorbell Automation

1. Go to **Settings → Automations & Scenes → Create Automation → Create new automation**
2. Click the three-dot menu → **Edit in YAML**
3. Paste the contents of [`ha_automation.yaml`](ha_automation.yaml)
4. Click **Save**

> Verify your entity IDs match your setup. Go to **Settings → Devices & Services → UniFi Protect** to confirm the exact names for your doorbell sensor and camera entities.

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
| SSH exit code 255 | Verify the public key is in `~/.ssh/authorized_keys` on the Mac Mini and that `-o StrictHostKeyChecking=no` is in both shell commands |
| Slack upload fails | Verify bot token is correct and the bot has been added to the channel |
| No snapshot / blank image | Increase the `delay` after `camera.snapshot` (try 3–4 seconds) |

---

## Cleanup

Once working, remove any legacy Slack integrations to avoid duplicate notifications:

1. In Slack → Manage Apps → remove any legacy Incoming Webhooks configured for the doorbell channel
2. In `configuration.yaml`, remove any unused `rest_command` entries pointing to old webhook URLs
3. Do a Quick Reload after cleanup

---

## File Reference

```
doorbell-slack-integration/
├── README.md                           # This file
├── ha_automation.yaml                  # Paste directly into HA automation editor
├── ha_configuration_snippets.yaml      # Snippets to add to configuration.yaml
└── scripts/
    └── slack_doorbell_uploader.py      # Python upload script (runs on Mac Mini)
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
