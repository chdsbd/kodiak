from django.urls import path
from core import views

urlpatterns = [
    path("installations", views.installations),
    path("login", views.login),
    path("logout", views.logout),
]
