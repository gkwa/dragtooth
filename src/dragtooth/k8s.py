import dataclasses
import logging

import jinja2

from . import common

_logger = logging.getLogger(__name__)


data_dir = common.data_dir
send_pull_pairs = []


@dataclasses.dataclass
class ManifestContainer:
    manifest: str
    template: jinja2.Template


@dataclasses.dataclass
class SendPullPair:
    send: ManifestContainer
    pull: ManifestContainer


send = ManifestContainer(
    manifest="sendstream.yaml",
    template=common.env.get_template("sendstream.yaml.j2"),
)

pull = ManifestContainer(
    manifest="pulltest.yaml", template=common.env.get_template("pulltest.yaml.j2")
)

pair = SendPullPair(send, pull)

send_pull_pairs.append(pair)


send = ManifestContainer(
    manifest="sendstream2.yaml",
    template=common.env.get_template("sendstream2.yaml.j2"),
)

pull = ManifestContainer(
    manifest="pulltest2.yaml", template=common.env.get_template("pulltest2.yaml.j2")
)

pair = SendPullPair(send, pull)

send_pull_pairs.append(pair)


def delete_old_manifests():
    _logger.debug(f"{data_dir=}")


def generate_manifest(session, container, directory):
    data = common.generate_data(session)

    x = session.encoder.lower()
    y = session.decoder.lower()
    pair_annotation = f"{x}-{y}".replace("$", "")

    x = f"{pair_annotation}-{container.manifest}"

    x = x.replace("$", "")

    path = directory / x
    text = container.template.render(data=data)
    _logger.info(f"writing {path.resolve()}")

    path.parent.mkdir(exist_ok=True, parents=True)
    path.write_text(text)


def generate_k8s(session):
    delete_old_manifests()

    for index, pair in enumerate(send_pull_pairs, 1):
        x = f"k8s-{str(session.encoder).replace('$', '')}-{index}"
        _dir = data_dir / x
        generate_manifest(session, pair.send, directory=_dir)
        generate_manifest(session, pair.pull, directory=_dir)
