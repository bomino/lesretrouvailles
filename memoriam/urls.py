from django.urls import path
from django.views.generic import TemplateView

app_name = "memoriam"

urlpatterns = [
    # Stub: real view added in Task 10.
    path(
        "in-memoriam/<int:pk>/",
        TemplateView.as_view(template_name="memoriam/detail.html"),
        name="detail",
    ),
]
