"""`GET /recordings/{kept_clip_id}/audio` et `/spectrogram` — contrat §6.13.

L'audio exige une session (les enregistrements peuvent contenir des voix privées,
contrat §2.2) ; le spectrogramme reste public.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.browser_auth import require_browser_session
from app.deps import get_db
from app.errors import ApiError
from app.models.kept_clip import KeptClip

router = APIRouter(tags=["recordings"])

_AUDIO_CONTENT_TYPES = {
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".aac": "audio/mp4",
    ".opus": "audio/ogg",
    ".ogg": "audio/ogg",
}


def _lookup_kept_clip_or_404(db: Session, kept_clip_id: int, error_code: str, message: str) -> KeptClip:
    kc = db.get(KeptClip, kept_clip_id)
    if kc is None or kc.evicted_at is not None or kc.missing:
        raise ApiError(404, error_code, message)
    return kc


@router.get("/recordings/{kept_clip_id}/audio", dependencies=[Depends(require_browser_session)])
def get_recording_audio(kept_clip_id: int, request: Request, db: Session = Depends(get_db)) -> Response:
    kc = _lookup_kept_clip_or_404(db, kept_clip_id, "recording_not_found", "Enregistrement introuvable.")
    if kc.audio_path is None or not Path(kc.audio_path).is_file():
        raise ApiError(404, "recording_not_found", "Enregistrement introuvable.")
    path = Path(kc.audio_path)
    content_type = _AUDIO_CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")
    # `private` : réponse soumise à session, jamais mise en cache par un proxy partagé.
    return _serve_with_range(path, request, content_type, "private, max-age=31536000, immutable")


@router.get("/recordings/{kept_clip_id}/spectrogram")
def get_recording_spectrogram(kept_clip_id: int, db: Session = Depends(get_db)) -> Response:
    kc = _lookup_kept_clip_or_404(db, kept_clip_id, "spectrogram_not_found", "Spectrogramme introuvable.")
    if kc.spectrogram_path is None or not Path(kc.spectrogram_path).is_file():
        raise ApiError(404, "spectrogram_not_found", "Spectrogramme introuvable.")
    content = Path(kc.spectrogram_path).read_bytes()
    return Response(
        content=content,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


def _serve_with_range(path: Path, request: Request, content_type: str, cache_control: str) -> Response:
    file_size = path.stat().st_size
    range_header = request.headers.get("range")

    if range_header is None:
        return Response(
            content=path.read_bytes(),
            media_type=content_type,
            headers={
                "Accept-Ranges": "bytes",
                "Cache-Control": cache_control,
                "Content-Length": str(file_size),
            },
        )

    try:
        start, end = _parse_range(range_header, file_size)
    except ValueError as exc:
        raise ApiError(
            416,
            "range_not_satisfiable",
            "Plage demandée hors bornes.",
            details=str(exc),
            headers={"Content-Range": f"bytes */{file_size}", "Accept-Ranges": "bytes"},
        ) from exc

    with path.open("rb") as f:
        f.seek(start)
        chunk = f.read(end - start + 1)

    return Response(
        content=chunk,
        status_code=206,
        media_type=content_type,
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": cache_control,
            "Content-Length": str(len(chunk)),
            "Content-Range": f"bytes {start}-{end}/{file_size}",
        },
    )


def _parse_range(range_header: str, file_size: int) -> tuple[int, int]:
    """`bytes=a-b`, `bytes=a-` ou `bytes=-n` — une seule plage (contrat §6.13)."""
    if not range_header.startswith("bytes="):
        raise ValueError("unité de plage non supportée")
    spec = range_header[len("bytes=") :]
    if "," in spec:
        raise ValueError("une seule plage supportée")

    start_str, _, end_str = spec.partition("-")
    if start_str == "" and end_str == "":
        raise ValueError("plage vide")

    if start_str == "":
        suffix_len = int(end_str)
        if suffix_len <= 0:
            raise ValueError("suffixe invalide")
        start = max(0, file_size - suffix_len)
        end = file_size - 1
    else:
        start = int(start_str)
        end = int(end_str) if end_str != "" else file_size - 1

    if start < 0 or start >= file_size or start > end:
        raise ValueError("plage hors bornes")

    return start, min(end, file_size - 1)
