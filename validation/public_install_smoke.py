"""Install the downloaded toolkit and exercise its public entry points."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile
from zipfile import ZipFile


INVENTORY = """available = 10
completed = set()
for reservation_id in ('R1', 'R1'):
    if reservation_id not in completed:
        available -= 2
        completed.add(reservation_id)
print(f'Available: {available}')
"""
RETRY_TEST = """import subprocess
import sys

result = subprocess.check_output([sys.executable, 'inventory.py', '--retry'], text=True)
if result.strip() != 'Available: 8':
    sys.exit('DUPLICATE_RESERVATION_DEBIT')
print('RETRY_CHECK_PASSED')
"""
DOCUMENT = """# Reservation retry

Replaying the same reservation ID deducts stock once.

```text
Available: 8
```
"""


def require(condition, message):
    if not condition:
        raise ValueError(message)


def run(argv, cwd, env, *, expected=0, payload=None):
    process = subprocess.run(argv, cwd=cwd, env=env, input=payload, text=True,
                             capture_output=True, timeout=180)
    require(process.returncode == expected,
            f'{argv[0]} returned {process.returncode}, expected {expected}.\n'
            f'{process.stdout}{process.stderr}')
    return process


def unpack(archive, manifest_path, source):
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    require(archive.name == manifest['archive'], 'Archive name differs from the delivery manifest.')
    require(digest == manifest['archive_sha256'], 'Downloaded ZIP failed SHA-256 verification.')
    with ZipFile(archive) as bundle:
        bundle.extractall(source)
    return digest


def isolated_env(root):
    home = root / 'user'
    home.mkdir()
    return dict(os.environ, HOME=str(home), CODEX_HOME=str(home / '.codex'),
                GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                npm_config_cache=str(root / 'npm cache'), npm_config_userconfig=os.devnull)


def install(root, source, config, env):
    phases = {'doctor': 'ready', 'plan': 'ready',
              'install': 'installed', 'verify': 'verified_runtime'}
    for phase, status in phases.items():
        result = run([sys.executable, 'install.py', phase, '--host', 'codex',
                      '--home', str(root / 'installed toolkit'), '--config', str(config)],
                     source, env)
        report = json.loads(result.stdout)
        require(report['status'] == status, f'{phase} returned {report}')
        print(f'{phase}: {status}', flush=True)
    return shlex.split(report['task_command'])


def commit_project(project, env, message):
    run(['git', 'add', '.'], project, env)
    run(['git', '-c', 'user.name=Release fixture', '-c', 'user.email=fixture@example.com',
         'commit', '-qm', message], project, env)
    return run(['git', 'rev-parse', 'HEAD'], project, env).stdout.strip()


def make_project(project, source, env):
    for name in ('.agent-toolkit', 'docs', 'tests'):
        (project / name).mkdir(parents=True)
    shutil.copyfile(source / 'examples/acceptance.json', project / '.agent-toolkit/acceptance.json')
    (project / 'inventory.py').write_text(INVENTORY, encoding='utf-8')
    (project / 'tests/check_retry.py').write_text(RETRY_TEST, encoding='utf-8')
    (project / 'docs/reservations.md').write_text(DOCUMENT, encoding='utf-8')
    run(['git', 'init', '-qb', 'main'], project, env)
    commit_project(project, env, 'Baseline reservation example')


def stop_hook(config, project, session, env):
    settings = json.loads(config.read_text(encoding='utf-8'))
    command = settings['hooks']['Stop'][0]['hooks'][0]['command']
    event = json.dumps({'hook_event_name': 'Stop', 'session_id': session, 'cwd': str(project)})
    return json.loads(run(shlex.split(command), project, env, payload=event).stdout)


def check_local_task(project, task_command, config, env):
    session = 'public-install-smoke'
    guard = [*task_command, '--session', session]
    check = [*guard, 'verify', '--review', 'A repeated reservation should debit two units once.',
             '--docs-only', '--acceptance']
    document = project / 'docs/reservations.md'
    run([*guard, 'begin'], project, env)
    document.write_text(DOCUMENT.replace('Available: 8', 'Available: 6'), encoding='utf-8')
    drift = run(check, project, env, expected=2)
    require('missing the expected output' in drift.stderr, f'Unexpected failure: {drift.stderr}')
    blocked = stop_hook(config, project, session, env)
    require(blocked.get('decision') == 'block', f'Stop accepted stale documentation: {blocked}')

    document.write_text(DOCUMENT + '\nThe example starts with ten units.\n', encoding='utf-8')
    verified = run(check, project, env)
    report = json.loads(verified.stdout.splitlines()[0])
    expected = [{'id': 'reservation-retry', 'document': 'docs/reservations.md',
                 'example': 'passed', 'test': 'passed', 'counterexample': 'rejected'}]
    require(report['acceptance'] == 'passed' and report['results'] == expected,
            f'Unexpected behavior report: {report}')
    allowed = stop_hook(config, project, session, env)
    require(allowed == {}, f'Stop did not allow a verified task: {allowed}')
    print('P2: rejected stale docs, passed the example and test, rejected duplicate debit', flush=True)
    print('Codex Stop command: blocked before verification and allowed afterward', flush=True)


def check_ci(project, guard, env):
    base = commit_project(project, env, 'Update reservation documentation')
    fixture = project / 'candidate.js'
    fixture.write_text('const buffer = Buffer.alloc(1);\n', encoding='utf-8')
    clean = commit_project(project, env, 'Use the supported Buffer API')
    check = [*guard, 'check', '--base', base, '--head']
    accepted = json.loads(run([*check, clean], project, env).stdout)
    require(accepted['status'] == 'passed', f'CI rejected a supported API: {accepted}')
    fixture.write_text('const buffer = new Buffer(1);\n', encoding='utf-8')
    candidate = commit_project(project, env, 'Introduce the deprecated Buffer API')
    rejected = json.loads(run([*check, candidate], project, env, expected=1).stdout)
    require(rejected['status'] == 'failed' and any('Buffer' in item for item in rejected['diagnostics']),
            f'CI did not report the deprecated API: {rejected}')
    print('P1 CI: accepted Buffer.alloc and rejected new Buffer', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='toolkit public smoke ') as temporary:
        root = Path(temporary).resolve()
        source = root / 'release source'
        digest = unpack(args.archive, args.manifest, source)
        env = isolated_env(root)
        config = Path(env['CODEX_HOME']) / 'hooks.json'
        project = root / 'reservation example'
        task_command = install(root, source, config, env)
        make_project(project, source, env)
        check_local_task(project, task_command, config, env)
        check_ci(project, task_command, env)
        node = run(['node', '--version'], root, env).stdout.strip()
        print(f'PUBLIC_INSTALL_OK {platform.system()} {platform.machine()} '
              f'Python {platform.python_version()} Node {node} SHA-256 {digest}')


if __name__ == '__main__':
    main()
