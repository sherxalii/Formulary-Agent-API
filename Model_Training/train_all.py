"""
Unified Model Training Pipeline
================================
Trains ALL models used by the UnifiedDrugSystem from the datasets/ folder.

Outputs -> backend/models/
    openfda_ddi_rf.pkl          - DDI Random Forest (from FDA adverse events)
    openfda_drug_profiles.pkl   - Drug reaction-frequency vectors
    decision_tree.pkl           - Drug class classifier
    svm.pkl                     - Drug class classifier (SVM)
    kmeans.pkl                  - Drug safety clustering
    rules.pkl                   - Association rules (side effects)
    processed_drugs_df.pkl      - Full drugs dataframe for lookup

Usage (run from project root):
    python Model_Training/train_all.py

    Options:
    --fda-only      Skip drugs_com CSV training
    --drugs-only    Skip FDA DDI training
    --max-reports N  Limit FDA reports processed (default: all)

All source data must be in datasets/:
    datasets/fda_data/       fda_adverse_events.json, fda_drug_labels.json
    datasets/sider/          side_effects.tsv, indications.tsv, ...
    datasets/drugs_com/      drugs_side_effects_drugs_com.csv
    datasets/synthetic_prescriptions/  prescriptions.json
"""

import argparse
import json
import os
import pickle
import random
import sys
import warnings
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LinearRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn import svm, tree

warnings.filterwarnings('ignore')

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT        = Path(__file__).resolve().parent.parent
DATASETS    = ROOT / 'datasets'
FDA_DIR     = DATASETS / 'fda_data'
SIDER_DIR   = DATASETS / 'sider'
DRUGS_COM   = DATASETS / 'drugs_com'
MODELS_OUT  = ROOT / 'backend' / 'models'
MODELS_OUT.mkdir(parents=True, exist_ok=True)

# Drugs.com dataset (now consolidated in datasets/drugs_com/)
DRUGS_CSV   = DRUGS_COM / 'drugs_side_effects_drugs_com.csv'

# DrugBank DDI dataset (ground truth)
DB_DDI_CSV  = DATASETS / 'db_drug_interactions.csv'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize(name: str) -> str:
    return str(name).upper().strip()


def section(title: str):
    print()
    print('=' * 60)
    print(f'  {title}')
    print('=' * 60)

# ---------------------------------------------------------------------------
# PIPELINE 1 — OpenFDA DDI Model
# ---------------------------------------------------------------------------

