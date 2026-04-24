# Generated migration for owner models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_customuser_ev_photo'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='user_type',
            field=models.CharField(choices=[('customer', 'Customer'), ('owner', 'Station Owner'), ('admin', 'Administrator')], default='customer', max_length=20),
        ),
        migrations.CreateModel(
            name='StationOwner',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('company_name', models.CharField(max_length=255)),
                ('company_phone', models.CharField(max_length=20)),
                ('company_email', models.EmailField(max_length=254)),
                ('company_address', models.TextField()),
                ('registration_number', models.CharField(max_length=100, unique=True)),
                ('tax_id', models.CharField(blank=True, max_length=100, null=True)),
                ('is_verified', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='station_owner', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='OwnerStation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stations', to='core.stationowner')),
                ('station', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='owner_station', to='core.chargingstation')),
            ],
        ),
        migrations.CreateModel(
            name='OwnerService',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('service_type', models.CharField(choices=[('charging', 'EV Charging'), ('repair', 'Repair & Maintenance'), ('food', 'Food & Beverage'), ('lodging', 'Lodging'), ('restroom', 'Restroom Facilities'), ('parking', 'Parking'), ('wifi', 'WiFi'), ('other', 'Other')], max_length=50)),
                ('description', models.TextField()),
                ('price', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('availability_hours', models.CharField(help_text='e.g., 24/7 or 9AM-6PM', max_length=255)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='services', to='core.stationowner')),
                ('station', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='services', to='core.ownerstation')),
            ],
            options={
                'unique_together': {('station', 'service_type')},
            },
        ),
    ]
