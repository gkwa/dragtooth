import logging

from . import common

_logger = logging.getLogger(__name__)

tpl_sendstream_k8s_manifest = common.env.get_template("sendstream.yaml.j2")
tpl_pulltest_k8s_manifest = common.env.get_template("pulltest.yaml.j2")


def generate_k8s(session):
    data = common.generate_data(session)

    x = session.encoder.lower()
    y = session.decoder.lower()
    pair_annotation = f"{x}-{y}".replace("$", "")

    x = f"{pair_annotation}-sendstream.yaml"
    x = x.replace("$", "")
    path = common.data_dir / x
    text = tpl_sendstream_k8s_manifest.render(data=data)
    _logger.info(f"writing {path.resolve()}")
    path.write_text(text)

    x = f"{pair_annotation}-pulltest.yaml"
    x = x.replace("$", "")
    path = common.data_dir / x
    text = tpl_pulltest_k8s_manifest.render(data=data)
    _logger.info(f"writing {path.resolve()}")
    path.write_text(text)
