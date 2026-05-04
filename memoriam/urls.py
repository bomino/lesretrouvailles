from django.urls import path
from django.views.generic import TemplateView

from . import views

app_name = "memoriam"

urlpatterns = [
    path("in-memoriam/", views.list_view, name="list"),
    path("in-memoriam/<int:pk>/", views.detail_view, name="detail"),
    # Stub — Task 11 replaces with real view + form.
    path(
        "in-memoriam/nominer/",
        TemplateView.as_view(template_name="memoriam/list.html"),
        name="nominate",
    ),
]
