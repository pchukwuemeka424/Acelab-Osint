from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Acelab OSINT"
    environment: str = "development"
    debug: bool = False
    secret_key: str = "dev-only-change-me"
    database_url: str = "sqlite:///./piae.db"
    redis_url: str = ""
    neo4j_uri: str = ""
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    investigation_eager: bool = True
    auto_create: bool = True
    seed_on_startup: bool = True
    analyst_email: str = "analyst@piae.test"
    analyst_password: str = "changeme-dev-only"
    analyst_display_name: str = "analyst"
    admin_email: str = "admin@piae.test"
    admin_password: str = "changeme-admin-dev-only"
    admin_display_name: str = "admin"
    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4o-mini"
    openrouter_referer: str = "http://localhost"
    demo_mode: bool = False
    urlhaus_enabled: bool = False
    dns_enabled: bool = True
    rdap_enabled: bool = True
    ct_enabled: bool = True
    ripe_enabled: bool = True
    wayback_enabled: bool = True
    page_enabled: bool = True
    profiles_enabled: bool = True
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    session_ttl_seconds: int = 60 * 60 * 12
    log_level: str = "INFO"
    graph_expand_limit: int = 25
    graph_node_cap: int = 1500

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
