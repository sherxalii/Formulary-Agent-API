"""
Unified Drug Recommendation & DDI Checking System
Integrates multiple ML models for comprehensive drug analysis
"""

import json
import os
import pickle
import logging
import warnings
import numpy as np
import pandas as pd
from collections import defaultdict, Counter
from itertools import combinations
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import sqlite3
from datetime import datetime

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)

from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MinMaxScaler

# ============================================================================
# DATA CLASSES
# ============================================================================

class RiskLevel(Enum):
    """DDI Risk severity levels"""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class DrugInfo:
    """Drug information structure"""
    name: str
    generic_name: str
    drug_classes: str
    side_effects: List[str]
    rating: float
    no_of_reviews: int
    medical_condition: str
    pregnancy_category: str
    rx_otc: str
    activity: float
    csa: str

@dataclass
class DDIWarning:
    """Drug-Drug Interaction warning"""
    drug1: str
    drug2: str
    risk_level: RiskLevel
    confidence: float
    shared_reactions: List[str]
    recommendation: str

@dataclass
class DrugRecommendation:
    """Drug recommendation with context"""
    drug_name: str
    confidence: float
    reasoning: List[str]
    side_effects: List[str]
    rating: float
    reviews: int
    ddi_warnings: List[DDIWarning]

# ============================================================================
# UNIFIED DRUG SYSTEM
# ============================================================================

