#!/bin/sh
# فتح نفق HTTPS عالمي للوصول إلى Hilal AI من أي هاتف في العالم.
# ملاحظة: تأكد أن الخادم يعمل أولاً:  cd backend && PORT=8000 sh start.sh
#
# الخيار 1 (مفضّل): Cloudflare Quick Tunnel — رابط ثابت طالما العملية تعمل.
# الخيار 2 (احتياطي): Pinggy SSH — رابط مجاني لمدة 60 دقيقة.
#
# لتنزيل cloudflared على Termux/arm64:
#   wget -O /tmp/opencode/cloudflared \
#     https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64
#   chmod +x /tmp/opencode/cloudflared

PORT="${PORT:-8000}"
CF_BIN="${CF_BIN:-/tmp/opencode/cloudflared}"

if [ -x "$CF_BIN" ]; then
  echo ">>> Cloudflare tunnel -> http://127.0.0.1:$PORT"
  exec "$CF_BIN" tunnel --no-autoupdate --url "http://127.0.0.1:$PORT"
fi

if command -v cloudflared >/dev/null 2>&1; then
  echo ">>> Cloudflare tunnel (system) -> http://127.0.0.1:$PORT"
  exec cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:$PORT"
fi

echo ">>> cloudflared غير موجود، استخدام Pinggy..."
exec ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -o ServerAliveInterval=30 -p 443 -R0:"localhost:$PORT" a.pinggy.io
