import joblib
from pathlib import Path
from django.conf import settings
import pandas as pd

_MODEL = None
_COLUMNS = None

def _load_model():
    global _MODEL, _COLUMNS
    if _MODEL is not None:
        return _MODEL, _COLUMNS

    model_path = Path(settings.BASE_DIR) / 'models' / 'preferred_category_dt.joblib'
    if not model_path.exists():
        raise FileNotFoundError(f'Model file not found at {model_path}. Train it with manage.py train_preferred_category')

    data = joblib.load(model_path)
    _MODEL = data.get('model')
    _COLUMNS = data.get('columns')
    return _MODEL, _COLUMNS

def predict_preferred_category_from_profile(profile: dict):
    """Given a profile dict with keys: age, household_size, has_children, monthly_income_sgd,
    gender, employment_status, occupation, education — return predicted preferred_category.
    """
    model, cols = _load_model()

    # build a single-row dataframe and one-hot encode to match training columns
    df = pd.DataFrame([{
        'age': profile.get('age', 0),
        'household_size': profile.get('household_size', 0),
        'has_children': profile.get('has_children', 0),
        'monthly_income_sgd': profile.get('monthly_income_sgd', profile.get('monthly_income', 0.0)),
        'gender': profile.get('gender', 'Male'),
        'employment_status': profile.get('employment_status', 'Full-time'),
        'occupation': profile.get('occupation', 'Other'),
        'education': profile.get('education', 'Secondary')
    }])

    df_enc = pd.get_dummies(df, columns=['gender', 'employment_status', 'occupation', 'education'])

    # ensure columns align
    for c in cols:
        if c not in df_enc.columns:
            df_enc[c] = 0

    df_enc = df_enc[cols]

    pred = model.predict(df_enc)
    return pred[0]
