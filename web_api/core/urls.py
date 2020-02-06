from django.urls import path
from core import views

urlpatterns = [
    path("current_datetime", views.current_datetime),
    path("hello", views.hello),
    path("installations", views.installations),
    path("login", views.login),
    path("logout", views.logout),
]
