#!/usr/bin/env bash
# Create .env from .env.example. Each CHANGEME gets its own random secret;
# CHANGEME_PG gets one shared value (password and DATABASE_URL must match);
# CHANGEME_KEY32 gets 32 random bytes as hex (Langfuse encryption key).
set -euo pipefail
python3 - <<'PY'
import re
import secrets

text = open(".env.example").read()
text = text.replace("CHANGEME_PG", secrets.token_hex(24))
text = text.replace("CHANGEME_KEY32", secrets.token_hex(32))
text = re.sub("CHANGEME", lambda _: secrets.token_hex(24), text)
open(".env", "w").write(text)
PY
echo ".env created with generated dev secrets"
