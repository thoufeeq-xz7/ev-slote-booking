from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # main user pages
    path('dashboard/', views.dashboard, name='dashboard'),
    path('slots/', views.slots, name='slots'),
    path('history/', views.history, name='history'),

    # admin dashboard pages
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-slots/', views.admin_slots, name='admin_slots'),
    path('admin-stations/', views.admin_stations, name='admin_stations'),

    # admin station management
    path('admin-stations-search/', views.admin_stations_search, name='admin_stations_search'),
    path('admin-stations-import/', views.admin_stations_import, name='admin_stations_import'),
    path('admin-station/<int:station_id>/update/', views.admin_station_update, name='admin_station_update'),
    path('admin-station/<int:station_id>/delete/', views.admin_station_delete, name='admin_station_delete'),
    path('admin-add-station/', views.admin_add_station, name='admin_add_station'),


    # POI management
    path('poi-recommendations/', views.poi_recommendations, name='poi_recommendations'),
    path('admin-poi-management/', views.admin_poi_management, name='admin_poi_management'),
    path('admin/poi/add/', views.admin_poi_add, name='admin_poi_add'),
    path('admin/poi/edit/<int:poi_id>/', views.admin_poi_edit, name='admin_poi_edit'),
    path('admin/poi/delete/<int:poi_id>/', views.admin_poi_delete, name='admin_poi_delete'),
    path('admin/poi/import-csv/', views.admin_poi_import_csv, name='admin_poi_import_csv'),

    # Owner registration and dashboard
    path('owner-register/', views.owner_register_view, name='owner_register'),
    path('owner-dashboard/', views.owner_dashboard, name='owner_dashboard'),
    path('owner-profile/', views.owner_profile, name='owner_profile'),

    # Owner station management
    path('owner-manage-stations/', views.owner_manage_stations, name='owner_manage_stations'),
    path('owner-add-station/', views.owner_add_station, name='owner_add_station'),
    path('owner-edit-station/<int:station_id>/', views.owner_edit_station, name='owner_edit_station'),
    path('owner-delete-station/<int:station_id>/', views.owner_delete_station, name='owner_delete_station'),

    # Owner service management
    path('owner-manage-services/<int:station_id>/', views.owner_manage_services, name='owner_manage_services'),
    path('owner-add-service/<int:station_id>/', views.owner_add_service, name='owner_add_service'),
    path('owner-edit-service/<int:station_id>/<int:service_id>/', views.owner_edit_service, name='owner_edit_service'),
    path('owner-delete-service/<int:station_id>/<int:service_id>/', views.owner_delete_service, name='owner_delete_service'),
]