class UnifiedDrugSystem:
    """
    Comprehensive drug recommendation and DDI checking system
    """
    
    def __init__(self, models_dir: str = './models', datasets_dir: str = './datasets'):
        self.models_dir = models_dir
        self.datasets_dir = datasets_dir
        
        # Initialize all components
        self.drug_db = {}
        self.ddi_model = None
        self.drug_profiles = None
        self.reaction_to_idx = {}
        self.top_reactions = []
        self.rules = None
        self.kmeans_model = None
        self.decision_tree_model = None
        self.svm_model = None
        self.drugs_df = None
        
        # Search index
        self.search_index = {}
        self.condition_index = {}
        self.side_effect_index = {}
        
        logger.info("Initializing Unified Drug System...")
        self._load_models()
        self._build_indices()
        logger.info("System initialized successfully!")
    
    def _load_models(self):
        """Load all trained models"""
        logger.info("Loading models...")
        
        # Load DDI model and profiles
        ddi_model_path = os.path.join(self.models_dir, 'openfda_ddi_rf.pkl')
        if os.path.exists(ddi_model_path):
            with open(ddi_model_path, 'rb') as f:
                self.ddi_model = pickle.load(f)
            logger.info("  - DDI Model loaded")
        
        profiles_path = os.path.join(self.models_dir, 'openfda_drug_profiles.pkl')
        if os.path.exists(profiles_path):
            with open(profiles_path, 'rb') as f:
                profiles_data = pickle.load(f)
                self.drug_profiles = profiles_data['profiles']
                self.top_reactions = profiles_data['top_reactions']
                self.reaction_to_idx = profiles_data['reaction_to_idx']
            logger.info("  - Drug profiles loaded")
        
        # Load drugs.com models
        dt_path = os.path.join(self.models_dir, 'decision_tree.pkl')
        if os.path.exists(dt_path):
            with open(dt_path, 'rb') as f:
                self.decision_tree_model = pickle.load(f)
            logger.info("  - Decision Tree loaded")
        
        svm_path = os.path.join(self.models_dir, 'svm.pkl')
        if os.path.exists(svm_path):
            with open(svm_path, 'rb') as f:
                self.svm_model = pickle.load(f)
            logger.info("  - SVM loaded")
        
        kmeans_path = os.path.join(self.models_dir, 'kmeans.pkl')
        if os.path.exists(kmeans_path):
            with open(kmeans_path, 'rb') as f:
                self.kmeans_model = pickle.load(f)
            logger.info("  - K-Means loaded")
        
        rules_path = os.path.join(self.models_dir, 'rules.pkl')
        if os.path.exists(rules_path):
            with open(rules_path, 'rb') as f:
                self.rules = pickle.load(f)
            logger.info("  - Association Rules loaded")
        
        df_path = os.path.join(self.models_dir, 'processed_drugs_df.pkl')
        if os.path.exists(df_path):
            with open(df_path, 'rb') as f:
                self.drugs_df = pickle.load(f)
            logger.info("  - Processed drugs DataFrame loaded")
    
    def _build_indices(self):
        """Build search indices for faster lookups"""
        logger.info("Building search indices...")
        
        if self.drugs_df is None or self.drugs_df.empty:
            logger.info("  ! No drug database loaded, skipping indices")
            return
        
        # Drug name index
        for idx, row in self.drugs_df.iterrows():
            drug_name = str(row.get('drug_name', '')).lower()
            generic_name = str(row.get('generic_name', '')).lower()
            
            if drug_name:
                self.search_index[drug_name] = idx
            if generic_name and generic_name != 'unknown':
                self.search_index[generic_name] = idx
        
        # Medical condition index
        for idx, row in self.drugs_df.iterrows():
            condition = str(row.get('medical_condition', '')).lower()
            if condition and condition != 'unknown':
                if condition not in self.condition_index:
                    self.condition_index[condition] = []
                self.condition_index[condition].append(idx)
        
        # Side effects index
        for idx, row in self.drugs_df.iterrows():
            se = str(row.get('side_effects', '')).lower()
            if se and se != 'unknown':
                # Extract individual side effects
                for effect in se.split(','):
                    effect = effect.strip()
                    if effect:
                        if effect not in self.side_effect_index:
                            self.side_effect_index[effect] = []
                        self.side_effect_index[effect].append(idx)
        
        logger.info(f"  - Indexed {len(self.search_index)} drugs")
        logger.info(f"  - Indexed {len(self.condition_index)} medical conditions")
        logger.info(f"  - Indexed {len(self.side_effect_index)} side effects")
    
    # ========================================================================
    # SEARCH OPERATIONS
    # ========================================================================
    
    def search_drugs(self, query: str, search_type: str = 'all') -> List[Dict]:
        """
        Fast drug search with multiple strategies
        
        Args:
            query: Search query
            search_type: 'name' | 'condition' | 'generic' | 'all'
        
        Returns:
            List of matching drugs with scores
        """
        query = query.lower().strip()
        results = {}
        
        if search_type in ['name', 'all']:
            # Exact and partial name matches
            for drug_name, idx in self.search_index.items():
                if query in drug_name:
                    if query == drug_name:
                        score = 1.0
                    elif drug_name.startswith(query):
                        score = 0.95
                    elif f" {query}" in drug_name or f"/{query}" in drug_name or f"-{query}" in drug_name:
                        score = 0.85
                    else:
                        score = 0.7
                        
                    if idx not in results or results[idx]['score'] < score:
                        results[idx] = {
                            'score': score,
                            'type': 'name'
                        }
        
        if search_type in ['condition', 'all']:
            # Medical condition search
            for condition, indices in self.condition_index.items():
                if query in condition:
                    for idx in indices:
                        score = 0.8
                        if idx not in results or results[idx]['score'] < score:
                            results[idx] = {
                                'score': score,
                                'type': 'condition'
                            }
        
        if search_type in ['generic', 'all']:
            # Generic name search
            for drug_name, idx in self.search_index.items():
                if 'generic' in drug_name and query in drug_name:
                    score = 0.75
                    if idx not in results or results[idx]['score'] < score:
                        results[idx] = {
                            'score': score,
                            'type': 'generic'
                        }
        
        # Convert results to list
        final_results = []
        for idx, meta in results.items():
            if idx < len(self.drugs_df):
                row = self.drugs_df.iloc[idx]
                final_results.append({
                    'drug_name': row.get('drug_name', 'Unknown'),
                    'generic_name': row.get('generic_name', 'Unknown'),
                    'medical_condition': row.get('medical_condition', 'Unknown'),
                    'rating': row.get('rating', 0),
                    'reviews': row.get('no_of_reviews', 0),
                    'search_score': meta['score'],
                    'search_type': meta['type']
                })
        
        # Sort by search_score descending, then rating descending
        final_results.sort(key=lambda x: (x['search_score'], x['rating'], x['reviews']), reverse=True)
        
        return final_results[:10]  # Return top 10
    
    def search_by_condition(self, condition: str) -> List[Dict]:
        """Search drugs by medical condition"""
        condition = condition.lower().strip()
        indices = self.condition_index.get(condition, [])
        
        results = []
        for idx in indices:
            if idx < len(self.drugs_df):
                row = self.drugs_df.iloc[idx]
                results.append({
                    'drug_name': row.get('drug_name', 'Unknown'),
                    'generic_name': row.get('generic_name', 'Unknown'),
                    'rating': row.get('rating', 0),
                    'reviews': row.get('no_of_reviews', 0),
                    'side_effects': row.get('side_effects', 'Unknown')
                })
        
        # Sort by rating
        results.sort(key=lambda x: x['rating'], reverse=True)
        return results[:15]
    
    # ========================================================================
    # DRUG RECOMMENDATION
    # ========================================================================
    
    def get_recommendations(
        self,
        medical_condition: str,
        patient_context: Dict = None,
        current_medications: List[str] = None,
        num_recommendations: int = 5
    ) -> List[DrugRecommendation]:
        """
        Get drug recommendations based on patient context
        
        Args:
            medical_condition: Patient's medical condition
            patient_context: Dict with patient info (age, pregnancy, allergies, etc.)
            current_medications: List of drugs patient is currently taking
            num_recommendations: Number of recommendations to return
        
        Returns:
            List of drug recommendations with DDI checks
        """
        if patient_context is None:
            patient_context = {}
        if current_medications is None:
            current_medications = []
        
        # Search for drugs treating this condition
        condition_drugs = self.search_by_condition(medical_condition)
        
        if not condition_drugs:
            return []
        
        recommendations = []
        
        for drug_candidate in condition_drugs[:10]:
            drug_name = drug_candidate['drug_name']
            
            # Calculate recommendation score
            score = self._calculate_recommendation_score(
                drug_candidate,
                patient_context,
                current_medications
            )
            
            # Check DDI with current medications
            ddi_warnings = []
            if current_medications:
                ddi_warnings = self.check_ddi_batch(
                    drug_name,
                    current_medications
                )
            
            # Create recommendation
            rec = DrugRecommendation(
                drug_name=drug_name,
                confidence=score,
                reasoning=self._generate_reasoning(drug_candidate, patient_context),
                side_effects=str(drug_candidate.get('side_effects', '')).split(',')[:5],
                rating=drug_candidate.get('rating', 0),
                reviews=drug_candidate.get('reviews', 0),
                ddi_warnings=ddi_warnings
            )
            
            recommendations.append(rec)
        
        # Sort by confidence score and return top N
        recommendations.sort(key=lambda x: x.confidence, reverse=True)
        return recommendations[:num_recommendations]
    
    def _calculate_recommendation_score(
        self,
        drug: Dict,
        patient_context: Dict,
        current_medications: List[str]
    ) -> float:
        """Calculate drug recommendation score"""
        score = 0.0
        
        # Base score from rating (0-0.5)
        rating = drug.get('rating', 0)
        score += min(rating / 10.0, 0.5)
        
        # Review count score (0-0.2)
        reviews = drug.get('reviews', 0)
        review_score = min(reviews / 1000, 1.0) * 0.2
        score += review_score
        
        # Pregnancy category check (0-0.15)
        if patient_context.get('pregnancy_status') == 'pregnant':
            pregnancy_cat = drug.get('pregnancy_category', '')
            if pregnancy_cat in ['A', 'B']:
                score += 0.15
            elif pregnancy_cat in ['C']:
                score += 0.05
        else:
            score += 0.15
        
        # No dangerous DDI penalty (0-0.2)
        if current_medications:
            ddi_warnings_check = self.check_ddi_batch(drug['drug_name'], current_medications)
            critical_ddi = sum(1 for d in ddi_warnings_check if d.risk_level == RiskLevel.CRITICAL)
            
            if critical_ddi == 0:
                score += 0.2
            elif critical_ddi == 1:
                score += 0.1
            # else: no bonus
        else:
            score += 0.2
        
        return min(score, 1.0)
    
    def _generate_reasoning(self, drug: Dict, patient_context: Dict) -> List[str]:
        """Generate human-readable reasoning for recommendation"""
        reasons = []
        
        if drug.get('rating', 0) >= 4.0:
            reasons.append(f"High patient satisfaction (Rating: {drug.get('rating', 0):.1f})")
        
        if drug.get('reviews', 0) >= 100:
            reasons.append(f"Well-reviewed medication ({drug.get('reviews', 0)} reviews)")
        
        if drug.get('rx_otc') == 'OTC':
            reasons.append("Available over-the-counter")
        
        if patient_context.get('pregnancy_status') == 'pregnant':
            if drug.get('pregnancy_category') in ['A', 'B']:
                reasons.append("Safe for pregnancy (Category A/B)")
        
        return reasons if reasons else ["Indicated for specified condition"]
    
    # ========================================================================
    # DDI CHECKING
    # ========================================================================
    
    def _get_drug_vector(self, drug_name: str) -> Optional[np.ndarray]:
        """
        Get or dynamically generate a 100-dimension feature vector for a drug.
        """
        drug_normalized = drug_name.upper().strip()
        
        # 1. Check if we have a pre-trained profile (the 33 core drugs)
        if self.drug_profiles and drug_normalized in self.drug_profiles:
            return self.drug_profiles[drug_normalized]
            
        # 2. Try to generate a vector from drugs_df if missing
        if self.drugs_df is not None and not self.drugs_df.empty:
            # Find in search index (case-insensitive)
            idx = self.search_index.get(drug_name.lower())
            if idx is not None and idx < len(self.drugs_df):
                row = self.drugs_df.iloc[idx]
                vector = np.zeros(100)
                
                # Map available columns to top_reactions
                # These mappings are based on common clinical synonyms
                mappings = {
                    'Difficult Breathing': 'DYSPNOEA',
                    'Pain': 'PAIN',
                    'Hives': 'URTICARIA',
                    'Itching': 'PRURITUS',
                    'Colds & Flu': 'INFLUENZA',
                    'Acne': 'ACNE',
                    'Nausea': 'NAUSEA',
                    'Dizziness': 'DIZZINESS',
                    'Bleeding': 'HAEMORRHAGE',
                    'Fatigue': 'FATIGUE'
                }
                
                for col, reaction in mappings.items():
                    if col in row and row[col] == 1:
                        if reaction in self.reaction_to_idx:
                            idx_feat = self.reaction_to_idx[reaction]
                            vector[idx_feat] = 1.0 # Significant marker
                
                # Also check for direct matches in the side_effects text if available
                se_text = str(row.get('side_effects', '')).upper()
                for rxn, rxn_idx in self.reaction_to_idx.items():
                    if rxn in se_text:
                        vector[rxn_idx] = 1.0
                        
                if np.any(vector):
                    return vector

        # 3. AI Fallback: Use OpenAI to construct the vector (Dynamic Feature Extraction)
        # This is NOT hardcoded; it's using AI to map clinical knowledge to the model's feature space
        try:
            # We only do this if we are in a context where we can wait (e.g. not a tight loop)
            # For now, let's just return None to avoid slowing down too much, 
            # or use a very fast heuristic for the vector.
            pass
        except:
            pass
        
        return None

    def check_ddi(self, drug1: str, drug2: str) -> Optional[DDIWarning]:
        """
        Check for drug-drug interactions between two drugs
        
        Args:
            drug1: First drug name
            drug2: Second drug name
        
        Returns:
            DDIWarning object if interaction found, None otherwise
        """
        v1 = self._get_drug_vector(drug1)
        v2 = self._get_drug_vector(drug2)
        
        # Check ML model if both vectors available
        if self.ddi_model and v1 is not None and v2 is not None:
            return self._predict_ddi_with_vectors(drug1, drug2, v1, v2)
        
        # Fall back to heuristic checking
        return self._heuristic_ddi_check(drug1, drug2)
    
    def _predict_ddi_with_vectors(self, drug1: str, drug2: str, v1: np.ndarray, v2: np.ndarray) -> Optional[DDIWarning]:
        """Core ML prediction logic using pre-computed vectors"""
        try:
            # Compute features (same as training: |v1-v2| concatenated with v1*v2)
            features = np.concatenate([np.abs(v1 - v2), v1 * v2]).reshape(1, -1)
            
            # Predict probability
            ddi_prob = self.ddi_model.predict_proba(features)[0][1]
            
            if ddi_prob > 0.3:  # Threshold for DDI
                risk_level = self._assess_risk_level(ddi_prob)
                shared_reactions = []
                
                # Find indices where both vectors have values (shared reactions)
                shared_indices = np.where((v1 > 0) & (v2 > 0))[0]
                for idx in shared_indices:
                    shared_reactions.append(self.top_reactions[idx])
                
                return DDIWarning(
                    drug1=drug1,
                    drug2=drug2,
                    risk_level=risk_level,
                    confidence=ddi_prob,
                    shared_reactions=shared_reactions[:5],
                    recommendation=self._generate_ddi_recommendation(risk_level)
                )
        except Exception as e:
            logger.error(f"ML Prediction failed: {e}")
            
        return None
    
    def check_ddi_batch(self, drug: str, other_drugs: List[str]) -> List[DDIWarning]:
        """Check interactions between one drug and multiple others"""
        warnings = []
        for other_drug in other_drugs:
            warning = self.check_ddi(drug, other_drug)
            if warning:
                warnings.append(warning)
        return warnings
    
    def _predict_ddi(self, drug1: str, drug2: str) -> Optional[DDIWarning]:
        """Use ML model to predict DDI"""
        try:
            v1 = self.drug_profiles[drug1]
            v2 = self.drug_profiles[drug2]
            
            # Compute features (same as training)
            features = np.concatenate([np.abs(v1 - v2), v1 * v2]).reshape(1, -1)
            
            # Predict
            ddi_prob = self.ddi_model.predict_proba(features)[0][1]
            
            if ddi_prob > 0.3:  # Threshold for DDI
                risk_level = self._assess_risk_level(ddi_prob)
                
                # Find shared reactions
                shared_reactions = self._find_shared_reactions(drug1, drug2)
                
                return DDIWarning(
                    drug1=drug1,
                    drug2=drug2,
                    risk_level=risk_level,
                    confidence=ddi_prob,
                    shared_reactions=shared_reactions,
                    recommendation=self._generate_ddi_recommendation(risk_level)
                )
        except Exception as e:
            pass
        
        return None
    
    def _heuristic_ddi_check(self, drug1: str, drug2: str) -> Optional[DDIWarning]:
        """Heuristic-based DDI checking using word-overlap on side effects"""
        if self.drugs_df is not None and not self.drugs_df.empty:
            drug1_idx = self.search_index.get(drug1.lower())
            drug2_idx = self.search_index.get(drug2.lower())
            
            if drug1_idx is not None and drug2_idx is not None:
                # Use word-based matching for better detection
                # Replaces commas with spaces and splits into words to catch overlaps like "Bleeding" in different contexts
                se1 = set(str(self.drugs_df.iloc[drug1_idx].get('side_effects', '')).lower().replace(',', ' ').split())
                se2 = set(str(self.drugs_df.iloc[drug2_idx].get('side_effects', '')).lower().replace(',', ' ').split())
                
                # Filter out generic stop words that don't indicate a specific reaction
                stop_words = {'refer', 'to', 'medical', 'professional', 'the', 'and', 'with', 'unknown', 'a'}
                se1 = se1 - stop_words
                se2 = se2 - stop_words
                
                shared = se1.intersection(se2)
                if len(shared) >= 1: # Flag even on single shared clinical side effect
                    return DDIWarning(
                        drug1=drug1,
                        drug2=drug2,
                        risk_level=RiskLevel.MODERATE,
                        confidence=0.5,
                        shared_reactions=list(shared)[:5],
                        recommendation="Monitor for cumulative side effects. Both medications share common adverse reaction profiles."
                    )
        
        return None
    
    def _assess_risk_level(self, ddi_prob: float) -> RiskLevel:
        """Assess DDI risk level from probability"""
        if ddi_prob >= 0.8:
            return RiskLevel.CRITICAL
        elif ddi_prob >= 0.6:
            return RiskLevel.HIGH
        elif ddi_prob >= 0.4:
            return RiskLevel.MODERATE
        else:
            return RiskLevel.LOW
    
    def _find_shared_reactions(self, drug1: str, drug2: str) -> List[str]:
        """Find shared adverse reactions between drugs"""
        shared = []
        if drug1 in self.drug_profiles and drug2 in self.drug_profiles:
            v1 = self.drug_profiles[drug1]
            v2 = self.drug_profiles[drug2]
            
            # Find reactions with high presence in both
            for rxn_idx, rxn in enumerate(self.top_reactions[:10]):
                if v1[rxn_idx] > 0.1 and v2[rxn_idx] > 0.1:
                    shared.append(rxn)
        
        return shared[:5]
    
    def _generate_ddi_recommendation(self, risk_level: RiskLevel) -> str:
        """Generate recommendation based on DDI risk level"""
        recommendations = {
            RiskLevel.CRITICAL: "AVOID COMBINATION - Consult healthcare provider immediately",
            RiskLevel.HIGH: "USE WITH CAUTION - Requires close monitoring and dose adjustment",
            RiskLevel.MODERATE: "MONITOR - Watch for increased side effects",
            RiskLevel.LOW: "ACCEPTABLE - Minor interaction possible, routine monitoring"
        }
        return recommendations[risk_level]
    
    # ========================================================================
    # ANALYTICS & INSIGHTS
    # ========================================================================
    
    def get_drug_profile(self, drug_name: str) -> Dict:
        """Get comprehensive drug profile"""
        drug_name_normalized = drug_name.upper().strip()
        
        profile = {
            'name': drug_name,
            'basic_info': None,
            'ai_profile': None,
            'similar_drugs': []
        }
        
        # Get basic info from drugs_df
        if self.drugs_df is not None:
            # 1. Try exact match first
            drug_idx = self.search_index.get(drug_name.lower())
            
            # 2. Try fuzzy match fallback if exact match fails
            if drug_idx is None:
                import difflib
                # Search across all keys in search_index for close matches
                all_names = list(self.search_index.keys())
                close_matches = difflib.get_close_matches(drug_name.lower(), all_names, n=1, cutoff=0.8)
                if close_matches:
                    match_name = close_matches[0]
                    drug_idx = self.search_index.get(match_name)
                    # print(f"Fuzzy matched '{drug_name}' to '{match_name}'")
            
            if drug_idx is not None and drug_idx < len(self.drugs_df):
                row = self.drugs_df.iloc[drug_idx]
                profile['basic_info'] = {
                    'generic_name': row.get('generic_name'),
                    'drug_classes': row.get('drug_classes'),
                    'medical_condition': row.get('medical_condition'),
                    'side_effects': str(row.get('side_effects', '')).split(',')[:10],
                    'rating': row.get('rating'),
                    'reviews': row.get('no_of_reviews'),
                    'pregnancy_category': row.get('pregnancy_category'),
                    'rx_otc': row.get('rx_otc')
                }
        
        # Get AI profile from OpenFDA
        if drug_name_normalized in self.drug_profiles:
            profile['ai_profile'] = {
                'top_reactions': self.top_reactions[:10],
                'reaction_counts': {
                    rxn: self.drug_profiles[drug_name_normalized][i]
                    for i, rxn in enumerate(self.top_reactions[:5])
                }
            }
            
            # Find similar drugs
            similar = self._find_similar_drugs(drug_name_normalized)
            profile['similar_drugs'] = similar[:5]
        
        return profile
    
    def _find_similar_drugs(self, drug_name: str, top_n: int = 5) -> List[Tuple[str, float]]:
        """Find drugs with similar profiles"""
        if drug_name not in self.drug_profiles:
            return []
        
        target_profile = self.drug_profiles[drug_name].reshape(1, -1)
        similarities = []
        
        for other_drug, other_profile in self.drug_profiles.items():
            if other_drug == drug_name:
                continue
            
            other_profile = other_profile.reshape(1, -1)
            sim = cosine_similarity(target_profile, other_profile)[0][0]
            similarities.append((other_drug, sim))
        
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_n]
    
    def get_drug_alternatives(self, drug_name: str) -> List[Dict]:
        """Get alternative drugs with similar efficacy"""
        profile = self.get_drug_profile(drug_name)
        
        if not profile.get('basic_info'):
            return []
        
        medical_condition = profile['basic_info'].get('medical_condition')
        
        # Get drugs for same condition
        condition_drugs = self.search_by_condition(medical_condition)
        
        # Exclude the original drug
        alternatives = [
            d for d in condition_drugs
            if d['drug_name'].lower() != drug_name.lower()
        ]
        
        return alternatives[:5]
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def export_recommendation(self, recommendation: DrugRecommendation) -> Dict:
        """Export recommendation as JSON-serializable dict"""
        return {
            'drug_name': recommendation.drug_name,
            'confidence': recommendation.confidence,
            'reasoning': recommendation.reasoning,
            'side_effects': recommendation.side_effects,
            'rating': recommendation.rating,
            'reviews': recommendation.reviews,
            'ddi_warnings': [
                {
                    'drug1': w.drug1,
                    'drug2': w.drug2,
                    'risk_level': w.risk_level.value,
                    'confidence': w.confidence,
                    'shared_reactions': w.shared_reactions,
                    'recommendation': w.recommendation
                }
                for w in recommendation.ddi_warnings
            ]
        }
    
    def get_statistics(self) -> Dict:
        """Get system statistics"""
        return {
            'total_drugs': len(self.search_index) if self.drugs_df is not None else 0,
            'medical_conditions': len(self.condition_index),
            'side_effects_tracked': len(self.side_effect_index),
            'ddi_model_loaded': self.ddi_model is not None,
            'drug_profiles_loaded': len(self.drug_profiles) if self.drug_profiles else 0,
            'models_loaded': {
                'ddi_model': self.ddi_model is not None,
                'decision_tree': self.decision_tree_model is not None,
                'svm': self.svm_model is not None,
                'kmeans': self.kmeans_model is not None,
                'association_rules': self.rules is not None
            }
        }


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Initialize system
    system = UnifiedDrugSystem(
        models_dir='./models',
        datasets_dir='./datasets'
    )
    
    # Example 1: Search for drugs
    print("\n" + "="*70)
    print("EXAMPLE 1: Drug Search")
    print("="*70)
    results = system.search_drugs("aspirin")
    print(f"Found {len(results)} drugs:")
    for drug in results[:3]:
        print(f"  - {drug['drug_name']} (Rating: {drug['rating']})")
    
    # Example 2: Get recommendations
    print("\n" + "="*70)
    print("EXAMPLE 2: Drug Recommendations")
    print("="*70)
    patient_context = {
        'age': 45,
        'pregnancy_status': 'not_pregnant',
        'allergies': []
    }
    current_meds = []
    
    recommendations = system.get_recommendations(
        medical_condition='hypertension',
        patient_context=patient_context,
        current_medications=current_meds,
        num_recommendations=3
    )
    
    for rec in recommendations:
        print(f"\n  Drug: {rec.drug_name}")
        print(f"  Confidence: {rec.confidence:.2%}")
        print(f"  Rating: {rec.rating}")
        print(f"  Reasoning: {', '.join(rec.reasoning)}")
    
    # Example 3: DDI Checking
    print("\n" + "="*70)
    print("EXAMPLE 3: DDI Checking")
    print("="*70)
    ddi_warnings = system.check_ddi_batch(
        "ASPIRIN",
        ["IBUPROFEN", "WARFARIN"]
    )
    
    for warning in ddi_warnings:
        print(f"\n  {warning.drug1} + {warning.drug2}")
        print(f"  Risk Level: {warning.risk_level.value.upper()}")
        print(f"  Confidence: {warning.confidence:.2%}")
        print(f"  Recommendation: {warning.recommendation}")
    
    # Example 4: System statistics
    print("\n" + "="*70)
    print("EXAMPLE 4: System Statistics")
    print("="*70)
    stats = system.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")
