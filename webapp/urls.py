from django.urls import path

from webapp.views import compare_traces


app_name = "webapp"

urlpatterns = [
    path("", compare_traces, name="compare"),
]