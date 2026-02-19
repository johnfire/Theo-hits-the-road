"""
Unit tests for the Lead Scout (artcrm/engine/lead_scout.py).

Mocking strategy:
- artcrm.engine.lead_scout.GOOGLE_MAPS_AVAILABLE  → bool patch for import guard
- artcrm.engine.lead_scout.googlemaps             → Google Maps client
- requests.post                                   → Overpass HTTP
- artcrm.engine.lead_scout.call_ai                → AI calls (all models)
- artcrm.engine.lead_scout.crm.*                  → all DB-touching crm calls
- artcrm.engine.lead_scout.SCOUT_DIR              → tmp_path
- time.sleep                                      → no-op
- tqdm                                            → passthrough
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from artcrm.models import Contact
from artcrm.engine.lead_scout import (
    LeadCandidate,
    search_google_maps,
    search_openstreetmap,
    enrich_with_ai,
    check_duplicate,
    insert_lead,
    scout_city,
)


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

SAMPLE_CANDIDATE = LeadCandidate(
    name='Galerie am Stadtpark',
    city='Augsburg',
    country='DE',
    type='gallery',
    source='openstreetmap',
)

SAMPLE_CONTACT = Contact(
    id=1, name='Galerie am Stadtpark', type='gallery',
    city='Augsburg', country='DE', status='cold', preferred_language='de',
)

OSM_RESPONSE_NODE = {
    'elements': [
        {
            'type': 'node',
            'lat': 48.3705,
            'lon': 10.8978,
            'tags': {
                'name': 'Galerie am See',
                'addr:street': 'Seestraße',
                'addr:housenumber': '12',
                'addr:city': 'Augsburg',
                'website': 'https://galerie-see.de',
                'email': 'info@galerie-see.de',
                'phone': '+49 821 123456',
            }
        }
    ]
}

OSM_RESPONSE_WAY = {
    'elements': [
        {
            'type': 'way',
            'center': {'lat': 48.370, 'lon': 10.897},
            'tags': {
                'name': 'Cafe Mitte',
            }
        }
    ]
}


def mock_osm_response(data: dict):
    resp = MagicMock()
    resp.json.return_value = data
    resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# LeadCandidate dataclass
# ---------------------------------------------------------------------------

def test_lead_candidate_default_confidence_score():
    c = LeadCandidate(name='Test')
    assert c.confidence_score == 50


def test_lead_candidate_default_source():
    c = LeadCandidate(name='Test')
    assert c.source == 'unknown'


def test_lead_candidate_stores_fields():
    c = LeadCandidate(
        name='Gallery X', city='München', country='DE',
        type='gallery', source='google_maps', confidence_score=90,
    )
    assert c.name == 'Gallery X'
    assert c.source == 'google_maps'
    assert c.confidence_score == 90


# ---------------------------------------------------------------------------
# search_google_maps
# ---------------------------------------------------------------------------

def test_search_google_maps_returns_empty_when_library_unavailable():
    with patch('artcrm.engine.lead_scout.GOOGLE_MAPS_AVAILABLE', False):
        result = search_google_maps('Augsburg', 'DE', 'gallery')
    assert result == []


def test_search_google_maps_returns_empty_when_no_api_key():
    with patch('artcrm.engine.lead_scout.GOOGLE_MAPS_AVAILABLE', True), \
         patch('artcrm.engine.lead_scout.config.GOOGLE_MAPS_API_KEY', ''):
        result = search_google_maps('Augsburg', 'DE', 'gallery')
    assert result == []


def test_search_google_maps_returns_candidates():
    mock_place_details = {
        'name': 'Galerie Stern',
        'formatted_address': 'Maximilianstr. 1, Augsburg',
        'website': 'https://galerie-stern.de',
        'formatted_phone_number': '+49 821 999',
        'geometry': {'location': {'lat': 48.37, 'lng': 10.89}},
        'business_status': 'OPERATIONAL',
    }
    mock_gmaps = MagicMock()
    mock_gmaps.places.return_value = {'results': [{'place_id': 'abc123'}]}
    mock_gmaps.place.return_value = {'result': mock_place_details}

    with patch('artcrm.engine.lead_scout.GOOGLE_MAPS_AVAILABLE', True), \
         patch('artcrm.engine.lead_scout.config.GOOGLE_MAPS_API_KEY', 'key123'), \
         patch('artcrm.engine.lead_scout.googlemaps.Client', return_value=mock_gmaps), \
         patch('time.sleep'):
        result = search_google_maps('Augsburg', 'DE', 'gallery')

    assert len(result) == 1
    assert result[0].name == 'Galerie Stern'
    assert result[0].source == 'google_maps'
    assert result[0].confidence_score == 90


def test_search_google_maps_skips_permanently_closed():
    mock_place_details = {
        'name': 'Closed Gallery',
        'formatted_address': 'Nowhere St',
        'geometry': {'location': {'lat': 0, 'lng': 0}},
        'business_status': 'CLOSED_PERMANENTLY',
    }
    mock_gmaps = MagicMock()
    mock_gmaps.places.return_value = {'results': [{'place_id': 'xyz'}]}
    mock_gmaps.place.return_value = {'result': mock_place_details}

    with patch('artcrm.engine.lead_scout.GOOGLE_MAPS_AVAILABLE', True), \
         patch('artcrm.engine.lead_scout.config.GOOGLE_MAPS_API_KEY', 'key'), \
         patch('artcrm.engine.lead_scout.googlemaps.Client', return_value=mock_gmaps), \
         patch('time.sleep'):
        result = search_google_maps('Augsburg', 'DE', 'gallery')

    assert result == []


def test_search_google_maps_returns_empty_on_exception():
    mock_gmaps = MagicMock()
    mock_gmaps.places.side_effect = Exception('API error')

    with patch('artcrm.engine.lead_scout.GOOGLE_MAPS_AVAILABLE', True), \
         patch('artcrm.engine.lead_scout.config.GOOGLE_MAPS_API_KEY', 'key'), \
         patch('artcrm.engine.lead_scout.googlemaps.Client', return_value=mock_gmaps), \
         patch('time.sleep'):
        result = search_google_maps('Augsburg', 'DE', 'gallery')

    assert result == []


# ---------------------------------------------------------------------------
# search_openstreetmap
# ---------------------------------------------------------------------------

def test_search_osm_returns_candidates_from_nodes():
    with patch('requests.post', return_value=mock_osm_response(OSM_RESPONSE_NODE)):
        result = search_openstreetmap('Augsburg', 'DE', 'gallery')

    assert len(result) == 1
    assert result[0].name == 'Galerie am See'
    assert result[0].source == 'openstreetmap'
    assert result[0].confidence_score == 70
    assert result[0].latitude == 48.3705
    assert result[0].longitude == 10.8978


def test_search_osm_extracts_contact_details():
    with patch('requests.post', return_value=mock_osm_response(OSM_RESPONSE_NODE)):
        result = search_openstreetmap('Augsburg', 'DE', 'gallery')

    assert result[0].website == 'https://galerie-see.de'
    assert result[0].email == 'info@galerie-see.de'
    assert result[0].phone == '+49 821 123456'


def test_search_osm_builds_address_from_street_and_number():
    with patch('requests.post', return_value=mock_osm_response(OSM_RESPONSE_NODE)):
        result = search_openstreetmap('Augsburg', 'DE', 'gallery')

    assert result[0].address == 'Seestraße 12'


def test_search_osm_uses_center_coords_for_way_elements():
    with patch('requests.post', return_value=mock_osm_response(OSM_RESPONSE_WAY)):
        result = search_openstreetmap('Augsburg', 'DE', 'cafe')

    assert result[0].latitude == 48.370
    assert result[0].longitude == 10.897


def test_search_osm_returns_empty_on_request_error():
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception('timeout')
    with patch('requests.post', return_value=mock_resp):
        result = search_openstreetmap('Augsburg', 'DE', 'gallery')

    assert result == []


def test_search_osm_posts_to_overpass_url():
    with patch('requests.post', return_value=mock_osm_response({'elements': []})) as mock_post:
        search_openstreetmap('Augsburg', 'DE', 'gallery')

    url = mock_post.call_args[0][0]
    assert 'overpass-api.de' in url


def test_search_osm_uses_verify_true():
    with patch('requests.post', return_value=mock_osm_response({'elements': []})) as mock_post:
        search_openstreetmap('Augsburg', 'DE', 'gallery')

    assert mock_post.call_args[1].get('verify') is True


def test_search_osm_unnamed_fallback():
    data = {'elements': [{'type': 'node', 'lat': 0, 'lon': 0, 'tags': {}}]}
    with patch('requests.post', return_value=mock_osm_response(data)):
        result = search_openstreetmap('Augsburg', 'DE', 'gallery')

    assert 'Unnamed' in result[0].name


# ---------------------------------------------------------------------------
# enrich_with_ai
# ---------------------------------------------------------------------------

AI_ENRICH_RESPONSE = "SUBTYPE: contemporary\nFIT_SCORE: 80\nCONFIDENCE: 75\nREASONING: Good fit."


def test_enrich_with_ai_deepseek_sets_subtype():
    candidate = LeadCandidate(name='Gallery X', type='gallery', city='Augsburg')
    with patch('artcrm.engine.lead_scout.call_ai', return_value=AI_ENRICH_RESPONSE):
        result = enrich_with_ai(candidate, model='deepseek-chat')
    assert result.subtype == 'contemporary'


def test_enrich_with_ai_claude_calls_call_ai():
    candidate = LeadCandidate(name='Gallery X', type='gallery', city='Augsburg')
    with patch('artcrm.engine.lead_scout.call_ai', return_value=AI_ENRICH_RESPONSE) as mock_ai:
        enrich_with_ai(candidate, model='claude')
    mock_ai.assert_called_once()


def test_enrich_with_ai_updates_confidence_score():
    candidate = LeadCandidate(name='Gallery X', type='gallery', city='Augsburg')
    with patch('artcrm.engine.lead_scout.call_ai', return_value=AI_ENRICH_RESPONSE):
        result = enrich_with_ai(candidate, model='deepseek-chat')
    assert result.confidence_score == 80


def test_enrich_with_ai_clamps_confidence_above_100():
    response = "SUBTYPE: upscale\nFIT_SCORE: 150\nREASONING: Perfect."
    candidate = LeadCandidate(name='Gallery X', type='gallery', city='Augsburg')
    with patch('artcrm.engine.lead_scout.call_ai', return_value=response):
        result = enrich_with_ai(candidate, model='deepseek-chat')
    assert result.confidence_score == 100


def test_enrich_with_ai_returns_candidate_unchanged_on_error():
    candidate = LeadCandidate(name='Gallery X', type='gallery', city='Augsburg', confidence_score=50)
    with patch('artcrm.engine.lead_scout.call_ai', side_effect=RuntimeError('down')):
        result = enrich_with_ai(candidate, model='deepseek-chat')
    assert result.confidence_score == 50
    assert result.subtype is None


def test_enrich_with_ai_skips_unknown_subtype():
    response = "SUBTYPE: unknown\nFIT_SCORE: 60\nREASONING: Unclear."
    candidate = LeadCandidate(name='Gallery X', type='gallery', city='Augsburg')
    with patch('artcrm.engine.lead_scout.call_ai', return_value=response):
        result = enrich_with_ai(candidate, model='deepseek-chat')
    assert result.subtype is None


def test_enrich_with_ai_includes_website_in_context():
    candidate = LeadCandidate(name='Gallery X', type='gallery', city='Augsburg',
                              website='https://gallery-x.de')
    with patch('artcrm.engine.lead_scout.call_ai', return_value=AI_ENRICH_RESPONSE) as mock_ai:
        enrich_with_ai(candidate, model='deepseek-chat')
    prompt = mock_ai.call_args[0][0]
    assert 'gallery-x.de' in prompt


# ---------------------------------------------------------------------------
# check_duplicate
# ---------------------------------------------------------------------------

def test_check_duplicate_returns_none_when_no_match():
    with patch('artcrm.engine.lead_scout.crm.search_contacts', return_value=[]):
        result = check_duplicate(SAMPLE_CANDIDATE)
    assert result is None


def test_check_duplicate_returns_contact_on_exact_match():
    with patch('artcrm.engine.lead_scout.crm.search_contacts', return_value=[SAMPLE_CONTACT]):
        result = check_duplicate(SAMPLE_CANDIDATE)
    assert result == SAMPLE_CONTACT


def test_check_duplicate_is_case_insensitive():
    candidate = LeadCandidate(name='galerie am stadtpark', city='Augsburg', type='gallery')
    with patch('artcrm.engine.lead_scout.crm.search_contacts', return_value=[SAMPLE_CONTACT]):
        result = check_duplicate(candidate)
    assert result == SAMPLE_CONTACT


def test_check_duplicate_returns_none_on_partial_match_only():
    other_contact = Contact(id=2, name='Galerie am Stadtpark Nord', city='Augsburg',
                            status='cold', preferred_language='de')
    with patch('artcrm.engine.lead_scout.crm.search_contacts', return_value=[other_contact]):
        result = check_duplicate(SAMPLE_CANDIDATE)
    assert result is None


# ---------------------------------------------------------------------------
# insert_lead
# ---------------------------------------------------------------------------

def test_insert_lead_skips_duplicate_when_skip_is_true():
    with patch('artcrm.engine.lead_scout.check_duplicate', return_value=SAMPLE_CONTACT):
        result = insert_lead(SAMPLE_CANDIDATE, skip_if_exists=True)
    assert result is None


def test_insert_lead_returns_existing_id_when_skip_false():
    with patch('artcrm.engine.lead_scout.check_duplicate', return_value=SAMPLE_CONTACT), \
         patch('artcrm.engine.lead_scout.crm.update_contact', return_value=True):
        result = insert_lead(SAMPLE_CANDIDATE, skip_if_exists=False)
    assert result == SAMPLE_CONTACT.id


def test_insert_lead_updates_empty_fields_on_existing():
    existing = Contact(id=1, name='Galerie am Stadtpark', city='Augsburg',
                       website=None, email=None, phone=None, address=None,
                       status='cold', preferred_language='de')
    candidate = LeadCandidate(name='Galerie am Stadtpark', city='Augsburg',
                              website='https://new.de', email='new@g.de',
                              phone='+49123', address='Str. 1')
    with patch('artcrm.engine.lead_scout.check_duplicate', return_value=existing), \
         patch('artcrm.engine.lead_scout.crm.update_contact') as mock_update:
        insert_lead(candidate, skip_if_exists=False)
    updates = mock_update.call_args[0][1]
    assert 'website' in updates
    assert 'email' in updates
    assert 'phone' in updates
    assert 'address' in updates


def test_insert_lead_does_not_overwrite_existing_fields():
    existing = Contact(id=1, name='Galerie am Stadtpark', city='Augsburg',
                       website='https://existing.de', email=None, phone=None, address=None,
                       status='cold', preferred_language='de')
    candidate = LeadCandidate(name='Galerie am Stadtpark', city='Augsburg',
                              website='https://new.de')
    with patch('artcrm.engine.lead_scout.check_duplicate', return_value=existing), \
         patch('artcrm.engine.lead_scout.crm.update_contact') as mock_update:
        insert_lead(candidate, skip_if_exists=False)
    if mock_update.called:
        updates = mock_update.call_args[0][1]
        assert 'website' not in updates


def test_insert_lead_creates_new_contact_when_no_duplicate():
    with patch('artcrm.engine.lead_scout.check_duplicate', return_value=None), \
         patch('artcrm.engine.lead_scout.crm.create_contact', return_value=42) as mock_create:
        result = insert_lead(SAMPLE_CANDIDATE)
    assert result == 42
    mock_create.assert_called_once()


def test_insert_lead_new_contact_has_lead_unverified_status():
    with patch('artcrm.engine.lead_scout.check_duplicate', return_value=None), \
         patch('artcrm.engine.lead_scout.crm.create_contact', return_value=42) as mock_create:
        insert_lead(SAMPLE_CANDIDATE)
    contact = mock_create.call_args[0][0]
    assert contact.status == 'lead_unverified'


def test_insert_lead_new_contact_notes_include_source():
    with patch('artcrm.engine.lead_scout.check_duplicate', return_value=None), \
         patch('artcrm.engine.lead_scout.crm.create_contact', return_value=1) as mock_create:
        insert_lead(SAMPLE_CANDIDATE)
    contact = mock_create.call_args[0][0]
    assert 'openstreetmap' in contact.notes


# ---------------------------------------------------------------------------
# scout_city
# ---------------------------------------------------------------------------

def test_scout_city_returns_stats_dict(tmp_path):
    with patch('artcrm.engine.lead_scout.search_google_maps', return_value=[]), \
         patch('artcrm.engine.lead_scout.search_openstreetmap', return_value=[]), \
         patch('artcrm.engine.lead_scout.enrich_with_ai', side_effect=lambda c, **kw: c), \
         patch('artcrm.engine.lead_scout.insert_lead', return_value=None), \
         patch('artcrm.engine.lead_scout.bus.emit'), \
         patch('artcrm.engine.lead_scout.SCOUT_DIR', tmp_path), \
         patch('time.sleep'), \
         patch('artcrm.engine.lead_scout.tqdm', side_effect=lambda x, **kw: x):
        result = scout_city('Augsburg', 'DE')

    assert 'city' in result
    assert 'total_found' in result
    assert 'total_inserted' in result
    assert 'total_skipped' in result


def test_scout_city_uses_default_business_types(tmp_path):
    searched_types = []

    def mock_gm(city, country, biz_type, radius_km=10):
        searched_types.append(biz_type)
        return []

    with patch('artcrm.engine.lead_scout.search_google_maps', side_effect=mock_gm), \
         patch('artcrm.engine.lead_scout.search_openstreetmap', return_value=[]), \
         patch('artcrm.engine.lead_scout.enrich_with_ai', side_effect=lambda c, **kw: c), \
         patch('artcrm.engine.lead_scout.insert_lead', return_value=None), \
         patch('artcrm.engine.lead_scout.bus.emit'), \
         patch('artcrm.engine.lead_scout.SCOUT_DIR', tmp_path), \
         patch('time.sleep'), \
         patch('artcrm.engine.lead_scout.tqdm', side_effect=lambda x, **kw: x):
        scout_city('Augsburg')

    assert 'gallery' in searched_types
    assert 'cafe' in searched_types
    assert 'coworking' in searched_types


def test_scout_city_skips_google_maps_when_disabled(tmp_path):
    with patch('artcrm.engine.lead_scout.search_google_maps') as mock_gm, \
         patch('artcrm.engine.lead_scout.search_openstreetmap', return_value=[]), \
         patch('artcrm.engine.lead_scout.enrich_with_ai', side_effect=lambda c, **kw: c), \
         patch('artcrm.engine.lead_scout.insert_lead', return_value=None), \
         patch('artcrm.engine.lead_scout.bus.emit'), \
         patch('artcrm.engine.lead_scout.SCOUT_DIR', tmp_path), \
         patch('time.sleep'), \
         patch('artcrm.engine.lead_scout.tqdm', side_effect=lambda x, **kw: x):
        scout_city('Augsburg', use_google_maps=False)

    mock_gm.assert_not_called()


def test_scout_city_counts_total_found(tmp_path):
    with patch('artcrm.engine.lead_scout.search_google_maps', return_value=[SAMPLE_CANDIDATE, SAMPLE_CANDIDATE]), \
         patch('artcrm.engine.lead_scout.search_openstreetmap', return_value=[]), \
         patch('artcrm.engine.lead_scout.enrich_with_ai', side_effect=lambda c, **kw: c), \
         patch('artcrm.engine.lead_scout.insert_lead', return_value=1), \
         patch('artcrm.engine.lead_scout.bus.emit'), \
         patch('artcrm.engine.lead_scout.SCOUT_DIR', tmp_path), \
         patch('time.sleep'), \
         patch('artcrm.engine.lead_scout.tqdm', side_effect=lambda x, **kw: x):
        result = scout_city('Augsburg', business_types=['gallery'])

    # 2 candidates found for 'gallery' type
    assert result['total_found'] == 2


def test_scout_city_counts_skipped(tmp_path):
    with patch('artcrm.engine.lead_scout.search_google_maps', return_value=[SAMPLE_CANDIDATE]), \
         patch('artcrm.engine.lead_scout.search_openstreetmap', return_value=[]), \
         patch('artcrm.engine.lead_scout.enrich_with_ai', side_effect=lambda c, **kw: c), \
         patch('artcrm.engine.lead_scout.insert_lead', return_value=None),  \
         patch('artcrm.engine.lead_scout.bus.emit'), \
         patch('artcrm.engine.lead_scout.SCOUT_DIR', tmp_path), \
         patch('time.sleep'), \
         patch('artcrm.engine.lead_scout.tqdm', side_effect=lambda x, **kw: x):
        result = scout_city('Augsburg', business_types=['gallery'])

    assert result['total_skipped'] == 1
    assert result['total_inserted'] == 0


def test_scout_city_writes_json_results(tmp_path):
    with patch('artcrm.engine.lead_scout.search_google_maps', return_value=[]), \
         patch('artcrm.engine.lead_scout.search_openstreetmap', return_value=[]), \
         patch('artcrm.engine.lead_scout.enrich_with_ai', side_effect=lambda c, **kw: c), \
         patch('artcrm.engine.lead_scout.insert_lead', return_value=None), \
         patch('artcrm.engine.lead_scout.bus.emit'), \
         patch('artcrm.engine.lead_scout.SCOUT_DIR', tmp_path), \
         patch('time.sleep'), \
         patch('artcrm.engine.lead_scout.tqdm', side_effect=lambda x, **kw: x):
        scout_city('Augsburg', 'DE')

    json_files = list(tmp_path.glob('scout_Augsburg_DE_*.json'))
    assert len(json_files) == 1
    data = json.loads(json_files[0].read_text())
    assert 'stats' in data
    assert 'candidates' in data


def test_scout_city_emits_scout_complete_event(tmp_path):
    with patch('artcrm.engine.lead_scout.search_google_maps', return_value=[]), \
         patch('artcrm.engine.lead_scout.search_openstreetmap', return_value=[]), \
         patch('artcrm.engine.lead_scout.enrich_with_ai', side_effect=lambda c, **kw: c), \
         patch('artcrm.engine.lead_scout.insert_lead', return_value=None), \
         patch('artcrm.engine.lead_scout.bus.emit') as mock_emit, \
         patch('artcrm.engine.lead_scout.SCOUT_DIR', tmp_path), \
         patch('time.sleep'), \
         patch('artcrm.engine.lead_scout.tqdm', side_effect=lambda x, **kw: x):
        scout_city('Augsburg', 'DE')

    mock_emit.assert_called_once()
    assert mock_emit.call_args[0][0] == 'scout_complete'


def test_scout_city_osm_used_as_fallback_when_few_gm_results(tmp_path):
    with patch('artcrm.engine.lead_scout.search_google_maps', return_value=[SAMPLE_CANDIDATE]), \
         patch('artcrm.engine.lead_scout.search_openstreetmap', return_value=[]) as mock_osm, \
         patch('artcrm.engine.lead_scout.enrich_with_ai', side_effect=lambda c, **kw: c), \
         patch('artcrm.engine.lead_scout.insert_lead', return_value=None), \
         patch('artcrm.engine.lead_scout.bus.emit'), \
         patch('artcrm.engine.lead_scout.SCOUT_DIR', tmp_path), \
         patch('time.sleep'), \
         patch('artcrm.engine.lead_scout.tqdm', side_effect=lambda x, **kw: x):
        # 1 GM result < 5 threshold → OSM should be called
        scout_city('Augsburg', business_types=['gallery'], use_google_maps=True, use_osm=True)

    mock_osm.assert_called()
