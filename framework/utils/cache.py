from fastapi import Response

def cdn_cache(max_age: int):
    """
    FastAPI dependency to set a 'Cache-Control' header for CloudFront.
    """
    async def set_cache_control_header(response: Response):
        if max_age == 0:
            response.headers["Cache-Control"] = "public, no-cache, no-store, must-revalidate, max-age=0"
        else:
            response.headers["Cache-Control"] = f"public, max-age={max_age}"
    return set_cache_control_header
