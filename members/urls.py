from django.urls import path

from . import views

app_name = "members"

urlpatterns = [
    path("charte/", views.charter_view, name="charter"),
]
