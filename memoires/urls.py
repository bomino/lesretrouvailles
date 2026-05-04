from django.urls import path

from . import views

app_name = "memoires"

urlpatterns = [
    path("souvenirs/", views.gallery_view, name="gallery"),
    path("souvenirs/<int:pk>/", views.detail_view, name="detail"),
]
