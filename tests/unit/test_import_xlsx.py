"""
Unit tests for scripts/import_xlsx.py.

Strategy:
  - Pure functions tested directly with varied inputs
  - Database-touching functions tested via dry_run DatabaseConnection (no real DB)
  - Sheet importers mock pd.read_excel and use dry_run mode
  - export_notes_sheets uses tmp_path for file I/O
  - run_import mocks sub-functions and XLSX_PATH to test orchestration flow

Coverage not attempted:
  - Live DB write paths (require a PostgreSQL connection)
  - main() CLI entry point (argparse + sys.exit)
"""

import sys
import logging
import numpy as np
import pandas as pd
import pytest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch, call

# Add scripts/ to path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from import_xlsx import (
    infer_outcome,
    make_dedup_key,
    make_unique_name,
    fuzzy_match_venue,
    DatabaseConnection,
    get_or_create_contact,
    create_interaction,
    import_contacts_leads,
    import_show_dates,
    import_online_platforms,
    export_notes_sheets,
    run_import,
)


# ---------------------------------------------------------------------------
# DataFrame helpers
# ---------------------------------------------------------------------------

def _make_df(n_rows, n_cols, rows=None):
    """Create an object-dtype DataFrame filled with NaN, then set specific cells."""
    df = pd.DataFrame(
        [[np.nan] * n_cols for _ in range(n_rows)],
        columns=range(n_cols),
        dtype=object,
    )
    for row_idx, col_data in (rows or {}).items():
        for col_idx, val in col_data.items():
            df.at[row_idx, col_idx] = val
    return df


def _contacts_df(rows=None):
    """
    Build a minimal contacts DataFrame mimicking the 'contacts  leads' sheet.
    rows: {row_index: {col_index: value}}
    Header row at index 3 (col 13 = 'name'), data from index 12 onward.
    """
    n_rows = max((max(rows.keys()) + 1 if rows else 0), 14)
    base = {3: {13: 'name'}}
    base.update(rows or {})
    return _make_df(n_rows, 21, base)


def _shows_df(rows=None):
    """
    Build a minimal shows DataFrame mimicking the 'show dates' sheet.
    Col 3: venue name, Col 1: month, Col 2: date, Col 4: theme.
    Data from index 4 onward.
    """
    n_rows = max((max(rows.keys()) + 1 if rows else 0), 6)
    return _make_df(n_rows, 6, rows)


def _online_df(rows=None):
    """
    Build a minimal online platforms DataFrame mimicking the 'on line' sheet.
    Col 2: name, Col 6: cost, Col 7: notes, Col 8: country, Col 9: website.
    Data from index 4 onward.
    """
    n_rows = max((max(rows.keys()) + 1 if rows else 0), 6)
    return _make_df(n_rows, 11, rows)


def _dry_db():
    return DatabaseConnection(dry_run=True)


# ---------------------------------------------------------------------------
# infer_outcome
# ---------------------------------------------------------------------------

class TestInferOutcome:

    def test_nan_returns_no_reply(self):
        assert infer_outcome(float('nan')) == 'no_reply'

    def test_none_returns_no_reply(self):
        assert infer_outcome(None) == 'no_reply'

    def test_empty_string_returns_no_reply(self):
        assert infer_outcome('') == 'no_reply'

    def test_unrecognised_text_defaults_to_no_reply(self):
        assert infer_outcome('random unrecognised content xyz') == 'no_reply'

    def test_interested(self):
        assert infer_outcome('she seemed interested in the work') == 'interested'

    def test_rejected(self):
        # 'not interested' would match 'interested' first; use unambiguous keyword
        assert infer_outcome('they declined our request') == 'rejected'

    def test_no_reply_keyword(self):
        assert infer_outcome('no reply received') == 'no_reply'

    def test_meeting_set(self):
        assert infer_outcome('a meeting was scheduled for next week') == 'meeting_set'

    def test_proposal_requested(self):
        assert infer_outcome('they asked me to send a portfolio') == 'proposal_requested'

    def test_accepted(self):
        assert infer_outcome('deal agreed, sold two prints') == 'accepted'

    def test_left_material(self):
        assert infer_outcome('dropped off some prints at the gallery') == 'left_material'

    def test_follow_up_needed(self):
        assert infer_outcome('follow up in two months') == 'follow_up_needed'

    def test_german_keine_antwort(self):
        assert infer_outcome('keine antwort erhalten') == 'no_reply'

    def test_german_interessiert(self):
        assert infer_outcome('sehr interessiert an meiner Arbeit') == 'interested'

    def test_case_insensitive(self):
        assert infer_outcome('INTERESTED in my paintings') == 'interested'

    def test_pd_na_returns_no_reply(self):
        assert infer_outcome(pd.NA) == 'no_reply'


