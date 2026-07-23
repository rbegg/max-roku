from dataclasses import dataclass

@dataclass
class AppTestConfig:
    app_id: str
    app_name: str
    content_id: str
    content_type: str