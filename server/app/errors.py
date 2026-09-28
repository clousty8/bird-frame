"""Format d'erreur unique du contrat (§1.8) : {"error", "message", "details"} sur tout 4xx/5xx.

`ApiError` est l'exception que tout le code applicatif DOIT lever pour signaler une erreur
métier — jamais `fastapi.HTTPException` directement, pour que le corps de réponse reste
toujours conforme au contrat (catalogue de codes `error` en §1.8).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("bird_frame.errors")


class ApiError(Exception):
    """Erreur métier avec code HTTP + code machine stable, conforme au contrat §1.8."""

    def __init__(
        self,
        status_code: int,
        error: str,
        message: str,
        details: object | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error = error
        self.message = message
        self.details = details
        self.headers = headers

    def to_response(self) -> JSONResponse:
        return JSONResponse(
            status_code=self.status_code,
            content={"error": self.error, "message": self.message, "details": self.details},
            headers=self.headers,
        )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return exc.to_response()

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation_error",
                "message": "Requête invalide : voir « details » pour le détail des champs.",
                "details": jsonable_encoder(exc.errors()),
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        # Remplace le format par défaut de Starlette ({"detail": ...}) par le nôtre,
        # y compris pour les 404 de route inconnue et les 405 (contrat §1.8).
        if exc.status_code == 404:
            error, message = "not_found", "Route inconnue."
        elif exc.status_code == 405:
            error, message = "method_not_allowed", "Méthode non autorisée sur cette route."
        else:
            error, message = "http_error", str(exc.detail) if exc.detail else "Erreur."
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": error, "message": message, "details": None},
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Aucune défaillance avalée en silence : toute exception non prévue est journalisée
        # avec sa trace complète avant de répondre 500 au client.
        logger.exception("Erreur interne non gérée sur %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "message": "Erreur interne du serveur.",
                "details": None,
            },
        )
