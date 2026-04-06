"""
Async HTTP clients for outbound calls.

There are 2 client types:

ServiceClient — internal microservices
    Resolves service names to base URLs from settings.SERVICE_URLS.

ExternalClient — external APIs (e.g. NEA)
    Instantiated with a fixed base URL and optional auth headers.

"""

import httpx
from ..config import settings

# Default timeout for all outbound calls (seconds)
_DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)


class ServiceClient:
    """
    Calls internal microservices. Mainly for our bike_cli routing service.
    """

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT)

    def _base_url(self, service_name: str) -> str:
        url = settings.SERVICE_URLS.get(service_name)
        if not url:
            raise ValueError(
                f"No URL configured for service '{service_name}'. "
                f"Add it to SERVICE_URLS in your .env."
            )
        return url.rstrip("/")

    async def get(self, service: str, path: str, **kwargs) -> httpx.Response:
        return await self._client.get(f"{self._base_url(service)}{path}", **kwargs)

    async def post(self, service: str, path: str, **kwargs) -> httpx.Response:
        return await self._client.post(f"{self._base_url(service)}{path}", **kwargs)

    async def aclose(self) -> None:
        await self._client.aclose()


class ExternalClient:
    """
    Reusable async HTTP client for external APIs. 
    Each external API should have its own ExternalClient instance whose lifecycle
    is registered in the FastAPI lifespan (main.py).

    Example:
        nea_client = ExternalClient(
            base_url=settings.NEA_BASE_URL,
            headers={"Authorization": f"Bearer {settings.NEA_API_KEY}"},
        )
    """

    def __init__(
        self,
        base_url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout = _DEFAULT_TIMEOUT,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers=headers or {},
            timeout=timeout,
        )

    async def get(self, path: str, **kwargs) -> httpx.Response:
        return await self._client.get(path, **kwargs)

    async def post(self, path: str, **kwargs) -> httpx.Response:
        return await self._client.post(path, **kwargs)

    async def aclose(self) -> None:
        await self._client.aclose()


# Singleton for internal calls — import this wherever needed
service_client = ServiceClient()

# Singleton for SendGrid email delivery
sendgrid_client = ExternalClient(
    base_url="https://api.sendgrid.com",
    headers={
        "Authorization": f"Bearer {settings.SENDGRID_API_KEY}",
        "Content-Type": "application/json",
    },
)
