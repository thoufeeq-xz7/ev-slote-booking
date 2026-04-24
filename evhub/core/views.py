from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count
from django.urls import reverse_lazy
from django.utils import timezone
from datetime import timedelta
import calendar
import pandas as pd
from geopy.distance import geodesic
import requests
from django.http import JsonResponse
from django.core.paginator import Paginator
from .forms import CustomUserCreationForm, CustomAuthenticationForm, OwnerRegistrationForm, StationOwnerForm, OwnerStationForm, OwnerServiceForm
from .models import CustomUser, ChargingStation, Reservation, POI, StationOwner, OwnerStation, OwnerService
from .utils import get_recommendations_for_station
from .openai_recommend import get_openai_recommendations
import logging
import os                         # For file path handling (recommendations CSV path)
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from .models import ChargingStation

logger = logging.getLogger(__name__)


def is_admin(user):
    return user.is_staff or user.is_superuser

def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = CustomUserCreationForm()
    return render(request, 'core/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            if user.is_staff or user.is_superuser:
                return redirect('admin_dashboard')
            elif user.user_type == 'owner' and hasattr(user, 'station_owner'):
                return redirect('owner_dashboard')
            else:
                return redirect('dashboard')
    else:
        form = CustomAuthenticationForm()
    return render(request, 'core/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def dashboard(request):
    # Handle EV photo upload
    if request.method == 'POST' and request.FILES.get('ev_photo'):
        try:
            request.user.ev_photo = request.FILES.get('ev_photo')
            request.user.save()
            return redirect('dashboard')
        except Exception as e:
            logger.error(f"Failed saving EV photo for user {request.user.id}: {e}")

    now = timezone.now()
    # 1. Fetch upcoming bookings (used for both list and map data)
    upcoming = Reservation.objects.filter(user=request.user, start_time__gte=now).order_by('start_time')
    
    # Booking Trends Chart Data - produce a beginner-friendly 6-month view
    reservations = Reservation.objects.filter(user=request.user)
    # Prepare last 6 months labels and counts
    last_n = 6
    months = []
    labels = []
    data = []
    for i in range(last_n - 1, -1, -1):
        m = (now.month - i - 1) % 12 + 1
        months.append(m)
        labels.append(calendar.month_abbr[m])

    counts_by_month = {m: 0 for m in months}
    for r in reservations:
        m = r.start_time.month
        if m in counts_by_month:
            counts_by_month[m] += 1

    for m in months:
        data.append(counts_by_month.get(m, 0))
    
    # Upcoming Booking Map Data
    booking_location = None
    if upcoming:
        first_upcoming_station = upcoming.first().station
        if first_upcoming_station.latitude and first_upcoming_station.longitude:
            booking_location = {
                'lat': first_upcoming_station.latitude,
                'lon': first_upcoming_station.longitude,
                'name': first_upcoming_station.name,
                'start_time': upcoming.first().start_time.strftime("%Y-%m-%d %H:%M")
            }

    # Prepare list for the template & backfill/add fallback recommendation
    upcoming_list = []
    # Ensure this file name is exactly as it appears in your core directory (image_879760.png)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    poi_file_path = os.path.join(base_dir, "kerala_poi_recommendations.csv")

    for r in upcoming[:5]:

        recs = r.recommendations if r.recommendations else []
        
        # Check if recommendations are empty or contain only the old diagnostic message
        # If recs is empty, we must attempt to backfill/add the fallback.
        is_empty_or_diagnostic = (
            not recs or 
            (recs and len(recs) == 1 and recs[0].get('category') == 'Diagnostic')
        )

        if is_empty_or_diagnostic:
            station = r.station 
            
            if station and station.latitude and station.longitude:
                lat = station.latitude
                lon = station.longitude
                
                try:
                    # Calculate the TOP 1 closest POI as a general fallback
                    fallback_df = get_recommendations_for_station(
                        station_latitude=lat, 
                        station_longitude=lon, 
                        poi_file_path=poi_file_path
                    ).head(1)
                    
                    if not fallback_df.empty:
                        fallback_dict = fallback_df.to_dict(orient='records')
                        fallback_dict[0]['category'] = 'General (Fallback)' 
                        recs = fallback_dict
                        
                        # CRUCIAL FIX: Save the fallback back to the database
                        r.recommendations = recs
                        r.save()
                        logger.info(f"Backfilled fallback POI for reservation {r.id}.")
                        
                except Exception as e:
                    logger.error(f"Error calculating dashboard fallback POI for {station.name}: {e}")
                    pass 
            
        r.recommendations = recs
        upcoming_list.append(r)

    return render(request, 'core/dashboard.html', {
        'upcoming': upcoming_list,
        'chart_labels': labels,
        'chart_data': data,
        'booking_location': booking_location,
    })

# core/views.py (Full slots function)

@login_required
def slots(request):
    stations = ChargingStation.objects.all()
    message = ""
    recommendations_list = []

    if request.method == 'POST':
        station_id = request.POST.get('station')
        start_time = request.POST.get('start_time')
        duration = request.POST.get('duration')
        get_recommend = request.POST.get('get_recommendations')

        if station_id and start_time:
            try:
                station = get_object_or_404(ChargingStation, id=station_id)
                start = timezone.make_aware(timezone.datetime.fromisoformat(start_time))
                end = start + timedelta(hours=int(duration))
            except Exception as e:
                logger.error(f"Booking data error: {e}")
                message = f"Error processing booking data. Details: {e}"
                return render(request, 'core/slots.html', {'stations': stations, 'message': message})

            base_dir = os.path.dirname(os.path.abspath(__file__))
            poi_file_path = os.path.join(base_dir, "kerala_poi_recommendations.csv")
            lat = station.latitude
            lon = station.longitude
            recommendation_error = None

            logger.info(f"Attempting POI recommendations for station {station.id} at ({lat}, {lon})")

            if lat and lon:
                try:
                    recommendations_df = get_recommendations_for_station(
                        station_latitude=lat,
                        station_longitude=lon,
                        poi_file_path=poi_file_path
                    )
                    if not recommendations_df.empty:
                        recommendations_list = recommendations_df.to_dict(orient='records')
                        logger.info(f"Generated {len(recommendations_list)} POIs successfully.")
                    else:
                        recommendation_error = "No relevant POIs found near this station."
                        logger.warning(f"No POIs returned for location ({lat}, {lon}).")
                        # OpenAI fallback
                        prompt = f"Suggest hotels and points of interest near latitude {lat}, longitude {lon} for an EV charging slot booking."
                        try:
                            openai_text = get_openai_recommendations(prompt)
                            recommendations_list = [{
                                'poi_name': 'AI Recommendation',
                                'category': 'AI Generated',
                                'distance_km': 0.0,
                                'description': openai_text
                            }]
                        except Exception as e:
                            logger.error(f"OpenAI recommendation failed: {e}")
                            recommendations_list = [{'poi_name': recommendation_error, 'category': 'Diagnostic', 'distance_km': 0.0}]
                except Exception as e:
                    logger.error(f"FATAL Error during POI recommendation: {e}")
                    recommendations_list = [{'poi_name': f"Fatal Error: {e}", 'category': 'Diagnostic', 'distance_km': 0.0}]

            if get_recommend:
                # Only show recommendations, do not book
                message = "Recommendations generated below."
            else:
                # Create Reservation
                reservation = Reservation.objects.create(
                    user=request.user,
                    station=station,
                    start_time=start,
                    end_time=end,
                    recommendations=recommendations_list
                )
                message = f"Successfully booked {station.name} from {start.strftime('%H:%M')} to {end.strftime('%H:%M')}!"
                if len(recommendations_list) > 1:
                    message += f" \n(See {len(recommendations_list)} recommended POIs on the Dashboard.)"
                elif recommendations_list and recommendations_list[0].get('category') == 'Diagnostic':
                    message += " \n(Note: POI recommendations could not be generated.)"
                elif recommendations_list and recommendations_list[0].get('category') != 'Diagnostic':
                    message += " \n(See 1 nearby POI suggestion on the Dashboard.)"
                
    # 3. Station Map Data for Front-end
    stations_map_data = list(ChargingStation.objects.all().values('id', 'name', 'latitude', 'longitude', 'location', 'ultra_fast'))

    return render(request, 'core/slots.html', {
        'stations': stations,
        'message': message,
        'recommendations': recommendations_list,
        'stations_map_data': stations_map_data,
    })
@login_required
def history(request):
    history = Reservation.objects.filter(user=request.user).order_by('-start_time')
    # Ensure recommendations are present for each reservation
    base_dir = os.path.dirname(os.path.abspath(__file__))
    poi_file_path = os.path.join(base_dir, "kerala_poi_recommendations.csv")
    for r in history:
        recs = r.recommendations if r.recommendations else []
        is_empty_or_diagnostic = (
            not recs or
            (recs and len(recs) == 1 and recs[0].get('category') == 'Diagnostic')
        )
        if is_empty_or_diagnostic:
            station = r.station
            if station and station.latitude and station.longitude:
                try:
                    recommendations_df = get_recommendations_for_station(
                        station_latitude=station.latitude,
                        station_longitude=station.longitude,
                        poi_file_path=poi_file_path
                    )
                    if not recommendations_df.empty:
                        recs = recommendations_df.to_dict(orient='records')
                        r.recommendations = recs
                        r.save()
                    else:
                        # Use OpenAI for fallback recommendation
                        prompt = f"Suggest hotels and points of interest near latitude {station.latitude}, longitude {station.longitude} for an EV charging slot booking."
                        try:
                            openai_text = get_openai_recommendations(prompt)
                            recs = [{
                                'poi_name': 'AI Recommendation',
                                'category': 'AI Generated',
                                'distance_km': 0.0,
                                'description': openai_text
                            }]
                            r.recommendations = recs
                            r.save()
                        except Exception as e:
                            logger.error(f"OpenAI recommendation failed for reservation {r.id}: {e}")
                except Exception as e:
                    logger.error(f"Error generating recommendations for history reservation {r.id}: {e}")
        r.recommendations = recs
    return render(request, 'core/history.html', {'history': history})

@user_passes_test(is_admin)
def admin_dashboard(request):
    total_users = CustomUser.objects.count()
    total_stations = ChargingStation.objects.count()
    total_bookings = Reservation.objects.count()
    all_reservations = Reservation.objects.all()

    admin_month_counts = [0] * 12
    for r in all_reservations:
        admin_month_counts[r.start_time.month - 1] += 1
    labels = [calendar.month_abbr[i+1] for i in range(12)]
    
    station_usage_data = []
    usage_counts = Reservation.objects.values('station__id', 'station__latitude', 'station__longitude') \
                                     .annotate(count=Count('station')) \
                                     .filter(station__latitude__isnull=False, station__longitude__isnull=False)

    for item in usage_counts:
        station_usage_data.append({
            'lat': item['station__latitude'],
            'lon': item['station__longitude'],
            'count': item['count'] 
        })
    
    ultra_fast_bookings = Reservation.objects.filter(station__ultra_fast=True).count()
    regular_bookings = Reservation.objects.filter(station__ultra_fast=False).count()

    return render(request, 'core/admin_dashboard.html', {
        'total_users': total_users,
        'total_stations': total_stations,
        'total_bookings': total_bookings,
        'chart_labels': labels,
        'admin_chart_data': admin_month_counts,
        'station_usage_data': station_usage_data,
        'ultra_fast_bookings': ultra_fast_bookings,
        'regular_bookings': regular_bookings,
    })

@user_passes_test(is_admin)
def admin_slots(request):
    all_reservations = Reservation.objects.select_related('user', 'station').order_by('-start_time')
    return render(request, 'core/admin_slots.html', {'all_reservations': all_reservations})

@user_passes_test(is_admin)
@user_passes_test(is_admin)
def admin_stations(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        location = request.POST.get('location')
        ultra_fast = request.POST.get('ultra_fast') == 'on'
        renew = request.POST.get('powered_by_renewables') == 'on'
        
        if name and location:
            try:
                station = ChargingStation.objects.create(
                    name=name, 
                    location=location,
                    ultra_fast=ultra_fast, 
                    powered_by_renewables=renew
                )
                return JsonResponse({
                    'success': f'Station "{name}" added successfully!',
                    'station_id': station.id
                })
            except Exception as e:
                return JsonResponse({
                    'error': f'Failed to add station: {str(e)}'
                }, status=400)
        else:
            return JsonResponse({
                'error': 'Station name and location are required'
            }, status=400)

    # Get all stations and paginate
    all_stations = ChargingStation.objects.all().order_by('-id')
    paginator = Paginator(all_stations, 10)  # 10 stations per page
    page_number = request.GET.get('page', 1)
    stations = paginator.get_page(page_number)
    
    # Calculate starting and ending row numbers for this page
    pagination_start = (stations.number - 1) * 10 + 1
    pagination_end = min(stations.number * 10, paginator.count)
    
    return render(request, 'core/admin_stations.html', {
        'stations': stations,
        'paginator': paginator,
        'page_number': page_number,
        'pagination_start': pagination_start,
        'pagination_end': pagination_end,
        'fast_chargers_count': ChargingStation.objects.filter(ultra_fast=True).count(),
        'renewable_count': ChargingStation.objects.filter(powered_by_renewables=True).count(),
        'todays_reservations': Reservation.objects.filter(
            start_time__date=timezone.now().date()
        ).count(),
    })

def admin_stations_search(request):
    """
    Search for nearby charging stations using multiple APIs
    - Uses Google Maps Places API (if configured) as primary
    - Falls back to OpenChargeMap API
    - Uses OpenStreetMap Nominatim for geocoding
    """
    location = request.GET.get("location")
    if not location:
        return JsonResponse({"error": "No location provided"}, status=400)

    # Step 1: Geocode the location
    location_query = location.replace(" ", "+")
    geocode_url = f"https://nominatim.openstreetmap.org/search?format=json&q={location_query}"
    headers = {"User-Agent": "EVHubApp/1.0 (thoufeeq471@gmail.com)"}

    try:
        geo_response = requests.get(geocode_url, headers=headers, timeout=10)
        geo_response.raise_for_status() 
        try:
            geo_data = geo_response.json()
        except ValueError:
            return JsonResponse({"error": "Invalid geocoding response"}, status=500)

        if not geo_data:
            return JsonResponse({"error": f"No geocoding results for {location}"}, status=404)

        lat = float(geo_data[0].get("lat"))
        lon = float(geo_data[0].get("lon"))
        if not lat or not lon:
            return JsonResponse({"error": "Incomplete geocoding data"}, status=500)

        # Step 2: Try Google Maps Places API first (if key is configured)
        from django.conf import settings
        google_api_key = settings.GOOGLE_MAPS_API_KEY
        
        stations = []
        
        if google_api_key and google_api_key != 'YOUR_GOOGLE_MAPS_API_KEY_HERE':
            try:
                # Google Places API endpoint for nearby search
                google_url = (
                    f"https://maps.googleapis.com/maps/api/place/nearbysearch/json"
                    f"?location={lat},{lon}&radius=10000&keyword=electric%20charging%20station"
                    f"&key={google_api_key}"
                )
                google_response = requests.get(google_url, headers=headers, timeout=10)
                google_response.raise_for_status()
                google_data = google_response.json()
                
                if google_data.get("results"):
                    for place in google_data["results"]:
                        stations.append({
                            "Title": place.get("name", "Unknown Station"),
                            "AddressInfo": {
                                "Title": place.get("name", "Unknown"),
                                "AddressLine1": place.get("vicinity", ""),
                            },
                            "latitude": place.get("geometry", {}).get("location", {}).get("lat"),
                            "longitude": place.get("geometry", {}).get("location", {}).get("lng"),
                            "source": "Google Maps"
                        })
            except Exception as e:
                logger.warning(f"Google Maps API error: {e}. Falling back to OpenChargeMap.")
        
        # Step 3: Fallback to OpenChargeMap if no Google results or API not configured
        if not stations:
            try:
                ocm_url = (
                    f"https://api.openchargemap.io/v3/poi/?output=json"
                    f"&latitude={lat}&longitude={lon}&distance=10&distanceunit=KM"
                )
                ocm_response = requests.get(ocm_url, headers=headers, timeout=10)
                ocm_response.raise_for_status()
                stations = ocm_response.json()
            except Exception as e:
                logger.error(f"OpenChargeMap API error: {e}")
                return JsonResponse({"error": f"Station API error: {str(e)}"}, status=500)

        return JsonResponse({"stations": stations})

    except requests.exceptions.RequestException as e:
        return JsonResponse({"error": f"Network/API error: {str(e)}"}, status=500)
    except Exception as e:
        return JsonResponse({"error": f"Unexpected error: {str(e)}"}, status=500)
    
@user_passes_test(is_admin)
@user_passes_test(is_admin)
def admin_station_delete(request, station_id):
    station = get_object_or_404(ChargingStation, id=station_id)
    if request.method == "POST":
        station_name = station.name
        station.delete()
        return JsonResponse({"success": f"Station '{station_name}' deleted successfully."})
    return JsonResponse({"error": "Invalid request method"}, status=400)

@user_passes_test(is_admin)
@login_required
@user_passes_test(is_admin)
def admin_station_update(request, station_id):
    station = get_object_or_404(ChargingStation, id=station_id)
    
    # Handle GET request - show edit page
    if request.method == "GET":
        return render(request, 'core/admin_station_edit.html', {'station': station})
    
    # Handle POST request - update station
    if request.method == "POST":
        name = request.POST.get("name", station.name).strip()
        location = request.POST.get("location", station.location).strip()
        ultra_fast = request.POST.get("ultra_fast") == "true"
        renew = request.POST.get("powered_by_renewables") == "true"

        # Only update fields if they have values
        if name:
            station.name = name
        if location:
            station.location = location
        station.ultra_fast = ultra_fast
        station.powered_by_renewables = renew
        station.save()

        return JsonResponse({"success": f"Station '{station.name}' updated successfully."})
    return JsonResponse({"error": "Invalid request method"}, status=400)


# ===== POI RECOMMENDATION SYSTEM =====

@login_required
def poi_recommendations(request):
    """
    Display POI recommendations for user's current location/district
    """
    districts = POI.objects.filter(is_active=True).values_list('district', flat=True).distinct().order_by('district')
    selected_district = request.GET.get('district')
    pois = POI.objects.filter(is_active=True)
    
    if selected_district:
        pois = pois.filter(district=selected_district)
    
    # Group by category
    categories = {}
    for poi in pois:
        if poi.category not in categories:
            categories[poi.category] = []
        categories[poi.category].append(poi)
    
    return render(request, 'core/poi_recommendations.html', {
        'districts': districts,
        'selected_district': selected_district,
        'categories': categories,
        'pois': pois,
    })


@login_required
@user_passes_test(is_admin)
def admin_poi_management(request):
    """
    Admin view to manage POI recommendations
    """
    pois = POI.objects.all().order_by('district', 'poi_name')
    districts = pois.values_list('district', flat=True).distinct()
    
    return render(request, 'core/admin_poi_management.html', {
        'pois': pois,
        'districts': districts,
    })


@login_required
@user_passes_test(is_admin)
def admin_poi_add(request):
    """
    Add new POI
    """
    if request.method == 'POST':
        try:
            poi = POI.objects.create(
                district=request.POST.get('district'),
                poi_name=request.POST.get('poi_name'),
                category=request.POST.get('category'),
                latitude=request.POST.get('latitude'),
                longitude=request.POST.get('longitude'),
                is_active=request.POST.get('is_active') == 'true'
            )
            return JsonResponse({"success": f"POI '{poi.poi_name}' added successfully."})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
    
    categories = [choice[0] for choice in POI._meta.get_field('category').choices]
    return JsonResponse({"categories": categories})


@login_required
@user_passes_test(is_admin)
def admin_poi_edit(request, poi_id):
    """
    Edit existing POI
    """
    poi = get_object_or_404(POI, id=poi_id)
    
    if request.method == 'POST':
        try:
            poi.district = request.POST.get('district', poi.district)
            poi.poi_name = request.POST.get('poi_name', poi.poi_name)
            poi.category = request.POST.get('category', poi.category)
            poi.latitude = request.POST.get('latitude', poi.latitude)
            poi.longitude = request.POST.get('longitude', poi.longitude)
            poi.is_active = request.POST.get('is_active') == 'true'
            poi.save()
            return JsonResponse({"success": f"POI '{poi.poi_name}' updated successfully."})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
    
    return JsonResponse({
        "id": poi.id,
        "district": poi.district,
        "poi_name": poi.poi_name,
        "category": poi.category,
        "latitude": str(poi.latitude),
        "longitude": str(poi.longitude),
        "is_active": poi.is_active,
    })


@login_required
@user_passes_test(is_admin)
def admin_poi_delete(request, poi_id):
    """
    Delete POI
    """
    poi = get_object_or_404(POI, id=poi_id)
    if request.method == 'POST':
        poi_name = poi.poi_name
        poi.delete()
        return JsonResponse({"success": f"POI '{poi_name}' deleted successfully."})
    return JsonResponse({"error": "Invalid request method"}, status=400)


@login_required
@user_passes_test(is_admin)
def admin_poi_import_csv(request):
    """
    Import POI data from CSV file
    """
    if request.method == 'POST' and request.FILES.get('csv_file'):
        try:
            csv_file = request.FILES['csv_file']
            
            # Read CSV file
            df = pd.read_csv(csv_file)
            
            # Validate required columns
            required_columns = ['district', 'poi_name', 'category', 'latitude', 'longitude']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                return JsonResponse({
                    "error": f"CSV missing required columns: {', '.join(missing_columns)}"
                }, status=400)
            
            count = 0
            errors = []
            
            for idx, row in df.iterrows():
                try:
                    # Validate row data
                    if pd.isna(row['district']) or pd.isna(row['poi_name']):
                        errors.append(f"Row {idx + 2}: Missing district or poi_name")
                        continue
                    
                    poi, created = POI.objects.get_or_create(
                        district=str(row['district']).strip(),
                        poi_name=str(row['poi_name']).strip(),
                        defaults={
                            'category': str(row['category']).strip().lower(),
                            'latitude': float(row['latitude']),
                            'longitude': float(row['longitude']),
                            'is_active': True
                        }
                    )
                    if created:
                        count += 1
                except Exception as row_error:
                    errors.append(f"Row {idx + 2}: {str(row_error)}")
                    continue
            
            message = f"Imported {count} new POIs from CSV."
            if errors:
                message += f" Skipped {len(errors)} rows with errors."
            
            return JsonResponse({"success": message})
        except Exception as e:
            logger.error(f"CSV import error: {str(e)}")
            return JsonResponse({
                "error": f"Import failed: {str(e)}"
            }, status=400)
    
    return JsonResponse({"error": "No file provided or invalid method"}, status=400)

@login_required
@user_passes_test(is_admin)
def admin_station_edit(request, station_id):
    """Admin edits a station"""
    station = get_object_or_404(ChargingStation, id=station_id)
    
    if request.method == 'POST':
        station.name = request.POST.get('name', station.name)
        station.location = request.POST.get('location', station.location)
        station.latitude = request.POST.get('latitude') or station.latitude
        station.longitude = request.POST.get('longitude') or station.longitude
        station.ultra_fast = request.POST.get('ultra_fast') == 'on'
        station.powered_by_renewables = request.POST.get('powered_by_renewables') == 'on'
        station.save()
        
        return redirect('admin_stations')
    
    context = {
        'station': station,
    }
    return render(request, 'core/admin_station_edit.html', context)

@login_required
@user_passes_test(is_admin)
def admin_add_station(request):
    """admin adds a charging station"""

    
    if request.method == 'POST':
        # Create new charging station
        name = request.POST.get('name')
        location = request.POST.get('location')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        total_ports = request.POST.get('total_ports', 1)
        ultra_fast = request.POST.get('ultra_fast') == 'on'
        powered_by_renewables = request.POST.get('powered_by_renewables') == 'on'
        
        try:
            station = ChargingStation.objects.create(
                name=name,
                location=location,
                latitude=latitude if latitude else None,
                longitude=longitude if longitude else None,
                total_ports=int(total_ports),
                ultra_fast=ultra_fast,
                powered_by_renewables=powered_by_renewables,
            )
            
            # Link station to admin
            OwnerStation.objects.create(admin=request.user, station=station)
            
            return redirect('admin_stations')
        except Exception as e:
            return render(request, 'core/admin_add_station.html', {
                'error': str(e)
            })
    
    return render(request, 'core/admin_add_station.html')




@user_passes_test(is_admin)
@require_POST
def admin_stations_import(request):
    """Import charging stations from Excel/CSV file"""
    try:
        if 'file' not in request.FILES:
            return JsonResponse({"error": "No file provided"}, status=400)
        
        file = request.FILES['file']
        if not file.name.endswith(('.xlsx', '.xls', '.csv')):
            return JsonResponse({"error": "Only Excel (.xlsx, .xls) and CSV files are supported"}, status=400)
        
        # Read file based on extension
        if file.name.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        
        # Validate columns
        required_cols = ['name', 'location']
        for col in required_cols:
            if col.lower() not in [c.lower() for c in df.columns]:
                return JsonResponse({
                    "error": f"Missing required column: {col}"
                }, status=400)
        
        # Normalize column names (case-insensitive)
        df.columns = [c.lower().strip() for c in df.columns]
        
        count = 0
        errors = []
        
        for idx, row in df.iterrows():
            try:
                name = str(row.get('name', '')).strip()
                location = str(row.get('location', '')).strip()
                
                if not name or not location:
                    errors.append(f"Row {idx + 2}: Name and location are required")
                    continue
                
                # Check if station already exists
                if ChargingStation.objects.filter(name=name, location=location).exists():
                    continue
                
                # Parse boolean values
                ultra_fast = str(row.get('ultra fast', 'no')).lower() in ['yes', 'true', '1', 'y']
                renewable = str(row.get('powered by renewables', 'no')).lower() in ['yes', 'true', '1', 'y']
                
                # Create station
                ChargingStation.objects.create(
                    name=name,
                    location=location,
                    ultra_fast=ultra_fast,
                    powered_by_renewables=renewable,
                    total_ports=0
                )
                count += 1
            except Exception as row_error:
                errors.append(f"Row {idx + 2}: {str(row_error)}")
                continue
        
        return JsonResponse({
            "success": True,
            "count": count,
            "message": f"Successfully imported {count} stations"
        })
    
    except Exception as e:
        logger.error(f"Station import error: {str(e)}")
        return JsonResponse({
            "error": f"Import failed: {str(e)}"
        }, status=400)


# ===== STATION OWNER FEATURES =====

def owner_register_view(request):
    """Register as a station owner"""
    if request.method == 'POST':
        user_form = OwnerRegistrationForm(request.POST)
        owner_form = StationOwnerForm(request.POST)
        
        if user_form.is_valid() and owner_form.is_valid():
            user = user_form.save()
            owner = owner_form.save(commit=False)
            owner.user = user
            owner.save()
            login(request, user)
            return redirect('owner_dashboard')
        else:
            context = {
                'user_form': user_form,
                'owner_form': owner_form,
            }
            return render(request, 'core/owner_register.html', context)
    else:
        user_form = OwnerRegistrationForm()
        owner_form = StationOwnerForm()
    
    return render(request, 'core/owner_register.html', {
        'user_form': user_form,
        'owner_form': owner_form,
    })


def is_owner(user):
    """Check if user is a station owner"""
    return hasattr(user, 'station_owner') and user.user_type == 'owner'


@login_required
@user_passes_test(is_owner)
def owner_dashboard(request):
    """Owner dashboard showing their stations and services"""
    try:
        owner = request.user.station_owner
    except StationOwner.DoesNotExist:
        return redirect('owner_register')
    
    owner_stations = OwnerStation.objects.filter(owner=owner).select_related('station')
    total_stations = owner_stations.count()
    total_services = OwnerService.objects.filter(owner=owner).count()
    
    # Get reservations for owner's stations
    owner_station_ids = owner_stations.values_list('station_id', flat=True)
    total_bookings = Reservation.objects.filter(station_id__in=owner_station_ids).count()
    
    context = {
        'owner': owner,
        'owner_stations': owner_stations,
        'total_stations': total_stations,
        'total_services': total_services,
        'total_bookings': total_bookings,
    }
    return render(request, 'core/owner_dashboard.html', context)


@login_required
@user_passes_test(is_owner)
def owner_add_station(request):
    """Owner adds a charging station"""
    try:
        owner = request.user.station_owner
    except StationOwner.DoesNotExist:
        return redirect('owner_register')
    
    if request.method == 'POST':
        # Create new charging station
        name = request.POST.get('name')
        location = request.POST.get('location')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        total_ports = request.POST.get('total_ports', 1)
        ultra_fast = request.POST.get('ultra_fast') == 'on'
        powered_by_renewables = request.POST.get('powered_by_renewables') == 'on'
        
        try:
            station = ChargingStation.objects.create(
                name=name,
                location=location,
                latitude=latitude if latitude else None,
                longitude=longitude if longitude else None,
                total_ports=int(total_ports),
                ultra_fast=ultra_fast,
                powered_by_renewables=powered_by_renewables,
            )
            
            # Link station to owner
            OwnerStation.objects.create(owner=owner, station=station)
            
            return redirect('owner_manage_stations')
        except Exception as e:
            return render(request, 'core/owner_add_station.html', {
                'error': str(e)
            })
    
    return render(request, 'core/owner_add_station.html')


@login_required
@user_passes_test(is_owner)
def owner_manage_stations(request):
    """Owner manages their stations"""
    try:
        owner = request.user.station_owner
    except StationOwner.DoesNotExist:
        return redirect('owner_register')
    
    owner_stations = OwnerStation.objects.filter(owner=owner).select_related('station')
    
    context = {
        'owner_stations': owner_stations,
    }
    return render(request, 'core/owner_manage_stations.html', context)


@login_required
@user_passes_test(is_owner)
def owner_edit_station(request, station_id):
    """Owner edits a station"""
    try:
        owner = request.user.station_owner
    except StationOwner.DoesNotExist:
        return redirect('owner_register')
    
    owner_station = get_object_or_404(OwnerStation, id=station_id, owner=owner)
    station = owner_station.station
    
    if request.method == 'POST':
        station.name = request.POST.get('name', station.name)
        station.location = request.POST.get('location', station.location)
        station.latitude = request.POST.get('latitude') or station.latitude
        station.longitude = request.POST.get('longitude') or station.longitude
        station.total_ports = int(request.POST.get('total_ports', station.total_ports))
        station.ultra_fast = request.POST.get('ultra_fast') == 'on'
        station.powered_by_renewables = request.POST.get('powered_by_renewables') == 'on'
        station.save()
        
        return redirect('owner_manage_stations')
    
    context = {
        'owner_station': owner_station,
        'station': station,
    }
    return render(request, 'core/owner_edit_station.html', context)


@login_required
@user_passes_test(is_owner)
def owner_delete_station(request, station_id):
    """Owner deletes a station"""
    try:
        owner = request.user.station_owner
    except StationOwner.DoesNotExist:
        return redirect('owner_register')
    
    owner_station = get_object_or_404(OwnerStation, id=station_id, owner=owner)
    
    if request.method == 'POST':
        station = owner_station.station
        owner_station.delete()
        station.delete()
        return redirect('owner_manage_stations')
    
    context = {
        'owner_station': owner_station,
    }
    return render(request, 'core/owner_delete_station.html', context)


@login_required
@user_passes_test(is_owner)
def owner_manage_services(request, station_id):
    """Owner manages services for a station"""
    try:
        owner = request.user.station_owner
    except StationOwner.DoesNotExist:
        return redirect('owner_register')
    
    owner_station = get_object_or_404(OwnerStation, id=station_id, owner=owner)
    services = OwnerService.objects.filter(station=owner_station)
    
    context = {
        'owner_station': owner_station,
        'services': services,
        'service_types': OwnerService.SERVICE_TYPES,
    }
    return render(request, 'core/owner_manage_services.html', context)


@login_required
@user_passes_test(is_owner)
def owner_add_service(request, station_id):
    """Owner adds a service to a station"""
    try:
        owner = request.user.station_owner
    except StationOwner.DoesNotExist:
        return redirect('owner_register')
    
    owner_station = get_object_or_404(OwnerStation, id=station_id, owner=owner)
    
    if request.method == 'POST':
        form = OwnerServiceForm(request.POST)
        if form.is_valid():
            service = form.save(commit=False)
            service.owner = owner
            service.station = owner_station
            service.save()
            return redirect('owner_manage_services', station_id)
    else:
        form = OwnerServiceForm()
    
    context = {
        'owner_station': owner_station,
        'form': form,
    }
    return render(request, 'core/owner_add_service.html', context)


@login_required
@user_passes_test(is_owner)
def owner_edit_service(request, station_id, service_id):
    """Owner edits a service"""
    try:
        owner = request.user.station_owner
    except StationOwner.DoesNotExist:
        return redirect('owner_register')
    
    owner_station = get_object_or_404(OwnerStation, id=station_id, owner=owner)
    service = get_object_or_404(OwnerService, id=service_id, owner=owner)
    
    if request.method == 'POST':
        form = OwnerServiceForm(request.POST, instance=service)
        if form.is_valid():
            form.save()
            return redirect('owner_manage_services', station_id)
    else:
        form = OwnerServiceForm(instance=service)
    
    context = {
        'owner_station': owner_station,
        'service': service,
        'form': form,
    }
    return render(request, 'core/owner_edit_service.html', context)


@login_required
@user_passes_test(is_owner)
def owner_delete_service(request, station_id, service_id):
    """Owner deletes a service"""
    try:
        owner = request.user.station_owner
    except StationOwner.DoesNotExist:
        return redirect('owner_register')
    
    owner_station = get_object_or_404(OwnerStation, id=station_id, owner=owner)
    service = get_object_or_404(OwnerService, id=service_id, owner=owner)
    
    if request.method == 'POST':
        service.delete()
        return redirect('owner_manage_services', station_id)
    
    context = {
        'owner_station': owner_station,
        'service': service,
    }
    return render(request, 'core/owner_delete_service.html', context)


@login_required
@user_passes_test(is_owner)
def owner_profile(request):
    """Owner profile management"""
    try:
        owner = request.user.station_owner
    except StationOwner.DoesNotExist:
        return redirect('owner_register')
    
    if request.method == 'POST':
        form = StationOwnerForm(request.POST, instance=owner)
        if form.is_valid():
            form.save()
            return redirect('owner_profile')
    else:
        form = StationOwnerForm(instance=owner)
    
    context = {
        'owner': owner,
        'form': form,
    }
    return render(request, 'core/owner_profile.html', context)
