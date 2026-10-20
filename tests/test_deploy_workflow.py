"""Exercise deployment decisions and SSH preflight without contacting a server."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import textwrap

import pytest

from tests.test_image_analysis import _node_runtime

ROOT = Path(__file__).resolve().parents[1]


def _bash():
    executable = shutil.which('bash')
    git_bash = Path('C:/Program Files/Git/bin/bash.exe')
    if os.name == 'nt' and git_bash.is_file():
        return str(git_bash)
    if executable:
        return executable
    pytest.skip('Bash is required for deployment script checks')


@pytest.fixture
def ssh_config(tmp_path):
    environment = {key: value for key, value in os.environ.items() if not key.startswith('EC2_')}
    key_path = tmp_path / 'test-only-key'
    environment['TEST_KEY_PATH'] = key_path.as_posix()
    subprocess.run(
        [_bash(), '-c', 'ssh-keygen -q -t ed25519 -N "" -f "$TEST_KEY_PATH"'],
        env=environment, check=True, capture_output=True,
    )
    public_key = key_path.with_suffix('.pub').read_text().strip()
    environment.update(
        RUNNER_TEMP=tmp_path.as_posix(), EC2_HOST='example.invalid',
        EC2_USER='ubuntu', EC2_PROJECT_DIR='/srv/siopa', EC2_PORT='2222',
        EC2_SSH_KEY=key_path.read_text(),
        EC2_KNOWN_HOSTS=f'[example.invalid]:2222 {public_key}',
    )
    return environment


def _prepare(environment):
    command = '''
if command -v cygpath >/dev/null 2>&1; then
    export RUNNER_TEMP="$(cygpath -u "$RUNNER_TEMP")"
fi
bash scripts/ec2/prepare-ssh.sh
'''
    return subprocess.run(
        [_bash(), '-c', command], cwd=ROOT, env=environment,
        capture_output=True, text=True, timeout=10,
    )


def test_ssh_preflight_missing_configuration_is_actionable(tmp_path):
    environment = {key: value for key, value in os.environ.items() if not key.startswith('EC2_')}
    environment['RUNNER_TEMP'] = tmp_path.as_posix()
    result = _prepare(environment)
    assert result.returncode != 0
    assert 'EC2_HOST' in result.stderr and 'EC2_SSH_KEY' in result.stderr
    assert 'docs/GITHUB_ACTIONS_SECRETS.md' in result.stderr
    assert not (tmp_path / 'siopa-ec2').exists()


@pytest.mark.parametrize('port', ['0', '65536', '22; echo unsafe'])
def test_ssh_preflight_rejects_invalid_port_without_exposing_values(ssh_config, port):
    ssh_config['EC2_PORT'] = port
    result = _prepare(ssh_config)
    assert result.returncode != 0 and 'EC2_PORT' in result.stderr
    assert 'PRIVATE KEY' not in result.stderr


def test_ssh_preflight_checks_key_and_pinned_host(ssh_config):
    valid_key = ssh_config['EC2_SSH_KEY']
    ssh_config['EC2_SSH_KEY'] = 'test-only-invalid-private-key'
    result = _prepare(ssh_config)
    assert result.returncode != 0 and 'EC2_SSH_KEY invalida' in result.stderr
    assert ssh_config['EC2_SSH_KEY'] not in result.stderr
    ssh_config['EC2_SSH_KEY'] = valid_key
    ssh_config['EC2_KNOWN_HOSTS'] = ssh_config['EC2_KNOWN_HOSTS'].replace(':2222', ':22')
    result = _prepare(ssh_config)
    assert result.returncode != 0 and 'EC2_KNOWN_HOSTS' in result.stderr


def test_ssh_preflight_accepts_custom_port_and_crlf_key_without_network(ssh_config):
    ssh_config['EC2_SSH_KEY'] = ssh_config['EC2_SSH_KEY'].replace('\n', '\r\n')
    result = _prepare(ssh_config)
    assert result.returncode == 0, result.stderr
    assert 'nenhuma conexao' in result.stdout
    key_file = Path(ssh_config['RUNNER_TEMP']) / 'siopa-ec2' / 'key'
    assert b'\r' not in key_file.read_bytes()
    if os.name != 'nt':
        assert key_file.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize('case', [
    'disabled', 'approved', 'ci_failed', 'pull_request', 'foreign_repository',
    'manual_unapproved', 'manual_other_branch', 'outdated',
])
def test_deploy_policy_requires_opt_in_and_approved_main_commit(tmp_path, case):
    # Execute the actual github-script body; actionlint validates its YAML boundary.
    workflow = (ROOT / '.github/workflows/deploy-ec2.yml').read_text()
    body = textwrap.dedent(workflow.split('          script: |\n', 1)[1].split('\n  deploy:', 1)[0])
    harness = r'''
const outputs = {}, failures = [], notices = [];
const calls = [];
const sha = 'a'.repeat(40);
const context = {
  eventName: 'workflow_run', ref: 'refs/heads/main', sha,
  repo: { owner: 'owner', repo: 'repo' },
  payload: { workflow_run: { event: 'push', head_branch: 'main',
    head_repository: { full_name: 'owner/repo' }, conclusion: 'success', head_sha: sha } }
};
const testCase = process.argv[2];
process.env.ENABLE_EC2_DEPLOY = testCase === 'disabled' ? '' : 'true';
if (testCase === 'ci_failed') context.payload.workflow_run.conclusion = 'failure';
if (testCase === 'pull_request') context.payload.workflow_run.event = 'pull_request';
if (testCase === 'foreign_repository') context.payload.workflow_run.head_repository.full_name = 'other/repo';
if (testCase.startsWith('manual')) {
  context.eventName = 'workflow_dispatch';
  context.payload = {};
}
if (testCase === 'manual_other_branch') context.ref = 'refs/heads/feature';
const summary = { addHeading() {return this}, addRaw() {return this}, async write() {} };
const core = {
  setOutput(k, v) {outputs[k] = v}, setFailed(v) {failures.push(v)},
  notice(v) {notices.push(v)}, summary
};
const github = {rest: {actions: {
  async listWorkflowRuns(args) {
    calls.push(args);
    return {data: {workflow_runs: [{id: 1, status: 'completed',
      conclusion: testCase === 'manual_unapproved' ? 'failure' : 'success'}]}};
  }
}, repos: {
  async getBranch() {return {data: {commit: {sha: testCase === 'outdated' ? 'b'.repeat(40) : sha}}}}
}}};
(async () => {
__BODY__
})().then(() => {
  process.stdout.write(JSON.stringify({outputs, failures, notices, calls}));
}).catch(error => {process.stderr.write(error.stack); process.exitCode = 1});
'''.replace('__BODY__', body)
    runner = tmp_path / 'policy.cjs'
    runner.write_text(harness)
    runtime, environment = _node_runtime()
    result = subprocess.run([runtime, str(runner), case], env=environment, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    if case == 'approved':
        assert observed['outputs'] == {'enabled': 'true', 'sha': 'a' * 40}
        assert observed['calls'][0]['head_sha'] == 'a' * 40
        assert observed['calls'][0]['workflow_id'] == 'ci.yml'
    else:
        assert observed['outputs']['enabled'] == 'false'
        assert observed['failures'] or observed['notices']
    if case in {'disabled', 'ci_failed', 'pull_request', 'foreign_repository', 'manual_other_branch'}:
        assert not observed['calls']
