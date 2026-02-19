#!/usr/bin/env python3
"""
slack_doorbell_uploader.py
Uploads a doorbell snapshot to Slack when triggered by Home Assistant.
Called via SSH from the HA shell_command integration.
"""

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# === Configuration — update these values ===
SLACK_BOT_TOKEN = "xoxb-your-token-here"
CHANNEL_ID = "C-your-channel-id-here"
FILE_PATH = "/Users/yourusername/ha_snapshots/doorbell_latest.jpg"
COMMENT = "🔔 Someone's at the front door!"
TITLE = "Doorbell Snapshot"

# === Upload ===
client = WebClient(token=SLACK_BOT_TOKEN)

try:
    response = client.files_upload_v2(
        channel=CHANNEL_ID,
        initial_comment=COMMENT,
        file=FILE_PATH,
        title=TITLE,
    )
    print("✅ File uploaded successfully")
except SlackApiError as e:
    print(f"❌ Slack API error: {e.response['error']}")
    raise SystemExit(1)
except FileNotFoundError:
    print(f"❌ Snapshot file not found at: {FILE_PATH}")
    raise SystemExit(1)
except Exception as e:
    print(f"❌ General error: {str(e)}")
    raise SystemExit(1)
