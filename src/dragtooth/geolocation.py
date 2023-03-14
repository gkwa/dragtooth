import io
import logging
import os
import pathlib
import sys

import peewee
import requests

_logger = logging.getLogger(__name__)

outfile = pathlib.Path("geo.sh")
request_url = "https://api.ip2location.io"
session = requests.Session()

db = peewee.SqliteDatabase("geo.db")


class IP2Location(peewee.Model):
    ip = peewee.CharField()
    country_code = peewee.CharField()
    country_name = peewee.CharField()
    region_name = peewee.CharField()
    city_name = peewee.CharField()
    latitude = peewee.CharField()
    longitude = peewee.CharField()
    zip_code = peewee.CharField()
    time_zone = peewee.CharField()
    asn = peewee.CharField()
    as_ = peewee.CharField()
    is_proxy = peewee.CharField()

    class Meta:
        database = db  # This model uses the "people.db" database.

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
