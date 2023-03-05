import dataclasses


@dataclasses.dataclass
class Credentials:
    login: str
    password: str


@dataclasses.dataclass
class LightSession:
    encoder: str
    decoder: str
    port: int