def train_fda_ddi(max_reports: int = None):
    section('PIPELINE 1: OpenFDA DDI Random Forest')

    # --- Load primary FDA adverse event data ---
    fda_path = FDA_DIR / 'fda_adverse_events.json'
    if not fda_path.exists():
        print(f'[SKIP] {fda_path} not found — skipping DDI training.')
        return

    print(f'Loading FDA adverse events: {fda_path}')
    with open(fda_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    results = data.get('results', [])
    if max_reports:
        results = results[:max_reports]
    print(f'Processing {len(results):,} reports...')

    # --- Optionally enrich with SIDER side-effect data ---
    sider_drug_reactions: dict[str, set] = {}
    se_path = SIDER_DIR / 'side_effects.tsv'
    if se_path.exists():
        print(f'Loading SIDER side-effects: {se_path}')
        try:
            sider_df = pd.read_csv(se_path, sep='\t', header=None,
                                   usecols=[3, 4],  # drug name, MedDRA term
                                   names=['drug', 'reaction'],
                                   on_bad_lines='skip')
            for _, row in sider_df.iterrows():
                drug = normalize(str(row['drug']))
                rxn  = str(row['reaction']).upper().strip()
                sider_drug_reactions.setdefault(drug, set()).add(rxn)
            print(f'  SIDER enrichment ready: {len(sider_drug_reactions):,} drugs')
        except Exception as e:
            print(f'  [WARN] SIDER load failed: {e}')

    # --- Build drug reaction profiles ---
    drug_reaction_counts: dict = defaultdict(Counter)
    drug_frequencies     : Counter = Counter()
    pair_cooccurrences   : Counter = Counter()
    all_reactions        : Counter = Counter()

    for report in results:
        patient  = report.get('patient', {})
        drugs_raw = patient.get('drug', [])
        rxns_raw  = patient.get('reaction', [])

        report_drugs = set()
        for d in drugs_raw:
            name = d.get('medicinalproduct')
            if name:
                report_drugs.add(normalize(name))

        report_reactions = set()
        for r in rxns_raw:
            pt = r.get('reactionmeddrapt')
            if pt:
                report_reactions.add(pt.upper())

        for drug in report_drugs:
            drug_frequencies[drug] += 1
            # Merge SIDER reactions for this drug
            extra = sider_drug_reactions.get(drug, set())
            for rxn in report_reactions | extra:
                drug_reaction_counts[drug][rxn] += 1
                all_reactions[rxn] += 1

        if len(report_drugs) > 1:
            for pair in combinations(sorted(report_drugs), 2):
                pair_cooccurrences[pair] += 1

    # Feature space: top 100 reactions
    TOP_N = 100
    top_reactions  = [rxn for rxn, _ in all_reactions.most_common(TOP_N)]
    reaction_to_idx = {rxn: i for i, rxn in enumerate(top_reactions)}

    # Filter: drugs with >= 5 mentions
    valid_drugs = {d for d, c in drug_frequencies.items() if c >= 5}
    print(f'Valid drugs (>=5 mentions): {len(valid_drugs):,}')

    drug_profiles: dict[str, np.ndarray] = {}
    for drug in valid_drugs:
        vec = np.zeros(TOP_N)
        total = sum(drug_reaction_counts[drug].values())
        if total > 0:
            for rxn, count in drug_reaction_counts[drug].items():
                if rxn in reaction_to_idx:
                    vec[reaction_to_idx[rxn]] = count / total
        drug_profiles[drug] = vec

    # --- Build training dataset ---
    print('Building labels from DrugBank DDI ground truth...')
    
    pos_pairs = []
    if DB_DDI_CSV.exists():
        try:
            ddi_df = pd.read_csv(DB_DDI_CSV)
            # Ensure we only use pairs where both drugs have OpenFDA profiles
            for _, row in ddi_df.iterrows():
                d1 = normalize(str(row['Drug 1']))
                d2 = normalize(str(row['Drug 2']))
                if d1 in valid_drugs and d2 in valid_drugs:
                    pair = tuple(sorted([d1, d2]))
                    pos_pairs.append(pair)
            
            # Remove duplicates
            pos_pairs = list(set(pos_pairs))
            print(f'  DrugBank pairs found in profile intersection: {len(pos_pairs):,}')
        except Exception as e:
            print(f'  [WARN] Failed to load DrugBank DDI CSV: {e}')

    # Fallback/Supplement with FDA co-occurrence if CSV is missing or sparse
    if len(pos_pairs) < 100:
        print('  Supplementing with FDA co-occurrence heuristics...')
        fda_pos = [
            p for p, c in pair_cooccurrences.items()
            if c >= 2 and p[0] in valid_drugs and p[1] in valid_drugs
        ]
        pos_pairs = list(set(pos_pairs + fda_pos))

    valid_list = list(valid_drugs)
    neg_pairs: list = []
    random.seed(42)
    target_neg = len(pos_pairs) * 1.5 # Slightly lower ratio for larger datasets
    attempts   = 0
    
    # Create a set of all known positive pairs for fast lookup
    pos_set = set(pos_pairs)
    
    print(f'Generating negative samples (target: {int(target_neg):,})...')
    while len(neg_pairs) < target_neg and attempts < 1_000_000:
        attempts += 1
        d1, d2 = random.sample(valid_list, 2)
        pair = tuple(sorted([d1, d2]))
        if pair not in pos_set and pair not in neg_pairs:
            neg_pairs.append(pair)

    print(f'Positive pairs: {len(pos_pairs):,}  |  Negative pairs: {len(neg_pairs):,}')

    def features(d1, d2):
        v1, v2 = drug_profiles[d1], drug_profiles[d2]
        return np.concatenate([np.abs(v1 - v2), v1 * v2])

    X = np.array([features(*p) for p in pos_pairs] + [features(*p) for p in neg_pairs])
    y = np.array([1] * len(pos_pairs) + [0] * len(neg_pairs))

    if len(X) < 20:
        print('[SKIP] Not enough samples — need more FDA data.')
        return

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print('Training Random Forest DDI classifier...')
    clf = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    )
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    print(classification_report(y_test, y_pred, target_names=['No DDI', 'DDI']))
    print(f'Accuracy: {accuracy_score(y_test, y_pred):.3f}')

    # --- Save ---
    with open(MODELS_OUT / 'openfda_ddi_rf.pkl', 'wb') as f:
        pickle.dump(clf, f)
    with open(MODELS_OUT / 'openfda_drug_profiles.pkl', 'wb') as f:
        pickle.dump({
            'profiles':       drug_profiles,
            'top_reactions':  top_reactions,
            'reaction_to_idx': reaction_to_idx,
        }, f)

    print(f'[SAVED] DDI model  -> {MODELS_OUT}/openfda_ddi_rf.pkl')
    print(f'[SAVED] Profiles   -> {MODELS_OUT}/openfda_drug_profiles.pkl')
    print(f'        Drug profiles: {len(drug_profiles):,}')

