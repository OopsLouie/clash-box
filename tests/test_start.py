"""Real Docker integration tests; needs Python 3, Docker/Compose, and curl.

Run: python3 -m unittest discover -s tests -v
Uses a temporary checkout, separate Compose project, and available local ports.
"""

import functools
import http.server
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[1]
PROVIDER = '''\
proxy-template: &node
  type: ss
  server: proxy.example.com
  port: 443
  cipher: aes-128-gcm
  password: "yes:# literal"
proxies:
  - <<: *node
    name: Sample
proxy-groups:
  - name: Select
    type: select
    proxies: [Sample, DIRECT]
rules:
  - DOMAIN,proxy.example.com,Select
  - MATCH,DIRECT
dns:
  enable: true
  nameserver: [1.1.1.1]
authentication: ["alice:secret"]
port: 9999
mixed-port: 9998
socks-port: 9997
allow-lan: false
external-controller: 0.0.0.0:9090
tun:
  enable: true
  stack: system
'''


def run(args, *, cwd=None, env=None, input=None):
    return subprocess.run(
        args, cwd=cwd, env=env, input=input,
        text=True, capture_output=True, timeout=120,
    )


def free_ports():
    with socket.socket() as first, socket.socket() as second:
        first.bind(('127.0.0.1', 0))
        second.bind(('127.0.0.1', 0))
        return first.getsockname()[1], second.getsockname()[1]


class StartIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for tool in ('docker', 'curl'):
            if not shutil.which(tool):
                raise unittest.SkipTest(f'{tool} is required')
        if run(['docker', 'info']).returncode:
            raise unittest.SkipTest('Docker is not available')
        cls.temp = tempfile.TemporaryDirectory(prefix='clash-box start test ')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.folder = Path(cls.temp.name)
        cls.repo = cls.folder / 'checkout with spaces'
        cls.repo.mkdir()
        for item in ('start.sh', 'compose.yaml'):
            shutil.copy2(ROOT / item, cls.repo / item)
        shutil.copytree(ROOT / 'scripts', cls.repo / 'scripts')
        cls.project = 'clash-box-test-' + uuid.uuid4().hex[:10]
        cls.env = os.environ.copy()
        for key in ('MIHOMO_VERSION', 'MIXED_PORT', 'SOCKS_PORT', 'PROXY_BIND_IP'):
            cls.env.pop(key, None)
        cls.env['COMPOSE_PROJECT_NAME'] = cls.project
        cls.mixed, cls.socks = free_ports()
        (cls.repo / '.env').write_text(
            f'MIXED_PORT={cls.mixed}\nSOCKS_PORT={cls.socks}\nPROXY_BIND_IP=0.0.0.0\n'
        )
        cls.source = cls.folder / '服务商 $(echo untouched).yaml'
        cls.source.write_text(PROVIDER)
        cls.addClassCleanup(cls.down)
        result = cls.start(cls.source)
        if result.returncode:
            log = cls.repo / 'runtime/start.log'
            raise AssertionError(result.stdout + result.stderr + (log.read_text() if log.exists() else ''))

    @classmethod
    def compose(cls, *args):
        return run(['docker', 'compose', '--project-directory', str(cls.repo),
                    '-f', str(cls.repo / 'compose.yaml'), *args], env=cls.env)

    @classmethod
    def start(cls, *args, env=None):
        # Deliberately run outside the checkout; also tests Unicode and spaces in paths.
        return run([str(cls.repo / 'start.sh'), *map(str, args)], cwd=cls.folder,
                   env=env or cls.env)

    @classmethod
    def down(cls):
        result = cls.compose('down', '--volumes', '--remove-orphans')
        if result.returncode:
            raise AssertionError(result.stderr)

    def runtime(self):
        return (self.repo / 'runtime/config.yaml').read_bytes()

    def container_id(self):
        result = self.compose('ps', '--quiet', 'mihomo')
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_01_preserves_provider_and_prepares_runtime(self):
        self.assertEqual(self.source.read_text(), PROVIDER)
        self.assertEqual((self.repo / 'config/config.yaml').read_text(), PROVIDER)
        result = run(['docker', 'run', '--rm', '-i', '--network', 'none',
                      'mikefarah/yq:4.54.1', 'eval', '-o=json', '.', '-'],
                     input=self.runtime().decode())
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data['proxies'][0]['password'], 'yes:# literal')
        self.assertEqual(data['proxies'][0]['server'], 'proxy.example.com')
        self.assertEqual(data['proxy-groups'][0]['proxies'], ['Sample', 'DIRECT'])
        self.assertEqual(data['rules'], ['DOMAIN,proxy.example.com,Select', 'MATCH,DIRECT'])
        self.assertEqual(data['dns'], {'enable': True, 'nameserver': ['1.1.1.1']})
        self.assertEqual(data['authentication'], ['alice:secret'])
        self.assertEqual((data['port'], data['mixed-port'], data['socks-port']), (0, 7890, 7891))
        self.assertIs(data['allow-lan'], True)
        self.assertEqual(data['external-controller'], '')
        self.assertIs(data['tun']['enable'], False)
        self.assertEqual(data['tun']['stack'], 'system')
        for path in ('runtime/config.yaml', 'runtime/start.log', 'config/config.yaml'):
            self.assertEqual((self.repo / path).stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.repo / 'runtime/.start.lock').exists())

    def test_02_http_and_socks_with_preserved_authentication(self):
        content_dir = self.folder / 'http'
        content_dir.mkdir()
        (content_dir / 'probe').write_text('clash-box integration probe')

        class QuietHandler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass

        handler = functools.partial(QuietHandler, directory=str(content_dir))
        server = http.server.ThreadingHTTPServer(('0.0.0.0', 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            inspect = run(['docker', 'network', 'inspect', self.project + '_default'])
            gateway = json.loads(inspect.stdout)[0]['IPAM']['Config'][0]['Gateway']
            target = f'http://{gateway}:{server.server_port}/probe'
            for proxy in (f'http://127.0.0.1:{self.mixed}', f'socks5h://127.0.0.1:{self.socks}'):
                with self.subTest(proxy=proxy):
                    result = run(['curl', '--silent', '--show-error', '--fail', '--max-time', '10',
                                  '--noproxy', '', '--proxy', proxy, '--proxy-user', 'alice:secret', target])
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, 'clash-box integration probe')
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_03_invalid_updates_do_not_replace_running_service(self):
        previous_id = self.container_id()
        previous_runtime = self.runtime()
        previous_source = (self.repo / 'config/config.yaml').read_bytes()
        cases = {
            'malformed': 'proxies: [\n',
            'html': '<html>expired subscription</html>\n',
            'sequence': '- one\n- two\n',
            'multiple-documents': 'rules: []\n---\nrules: []\n',
            'mihomo-invalid-rule': 'proxies: []\nrules: [INVALID_RULE]\n',
        }
        for name, text in cases.items():
            with self.subTest(case=name):
                source = self.folder / (name + '.yaml')
                source.write_text(text)
                result = self.start(source)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(self.runtime(), previous_runtime)
                self.assertEqual(self.container_id(), previous_id)
                self.assertEqual((self.repo / 'config/config.yaml').read_bytes(), previous_source)
                self.assertFalse((self.repo / 'runtime/.start.lock').exists())
                self.assertEqual(list((self.repo / 'runtime').glob('.start.*')), [])

    def test_04_default_restart_uses_imported_source(self):
        previous_id = self.container_id()
        result = self.start()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotEqual(self.container_id(), previous_id)
        self.assertEqual((self.repo / 'config/config.yaml').read_text(), PROVIDER)

    def test_05_failed_start_restores_previous_configuration(self):
        previous = self.runtime()
        wrapper_dir = self.folder / 'bin'
        wrapper_dir.mkdir()
        wrapper = wrapper_dir / 'docker'
        wrapper.write_text('''#!/usr/bin/env bash
set -eu
if [[ " $* " == *" up "* && ! -e $FAIL_ONCE ]]; then
  : > "$FAIL_ONCE"
  exit 1
fi
exec "$REAL_DOCKER" "$@"
''')
        wrapper.chmod(0o755)
        env = self.env.copy()
        env['PATH'] = str(wrapper_dir) + os.pathsep + env['PATH']
        env['REAL_DOCKER'] = shutil.which('docker')
        env['FAIL_ONCE'] = str(self.folder / 'fail-once')
        candidate = self.folder / 'new valid.yaml'
        candidate.write_text(PROVIDER.replace('log-level: info', 'log-level: warning') + '\nlog-level: warning\n')
        result = self.start(candidate, env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.runtime(), previous)
        self.assertEqual((self.repo / 'config/config.yaml').read_text(), PROVIDER)
        status = run(['docker', 'inspect', '--format', '{{.State.Health.Status}}', self.container_id()])
        self.assertEqual(status.stdout.strip(), 'healthy')

    def test_06_missing_input_and_lock_are_reported(self):
        previous = self.runtime()
        result = self.start(self.folder / 'missing.yaml')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('找不到', result.stderr)
        lock = self.repo / 'runtime/.start.lock'
        lock.mkdir()
        try:
            result = self.start()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('启动锁', result.stderr)
            self.assertTrue(lock.exists())
            self.assertEqual(self.runtime(), previous)
        finally:
            lock.rmdir()


if __name__ == '__main__':
    unittest.main()
