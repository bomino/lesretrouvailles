from django.urls import path

from . import views

app_name = "cooptation"

urlpatterns = [
    path("inscription/", views.signup_view, name="signup"),
    path("inscription/merci/", views.signup_success_view, name="signup_success"),
]
