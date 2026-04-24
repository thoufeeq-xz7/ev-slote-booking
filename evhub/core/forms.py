from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import CustomUser, ChargingStation, StationOwner, OwnerStation, OwnerService

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'phone', 'is_hotel_partner')
        widgets = {
            'password': forms.PasswordInput(),
        }

class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(max_length=254)
    password = forms.CharField(label="Password", strip=False, widget=forms.PasswordInput)
    class Meta:
        model = CustomUser
        fields = ('username', 'password')


class ChargingStationForm(forms.ModelForm):
    """Form for creating and updating charging stations"""
    class Meta:
        model = ChargingStation
        fields = ('name', 'location', 'latitude', 'longitude', 'total_ports', 'ultra_fast', 'powered_by_renewables')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Station Name'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Location/Address'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Latitude', 'step': 0.000001}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Longitude', 'step': 0.000001}),
            'total_ports': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'ultra_fast': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'powered_by_renewables': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class OwnerRegistrationForm(UserCreationForm):
    """Form for station owner registration"""
    email = forms.EmailField(required=True)

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'phone', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.user_type = 'owner'
        if commit:
            user.save()
        return user


class StationOwnerForm(forms.ModelForm):
    """Form for station owner profile/company information"""
    class Meta:
        model = StationOwner
        fields = ('company_name', 'company_phone', 'company_email', 'company_address', 'registration_number', 'tax_id')
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Company Name'}),
            'company_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Company Phone'}),
            'company_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Company Email'}),
            'company_address': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Company Address', 'rows': 3}),
            'registration_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Registration Number'}),
            'tax_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tax ID (Optional)'}),
        }


class OwnerStationForm(forms.ModelForm):
    """Form for owner to link a charging station"""
    class Meta:
        model = OwnerStation
        fields = ('station',)
        widgets = {
            'station': forms.Select(attrs={'class': 'form-control'}),
        }


class OwnerServiceForm(forms.ModelForm):
    """Form for owner to add/edit services"""
    class Meta:
        model = OwnerService
        fields = ('service_type', 'description', 'price', 'availability_hours', 'is_active')
        widgets = {
            'service_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Service Description'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Price (Optional)', 'step': 0.01}),
            'availability_hours': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 24/7 or 9AM-6PM'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }