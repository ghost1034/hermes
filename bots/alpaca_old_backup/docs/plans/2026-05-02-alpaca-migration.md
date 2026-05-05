# Alpaca Bot Migration Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Migrate the Alpaca daytrading bot from the legacy OpenClaw framework to Hermes, removing absolute paths and replacing OpenClaw gateway alerts with native Telegram alerts.

**Architecture:** We will copy the `bots/alpaca` directory from the cloned repository into `~/bots/alpaca`. Python and bash scripts will be refactored to use dynamic, relative pathing for their `.env` files. The alerting system will be updated to hit the Telegram API directly using `TELEGRAM_BOT_TOKEN` and `TELEGRAM_HOME_CHANNEL`.

**Tech Stack:** Python, Bash, Telegram API

---

### Task 1: Setup Target Directory

**Objective:** Copy the bot directory to its new permanent location.

**Files:**
- Create: `~/bots/alpaca/`

**Step 1: Copy files from clone**

```bash
mkdir -p ~/bots/alpaca
cp -r /tmp/ghost-workspace-ssh/bots/alpaca/* ~/bots/alpaca/
```

**Step 2: Verify copy**

Run: `ls ~/bots/alpaca/daytrader.py`
Expected: Exists

---

### Task 2: Refactor `.env` Loading in Python Scripts

**Objective:** Remove the hardcoded `/home/node/.openclaw/...` paths from all `check_*.py` files and `daytrader.py`.

**Files:**
- Modify: `~/bots/alpaca/*.py`

**Step 1: Apply multi-file patch**

```python
from hermes_tools import search_files, read_file, patch

# Find all python files containing the openclaw path
results = search_files(pattern='env_path = "/home/node/.openclaw/workspace/bots/alpaca/.env"', target="files", path="~/bots/alpaca", file_glob="*.py")

# Patch them to use pathlib
for file_path in results.get("matches", []):
    old_string = 'env_path = "/home/node/.openclaw/workspace/bots/alpaca/.env"'
    new_string = 'import os\nfrom pathlib import Path\nenv_path = Path(__file__).parent / ".env"'
    patch(file_path, old_string, new_string)
```

**Step 2: Verify refactoring**

Run: `grep -r "openclaw" ~/bots/alpaca/*.py`
Expected: No matches found

---

### Task 3: Refactor `send_telegram_alert` in `daytrader.py`

**Objective:** Update the `daytrader.py` alert function to use native Telegram API instead of OpenClaw gateway.

**Files:**
- Modify: `~/bots/alpaca/daytrader.py`

**Step 1: Replace function**

```python
from hermes_tools import read_file, patch

# You'll need to locate the exact send_telegram_alert function block and replace it
# Use a regex or large string replace to swap it to this:

"""
def send_telegram_alert(message):
    try:
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_HOME_CHANNEL")
        if not bot_token or not chat_id:
            logger.error("TELEGRAM_BOT_TOKEN or TELEGRAM_HOME_CHANNEL is not set; alert not sent.")
            return
            
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": f"🚨 Alpaca Bot Alert:\n\n{message}"
        }
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url, 
            data=data, 
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status != 200:
                logger.error(f"Failed to send Telegram alert. Status: {response.status}")
    except Exception as e:
        logger.error(f"Error sending Telegram alert: {e}")
"""
```

*(Note: In the subagent step, read `daytrader.py`, extract the old `send_telegram_alert` using `re`, and overwrite it.)*

**Step 2: Verify modification**

Run: `grep "api.telegram.org" ~/bots/alpaca/daytrader.py`
Expected: Match found.

---

### Task 4: Refactor `start_bot.sh`

**Objective:** Update the crash alert curl command in `start_bot.sh` to use Telegram API.

**Files:**
- Modify: `~/bots/alpaca/start_bot.sh`

**Step 1: Replace OpenClaw curl block**

Find the block containing `if [ -n "$OPENCLAW_TOKEN" ]; then ... curl ...` and replace it with:

```bash
  if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_HOME_CHANNEL" ]; then
    curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      -H "Content-Type: application/json" \
      -d "{\"chat_id\":\"${TELEGRAM_HOME_CHANNEL}\",\"text\":\"🚨 *Alpaca Bash Alert* 🚨\nThe daytrader bot crashed with exit code $EXIT_CODE.\"}" > /dev/null
  else
    echo "Telegram tokens are not set; crash alert not sent."
  fi
```

**Step 2: Verify script syntax**

Run: `bash -n ~/bots/alpaca/start_bot.sh`
Expected: No output (success).

---

### Task 5: Refactor `run_daytrader.sh`

**Objective:** Remove absolute paths and OpenClaw variable assignments.

**Files:**
- Modify: `~/bots/alpaca/run_daytrader.sh`

**Step 1: Rewrite script**

Replace the entire contents with:

```bash
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
set -a
[ -f "$SCRIPT_DIR/.env" ] && source "$SCRIPT_DIR/.env"
set +a

python3 "$SCRIPT_DIR/daytrader.py" >> "$SCRIPT_DIR/daytrader.log" 2>&1
```

**Step 2: Verify script syntax**

Run: `bash -n ~/bots/alpaca/run_daytrader.sh`
Expected: No output.

---

### Task 6: Commit Migration

**Objective:** Initialize a git repo in the new location and commit the clean state.

**Step 1: Initialize and commit**

```bash
cd ~/bots/alpaca
git init
git add .
git commit -m "chore: migrate from OpenClaw to Hermes framework"
```
