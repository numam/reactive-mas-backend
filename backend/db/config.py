import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DatabaseSettings:
    host: str = os.getenv("DB_HOST", "127.0.0.1")
    port: int = int(os.getenv("DB_PORT", "3306"))
    user: str = os.getenv("DB_USER", "root")
    password: str = os.getenv("DB_PASSWORD", "")
    name: str = os.getenv("DB_NAME", "supply")

    @property
    def url(self) -> str:
        from urllib.parse import quote_plus

        password = quote_plus(self.password)
        return f"mysql+pymysql://{self.user}:{password}@{self.host}:{self.port}/{self.name}?charset=utf8mb4"


settings = DatabaseSettings()
