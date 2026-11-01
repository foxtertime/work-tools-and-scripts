"""Offline VMaaS fixtures mirror the public v3 GET API."""
import json
import os
import tempfile
import unittest
from concurrent.futures import Future, ThreadPoolExecutor
from unittest import mock
from urllib.parse import quote

from patchaudit.vmaas import VmaasClient, VmaasError, VmaasSettings
from tests.fakes import FakeTransport, Response

BASE = 'https://console.redhat.com/api/vmaas/v3'
REPO = 'rhel-9-for-x86_64-baseos-rpms'


def response(body, status=200):
    return Response(status, body, {})


def repo(label=REPO, release='9', arch='x86_64'):
    return {'label': label, 'releasever': release, 'basearch': arch,
            'name': label, 'revision': '2026-11-01T00:00:00Z'}


def item(nevra, repos=None, errata=()):
    return {'nevra': nevra, 'repositories': [repo()] if repos is None else repos,
            'errata': [{'name': name, 'issued': '2026-01-01'} for name in errata],
            'first_published': '2026-01-01T00:00:00Z'}


def tree(name, entries, page=1, pages=1):
    return response({'package_name_list': {name: entries}, 'page': page,
                     'pages': pages, 'page_size': 1, 'last_change': '2026-11-01'})


def routes(name='vim', binary='vim-minimal', entries=None, sources=None):
    entries = entries or [item('vim-minimal-2:8.2-9.el9.x86_64')]
    result = {
        BASE + '/package_names/srpms/' + name: response({
            'srpm_name_list': {name: {REPO: [binary]}}, 'last_change': '2026-11-01'}),
        BASE + '/pkgtree/' + binary: tree(binary, entries),
    }
    for entry in entries:
        nevra = entry['nevra']
        source = (sources or {}).get(nevra, name + '-' + nevra.rsplit('-', 2)[1] + '-' + nevra.rsplit('-', 1)[1].rsplit('.', 1)[0] + '.src')
        result[BASE + '/packages/' + quote(nevra, safe='')] = response({
            'package_list': {nevra: {'source_package': source}}, 'last_change': '2026-11-01'})
    return result


def client(data, **settings):
    transport = FakeTransport(data)
    return VmaasClient(VmaasSettings(**settings), transport=transport,
                       sleeper=lambda seconds: None), transport


