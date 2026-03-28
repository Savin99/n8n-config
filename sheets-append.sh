#!/bin/bash
# Append a row to Google Sheets using service account
# Usage: sheets-append.sh "date" "bank" "type" "amount" "recipient" "category" "source"

SA_KEY_FILE="/opt/n8n/service-account.json"
SPREADSHEET_ID="1Np6jHLfIeudk_N5yNQZLQ8Puxkk8MxAKrxdY8gVtinE"
SHEET="Транзакции"

# Generate JWT using python3 (available on most systems)
ACCESS_TOKEN=$(python3 << PYEOF
import json, time, urllib.request, urllib.parse
from http.client import HTTPSConnection
import hashlib, hmac, base64

# Read service account
with open("$SA_KEY_FILE") as f:
    sa = json.load(f)

# Create JWT
import subprocess
header = base64.urlsafe_b64encode(json.dumps({"alg":"RS256","typ":"JWT"}).encode()).rstrip(b"=").decode()
now = int(time.time())
claims = base64.urlsafe_b64encode(json.dumps({"iss":sa["client_email"],"scope":"https://www.googleapis.com/auth/spreadsheets","aud":"https://oauth2.googleapis.com/token","iat":now,"exp":now+3600}).encode()).rstrip(b"=").decode()
sign_input = f"{header}.{claims}"

# Sign with openssl
import tempfile, os
with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as f:
    f.write(sa["private_key"])
    keyfile = f.name

result = subprocess.run(['openssl', 'dgst', '-sha256', '-sign', keyfile], input=sign_input.encode(), capture_output=True)
os.unlink(keyfile)
sig = base64.urlsafe_b64encode(result.stdout).rstrip(b"=").decode()
jwt = f"{sign_input}.{sig}"

# Get access token
data = urllib.parse.urlencode({"grant_type":"urn:ietf:params:oauth:grant-type:jwt-bearer","assertion":jwt}).encode()
req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
resp = json.loads(urllib.request.urlopen(req).read())
print(resp["access_token"])
PYEOF
)

echo "$ACCESS_TOKEN"
