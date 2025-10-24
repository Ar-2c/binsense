# core/storage.py
from __future__ import annotations

from dotenv import load_dotenv, find_dotenv
import io, os, uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from PIL import Image
from azure.storage.blob import BlobServiceClient, BlobSasPermissions, generate_blob_sas

load_dotenv(find_dotenv())

_CFG: tuple[str, str] | None = None
_bsc: BlobServiceClient | None = None

def _get_cfg() -> tuple[str, str]:
    """Läs konfig från env eller streamlit secrets, cacha resultatet."""
    global _CFG
    if _CFG is not None:
        return _CFG

    conn = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    container = os.getenv("AZURE_BLOB_CONTAINER", "images")

    if not conn:
        try:
            import streamlit as st  # type: ignore
            conn = st.secrets.get("AZURE_STORAGE_CONNECTION_STRING") or conn
            container = st.secrets.get("AZURE_BLOB_CONTAINER", container)
        except Exception:
            pass

    if not conn:
        raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING saknas. Sätt den i .env eller Streamlit secrets.")

    _CFG = (conn, container)
    return _CFG

def _get_bsc() -> BlobServiceClient:
    global _bsc
    if _bsc is None:
        conn, _ = _get_cfg()
        _bsc = BlobServiceClient.from_connection_string(conn)
    return _bsc

def _ensure_container():
    _, container = _get_cfg()
    cc = _get_bsc().get_container_client(container)
    try:
        cc.create_container()
    except Exception:
        pass
    return cc

def _make_sas_for_blob(bc, hours: int) -> str:
    expiry = datetime.now(timezone.utc) + timedelta(hours=hours)
    sas = generate_blob_sas(
        account_name=bc.account_name,
        container_name=bc.container_name,
        blob_name=bc.blob_name,
        permission=BlobSasPermissions(read=True),
        expiry=expiry,
        account_key=_get_bsc().credential.account_key if hasattr(_get_bsc().credential, "account_key") else None,
    )
    return f"{bc.url}?{sas}" if sas else bc.url

# Publikt API
def save_image_bytes(site_id: str, data: bytes, original_name: str = "image.jpg") -> Tuple[str, str]:
    suffix = ("." + original_name.split(".")[-1].lower().strip(".")) if "." in original_name else ".jpg"
    content_type = "image/jpeg" if suffix in (".jpg", ".jpeg") else ("image/png" if suffix == ".png" else "application/octet-stream")
    ts = int(datetime.now(timezone.utc).timestamp())
    key = f"{site_id}/{datetime.now(timezone.utc):%Y/%m/%d}/{ts}_{uuid.uuid4().hex}{suffix}"

    cc = _ensure_container()
    bc = cc.get_blob_client(key)
    bc.upload_blob(data, overwrite=True, content_type=content_type)

    image_uri = bc.url
    sas_url = _make_sas_for_blob(bc, hours=1)
    return image_uri, sas_url

# definition av återkommande funktioner för Azure
def sas_url_for(image_uri: str, hours: int = 1) -> str:
    if "blob.core.windows.net" not in image_uri:
        return image_uri
    parts = image_uri.split("/")
    container = parts[3]
    blob_name = "/".join(parts[4:])
    bc = _get_bsc().get_blob_client(container=container, blob=blob_name)
    return _make_sas_for_blob(bc, hours=hours)

def load_image_from_uri(uri: str) -> Optional[Image.Image]:
    try:
        if not uri.lower().startswith("http"):
            return None
        import requests
        r = requests.get(uri, timeout=10)
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGB")
    except Exception:
        return None

def _make_sas_for_blob(bc, hours: int) -> str:
    expiry = datetime.now(timezone.utc) + timedelta(hours=hours)
    sas = generate_blob_sas(
        account_name=bc.account_name,
        container_name=bc.container_name,
        blob_name=bc.blob_name,
        permission=BlobSasPermissions(read=True),
        expiry=expiry,
        account_key=_get_bsc().credential.account_key if hasattr(_get_bsc().credential, "account_key") else None,
    )
    return f"{bc.url}?{sas}" if sas else bc.url

def delete_site_blobs(site_id: str, container: str | None = None) -> int:
    """
    Tar bort alla blobbar under prefixet '<site_id>/'.
    Returnerar antal borttagna blobbar.
    """
    cc = _ensure_container()
    prefix = f"{site_id}/"
    deleted = 0
    for blob in cc.list_blobs(name_starts_with=prefix):
        try:
            cc.delete_blob(blob.name)
            deleted += 1
        except Exception:
            pass
    return deleted
