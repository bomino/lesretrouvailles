from django.urls import path

from . import views

app_name = "members"

urlpatterns = [
    path("charte/", views.charter_view, name="charter"),
    path("membres/<uuid:slug>/", views.profile_detail_view, name="profile_detail"),
    path("profil/", views.profile_edit_view, name="profile_edit"),
    path("api/cloudinary/sign/", views.cloudinary_sign_view, name="cloudinary_sign"),
    path("annuaire/", views.directory_view, name="directory"),
    path(
        "retrait/merci/",
        views.removal_request_done_view,
        name="removal_request_done",
    ),
    path(
        "retrait/<str:entry_token>/",
        views.removal_request_form_view,
        name="removal_request_form",
    ),
]
