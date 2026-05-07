from django.urls import path

from . import views

app_name = "gestion"

urlpatterns = [
    path("", views.dashboard_view, name="dashboard"),
    path("membres/", views.member_list_view, name="member_list"),
    path("membres/<uuid:slug>/", views.member_detail_view, name="member_detail"),
    path(
        "membres/<uuid:slug>/modifier/",
        views.member_edit_view,
        name="member_edit",
    ),
    path(
        "membres/<uuid:slug>/statut/",
        views.member_status_view,
        name="member_status",
    ),
    path(
        "membres/<uuid:slug>/identifiant/",
        views.member_username_view,
        name="member_username",
    ),
    path(
        "membres/<uuid:slug>/lien/",
        views.member_login_link_view,
        name="member_login_link",
    ),
]
