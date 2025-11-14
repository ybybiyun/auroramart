from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path
import pandas as pd
import joblib

def build_dataframe_from_customers(customers):
    rows = []
    for c in customers:
        rows.append({
            'age': c.age or 0,
            'household_size': c.household_size or 0,
            'has_children': c.has_children or 0,
            'monthly_income_sgd': c.monthly_income or 0.0,
            'gender': c.gender or 'Male',
            'employment_status': c.employment_status or 'Full-time',
            'occupation': c.occupation or 'Other',
            'education': c.education or 'Secondary',
            'preferred_category': c.preferred_category or ''
        })
    df = pd.DataFrame(rows)
    return df


class Command(BaseCommand):
    help = 'Train a DecisionTreeClassifier to predict customer preferred_category from profile features'

    def add_arguments(self, parser):
        parser.add_argument('--out', help='Output joblib file path', default=None)

    def handle(self, *args, **options):
        from onlineshopfront.models import Customer
        from sklearn.model_selection import train_test_split
        from sklearn.tree import DecisionTreeClassifier
        from sklearn import metrics

        customers = Customer.objects.all()
        if not customers.exists():
            self.stdout.write(self.style.ERROR('No customers found in database. Populate Customer table first.'))
            return

        df = build_dataframe_from_customers(customers)

        # drop rows with empty preferred_category
        df = df[df['preferred_category'].astype(bool)].copy()
        if df.empty:
            self.stdout.write(self.style.ERROR('No customers with a preferred_category found.'))
            return

        # features and target
        X = df.drop(columns=['preferred_category'])
        y = df['preferred_category']

        # one-hot encode categorical features
        X_encoded = pd.get_dummies(X, columns=['gender', 'employment_status', 'occupation', 'education'])

        # align training set columns (not necessary here, but helpful if reusing)
        X_train, X_test, y_train, y_test = train_test_split(X_encoded, y, test_size=0.2, random_state=42, stratify=y)

        clf = DecisionTreeClassifier(random_state=42)
        clf.fit(X_train, y_train)

        preds = clf.predict(X_test)
        acc = metrics.accuracy_score(y_test, preds)
        report = metrics.classification_report(y_test, preds, zero_division=0)

        out_path = options.get('out')
        if not out_path:
            base = Path(settings.BASE_DIR)
            models_dir = base / 'models'
            models_dir.mkdir(exist_ok=True)
            out_path = str(models_dir / 'preferred_category_dt.joblib')

        joblib.dump({'model': clf, 'columns': list(X_encoded.columns)}, out_path)

        self.stdout.write(self.style.SUCCESS(f'Model trained and saved to {out_path}'))
        self.stdout.write(self.style.SUCCESS(f'Accuracy on test set: {acc:.4f}'))
        self.stdout.write(report)
