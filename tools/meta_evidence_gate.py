#!/usr/bin/env python3
"""Fail-closed, offline PBT exact-HEAD evidence graph verifier.

Requires real artifact ZIP bytes and an *externally fetched* GitHub run/artefact
manifest (tools/evidence_collect.py). Policy is data: config/evidence-policy.json
binds each target event to its receipts; config/required-tests.json names the
critical tests. Measurements are recomputed from raw samples and mutation verdicts
recounted against the catalog in this checkout, so run it from the target revision.
Scanner receipts cannot be re-executed offline: they are the producer's statement,
bound to the exact SHA and repository, and OSV findings are read from its raw output. Proves their consistency, NOT authenticity of the provider snapshot,
production availability, field CWV, or correctness of the test oracles.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import stat
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
import zlib

WORKFLOWS = {'full', 'transport', 'visual', 'security', 'soak'}
ARTIFACT_TO_WORKFLOW = {
    'release': 'full', 'baseline': 'full', 'mobile': 'full',
    'http': 'transport', 'visual': 'visual',
    'osv': 'security', 'static': 'security', 'soak': 'soak',
    'mutation': 'full', 'sast': 'security',
}
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools import security_receipt, supply_chain  # noqa: E402

SHA = re.compile(r'[0-9a-f]{40}\Z')
DIGEST = re.compile(r'[0-9a-f]{64}\Z')


class Rejected(ValueError):
    """A single falsified invariant invalidates the entire certificate."""


def require(condition, code):
    if not condition:
        raise Rejected(code)


def num(v, name, *, integer=False, min_value=0):
    require(type(v) is int if integer else type(v) in (float, int), name + '_type')
    require(math.isfinite(v) and v >= min_value, name + '_range')
    return v


def json_bytes(raw):
    def nonfinite(value):
        raise Rejected('non_finite_json_constant_' + value)

    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, 'duplicate_json_key')
            value[key] = item
        return value

    return json.loads(raw, parse_constant=nonfinite, object_pairs_hook=unique)


def lock_sources_at(root, head):
    """Read trusted comparison bytes from the measured Git revision, never the receipts."""
    require(isinstance(head, str) and SHA.fullmatch(head), 'expected_sha_format')
    sources = {}
    for name in supply_chain.LOCKS:
        try:
            sources[name] = subprocess.run(
                ['git', 'cat-file', 'blob', f'{head}:{name}'], cwd=root,
                check=True, capture_output=True, timeout=20).stdout
        except (OSError, subprocess.SubprocessError) as exc:
            raise Rejected('source_lock_unavailable_' + name) from exc
    return sources


def archive(path, expected_sha):
    require(path.is_file() and DIGEST.fullmatch(expected_sha) is not None, 'missing_archive_or_digest')
    require(path.stat().st_size <= 150 * 1024 * 1024, 'zip_size_budget')
    require(hashlib.sha256(path.read_bytes()).hexdigest() == expected_sha, 'zip_sha256')
    z = zipfile.ZipFile(path)
    names = z.namelist()
    require(len(names) == len(set(names)) and len(names) <= 512, 'duplicate_or_too_many_members')
    require(sum(x.file_size for x in z.infolist()) <= 256 * 1024 * 1024, 'zip_expansion_budget')
    for info in z.infolist():
        name = info.filename
        require(name and not name.startswith('/') and '\\' not in name
                and '..' not in Path(name).parts, 'unsafe_zip_path')
        require(stat.S_IFMT(info.external_attr >> 16) != stat.S_IFLNK, 'zip_symlink')
    require(z.testzip() is None, 'zip_crc')
    return z


def member(z, name):
    require(name in z.namelist(), 'missing_member_' + name)
    return z.read(name)


def digest_match(raw, sha):
    require(isinstance(sha, str) and DIGEST.fullmatch(sha) is not None, 'invalid_sha256')
    require(hashlib.sha256(raw).hexdigest() == sha, 'content_sha256')


def junit(z, path, minimum, required=()):
    raw = member(z, path)
    # DTDs are refused before parsing; a UTF-16 document could hide the marker from a byte search.
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        raise Rejected('unsafe_junit') from None
    require(len(raw) < 8 * 1024 * 1024 and '<!DOCTYPE' not in text and '<!ENTITY' not in text, 'unsafe_junit')
    rt = ET.fromstring(raw)
    suites = rt.findall('.//testsuite') if rt.tag == 'testsuites' else [rt]
    cases = rt.findall('.//testcase')
    require(len(suites) > 0 and len(cases) >= minimum, 'junit_coverage_dilution')
    require(sum(int(s.get('tests', -1)) for s in suites) == len(cases), 'junit_count_mismatch')
    require(all(int(s.get(k, -1)) == 0 for s in suites for k in ('errors','failures','skipped')), 'junit_summary_failure')
    require(not any(rt.findall('.//' + k) for k in ('error','failure','skipped')), 'junit_case_failure')
    seen = {}
    full_testcase_ids = set()
    for case in cases:
        classname, name = case.get('classname'), case.get('name')
        require(bool(classname) and bool(name), 'junit_testcase_identity_missing')
        full_identity = (classname, name)
        # Parameterized [0] and [1] are distinct; replaying [0] is not another execution.
        require(full_identity not in full_testcase_ids, 'duplicate_junit_testcase_identity')
        full_testcase_ids.add(full_identity)
        identity = f"{classname}::{name.split('[', 1)[0]}"
        seen[identity] = seen.get(identity, 0) + 1
    for rule in required:
        require(seen.get(rule['id'], 0) >= max(rule['min_cases'], 1), 'required_test_missing_' + rule['id'])
    return len(cases)


def nearest(values, pct):
    return sorted(values)[math.ceil(len(values) * pct / 100) - 1]


def verify_soak(data, budget, head):
    require(data['schema'] == 'pbt-soak-evidence-v1', 'soak_schema')
    require(data['source_sha'] == head and data['profile'] == 'soak', 'soak_head_profile')
    require(data['status'] == 'PASS' and data['violations'] == [], 'soak_report_failure')
    require(data['scope'] == 'synthetic_local_http_sqlite_not_production', 'soak_scope')
    require(data['field_inp'] == 'NOT_MEASURED', 'fake_field_inp')
    rules = budget['budgets']
    require(data['limits'] == rules, 'budget_drift')
    n = num(data['accepted_leads'], 'accepted_leads', integer=True, min_value=3000)
    duration = num(data['observed_duration_s'], 'duration', min_value=1800)
    require(duration >= budget['soak']['minimum_duration_s'] and n >= budget['soak']['minimum_accepted'], 'diluted_soak')
    latency = data['api_latency_samples_ms']
    require(len(latency) == n, 'latency_sample_count')
    for v in latency:
        num(v, 'latency')
    for pct, key in ((50, 'api_p50_ms'), (95, 'api_p95_ms'), (99, 'api_p99_ms')):
        require(abs(nearest(latency, pct) - num(data[key],key)) <= 0.002, 'latency_percentile_mismatch')
    require(data['api_p99_ms'] <= rules['maximum_p99_lead_ms'], 'latency_limit')
    require(abs(max(latency) - num(data['api_max_ms'],'api_max')) <= .002, 'latency_max_mismatch')
    parent = data['rss_sample_epochs_kib']
    child = data['child_rss_sample_epochs_kib']
    counts = data['child_process_sample_epochs']
    require(len(parent) == len(child) == len(counts) == 2, 'memory_epoch_count')
    sums = []
    for p, c, k in zip(parent, child, counts):
        require(len(p) == len(c) == len(k) and len(p) >= 90, 'memory_sample_coverage')
        for a,b,nc in zip(p,c,k):
            num(a,'parent_rss',integer=True,min_value=1)
            num(b,'child_rss',integer=True)
            num(nc,'child_count',integer=True)
            require(nc > 0 or b == 0, 'child_memory_without_process')
            sums.append(a+b)
    max_parent=max(max(ep) for ep in parent)
    growth=max(max(ep)-ep[0] for ep in parent)
    peak_children=max(v for ep in counts for v in ep)
    for key in ('rss_peak_kib', 'rss_growth_max_kib', 'tree_vm_rss_sum_peak_kib',
                'observed_child_processes_peak'):
        num(data[key], key, integer=True)
    require(data['rss_peak_kib'] == max_parent and data['rss_growth_max_kib'] == growth, 'parent_rss_provenance')
    require(data['tree_vm_rss_sum_peak_kib'] == max(sums), 'tree_rss_provenance')
    require(data['observed_child_processes_peak'] == peak_children >= 1, 'child_process_provenance')
    require(data['resource_scope'] == 'sampled_server_plus_descendants_sum_vm_rss_not_cgroup_peak', 'resource_scope')
    require(max_parent <= rules['maximum_rss_kib'] and growth <= rules['maximum_rss_growth_kib_per_process']
            and max(sums) <= rules['maximum_tree_vm_rss_sum_kib']
            and peak_children <= rules['maximum_delivery_descendants'], 'memory_or_child_budget')
    require(num(data['threads_peak'],'threads_peak',integer=True,min_value=1) <= rules['maximum_thread_count'], 'thread_budget')
    require(num(data['pending_outbox_peak'],'pending',integer=True) <= rules['maximum_pending_outbox'], 'backlog_budget')
    require(num(data['drain_elapsed_s'],'drain') <= rules['maximum_drain_s'], 'drain_budget')
    for key in ('leads', 'pending', 'delivered', 'failed'):
        num(data['outbox'][key], 'outbox_' + key, integer=True)
    require(data['outbox'] == dict(leads=n,pending=0,delivered=n,failed=0), 'accepted_outbox_invariant')
    require(data['final_sqlite_integrity'] == 'ok' and data['process_crash_and_restart'] is True, 'recovery_not_verified')
    require(num(data['backup_checkpoints'],'backups',integer=True) >= rules['minimum_backup_checkpoints'], 'backups_not_verified')
    require(num(data['idempotent_replays'],'replays',integer=True) >= 1, 'missing_idempotency')
    crm=data['crm']
    for key in ('observed_distinct_leads', 'total_webhook_attempts', 'invalid_hmac',
                'invalid_payloads', 'unexpected_transport_aborts', 'expected_crash_aborts'):
        num(crm[key], 'crm_' + key, integer=True)
    require(crm['observed_distinct_leads'] == n and crm['total_webhook_attempts'] > n, 'crm_delivery_retry')
    require(all(crm[k] == 0 for k in ('invalid_hmac','invalid_payloads','unexpected_transport_aborts')), 'webhook_integrity')
    require(type(crm['expected_crash_aborts']) is int and 0 <= crm['expected_crash_aborts'] <= 4, 'crash_abort_bound')
    statuses = crm['http_status_counts']
    require(type(statuses) is dict and not set(statuses) - {'200','400','408','429','503'}, 'crm_statuses')
    for count in statuses.values():
        num(count, 'http_status_count', integer=True)
    require(sum(statuses.values()) == crm['total_webhook_attempts'] + crm['expected_crash_aborts']
            and statuses.get('400', 0) == crm['expected_crash_aborts']
            and statuses.get('200', 0) >= n, 'crm_counter_consistency')
    require(all(crm['http_status_counts'].get(str(code), 0) > 0 for code in (408,429,503)), 'fault_classes_missing')
    return {'duration_s': duration, 'accepted': n, 'api_p99_ms': data['api_p99_ms'],
            'tree_rss_peak_kib': max(sums), 'sampled_child_count_max': peak_children}


def verify_png(raw, capture):
    require(raw.startswith(b'\x89PNG\r\n\x1a\n'), 'png_signature')
    require(len(raw) == capture['bytes'], 'png_size')
    digest_match(raw, capture['sha256'])
    i=8; count=0; dims=None; terminal=False
    while i < len(raw):
        require(i + 12 <= len(raw), 'png_truncated')
        n=struct.unpack_from('>I',raw,i)[0]
        require(i + 12 + n <= len(raw), 'png_chunk_overflow')
        typ=raw[i+4:i+8]; data=raw[i+8:i+8+n]
        recorded=struct.unpack_from('>I',raw,i+8+n)[0]
        require(zlib.crc32(typ+data)&0xffffffff == recorded, 'png_chunk_crc')
        if typ == b'IHDR':
            require(n>=8 and dims is None, 'png_header')
            dims=struct.unpack_from('>II', data)
        i+=12+n;count+=1
        if typ == b'IEND':
            terminal=True
            break
    require(terminal and i==len(raw) and dims==(capture['width'],capture['height']), 'png_geometry')
    return count


def verify_mobile(mobile, expected_head, budgets):
    """Budgets are recomputed from raw samples: a producer's own verdict field is never read."""
    require(mobile.get('schema_version') == 3, 'mobile_observer_schema')
    require(mobile['execution_sha']==expected_head and mobile['branch_head_sha'] in (expected_head,None), 'mobile_execution_sha')
    require(mobile['field_vitals_verified'] is False and mobile['inp_ms'] is None
            and mobile['kind']=='synthetic_chromium_lab_not_field_data', 'synthetic_mobile_boundary')
    result={}
    for theme in ('sky','precision'):
        metric=mobile['themes'][theme];raw=metric['raw']
        require(len(raw)>=budgets['min_runs'],'mobile_sample_count')
        for sample in raw:
            observers = sample.get('observers')
            require(isinstance(observers, dict)
                    and observers.get('largest-contentful-paint') == 'registered'
                    and observers.get('layout-shift') == 'registered', 'mobile_observer_unavailable')
        p75_lcp=nearest([num(x['lcp_ms'],'lcp_ms') for x in raw],75)
        p75_cls=nearest([num(x['cls'],'cls') for x in raw],75)
        shift=max(num(x['switch_unprompted_shift_sum'],'switch_shift') for x in raw)
        require(abs(p75_lcp-metric['p75_lcp_ms'])<0.02 and abs(p75_cls-metric['p75_cls'])<0.02, 'mobile_percentile')
        require(p75_lcp<=budgets['lcp_ms'], 'mobile_lcp_budget')
        require(p75_cls<=budgets['cls'], 'mobile_cls_budget')
        require(shift<=budgets['max_deferred_switch_shift'], 'mobile_deferred_shift_budget')
        result[theme]={'p75_lcp_ms':p75_lcp,'p75_cls':p75_cls,'max_deferred_switch_shift':shift}
    return result