# ---------------------------------------------------------------------------
# make_dedup_key
# ---------------------------------------------------------------------------

class TestMakeDedupKey:

    def test_basic(self):
        assert make_dedup_key('Galerie Stern', 'Augsburg') == 'galerie stern|augsburg'

    def test_strips_whitespace(self):
        assert make_dedup_key('  Galerie  ', '  Augsburg  ') == 'galerie|augsburg'

    def test_lowercased(self):
        assert make_dedup_key('GALERIE STERN', 'AUGSBURG') == 'galerie stern|augsburg'

    def test_none_name(self):
        assert make_dedup_key(None, 'Augsburg') == '|augsburg'

    def test_none_city(self):
        assert make_dedup_key('Galerie', None) == 'galerie|'

    def test_both_none(self):
        assert make_dedup_key(None, None) == '|'

    def test_deterministic(self):
        assert make_dedup_key('Test', 'City') == make_dedup_key('Test', 'City')


# ---------------------------------------------------------------------------
# make_unique_name
# ---------------------------------------------------------------------------

class TestMakeUniqueName:

    def test_first_occurrence_returned_unchanged(self):
        existing = {}
        result = make_unique_name('Galerie Stern', 'Augsburg', existing)
        assert result == 'Galerie Stern'

    def test_first_occurrence_registered_in_dict(self):
        existing = {}
        make_unique_name('Galerie Stern', 'Augsburg', existing)
        assert 'galerie stern|augsburg' in existing

    def test_duplicate_appends_city(self):
        existing = {'galerie stern|augsburg': 1}
        result = make_unique_name('Galerie Stern', 'Augsburg', existing)
        assert result == 'Galerie Stern (Augsburg)'

    def test_duplicate_without_city_unchanged(self):
        existing = {'galerie stern|': 1}
        result = make_unique_name('Galerie Stern', None, existing)
        assert result == 'Galerie Stern'

    def test_different_cities_are_not_duplicates(self):
        existing = {}
        r1 = make_unique_name('Cafe X', 'Berlin', existing)
        r2 = make_unique_name('Cafe X', 'Munich', existing)
        assert r1 == 'Cafe X'
        assert r2 == 'Cafe X'


# ---------------------------------------------------------------------------
# fuzzy_match_venue
# ---------------------------------------------------------------------------

class TestFuzzyMatchVenue:

    CONTACTS = [
        {'id': 1, 'name': 'Galerie Stern'},
        {'id': 2, 'name': 'Kunsthaus Munich'},
        {'id': 3, 'name': 'Cafe Boheme'},
    ]

    def test_exact_match_returns_id(self):
        assert fuzzy_match_venue('Galerie Stern', self.CONTACTS, threshold=80) == 1

    def test_near_match_above_threshold_returns_id(self):
        # 'Galerie Sterne' is very close to 'Galerie Stern'
        result = fuzzy_match_venue('Galerie Sterne', self.CONTACTS, threshold=80)
        assert result == 1

    def test_no_match_below_threshold_returns_none(self):
        result = fuzzy_match_venue('Totally Unrelated Name', self.CONTACTS, threshold=80)
        assert result is None

    def test_empty_string_returns_none(self):
        assert fuzzy_match_venue('', self.CONTACTS, threshold=80) is None

    def test_none_returns_none(self):
        assert fuzzy_match_venue(None, self.CONTACTS, threshold=80) is None

    def test_empty_contacts_returns_none(self):
        assert fuzzy_match_venue('Galerie Stern', [], threshold=80) is None

    def test_contact_without_name_is_skipped(self):
        contacts = [{'id': 1, 'name': ''}, {'id': 2, 'name': 'Galerie Stern'}]
        assert fuzzy_match_venue('Galerie Stern', contacts, threshold=80) == 2

    def test_lower_threshold_permits_weaker_match(self):
        result = fuzzy_match_venue('Galerie', self.CONTACTS, threshold=30)
        assert result is not None


# ---------------------------------------------------------------------------
# DatabaseConnection — dry_run mode
# ---------------------------------------------------------------------------

