# onlineshopfront/recommender.py

import joblib
import os
import pandas as pd
from django.apps import apps

# --- 1. LOAD MODELS (as per professor's instructions) ---

# Get the path to the 'onlineshopfront' app
app_path = apps.get_app_config('onlineshopfront').path

# Load Decision Tree Classifier
model_path_classifier = os.path.join(app_path, 'mlmodels', 'b2c_customers_100.joblib')
classifier_model = joblib.load(model_path_classifier)

# Load Association Rules
model_path_rules = os.path.join(app_path, 'mlmodels', 'b2c_products_500_transactions_50k.joblib')
association_rules = joblib.load(model_path_rules)


# --- 2. PREDICTION FUNCTION 1 (from predict_classifier.ipynb) ---

def predict_preferred_category(customer_data):
    """
    Predicts the preferred category for a new customer.
    customer_data should be a dict, e.g.:
    {
        'age': 29, 'household_size': 2, 'has_children': 1, 'monthly_income_sgd': 5000,
        'gender': 'Female', 'employment_status': 'Full-time',
        'occupation': 'Sales', 'education': 'Bachelor'
    }
    """
    columns = {
        'age':'int64', 'household_size':'int64', 'has_children':'int64', 'monthly_income_sgd':'float64',
        'gender_Female':'bool', 'gender_Male':'bool', 'employment_status_Full-time':'bool',
        'employment_status_Part-time':'bool', 'employment_status_Retired':'bool',
        'employment_status_Self-employed':'bool', 'employment_status_Student':'bool',
        'occupation_Admin':'bool', 'occupation_Education':'bool', 'occupation_Sales':'bool',
        'occupation_Service':'bool', 'occupation_Skilled Trades':'bool', 'occupation_Tech':'bool',
        'education_Bachelor':'bool', 'education_Diploma':'bool', 'education_Doctorate':'bool',
        'education_Master':'bool', 'education_Secondary':'bool'
    }

    df = pd.DataFrame({col: pd.Series(dtype=dtype) for col, dtype in columns.items()})
    customer_df = pd.DataFrame([customer_data])
    customer_encoded = pd.get_dummies(customer_df, columns=['gender', 'employment_status', 'occupation', 'education'])    

    for col in df.columns:
        if col not in customer_encoded.columns:
            if df[col].dtype == bool:
                df[col] = False
            else:
                df[col] = 0
        else:
            df[col] = customer_encoded[col]

    # Get the prediction
    prediction = classifier_model.predict(df)    

    # Return the first item, e.g., "Beauty & Personal Care"
    return prediction[0]


# --- 3. PREDICTION FUNCTION 2 (from predict_associationrules.ipynb) ---

def get_recommendations(items, metric='confidence', top_n=3):
    """
    Gets product recommendations based on a list of items (SKUs) in the cart.
    e.g., items = ['AIA-JM4T8BP6', 'AEA-BMAE38SR']
    """
    recommendations = set()

    for item in items:
        # Find rules where the item is in the antecedents
        matched_rules = association_rules[association_rules['antecedents'].apply(lambda x: item in x)]
        # Sort by the specified metric
        top_rules = matched_rules.sort_values(by=metric, ascending=False).head(top_n)

        for _, row in top_rules.iterrows():
            recommendations.update(row['consequents'])

    # Remove items that are already in the input list
    recommendations.difference_update(items)

    # Return a list of SKUs
    return list(recommendations)[:top_n]