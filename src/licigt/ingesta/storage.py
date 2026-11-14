"""Almacenamiento de originales con claves únicas por documento y versión."""

from __future__ import annotations

import os
from pathlib import Path


class LocalOriginalStore:
    """Adaptador local para desarrollo; crea archivos sin sobrescribirlos."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def put(self, source: Path, key: str) -> str:
        target = self.root / key
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with source.open("rb") as input_file, target.open("xb") as output_file:
            while block := input_file.read(1024 * 1024):
                output_file.write(block)
        target.chmod(0o600)
        return f"file://{target.resolve()}"


class MinioOriginalStore:
    """Adaptador MinIO; exige bucket precreado y versionado habilitado."""

    def __init__(self, endpoint: str, bucket: str, access_key: str, secret_key: str, secure: bool = True):
        try:
            from minio import Minio
        except ImportError as exc:
            raise RuntimeError("Instala la dependencia opcional: pip install minio") from exc
        self.client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
        self.bucket = bucket
        if not self.client.bucket_exists(bucket_name=bucket):
            raise ValueError(f"El bucket {bucket!r} no existe")
        if self.client.get_bucket_versioning(bucket_name=bucket).status != "Enabled":
            raise ValueError(f"El bucket {bucket!r} debe tener versionado habilitado")

    def put(self, source: Path, key: str) -> str:
        # La clave incluye un UUID nuevo. Nunca se reutiliza para otra versión.
        result = self.client.fput_object(
            bucket_name=self.bucket,
            object_name=key,
            file_path=str(source),
            content_type="application/pdf",
        )
        return f"s3://{self.bucket}/{key}?versionId={result.version_id}"


def store_from_environment(data_dir: Path):
    endpoint = os.getenv("LICIGT_MINIO_ENDPOINT")
    if not endpoint:
        return LocalOriginalStore(data_dir / "originales")
    required = {name: os.getenv(name) for name in ("LICIGT_MINIO_BUCKET", "LICIGT_MINIO_ACCESS_KEY", "LICIGT_MINIO_SECRET_KEY")}
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError("Faltan variables MinIO: " + ", ".join(missing))
    return MinioOriginalStore(
        endpoint=endpoint,
        bucket=required["LICIGT_MINIO_BUCKET"],
        access_key=required["LICIGT_MINIO_ACCESS_KEY"],
        secret_key=required["LICIGT_MINIO_SECRET_KEY"],
        secure=os.getenv("LICIGT_MINIO_SECURE", "true").lower() == "true",
    )
