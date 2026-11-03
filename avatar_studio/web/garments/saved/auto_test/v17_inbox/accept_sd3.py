"""Accept the SD3 license for the logged-in account. Does not print the token."""

import json
from pathlib import Path
from urllib import request

TOKEN = Path("/home/nadhir/remu/hf/token").read_text(encoding="utf-8").strip()
URL = "https://huggingface.co/stabilityai/stable-diffusion-3-medium-diffusers/ask-access"
BODY = {
    "Name": "Nadhir Maamar",
    "Email": "nadhir.maamar@esprit.tn",
    "Country": "TN",
    "Organization or Affiliation": "ESPRIT",
    "Receive email updates and promotions on Stability AI products, services, and research?": "No",
    "I acknowledge that this model is for non-commercial use only unless I acquire a separate license from Stability AI": "true",
}
data = json.dumps(BODY).encode("utf-8")
req = request.Request(
    URL,
    data=data,
    headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    method="POST",
)
try:
    with request.urlopen(req) as response:
        print("status", response.status)
        print(response.read().decode("utf-8")[:400])
except Exception as error:
    body = getattr(error, "read", lambda: b"")()
    print(type(error).__name__, getattr(error, "code", ""))
    print(body.decode("utf-8", errors="replace")[:500])
