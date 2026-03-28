#!/usr/bin/env python3
"""HTTP server for Google Sheets read/write using service account."""
import json, time, subprocess, tempfile, os, base64, urllib.request, urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

SA_KEY_FILE = "/opt/n8n/service-account.json"
SPREADSHEET_ID = "1Np6jHLfIeudk_N5yNQZLQ8Puxkk8MxAKrxdY8gVtinE"

_token_cache = {"token": None, "expires": 0}

def get_access_token():
    now = int(time.time())
    if _token_cache["token"] and _token_cache["expires"] > now + 60:
        return _token_cache["token"]
    with open(SA_KEY_FILE) as f:
        sa = json.load(f)
    header = base64.urlsafe_b64encode(json.dumps({"alg":"RS256","typ":"JWT"}).encode()).rstrip(b"=").decode()
    claims = base64.urlsafe_b64encode(json.dumps({
        "iss": sa["client_email"],
        "scope": "https://www.googleapis.com/auth/spreadsheets",
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now, "exp": now + 3600
    }).encode()).rstrip(b"=").decode()
    sign_input = f"{header}.{claims}"
    with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as f:
        f.write(sa["private_key"]); keyfile = f.name
    result = subprocess.run(['openssl', 'dgst', '-sha256', '-sign', keyfile], input=sign_input.encode(), capture_output=True)
    os.unlink(keyfile)
    sig = base64.urlsafe_b64encode(result.stdout).rstrip(b"=").decode()
    jwt = f"{sign_input}.{sig}"
    data = urllib.parse.urlencode({"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": jwt}).encode()
    resp = json.loads(urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=data)).read())
    _token_cache["token"] = resp["access_token"]
    _token_cache["expires"] = now + 3600
    return resp["access_token"]


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Read sheets data. GET /?sheets=Транзакции,Подписки"""
        from urllib.parse import urlparse, parse_qs
        params = parse_qs(urlparse(self.path).query)
        sheets = params.get('sheets', ['Транзакции,Подписки'])[0].split(',')
        
        token = get_access_token()
        result = {}
        for sheet in sheets:
            sheet = sheet.strip()
            url = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/{urllib.parse.quote(sheet)}"
            req = urllib.request.Request(url)
            req.add_header('Authorization', f'Bearer {token}')
            try:
                resp = json.loads(urllib.request.urlopen(req).read())
                result[sheet] = resp.get('values', [])
            except Exception as e:
                result[sheet] = {"error": str(e)}
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(result, ensure_ascii=False).encode())

    def do_POST(self):
        """Append rows. POST body: {"sheet": "...", "rows": [[...]]}"""
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length))
        sheet = body.get("sheet", "Транзакции")
        rows = body.get("rows", [])
        if not rows:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{"error":"no rows"}')
            return
        token = get_access_token()
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/{urllib.parse.quote(sheet)}:append?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS"
        req = urllib.request.Request(url, method='POST')
        req.add_header('Authorization', f'Bearer {token}')
        req.add_header('Content-Type', 'application/json')
        resp = urllib.request.urlopen(req, json.dumps({"values": rows}).encode())
        result = json.loads(resp.read())
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True, "updates": result.get("updates", {})}).encode())

    def log_message(self, format, *args):
        pass

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 9876), Handler)
    print("Sheets API server on :9876")
    server.serve_forever()
