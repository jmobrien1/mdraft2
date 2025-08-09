import logging
import os
from typing import Optional

from markitdown import MarkItDown
from google.cloud import documentai

from models import db, Document
from gcp_utils import download_gcs_bytes, get_text_embedding, initialize_vertex


def detect_mime(extension: str) -> str:
    ext = extension.lower().lstrip(".")
    mapping = {
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "html": "text/html",
        "htm": "text/html",
        "txt": "text/plain",
        "pdf": "application/pdf",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "tiff": "image/tiff",
        "tif": "image/tiff",
    }
    return mapping.get(ext, "application/octet-stream")


def convert_with_markitdown(content: bytes | str) -> str:
    mid = MarkItDown()
    if isinstance(content, bytes):
        text = content
    else:
        text = content
    # MarkItDown auto-detects. Provide bytes or path-like; we use bytes.
    result = mid.convert(input_bytes=text)
    return result.text_content or ""


def convert_with_docai_ocr(raw_bytes: bytes, mime_type: str, processor_name: str) -> str:
    client = documentai.DocumentProcessorServiceClient()
    request = documentai.ProcessRequest(
        name=processor_name,
        raw_document=documentai.RawDocument(content=raw_bytes, mime_type=mime_type),
    )
    result = client.process_document(request=request)
    doc = result.document
    text = doc.text or ""
    # Simple Markdown: separate pages with headings if page anchors exist
    lines = ["# Document"]
    if doc.pages:
        for idx, _page in enumerate(doc.pages, start=1):
            lines.append(f"\n\n## Page {idx}\n")
        # Fallback: if pages list exists but text lacks per-page segmentation, just append at end
        lines.append(text)
    else:
        lines.append(text)
    return "\n".join(lines)


def execute_processing(document: Document) -> None:
    logging.info("Processing document id=%s status=%s", document.id, document.status)

    # Download source
    raw = download_gcs_bytes(document.gcs_input_uri)
    _, ext = os.path.splitext(document.original_filename)
    ext = ext.lstrip(".").lower()

    try:
        # Ensure Vertex is initialized for embeddings
        initialize_vertex(os.getenv("GCP_PROJECT_ID"), os.getenv("GCP_LOCATION", "us-east4"))
        if ext in {"docx", "pptx", "xlsx", "html", "htm", "txt"}:
            markdown = convert_with_markitdown(raw)
        else:
            mime_type = detect_mime(ext or "pdf")
            processor = os.getenv("DOC_AI_PROCESSOR_NAME")
            markdown = convert_with_docai_ocr(raw, mime_type, processor)

        document.markdown_output = markdown
        # Embedding
        embedding = get_text_embedding(markdown)
        document.embedding = embedding if embedding else None
        document.status = "DONE"
        db.session.add(document)
        db.session.commit()
        logging.info("Document processed id=%s status=%s", document.id, document.status)
    except Exception as exc:  # noqa: BLE001
        logging.exception("Failed processing document id=%s error=%s", document.id, exc)
        document.status = "FAILED"
        db.session.add(document)
        db.session.commit()


