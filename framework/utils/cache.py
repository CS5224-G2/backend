from fastapi import Response

def cdn_cache(max_age: int):
    """
    FastAPI dependency to set a 'Cache-Control' header for CloudFront.
    """
    async def set_cache_control_header(response: Response):
        response.headers["Cache-Control"] = f"public, max-age={max_age}"
    return set_cache_control_header
