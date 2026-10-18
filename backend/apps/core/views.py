from django.http import JsonResponse
from django.views.defaults import page_not_found, server_error


def not_found(request, exception=None):
    """JSON 404 for API paths, Django's normal page elsewhere (e.g. the admin site)."""
    if request.path.startswith("/api/"):
        return JsonResponse({"detail": "Not found."}, status=404)
    return page_not_found(request, exception)


def internal_error(request):
    if request.path.startswith("/api/"):
        return JsonResponse({"detail": "An unexpected error occurred. Please try again later."}, status=500)
    return server_error(request)
