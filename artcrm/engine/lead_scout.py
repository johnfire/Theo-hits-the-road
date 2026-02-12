"""
Lead Scout - Automated Lead Generation
Discovers galleries, cafes, and co-working spaces in cities.
Uses Google Maps API, OpenStreetMap, and web scraping.
"""

import logging
import time
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Literal
from dataclasses import dataclass

import requests
from tqdm import tqdm

try:
    import googlemaps
    GOOGLE_MAPS_AVAILABLE = True
except ImportError:
    GOOGLE_MAPS_AVAILABLE = False
    logging.warning("googlemaps library not installed. Google Maps API will not be available.")

from artcrm.engine import crm, ai_planner
from artcrm.engine.email_composer import call_claude
from artcrm.models import Contact
from artcrm.bus.events import bus, EVENT_CONTACT_CREATED
from artcrm.config import config

logger = logging.getLogger(__name__)

# Scout results storage
SCOUT_DIR = Path(__file__).parent.parent.parent / "data" / "scout_results"
SCOUT_DIR.mkdir(exist_ok=True, parents=True)


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class LeadCandidate:
    """Represents a potential venue before insertion into database."""
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    type: Optional[str] = None  # gallery, cafe, coworking
    subtype: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    confidence_score: int = 50  # 0-100, higher = more confident data is accurate
    source: str = 'unknown'  # google_maps, osm, web_scrape
    raw_data: Optional[Dict[str, Any]] = None


# =============================================================================
# GOOGLE MAPS API
# =============================================================================

def search_google_maps(
    city: str,
    country: str,
    business_type: str,
    radius_km: float = 10.0
) -> List[LeadCandidate]:
    """
    Search Google Maps Places API for businesses.

    Args:
        city: City name (e.g., "Rosenheim")
        country: Country code (e.g., "DE")
        business_type: Type of business (gallery, cafe, coworking)
        radius_km: Search radius in kilometers

    Returns: List of LeadCandidate objects
    """
    if not GOOGLE_MAPS_AVAILABLE:
        logger.warning("Google Maps library not available. Skipping Google Maps search.")
        return []

    if not config.GOOGLE_MAPS_API_KEY:
        logger.warning("GOOGLE_MAPS_API_KEY not set. Skipping Google Maps search.")
        return []

    logger.info(f"Searching Google Maps for {business_type} in {city}, {country}")

    try:
        gmaps = googlemaps.Client(key=config.GOOGLE_MAPS_API_KEY)

        # Map our types to Google Places types
        type_mapping = {
            'gallery': 'art_gallery',
            'cafe': 'cafe',
            'coworking': 'coworking_space'
        }

        places_type = type_mapping.get(business_type, business_type)
        query = f"{places_type} in {city}, {country}"

        # Text search for places
        results = gmaps.places(query=query, type=places_type)

        candidates = []

        for place in results.get('results', []):
            # Get detailed place info
            place_id = place.get('place_id')
            details = gmaps.place(place_id=place_id, fields=[
                'name', 'formatted_address', 'website', 'formatted_phone_number',
                'geometry', 'types', 'business_status'
            ])

            place_details = details.get('result', {})

            # Skip closed businesses
            if place_details.get('business_status') == 'CLOSED_PERMANENTLY':
                continue

            # Extract address components
            address = place_details.get('formatted_address', '')
            geometry = place_details.get('geometry', {}).get('location', {})

            candidate = LeadCandidate(
                name=place_details.get('name', ''),
                address=address,
                city=city,
                country=country,
                website=place_details.get('website'),
                phone=place_details.get('formatted_phone_number'),
                type=business_type,
                latitude=geometry.get('lat'),
                longitude=geometry.get('lng'),
                confidence_score=90,  # Google Maps data is high quality
                source='google_maps',
                raw_data=place_details
            )

            candidates.append(candidate)

            # Rate limiting
            time.sleep(config.LEAD_SCOUT_RATE_LIMIT_SECONDS)

        logger.info(f"Found {len(candidates)} {business_type} venues via Google Maps")
        return candidates

    except Exception as e:
        logger.error(f"Google Maps API error: {e}")
        return []


