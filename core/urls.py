from django.urls import path
from . import views

urlpatterns = [
    path("strings", views.create_string),
    path("strings/<str:string_value>", views.get_string),
    path("strings/filter-by-natural-language", views.filter_by_natural_language),
    path("strings", views.list_strings),
    path("strings/<str:string_value>", views.delete_string),
]