class TestDatabaseConnectionDryRun:

    def test_enter_does_not_call_psycopg2_connect(self):
        with patch('psycopg2.connect') as mock_connect:
            with _dry_db():
                pass
        mock_connect.assert_not_called()

    def test_execute_returns_none(self):
        with _dry_db() as db:
            result = db.execute("SELECT 1")
        assert result is None

    def test_fetchone_returns_none(self):
        with _dry_db() as db:
            assert db.fetchone() is None

    def test_fetchall_returns_empty_list(self):
        with _dry_db() as db:
            assert db.fetchall() == []

    def test_exit_does_not_commit(self):
        with patch('psycopg2.connect') as mock_connect:
            with _dry_db():
                pass
        mock_connect.assert_not_called()


# ---------------------------------------------------------------------------
# get_or_create_contact — dry_run
# ---------------------------------------------------------------------------

class TestGetOrCreateContactDryRun:

    CONTACT_DATA = {
        'name': 'Galerie Test', 'city': 'Augsburg', 'type': 'gallery',
        'subtype': None, 'address': None, 'website': None, 'email': None,
        'phone': None, 'preferred_language': 'de', 'status': 'cold',
        'notes': None, 'country': 'DE',
    }

    def test_returns_none(self):
        with _dry_db() as db:
            result = get_or_create_contact(db, self.CONTACT_DATA, 'galerie test|augsburg')
        assert result is None

    def test_does_not_call_execute(self):
        with _dry_db() as db:
            with patch.object(db, 'execute') as mock_exec:
                get_or_create_contact(db, self.CONTACT_DATA, 'galerie test|augsburg')
        mock_exec.assert_not_called()


# ---------------------------------------------------------------------------
# create_interaction — dry_run
# ---------------------------------------------------------------------------

class TestCreateInteractionDryRun:

    INTERACTION_DATA = {
        'contact_id': 1,
        'interaction_date': date(2026, 1, 15),
        'method': 'email',
        'direction': 'outbound',
        'summary': 'Sent intro letter to the gallery.',
        'outcome': 'no_reply',
        'next_action': None,
        'next_action_date': None,
    }

    def test_is_noop(self):
        with _dry_db() as db:
            with patch.object(db, 'execute') as mock_exec:
                create_interaction(db, self.INTERACTION_DATA)
        mock_exec.assert_not_called()


# ---------------------------------------------------------------------------
# import_contacts_leads — dry_run + mocked DataFrame
# ---------------------------------------------------------------------------

class TestImportContactsLeads:

    def _run(self, df):
        with _dry_db() as db:
            with patch('pandas.read_excel', return_value=df):
                return import_contacts_leads(db, MagicMock())

    def test_empty_sheet_returns_zeros(self):
        created, updated, skipped = self._run(_contacts_df())
        assert created == 0 and updated == 0 and skipped == 0

    def test_single_contact_counted_as_created(self):
        df = _contacts_df({12: {13: 'Galerie Test', 14: 'Augsburg', 16: 'gallery'}})
        created, _, _ = self._run(df)
        assert created == 1

    def test_city_people_skipped(self):
        df = _contacts_df({12: {13: 'Someone', 14: 'people'}})
        _, _, skipped = self._run(df)
        assert skipped == 1

    def test_row_without_name_ignored(self):
        df = _contacts_df({12: {14: 'Augsburg'}})  # col 13 is NaN
        created, _, _ = self._run(df)
        assert created == 0

    def test_row_named_name_ignored(self):
        # 'name' is the header value — should be skipped
        df = _contacts_df({12: {13: 'name', 14: 'Augsburg'}})
        created, _, _ = self._run(df)
        assert created == 0

    def test_multiple_contacts_all_counted(self):
        df = _contacts_df({
            12: {13: 'Galerie A', 14: 'Augsburg'},
            13: {13: 'Galerie B', 14: 'Munich'},
        })
        created, _, _ = self._run(df)
        assert created == 2

    def test_timestamp_first_contact_date_accepted(self):
        df = _contacts_df({12: {
            13: 'Galerie Test', 14: 'Augsburg',
            3: pd.Timestamp('2025-01-15'),
            4: 'interested in my work',
        }})
        created, _, _ = self._run(df)
        assert created == 1

    def test_non_date_first_contact_handled(self):
        # Text in the date column — should not crash
        df = _contacts_df({12: {
            13: 'Galerie Test', 14: 'Augsburg',
            3: 'yes',
            4: 'no reply',
        }})
        created, _, _ = self._run(df)
        assert created == 1

    def test_returns_three_tuple(self):
        result = self._run(_contacts_df())
        assert len(result) == 3


# ---------------------------------------------------------------------------
# import_show_dates — dry_run + mocked DataFrame
# ---------------------------------------------------------------------------

