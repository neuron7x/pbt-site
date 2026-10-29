#!/usr/bin/env python3
"""Fail-closed, offline PBT exact-HEAD evidence graph verifier.

Requires real artifact ZIP bytes and an *externally fetched* GitHub run/artefact
manifest. Proves their consistency, NOT authenticity of the provider snapshot,
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
import sys
import xml.etree.ElementTree as ET
import zipfile
import zlib

WORKFLOWS = {'full', 'transport', 'visual', 'security', 'soak'}
ARTIFACT_TO_WORKFLOW = {
    'release': 'full', 'baseline': 'full', 'mobile': 'full',
    'http': 'transport', 'visual': 'visual',
    'osv': 'security', 'static': 'security', 'soak': 'soak',
}
MIN_TESTS = {'release': 390, 'baseline': 191, 'http': 160}
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
    return json.loads(raw, parse_constant=nonfinite)


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


def junit(z, path, minimum):
    raw = member(z, path)
    require(len(raw) < 8 * 1024 * 1024 and b'<!DOCTYPE' not in raw, 'unsafe_junit')
    rt = ET.fromstring(raw)
    suites = rt.findall('.//testsuite') if rt.tag == 'testsuites' else [rt]
    cases = rt.findall('.//testcase')
    require(len(suites) > 0 and len(cases) >= minimum, 'junit_coverage_dilution')
    require(sum(int(s.get('tests', -1)) for s in suites) == len(cases), 'junit_count_mismatch')
    require(all(int(s.get(k, -1)) == 0 for s in suites for k in ('errors','failures','skipped')), 'junit_summary_failure')
    require(not any(rt.findall('.//' + k) for k in ('error','failure','skipped')), 'junit_case_failure')
    return len(cases)


def nearest(values, pct):
    return sorted(values)[math.ceil(len(values) * pct / 100) - 1]


def verify_soak(data, budget, head):
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
            sums.append(a+b)
    max_parent=max(max(ep) for ep in parent)
    growth=max(max(ep)-ep[0] for ep in parent)
    peak_children=max(v for ep in counts for v in ep)
    require(data['rss_peak_kib'] == max_parent and data['rss_growth_max_kib'] == growth, 'parent_rss_provenance')
    require(data['tree_vm_rss_sum_peak_kib'] == max(sums), 'tree_rss_provenance')
    require(data['observed_child_processes_peak'] == peak_children >= 1, 'child_process_provenance')
    require(data['resource_scope'] == 'sampled_server_plus_descendants_sum_vm_rss_not_cgroup_peak', 'resource_scope')
    require(max_parent <= rules['maximum_rss_kib'] and growth <= rules['maximum_rss_growth_kib_per_process']
            and max(sums) <= rules['maximum_tree_vm_rss_sum_kib']
            and peak_children <= rules['maximum_delivery_descendants'], 'memory_or_child_budget')
    require(num(data['threads_peak'],'threads_peak',integer=True) <= rules['maximum_thread_count'], 'thread_budget')
    require(num(data['pending_outbox_peak'],'pending',integer=True) <= rules['maximum_pending_outbox'], 'backlog_budget')
    require(num(data['drain_elapsed_s'],'drain') <= rules['maximum_drain_s'], 'drain_budget')
    require(data['outbox'] == dict(leads=n,pending=0,delivered=n,failed=0), 'accepted_outbox_invariant')
    require(data['final_sqlite_integrity'] == 'ok' and data['process_crash_and_restart'] is True, 'recovery_not_verified')
    require(num(data['backup_checkpoints'],'backups',integer=True) >= rules['minimum_backup_checkpoints'], 'backups_not_verified')
    require(num(data['idempotent_replays'],'replays',integer=True) >= 1, 'missing_idempotency')
    crm=data['crm']
    require(crm['observed_distinct_leads'] == n and crm['total_webhook_attempts'] > n, 'crm_delivery_retry')
    require(all(crm[k] == 0 for k in ('invalid_hmac','invalid_payloads','unexpected_transport_aborts')), 'webhook_integrity')
    require(type(crm['expected_crash_aborts']) is int and 0 <= crm['expected_crash_aborts'] <= 4, 'crash_abort_bound')
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


def verify_manifest(meta, evidence_dir, policy, expected_head, expected_base):
    require(SHA.fullmatch(expected_head) and SHA.fullmatch(expected_base), 'expected_sha_format')
    require(meta['schema'] == 'pbt-exact-head-evidence-matrix-v1', 'manifest_schema')
    require(meta['head_sha'] == expected_head and meta['base_sha'] == expected_base, 'manifest_sha_mismatch')
    require(meta['pr_number'] == 8 and meta['draft'] is True, 'incorrect_target')
    runs=meta['runs']; artifacts=meta['artifacts']
    require(set(runs) == WORKFLOWS and set(artifacts) == set(ARTIFACT_TO_WORKFLOW), 'missing_or_extra_gate')
    used_runs=[];used_ids=[]; archives={}
    for role in WORKFLOWS:
        run=runs[role]
        require(run['head_sha'] == expected_head and run['event'] == 'pull_request'
                and run['status'] == 'completed' and run['conclusion'] == 'success', 'stale_or_failed_workflow')
        used_runs.append(num(run['id'], 'run_id', integer=True,min_value=1))
        num(run['attempt'], 'run_attempt', integer=True,min_value=1)
    require(len(set(used_runs))==5, 'reused_run_id')
    for role,workflow in ARTIFACT_TO_WORKFLOW.items():
        item=artifacts[role]
        require(item['run_id'] == runs[workflow]['id'], 'artifact_wrong_run')
        used_ids.append(num(item['id'],'artifact_id',integer=True,min_value=1))
        filename=item['filename']
        require(filename == role+'.zip', 'artifact_filename')
        archives[role]=archive(evidence_dir/filename,item['sha256'])
    require(len(set(used_ids)) == 8, 'reused_artifact_id')
    try:
        test_counts={
            'release': junit(archives['release'],'artifacts/full-junit.xml', MIN_TESTS['release']),
            'baseline': junit(archives['baseline'],'base-junit.xml',MIN_TESTS['baseline']),
            'http': junit(archives['http'],'http-junit.xml',MIN_TESTS['http']),
        }
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
        osv=json_bytes(member(archives['osv'],'osv-receipt.json'))
        require(osv['head_sha']==expected_head and osv['outcome']=='success'
                and osv['require_hashes'] is True and osv['no_deps'] is True
                and osv['service']=='OSV', 'osv_evidence')
        require(hashlib.sha256(osv['scanner_output'].encode()).hexdigest()==osv['scanner_output_sha256'], 'osv_receipt_integrity')
        mobile=json_bytes(member(archives['mobile'],'dual-theme-mobile.json'))
        require(mobile['branch_head_sha']==expected_head and mobile['field_vitals_verified'] is False
                and mobile['inp_ms'] is None and mobile['kind']=='synthetic_chromium_lab_not_field_data', 'synthetic_mobile_boundary')
        for theme in ('sky','precision'):
            metric=mobile['themes'][theme];raw=metric['raw']
            require(len(raw)>=3,'mobile_sample_count')
            for pct, field, key in ((75,'p75_lcp_ms','lcp_ms'),(75,'p75_cls','cls')):
                vals=[num(x[key],key) for x in raw]
                require(abs(nearest(vals,pct)-metric[field])<0.02, 'mobile_percentile')
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
        return {'schema':'pbt-exact-head-evidence-decision-v1','status':'PASS',
                'head_sha':expected_head,'base_sha':expected_base,'workflow_count':5,
                'artifact_count':8,'junit_tests':test_counts,'verified_png':32,
                'verified_png_chunks':shot_count,'soak':soak,
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
    args=parser.parse_args(argv)
    try:
        result=verify_manifest(json_bytes(args.manifest.read_bytes()),args.evidence_dir,
                               json_bytes(args.policy.read_bytes()),args.expected_head,args.expected_base)
    except (Rejected,KeyError,TypeError,ValueError,OSError,ET.ParseError,zipfile.BadZipFile,UnicodeError,OverflowError,IndexError) as e:
        print(json.dumps({'status':'FAIL','reason':str(e)[:150]},sort_keys=True))
        return 1
    print(json.dumps(result,sort_keys=True,separators=(',',':')))
    return 0


if __name__=='__main__':
    sys.exit(main())
