import logging
import os
import re

import bs4
import requests
import requests.exceptions

_logger = logging.getLogger(__name__)

pat = re.compile(
    r"Session pair has been generated\(dec\)"
    r" (?P<dec>\$[^:]+)\s+:\s+(?P<enc>\$[^:]+) \(enc\)"
)

CONNECT_TIMEOUT_SEC = 2

# use requests's session auto manage cookies
curSession = requests.Session()


def startup():
    # all cookies received will be stored in the session object

    login = os.getenv("WEBUI_LOGIN", None)
    password = os.getenv("WEBUI_PASSWORD", None)

    if not login:
        ValueError("WEBUI_LOGIN")
    if not password:
        ValueError("WEBUI_PASSWORD")

    payload = {"login": login, "password": password}
    url = "http://tl3.streambox.com/light/light_status.php"

    try:
        r = requests.get(url, timeout=CONNECT_TIMEOUT_SEC)
        _logger.debug(f"feching {url}")
        r.raise_for_status()  # Raises a HTTPError if the status is 4xx, 5xxx
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        _logger.critical(f"can't reach {url}")
        raise

    except requests.exceptions.HTTPError:
        print("4xx, 5xx")
    else:
        print("All good!")  # Proceed to do stuff with `r`

    curSession.post(url, data=payload, timeout=CONNECT_TIMEOUT_SEC)
    # internally return your expected cookies, can use for following auth

    # internally use previously generated cookies, can access the resources


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
    response = curSession.post(url, data=payload, timeout=5)
    soup = bs4.BeautifulSoup(response.text, "html.parser")
    text = soup.get_text()
    return text


def main():
    startup()
    port = 2000
    for i in range(30):
        port = port + i
        stuff = doit(port)
        enc, dec = doit2(stuff)
        print(f"{port=}, {dec=}, {enc=}")
