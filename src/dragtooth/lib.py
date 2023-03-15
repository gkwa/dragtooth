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
import durations
import pandas
import pytz
import requests
import requests.exceptions

from . import common, geolocate, k8s, model, scripts

_logger = logging.getLogger(__name__)

session_pair_pat = re.compile(
    r"Session pair has been generated\(dec\)"
    r" (?P<dec>\$[^:]+)\s+:\s+(?P<enc>\$[^:]+) \(enc\)"
)

sls_offline_pat = re.compile(r"ERROR: SLS service is offline")

CONNECT_TIMEOUT_SEC = 2

if not common.base_url:
    raise ValueError(common.msg_base_url_invalid)

# use requests's session auto manage cookies
module_session = requests.Session()

host_timezone = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo


def avoid_sls_crash():
    time.sleep(common.delay_to_prevent_crash.total_seconds())


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

    _logger.debug(f"submitting post request to {common.status_url} with {payload=}")
    avoid_sls_crash()
    response = module_session.post(
        common.status_url, data=payload, timeout=CONNECT_TIMEOUT_SEC
    )

    msg = (
        f"posting payload {payload} to "
        f"{common.status_url} returns response {response}"
    )

    _logger.debug(msg)


def ports_from_range(_range: str | int) -> set[int]:
    """
    1770 -> {1770}
    "1770" -> {1770}
    "1770-1771" -> {1770, 1771}
    "1770-1770" -> {1770}
    "Request public session from broker" -> {}
    """

    u = str(_range)
    start = finish = u
    ports_in_range = set()

    if "-" in u:
        start, finish = [int(i) for i in u.split("-")]

    msg = (
        "returning early in ports_from_range() because"
        f" I can't cast '{start}' to int."
        " Not being able to parse this value is an"
        " expected condition since we're parsing a UI"
    )

    try:
        start = int(str(start).strip())
    except ValueError:
        _logger.debug(msg)
        return set()

    finish = int(str(finish).strip())
    ports = [start] if start == finish else list(range(start, finish + 1))

    for port in ports:
        ports_in_range.add(port)

    return ports_in_range


def get_remaining_unused_ports() -> list[int]:
    df_list = url_to_dataframe_list(common.status_url)
    df = get_session_port_map_dataframe(df_list)

    x = set([str(x) for x in df["ports"].tolist()])
    # x is mishmash of UI elements and port ranges and ports,
    # example: [1779, "1780-1782", 'Request public session from broker']
    _logger.debug(f"parsed ports from webui: {x}")

    ports_in_use = set()
    for _range in x:
        p = ports_from_range(_range)
        ports_in_use = ports_in_use | p

    _logger.debug(f"{sorted(ports_in_use)=}")

    y = set([int(x) for x in sls_listening_ports])
    _logger.debug(f"sls_listening_ports={sorted(y)}")

    remaining = y - ports_in_use

    msg = f"remaining ports availble for use {sorted(remaining)=}"
    _logger.debug(msg)

    remaining = sorted([int(x) for x in remaining])

    return remaining


def get_session_port_map_dataframe(
    df_list: typing.List[pandas.DataFrame],
) -> pandas.DataFrame:
    for df in df_list:
        if "enc" in df.columns and "dec" in df.columns:
            return df

    msg = "its unusual to not be able to find this port mapping"
    _logger.critical(msg)

    return pandas.DataFrame()


def get_incoming_ports_dataframe(
    df_list: typing.List[pandas.DataFrame],
) -> pandas.DataFrame:
    for df in df_list:
        if (
            "port" in df.columns
            and "encoders" in df.columns
            and "bitrate in" in df.columns
            and "bitrate out" in df.columns
        ):
            return df

    msg = "its unusual to not be able to find the Incoming Ports table"
    _logger.critical(msg)

    return pandas.DataFrame()


def dataframe_to_dict_list(df: pandas.DataFrame) -> typing.List[typing.Dict]:
    return df.to_dict("index")


def i_am_authenticated() -> bool:
    response = module_session.get(common.status_url)
    _logger.debug("\nauthenticated:")
    _logger.debug(response.text)
    if "sign in" in response.text.lower():
        return False
    return True


def url_to_dataframe_list(url: str) -> typing.List[pandas.DataFrame]:
    avoid_sls_crash()
    response = module_session.get(common.status_url)
    _logger.debug(response.text)
    df_list = html_to_dataframes(response.text)
    return df_list


def html_to_dataframes(html: str) -> typing.List[pandas.DataFrame]:
    _logger.debug(f"response from fetching {common.status_url}:")
    _logger.debug(html)

    try:
        df_list = pandas.read_html(html)
    except ValueError:
        _logger.warning("pandas.read_html caused exception")

    msg = f"There are {len(df_list):,} data frames in page {common.status_url}"
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
        response = module_session.post(common.request_url, data=payload, timeout=5)
        _logger.debug(
            f"response from post request to {common.request_url} is {response.text}"
        )

        # Raises a HTTPError if the status is 4xx, 5xxx
        response.raise_for_status()

    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        _logger.critical(f"can't reach {common.request_url}")
        sys.exit(-1)

    except requests.exceptions.HTTPError:
        _logger.critical("4xx, 5xx")
        sys.exit(-1)

    else:
        _logger.debug(f"Great!  I'm able to reach {common.request_url}")

    # refresh page so my new port appears on status page
    url = common.status_url.rstrip("?")
    url = f"{common.status_url}?"
    module_session.get(url)

    return response.text


