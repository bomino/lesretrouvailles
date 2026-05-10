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
    path(
        "cooptations/",
        views.application_list_view,
        name="application_list",
    ),
    path(
        "cooptations/<int:pk>/",
        views.application_detail_view,
        name="application_detail",
    ),
    path(
        "cooptations/<int:pk>/approuver/",
        views.application_approve_view,
        name="application_approve",
    ),
    path(
        "cooptations/<int:pk>/rejeter/",
        views.application_reject_view,
        name="application_reject",
    ),
    path(
        "souvenirs/",
        views.memory_list_view,
        name="memory_list",
    ),
    path(
        "souvenirs/nouveau/",
        views.memory_create_view,
        name="memory_create",
    ),
    path(
        "souvenirs/<int:pk>/modifier/",
        views.memory_edit_view,
        name="memory_edit",
    ),
    path(
        "souvenirs/<int:pk>/statut/",
        views.memory_status_view,
        name="memory_status",
    ),
]