def verify_mutation(ledger, expected_head, catalog_raw):
    """Verdicts are recounted against the whole catalog: the ledger's own status field is not read,
    and a slice (--only) or invented rows cannot stand in for the designated faults."""
    require(ledger['head_sha']==expected_head, 'mutation_source_revision')
    require(ledger['catalog_sha256']==hashlib.sha256(catalog_raw).hexdigest(), 'mutation_catalog_digest')
    catalog={m['id']:m for m in json_bytes(catalog_raw)['mutants']}
    results=ledger['results']
    ids=[r['id'] for r in results]
    require(len(ids)==len(set(ids)) and set(ids)==set(catalog), 'mutation_catalog_coverage')
    counts={}
    for row in results:
        verdict=row['verdict']
        counts[verdict]=counts.get(verdict,0)+1
        allowed='UNTESTABLE' if catalog[row['id']].get('expected')=='UNTESTABLE' else 'KILLED'
        require(verdict==allowed, 'mutant_not_killed_'+str(row['id']))
    return counts


def verify_osv(osv, expected_head, lock_name, source):
    require(isinstance(osv, dict), 'osv_receipt_type')
    require(osv.get('schema') == 'pbt-osv-audit-receipt-v2'
            and osv.get('head_sha') == expected_head and osv.get('outcome') == 'success'
            and osv.get('baseline_outcome') == 'success' and osv.get('validation_errors') == []
            and osv.get('require_hashes') is True and osv.get('no_deps') is True
            and osv.get('disable_pip') is True and osv.get('service') == 'OSV'
            and osv.get('action_commit') == security_receipt.ACTION_COMMIT, 'osv_evidence')
    require(osv.get('input') == lock_name and osv.get('requirements_match_head_blob') is True,
            'osv_lock_source')
    digest_match(source, osv.get('requirements_sha256'))
    require(isinstance(osv.get('scanner_version'), str), 'osv_scanner_version')
    security_receipt.Version(osv['scanner_version'])
    output = osv.get('scanner_output')
    require(isinstance(output, str), 'osv_scanner_output')
    digest_match(output.encode('utf-8'), osv.get('scanner_output_sha256'))
    count = security_receipt.verify_report(output, security_receipt.required_packages(source))
    require(type(osv.get('dependency_count')) is int and osv['dependency_count'] == count,
            'osv_dependency_count')
    return count


