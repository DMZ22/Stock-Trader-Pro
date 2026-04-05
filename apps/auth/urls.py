from django.urls import path
from . import views

app_name = "firebase_auth"

urlpatterns = [
    path("login/", views.login_page, name="login"),
    path("signup/", views.signup_page, name="signup"),
    path("session/", views.session_login, name="session"),
    path("logout/", views.logout_view, name="logout"),
    path("whoami/", views.whoami, name="whoami"),
]
