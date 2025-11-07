from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
import csv
from decimal import Decimal, InvalidOperation
from onlineshopfront.models import Category, SubCategory, Product


class Command(BaseCommand):
    help = "Import products from a CSV file into the Product, Category and SubCategory models."

    def add_arguments(self, parser):
        parser.add_argument("--file", dest="file", help="Path to products CSV file", required=True)

    def handle(self, *args, **options):
        path = options.get("file")
        if not path:
            raise CommandError("Please provide --file /path/to/b2c_products_500.csv")

        created = 0
        updated = 0

        # Try UTF-8 first; fall back to latin-1 (CP1252) if the file contains non-UTF8 bytes.
        try:
            # quick check to force a decode and catch UnicodeDecodeError early
            with open(path, newline='', encoding='utf-8') as _check:
                _check.read(4096)
            f = open(path, newline='', encoding='utf-8')
        except UnicodeDecodeError:
            # many CSVs exported from Windows use cp1252/latin-1 encoding; open with replace to avoid crashes
            try:
                f = open(path, newline='', encoding='latin-1', errors='replace')
                self.stdout.write(self.style.WARNING('File not UTF-8 — opened with latin-1 (fallback)'))
            except Exception as e:
                raise CommandError(f"Could not open file with fallback encoding: {e}")
        except Exception as e:
            raise CommandError(f"Could not open file: {e}")

        reader = csv.DictReader(f)

        with transaction.atomic():
            for row in reader:
                sku = row.get('SKU code') or row.get('sku') or row.get('sku_code')
                name = row.get('Product name') or row.get('product_name')
                desc = row.get('Product description') or row.get('description') or ''
                cat_name = row.get('Product Category') or row.get('category') or 'Uncategorized'
                subcat_name = row.get('Product Subcategory') or row.get('sub_category') or row.get('subcategory') or None
                qty = row.get('Quantity on hand') or row.get('quantity_on_hand') or '0'
                reorder = row.get('Reorder Quantity') or row.get('reorder_quantity') or '0'
                price = row.get('Unit price') or row.get('unit_price') or '0'

                if not sku:
                    self.stderr.write("Skipping row without SKU")
                    continue

                # get or create category (models use `category_name`)
                category, _ = Category.objects.get_or_create(category_name=cat_name.strip())

                # get or create subcategory if present (models use `subcategory_name`)
                subcategory = None
                if subcat_name:
                    subcategory, _ = SubCategory.objects.get_or_create(subcategory_name=subcat_name.strip(), category=category)

                # parse numbers
                try:
                    quantity_on_hand = int(float(qty))
                except Exception:
                    quantity_on_hand = 0

                try:
                    reorder_quantity = int(float(reorder))
                except Exception:
                    reorder_quantity = 0

                try:
                    unit_price = Decimal(price)
                except (InvalidOperation, TypeError):
                    unit_price = Decimal('0')

                # parse product rating (may be missing)
                rating_raw = row.get('Product rating') or row.get('product_rating') or '0'
                try:
                    product_rating = float(rating_raw)
                except Exception:
                    product_rating = 0.0

                # Map CSV columns to the current Product model fields
                product_values = {
                    'product_name': name.strip() if name else sku,
                    'product_description': desc or '',
                    'product_category': cat_name.strip(),
                    'product_subcategory': subcategory,
                    'quantity_on_hand': quantity_on_hand,
                    'reorder_quantity': reorder_quantity,
                    'unit_price': unit_price,
                    'product_rating': product_rating,
                }

                # Product primary key in the model is `sku`
                obj, created_flag = Product.objects.update_or_create(sku=sku.strip(), defaults=product_values)
                if created_flag:
                    created += 1
                else:
                    updated += 1

        f.close()

        self.stdout.write(self.style.SUCCESS(f"Import finished. Created: {created}, Updated: {updated}"))