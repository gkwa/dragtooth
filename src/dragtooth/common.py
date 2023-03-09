import logging
import os
import pathlib

import jinja2
import pkg_resources

global delay_to_prevent_crash_seconds
delay_to_prevent_crash_seconds = None


_logger = logging.getLogger(__name__)

data_dir = pathlib.Path("data")
_logger.info(f"data directory is {data_dir.resolve()}")
data_dir.mkdir(parents=True, exist_ok=True)


package = __name__.split(".")[0]
templates_dir = pathlib.Path(pkg_resources.resource_filename(package, "templates"))
loader = jinja2.FileSystemLoader(searchpath=templates_dir)
env = jinja2.Environment(loader=loader, keep_trailing_newline=True)


def generate_pulltest_login():
    pulltest_login = os.getenv("PULLTEST_LOGIN", None)

    if not pulltest_login:
        raise ValueError("PULLTEST_LOGIN not defined")

    return pulltest_login


def generate_pulltest_password():
    pulltest_password = os.getenv("PULLTEST_PASSWORD", None)

    if not pulltest_password:
        raise ValueError("PULLTEST_PASSWORD not defined")

    return pulltest_password


def generate_data(session):
    pulltest_password = generate_pulltest_password()
    pulltest_login = generate_pulltest_login()

    data = {
        "ip": "172.30.0.139",
        "drm": session.encoder,
        "network1": session.encoder,
        "NET1": session.decoder,
        "reporter": f"reporter-{session.encoder}-{session.decoder}".lower().replace(
            "$", ""
        ),
        "slug": f"slug-{session.encoder}-{session.decoder}".lower().replace("$", ""),
        "decoder": session.decoder,
        "pull_port": session.port,
        "pulltest_login": pulltest_login,
        "pulltest_password": pulltest_password,
    }
    return data
