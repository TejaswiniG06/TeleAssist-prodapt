"""Case capture and reviewed publication reuse the existing evidence ingestion path."""
import sqlite3
from fastapi import Depends, HTTPException, Query
from cases import CaseCreate, CaseOutcome, CaseReview
from catalog import Conflict, IngestRequest


def install_case_routes(app, state, access):
    def read(case_id):
        try:
            return state['cases'].refresh(case_id, state['catalog'])
        except KeyError:
            raise HTTPException(404, 'Case not found.') from None
        except Conflict as error:
            raise HTTPException(409, str(error)) from None
        except sqlite3.Error:
            raise HTTPException(503, 'Case storage unavailable; check status before retrying.') from None

    def change(operation):
        try:
            return operation()
        except KeyError:
            raise HTTPException(404, 'Case not found.') from None
        except Conflict as error:
            raise HTTPException(409, str(error)) from None
        except ValueError:
            raise HTTPException(422, 'Reviewed evidence is invalid; check actions, outcome and applicability.') from None
        except sqlite3.Error:
            raise HTTPException(503, 'Case storage unavailable; check status before retrying.') from None

    @app.post('/cases', status_code=201)
    def save(request: CaseCreate, role=Depends(access.agent)):
        return change(lambda: state['cases'].save(request, role))

    @app.get('/cases')
    def list_cases(limit: int = Query(default=50, ge=1, le=100), role=Depends(access.agent)):
        store = state['cases']
        with store.lock:
            cases = [read(case['id']) for case in store.list(limit)]
        return {'cases':[{'id':case['id'], 'status':case['status'], 'revision':case['revision'],
                          'created_at':case['created_at'], 'complaint':case['complaint'][:150]}
                         for case in cases],
                'notice':'Shared prototype case workspace. Pending cases are not retrieval evidence.'}

    @app.get('/cases/{case_id}')
    def get_case(case_id: str, role=Depends(access.agent)):
        return read(case_id)

    @app.post('/cases/{case_id}/outcome')
    def outcome(case_id: str, request: CaseOutcome, role=Depends(access.agent)):
        read(case_id)
        return change(lambda: state['cases'].record_outcome(case_id, request, role))

    @app.post('/admin/cases/{case_id}/review', status_code=202)
    def review(case_id: str, request: CaseReview, role=Depends(access.editor)):
        store, catalog = state['cases'], state['catalog']
        # No other case operation can observe a half-submitted publication.
        with store.lock:
            read(case_id)
            if request.decision == 'approve':
                if request.category not in state['topics'].taxonomy():
                    raise HTTPException(422, 'New categories need taxonomy review before publication.')
                with catalog.lock:
                    if request.expected_index_version != catalog.current.version:
                        raise HTTPException(409, 'Index changed; refresh before publishing.')
            case = change(lambda: store.review(case_id, request, role))
            if request.decision == 'reject':
                return case
            try:
                job = catalog.submit(IngestRequest(expected_index_version=request.expected_index_version,
                    changes=[{'expected_version':0, 'record':case['publication']['record']}]), role)
            except Conflict as error:
                store.publication_failed(case_id)
                raise HTTPException(409, str(error)) from None
            change(lambda: store.attach_job(case_id, job['id']))
            return read(case_id)
