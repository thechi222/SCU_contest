from django.contrib import admin
from django.urls import include, path
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import TemplateView


def page(template_name, name):
    # 頁面載入時先發出 csrftoken cookie,api.js 才能在寫入請求附上 X-CSRFToken
    return ensure_csrf_cookie(
        TemplateView.as_view(template_name=template_name, extra_context={"page": name}),
    )


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
    path("", page("home.html", "home"), name="home"),
    path("login/", page("login.html", "login"), name="login"),
    path("register/", page("register.html", "register"), name="register"),
    path("workbench/", page("workbench.html", "workbench"), name="workbench"),
    path("nodes/", page("nodes.html", "nodes"), name="nodes"),
    path("dashboard/", page("dashboard.html", "dashboard"), name="dashboard"),
    path("rentals/", page("rentals.html", "rentals"), name="rentals"),
    path("assistant/", page("assistant.html", "assistant"), name="assistant"),
    path("display/", page("display.html", "display"), name="display"),
]

handler404 = "core.exceptions.api_not_found"
handler500 = "core.exceptions.api_server_error"
