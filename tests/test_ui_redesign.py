"""UI role choices cannot grant access; examples/tags never submit a complaint."""
from pathlib import Path
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from frontend.client import DashboardClient, DashboardError

ROOT = Path(__file__).resolve().parents[1]


class RedesignTests(unittest.TestCase):
    def test_verified_editor_key_survives_login_and_screen_reruns(self):
        from fastapi.testclient import TestClient
        from teleassist.common.access import AccessPolicy
        from teleassist.services.combined import create_app
        class NoProvider:
            configured = False
        with TestClient(create_app(provider=NoProvider(), include_public=False,
                                  access=AccessPolicy('required', 'test-agent', 'test-editor'))) as backend:
            def send(client, path, payload=None, **kwargs):
                response = backend.request('POST' if payload is not None else 'GET', path,
                    json=payload, headers={'X-API-Key':client.key})
                if response.status_code >= 400:
                    raise DashboardError(str(response.json()['detail']), response.status_code)
                return response.json()
            with patch.object(DashboardClient, 'request', send):
                app = AppTest.from_file(str(ROOT/'dashboard.py')).run()
                next(b for b in app.button if b.label == 'Open Knowledge Editor workspace').click().run()
                app.text_input(key='application_key').set_value('test-editor')
                next(b for b in app.button if b.label == 'Verify editor access').click().run()
                self.assertFalse(app.exception)
                self.assertFalse(app.error)
                self.assertEqual(app.session_state['view_role'], 'editor')
                self.assertEqual(app.text_input(key='application_key').value, 'test-editor')
                self.assertTrue(any(x.value == 'Evidence Explorer' for x in app.title))
                app.run()
                self.assertFalse(app.error)
                self.assertEqual(app.text_input(key='application_key').value, 'test-editor')

    def test_editor_choice_requires_backend_authorization(self):
        with patch.object(DashboardClient, 'request', side_effect=DashboardError('Editor access denied.', 403)) as request:
            app = AppTest.from_file(str(ROOT/'dashboard.py')).run()
            self.assertFalse(app.exception)
            request.assert_not_called()
            next(b for b in app.button if b.label == 'Open Knowledge Editor workspace').click().run()
            self.assertEqual(app.session_state['view_role'], 'editor_login')
            app.text_input(key='application_key').set_value('incorrect-key')
            next(b for b in app.button if b.label == 'Verify editor access').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['view_role'], 'editor_login')
            self.assertTrue(app.error)
            self.assertFalse(any('Health' in x.label for x in app.button))

    def test_example_does_not_call_api_and_switch_role_clears_identity(self):
        with patch.object(DashboardClient, 'request', side_effect=AssertionError('No API request expected')) as request:
            app = AppTest.from_file(str(ROOT/'dashboard.py')).run()
            next(b for b in app.button if b.label == 'Open Support Agent workspace').click().run()
            next(b for b in app.button if b.label == 'Already tried a fix').click().run()
            self.assertFalse(app.exception)
            self.assertIn('restarted the router', app.text_area(key='complaint').value)
            request.assert_not_called()
            app.text_input(key='application_key').set_value('application-test-key').run()
            app.text_area(key='complaint').set_value('Private complaint')
            next(b for b in app.button if b.label == 'Switch role').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['view_role'], 'landing')
            self.assertNotIn('application_key', app.session_state)
            self.assertEqual(app.session_state['complaint'], '')

    def test_action_tags_preserve_manual_notes_and_do_not_invent_failure(self):
        app = AppTest.from_string('from frontend.components import update_tags\nimport streamlit as st\nupdate_tags()').run()
        app.session_state['observations'] = 'The ONT alarm is lit.'
        app.session_state['tried_tags'] = ['Restarted router', 'Checked cables']
        app.run()
        self.assertFalse(app.exception)
        self.assertIn('The ONT alarm is lit.', app.session_state['observations'])
        self.assertIn('result unknown', app.session_state['observations'])
        self.assertNotIn('failed', app.session_state['observations'])
        app.session_state['tried_tags'] = ['Checked cables']
        app.run()
        self.assertNotIn('restarted', app.session_state['observations'])
        self.assertIn('checked the cables', app.session_state['observations'])

    def test_carousel_preserves_exact_citation_versions(self):
        seen = []
        def source(client, source_id, version=None):
            seen.append((source_id, version))
            return {'id':source_id, 'version':version, 'title':'Original evidence', 'evidence_tier':'kb'}
        script = """from frontend.components import carousel
from frontend.components import source_view
from frontend.client import DashboardClient
client=DashboardClient()
carousel([{'id':'KB-A','version':2},{'id':'KB-B','version':5}], 'citations_test', lambda item:source_view(client.source(item['id'],item['version'])))
"""
        with patch.object(DashboardClient, 'source', source):
            app = AppTest.from_string(script).run()
            self.assertFalse(app.exception)
            self.assertEqual(seen[-1], ('KB-A', 2))
            next(b for b in app.button if b.label == 'Next →').click().run()
            self.assertEqual(seen[-1], ('KB-B', 5))
            next(b for b in app.button if b.label == '← Previous').click().run()
            self.assertEqual(seen[-1], ('KB-A', 2))


if __name__ == '__main__':
    unittest.main()
