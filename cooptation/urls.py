from django.urls import path

from . import views

app_name = "cooptation"

urlpatterns = [
    path("inscription/", views.signup_view, name="signup"),
    path("inscription/merci/", views.signup_success_view, name="signup_success"),
    path("cooptations-a-valider/", views.parrain_dashboard_view, name="parrain_dashboard"),
    path("cooptation/<str:token>/", views.parrain_vouch_view, name="parrain_vouch"),
    path("questionnaire/<str:token>/", views.questionnaire_view, name="questionnaire"),
]
