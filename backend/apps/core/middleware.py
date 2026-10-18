class SecurityHeadersMiddleware:
    """Adds headers Django does not set by default. The API only returns JSON."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if request.path.startswith("/api/") and not request.path.startswith(("/api/v1/docs", "/api/v1/redoc")):
            response.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
            response.setdefault("Cache-Control", "no-store")
        return response
