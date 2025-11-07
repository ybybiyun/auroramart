from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
import csv

from onlineshopfront.models import Customer


class Command(BaseCommand):
    help = "Import customers from a CSV file into the Customer model."

    def add_arguments(self, parser):
        parser.add_argument("--file", dest="file", help="Path to customers CSV file", required=True)

    def handle(self, *args, **options):
        path = options.get("file")
        if not path:
            raise CommandError("Please provide --file /path/to/b2c_customers_100.csv")

        created = 0

        # Open with UTF-8 first, fall back to latin-1 with replace
        try:
            with open(path, newline='', encoding='utf-8') as _check:
                _check.read(4096)
            f = open(path, newline='', encoding='utf-8')
        except UnicodeDecodeError:
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
                try:
                    age = int(float(row.get('age') or 0))
                except Exception:
                    age = 0

                gender = (row.get('gender') or '').strip()
                employment_status = (row.get('employment_status') or '').strip()
                occupation = (row.get('occupation') or '').strip()
                education = (row.get('education') or '').strip()

                try:
                    household_size = int(float(row.get('household_size') or 0))
                except Exception:
                    household_size = 0

                try:
                    has_children = int(float(row.get('has_children') or 0))
                except Exception:
                    has_children = 0

                try:
                    monthly_income = float(row.get('monthly_income_sgd') or row.get('monthly_income') or 0.0)
                except Exception:
                    monthly_income = 0.0

                preferred_category = (row.get('preferred_category') or '').strip()

                # Create a new Customer row. There is no unique identifier in the CSV so we insert all rows.
                Customer.objects.create(
                    first_name=None,
                    last_name=None,
                    phone=None,
                    email=None,
                    address=None,
                    postal_code=None,
                    age=age,
                    gender=gender if gender else 'Male',
                    employment_status=employment_status if employment_status else 'Full-time',
                    occupation=occupation,
                    education=education if education else 'Secondary',
                    household_size=household_size,
                    has_children=has_children,
                    monthly_income=monthly_income,
                    preferred_category=preferred_category or '',
                )
                created += 1

        f.close()

        self.stdout.write(self.style.SUCCESS(f"Import finished. Created: {created}"))
