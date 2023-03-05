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

    def __post_init__(self):
        if not self.encoder:
            raise ValueError("encoder session id should not be empty")

        if not self.decoder:
            raise ValueError("decoder session id should not be empty")
