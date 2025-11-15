import joblib
import os
import pandas as pd
from django.apps import apps

# --- Global variables to hold the loaded models (Lazy Loading) ---
CLASSIFIER_MODEL = None
CLASSIFIER_FEATURE_NAMES = None  # To store the model's required feature order
ASSOCIATION_RULES_DF = None      # To store the rules DataFrame

def get_model_path(model_name):
    """
    Constructs the absolute path to a model file in the 'mlmodels' folder.
    """
    app_path = apps.get_app_config('onlineshopfront').path
    return os.path.join(app_path, 'mlmodels', model_name)

# --- MODEL 1: DECISION TREE CLASSIFIER ---

def get_classifier():
    """
    Lazily loads the Decision Tree Classifier model AND its feature order.
    """
    global CLASSIFIER_MODEL, CLASSIFIER_FEATURE_NAMES
    
    if CLASSIFIER_MODEL is None:
        print("Loading Decision Tree Classifier for the first time...")
        try:
            model_path = get_model_path('b2c_customers_100.joblib')
            CLASSIFIER_MODEL = joblib.load(model_path)
            
            # Read the feature names and their exact order from the model
            if hasattr(CLASSIFIER_MODEL, 'feature_names_in_'):
                CLASSIFIER_FEATURE_NAMES = CLASSIFIER_MODEL.feature_names_in_
                print("Successfully loaded model and feature names.")
            else:
                print("CRITICAL ERROR: Model file does not contain 'feature_names_in_'.")
            
        except FileNotFoundError:
            print(f"ERROR: Classifier file not found at {model_path}")
            
    return CLASSIFIER_MODEL

def predict_preferred_category(customer_data):
    """
    Predicts a new customer's preferred category based on their profile.
    'customer_data' should be a dictionary.
    """
    classifier = get_classifier()
    
    if classifier is None or CLASSIFIER_FEATURE_NAMES is None: 
        print("Classifier or feature names not loaded. Aborting prediction.")
        return None

    try:
        # 1. Create a DataFrame from the single row of data
        input_df = pd.DataFrame([customer_data])

        # 2. Define the categorical prefixes from your form
        categorical_prefixes = ['gender', 'employment_status', 'occupation', 'education']
        
        # 3. Create the one-hot encoded columns
        encoded_df = pd.get_dummies(input_df, prefix=categorical_prefixes)
        
        # 4. Reindex to match the model's exact feature order
        final_df = encoded_df.reindex(columns=CLASSIFIER_FEATURE_NAMES, fill_value=0)
        
        # 5. Predict using the perfectly formatted DataFrame
        prediction = classifier.predict(final_df)
        
        return prediction[0]
        
    except Exception as e:
        print(f"Error during category prediction: {e}")
        return None

# --- MODEL 2: ASSOCIATION RULES ---

def get_rules():
    """
    Lazily loads the Association Rules DataFrame.
    """
    global ASSOCIATION_RULES_DF
    if ASSOCIATION_RULES_DF is None:
        print("Loading Association Rules for the first time...")
        try:
            model_path = get_model_path('b2c_products_500_transactions_50k.joblib')
            # The .joblib file is a pandas DataFrame
            ASSOCIATION_RULES_DF = joblib.load(model_path)
            print("Successfully loaded association rules DataFrame.")
        except FileNotFoundError:
            print(f"ERROR: Association rules file not found at {model_path}")
            
    return ASSOCIATION_RULES_DF

def get_associated_products(sku_list, metric='confidence', top_n=4):
    """
    Finds product SKUs frequently bought with items in the cart.
    This logic is taken directly from your notebook.
    """
    loaded_rules = get_rules()
    if loaded_rules is None or loaded_rules.empty:
        return []

    recommendations = set()
    
    try:
        for item_sku in sku_list:
            # Find rules where the item_sku is in the 'antecedents' (which is a frozenset)
            matched_rules = loaded_rules[loaded_rules['antecedents'].apply(lambda x: item_sku in x)]
            
            # Sort by the metric (e.g., 'confidence' or 'lift')
            top_rules = matched_rules.sort_values(by=metric, ascending=False).head(top_n)
            
            for _, row in top_rules.iterrows():
                recommendations.update(row['consequents'])
                
    except Exception as e:
        print(f"Error processing association rules: {e}")
        return []

    # Remove items that are already in the cart
    recommendations.difference_update(sku_list)
    
    return list(recommendations)[:top_n]