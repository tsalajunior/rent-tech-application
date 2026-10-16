from django.urls import path
from . import views


app_name = 'core'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('equipements/', views.liste_equipements, name='liste_equipements'),
    path('clients/', views.liste_clients, name='liste_clients'),
]