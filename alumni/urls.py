from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("gestion/", include("gestion.urls")),
    path("", include("cooptation.urls")),
    path("", include("memoires.urls")),
    path("", include("memoriam.urls")),
    path("", include("members.urls")),
    path("", include("core.urls")),
]
