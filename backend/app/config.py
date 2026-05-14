from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    legiscan_api_key: str
    allowed_origins: list[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, v: str | list) -> list[str]:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",")]
        return v

    @property
    def asyncpg_database_url(self) -> str:
        libpq_only = {
            "sslmode", "sslcert", "sslkey", "sslrootcert",
            "sslcrl", "sslcompression", "channel_binding",
        }
        url = self.database_url
        for prefix in ("postgresql://", "postgres://"):
            if url.startswith(prefix):
                url = "postgresql+asyncpg://" + url[len(prefix):]
                break
        parts = urlsplit(url)
        params = [(k, v) for k, v in parse_qsl(parts.query) if k not in libpq_only]
        if "ssl" not in dict(params):
            params.append(("ssl", "require"))
        return urlunsplit(parts._replace(query=urlencode(params)))

settings = Settings()
