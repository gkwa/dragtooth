import logging
import os
import pathlib

import jinja2
import pkg_resources

_logger = logging.getLogger(__name__)

data_dir = pathlib.Path("k8s")
_logger.info(f"data directory is {data_dir.resolve()}")
data_dir.mkdir(parents=True, exist_ok=True)

package = __name__.split(".")[0]
templates_dir = pathlib.Path(pkg_resources.resource_filename(package, "templates"))
loader = jinja2.FileSystemLoader(searchpath=templates_dir)
env = jinja2.Environment(loader=loader, keep_trailing_newline=True)
tpl_sendstream = env.get_template("sendstream.yaml.j2")
tpl_pulltest = env.get_template("pulltest.yaml.j2")


def generate_k8s(session):
    pulltest_login = os.getenv("PULLTEST_LOGIN", None)

    if not pulltest_login:
        raise ValueError("PULLTEST_LOGIN not defined")

    pulltest_password = os.getenv("PULLTEST_PASSWORD", None)

    if not pulltest_password:
        raise ValueError("PULLTEST_PASSWORD not defined")

    x = session.encoder.lower()
    y = session.decoder.lower()
    pair_annotation = f"{x}-{y}".replace("$", "")

    data = {
        "ip": "172.30.0.139",
        "drm": session.encoder,
        "network1": session.encoder,
        "NET1": session.decoder,
        "reporter": f"reporter-{pair_annotation}",
        "decoder": session.decoder,
        "pair": pair_annotation,
        "pull_port": session.port,
        "pulltest_login": pulltest_login,
        "pulltest_password": pulltest_password,
    }

    x = f"{pair_annotation}-sendstream.yaml"
    x = x.replace("$", "")
    path = data_dir / x
    text = tpl_sendstream.render(data=data)
    _logger.info(f"writing {path.resolve()}")
    path.write_text(text)

    x = f"{pair_annotation}-pulltest.yaml"
    x = x.replace("$", "")
    path = data_dir / x
    text = tpl_pulltest.render(data=data)
    _logger.info(f"writing {path.resolve()}")
    path.write_text(text)