def verify_sast(z, expected_head, source_locks):
    provenance=json_bytes(member(z,'provenance.json'))
    require(isinstance(provenance, dict) and provenance.get('schema') == 'pbt-provenance-v1'
            and provenance['head_sha']==expected_head and provenance['signed'] is False
            and provenance['slsa_level']=='none_claimed', 'provenance_receipt')
    require(provenance.get('locks_sha256') == {
        name: hashlib.sha256(raw).hexdigest() for name, raw in source_locks.items()
    }, 'provenance_lock_digest')
    report=json_bytes(member(z,'sast.json'))
    require(report['status']=='PASS' and report['open']==[] and report['stale_waivers']==[]
            and report['files_scanned']>=20 and report['loc']>0, 'sast_receipt')
    bom=json_bytes(member(z,'sbom.json'))
    require(bom['bomFormat']=='CycloneDX' and bom['metadata']['component']['version']==expected_head
            and all(c['hashes'] for c in bom['components']) and len(bom['components'])>=5, 'sbom_receipt')
    supply_chain.validate_sbom_contract(bom)
    expected = {}
    for name, raw in source_locks.items():
        for item in supply_chain.parse_locked_requirements(raw.decode('utf-8'), name):
            ref = f"{name}::{item['name']}@{item['version']}"
            require(ref not in expected, 'duplicate_locked_component')
            expected[ref] = {
                'type': 'library', 'name': item['name'], 'version': item['version'],
                'bom-ref': ref, 'purl': f"pkg:pypi/{item['name']}@{item['version']}",
                'scope': 'required', 'properties': [{'name': 'pbt:source-lockfile', 'value': name}],
                'hashes': [{'alg': 'SHA-256', 'content': digest} for digest in item['hashes']],
            }
    require({item['bom-ref']: item for item in bom['components']} == expected, 'sbom_lock_coverage')
    return {'files_scanned':report['files_scanned'],'components':len(bom['components'])}


