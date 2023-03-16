import logging
import os
import pathlib

import jinja2
import pkg_resources

global delay_to_prevent_crash
delay_to_prevent_crash = None


_logger = logging.getLogger(__name__)

data_dir = pathlib.Path("data")
_logger.info(f"data directory is {data_dir.resolve()}")
data_dir.mkdir(parents=True, exist_ok=True)


package = __name__.split(".")[0]
templates_dir = pathlib.Path(pkg_resources.resource_filename(package, "templates"))
loader = jinja2.FileSystemLoader(searchpath=templates_dir)
env = jinja2.Environment(loader=loader, keep_trailing_newline=True)

msg_base_url_invalid = (
    "VAR_SLS_LIGHT_BASE_URL is required."
    " Example: http://hostname.domainname.com/, "
    "quitting prematurely."
)

base_url = os.getenv("VAR_SLS_LIGHT_BASE_URL", None)
status_url = f"{base_url}/light/light_status.php"
request_url = f"{base_url}/light/sreq.php"


def generate_pulltest_login():
    pulltest_login = os.getenv("VAR_PULLTEST_LOGIN", None)

    if not pulltest_login:
        raise ValueError("VAR_PULLTEST_LOGIN not defined")

    return pulltest_login


def generate_pulltest_password():
    pulltest_password = os.getenv("VAR_PULLTEST_PASSWORD", None)

    if not pulltest_password:
        raise ValueError("VAR_PULLTEST_PASSWORD not defined")

    return pulltest_password


def generate_data(session):
    pulltest_password = generate_pulltest_password()
    pulltest_login = generate_pulltest_login()

    encoder_decoder_id = f"{session.encoder}-{session.decoder}"
    slug = f"slug-{encoder_decoder_id}".lower().replace("$", "")
    reporter = f"reporter-{encoder_decoder_id}".lower().replace("$", "")

    data = {
        "ip": "172.30.0.139",
        "encoder_decoder_id": encoder_decoder_id,
        "drm": session.encoder,
        "network1": session.encoder,
        "NET1": session.decoder,
        "reporter": reporter,
        "slug": slug,
        "decoder": session.decoder,
        "pull_port": session.port,
        "pulltest_login": pulltest_login,
        "pulltest_password": pulltest_password,
    }
    return data
