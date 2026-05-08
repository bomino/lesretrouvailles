from django.urls import path

from . import views

app_name = "aide"

urlpatterns = [
    path("", views.aide_view, name="index"),
]
