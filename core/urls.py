from django.contrib.sitemaps.views import sitemap
from django.urls import path

from . import views
from .sitemaps import PublicSurfaceSitemap

sitemaps_dict = {"public": PublicSurfaceSitemap}

urlpatterns = [
    path("", views.landing_view, name="landing"),
    path("health", views.health, name="health"),
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps_dict},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    path("robots.txt", views.robots_txt, name="robots_txt"),
]
