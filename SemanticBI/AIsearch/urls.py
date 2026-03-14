from django.urls import path
from . import views

urlpatterns = [
    path('', views.upload_view, name='upload'),
    path('search/', views.search_view, name='search'),
    path('insights/', views.insights_view, name='insights'),
    path('analytics/', views.analytics_view, name='analytics'),
    path('history/', views.history_view, name='history'),
    path('select/<int:dataset_id>/', views.select_dataset_view, name='select_dataset'),
]
