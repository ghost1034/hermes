#!/bin/bash
# scripts/alpaca.sh
# Wrapper for Alpaca v2 Paper Trading API

API_URL="https://paper-api.alpaca.markets"
API_KEY="${APCA_API_KEY_ID}"
API_SECRET="${APCA_API_SECRET_KEY}"

if [ -z "$API_KEY" ] || [ -z "$API_SECRET" ]; then
  echo "Error: APCA_API_KEY_ID and APCA_API_SECRET_KEY environment variables must be set."
  exit 1
fi

HEADERS=(
  "-H" "APCA-API-KEY-ID: $API_KEY"
  "-H" "APCA-API-SECRET-KEY: $API_SECRET"
  "-H" "accept: application/json"
)

parse_confirmation() {
  CONFIRM=0
  ORDER_ARGS=("$@")
  if [ "${ORDER_ARGS[0]}" = "--yes" ]; then
    CONFIRM=1
    ORDER_ARGS=("${ORDER_ARGS[@]:1}")
  fi
}

require_confirmation() {
  if [ "$CONFIRM" -ne 1 ] && [ "$ALPACA_CONFIRM_ORDERS" != "1" ]; then
    echo "Error: order command requires --yes or ALPACA_CONFIRM_ORDERS=1."
    exit 1
  fi
}

validate_symbol() {
  if ! [[ "$1" =~ ^[A-Z][A-Z0-9.]{0,9}$ ]]; then
    echo "Error: invalid symbol '$1'."
    exit 1
  fi
}

validate_positive_number() {
  if ! [[ "$1" =~ ^([1-9][0-9]*)(\.[0-9]+)?$|^0\.[0-9]*[1-9][0-9]*$ ]]; then
    echo "Error: $2 must be a positive number."
    exit 1
  fi
}

get_exit_side_for_position() {
  local SYMBOL=$1
  local REQUESTED_QTY=$2
  local POSITION
  POSITION=$(curl -sS -X GET "${API_URL}/v2/positions/${SYMBOL}" "${HEADERS[@]}")
  POSITION_JSON="$POSITION" REQUESTED_QTY="$REQUESTED_QTY" SYMBOL="$SYMBOL" python3 - <<'PY'
import json
import os
import sys

symbol = os.environ["SYMBOL"]
try:
    position = json.loads(os.environ["POSITION_JSON"])
except json.JSONDecodeError as exc:
    print(f"Error: could not parse position response for {symbol}: {exc}", file=sys.stderr)
    sys.exit(1)

if "side" not in position or "qty" not in position:
    message = position.get("message", "position not found") if isinstance(position, dict) else "position not found"
    print(f"Error: cannot exit {symbol}; {message}.", file=sys.stderr)
    sys.exit(1)

requested_qty = float(os.environ["REQUESTED_QTY"])
position_qty = float(position["qty"])
if requested_qty > position_qty:
    print(f"Error: requested qty {requested_qty:g} exceeds current {symbol} position qty {position_qty:g}.", file=sys.stderr)
    sys.exit(1)

if position["side"] == "long":
    print("sell")
elif position["side"] == "short":
    print("buy")
else:
    print(f"Error: unsupported position side for {symbol}: {position['side']}", file=sys.stderr)
    sys.exit(1)
PY
}

COMMAND=$1
shift

case "$COMMAND" in
  account)
    curl -sS -X GET "${API_URL}/v2/account" "${HEADERS[@]}" | python3 -m json.tool
    ;;
  positions)
    curl -sS -X GET "${API_URL}/v2/positions" "${HEADERS[@]}" | python3 -m json.tool
    ;;
  buy)
    # Usage: ./alpaca.sh buy --yes TICKER QTY LIMIT_PRICE
    parse_confirmation "$@"
    require_confirmation
    SYMBOL=${ORDER_ARGS[0]}
    QTY=${ORDER_ARGS[1]}
    LIMIT=${ORDER_ARGS[2]}
    validate_symbol "$SYMBOL"
    validate_positive_number "$QTY" "QTY"
    validate_positive_number "$LIMIT" "LIMIT_PRICE"
    curl -sS -X POST "${API_URL}/v2/orders" "${HEADERS[@]}" \
      -H "content-type: application/json" \
      -d "{\"symbol\":\"${SYMBOL}\",\"qty\":\"${QTY}\",\"side\":\"buy\",\"type\":\"limit\",\"limit_price\":\"${LIMIT}\",\"time_in_force\":\"day\"}" | python3 -m json.tool
    ;;
  sell)
    # Usage: ./alpaca.sh sell --yes TICKER QTY
    parse_confirmation "$@"
    require_confirmation
    SYMBOL=${ORDER_ARGS[0]}
    QTY=${ORDER_ARGS[1]}
    validate_symbol "$SYMBOL"
    validate_positive_number "$QTY" "QTY"
    EXIT_SIDE=$(get_exit_side_for_position "$SYMBOL" "$QTY") || exit 1
    if [ "$EXIT_SIDE" != "sell" ]; then
      echo "Error: sell would increase a short position for $SYMBOL; refusing."
      exit 1
    fi
    curl -sS -X POST "${API_URL}/v2/orders" "${HEADERS[@]}" \
      -H "content-type: application/json" \
      -d "{\"symbol\":\"${SYMBOL}\",\"qty\":\"${QTY}\",\"side\":\"sell\",\"type\":\"market\",\"time_in_force\":\"day\"}" | python3 -m json.tool
    ;;
  trailing_stop)
    # Usage: ./alpaca.sh trailing_stop --yes TICKER QTY TRAIL_PERCENT
    parse_confirmation "$@"
    require_confirmation
    SYMBOL=${ORDER_ARGS[0]}
    QTY=${ORDER_ARGS[1]}
    PERCENT=${ORDER_ARGS[2]}
    validate_symbol "$SYMBOL"
    validate_positive_number "$QTY" "QTY"
    validate_positive_number "$PERCENT" "TRAIL_PERCENT"
    EXIT_SIDE=$(get_exit_side_for_position "$SYMBOL" "$QTY") || exit 1
    curl -sS -X POST "${API_URL}/v2/orders" "${HEADERS[@]}" \
      -H "content-type: application/json" \
      -d "{\"symbol\":\"${SYMBOL}\",\"qty\":\"${QTY}\",\"side\":\"${EXIT_SIDE}\",\"type\":\"trailing_stop\",\"trail_percent\":\"${PERCENT}\",\"time_in_force\":\"gtc\"}" | python3 -m json.tool
    ;;
  orders)
    curl -sS -X GET "${API_URL}/v2/orders?status=open" "${HEADERS[@]}" | python3 -m json.tool
    ;;
  verify)
    # Usage: ./alpaca.sh verify TICKER
    SYMBOL=$1
    curl -sS -X GET "${API_URL}/v2/assets/${SYMBOL}" "${HEADERS[@]}" | python3 -m json.tool
    ;;
  cancel)
    # Usage: ./alpaca.sh cancel ORDER_ID
    ORDER_ID=$1
    if [ -z "$ORDER_ID" ]; then
      echo "Error: ORDER_ID is required to cancel an order."
      echo "Usage: ./alpaca.sh cancel ORDER_ID"
      exit 1
    fi
    curl -sS -X DELETE "${API_URL}/v2/orders/${ORDER_ID}" "${HEADERS[@]}"
    echo "Order $ORDER_ID cancelled."
    ;;
  *)
    echo "Usage: $0 {account|positions|orders|buy|sell|trailing_stop|cancel} [args]"
    echo "Order commands require --yes or ALPACA_CONFIRM_ORDERS=1."
    exit 1
    ;;
esac
