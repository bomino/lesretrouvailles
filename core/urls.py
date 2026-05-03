from django.contrib.sitemaps.views import sitemap
from django.urls import path

from . import views
from .sitemaps import PublicSurfaceSitemap

sitemaps_dict = {"public": PublicSurfaceSitemap}

urlpatterns = [
    path("", views.landing_placeholder, name="landing_placeholder"),
    path("health", views.health, name="health"),
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps_dict},
        name="django.contrib.sitemaps.views.sitemap",
    ),
]
