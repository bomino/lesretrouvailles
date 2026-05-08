from django.contrib import admin
from django.urls import include, path

from aide import views as aide_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("gestion/", include("gestion.urls")),
    path("", include("cooptation.urls")),
    path("", include("memoires.urls")),
    path("", include("memoriam.urls")),
    path("", include("members.urls")),
    path("aide/", include("aide.urls")),
    path("guide/", aide_views.guide_view, name="member_guide"),
    path("", include("core.urls")),
]
