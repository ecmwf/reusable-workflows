"""CI gating policy and polling tests; no network or credentials needed."""
import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

SPEC = importlib.util.spec_from_file_location(
    'ci_gate', Path(__file__).parents[1] / 'require-successful-ci' / 'gate.py'
)
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)
SHA = 'a' * 40
REPO = 'ecmwf/ecbuild'


def run(**overrides):
    result = dict(id=1, head_sha=SHA, event='push', head_branch='develop',
                  head_repository={'full_name': REPO}, status='completed',
                  conclusion='success', html_url='https://github.com/ecmwf/ecbuild/actions/runs/1')
    result.update(overrides)
    return result


def select(runs):
    return gate.select_run(runs, SHA, REPO, {'push'}, {'master', 'develop'})


def test_exact_trusted_run():
    assert gate.verdict(select([run()]))


@pytest.mark.parametrize('overrides', [
    {'head_sha': 'b' * 40}, {'event': 'pull_request'},
    {'event': 'workflow_dispatch'}, {'head_branch': 'feature/test'},
    {'head_repository': {'full_name': 'someone/ecbuild'}}, {'head_repository': None},
])
def test_untrusted_or_different_source(overrides):
    assert select([run(**overrides)]) is None


def test_feature_branch_requires_explicit_policy():
    candidate = run(event='workflow_dispatch', head_branch='feature/test')
    assert select([candidate]) is None
    assert gate.select_run([candidate], SHA, REPO, {'workflow_dispatch'}, {'feature/test'}) == candidate


@pytest.mark.parametrize('conclusion', ['failure', 'cancelled', 'timed_out', 'skipped', 'neutral', 'action_required', 'stale'])
def test_failed_latest_run_cannot_fall_back(conclusion):
    with pytest.raises(RuntimeError, match=conclusion):
        gate.verdict(select([run(), run(id=2, conclusion=conclusion)]))


def test_pending_latest_run_cannot_fall_back():
    assert not gate.verdict(select([run(), run(id=2, status='in_progress', conclusion=None)]))
    assert not gate.verdict(None)


@pytest.fixture
def env(monkeypatch, tmp_path):
    values = dict(CI_SOURCE_SHA=SHA, GITHUB_REPOSITORY=REPO, CI_WORKFLOW='ci.yml',
                  CI_ALLOWED_EVENTS='push', CI_ALLOWED_BRANCHES='master,develop',
                  CI_TIMEOUT_SECONDS='60', GITHUB_OUTPUT=str(tmp_path / 'outputs'),
                  GITHUB_STEP_SUMMARY=str(tmp_path / 'summary'))
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return values


def response(runs):
    return Mock(stdout=json.dumps([{'workflow_runs': runs}]))


def test_wait_then_success(env, monkeypatch):
    api = Mock(side_effect=[response([]), response([run(status='in_progress')]), response([run()])])
    monkeypatch.setattr(gate.subprocess, 'run', api)
    monkeypatch.setattr(gate.time, 'sleep', Mock())
    gate.main()
    assert api.call_count == 3
    assert f'head_sha={SHA}' in api.call_args.args[0][-1]
    assert 'run_url=' in Path(env['GITHUB_OUTPUT']).read_text()
    assert SHA in Path(env['GITHUB_STEP_SUMMARY']).read_text()


def test_timeout(env, monkeypatch):
    monkeypatch.setattr(gate.subprocess, 'run', Mock(return_value=response([])))
    monkeypatch.setattr(gate.time, 'monotonic', Mock(side_effect=[0, 61]))
    with pytest.raises(RuntimeError, match='before timeout'):
        gate.main()
    assert not Path(env['GITHUB_OUTPUT']).exists()


def test_api_failure_is_not_success(env, monkeypatch):
    monkeypatch.setattr(gate.subprocess, 'run', Mock(side_effect=RuntimeError('API unavailable')))
    with pytest.raises(RuntimeError, match='API unavailable'):
        gate.main()
    assert not Path(env['GITHUB_OUTPUT']).exists()


@pytest.mark.parametrize('key,value', [('CI_SOURCE_SHA', 'develop'), ('CI_ALLOWED_BRANCHES', ''),
                                      ('CI_ALLOWED_EVENTS', ''), ('CI_TIMEOUT_SECONDS', '0')])
def test_invalid_inputs(env, monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError):
        gate.main()