# =============================================================================
# OPENSTREETMAP API
# =============================================================================

def search_openstreetmap(
    city: str,
    country: str,
    business_type: str
) -> List[LeadCandidate]:
    """
    Search OpenStreetMap Overpass API for businesses.
    Free, open data source as fallback.

    Args:
        city: City name
        country: Country code
        business_type: Type of business

    Returns: List of LeadCandidate objects
    """
    logger.info(f"Searching OpenStreetMap for {business_type} in {city}, {country}")

    # Map our types to OSM tags
    osm_queries = {
        'gallery': '["tourism"="gallery"]',
        'cafe': '["amenity"="cafe"]',
        'coworking': '["office"="coworking"]'
    }

    osm_query = osm_queries.get(business_type, '["amenity"="*"]')

    # Overpass API query
    overpass_url = "http://overpass-api.de/api/interpreter"
    overpass_query = f"""
    [out:json][timeout:25];
    area["name"="{city}"]["admin_level"~"[4-8]"]->.searchArea;
    (
      node{osm_query}(area.searchArea);
      way{osm_query}(area.searchArea);
      relation{osm_query}(area.searchArea);
    );
    out center;
    """

    try:
        response = requests.post(overpass_url, data={'data': overpass_query}, timeout=30)
        response.raise_for_status()

        data = response.json()
        candidates = []

        for element in data.get('elements', []):
            tags = element.get('tags', {})

            # Extract coordinates (center for ways/relations)
            if element.get('type') == 'node':
                lat = element.get('lat')
                lon = element.get('lon')
            else:
                center = element.get('center', {})
                lat = center.get('lat')
                lon = center.get('lon')

            # Extract address components
            addr_street = tags.get('addr:street', '')
            addr_housenumber = tags.get('addr:housenumber', '')
            address = f"{addr_street} {addr_housenumber}".strip() if addr_street else None

            candidate = LeadCandidate(
                name=tags.get('name', f"Unnamed {business_type}"),
                address=address,
                city=tags.get('addr:city', city),
                country=country,
                website=tags.get('website') or tags.get('contact:website'),
                email=tags.get('email') or tags.get('contact:email'),
                phone=tags.get('phone') or tags.get('contact:phone'),
                type=business_type,
                latitude=lat,
                longitude=lon,
                confidence_score=70,  # OSM data quality varies
                source='openstreetmap',
                raw_data=element
            )

            candidates.append(candidate)

        logger.info(f"Found {len(candidates)} {business_type} venues via OpenStreetMap")
        return candidates

    except Exception as e:
        logger.error(f"OpenStreetMap API error: {e}")
        return []


# =============================================================================
# AI ENRICHMENT
# =============================================================================

