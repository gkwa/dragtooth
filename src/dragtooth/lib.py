import datetime
import logging
import os
import pprint
import random
import re
import sys
import time
import typing

import bs4
import pandas
import pytz
import requests
import requests.exceptions

from . import common, k8s, model, scripts

_logger = logging.getLogger(__name__)

session_pair_pat = re.compile(
    r"Session pair has been generated\(dec\)"
    r" (?P<dec>\$[^:]+)\s+:\s+(?P<enc>\$[^:]+) \(enc\)"
)

sls_offline_pat = re.compile(r"ERROR: SLS service is offline")

CONNECT_TIMEOUT_SEC = 2

base_url = "http://tl3.streambox.com/"
status_url = f"{base_url}/light/light_status.php"
request_url = f"{base_url}/light/sreq.php"

# use requests's session auto manage cookies
module_session = requests.Session()

host_timezone = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo


def avoid_sls_crash():
    time.sleep(common.delay_to_prevent_crash_seconds)


def get_credentials_from_env() -> model.Credentials:
    def validate_credentials():
        msgs = []
        for v1 in ["WEBUI", "PULLTEST"]:
            for v2 in ["LOGIN", "PASSWORD"]:
                v3 = f"{v1}_{v2}"
                msg = f"{v3} is not set, try export {v3}=xyz"
                if not os.getenv(v3, None):
                    msgs.append(msg)
        for msg in msgs:
            _logger.critical(msg)

        if msgs:
            sys.exit(-1)

    validate_credentials()

    login = os.getenv("WEBUI_LOGIN", None)
    password = os.getenv("WEBUI_PASSWORD", None)

    return model.Credentials(login, password)


def check_host_is_running(endpoint: str) -> None:
    try:
        _logger.debug(f"feching {endpoint}")
        response = requests.get(endpoint, timeout=CONNECT_TIMEOUT_SEC)

        # Raises a HTTPError if the status is 4xx, 5xxx
        response.raise_for_status()

    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        _logger.critical(f"can't reach {endpoint}")
        sys.exit(-1)

    except requests.exceptions.HTTPError:
        _logger.critical("4xx, 5xx")
        sys.exit(-1)

    else:
        _logger.debug(f"Great!  I'm able to reach {endpoint}")


def populate_login_session(credentials: model.Credentials) -> None:
    payload = {"login": credentials.login, "password": credentials.password}

    _logger.debug(f"submitting post request to {status_url} with {payload=}")
    avoid_sls_crash()
    response = module_session.post(
        status_url, data=payload, timeout=CONNECT_TIMEOUT_SEC
    )

    msg = f"posting payload {payload} to " f"{status_url} returns response {response}"

    _logger.debug(msg)


def get_session_port_map_dataframe(
    df_list: typing.List[pandas.DataFrame],
) -> pandas.DataFrame:
    for df in df_list:
        if "enc" in df.columns and "dec" in df.columns:
            return df

    msg = "its unusual to not be able to find this port mapping"
    _logger.critical(msg)

    return pandas.DataFrame()


def dataframe_to_dict_list(df: pandas.DataFrame) -> typing.List[typing.Dict]:
    return df.to_dict("index")


def url_to_dataframe_list(url: str) -> typing.List[pandas.DataFrame]:
    avoid_sls_crash()
    response = module_session.get(status_url)
    _logger.debug(response.text)
    df_list = html_to_dataframes(response.text)
    return df_list


def html_to_dataframes(html: str) -> typing.List[pandas.DataFrame]:
    _logger.debug(f"response from fetching {status_url}:")
    _logger.debug(html)

    try:
        df_list = pandas.read_html(html)
    except ValueError:
        _logger.warning("pandas.read_html caused exception")

    msg = f"There are {len(df_list):,} data frames in page {status_url}"
    _logger.debug(msg)

    for i, df in enumerate(df_list, 1):
        msg = f"data frame number {i}:"
        _logger.debug(msg)
        _logger.debug(df.head())

    return df_list


def html_to_text(html: str):
    soup = bs4.BeautifulSoup(html, "html.parser")
    text = soup.get_text().strip()
    text = text.strip()
    _logger.debug(f"beautiful soup parses html as text like this: {text}")

    return text


def post_sessioncreate_request(port: int, lifetime: datetime.timedelta) -> str:
    payload = {
        "port1": port,
        "port2": port,
        "lifetime": lifetime.total_seconds() / 3600,
        "request": "Request",
    }

    try:
        avoid_sls_crash()
        response = module_session.post(request_url, data=payload, timeout=5)
        _logger.debug(f"response from post request to {request_url} is {response.text}")

        # Raises a HTTPError if the status is 4xx, 5xxx
        response.raise_for_status()

    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        _logger.critical(f"can't reach {request_url}")
        sys.exit(-1)

    except requests.exceptions.HTTPError:
        _logger.critical("4xx, 5xx")
        sys.exit(-1)

    else:
        _logger.debug(f"Great!  I'm able to reach {request_url}")

    return response.text


