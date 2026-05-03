from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render


def health(_request):
    db_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        db_ok = False
    payload = {"status": "ok" if db_ok else "degraded", "db": "ok" if db_ok else "fail"}
    status_code = 200 if db_ok else 503
    return JsonResponse(payload, status=status_code)


def landing_placeholder(request):
    return render(request, "core/landing_placeholder.html")


def robots_txt(request):
    from django.conf import settings as django_settings

    return render(
        request,
        "robots.txt",
        {"site_url": django_settings.SITE_URL},
        content_type="text/plain",
    )
