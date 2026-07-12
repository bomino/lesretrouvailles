from django.urls import path

from . import views

app_name = "members"

urlpatterns = [
    path("charte/", views.charter_view, name="charter"),
    path("membres/<uuid:slug>/", views.profile_detail_view, name="profile_detail"),
    path("profil/", views.profile_edit_view, name="profile_edit"),
    path("api/cloudinary/sign/", views.cloudinary_sign_view, name="cloudinary_sign"),
    path("annuaire/", views.directory_view, name="directory"),
    path("promotions/", views.promotions_index_view, name="promotions_index"),
    path(
        "promotions/<int:year>/<str:class_label>/",
        views.promotion_class_view,
        name="promotion_class",
    ),
    path(
        "promotions/entree/<int:pk>/revendiquer/",
        views.roster_claim_view,
        name="roster_claim",
    ),
    path(
        "retrait/merci/",
        views.removal_request_done_view,
        name="removal_request_done",
    ),
    path(
        "retrait/expire/",
        views.removal_expired_view,
        name="removal_expired",
    ),
    path(
        "retrait/confirme/<str:confirm_token>/",
        views.removal_confirm_view,
        name="removal_confirm",
    ),
    path(
        "retrait/<str:entry_token>/",
        views.removal_request_form_view,
        name="removal_request_form",
    ),
]
