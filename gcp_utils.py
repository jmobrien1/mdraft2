import base64
import json
import logging
import os
from typing import Dict, List

from google.cloud import storage
from google.cloud import tasks_v2
from google.oauth2 import service_account  # not used; rely on ADC
from google.cloud import aiplatform
from google.api_core.retry import Retry


def upload_to_gcs(file_stream, bucket_name: str, key: str, content_type: str) -> str:
    client = storage.Client()  # ADC
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(key)
    blob.upload_from_file(file_stream, content_type=content_type)
    logging.info("Uploaded to GCS: gs://%s/%s", bucket_name, key)
    return f"gs://{bucket_name}/{key}"


def download_gcs_bytes(gcs_uri: str) -> bytes:
    if not gcs_uri.startswith("gs://"):
        raise ValueError("gcs_uri must start with gs://")
    _, path = gcs_uri.split("gs://", 1)
    bucket_name, key = path.split("/", 1)
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(key)
    data = blob.download_as_bytes()
    logging.info("Downloaded from GCS: %s bytes=%d", gcs_uri, len(data))
    return data


def create_http_task(
    project_id: str,
    location: str,
    queue: str,
    url: str,
    payload: Dict,
) -> str:
    client = tasks_v2.CloudTasksClient()
    parent = client.queue_path(project_id, location, queue)

    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": url,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(payload).encode(),
        }
    }

    response = client.create_task(request={"parent": parent, "task": task})
    logging.info("Created Cloud Task: %s", response.name)
    return response.name


def initialize_vertex(project_id: str, location: str) -> None:
    # Initialize only once; safe to call multiple times
    aiplatform.init(project=project_id, location=location)


def get_text_embedding(text: str) -> List[float]:
    # Vertex AI Embeddings for Text (textembedding-gecko@003)
    embed_model = aiplatform.TextEmbeddingModel.from_pretrained(
        "textembedding-gecko@003"
    )
    result = embed_model.get_embeddings([text])
    if not result or not result[0].values:
        return []
    vector = list(result[0].values)
    return vector


