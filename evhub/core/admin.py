from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, ChargingStation, Reservation, POI, StationOwner, OwnerStation, OwnerService

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_hotel_partner')
    list_filter = ('is_staff', 'is_superuser', 'is_hotel_partner', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)
    fieldsets = UserAdmin.fieldsets + (
        ('Extra info', {'fields': ('phone', 'is_hotel_partner', 'is_emergency_contact')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Extra info', {'fields': ('phone', 'is_hotel_partner')}),
    )

@admin.register(ChargingStation)
class ChargingStationAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'total_ports', 'ultra_fast', 'powered_by_renewables')
    search_fields = ('name', 'location')
    list_filter = ('ultra_fast', 'powered_by_renewables')

@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('user', 'station', 'start_time', 'end_time', 'booked_hotel')
    list_filter = ('booked_hotel',)
    search_fields = ('user__username', 'station__name')

@admin.register(POI)
class POIAdmin(admin.ModelAdmin):
    list_display = ('poi_name', 'district', 'category', 'latitude', 'longitude', 'is_active')
    list_filter = ('district', 'category', 'is_active')
    search_fields = ('poi_name', 'district')
    ordering = ('district', 'poi_name')


@admin.register(StationOwner)
class StationOwnerAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'user', 'company_phone', 'is_verified')
    list_filter = ('is_verified', 'created_at')
    search_fields = ('company_name', 'user__username', 'company_email')
    ordering = ('-created_at',)


@admin.register(OwnerStation)
class OwnerStationAdmin(admin.ModelAdmin):
    list_display = ('station', 'owner', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('station__name', 'owner__company_name')
    ordering = ('-created_at',)


@admin.register(OwnerService)
class OwnerServiceAdmin(admin.ModelAdmin):
    list_display = ('owner', 'station', 'service_type', 'is_active', 'created_at')
    list_filter = ('service_type', 'is_active', 'created_at')
    search_fields = ('owner__company_name', 'station__station__name', 'description')
    ordering = ('-created_at',)

