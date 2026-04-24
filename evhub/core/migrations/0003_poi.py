# Generated migration for POI model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_reservation_recommendations'),
    ]

    operations = [
        migrations.CreateModel(
            name='POI',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('district', models.CharField(max_length=150)),
                ('poi_name', models.CharField(max_length=255)),
                ('category', models.CharField(choices=[('hotel', 'Hotel'), ('restaurant', 'Restaurant'), ('cafe', 'Cafe'), ('attraction', 'Attraction'), ('landmark', 'Landmark')], max_length=50)),
                ('latitude', models.DecimalField(decimal_places=6, max_digits=9)),
                ('longitude', models.DecimalField(decimal_places=6, max_digits=9)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['district', 'poi_name'],
            },
        ),
    ]