def post_session_delete_request(session: model.LightSession) -> str:
    payload = {
        "action": 3,
        "idd1": session.encoder,
        "idd2": session.decoder,
    }

    avoid_sls_crash()
    response = module_session.post(common.request_url, data=payload, timeout=5)
    _logger.debug(
        f"response from post request to {common.request_url} is {response.text}"
    )

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
    response = module_session.get(common.status_url)
    _logger.debug(response.text)
    text = response.text
    msg = f"sls process isn't running according to parsing {common.status_url}"
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
    df_list = dataframe_list_to_list_of_lists_of_dicts(common.status_url)
    pf = pprint.pformat(df_list)
    pf = f"\n{pf}"
    _logger.debug("dataframe_list_to_list_of_lists_of_dicts")
    _logger.debug(pf)

    return df_list


def is_dataframe_empty(df: pandas.DataFrame):
    return df.empty


def display_dataframe(df: pandas.DataFrame):
    # display all the  rows
    pandas.set_option("display.max_rows", None)

    # display all the  columns
    pandas.set_option("display.max_columns", None)

    # set width  - 100
    pandas.set_option("display.width", 1000)

    # set column header -  left
    pandas.set_option("display.colheader_justify", "left")

    # set precision - 5
    pandas.set_option("display.precision", 5)

    _logger.debug(df)


def port_in_use(port: int) -> bool:
    df_list = url_to_dataframe_list(common.status_url)
    df = get_session_port_map_dataframe(df_list)
    display_dataframe(df)

    if is_dataframe_empty(df):
        _logger.warning("dataframe is empty")

    msg = f"{port} already exists, try another one please"
    if str(port) in df.ports.values:
        _logger.info(msg)
        return True
    return False


def get_data_usage_dataframe(
    df_list: typing.List[pandas.DataFrame],
) -> pandas.DataFrame | None:

    headers = {
        "ip",
        "data",
        "time",
        "first active",
        "last active",
    }

    for df in df_list:
        if headers.issubset(df.columns):
            return df

    msg = (
        "I searched through all tables"
        " but couldn't find the table whose field names matched"
        f" {headers}"
    )
    raise ValueError(msg)


def get_ip_addresses(column: str = "ip") -> list[str]:
    df_list = url_to_dataframe_list(common.status_url)
    df = get_data_usage_dataframe(df_list)
    _logger.debug(f"{column=}")
    ips = df[column].values
    _logger.debug(f"{ips=}")

    return ips


def set_global_sls_listening_ports():
    global sls_listening_ports
    df_list = url_to_dataframe_list(common.status_url)
    df = get_incoming_ports_dataframe(df_list)
    sls_listening_ports = list(set(df.port.values))


def get_random_port() -> int:
    _logger.debug(f"{sls_listening_ports=}")
    return random.choice(sls_listening_ports)


# WARNING THIS IS RACY since the port could be taken after checking
# whether its available
def get_available_port() -> int | None:
    remaining = get_remaining_unused_ports()
    if not remaining:
        return None
    return remaining[0]


def main(args):
    session_count = args.session_count
    session_lifetime_duration = durations.Duration(args.session_lifetime)

    d1 = args.prevent_crash_delay
    duration = durations.Duration(d1)
    delta = datetime.timedelta(seconds=duration.to_seconds())
    common.delay_to_prevent_crash = delta

    check_host_is_running(endpoint=common.status_url)

    login = os.getenv("VAR_SLS_LIGHT_WEBUI_LOGIN_USERNAME", None)
    password = os.getenv("VAR_SLS_LIGHT_WEBUI_LOGIN_PASSWORD", None)
    if not login:
        raise ValueError("VAR_SLS_LIGHT_WEBUI_LOGIN_USERNAME not defined")
    if not password:
        raise ValueError("VAR_SLS_LIGHT_WEBUI_LOGIN_PASSWORD not defined")
    creds = model.Credentials(login, password)

    populate_login_session(credentials=creds)

    if not i_am_authenticated():
        raise ValueError("not authenticated")

    session_lifetime = datetime.timedelta(
        seconds=session_lifetime_duration.to_seconds()
    )

    check_sls_offline()

    set_global_sls_listening_ports()

    ports_available = get_remaining_unused_ports()

    msg1 = (
        f"you asked for {session_count:,} ports, but there are only"
        f" {len(ports_available):,} remaining"
        f" available: {', '.join([str(x) for x in ports_available])}."
        " I will use the remaing ports"
    )

    if not ports_available:
        msg1 = (
            f"you asked for {session_count:,} port(s), but there are no"
            f" ports remaining available."
        )

    if len(ports_available) < session_count:
        _logger.warning(msg1)

    msg2 = f"you asked for {session_count:,} ports, but" " there are no ports availble"

    if get_available_port() is None:
        _logger.warning(msg2)
        _logger.warning("quitting prematurely")
        sys.exit(-1)

    if args.update_geolocation:
        get_remaining_unused_ports()
        # geolocation.ip_geolocation(get_ip_addresses())
        ips_list = get_ip_addresses()
        geolocate.get_regions_for_ips(ips_list)

    counter = session_count
    sessions = []
    while counter:
        port = get_available_port()
        _logger.debug(f"{port=}")

        if get_available_port() is None:
            msg = (
                f"you asked for {session_count:,} ports but I"
                f" could only create {len(sessions):,} ports"
                " before I ran out of available ports"
            )
            _logger.warning(msg)
            sys.exit(-1)

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
