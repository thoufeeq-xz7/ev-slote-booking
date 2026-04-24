from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    """
    Extend AbstractUser to add fields specific to the EV Charging + Hospitality context.
    Username, email, password, first_name, last_name exist already.
    """
    USER_TYPE_CHOICES = [
        ('customer', 'Customer'),
        ('owner', 'Station Owner'),
        ('admin', 'Administrator'),
    ]
    
    phone = models.CharField(max_length=20, blank=True, null=True)
    is_hotel_partner = models.BooleanField(default=False)
    # whether the user can access vendor/hotel features
    is_emergency_contact = models.BooleanField(default=False)
    # Optional EV photo uploaded by the user
    ev_photo = models.ImageField(upload_to='ev_photos/', blank=True, null=True)
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='customer')

    # Add billing info, preferred payment method, etc. as needed
    # profile picture, address, etc.
    def __str__(self):
        return f"{self.username} ({self.email})"


# Example domain models for the project (charging stations, bookings)
class ChargingStation(models.Model):
    name = models.CharField(max_length=150)
    location = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    total_ports = models.PositiveIntegerField(default=1)
    ultra_fast = models.BooleanField(default=False)
    powered_by_renewables = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Reservation(models.Model):
    """
    Reservation for a user to use a charger and optionally book hospitality services.
    """
    user = models.ForeignKey('core.CustomUser', on_delete=models.CASCADE, related_name='reservations')
    station = models.ForeignKey(ChargingStation, on_delete=models.CASCADE, related_name='reservations')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    booked_hotel = models.CharField(max_length=255, blank=True, null=True)
    recommendations = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    emergency_contact_requested = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user} @ {self.station} from {self.start_time}"


class POI(models.Model):
    """
    Points of Interest (Hotels, Restaurants, Attractions, Landmarks, Cafes)
    """
    CATEGORY_CHOICES = [
        ('hotel', 'Hotel'),
        ('restaurant', 'Restaurant'),
        ('cafe', 'Cafe'),
        ('attraction', 'Attraction'),
        ('landmark', 'Landmark'),
    ]
    
    district = models.CharField(max_length=150)
    poi_name = models.CharField(max_length=255)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['district', 'poi_name']
    
    def __str__(self):
        return f"{self.poi_name} ({self.district})"


class StationOwner(models.Model):
    """
    Model to manage station owners and their details
    """
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='station_owner')
    company_name = models.CharField(max_length=255)
    company_phone = models.CharField(max_length=20)
    company_email = models.EmailField()
    company_address = models.TextField()
    registration_number = models.CharField(max_length=100, unique=True)
    tax_id = models.CharField(max_length=100, blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.company_name} - {self.user.username}"


class OwnerStation(models.Model):
    """
    Charging stations owned by station owners
    """
    owner = models.ForeignKey(StationOwner, on_delete=models.CASCADE, related_name='stations')
    station = models.OneToOneField(ChargingStation, on_delete=models.CASCADE, related_name='owner_station')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.station.name} ({self.owner.company_name})"


class OwnerService(models.Model):
    """
    Services offered by station owners
    """
    SERVICE_TYPES = [
        ('charging', 'EV Charging'),
        ('repair', 'Repair & Maintenance'),
        ('food', 'Food & Beverage'),
        ('lodging', 'Lodging'),
        ('restroom', 'Restroom Facilities'),
        ('parking', 'Parking'),
        ('wifi', 'WiFi'),
        ('other', 'Other'),
    ]
    
    owner = models.ForeignKey(StationOwner, on_delete=models.CASCADE, related_name='services')
    station = models.ForeignKey(OwnerStation, on_delete=models.CASCADE, related_name='services')
    service_type = models.CharField(max_length=50, choices=SERVICE_TYPES)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    availability_hours = models.CharField(max_length=255, help_text="e.g., 24/7 or 9AM-6PM")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('station', 'service_type')

    def __str__(self):
        return f"{self.get_service_type_display()} at {self.station.station.name}"