def post_session_delete_request(session: model.LightSession) -> str:
    payload = {
        "action": 3,
        "idd1": session.encoder,
        "idd2": session.decoder,
    }

    avoid_sls_crash()
    response = module_session.post(request_url, data=payload, timeout=5)
    _logger.debug(f"response from post request to {request_url} is {response.text}")

    return response.text


def generate_session_from_text(
    text: str, port: int, expires_at: datetime.timedelta
) -> model.LightSession:
    def debug(session):
        msg = (
            f"session {session} will expire at "
            f"{session.expires_at.astimezone(host_timezone)} utc: {session.expires_at}"
        )
        _logger.debug(msg)

    for line in text.splitlines():
        mo = session_pair_pat.search(line)
        if mo:
            dec = mo.group("dec").strip()
            enc = mo.group("enc").strip()
            session = model.LightSession(
                encoder=enc, decoder=dec, port=port, expires_at=expires_at
            )
            debug(session)
            return session

    session = model.LightSession(
        encoder="", decoder="", port=port, expires_at=expires_at
    )
    debug(session)

    return session


def check_sls_offline():
    avoid_sls_crash()
    response = module_session.get(status_url)
    _logger.debug(response.text)
    text = response.text
    msg = f"sls process isn't running according to parsing {status_url}"
    mo = sls_offline_pat.search(text)
    if mo:
        raise ValueError(msg)


def dataframe_list_to_list_of_lists_of_dicts(url: str) -> typing.List:
    df_list = url_to_dataframe_list(url)

    if df_list is None:
        msg = "data frame list is empty"
        _logger.critical(msg)
        return []

    df_list_as_list_of_list_of_dicts = []
    for df in df_list:
        _logger.debug("dataframe to dict list")
        dict_list = dataframe_to_dict_list(df)
        pf = pprint.pformat(dict_list)
        pf = f"\n{pf}"
        _logger.debug(pf)
        df_list_as_list_of_list_of_dicts.append(dict_list)

    return df_list_as_list_of_list_of_dicts


def show_list_of_dataframes_as_list_of_dicts():
    mylist = dataframe_list_to_list_of_lists_of_dicts(status_url)
    pf = pprint.pformat(mylist)
    pf = f"\n{pf}"
    _logger.debug("dataframe_list_to_list_of_lists_of_dicts")
    _logger.debug(pf)

    return mylist


def is_dataframe_empty(df: pandas.DataFrame):
    return df.empty


def port_in_use(port: int) -> bool:
    mylist = url_to_dataframe_list(status_url)
    df = get_session_port_map_dataframe(mylist)

    if is_dataframe_empty(df):
        _logger.warning("dataframe is empty")

    msg = f"{port} already exists, try another one please"
    if port in df.values:
        _logger.info(msg)
        return True
    return False


def get_random_port() -> int:
    ports = [
        1770,
        1771,
        1772,
        1773,
        1774,
        1775,
        1776,
        1777,
        1778,
        1779,
        1780,
        1781,
        1785,
    ]
    return random.choice(ports)


# WARNING THIS IS RACY since the port could be taken after checking
# whether its available
def get_available_port() -> int:
    port = get_random_port()
    while port_in_use(port):
        port = get_random_port()

    return port


def main(args):
    session_count = args.session_count
    session_lifetime_hours = args.session_lifetime_hours
    common.delay_to_prevent_crash_seconds = args.delay_to_prevent_crash

    check_host_is_running(endpoint=status_url)

    creds = get_credentials_from_env()
    populate_login_session(credentials=creds)

    session_lifetime = datetime.timedelta(hours=session_lifetime_hours)

    check_sls_offline()

    counter = session_count
    sessions = []
    while counter:
        port = get_available_port()
        _logger.debug(f"{port=}")
        html = post_sessioncreate_request(port=port, lifetime=session_lifetime)
        text = html_to_text(html)
        expires_at = (
            datetime.datetime.now(pytz.utc)
            + session_lifetime
            - datetime.timedelta(seconds=60)
        )
        session = generate_session_from_text(text, port=port, expires_at=expires_at)
        sessions.append(session)

        counter -= 1
        msg = (
            "session pair generated or re-fetched for "
            f"{port=} {session=}, {counter:,} remaining"
        )
        _logger.info(msg)

    for session in sessions:
        k8s.generate_k8s(session)
        scripts.generate_scripts(session)
