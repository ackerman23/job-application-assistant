from datetime import datetime
from sqlalchemy import create_engine, String, Text, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from app.core.config import DATABASE_URL


class Base(DeclarativeBase):
    pass


class Application(Base):
    __tablename__ = "applications"
    id: Mapped[int] = mapped_column(primary_key=True)
    company: Mapped[str] = mapped_column(String(200), default="")
    position: Mapped[str] = mapped_column(String(300), default="")
    date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    match_summary: Mapped[str] = mapped_column(Text, default="")
    cv_path: Mapped[str] = mapped_column(String(1000), default="")
    cover_letter_path: Mapped[str] = mapped_column(String(1000), default="")
    job_description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")


engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base.metadata.create_all(engine)
