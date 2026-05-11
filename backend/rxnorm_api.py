"""
RxNorm and RxClass API Integration Module
This module provides functions to interact with RxNorm and RxClass APIs
to get drug information and therapeutic classes for drug comparison.
"""

import requests
import json
import time
from typing import Dict, List, Optional, Any
import xml.etree.ElementTree as ET
import logging
import functools

logger = logging.getLogger(__name__)

class RxNormAPI:
    """Handler for RxNorm and RxClass API interactions"""
    
    BASE_URL = "https://rxnav.nlm.nih.gov"
    
    def __init__(self, rate_limit_delay: float = 0.2):
        """
        Initialize RxNorm API handler
        
        Args:
            rate_limit_delay: Delay between API calls (set to 0.0 for maximum speed - 15-sec goal)
        """
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'FormularyDrugRAG/1.0'
        })
    
    def _make_request(self, endpoint: str, params: Dict[str, Any], max_retries: int = 2) -> Optional[Dict]:
        """
        Make a request to RxNorm API with error handling, rate limiting, and retry with exponential backoff
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            max_retries: Maximum number of retries (default: 3)
            
        Returns:
            Parsed response data or None if failed
        """
        url = f"{self.BASE_URL}{endpoint}"
        backoff_base = 0.5
        for attempt in range(max_retries + 1):  # +1 for initial attempt
            try:
                # NO RATE LIMITING - Maximum speed for 15-second goal
                if self.rate_limit_delay > 0:
                    time.sleep(self.rate_limit_delay)
                
                # Reduced logging for performance
                logger.debug(f"Making request (attempt {attempt + 1}/{max_retries + 1}) to: {url} params: {params}")
                response = self.session.get(url, params=params, timeout=10)  # Reduced timeout to 10s
                if response.status_code == 429 or 500 <= response.status_code < 600:
                    if attempt < max_retries:
                        delay = backoff_base * (2 ** attempt)
                        logger.warning(f"Received status {response.status_code} for {url}. Retrying in {delay}s (attempt {attempt + 1}/{max_retries + 1})")
                        time.sleep(delay)
                        continue
                    else:
                        logger.error(f"Received status {response.status_code} for {url} after {max_retries + 1} attempts.")
                        return None
                
                # Do not retry on 4xx client errors (like 400, 404)
                if 400 <= response.status_code < 500 and response.status_code != 429:
                    logger.debug(f"Client error {response.status_code} for {url}. Not retrying.")
                    return None
                
                response.raise_for_status()
                
                # Parse JSON response
                if response.headers.get('content-type', '').startswith('application/json'):
                    result = response.json()
                    logger.debug(f"Received JSON response on attempt {attempt + 1}")
                    return result
                else:
                    # Parse XML response
                    root = ET.fromstring(response.content)
                    result = self._xml_to_dict(root)
                    logger.debug(f"Received XML response on attempt {attempt + 1}")
                    return result
                    
            except requests.exceptions.RequestException as e:
                if attempt < max_retries:
                    # Aggressive backoff: 0.1s, 0.2s, 0.4s (much faster than before)
                    backoff_delay = 0.1 * (2 ** attempt)
                    logger.warning(f"API request failed for {url} (attempt {attempt + 1}/{max_retries + 1}): {e}. Retrying in {backoff_delay}s...")
                    time.sleep(backoff_delay)
                    continue
                else:
                    logger.error(f"API request failed for {url} after {max_retries + 1} attempts: {e}")
                    return None
            except Exception as e:
                if attempt < max_retries:
                    backoff_delay = 0.1 * (2 ** attempt)
                    logger.warning(f"Error parsing API response for {url} (attempt {attempt + 1}/{max_retries + 1}): {e}. Retrying in {backoff_delay}s...")
                    time.sleep(backoff_delay)
                    continue
                else:
                    logger.error(f"Error parsing API response for {url} after {max_retries + 1} attempts: {e}")
                    return None
        
        return None
    
    def _xml_to_dict(self, element) -> Dict:
        """Convert XML element to dictionary"""
        result = {}
        
        # Handle attributes
        if element.attrib:
            result.update(element.attrib)
        
        # Handle children
        children = list(element)
        if children:
            child_dict = {}
            for child in children:
                child_data = self._xml_to_dict(child)
                if child.tag in child_dict:
                    if not isinstance(child_dict[child.tag], list):
                        child_dict[child.tag] = [child_dict[child.tag]]
                    child_dict[child.tag].append(child_data)
                else:
                    child_dict[child.tag] = child_data
            result.update(child_dict)
        elif element.text:
            result = element.text.strip()
        
        return result

    @functools.lru_cache(maxsize=512)
    def find_rxcui_by_name(self, drug_name: str, search_type: int = 2) -> Optional[List[str]]:
        """
        Find RXCUI (RxNorm Concept Unique Identifier) for a drug name
        
        Args:
            drug_name: Name of the drug to search for
            search_type: Search precision (0=exact, 1=normalized, 2=exact or normalized, 9=approximate)
            
        Returns:
            List of RXCUIs or None if not found
        """
        endpoint = "/REST/rxcui.json"
        params = {
            'name': drug_name,
            'allsrc': 0,  # Only active concepts
            'search': search_type
        }
        
        response_data = self._make_request(endpoint, params)
        if not response_data:
            return None
        
        # Extract RXCUIs from response
        rxcuis = []
        if 'idGroup' in response_data and 'rxnormId' in response_data['idGroup']:
            rxnorm_ids = response_data['idGroup']['rxnormId']
            if isinstance(rxnorm_ids, list):
                rxcuis = rxnorm_ids
            elif rxnorm_ids:
                rxcuis = [rxnorm_ids]
        
        return rxcuis if rxcuis else None
    
    @functools.lru_cache(maxsize=512)
    def get_spelling_suggestions(self, drug_name: str) -> Optional[List[str]]:
        """
        Get spelling suggestions for a drug name using RxNorm API
        
        Args:
            drug_name: Name of the drug to get spelling suggestions for
            
        Returns:
            List of suggested drug names or None if no suggestions found
        """
        endpoint = "/REST/spellingsuggestions.json"
        params = {
            'name': drug_name
        }
        
        response_data = self._make_request(endpoint, params)
        if not response_data:
            return None
        
        # Extract suggestions from response
        suggestions = []
        if ('suggestionGroup' in response_data and 
            response_data['suggestionGroup'] and
            'suggestionList' in response_data['suggestionGroup'] and
            response_data['suggestionGroup']['suggestionList'] and
            'suggestion' in response_data['suggestionGroup']['suggestionList']):
            
            suggestion_data = response_data['suggestionGroup']['suggestionList']['suggestion']
            if isinstance(suggestion_data, list):
                suggestions = suggestion_data
            elif suggestion_data:
                suggestions = [suggestion_data]
        
        logger.info(f"Spelling suggestions for '{drug_name}': {suggestions}")
        return suggestions if suggestions else None
    
    @functools.lru_cache(maxsize=512)
    def get_corrected_drug_name(self, drug_name: str) -> str:
        """
        Get corrected drug name using spelling suggestions.
        Returns the original name if no suggestions found or if original name is already correct.
        
        Args:
            drug_name: Original drug name (potentially misspelled)
            
        Returns:
            Corrected drug name or original name if no corrections found
        """
        # First, try to find RXCUI for the original name to see if it's already correct
        rxcuis = self.find_rxcui_by_name(drug_name)
        if rxcuis:
            logger.info(f"Drug name '{drug_name}' is already correct (found RXCUI: {rxcuis[0]})")
            return drug_name
        
        # If no RXCUI found, try spelling suggestions
        suggestions = self.get_spelling_suggestions(drug_name)
        if suggestions and len(suggestions) > 0:
            corrected_name = suggestions[0]  # Take the first (most likely) suggestion
            logger.info(f"Corrected '{drug_name}' to '{corrected_name}' using RxNorm spelling suggestions")
            return corrected_name
        
        logger.warning(f"No spelling corrections found for '{drug_name}', using original name")
        return drug_name
    
    @functools.lru_cache(maxsize=512)
    def get_approximate_matches(self, drug_name: str) -> Optional[List[Dict[str, str]]]:
        """
        Search for drugs using approximate matching (best for autocomplete).
        """
        endpoint = "/REST/approximateTerm.json"
        params = {
            'term': drug_name,
            'maxEntries': 10
        }
        
        response_data = self._make_request(endpoint, params)
        if not response_data:
            return None
            
        matches = []
        if ('approximateGroup' in response_data and 
            'candidate' in response_data['approximateGroup']):
            candidates = response_data['approximateGroup']['candidate']
            if not isinstance(candidates, list):
                candidates = [candidates]
                
            for cand in candidates:
                # Use name or term if available, fallback to rxcui only if necessary
                name = cand.get('name') or cand.get('term') or cand.get('rxcui')
                matches.append({
                    'name': name,
                    'rxcui': cand.get('rxcui'),
                    'score': cand.get('score'),
                    'rank': cand.get('rank')
                })
        
        # To get the actual names, we'd need another call or use a different endpoint
        # Let's try /REST/displaynames.json or just resolve the RXCUIs
        return matches

    @functools.lru_cache(maxsize=512)
    def get_ddi_interactions(self, rxcuis: tuple) -> Optional[Dict]:
        """
        Check for interactions between a list of RXCUIs.
        """
        if not rxcuis or len(rxcuis) < 2:
            return None
            
        endpoint = "/REST/interaction/list.json"
        params = {
            'rxcuis': " ".join(rxcuis)
        }
        
        return self._make_request(endpoint, params)

    @functools.lru_cache(maxsize=512)
    def search_drug_names(self, query: str) -> List[Dict[str, str]]:
        """
        Search for drugs by name and return list of {name, rxcui}.
        Uses /REST/drugs.json which is better for finding actual drug products.
        """
        endpoint = "/REST/drugs.json"
        params = {'name': query}
        
        response_data = self._make_request(endpoint, params)
        results = []
        if not response_data:
            return results
            
        if ('drugGroup' in response_data and 
            'conceptGroup' in response_data['drugGroup']):
            groups = response_data['drugGroup']['conceptGroup']
            for group in groups:
                if 'conceptProperties' in group:
                    props = group['conceptProperties']
                    if not isinstance(props, list):
                        props = [props]
                    for p in props:
                        results.append({
                            'name': p.get('name'),
                            'rxcui': p.get('rxcui'),
                            'synonym': p.get('synonym')
                        })
        return results
    
    @functools.lru_cache(maxsize=512)
    def get_drug_classes_by_name(self, drug_name: str, rela_source: str = "ATC") -> Optional[List[Dict]]:
        """
        Get drug classes for a drug by name using RxClass API
        
        Args:
            drug_name: Name of the drug
            rela_source: Source of drug-class relationships (ATC, MESH, FMTSME, etc.)
            
        Returns:
            List of drug class information or None if not found
        """
        endpoint = "/REST/rxclass/class/byDrugName.json"
        params = {
            'drugName': drug_name,
            'relaSource': rela_source,
            'relas': 'ALL'
        }
        
        response_data = self._make_request(endpoint, params)
        if not response_data:
            return None
        
        # Extract class information
        classes = []
        if 'rxclassDrugInfoList' in response_data and 'rxclassDrugInfo' in response_data['rxclassDrugInfoList']:
            drug_info_list = response_data['rxclassDrugInfoList']['rxclassDrugInfo']
            if not isinstance(drug_info_list, list):
                drug_info_list = [drug_info_list]
            
            for drug_info in drug_info_list:
                if 'rxclassMinConceptItem' in drug_info:
                    class_info = drug_info['rxclassMinConceptItem']
                    classes.append({
                        'class_id': class_info.get('classId', ''),
                        'class_name': class_info.get('className', ''),
                        'class_type': class_info.get('classType', ''),
                        'rela_source': rela_source
                    })
        
        return classes if classes else None
    
    @functools.lru_cache(maxsize=512)
    def get_drug_classes_by_rxcui(self, rxcui: str, rela_source: str = "ATC") -> Optional[List[Dict]]:
        """
        Get drug classes for a drug by RXCUI using RxClass API
        
        Args:
            rxcui: RxNorm Concept Unique Identifier
            rela_source: Source of drug-class relationships (ATC, MESH, FMTSME, etc.)
            
        Returns:
            List of drug class information or None if not found
        """
        endpoint = "/REST/rxclass/class/byRxcui.json"
        params = {
            'rxcui': rxcui,
            'relaSource': rela_source,
            'relas': 'ALL'
        }
        
        response_data = self._make_request(endpoint, params)
        if not response_data:
            return None
        
        # Extract class information
        classes = []
        if 'rxclassDrugInfoList' in response_data and 'rxclassDrugInfo' in response_data['rxclassDrugInfoList']:
            drug_info_list = response_data['rxclassDrugInfoList']['rxclassDrugInfo']
            if not isinstance(drug_info_list, list):
                drug_info_list = [drug_info_list]
            
            for drug_info in drug_info_list:
                if 'rxclassMinConceptItem' in drug_info:
                    class_info = drug_info['rxclassMinConceptItem']
                    classes.append({
                        'class_id': class_info.get('classId', ''),
                        'class_name': class_info.get('className', ''),
                        'class_type': class_info.get('classType', ''),
                        'rela_source': rela_source
                    })
        
        return classes if classes else None
    
    @functools.lru_cache(maxsize=512)
    def get_therapeutic_class(self, drug_name: str) -> Optional[Dict]:
        """
        Get therapeutic class information for a drug
        
        Args:
            drug_name: Name of the drug
            
        Returns:
            Dictionary with therapeutic class information
        """
        # Step 1: Get RXCUI
        rxcuis = self.find_rxcui_by_name(drug_name)
        if not rxcuis:
            logger.warning(f"No RXCUI found for drug: {drug_name}")
            return None
        
        # Use the first RXCUI found
        rxcui = rxcuis[0]
        
        # Step 2: Get drug classes using multiple sources
        all_classes = {}
        sources = ["ATC", "MESH", "FMTSME"]  # Try multiple sources
        
        for source in sources:
            classes = self.get_drug_classes_by_rxcui(rxcui, source)
            if classes:
                all_classes[source] = classes
        
        if not all_classes:
            logger.warning(f"No therapeutic classes found for drug: {drug_name} (RXCUI: {rxcui})")
            return None
        
        return {
            'drug_name': drug_name,
            'rxcui': rxcui,
            'therapeutic_classes': all_classes,
            'primary_therapeutic_class': self._extract_primary_class(all_classes)
        }

    def _extract_primary_class(self, all_classes: Dict) -> Optional[str]:
        """
        Extract the primary therapeutic class from multiple sources
        
        Args:
            all_classes: Dictionary of classes from different sources
            
        Returns:
            Primary therapeutic class name
        """
        # Prioritize ATC classes as they are most commonly used for therapeutic classification
        if "ATC" in all_classes and all_classes["ATC"]:
            # Get the most specific ATC class (usually the longest class name)
            atc_classes = all_classes["ATC"]
            longest_class = max(atc_classes, key=lambda x: len(x.get('class_name', '')))
            return longest_class.get('class_name', '')
        
        # Fallback to other sources
        for source in ["MESH", "FMTSME"]:
            if source in all_classes and all_classes[source]:
                return all_classes[source][0].get('class_name', '')
        
        return None
    
    def compare_therapeutic_classes(self, drug1_name: str, drug2_name: str) -> Dict:
        """
        Compare therapeutic classes between two drugs
        
        Args:
            drug1_name: Name of first drug
            drug2_name: Name of second drug
            
        Returns:
            Dictionary with comparison results
        """
        drug1_info = self.get_therapeutic_class(drug1_name)
        drug2_info = self.get_therapeutic_class(drug2_name)
        
        if not drug1_info or not drug2_info:
            return {
                'same_therapeutic_class': False,
                'drug1_info': drug1_info,
                'drug2_info': drug2_info,
                'matching_classes': [],
                'error': 'Could not retrieve therapeutic class information for one or both drugs'
            }
        
        # Find matching classes
        matching_classes = []
        drug1_classes = drug1_info.get('therapeutic_classes', {})
        drug2_classes = drug2_info.get('therapeutic_classes', {})
        
        # Compare classes across all sources
        for source in drug1_classes:
            if source in drug2_classes:
                drug1_source_classes = {cls['class_id'] for cls in drug1_classes[source]}
                drug2_source_classes = {cls['class_id'] for cls in drug2_classes[source]}
                
                common_class_ids = drug1_source_classes.intersection(drug2_source_classes)
                for class_id in common_class_ids:
                    # Find the class name
                    for cls in drug1_classes[source]:
                        if cls['class_id'] == class_id:
                            matching_classes.append({
                                'source': source,
                                'class_id': class_id,
                                'class_name': cls['class_name']
                            })
                            break
        
        return {
            'same_therapeutic_class': len(matching_classes) > 0,
            'drug1_info': drug1_info,
            'drug2_info': drug2_info,
            'matching_classes': matching_classes,
            'primary_class_match': (
                drug1_info.get('primary_therapeutic_class') == 
                drug2_info.get('primary_therapeutic_class')
            ) if drug1_info.get('primary_therapeutic_class') and drug2_info.get('primary_therapeutic_class') else False
        }


