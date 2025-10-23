from django.urls import path
from . import views

urlpatterns = [
    path("strings/filter-by-natural-language", views.filter_by_natural_language),
    path("strings", views.strings),
    path("strings/<str:string_value>", views.string_detail),
    
    
]
