"""WP-11 : cycle CSRF contre un faux serveur HTTP local simulant BirdNET-Go.

Le point important, propre à ce lot (voir node/bridge/csrf_client.py) : le jeton envoyé dans
`X-CSRF-Token` est la valeur du **cookie** `csrf`, pas le champ JSON `csrfToken` du corps — les
deux diffèrent volontairement dans ces tests pour vérifier lequel est réellement utilisé.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from bridge.csrf_client import CsrfClient, CsrfError

NODE_API = "http://localhost:8080"


@pytest.mark.asyncio
async def test_get_request_needs_no_csrf_token() -> None:
    async with httpx.AsyncClient() as client, respx.mock(base_url=NODE_API) as mock:
        route = mock.get("/api/v2/health").mock(return_value=httpx.Response(200, json={"status": "ok"}))
        csrf = CsrfClient(client, NODE_API)
        response = await csrf.request("GET", "/api/v2/health")
        assert response.status_code == 200
        assert route.calls.last.request.headers.get("X-CSRF-Token") is None


@pytest.mark.asyncio
async def test_mutating_request_uses_cookie_value_not_json_field() -> None:
    async with httpx.AsyncClient() as client, respx.mock(base_url=NODE_API) as mock:
        mock.get("/api/v2/app/config").mock(
            return_value=httpx.Response(
                200,
                json={"csrfToken": "json-field-value-should-NOT-be-used"},
                headers={"Set-Cookie": "csrf=cookie-value-must-be-used; Path=/"},
            )
        )
        mutate_route = mock.post("/api/v2/settings/species").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )

        csrf = CsrfClient(client, NODE_API)
        response = await csrf.request("POST", "/api/v2/settings/species", json_body={"exclude": []})

        assert response.status_code == 200
        sent_headers = mutate_route.calls.last.request.headers
        assert sent_headers["X-CSRF-Token"] == "cookie-value-must-be-used"
        assert "csrf=cookie-value-must-be-used" in sent_headers.get("cookie", "")


@pytest.mark.asyncio
async def test_403_refreshes_token_and_retries_once() -> None:
    async with httpx.AsyncClient() as client, respx.mock(base_url=NODE_API) as mock:
        config_calls = {"count": 0}

        def config_response(request: httpx.Request) -> httpx.Response:
            config_calls["count"] += 1
            cookie_value = f"token-{config_calls['count']}"
            return httpx.Response(
                200, json={"csrfToken": "unused"}, headers={"Set-Cookie": f"csrf={cookie_value}; Path=/"}
            )

        mock.get("/api/v2/app/config").mock(side_effect=config_response)

        post_calls = {"count": 0}

        def post_response(request: httpx.Request) -> httpx.Response:
            post_calls["count"] += 1
            if post_calls["count"] == 1:
                return httpx.Response(403, json={"error": "csrf mismatch"})
            return httpx.Response(200, json={"ok": True})

        mock.post("/api/v2/settings/species").mock(side_effect=post_response)

        csrf = CsrfClient(client, NODE_API)
        response = await csrf.request("POST", "/api/v2/settings/species", json_body={})

        assert response.status_code == 200
        assert config_calls["count"] == 2  # une fois au départ, une fois après le 403
        assert post_calls["count"] == 2  # échec puis réessai réussi


@pytest.mark.asyncio
async def test_missing_cookie_raises_clear_error() -> None:
    async with httpx.AsyncClient() as client, respx.mock(base_url=NODE_API) as mock:
        mock.get("/api/v2/app/config").mock(return_value=httpx.Response(200, json={"csrfToken": "x"}))
        csrf = CsrfClient(client, NODE_API)
        with pytest.raises(CsrfError):
            await csrf.request("POST", "/api/v2/settings/species", json_body={})


@pytest.mark.asyncio
async def test_bearer_token_added_when_configured() -> None:
    async with httpx.AsyncClient() as client, respx.mock(base_url=NODE_API) as mock:
        route = mock.get("/api/v2/health").mock(return_value=httpx.Response(200, json={}))
        csrf = CsrfClient(client, NODE_API, bearer_token="s3cr3t")
        await csrf.request("GET", "/api/v2/health")
        assert route.calls.last.request.headers["Authorization"] == "Bearer s3cr3t"
