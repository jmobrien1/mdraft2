import json
import logging
import os
import uuid
from typing import Any, Dict

from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

from models import db, Document
from gcp_utils import upload_to_gcs, create_http_task, initialize_vertex
from processors import execute_processing


api_bp = Blueprint("api", __name__)


@api_bp.route("/health", methods=["GET"])
def health() -> Any:
    return jsonify({"ok": True})


@api_bp.route("/upload", methods=["POST"])
def upload() -> Any:
    if "file" not in request.files:
        return jsonify({"error": "file is required"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "empty filename"}), 400

    original_filename = secure_filename(file.filename)
    document_id = uuid.uuid4()
    key = f"input/{document_id}/{original_filename}"

    bucket_name = os.getenv("GCS_BUCKET_NAME")
    if not bucket_name:
        return jsonify({"error": "GCS_BUCKET_NAME is not set"}), 500

    gcs_uri = upload_to_gcs(
        file_stream=file.stream,
        bucket_name=bucket_name,
        key=key,
        content_type=file.content_type or "application/octet-stream",
    )

    # Create DB row with QUEUED status
    document = Document(
        id=document_id,
        original_filename=original_filename,
        gcs_input_uri=gcs_uri,
        status="QUEUED",
    )
    db.session.add(document)
    db.session.commit()

    # Initialize Vertex upfront (safe to call multiple times)
    initialize_vertex(os.getenv("GCP_PROJECT_ID"), os.getenv("GCP_LOCATION", "us-east4"))

    # Enqueue Cloud Task
    project_id = os.getenv("GCP_PROJECT_ID")
    tasks_location = os.getenv("CLOUD_TASKS_LOCATION", "us-central1")
    queue_name = os.getenv("CLOUD_TASKS_QUEUE_NAME")
    host_url = os.getenv("HOST_URL", "http://localhost:8080")
    task_url = f"{host_url}/api/tasks/process"
    create_http_task(project_id, tasks_location, queue_name, task_url, {"document_id": str(document_id)})

    return jsonify({"id": str(document_id), "status": document.status})


@api_bp.route("/tasks/process", methods=["POST"])
def tasks_process() -> Any:
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    document_id = data.get("document_id")
    if not document_id:
        return jsonify({"error": "document_id is required"}), 400

    document = db.session.get(Document, uuid.UUID(document_id))
    if not document:
        return jsonify({"error": "document not found"}), 404

    document.status = "PROCESSING"
    db.session.add(document)
    db.session.commit()

    execute_processing(document)

    return jsonify({"id": str(document.id), "status": document.status})


@api_bp.route("/documents/<doc_id>", methods=["GET"])
def get_document(doc_id: str) -> Any:
    try:
        doc_uuid = uuid.UUID(doc_id)
    except Exception:
        return jsonify({"error": "invalid id"}), 400

    document = db.session.get(Document, doc_uuid)
    if not document:
        return jsonify({"error": "not found"}), 404

    resp = {
        "id": str(document.id),
        "status": document.status,
        "original_filename": document.original_filename,
    }
    if document.status == "DONE":
        resp["markdown_output"] = document.markdown_output
    return jsonify(resp)