class TestImportShowDates:

    def _run(self, df):
        with _dry_db() as db:
            with patch('pandas.read_excel', return_value=df):
                return import_show_dates(db, MagicMock())

    def test_empty_sheet_returns_zero(self):
        assert self._run(_shows_df()) == 0

    def test_venue_named_venue_is_header_and_skipped(self):
        df = _shows_df({4: {3: 'venue'}})
        assert self._run(df) == 0

    def test_nan_venue_skipped(self):
        df = _shows_df({4: {1: 'April'}})  # no venue at col 3
        assert self._run(df) == 0

    def test_single_show_counted(self):
        df = _shows_df({4: {3: 'Galerie Stern', 1: 'April', 4: 'Landscapes'}})
        assert self._run(df) == 1

    def test_show_with_timestamp_date(self):
        df = _shows_df({4: {3: 'Galerie Stern', 2: pd.Timestamp('2026-04-01')}})
        assert self._run(df) == 1

    def test_multiple_shows_counted(self):
        df = _shows_df({
            4: {3: 'Galerie A', 1: 'March'},
            5: {3: 'Galerie B', 1: 'May'},
        })
        assert self._run(df) == 2


# ---------------------------------------------------------------------------
# import_online_platforms — dry_run + mocked DataFrame
# ---------------------------------------------------------------------------

class TestImportOnlinePlatforms:

    def _run(self, df):
        with _dry_db() as db:
            with patch('pandas.read_excel', return_value=df):
                return import_online_platforms(db, MagicMock())

    def test_empty_sheet_returns_zero(self):
        assert self._run(_online_df()) == 0

    @pytest.mark.parametrize("excluded", [
        'on line sales options', 'HAVE:', 'General Online Sites', 'Online galleries'
    ])
    def test_header_names_skipped(self, excluded):
        df = _online_df({4: {2: excluded}})
        assert self._run(df) == 0

    def test_single_platform_counted(self):
        df = _online_df({4: {2: 'Artsy', 9: 'https://artsy.net', 8: 'US'}})
        assert self._run(df) == 1

    def test_cost_and_notes_combined(self):
        df = _online_df({4: {2: 'Saatchi', 6: '20%', 7: 'Good for prints'}})
        with _dry_db() as db:
            with patch('pandas.read_excel', return_value=df), \
                 patch('import_xlsx.get_or_create_contact') as mock_create:
                mock_create.return_value = None
                import_online_platforms(db, MagicMock())
        contact_data = mock_create.call_args[0][1]
        assert 'Commission: 20%' in contact_data['notes']
        assert 'Good for prints' in contact_data['notes']

    def test_two_letter_country_code_kept(self):
        df = _online_df({4: {2: 'Platform', 8: 'DE'}})
        with _dry_db() as db:
            with patch('pandas.read_excel', return_value=df), \
                 patch('import_xlsx.get_or_create_contact') as mock_create:
                mock_create.return_value = None
                import_online_platforms(db, MagicMock())
        assert mock_create.call_args[0][1]['country'] == 'DE'

    def test_longer_country_value_discarded(self):
        df = _online_df({4: {2: 'Platform', 8: 'Germany'}})
        with _dry_db() as db:
            with patch('pandas.read_excel', return_value=df), \
                 patch('import_xlsx.get_or_create_contact') as mock_create:
                mock_create.return_value = None
                import_online_platforms(db, MagicMock())
        assert mock_create.call_args[0][1]['country'] is None

    def test_type_set_to_online_platform(self):
        df = _online_df({4: {2: 'Artfinder'}})
        with _dry_db() as db:
            with patch('pandas.read_excel', return_value=df), \
                 patch('import_xlsx.get_or_create_contact') as mock_create:
                mock_create.return_value = None
                import_online_platforms(db, MagicMock())
        assert mock_create.call_args[0][1]['type'] == 'online_platform'


# ---------------------------------------------------------------------------
# export_notes_sheets
# ---------------------------------------------------------------------------

