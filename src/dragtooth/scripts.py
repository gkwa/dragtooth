import dataclasses
import logging

import jinja2

from . import common

_logger = logging.getLogger(__name__)


@dataclasses.dataclass
class ScriptContainer:
    script: str
    template: jinja2.Template


scripts = [
    ScriptContainer(
        script="sendstream.sh", template=common.env.get_template("sendstream.sh.j2")
    ),
    ScriptContainer(
        script="pulltest.sh", template=common.env.get_template("pulltest.sh.j2")
    ),
]


def generate_scripts(session):
    for container in scripts:
        generate_script(session, container)


def generate_script(session, container):
    data = common.generate_data(session)

    path = common.data_dir / container.script
    text = container.template.render(data=data)
    _logger.info(f"writing {path.resolve()}")
    path.write_text(text)