def enrich_with_ai(
    candidate: LeadCandidate,
    model: Literal['claude', 'ollama'] = 'ollama'
) -> LeadCandidate:
    """
    Use AI to infer missing data and categorize venue.

    Args:
        candidate: LeadCandidate to enrich
        model: Which AI model to use

    Returns: Enriched LeadCandidate
    """
    # Build context for AI
    context_parts = [
        f"Business name: {candidate.name}",
        f"Type: {candidate.type or 'unknown'}",
        f"City: {candidate.city or 'unknown'}",
    ]

    if candidate.website:
        context_parts.append(f"Website: {candidate.website}")
    if candidate.address:
        context_parts.append(f"Address: {candidate.address}")

    context = "\n".join(context_parts)

    prompt = f"""Analyze this business and provide categorization.

{context}

Based on the name, location, and any available details, determine:
1. SUBTYPE: What kind of venue is this? Options: upscale, hippy, commercial, alternative, contemporary, traditional, corporate, indie, boutique, chain
2. FIT_SCORE: How well does this venue fit an artist showing paintings (watercolor, oil, acrylic, landscapes, cityscapes)? Score 0-100.
3. CONFIDENCE: How confident are you in this assessment? 0-100

Format as:
SUBTYPE: [your answer]
FIT_SCORE: [0-100]
CONFIDENCE: [0-100]
REASONING: [1-2 sentences]"""

    try:
        if model == 'claude':
            response = call_claude(prompt, max_tokens=500)
        else:
            from artcrm.engine.ai_planner import call_ollama
            response = call_ollama(prompt)

        # Parse response
        lines = response.split('\n')
        for line in lines:
            if line.startswith('SUBTYPE:'):
                subtype = line.split(':', 1)[1].strip().lower()
                if subtype and subtype != 'unknown':
                    candidate.subtype = subtype
            elif line.startswith('FIT_SCORE:'):
                try:
                    fit_score = int(''.join(filter(str.isdigit, line.split(':')[1])))
                    candidate.confidence_score = max(0, min(100, fit_score))
                except:
                    pass

        logger.debug(f"Enriched {candidate.name}: subtype={candidate.subtype}, confidence={candidate.confidence_score}")

    except Exception as e:
        logger.error(f"AI enrichment error for {candidate.name}: {e}")

    return candidate


# =============================================================================
# DEDUPLICATION & INSERTION
# =============================================================================

def check_duplicate(candidate: LeadCandidate) -> Optional[Contact]:
    """
    Check if candidate already exists in database.
    Uses name+city matching (existing dedup logic).

    Returns: Existing Contact if found, None otherwise
    """
    existing = crm.search_contacts(name=candidate.name, city=candidate.city, limit=5)

    # Exact match check
    for contact in existing:
        if contact.name.lower() == candidate.name.lower():
            return contact

    return None


def insert_lead(candidate: LeadCandidate, skip_if_exists: bool = True) -> Optional[int]:
    """
    Insert lead candidate into database.

    Args:
        candidate: LeadCandidate to insert
        skip_if_exists: If True, skip existing contacts

    Returns: Contact ID if inserted, None if skipped
    """
    # Check for duplicates
    existing = check_duplicate(candidate)
    if existing:
        if skip_if_exists:
            logger.debug(f"Skipping duplicate: {candidate.name} (ID: {existing.id})")
            return None
        else:
            logger.info(f"Updating existing contact: {candidate.name} (ID: {existing.id})")
            # Update only if fields are empty
            updates = {}
            if not existing.website and candidate.website:
                updates['website'] = candidate.website
            if not existing.email and candidate.email:
                updates['email'] = candidate.email
            if not existing.phone and candidate.phone:
                updates['phone'] = candidate.phone
            if not existing.address and candidate.address:
                updates['address'] = candidate.address

            if updates:
                crm.update_contact(existing.id, updates)

            return existing.id

    # Create new contact
    contact = Contact(
        name=candidate.name,
        type=candidate.type,
        subtype=candidate.subtype,
        city=candidate.city,
        country=candidate.country,
        address=candidate.address,
        website=candidate.website,
        email=candidate.email,
        phone=candidate.phone,
        status='lead_unverified',  # Special status for scouted leads
        fit_score=candidate.confidence_score if candidate.confidence_score > 50 else None,
        preferred_language='de',  # Default for Germany/Bavaria
        notes=f"Auto-discovered via {candidate.source} on {datetime.now().date()}"
    )

    contact_id = crm.create_contact(contact)
    logger.info(f"Created new lead: {candidate.name} (ID: {contact_id})")

    return contact_id


# =============================================================================
# MAIN SCOUT FUNCTION
# =============================================================================