class LatestTest(unittest.TestCase):
    def test_source_name_mapping_and_epoch_order_return_source_nvr(self):
        data = routes(entries=[item('vim-minimal-1:99-1.el9.x86_64'),
                               item('vim-minimal-2:8.2-9.el9.x86_64')])
        cli, transport = client(data)
        self.assertEqual(cli.latest('vim', '9'), 'vim-8.2-9.el9')
        for url, params, headers in transport.requests:
            self.assertTrue(url.startswith(BASE + '/'))
            self.assertNotIn('Authorization', headers)
            self.assertNotIn('PRIVATE-TOKEN', headers)

    def test_rpm_numeric_release_and_names_with_hyphens(self):
        entries = [item('my-lib-bin-1.0-9.el9.x86_64'), item('my-lib-bin-1.0-10.el9.x86_64')]
        cli, _ = client(routes('my-lib', 'my-lib-bin', entries))
        self.assertEqual(cli.latest('my-lib', '9'), 'my-lib-1.0-10.el9')

    def test_tree_names_are_literal_regex_patterns(self):
        for name, escaped in [('libstdc++', r'libstdc\+\+'), ('python3.11', r'python3\.11')]:
            with self.subTest(name=name):
                nevra = name + '-1.0-1.el9.x86_64'
                data = {
                    BASE + '/package_names/srpms/' + quote(name, safe=''): response({'srpm_name_list': {}}),
                    BASE + '/pkgtree/' + quote(escaped, safe=''): tree(name, [item(nevra)]),
                    BASE + '/packages/' + quote(nevra, safe=''): response({'package_list': {
                        nevra: {'source_package': name + '-1.0-1.el9.src'}}})}
                cli, _ = client(data)
                self.assertEqual(cli.latest(name, '9'), name + '-1.0-1.el9')

    def test_only_stable_rhel_arch_and_exact_major_repositories(self):
        excluded = [repo(release='9.2'), repo(arch='aarch64'),
                    repo('rhel-9-for-x86_64-baseos-eus-rpms'),
                    repo('rhel-9-for-x86_64-baseos-rhui-rpms'),
                    repo('rhel-9-for-x86_64-baseos-beta-rpms'),
                    repo('fast-datapath-for-rhel-9-x86_64-rpms'),
                    repo('rhel-8-for-x86_64-baseos-rpms', '8')]
        entries = [item('vim-minimal-8.2-1.el9.x86_64')]
        entries += [item('vim-minimal-99-%d.el9.x86_64' % i, [value]) for i, value in enumerate(excluded)]
        entries += [item('vim-minimal-100-1.el9.aarch64'), item('vim-minimal-101-1.el9.src', [])]
        cli, _ = client(routes(entries=entries))
        self.assertEqual(cli.latest('vim', '9'), 'vim-8.2-1.el9')

    def test_exact_minor_uses_support_repository(self):
        entries = [item('vim-minimal-8.2-1.el9.x86_64', [repo(release='9.2', label='rhel-9-for-x86_64-baseos-eus-rpms')]),
                   item('vim-minimal-99-1.el9.x86_64'),
                   item('vim-minimal-100-1.el9.x86_64', [repo(release='9.4', label='rhel-9-for-x86_64-baseos-eus-rpms')])]
        cli, _ = client(routes(entries=entries))
        self.assertEqual(cli.latest('vim', '9.2'), 'vim-8.2-1.el9')

    def test_arch_setting_and_noarch_are_allowed(self):
        entries = [item('vim-minimal-8.2-1.el9.noarch', [repo('rhel-9-for-aarch64-baseos-rpms', arch='aarch64')]),
                   item('vim-minimal-99-1.el9.x86_64')]
        cli, _ = client(routes(entries=entries), arch='aarch64')
        self.assertEqual(cli.latest('vim', '9'), 'vim-8.2-1.el9')

    def test_regular_package_excludes_modular_builds(self):
        entries = [item('vim-minimal-8.2-1.el9.x86_64'),
                   item('vim-minimal-99-1.module+el9.0.x86_64')]
        cli, _ = client(routes(entries=entries))
        self.assertEqual(cli.latest('vim', '9'), 'vim-8.2-1.el9')

    def test_stream_verified_by_module_package_membership(self):
        entries = [item('nginx-1:1.24-1.module+el9.x86_64', errata=['RHSA-2026:1']),
                   item('nginx-2:1.26-1.module+el9.x86_64', errata=['RHSA-2026:2'])]
        data = routes('nginx', 'nginx', entries)
        for index, entry in enumerate(entries, 1):
            data[BASE + '/errata/RHSA-2026%3A' + str(index)] = response({
                'errata_list': {'RHSA-2026:' + str(index): {'modules_list': [{
                    'module_name': 'nginx', 'module_stream': '1.24' if index == 1 else '1.26',
                    'package_list': [entry['nevra']], 'source_package_list': []}]}},
                'page': 1, 'pages': 1, 'page_size': 1})
        cli, _ = client(data)
        self.assertEqual(cli.latest('nginx', '9', stream='nginx:1.24'), 'nginx-1.24-1.module+el9')

    def test_unverifiable_stream_is_error(self):
        cli, _ = client(routes(entries=[item('vim-minimal-8.2-1.module+el9.x86_64')]))
        with self.assertRaises(VmaasError):
            cli.latest('vim', '9', stream='8.2')

    def test_binary_request_can_return_different_source_name(self):
        nevra = 'vim-minimal-2:8.2-9.el9.x86_64'
        data = routes('vim-minimal', 'vim-minimal', sources={nevra: 'vim-2:8.2-9.el9.src'})
        data[BASE + '/package_names/srpms/vim-minimal'] = response({'srpm_name_list': {}})
        cli, _ = client(data)
        self.assertEqual(cli.latest('vim-minimal', '9'), 'vim-8.2-9.el9')

    def test_alias_cannot_substitute_unrelated_source_for_known_srpm(self):
        data = routes()
        data[BASE + '/pkgtree/unrelated'] = tree('unrelated', [item('unrelated-100-1.el9.x86_64')])
        data[BASE + '/packages/unrelated-100-1.el9.x86_64'] = response({'package_list': {
            'unrelated-100-1.el9.x86_64': {'source_package': 'another-100-1.el9.src'}}})
        cli, _ = client(data)
        self.assertEqual(cli.latest('vim', '9', aliases=('unrelated',)), 'vim-8.2-9.el9')

    def test_binary_alias_keeps_original_source_cohort(self):
        data = routes('vim-minimal', 'vim-minimal', sources={
            'vim-minimal-2:8.2-9.el9.x86_64': 'vim-2:8.2-9.el9.src'})
        data[BASE + '/package_names/srpms/vim-minimal'] = response({'srpm_name_list': {}})
        data[BASE + '/pkgtree/other'] = tree('other', [item('other-9:99-1.el9.x86_64')])
        data[BASE + '/packages/other-9%3A99-1.el9.x86_64'] = response({'package_list': {
            'other-9:99-1.el9.x86_64': {'source_package': 'unrelated-9:99-1.el9.src'}}})
        cli, _ = client(data)
        self.assertEqual(cli.latest('vim-minimal', '9', aliases=('other',)), 'vim-8.2-9.el9')

    def test_reused_binary_name_does_not_replace_requested_source(self):
        unrelated = 'vim-minimal-100-1.el9.x86_64'
        original = 'vim-minimal-8.2-9.el9.x86_64'
        sources = {unrelated: 'another-100-1.el9.src', original: 'vim-8.2-9.el9.src'}
        for entries, expected in [([item(unrelated), item(original)], 'vim-8.2-9.el9'),
                                  ([item(unrelated)], None)]:
            with self.subTest(expected=expected):
                cli, _ = client(routes(entries=entries, sources=sources))
                self.assertEqual(cli.latest('vim', '9'), expected)

    def test_source_version_can_differ_from_binary_version(self):
        cli, _ = client(routes('ruby', 'rubygem-rake',
            [item('rubygem-rake-13.0.3-168.el9_8.noarch')],
            {'rubygem-rake-13.0.3-168.el9_8.noarch': 'ruby-3.0.7-168.el9_8.src'}))
        self.assertEqual(cli.latest('ruby', '9'), 'ruby-3.0.7-168.el9_8')

    def test_latest_orders_actual_source_evr_including_epoch(self):
        data = routes('source', 'binary', [item('binary-99-9.el9.x86_64'),
                                          item('binary-10-1.el9.x86_64')], {
            'binary-99-9.el9.x86_64': 'source-1:90-9.el9.src',
            'binary-10-1.el9.x86_64': 'source-2:2-1.el9.src'})
        cli, _ = client(data)
        self.assertEqual(cli.latest('source', '9'), 'source-2-1.el9')

    def test_malformed_source_is_error(self):
        for source in ('vim-2:8.2-bad:release.src', 'vim-2:8.2-9.el9.x86_64', None):
            with self.subTest(source=source):
                cli, _ = client(routes(sources={'vim-minimal-2:8.2-9.el9.x86_64': source}))
                with self.assertRaises(VmaasError): cli.latest('vim', '9')

    def test_binary_without_repository_metadata_is_not_complete_absence(self):
        data = routes()
        data[BASE + '/pkgtree/vim-minimal'] = tree('vim-minimal', [{
            'nevra': 'vim-minimal-2:8.2-9.el9.x86_64', 'first_published': '2026-01-01'}])
        cli, _ = client(data)
        with self.assertRaises(VmaasError): cli.latest('vim', '9')

    def test_true_absence_is_none(self):
        cli, _ = client({BASE + '/package_names/srpms/missing': response({'srpm_name_list': {}}),
                         BASE + '/pkgtree/missing': tree('missing', [])})
        self.assertIsNone(cli.latest('missing', '9'))

    def test_http_errors_and_malformed_responses_are_errors(self):
        for bad in (response({}, 404), response({}, 403), response({}, 500),
                    response(None), response({}), response({'srpm_name_list': []}),
                    response({'srpm_name_list': {'vim': {'repo': 'not-a-list'}}})):
            with self.subTest(response=bad):
                cli, _ = client({BASE + '/package_names/srpms/vim': bad}, retries=1)
                with self.assertRaises(VmaasError): cli.latest('vim', '9')

    def test_invalid_tree_and_source_are_errors(self):
        cases = [response({'package_name_list': {'vim-minimal': 'bad'}}),
                 tree('vim-minimal', [{'nevra': 'bad', 'repositories': []}]),
                 tree('vim-minimal', [item('vim-minimal-8-1.el9.x86_64', ['bad'])]),
                 response({'package_name_list': {}, 'page': 1, 'pages': 1, 'page_size': 1})]
        for bad in cases:
            with self.subTest(response=bad):
                data = routes(); data[BASE + '/pkgtree/vim-minimal'] = bad
                cli, _ = client(data)
                with self.assertRaises(VmaasError): cli.latest('vim', '9')
        data = routes(); data[BASE + '/packages/vim-minimal-2%3A8.2-9.el9.x86_64'] = response({'package_list': {}})
        cli, _ = client(data)
        with self.assertRaises(VmaasError): cli.latest('vim', '9')

    def test_partial_pagination_never_returns_lower_result(self):
        data = routes(); data[BASE + '/pkgtree/vim-minimal'] = tree('vim-minimal', [item('vim-minimal-8-1.el9.x86_64')], pages=2)
        cli, _ = client(data)
        with self.assertRaises(VmaasError): cli.latest('vim', '9')

    def test_source_failure_does_not_schedule_entire_remaining_history(self):
        entries = [item('vim-minimal-8.2-%d.el9.x86_64' % i) for i in range(30)]
        cli, _ = client(routes(entries=entries))
        submitted = []

        class FailingExecutor(ThreadPoolExecutor):
            def submit(self, function, *args, **kwargs):
                submitted.append(args)
                if len(submitted) == 1:
                    future = Future()
                    future.set_exception(VmaasError('source service unavailable'))
                    return future
                return super().submit(function, *args, **kwargs)

        with mock.patch('patchaudit.vmaas.ThreadPoolExecutor', FailingExecutor):
            with self.assertRaisesRegex(VmaasError, 'source service unavailable'):
                cli.latest('vim', '9')
        self.assertLessEqual(len(submitted), 8)

    def test_retries_transient_failure_without_auth(self):
        data = routes(); key = BASE + '/package_names/srpms/vim'
        data[key] = [response({}, 503), data[key]]
        cli, transport = client(data)
        self.assertEqual(cli.latest('vim', '9'), 'vim-8.2-9.el9')
        self.assertEqual(sum(url == key for url, _, _ in transport.requests), 2)

    def test_unsupported_legacy_rhel_is_explicit_error(self):
        cli, _ = client({})
        with self.assertRaises(VmaasError): cli.latest('vim', '7')


