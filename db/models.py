from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import UniqueConstraint, PrimaryKeyConstraint


class User(SQLModel, table=True):
    __tablename__ = "users"

    telegram_id: int = Field(primary_key=True)
    username: Optional[str] = None
    cv_text: Optional[str] = None
    profile_json: Optional[str] = None
    search_interval_hours: int = Field(default=24)
    is_searching: bool = Field(default=False)
    last_searched_at: Optional[datetime] = None
    last_cv_uploaded_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SeenJob(SQLModel, table=True):
    __tablename__ = "seen_jobs"
    __table_args__ = (UniqueConstraint("telegram_id", "job_hash", name="uq_user_job"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_id: int = Field(foreign_key="users.telegram_id")
    job_hash: str
    job_url: str
    job_title: str
    company: str
    score: int
    score_reason: str
    notified_at: datetime = Field(default_factory=datetime.utcnow)


class ScrapeCache(SQLModel, table=True):
    __tablename__ = "scrape_cache"
    __table_args__ = (
        PrimaryKeyConstraint("telegram_id", "site", "query_key"),
    )

    telegram_id: int = Field(foreign_key="users.telegram_id", sa_column_kwargs={"primary_key": True})
    site: str = Field(sa_column_kwargs={"primary_key": True})
    query_key: str = Field(sa_column_kwargs={"primary_key": True})
    last_scraped_at: datetime = Field(default_factory=datetime.utcnow)