def policy_digest(*documents):
    return hashlib.sha256(json.dumps(documents,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def verify_manifest(meta, evidence_dir, policy, expected_head, expected_base, evidence_policy, required_tests,
                    mutation_catalog, expected_repo='neuron7x/pbt-site', *, source_locks=None):
    require(SHA.fullmatch(expected_head) and SHA.fullmatch(expected_base), 'expected_sha_format')
    require(meta['schema'] == 'pbt-exact-head-evidence-matrix-v2', 'manifest_schema')
    require(meta['head_sha'] == expected_head and meta['base_sha'] == expected_base, 'manifest_sha_mismatch')
    require(meta['repository']==expected_repo, 'manifest_other_repository')
    if source_locks is None:
        source_locks = lock_sources_at(ROOT, expected_head)
    require(isinstance(source_locks, dict) and set(source_locks) == set(supply_chain.LOCKS)
            and all(isinstance(raw, bytes) for raw in source_locks.values()), 'source_lock_set')
    target=meta['target']
    rules=evidence_policy['targets'].get(target['kind'])
    require(rules is not None, 'unsupported_target_event')
    if target['kind']=='pull_request':
        require(type(target['pr_number']) is int and target['pr_number']>0, 'incorrect_target')
    else:
        require(target['pr_number'] is None and target['ref']==evidence_policy['main_ref'], 'incorrect_target')
    roles=set(rules['roles'])
    workflows={ARTIFACT_TO_WORKFLOW[r] for r in roles}
    runs=meta['runs']; artifacts=meta['artifacts']
    require(set(runs) == workflows and set(artifacts) == roles, 'missing_or_extra_gate')
    used_runs=[];used_ids=[]; archives={}
    for role in workflows:
        run=runs[role]
        require(run['event'] in rules['run_events'], 'receipt_from_other_target_event')
        if target['kind']=='pull_request':
            require(target['pr_number'] in run['pull_requests'], 'run_not_linked_to_this_pull_request')
        require(run['head_sha'] == expected_head
                and run['status'] == 'completed' and run['conclusion'] == 'success', 'stale_or_failed_workflow')
        jobs=run['jobs']
        needed=list(evidence_policy['required_jobs'][role])
        if target['kind']=='pull_request':
            needed+=evidence_policy['required_jobs_pull_request_only'].get(role,[])
        for name in needed:
            require(name in jobs, 'required_job_missing_'+role)
            require(jobs[name]['status']=='completed' and jobs[name]['conclusion']=='success', 'required_job_not_successful_'+role)
        used_runs.append(num(run['id'], 'run_id', integer=True,min_value=1))
        num(run['attempt'], 'run_attempt', integer=True,min_value=1)
    require(len(set(used_runs))==5, 'reused_run_id')
    for role in sorted(roles):
        workflow=ARTIFACT_TO_WORKFLOW[role]
        item=artifacts[role]
        require(item['run_id'] == runs[workflow]['id'], 'artifact_wrong_run')
        used_ids.append(num(item['id'],'artifact_id',integer=True,min_value=1))
        filename=item['filename']
        require(filename == role+'.zip', 'artifact_filename')
        archives[role]=archive(evidence_dir/filename,item['sha256'])
    require(len(set(used_ids)) == len(roles), 'reused_artifact_id')
    need=required_tests['required']
    minimum=evidence_policy['min_tests']
    try:
        test_counts={
            'release': junit(archives['release'],'artifacts/full-junit.xml', minimum['release'], need['release']),
            'http': junit(archives['http'],'http-junit.xml',minimum['http'], need['http']),
        }
        if 'baseline' in roles:
            test_counts['baseline']=junit(archives['baseline'],'base-junit.xml',minimum['baseline'])
            require(member(archives['baseline'],'base-commit.txt').strip().decode('ascii')==expected_base,'base_commit_drift')
        offline=member(archives['release'],'artifacts/offline-bundles.sha256').decode().splitlines()
        expected_html={'dist/pbt-site.html','dist/pbt-site.artifact.html','dist/artifact/index.html'}
        offline_paths=set()
        for line in offline:
            sha,name=line.split('  ')
            require(name in expected_html and name not in offline_paths, 'offline_manifest_member')
            digest_match(member(archives['release'],name),sha)
            offline_paths.add(name)
        require(offline_paths==expected_html,'offline_bundle_coverage')
        scope=json_bytes(member(archives['static'],'scoped-static.json'))
        require(scope['head_sha']==expected_head and scope['status']=='PASS' and scope['findings']==[]
                and scope['files_scanned']>=6 and set(scope['scanned_roots'])=={'server','ops'}, 'scoped_static_evidence')
        osv_by_lock = {
            name: verify_osv(json_bytes(member(archives['osv'], receipt)), expected_head, name, source_locks[name])
            for name, receipt in (('requirements.txt', 'osv-receipt.json'),
                                  ('requirements-sast.txt', 'osv-sast-receipt.json'))
        }
        osv_dependencies = osv_by_lock['requirements.txt']
        mobile=json_bytes(member(archives['mobile'],'dual-theme-mobile.json'))
        mobile_result=verify_mobile(mobile,expected_head,evidence_policy['mobile'])
        mutation=verify_mutation(json_bytes(member(archives['mutation'],'mutation-ledger.json')),expected_head,mutation_catalog)
        sast=verify_sast(archives['sast'],expected_head,source_locks)
        manifest=json_bytes(member(archives['visual'],'shots/manifest.json'))
        media_raw=member(archives['visual'],'media-budget.json')
        media=json_bytes(media_raw)
        ev=json_bytes(member(archives['visual'],'evidence-verification.json'))
        m_raw=member(archives['visual'],'shots/manifest.json')
        require(manifest['revision']==expected_head and manifest['failures']==[] and len(manifest['captures'])==32, 'visual_manifest')
        require(ev['expected_head_sha']==expected_head and ev['ok'] is True and ev['failures']==[] and ev['screenshot_count']==32, 'visual_receipt')
        for key,raw in (('media_report',media_raw),('shots_manifest',m_raw)):
            require(ev['evidence'][key]['bytes']==len(raw),'visual_report_size')
            digest_match(raw,ev['evidence'][key]['sha256'])
        require(media['failures']==[] and media['media_files']>=160 and len(media['files'])==media['media_files'], 'media_report')
        shot_count=0;names=set()
        for capture in manifest['captures']:
            filename=capture['filename']
            require(isinstance(filename,str) and '/' not in filename and '\\' not in filename and filename not in names, 'screenshot_membership')
            shot_count+=verify_png(member(archives['visual'],'shots/'+filename), capture)
            names.add(filename)
        require(len(names)==32, 'screenshot_coverage')
        soak=verify_soak(json_bytes(member(archives['soak'],'soak-evidence.json')),policy,expected_head)
        return {'schema':'pbt-exact-head-evidence-decision-v2','status':'PASS',
                'head_sha':expected_head,'base_sha':expected_base,'target':target,
                'repository':expected_repo,'policy_digest':policy_digest(policy,evidence_policy,required_tests),
                'workflow_count':len(workflows),
                'artifact_count':len(roles),'junit_tests':test_counts,'verified_png':32,
                'verified_png_chunks':shot_count,'soak':soak,'mobile':mobile_result,'mutation':mutation,'sast':sast,'osv_dependencies':osv_dependencies,
                'osv_dependencies_by_lock':osv_by_lock,
                'claim_boundary':'offline cross-consistency of supplied GitHub metadata and bytes, not authenticated GitHub API, production SLO, field INP or merge authorization'}
    finally:
        for z in archives.values():
            z.close()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--evidence-dir',type=Path,required=True)
    parser.add_argument('--policy',type=Path,required=True)
    parser.add_argument('--expected-head',required=True)
    parser.add_argument('--expected-base',required=True)
    parser.add_argument('--evidence-policy',type=Path,default=ROOT/'config/evidence-policy.json')
    parser.add_argument('--required-tests',type=Path,default=ROOT/'config/required-tests.json')
    parser.add_argument('--mutation-catalog',type=Path,default=ROOT/'config/mutation-catalog.json')
    parser.add_argument('--expected-repo',default='neuron7x/pbt-site')
    args=parser.parse_args(argv)
    try:
        result=verify_manifest(json_bytes(args.manifest.read_bytes()),args.evidence_dir,
                               json_bytes(args.policy.read_bytes()),args.expected_head,args.expected_base,
                               json_bytes(args.evidence_policy.read_bytes()),json_bytes(args.required_tests.read_bytes()),
                               args.mutation_catalog.read_bytes(),args.expected_repo)
    except (Rejected,KeyError,TypeError,ValueError,OSError,ET.ParseError,zipfile.BadZipFile,UnicodeError,OverflowError,IndexError) as e:
        print(json.dumps({'status':'FAIL','reason':str(e)[:150],'error_type':type(e).__name__},sort_keys=True))
        return 1
    print(json.dumps(result,sort_keys=True,separators=(',',':')))
    return 0


if __name__=='__main__':
    sys.exit(main())
