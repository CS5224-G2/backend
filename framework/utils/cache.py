from fastapi import Response


def cdn_cache(max_age: int = 1):
    """
    FastAPI dependency to set a 'Cache-Control' header for CloudFront.
    Defaults to 1 second if no max_age is provided.
    """

    async def set_cache_control_header(response: Response):
        # We enforce a minimum of 1 to align with CloudFront's CachingOptimized Minimum TTL
        effective_age = max(max_age, 1)

        response.headers["Cache-Control"] = f"public, max-age={effective_age}"

    return set_cache_control_header
