from django.urls import path

from . import views

urlpatterns = [
    path("", views.landing_placeholder, name="landing_placeholder"),
    path("health", views.health, name="health"),
]
