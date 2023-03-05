import datetime
import logging
import os
import re
import sys

import bs4
import requests
import requests.exceptions

from . import model

_logger = logging.getLogger(__name__)

session_pair_pat = re.compile(
    r"Session pair has been generated\(dec\)"
    r" (?P<dec>\$[^:]+)\s+:\s+(?P<enc>\$[^:]+) \(enc\)"
)

sls_offline_pat = re.compile(r"ERROR: SLS service is offline")

CONNECT_TIMEOUT_SEC = 2

# use requests's session auto manage cookies
module_session = requests.Session()
status_url = "http://tl3.streambox.com/light/light_status.php"


def get_credentials_from_env() -> model.Credentials:
    def validate_login(login):
        msg_login = (
            "WEBUI_LOGIN is incorrect, try: export "
            "WEBUI_LOGIN=username WEBUI_PASSWORD=password"
        )

        if not login:
            _logger.critical(msg_login)
            sys.exit(-1)

    def validate_password(login):
        msg_password = (
            "WEBUI_PASSWORD is incorrect, try: export "
            "WEBUI_LOGIN=username WEBUI_PASSWORD=password"
        )

        if not password:
            _logger.critical(msg_password)
            sys.exit(-1)

    login = os.getenv("WEBUI_LOGIN", None)
    validate_login(login)

    password = os.getenv("WEBUI_PASSWORD", None)
    validate_login(password)

    return model.Credentials(login, password)


def check_host_is_running(endpoint: str) -> None:
    try:
        _logger.debug(f"feching {endpoint}")
        response = requests.get(endpoint, timeout=CONNECT_TIMEOUT_SEC)

        # Raises a HTTPError if the status is 4xx, 5xxx
        response.raise_for_status()

    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        _logger.critical(f"can't reach {endpoint}")
        raise

    except requests.exceptions.HTTPError:
        _logger.critical("4xx, 5xx")
        raise

    else:
        _logger.debug(f"Great!  I'm able to reach {endpoint}")


def populate_login_session(credentials: model.Credentials) -> None:
    payload = {"login": credentials.login, "password": credentials.password}

    _logger.debug(f"submitting post request to {status_url} with {payload=}")
    response = module_session.post(
        status_url, data=payload, timeout=CONNECT_TIMEOUT_SEC
    )

    msg = f"posting payload {payload} to " f"{status_url} returns response {response}"

    _logger.debug(msg)


def parse_sessions_from_status_endpoint() -> None:
    response = module_session.get(status_url)

    # expect html table of encoder session ids and decoder session ids
    _logger.debug(response.text)

    return response.text


def html_to_text(html: str):
    soup = bs4.BeautifulSoup(html, "html.parser")
    text = soup.get_text().strip()
    text = text.strip()
    _logger.debug(f"beautiful soup parses html as text like this: {text}")

    return text


def post_sessioncreate_request(port: int, lifetime: datetime.timedelta) -> str:
    url = "http://tl3.streambox.com/light/sreq.php"
    payload = {
        "port1": port,
        "port2": port,
        "lifetime": lifetime.total_seconds() / 3600,
        "request": "Request",
    }

    try:
        response = module_session.post(url, data=payload, timeout=5)
        _logger.debug(f"response from post request to {url} is {response.text}")

        # Raises a HTTPError if the status is 4xx, 5xxx
        response.raise_for_status()

    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        _logger.critical(f"can't reach {url}")
        sys.exit(-1)

    except requests.exceptions.HTTPError:
        _logger.critical("4xx, 5xx")
        sys.exit(-1)

    else:
        _logger.debug(f"Great!  I'm able to reach {url}")

    return response.text


def post_session_delete_request(session: model.LightSession) -> str:
    payload = {
        "action": 3,
        "idd1": session.encoder,
        "idd2": session.decoder,
    }

    url = "http://tl3.streambox.com/light/sreq.php"
    response = module_session.post(url, data=payload, timeout=5)
    _logger.debug(f"response from post request to {url} is {response.text}")

    return response.text


def generate_session_from_text(text: str, port: int) -> model.LightSession:
    for line in text.splitlines():
        mo = session_pair_pat.search(line)
        if mo:
            dec = mo.group("dec").strip()
            enc = mo.group("enc").strip()
            return model.LightSession(encoder=enc, decoder=dec, port=port)

    return model.LightSession(encoder="", decoder="", port=port)


def check_sls_offline():
    response = module_session.get(status_url)
    _logger.debug(response.text)
    text = response.text
    mo = sls_offline_pat.search(text)
    if mo:
        raise ValueError(
            "sls process isn't running according" f" to parsing {status_url}"
        )


def main(args):
    session_count = args.session_count
    session_lifetime_hours = args.session_lifetime_hours

    check_host_is_running(endpoint=status_url)
    creds = get_credentials_from_env()
    populate_login_session(credentials=creds)

    check_sls_offline()

    session_lifetime = datetime.timedelta(hours=session_lifetime_hours)

    starting_port = 2000
    msg = (
        f"request to create {session_count} "
        f"sessions, starting at port {starting_port}"
    )
    _logger.info(msg)

    status_page = parse_sessions_from_status_endpoint()
    _logger.debug(f"{status_page=}")

    check_sls_offline()

    for offset in range(session_count):
        port = starting_port + offset
        _logger.debug(f"{port=}, {offset=}")
        html = post_sessioncreate_request(port=port, lifetime=session_lifetime)
        text = html_to_text(html)
        session = generate_session_from_text(text, port=port)
        msg = (
            "session pair generated or re-fetched for "
            f"{port=} {session=}, {session_count-offset-1:,} remaining"
        )
        _logger.info(msg)
