#!/bin/bash
source ./.env
python3 bot.py 1>bot.log 2>&1 &
python3 redirector.py 1>redirector.log 2>&1 &
if [ ! -f "cfd" ]; then
    wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O cfd && chmod +x cfd
fi
./cfd --no-autoupdate tunnel run --token $CFD_TOKEN 1>/dev/null 2>&1 &