class TestExportNotesSheets:

    def test_no_matching_sheets_returns_zero(self, tmp_path):
        excel_file = MagicMock()
        excel_file.sheet_names = []
        with patch('import_xlsx.NOTES_DIR', tmp_path):
            assert export_notes_sheets(excel_file) == 0

    def test_known_sheet_creates_markdown_file(self, tmp_path):
        df = pd.DataFrame({0: ['Row A', 'Row B'], 1: ['Val 1', 'Val 2']})
        excel_file = MagicMock()
        excel_file.sheet_names = ['plans']
        with patch('import_xlsx.NOTES_DIR', tmp_path), \
             patch('pandas.read_excel', return_value=df):
            count = export_notes_sheets(excel_file)
        assert count == 1
        assert (tmp_path / 'plans.md').exists()

    def test_markdown_contains_sheet_heading(self, tmp_path):
        df = pd.DataFrame({0: ['content']})
        excel_file = MagicMock()
        excel_file.sheet_names = ['plans']
        with patch('import_xlsx.NOTES_DIR', tmp_path), \
             patch('pandas.read_excel', return_value=df):
            export_notes_sheets(excel_file)
        assert '# plans' in (tmp_path / 'plans.md').read_text()

    def test_read_error_caught_file_not_created(self, tmp_path):
        excel_file = MagicMock()
        excel_file.sheet_names = ['plans']
        with patch('import_xlsx.NOTES_DIR', tmp_path), \
             patch('pandas.read_excel', side_effect=Exception("corrupt sheet")):
            count = export_notes_sheets(excel_file)
        assert count == 0
        assert not (tmp_path / 'plans.md').exists()

    def test_multiple_known_sheets_all_exported(self, tmp_path):
        df = pd.DataFrame({0: ['content']})
        excel_file = MagicMock()
        excel_file.sheet_names = ['plans', 'ideas']
        with patch('import_xlsx.NOTES_DIR', tmp_path), \
             patch('pandas.read_excel', return_value=df):
            assert export_notes_sheets(excel_file) == 2

    def test_unknown_sheet_not_exported(self, tmp_path):
        excel_file = MagicMock()
        excel_file.sheet_names = ['unknown_sheet']
        with patch('import_xlsx.NOTES_DIR', tmp_path):
            assert export_notes_sheets(excel_file) == 0


# ---------------------------------------------------------------------------
# run_import — orchestration flow
# ---------------------------------------------------------------------------

class TestRunImport:

    def _patch_run(self, tmp_path, xlsx_exists=True, excel_raises=False,
                   contacts_result=(0, 0, 0), contacts_raises=False):
        """Helper: patch everything needed for run_import."""
        mock_xlsx = MagicMock()
        mock_xlsx.exists.return_value = xlsx_exists
        mock_excel = MagicMock()
        mock_excel.sheet_names = []

        patches = [
            patch('import_xlsx.XLSX_PATH', mock_xlsx),
            patch('import_xlsx.project_root', tmp_path),
            patch('logging.basicConfig'),  # prevent root logger modification
        ]
        if not excel_raises:
            patches += [
                patch('pandas.ExcelFile', return_value=mock_excel),
                patch('import_xlsx.import_contacts_leads',
                      side_effect=Exception("db") if contacts_raises else MagicMock(return_value=contacts_result)),
                patch('import_xlsx.import_show_dates', return_value=0),
                patch('import_xlsx.import_online_platforms', return_value=0),
                patch('import_xlsx.export_notes_sheets', return_value=0),
            ]
        else:
            patches.append(patch('pandas.ExcelFile', side_effect=Exception("bad xlsx")))
        return patches

    def test_returns_1_if_xlsx_missing(self, tmp_path):
        patches = self._patch_run(tmp_path, xlsx_exists=False)
        with ExitStack(patches) as _:
            result = run_import(dry_run=True, log_level='WARNING')
        assert result == 1

    def test_returns_1_if_excel_unreadable(self, tmp_path):
        patches = self._patch_run(tmp_path, excel_raises=True)
        with ExitStack(patches) as _:
            result = run_import(dry_run=True, log_level='WARNING')
        assert result == 1

    def test_returns_0_on_clean_run(self, tmp_path):
        patches = self._patch_run(tmp_path)
        with ExitStack(patches) as _:
            result = run_import(dry_run=True, log_level='WARNING')
        assert result == 0

    def test_returns_1_when_sub_importer_raises(self, tmp_path):
        patches = self._patch_run(tmp_path, contacts_raises=True)
        with ExitStack(patches) as _:
            result = run_import(dry_run=True, log_level='WARNING')
        assert result == 1


# ---------------------------------------------------------------------------
# ExitStack helper (contextlib.ExitStack equivalent for a list of patchers)
# ---------------------------------------------------------------------------

from contextlib import contextmanager

class ExitStack:
    """Apply a list of patch() context managers."""
    def __init__(self, patchers):
        self.patchers = patchers
        self.mocks = []

    def __enter__(self):
        for p in self.patchers:
            self.mocks.append(p.__enter__())
        return self.mocks

    def __exit__(self, *args):
        for p in reversed(self.patchers):
            p.__exit__(*args)
