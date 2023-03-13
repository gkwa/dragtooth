import dataclasses
import io
import logging
import os
import pathlib
import sys

import requests

_logger = logging.getLogger(__name__)

outfile = pathlib.Path("geo.sh")
request_url = "https://api.ip2location.io"
session = requests.Session()


@dataclasses.dataclass
class IP2LocationRecord:
    ip: str
    country_code: str
    country_name: str
    region_name: str
    city_name: str
    latitude: str
    longitude: str
    zip_code: str
    time_zone: str
    asn: str
    as_: str = dataclasses.field(
        metadata={"description": "renamed from 'as' to 'as_' to prevent syntax error"}
    )
    is_proxy: str

    @classmethod
    def from_dict(cls, dct):
        dct["as_"] = dct["as"]
        del dct["as"]
        return cls(**dct)


def ip_geolocation(ips: list[str]) -> dict:
    def quick_check(ips):
        vfile = io.StringIO("")

        vfile.write("#!/usr/bin/env bash")
        vfile.write("\n")

        for ip in ips:
            out = f"""
            curl 'https://api.ip2location.io/?key={key}&ip={ip}'
            """
            out = out.strip()
            vfile.write(out)

            vfile.write("\n")
            vfile.write("echo")

            vfile.write("\n")
        return vfile

    keyname = "LOCATION_KEY"
    key = os.getenv(keyname, None)

    if not key:
        raise ValueError(keyname)

    _logger.debug("quick check")
    strio = quick_check(ips).getvalue()
    debug = f"\n{strio}"

    outfile.write_text(debug)

    _logger.debug(debug)


def get_api_key_from_env() -> str:
    keyname = "LOCATION_KEY"
    key = os.getenv(keyname, None)

    if not key:
        raise ValueError(keyname)

    return key


def fetch_data_for_ip(ip: str, api_key: str) -> dict:
    payload = {
        "key": api_key,
        "ip": ip,
    }

    try:
        response = requests.get(request_url, params=payload, timeout=5)
        _logger.debug(f"{response.url=}")

        # Raises a HTTPError if the status is 4xx, 5xxx
        response.raise_for_status()

    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        _logger.critical(f"can't reach {request_url}")
        sys.exit(-1)

    except requests.exceptions.HTTPError:
        _logger.critical("4xx, 5xx")
        raise

    else:
        _logger.debug(f"Great!  I'm able to reach {request_url}")

    _logger.debug(response.text)

    return response.json()


def test():
    # These two lines enable debugging at httplib level
    # (requests->urllib3->http.client) You will see the REQUEST,
    # including HEADERS and DATA, and RESPONSE with HEADERS but
    # without DATA. The only thing missing will be the response.body
    # which is not logged.

    try:
        import http.client as http_client
    except ImportError:
        # Python 2
        import httplib as http_client

    http_client.HTTPConnection.debuglevel = 1

    # You must initialize logging, otherwise you'll not see debug output.
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True

    ip = "89.189.176.193"
    api_key = get_api_key_from_env()
    dct = fetch_data_for_ip(ip, api_key)
    ipl = IP2LocationRecord.from_dict(dct)
    print(ipl)
    _logger.debug(dct)


if __name__ == "__main__":
    test()
