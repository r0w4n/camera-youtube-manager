from dataclasses import dataclass, field


@dataclass(frozen=True)
class CameraConfig:
    name: str
    title: str = ""
    description: str = ""
    enabled: bool = True
    url: str = ""
    key: str = ""


@dataclass(frozen=True)
class AppSettings:
    cameras: list[CameraConfig] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data):
        return cls(
            cameras=[CameraConfig(**camera) for camera in data.get("cameras", [])]
        )
