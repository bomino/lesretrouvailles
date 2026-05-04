from django.urls import path

from . import views

app_name = "memoriam"

urlpatterns = [
    path("in-memoriam/", views.list_view, name="list"),
    path("in-memoriam/<int:pk>/", views.detail_view, name="detail"),
    path("in-memoriam/nominer/", views.nominate_view, name="nominate"),
    path("in-memoriam/nominer/merci/", views.nominate_thanks_view, name="nominate_thanks"),
]
