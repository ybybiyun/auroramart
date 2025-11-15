# Recommender / Classification

This folder contains a small Decision Tree training command and a prediction helper.

- Training command: `python manage.py train_preferred_category` — trains a DecisionTreeClassifier on `Customer` rows and writes `models/preferred_category_dt.joblib`.
- Prediction helper: `onlineshopfront.recommender.predict_preferred_category_from_profile(profile_dict)` — loads model and predicts a preferred category.

Notes:
- This is a small demo pipeline intended for local experiments. The trained model and feature columns are saved together in a joblib file.
- Ensure you have `pandas` and `scikit-learn` installed (added to `requirements.txt`).