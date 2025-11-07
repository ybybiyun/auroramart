import csv
import random
import os

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from onlineshopfront.models import Product, Category


class Command(BaseCommand):
    help = (
        "Create Product rows from the header SKUs of a transactions CSV file. "
        "Usage: python manage.py import_products_from_transactions /path/to/b2c_products_500_transactions_50k.csv"
    )

    def add_arguments(self, parser):
        parser.add_argument('csv_path', nargs='?', help='Path to transactions CSV file')

    def handle(self, *args, **options):
        csv_path = options.get('csv_path')
        if not csv_path:
            raise CommandError('csv_path is required')

        if not os.path.exists(csv_path):
            raise CommandError(f'File not found: {csv_path}')

        with open(csv_path, newline='') as fh:
            reader = csv.reader(fh)
            try:
                header = next(reader)
            except StopIteration:
                raise CommandError('CSV appears empty')

        # create or get a default category
        cat, _ = Category.objects.get_or_create(slug='uncategorized', defaults={'name': 'Uncategorized'})

        created = 0
        for sku in header:
            sku = sku.strip()
            if not sku:
                continue
            if Product.objects.filter(sku=sku).exists():
                continue
            p = Product.objects.create(
                sku=sku,
                name=sku,
                description=f'Imported from transactions header ({sku})',
                category=cat,
                price=round(random.uniform(5.0, 200.0), 2),
                rating=round(random.uniform(2.5, 5.0), 2),
                stock=random.randint(0, 200),
                reorder_threshold=10,
            )
            created += 1

        self.stdout.write(self.style.SUCCESS(f'Created {created} products (from {csv_path})'))