class CacheTest(unittest.TestCase):
    def test_fresh_result_is_reused_by_new_client_and_arch_is_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            cli, _ = client(routes(), cache_dir=directory)
            self.assertEqual(cli.latest('vim', '9'), 'vim-8.2-9.el9')
            cli, transport = client({}, cache_dir=directory)
            self.assertEqual(cli.latest('vim', '9'), 'vim-8.2-9.el9')
            self.assertEqual(transport.requests, [])
            cli, _ = client({}, cache_dir=directory, arch='aarch64', retries=1)
            with self.assertRaises(VmaasError): cli.latest('vim', '9')

    def test_zero_ttl_refetches_and_malformed_cache_is_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            cli, _ = client(routes(), cache_dir=directory)
            cli.latest('vim', '9')
            path = os.path.join(directory, os.listdir(directory)[0])
            with open(path, 'w') as handle: json.dump({'schema': 999, 'result': 'fake-99-1'}, handle)
            cli, transport = client(routes(), cache_dir=directory)
            self.assertEqual(cli.latest('vim', '9'), 'vim-8.2-9.el9')
            self.assertTrue(transport.requests)
            cli, transport = client(routes(), cache_dir=directory, cache_ttl=0)
            self.assertEqual(cli.latest('vim', '9'), 'vim-8.2-9.el9')
            self.assertTrue(transport.requests)

    def test_error_does_not_create_success_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            cli, _ = client({}, cache_dir=directory, retries=1)
            with self.assertRaises(VmaasError): cli.latest('vim', '9')
            self.assertEqual(os.listdir(directory), [])