# ---------------------------------------------------------------------------
# PIPELINE 2 - Drugs.com Side-Effect Models
# ---------------------------------------------------------------------------

def train_drugs_com_models():
    section('PIPELINE 2: Drugs.com Safety Models (DT / SVM / K-Means / Rules)')

    if not DRUGS_CSV.exists():
        print(f'[SKIP] {DRUGS_CSV} not found.')
        print('       Place drugs_side_effects_drugs_com.csv in Model_Training/ and re-run.')
        return

    try:
        from mlxtend.frequent_patterns import apriori, association_rules as arm_rules
    except ImportError:
        print('[SKIP] mlxtend not installed. Run: pip install mlxtend')
        return

    print(f'Loading {DRUGS_CSV.name}...')
    data = pd.read_csv(DRUGS_CSV)
    print(f'  Rows: {len(data):,}')

    # --- Preprocessing ---
    data.drop(columns=['brand_names'], inplace=True, errors='ignore')
    
    if 'alcohol' in data.columns:
        data['alcohol'] = data['alcohol'].replace(float('nan'), '0').replace({'X': 1})
    else:
        data['alcohol'] = 0

    optional_cols = ['side_effects', 'related_drugs', 'generic_name', 'drug_classes', 'rx_otc', 'pregnancy_category', 'csa']
    for col in optional_cols:
        if col in data.columns:
            data[col] = data[col].fillna('Unknown')
        else:
            data[col] = 'Unknown'

    data['rating']        = pd.to_numeric(data['rating'].fillna('0'),        errors='coerce').fillna(0)
    data['no_of_reviews'] = pd.to_numeric(data['no_of_reviews'].fillna('0'), errors='coerce').fillna(0)
    
    if 'activity' in data.columns:
        data['activity'] = (
            data['activity'].astype(str)
                .str.replace(r'\s+', '', regex=True)
                .str.rstrip('%')
        )
        data['activity'] = pd.to_numeric(data['activity'], errors='coerce') / 100
    else:
        data['activity'] = 0.5 # Default middle activity if missing

    # SIDER indications enrichment
    ind_path = SIDER_DIR / 'indications.tsv'
    if ind_path.exists():
        print(f'Enriching with SIDER indications: {ind_path.name}')
        try:
            ind_df = pd.read_csv(ind_path, sep='\t', header=None,
                                 usecols=[3, 4], names=['drug', 'indication'],
                                 on_bad_lines='skip')
            ind_map = ind_df.dropna(subset=['indication']).groupby('drug')['indication'].apply(
                lambda x: ', '.join([str(i) for i in x.unique() if isinstance(i, str) or not pd.isna(i)])
            ).to_dict()
            # Add indication as a new column where missing
            if 'medical_condition' not in data.columns:
                data['medical_condition'] = data['drug_name'].str.upper().map(ind_map).fillna('Unknown')
            print(f'  SIDER indication map: {len(ind_map):,} entries')
        except Exception as e:
            print(f'  [WARN] SIDER indications load failed: {e}')

    if 'medical_condition' not in data.columns:
        data['medical_condition'] = 'Unknown'

    # Label encoding for ML
    le  = LabelEncoder()
    data_enc = data.copy()
    for col in ['csa', 'rx_otc', 'generic_name', 'medical_condition', 'pregnancy_category', 'side_effects']:
        data_enc[col] = le.fit_transform(data_enc[col].astype(str))

    # --- Association Rule Mining (side-effect co-occurrences) ---
    print('Mining association rules...')
    arm_data = data.copy()
    arm_data['Hives']              = arm_data['side_effects'].str.contains('hives',     case=False, na=False)
    arm_data['Difficult Breathing'] = arm_data['side_effects'].str.contains('breathing', case=False, na=False)
    arm_data['Itching']            = arm_data['side_effects'].str.contains('itching',   case=False, na=False)

    arm_df = pd.get_dummies(arm_data[['drug_classes', 'Hives', 'Difficult Breathing', 'Itching']])
    arm_df  = arm_df.astype(bool)
    freq    = apriori(arm_df, min_support=0.001, use_colnames=True)
    rules   = arm_rules(freq, metric='confidence', min_threshold=0.3)
    print(f'  Association rules mined: {len(rules):,}')

    # --- K-Means Clustering ---
    print('Training K-Means clustering...')
    cluster_df = data[['rating', 'no_of_reviews']].copy()
    cluster_df = cluster_df[(cluster_df['rating'] != 0) & (cluster_df['no_of_reviews'] != 0)].dropna()
    kmeans = KMeans(n_clusters=3, random_state=0, n_init=10)
    kmeans.fit(cluster_df)
    print(f'  Clusters: 3  |  Samples: {len(cluster_df):,}')

    # --- Decision Tree + SVM ---
    print('Training Decision Tree and SVM classifiers...')
    arm_data['Drug Class'] = arm_data['drug_classes'].apply(
        lambda x: 'URC' if 'Upper respiratory' in str(x) else 'Non-URC'
    )
    
    unique_classes = arm_data['Drug Class'].nunique()
    if unique_classes > 1:
        X_cls = arm_data[['Hives', 'Difficult Breathing', 'Itching']]
        y_cls = arm_data['Drug Class']
        X_tr, X_te, y_tr, y_te = train_test_split(X_cls, y_cls, test_size=0.2, random_state=42)

        clf_dt  = tree.DecisionTreeClassifier(max_depth=4)
        clf_dt.fit(X_tr, y_tr)
        print(f'  Decision Tree  accuracy: {accuracy_score(y_te, clf_dt.predict(X_te)):.3f}')

        clf_svm = svm.SVC(kernel='linear', probability=True)
        clf_svm.fit(X_tr, y_tr)
        print(f'  SVM            accuracy: {accuracy_score(y_te, clf_svm.predict(X_te)):.3f}')
        
        # Save these models
        with open(MODELS_OUT / 'decision_tree.pkl', 'wb') as f:
            pickle.dump(clf_dt, f)
        with open(MODELS_OUT / 'svm.pkl', 'wb') as f:
            pickle.dump(clf_svm, f)
        print('[SAVED] decision_tree.pkl')
        print('[SAVED] svm.pkl')
    else:
        print(f'  [SKIP] Only {unique_classes} class found in "Drug Class" — skipping DT/SVM.')

    # --- Save remaining models ---
    for name, obj in [
        ('kmeans.pkl',        kmeans),
        ('rules.pkl',         rules),
    ]:
        with open(MODELS_OUT / name, 'wb') as f:
            pickle.dump(obj, f)
        print(f'[SAVED] {name}')

    # Processed dataframe for UnifiedDrugSystem search index
    df_out = data[(data['rating'] != 0) & (data['no_of_reviews'] != 0)].copy()
    df_out.to_pickle(MODELS_OUT / 'processed_drugs_df.pkl')
    print(f'[SAVED] processed_drugs_df.pkl  ({len(df_out):,} rows)')

# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Train all Formulary Agent ML models')
    parser.add_argument('--fda-only',    action='store_true', help='Train FDA DDI model only')
    parser.add_argument('--drugs-only',  action='store_true', help='Train drugs.com models only')
    parser.add_argument('--max-reports', type=int, default=None,
                        help='Limit number of FDA reports (default: all)')
    args = parser.parse_args()

    print()
    print('=' * 60)
    print('  Formulary Agent - Unified Training Pipeline')
    print(f'  Datasets : {DATASETS}')
    print(f'  Output   : {MODELS_OUT}')
    print('=' * 60)

    if not args.drugs_only:
        train_fda_ddi(max_reports=args.max_reports)

    if not args.fda_only:
        train_drugs_com_models()

    section('DONE')
    print('All models saved to:', MODELS_OUT)
    print()
    print('Next step: restart the API server to load the new models.')
    print('  python -m uvicorn app.main:app --host 0.0.0.0 --port 8000')


if __name__ == '__main__':
    main()
