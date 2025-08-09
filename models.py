import uuid
from datetime import datetime
from typing import Any

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import event
from pgvector.sqlalchemy import Vector


db = SQLAlchemy()


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    original_filename = db.Column(db.String(512), nullable=False)
    gcs_input_uri = db.Column(db.String(1024), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="PENDING")
    markdown_output = db.Column(db.Text, nullable=True)
    embedding = db.Column(Vector(768), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


@event.listens_for(Document, "before_insert")
def before_insert(mapper: Any, connection: Any, target: "Document") -> None:  # noqa: ANN001
    if target.status is None:
        target.status = "PENDING"
    now = datetime.utcnow()
    target.created_at = now
    target.updated_at = now


@event.listens_for(Document, "before_update")
def before_update(mapper: Any, connection: Any, target: "Document") -> None:  # noqa: ANN001
    target.updated_at = datetime.utcnow()


