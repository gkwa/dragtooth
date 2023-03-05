import os
import re

import bs4
import requests

# use requests's session auto manage cookies
curSession = requests.Session()
# all cookies received will be stored in the session object

login = os.getenv("WEBUI_LOGIN", None)
password = os.getenv("WEBUI_PASSWORD", None)

if not login:
    ValueError("WEBUI_LOGIN")
if not password:
    ValueError("WEBUI_PASSWORD")

payload = {"login": login, "password": password}
url = "http://tl3.streambox.com/light/light_status.php"

curSession.post(url, data=payload)
# internally return your expected cookies, can use for following auth

# internally use previously generated cookies, can access the resources

pat = re.compile(
    r"Session pair has been generated\(dec\)"
    r" (?P<dec>\$[^:]+)\s+:\s+(?P<enc>\$[^:]+) \(enc\)"
)


def doit2(text: str):
    for line in text.splitlines():
        # print(f"[{line}]")
        mo = pat.search(line)
        if mo:
            dec = mo.group("dec")
            enc = mo.group("enc")
            dec = dec.strip()
            enc = enc.strip()
            return (enc, dec)
    return (None, None)


def doit(port: int):
    payload = {
        "port1": port,
        "port2": port,
        "lifetime": "1",
        "request": "Request",
    }

    url = "http://tl3.streambox.com/light/sreq.php"
    response = curSession.post(url, data=payload)
    soup = bs4.BeautifulSoup(response.text, "html.parser")
    text = soup.get_text()
    return text


port = 2000
for i in range(30):
    port = port + i
    stuff = doit(port)
    enc, dec = doit2(stuff)
    print(f"{port=}, {dec=}, {enc=}")
