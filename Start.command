#!/bin/bash
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.10 or newer is required. Install Python, then reopen Start.command."
  read -r -p "Press Enter to close."
  exit 1
fi
python3 app.py --open "$@"
result=$?
if [ "$result" -ne 0 ]; then
  echo "The app could not start. Review the message above."
  read -r -p "Press Enter to close."
fi
exit "$result"
