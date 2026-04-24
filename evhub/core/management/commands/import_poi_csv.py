import os
import pandas as pd
from django.core.management.base import BaseCommand
from core.models import POI


class Command(BaseCommand):
    help = 'Import POI data from kerala_poi_recommendations.csv'

    def handle(self, *args, **options):
        # Get the CSV file path
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        csv_path = os.path.join(base_dir, 'kerala_poi_recommendations.csv')

        if not os.path.exists(csv_path):
            self.stdout.write(self.style.ERROR(f'CSV file not found at {csv_path}'))
            return

        try:
            df = pd.read_csv(csv_path)
            count = 0

            for _, row in df.iterrows():
                poi, created = POI.objects.get_or_create(
                    district=row['district'],
                    poi_name=row['poi_name'],
                    defaults={
                        'category': row['category'],
                        'latitude': row['latitude'],
                        'longitude': row['longitude'],
                        'is_active': True
                    }
                )
                if created:
                    count += 1

            self.stdout.write(
                self.style.SUCCESS(f'Successfully imported {count} new POIs from CSV')
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error importing CSV: {str(e)}'))
