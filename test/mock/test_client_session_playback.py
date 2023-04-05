import unittest
from test.mock.client_session_playback import Base, ClientSessionPlayback
from test.mock.client_session_request_utils import (
    ClientSessionRequestMethod,
    ClientSessionRequestType,
    ClientSessionResponseType,
)

from sqlalchemy import and_, create_engine
from sqlalchemy.orm import sessionmaker


class TestClientSessionPlayback(unittest.TestCase):
    session = None

    @classmethod
    def setUpClass(cls):
        engine = create_engine('sqlite:///test.db')
        engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        cls.session = Session()

    @classmethod
    def tearDownClass(cls):
        cls.session.close()

    def test_as_dict(self):
        playback = ClientSessionPlayback(
            timestamp=1,
            url='http://example.com',
            method=ClientSessionRequestMethod.GET,
            request_type=ClientSessionRequestType.PLAIN,
            request_params={'key': 'value'},
            request_json={'data': 'example'},
            response_type=ClientSessionResponseType.WITH_JSON,
            response_code=200,
            response_text='OK',
            response_json={'result': 'success'}
        )
        expected_dict = {
            'id': None,
            'timestamp': 1,
            'url': 'http://example.com',
            'method': ClientSessionRequestMethod.GET,
            'request_type': ClientSessionRequestType.PLAIN,
            'request_params': {'key': 'value'},
            'request_json': {'data': 'example'},
            'response_type': ClientSessionResponseType.WITH_JSON,
            'response_code': 200,
            'response_text': 'OK',
            'response_json': {'result': 'success'}
        }
        self.assertDictEqual(playback.as_dict(), expected_dict)

    def test_required_fields_missing_response_code_raises_commit(self):
        playback = ClientSessionPlayback(
            timestamp=1,
            url='http://example.com',
            method=ClientSessionRequestMethod.GET,
            request_type=ClientSessionRequestType.PLAIN,
            response_type=ClientSessionResponseType.WITH_JSON,
        )
        self.session.add(playback)
        with self.assertRaises(Exception):
            self.session.commit()

    def test_required_fields_with_response_code(self):
        playback = ClientSessionPlayback(
            timestamp=1,
            url='http://example.com',
            method=ClientSessionRequestMethod.GET,
            request_type=ClientSessionRequestType.PLAIN,
            response_type=ClientSessionResponseType.WITH_JSON,
            response_code=200,
        )
        self.session.add(playback)
        self.session.commit()

        # Verify that the instance was successfully added to the database
        query = self.session.query(ClientSessionPlayback).filter(
            and_(
                ClientSessionPlayback.timestamp == 1,
                ClientSessionPlayback.url == 'http://example.com',
                ClientSessionPlayback.method == ClientSessionRequestMethod.GET,
                ClientSessionPlayback.request_type == ClientSessionRequestType.PLAIN,
                ClientSessionPlayback.response_type == ClientSessionResponseType.WITH_JSON,
                ClientSessionPlayback.response_code == 200,
            )
        )
        self.assertIsNotNone(query.one_or_none())

    def test_required_fields(self):
        # Test missing required fields
        required_fields = ['timestamp', 'url', 'method', 'request_type', 'response_type', 'response_code']
        for field in required_fields:
            playback_missing_field = ClientSessionPlayback(
                **{k: v for k, v in {
                    'timestamp': 1,
                    'url': 'http://example.com',
                    'method': ClientSessionRequestMethod.GET,
                    'request_type': ClientSessionRequestType.PLAIN,
                    'request_params': {'key': 'value'},
                    'request_json': {'data': 'example'},
                    'response_type': ClientSessionResponseType.WITH_JSON,
                    'response_code': 200,
                    'response_text': 'OK',
                    'response_json': {'result': 'success'}
                }.items() if k != field}
            )
            with self.assertRaises(Exception):
                self.session.add(playback_missing_field)
                self.session.commit()
            # Roll back the session to clear the pending rollback state
            self.session.rollback()

        # Test all fields set
        playback_all_fields = ClientSessionPlayback(
            timestamp=1,
            url='http://example.com',
            method=ClientSessionRequestMethod.GET,
            request_type=ClientSessionRequestType.PLAIN,
            request_params={'key': 'value'},
            request_json={'data': 'example'},
            response_type=ClientSessionResponseType.WITH_JSON,
            response_code=200,
            response_text='OK',
            response_json={'result': 'success'}
        )
        self.session.add(playback_all_fields)
        self.session.commit()

        # Test non-required fields
        non_required_fields = ['request_params', 'request_json', 'response_text', 'response_json']
        for field in non_required_fields:
            playback_missing_field = ClientSessionPlayback(
                timestamp=1,
                url='http://example.com',
                method=ClientSessionRequestMethod.GET,
                request_type=ClientSessionRequestType.PLAIN,
                response_type=ClientSessionResponseType.WITH_JSON,
                response_code=200,
                **{field: None}
            )
            self.session.add(playback_missing_field)
            self.session.commit()

    def test_full_behaviour(self):
        # Create playback instances with missing required fields, and add them to the session
        missing_fields_instances = []
        for field in ClientSessionPlayback.__table__.columns:
            if not field.nullable and field.default is None:
                playback_missing_fields = ClientSessionPlayback(
                    timestamp=1,
                    url='http://example.com',
                    method=ClientSessionRequestMethod.GET,
                    request_type=ClientSessionRequestType.PLAIN,
                    response_type=ClientSessionResponseType.WITH_JSON,
                )
                missing_fields_instances.append(playback_missing_fields)
                with self.assertRaises(Exception):
                    self.session.add(playback_missing_fields)
                    self.session.commit()
                # Roll back the session to clear the pending rollback state
                self.session.rollback()

        # Create playback instances with all fields set, and add them to the session
        all_fields_instances = []
        for i in range(3):
            playback_all_fields = ClientSessionPlayback(
                timestamp=1,
                url='http://example.com',
                method=ClientSessionRequestMethod.GET,
                request_type=ClientSessionRequestType.PLAIN,
                request_params={'key': 'value'},
                request_json={'data': 'example'},
                response_type=ClientSessionResponseType.WITH_JSON,
                response_code=200,
                response_text='OK',
                response_json={'result': 'success'}
            )
            all_fields_instances.append(playback_all_fields)
            self.session.add(playback_all_fields)
            self.session.commit()

        # Verify that the instances were recorded in the database
        all_fields_count = self.session.query(ClientSessionPlayback).count()
        self.assertEqual(len(all_fields_instances), all_fields_count)

    def test_optional_fields(self):
        playback = ClientSessionPlayback(
            timestamp=1,
            url='http://example.com',
            method=ClientSessionRequestMethod.GET,
            request_type=ClientSessionRequestType.PLAIN,
            response_type=ClientSessionResponseType.WITH_JSON,
            response_code=200,
            request_params={'key': 'value'},
            request_json={'data': 'example'},
            response_text='OK',
            response_json={'result': 'success'}
        )
        self.session.add(playback)
        self.session.commit()
        result = self.session.query(ClientSessionPlayback).first()
        self.assertEqual(result.timestamp, 1)
        self.assertEqual(result.url, 'http://example.com')
        self.assertEqual(result.method, ClientSessionRequestMethod.GET)
        self.assertEqual(result.request_type, ClientSessionRequestType.PLAIN)
        self.assertEqual(result.response_type, ClientSessionResponseType.WITH_JSON)
        self.assertEqual(result.response_code, 200)
        self.assertEqual(result.request_params, {'key': 'value'})
        self.assertEqual(result.request_json, {'data': 'example'})
        self.assertEqual(result.response_text, 'OK')
        self.assertEqual(result.response_json, {'result': 'success'})