class TherapeuticClassFilter:
    """Filter drug alternatives based on therapeutic class matching"""
    
    def __init__(self, rxnorm_api: RxNormAPI):
        self.rxnorm_api = rxnorm_api
        self._cache = {}  # Cache therapeutic class results
    
    def filter_alternatives_by_therapeutic_class(self, 
                                               search_drug: str, 
                                               alternatives: List[Dict]) -> List[Dict]:
        """
        Filter alternatives to only include drugs with the same therapeutic class
        (Optimized batch processing version)
        """
        # logger.info(f"Starting therapeutic filtering for search drug: {search_drug}")
        # logger.info(f"Number of alternatives to filter: {len(alternatives)}")

        # Get therapeutic class for search drug
        search_drug_class = self._get_cached_therapeutic_class(search_drug)
        if not search_drug_class:
            logger.warning(f"Could not determine therapeutic class for search drug: {search_drug}")
            # Return all alternatives if we can't determine the search drug's class
            for alternative in alternatives:
                alternative['therapeutic_class_info'] = {
                    'same_class': False,
                    'matching_classes': [],
                    'primary_class_match': False,
                    'therapeutic_class': 'Unknown (Search drug class not found)',
                    'error': 'Could not determine search drug therapeutic class'
                }
            return alternatives

        # logger.info(f"Search drug therapeutic class: {search_drug_class.get('primary_therapeutic_class')}")

        # Extract all unique drug names from alternatives
        drug_names = []
        for alternative in alternatives:
            drug_name = alternative.get('drug_name', '').strip()
            if drug_name and drug_name not in drug_names:
                drug_names.append(drug_name)

        # logger.info(f"Fetching therapeutic classes for {len(drug_names)} unique drugs in batch")

        # Batch fetch therapeutic classes for all alternatives
        drug_classes = self._batch_get_therapeutic_classes(drug_names)
        
        # Now filter alternatives based on therapeutic class matching
        filtered_alternatives = []
        
        for alternative in alternatives:
            drug_name = alternative.get('drug_name', '').strip()
            if not drug_name:
                logger.warning(f"Alternative has no drug_name, skipping")
                continue
                
            drug_class_info = drug_classes.get(drug_name)
            if not drug_class_info:
                logger.warning(f"Could not get therapeutic class for {drug_name}")
                alternative['therapeutic_class_info'] = {
                    'same_class': False,
                    'matching_classes': [],
                    'primary_class_match': False,
                    'therapeutic_class': 'Unknown (API error)',
                    'error': 'Could not retrieve therapeutic class'
                }
                continue
            
            # Compare therapeutic classes locally
            comparison = self._compare_therapeutic_classes_local(search_drug_class, drug_class_info)
            if comparison.get('same_therapeutic_class', False):
                logger.debug(f"{drug_name} matches therapeutic class")
                alternative['therapeutic_class_info'] = {
                    'same_class': True,
                    'matching_classes': comparison.get('matching_classes', []),
                    'primary_class_match': comparison.get('primary_class_match', False),
                    'therapeutic_class': drug_class_info.get('primary_therapeutic_class', '')
                }
                filtered_alternatives.append(alternative)
            else:
                logger.debug(f"{drug_name} does not match therapeutic class")
                alternative['therapeutic_class_info'] = {
                    'same_class': False,
                    'matching_classes': [],
                    'primary_class_match': False,
                    'therapeutic_class': drug_class_info.get('primary_therapeutic_class', 'Unknown'),
                    'search_drug_class': search_drug_class.get('primary_therapeutic_class', 'Unknown')
                }

        logger.info(f"Filtered {len(alternatives)} alternatives to {len(filtered_alternatives)} based on therapeutic class matching")

        if len(filtered_alternatives) == 0:
            logger.info("No alternatives matched therapeutic class. Returning empty list.")

        return filtered_alternatives

    def _batch_get_therapeutic_classes(self, drug_names: List[str], batch_size: int = 5) -> Dict[str, Dict]:
        """
        Batch fetch therapeutic classes for multiple drugs using parallelization and batching.
        Optimized for speed: deduplicate drug names, cache failed lookups, and reduce logging.
        Args:
            drug_names: List of drug names to fetch therapeutic classes for
            batch_size: Number of drugs per batch (default: 48)
        Returns:
            Dictionary mapping drug names to their therapeutic class information
        """
        import concurrent.futures
        from concurrent.futures import ThreadPoolExecutor
        import threading

        # Reduce logging to WARNING for performance
        logger.setLevel(logging.WARNING)

        # Deduplicate drug names for efficiency
        unique_drug_names = list(dict.fromkeys(drug_names))
        total_drugs = len(unique_drug_names)

        # Thread-safe results and failed cache
        results = {}
        failed_cache = set()
        results_lock = threading.Lock()

        def batcher(seq, size):
            for pos in range(0, len(seq), size):
                yield seq[pos:pos + size]

        def fetch_single_drug_class(drug_name: str) -> tuple:
            try:
                therapeutic_class = self._get_cached_therapeutic_class(drug_name)
                if therapeutic_class is None:
                    with results_lock:
                        failed_cache.add(drug_name)
                return drug_name, therapeutic_class
            except Exception as e:
                with results_lock:
                    failed_cache.add(drug_name)
                logger.exception(f"Exception in fetch_single_drug_class for {drug_name}: {e}")
                return drug_name, None

        batch_num = 0
        for batch in batcher(unique_drug_names, batch_size):
            batch_num += 1
            max_workers = min(24, len(batch))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_drug = {executor.submit(fetch_single_drug_class, drug_name): drug_name for drug_name in batch}
                for future in concurrent.futures.as_completed(future_to_drug):
                    drug_name = future_to_drug[future]
                    try:
                        drug_name_res, therapeutic_class = future.result(timeout=20)
                        with results_lock:
                            results[drug_name_res] = therapeutic_class
                    except concurrent.futures.TimeoutError:
                        logger.warning(f"Timeout fetching therapeutic class for {drug_name} in batch {batch_num}")
                        with results_lock:
                            results[drug_name] = None
                            failed_cache.add(drug_name)
                    except Exception as e:
                        logger.warning(f"Error fetching therapeutic class for {drug_name}: {e}")
                        with results_lock:
                            results[drug_name] = None
                            failed_cache.add(drug_name)
            logger.info(f"Processed batch {batch_num} with {len(batch)} drugs. Total processed: {min(batch_num * batch_size, total_drugs)}/{total_drugs}")
        # Map back to original input order (including duplicates)
        final_results = {name: results.get(name) for name in drug_names}
        if failed_cache:
            logger.warning(f"Therapeutic class fetch had {len(failed_cache)} failed entries (will appear as None). Examples: {list(failed_cache)[:5]}")
        # print (final_results)
        return final_results

    def       _compare_therapeutic_classes_local(self, drug1_info: Dict, drug2_info: Dict) -> Dict:
        """
        Compare therapeutic classes between two drug info dictionaries locally
        (No API calls needed)
        
        Args:
            drug1_info: Therapeutic class info for first drug
            drug2_info: Therapeutic class info for second drug
            
        Returns:
            Dictionary with comparison results
        """
        if not drug1_info or not drug2_info:
            return {
                'same_therapeutic_class': False,
                'drug1_info': drug1_info,
                'drug2_info': drug2_info,
                'matching_classes': [],
                'error': 'Missing therapeutic class information for one or both drugs'
            }
        
        # Find matching classes
        matching_classes = []
        drug1_classes = drug1_info.get('therapeutic_classes', {})
        drug2_classes = drug2_info.get('therapeutic_classes', {})
        
        # Compare classes across all sources
        for source in drug1_classes:
            if source in drug2_classes:
                drug1_source_classes = {cls['class_id'] for cls in drug1_classes[source]}
                drug2_source_classes = {cls['class_id'] for cls in drug2_classes[source]}
                
                common_class_ids = drug1_source_classes.intersection(drug2_source_classes)
                for class_id in common_class_ids:
                    # Find the class name
                    for cls in drug1_classes[source]:
                        if cls['class_id'] == class_id:
                            matching_classes.append({
                                'source': source,
                                'class_id': class_id,
                                'class_name': cls['class_name']
                            })
                            break
        
        return {
            'same_therapeutic_class': len(matching_classes) > 0,
            'drug1_info': drug1_info,
            'drug2_info': drug2_info,
            'matching_classes': matching_classes,
            'primary_class_match': (
                drug1_info.get('primary_therapeutic_class') == 
                drug2_info.get('primary_therapeutic_class')
            ) if drug1_info.get('primary_therapeutic_class') and drug2_info.get('primary_therapeutic_class') else False
        }
    
    def _get_cached_therapeutic_class(self, drug_name: str, max_retries :int = 1) -> Optional[Dict]:
        """Get therapeutic class with enhanced caching and minimal logging for performance"""
        if drug_name in self._cache:
            if self._cache[drug_name] is not None:
                logger.debug(f"Cache HIT for {drug_name}")
                return self._cache[drug_name]
            else:
                logger.debug(f"Cache MISS for {drug_name}, fetching from API...")
        
        attempt = 1
        while attempt <= max_retries:
            logger.debug(f"Fetching therapeutic class for {drug_name} (attempt {attempt}/{max_retries + 1})")
            result = self.rxnorm_api.get_therapeutic_class(drug_name)
            if result is not None:
                logger.debug(f"Successfully fetched therapeutic class for {drug_name} on attempt {attempt}")
                self._cache[drug_name] = result
                return result
            else:
                logger.warning(f"Failed to fetch therapeutic class for {drug_name} on attempt {attempt}")
                attempt += 1
                # time.sleep(0.1 * (2 ** attempt))  # Aggressive backoff: 0.1s, 0.2s, 0.4s
        # if result:
        #     logger.debug(f"Successfully cached therapeutic class for {drug_name}")
        # else:
        #     logger.debug(f"Failed to fetch therapeutic class for {drug_name}, caching None")
        self._cache[drug_name] = None
        return None
        # return result
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics for monitoring performance"""
        return {
            'cache_size': len(self._cache),
            'cached_drugs': list(self._cache.keys()),
            'successful_entries': len([k for k, v in self._cache.items() if v is not None]),
            'failed_entries': len([k for k, v in self._cache.items() if v is None])
        }
    
    def clear_cache(self) -> None:
        """Clear the therapeutic class cache"""
        cache_size = len(self._cache)
        self._cache.clear()
        logger.info(f"🗑️ Cleared therapeutic class cache ({cache_size} entries removed)")
