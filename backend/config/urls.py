from django.contrib import admin
from django.urls import include, path
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import TemplateView


def page(template_name):
    # 頁面載入時先發出 csrftoken cookie,api.js 才能在寫入請求附上 X-CSRFToken
    return ensure_csrf_cookie(TemplateView.as_view(template_name=template_name))


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
    path("", page("index.html"), name="index"),
    path("login/", page("login.html"), name="login"),
    path("nodes/", page("nodes.html"), name="nodes"),
    path("assistant/", page("assistant.html"), name="assistant"),
    path("display/", page("display.html"), name="display"),
]

handler404 = "core.exceptions.api_not_found"
handler500 = "core.exceptions.api_server_error"
