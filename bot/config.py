from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    bot_token: str
    developer_handle: str = "developer"
    channel_id: str = "@BerlinFlatsAll"
    database_url: str = "sqlite+aiosqlite:///./berlin_flats.db"
    scrape_interval_minutes: int = 10
    log_level: str = "INFO"
    # How long (hours) an editable /search message stays active
    search_message_ttl_hours: int = 48
    # ScrapFly API key — enables IS24 scraping by bypassing Cloudflare (optional)
    scrapfly_key: str = ""


settings = Settings()