def scout_city(
    city: str,
    country: str = 'DE',
    business_types: Optional[List[str]] = None,
    radius_km: float = 10.0,
    ai_model: Literal['claude', 'ollama'] = 'ollama',
    use_google_maps: bool = True,
    use_osm: bool = True,
    skip_duplicates: bool = True
) -> Dict[str, Any]:
    """
    Scout a city for leads: galleries, cafes, co-working spaces.

    Args:
        city: City name (e.g., "Rosenheim")
        country: Country code (e.g., "DE")
        business_types: List of types to search (default: gallery, cafe, coworking)
        radius_km: Search radius in km
        ai_model: Which AI model to use for enrichment
        use_google_maps: Use Google Maps API
        use_osm: Use OpenStreetMap as fallback
        skip_duplicates: Skip existing contacts

    Returns: Dict with summary stats
    """
    if business_types is None:
        business_types = ['gallery', 'cafe', 'coworking']

    logger.info(f"Starting scout mission for {city}, {country}")
    logger.info(f"Target types: {', '.join(business_types)}")

    all_candidates = []
    stats = {
        'city': city,
        'country': country,
        'types_searched': business_types,
        'sources_used': [],
        'total_found': 0,
        'total_inserted': 0,
        'total_skipped': 0,
        'by_type': {},
        'timestamp': datetime.now().isoformat()
    }

    # Search each business type
    for biz_type in business_types:
        logger.info(f"Searching for {biz_type} venues...")

        candidates = []

        # Try Google Maps first
        if use_google_maps:
            gm_results = search_google_maps(city, country, biz_type, radius_km)
            candidates.extend(gm_results)
            if gm_results and 'google_maps' not in stats['sources_used']:
                stats['sources_used'].append('google_maps')

        # Fall back to OpenStreetMap
        if use_osm and len(candidates) < 5:  # OSM as backup if Google didn't find much
            osm_results = search_openstreetmap(city, country, biz_type)
            candidates.extend(osm_results)
            if osm_results and 'openstreetmap' not in stats['sources_used']:
                stats['sources_used'].append('openstreetmap')

        stats['by_type'][biz_type] = len(candidates)
        all_candidates.extend(candidates)

    stats['total_found'] = len(all_candidates)

    # Enrich with AI (batch processing)
    logger.info(f"Enriching {len(all_candidates)} candidates with AI ({ai_model})...")

    enriched = []
    for candidate in tqdm(all_candidates, desc="AI enrichment", unit="venue"):
        enriched_candidate = enrich_with_ai(candidate, model=ai_model)
        enriched.append(enriched_candidate)
        time.sleep(config.LEAD_SCOUT_RATE_LIMIT_SECONDS)

    # Insert into database (batch processing)
    logger.info("Inserting leads into database...")

    inserted_ids = []
    for candidate in tqdm(enriched, desc="Inserting leads", unit="lead"):
        contact_id = insert_lead(candidate, skip_if_exists=skip_duplicates)
        if contact_id:
            inserted_ids.append(contact_id)
        else:
            stats['total_skipped'] += 1

    stats['total_inserted'] = len(inserted_ids)

    # Save raw results to JSON
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    results_file = SCOUT_DIR / f"scout_{city}_{country}_{timestamp}.json"

    results_data = {
        'stats': stats,
        'candidates': [
            {
                'name': c.name,
                'address': c.address,
                'city': c.city,
                'type': c.type,
                'subtype': c.subtype,
                'website': c.website,
                'email': c.email,
                'phone': c.phone,
                'confidence_score': c.confidence_score,
                'source': c.source,
                'raw_data': c.raw_data
            }
            for c in enriched
        ],
        'inserted_ids': inserted_ids
    }

    results_file.write_text(json.dumps(results_data, indent=2, default=str))
    logger.info(f"Scout results saved to {results_file}")

    # Emit event
    bus.emit('scout_complete', {
        'city': city,
        'country': country,
        'total_found': stats['total_found'],
        'total_inserted': stats['total_inserted'],
        'results_file': str(results_file)
    })

    return stats
