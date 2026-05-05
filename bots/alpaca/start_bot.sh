#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

if [ -f "$ENV_FILE" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    line=$(echo "$line" | tr -d '\r')
    case "$line" in
      ''|'#'*) continue ;;
    esac
    if [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
      export "$line"
    else
      echo "Ignoring unsafe .env line: $line"
    fi
  done < "$ENV_FILE"
fi

# Run the bot
cd "$SCRIPT_DIR" || exit 1
python3 "$SCRIPT_DIR/main.py" >> "$SCRIPT_DIR/daytrader.log" 2>&1
EXIT_CODE=$?

# If the bot exits with a non-zero code, send an alert
if [ $EXIT_CODE -ne 0 ] && [ $EXIT_CODE -ne 99 ]; then
  echo "Bot crashed with exit code $EXIT_CODE"
  if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_HOME_CHANNEL" ]; then
    curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      -H "Content-Type: application/json" \
      -d "{\"chat_id\":\"${TELEGRAM_HOME_CHANNEL}\",\"text\":\"🚨 *Alpaca Bash Alert* 🚨\nThe daytrader bot crashed with exit code $EXIT_CODE.\",\"parse_mode\":\"Markdown\"}" > /dev/null
  else
    echo "Telegram tokens are not set; crash alert not sent."
  fi
fi

exit $EXIT_CODE
