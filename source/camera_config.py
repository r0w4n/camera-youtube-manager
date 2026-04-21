from dataclasses import dataclass, field


REQUIRED_CAMERA_FIELDS = ("name", "title", "url", "key")


@dataclass(frozen=True)
class CameraConfig:
    name: str
    title: str = ""
    description: str = ""
    enabled: bool = True
    url: str = ""
    key: str = ""

    @classmethod
    def from_dict(cls, data):
        missing_fields = [
            field_name
            for field_name in REQUIRED_CAMERA_FIELDS
            if not str(data.get(field_name, "")).strip()
        ]
        if missing_fields:
            missing_fields_text = ", ".join(missing_fields)
            raise ValueError(
                f"Camera configuration is missing required field(s): "
                f"{missing_fields_text}"
            )

        return cls(
            name=data["name"],
            title=data["title"],
            description=data.get("description", ""),
            enabled=data.get("enabled", True),
            url=data["url"],
            key=data["key"],
        )


@dataclass(frozen=True)
class AppSettings:
    cameras: list[CameraConfig] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data):
        cameras = data.get("cameras", [])
        if not isinstance(cameras, list):
            raise ValueError("Settings field 'cameras' must be a list")

        return cls(
            cameras=[CameraConfig.from_dict(camera) for camera in cameras]
        )
