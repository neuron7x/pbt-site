"""Self-falsification: a healthy synthetic evidence graph and adversarial mutations."""
import copy
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import zipfile
import zlib

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import meta_evidence_gate as gate

HEAD = 'a' * 40
BASE = 'b' * 40
ZIP_ROLES = None


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def pack(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as z:
        for path, data in files.items():
            z.writestr(path, data)
    return stream.getvalue()


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_POLICY = json.loads((ROOT / 'config/evidence-policy.json').read_text())
REQUIRED_TESTS = json.loads((ROOT / 'config/required-tests.json').read_text())


def junit(n, role=None, drop=None, extra=()):
    names = list(extra)
    for rule in REQUIRED_TESTS['required'].get(role, ()):
        cls, name = rule['id'].split('::')
        if rule['id'] != drop:
            names += [(cls, f'{name}[{i}]') for i in range(max(rule['min_cases'], 1))]
    names += [('T', f'case_{i}') for i in range(max(n - len(names), 0))]
    cases = ''.join(f'<testcase classname="{c}" name="{m}" />' for c, m in names)
    return (f'<testsuites><testsuite tests="{len(names)}" errors="0" failures="0" skipped="0">'
            f'{cases}</testsuite></testsuites>').encode()


CATALOG_RAW = (ROOT / 'config/mutation-catalog.json').read_bytes()
CATALOG = json.loads(CATALOG_RAW)['mutants']


def verify(meta, directory, policy, head=HEAD, base=BASE, evidence_policy=None):
    return gate.verify_manifest(meta, directory, policy, head, base, evidence_policy or EVIDENCE_POLICY, REQUIRED_TESTS, CATALOG_RAW)


def png():
    def chunk(kind, data):
        return struct.pack('>I', len(data))+kind+data+struct.pack('>I', zlib.crc32(kind+data)&0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB',1,1,8,6,0,0,0))
            + chunk(b'IDAT', zlib.compress(b'\x00\xff\x00\x00\xff')) + chunk(b'IEND',b''))


@pytest.fixture
def state(tmp_path):
    return build_state(tmp_path)


def _jobs(role):
    names = EVIDENCE_POLICY['required_jobs'][role] + EVIDENCE_POLICY['required_jobs_pull_request_only'].get(role, [])
    return {name: {'id': 1000 + i, 'status': 'completed', 'conclusion': 'success'} for i, name in enumerate(names)}


def build_state(tmp_path, HEAD=HEAD, BASE=BASE, extra_release_cases=(), extra_mutation_verdicts=None, catalog_raw=None, event='pull_request', pr=14):
    # A synthetic fixture does not claim to be an actual GitHub workflow run.
    CATALOG_RAW_ = catalog_raw or CATALOG_RAW
    CATALOG_ = json.loads(CATALOG_RAW_)['mutants']
    policy = {'soak':{'minimum_duration_s':1800,'minimum_accepted':3000},
              'budgets':{'maximum_p99_lead_ms':2000,'maximum_rss_kib':262144,
                         'maximum_rss_growth_kib_per_process':65536,'maximum_thread_count':96,
                         'maximum_pending_outbox':128,'maximum_drain_s':60,
                         'maximum_failed_deliveries':0,'minimum_backup_checkpoints':2,
                         'maximum_tree_vm_rss_sum_kib':393216,'maximum_delivery_descendants':8}}
    n=3000
    soak={'source_sha':HEAD,'profile':'soak','status':'PASS','violations':[],
          'scope':'synthetic_local_http_sqlite_not_production','field_inp':'NOT_MEASURED',
          'limits':policy['budgets'],'accepted_leads':n,'observed_duration_s':1800.001,
          'api_latency_samples_ms':[1.]*n,'api_p50_ms':1.,'api_p95_ms':1.,'api_p99_ms':1.,'api_max_ms':1.,
          'rss_sample_epochs_kib':[[30000]*90,[30100]*90],
          'child_rss_sample_epochs_kib':[[3000]*90,[4000]*90],
          'child_process_sample_epochs':[[1]*90,[1]*90],
          'rss_peak_kib':30100,'rss_growth_max_kib':0,
          'tree_vm_rss_sum_peak_kib':34100,'observed_child_processes_peak':1,
          'resource_scope':'sampled_server_plus_descendants_sum_vm_rss_not_cgroup_peak',
          'threads_peak':4,'pending_outbox_peak':2,'drain_elapsed_s':1.,
          'outbox':{'leads':n,'pending':0,'delivered':n,'failed':0},
          'final_sqlite_integrity':'ok','process_crash_and_restart':True,
          'backup_checkpoints':2,'idempotent_replays':1,
          'crm':{'observed_distinct_leads':n,'total_webhook_attempts':n+20,
                 'invalid_hmac':0,'invalid_payloads':0,'unexpected_transport_aborts':0,
                 'expected_crash_aborts':0,'http_status_counts':{'408':1,'429':1,'503':1}}}
    raw_html={name:(name+'<html></html>').encode() for name in
              ('dist/pbt-site.html','dist/pbt-site.artifact.html','dist/artifact/index.html')}
    sha_lines=''.join(sha(data)+'  '+name+'\n' for name,data in raw_html.items()).encode()
    shots={}; captures=[]; raw_png=png()
    for i in range(32):
        name=f'{i:02d}.png'; shots['shots/'+name]=raw_png
        captures.append({'filename':name,'bytes':len(raw_png),'sha256':sha(raw_png),
                         'height':1,'width':1})
    manifest=json.dumps({'revision':HEAD,'failures':[],'captures':captures}).encode()
    media=json.dumps({'failures':[],'media_files':160,
                      'files':[{'path':f'file{i}'} for i in range(160)]}).encode()
    visual_receipt=json.dumps({'expected_head_sha':HEAD,'ok':True,'failures':[],
                                'screenshot_count':32,'evidence':{
                                'shots_manifest':{'bytes':len(manifest),'sha256':sha(manifest)},
                                'media_report':{'bytes':len(media),'sha256':sha(media)}}}).encode()
    mobile={'execution_sha':HEAD,'branch_head_sha':HEAD,'event_sha':'e'*40,'field_vitals_verified':False,'inp_ms':None,
            'kind':'synthetic_chromium_lab_not_field_data',
            'themes':{theme:{'raw':[{'lcp_ms':1200,'cls':0.01,'switch_unprompted_shift_sum':0.0}]*3,
                              'p75_lcp_ms':1200,'p75_cls':0.01,'synthetic_budget_met':True} for theme in ('sky','precision')}}
    osv_output=json.dumps({'dependencies':[{'name':'a','version':'1','vulns':[]}]})
    osv={'head_sha':HEAD,'outcome':'success','require_hashes':True,'no_deps':True,'dependency_count':1,
         'service':'OSV','scanner_output':osv_output,'scanner_output_sha256':sha(osv_output.encode())}
    static={'head_sha':HEAD,'status':'PASS','findings':[],'files_scanned':6,
            'scanned_roots':['server','ops']}
    mutation={'head_sha':HEAD,'status':'PASS','catalog_sha256':sha(CATALOG_RAW_),
              'results':[{'id':m['id'],'verdict':(extra_mutation_verdicts or {}).get(m['id'],m.get('expected','KILLED'))} for m in CATALOG_]}
    sast={'sast.json':json.dumps({'status':'PASS','open':[],'stale_waivers':[],'files_scanned':30,'loc':100}).encode(),
          'provenance.json':json.dumps({'head_sha':HEAD,'signed':False,'slsa_level':'none_claimed'}).encode(),
          'sbom.json':json.dumps({'bomFormat':'CycloneDX','metadata':{'component':{'version':HEAD}},
                                  'components':[{'hashes':[1]}]*6}).encode()}
    contents={
        'mutation':{'mutation-ledger.json':json.dumps(mutation).encode()},'sast':sast,
        'release':{'artifacts/full-junit.xml':junit(390,'release',extra=extra_release_cases),
                   'artifacts/offline-bundles.sha256':sha_lines,**raw_html},
        'baseline':{'base-junit.xml':junit(191),'base-commit.txt':(BASE+'\n').encode()},
        'http':{'http-junit.xml':junit(160,'http')},
        'visual':{'shots/manifest.json':manifest,'media-budget.json':media,
                  'evidence-verification.json':visual_receipt,**shots},
        'static':{'scoped-static.json':json.dumps(static).encode()},
        'osv':{'osv-receipt.json':json.dumps(osv).encode()},
        'soak':{'soak-evidence.json':json.dumps(soak).encode()},
        'mobile':{'dual-theme-mobile.json':json.dumps(mobile).encode()},
    }
    runs={x:{'id':i+1,'head_sha':HEAD,'event':'pull_request','status':'completed',
             'conclusion':'success','attempt':1,'pull_requests':[14],'jobs':_jobs(x)} for i,x in enumerate(sorted(gate.WORKFLOWS))}
    artifacts={}
    for i,(role,owner) in enumerate(gate.ARTIFACT_TO_WORKFLOW.items()):
        path=tmp_path/(role+'.zip');path.write_bytes(pack(contents[role]))
        artifacts[role]={'id':100+i,'run_id':runs[owner]['id'],
                         'filename':role+'.zip','sha256':sha(path.read_bytes())}
    meta={'schema':'pbt-exact-head-evidence-matrix-v2','repository':'neuron7x/pbt-site','head_sha':HEAD,'base_sha':BASE,
          'target':{'kind':'pull_request','pr_number':14,'ref':'refs/pull/14/head'},'runs':runs,'artifacts':artifacts}
    return meta,policy,tmp_path,contents


def test_complete_matrix_accepts_consistent_evidence(state):
    meta,policy,directory,_=state
    result=verify(meta,directory,policy)
    assert result['status']=='PASS'
    assert result['junit_tests']['baseline']==191 and result['junit_tests']['release']>=390
    assert result['policy_digest']==gate.policy_digest(policy,EVIDENCE_POLICY,REQUIRED_TESTS)
    assert result['target']['pr_number']==14
    assert result['verified_png']==32 and result['soak']['accepted']==3000
    assert result['mutation']['KILLED']==len(CATALOG)-1 and result['mutation']['UNTESTABLE']==1 and result['sast']['components']==6


@pytest.mark.parametrize('mutant',[
    'stale_head','run_cancelled','run_reused','missing_role','artifact_wrong_run',
    'artifact_reused','zip_tampered','junit_falsified','latency_forged',
    'tree_rss_forged','child_rss_missing','outbox_lost','hmac_failure',
    'field_inp_forged','visual_crc_corruption','osv_outcome',
    'historic_pr8_v1_schema','unsupported_event','pr_number_on_main_target','required_test_removed',
    'required_test_skipped','mobile_lcp_over_budget_coherent_summary','mobile_cls_over_budget_coherent_summary',
    'mobile_forged_budget_flag','mobile_late_switch_shift','mobile_wrong_execution_sha','mobile_event_sha_as_execution',
    'wrong_source_revision_all_artifacts','junit_utf16_doctype','soak_coherent_over_latency_budget',
    'mutant_survived_but_status_pass','mutation_catalog_diluted','mutation_other_revision','sast_open_finding','sast_scanned_nothing',
    'sbom_other_revision','provenance_other_revision','png_bad_crc_with_matching_manifest',
    'mutation_invented_rows','mutation_slice','mutation_other_catalog','mutation_killed_untestable_swap',
    'required_job_never_completed','required_job_failed_but_run_success','required_job_missing',
    'fork_same_sha','run_of_another_pull_request','osv_vulnerability_with_success','osv_empty_output',
])
def test_forged_success_is_rejected(state,mutant):
    meta,policy,directory,contents=state
    meta=copy.deepcopy(meta)
    contents=copy.deepcopy(contents)
    def rewrite(role):
        path=directory/(role+'.zip');path.write_bytes(pack(contents[role]))
        meta['artifacts'][role]['sha256']=sha(path.read_bytes())
    if mutant=='stale_head':meta['runs']['soak']['head_sha']='c'*40
    elif mutant=='run_cancelled':meta['runs']['full']['conclusion']='cancelled'
    elif mutant=='run_reused':meta['runs']['visual']['id']=meta['runs']['security']['id']
    elif mutant=='missing_role':del meta['artifacts']['mobile']
    elif mutant=='artifact_wrong_run':meta['artifacts']['osv']['run_id']=99
    elif mutant=='artifact_reused':meta['artifacts']['osv']['id']=meta['artifacts']['static']['id']
    elif mutant=='zip_tampered':(directory/'http.zip').write_bytes(b'corrupt'+(directory/'http.zip').read_bytes())
    elif mutant=='junit_falsified':
        contents['http']['http-junit.xml']=b'<testsuites><testsuite tests="0" failures="0" errors="0" skipped="0"/></testsuites>'
        rewrite('http')
    elif mutant in ('latency_forged','tree_rss_forged','child_rss_missing','outbox_lost','hmac_failure'):
        d=json.loads(contents['soak']['soak-evidence.json'])
        if mutant=='latency_forged':d['api_p99_ms']=0.
        if mutant=='tree_rss_forged':d['tree_vm_rss_sum_peak_kib']=30000
        if mutant=='child_rss_missing':d['child_rss_sample_epochs_kib'][0].pop()
        if mutant=='outbox_lost':d['outbox']['delivered']-=1
        if mutant=='hmac_failure':d['crm']['invalid_hmac']+=1
        contents['soak']['soak-evidence.json']=json.dumps(d).encode();rewrite('soak')
    elif mutant=='field_inp_forged':
        d=json.loads(contents['mobile']['dual-theme-mobile.json']);d['field_vitals_verified']=True
        contents['mobile']['dual-theme-mobile.json']=json.dumps(d).encode();rewrite('mobile')
    elif mutant=='visual_crc_corruption':
        png_file=contents['visual']['shots/00.png'];contents['visual']['shots/00.png']=png_file[:-5]+b'bad!!'
        rewrite('visual')
    elif mutant=='osv_outcome':
        d=json.loads(contents['osv']['osv-receipt.json']);d['outcome']='failure'
        contents['osv']['osv-receipt.json']=json.dumps(d).encode();rewrite('osv')
    elif mutant=='required_job_never_completed':
        name=EVIDENCE_POLICY['required_jobs']['soak'][0];meta['runs']['soak']['jobs'][name].update(status='in_progress',conclusion=None)
    elif mutant=='required_job_failed_but_run_success':
        name=EVIDENCE_POLICY['required_jobs']['full'][-1];meta['runs']['full']['jobs'][name]['conclusion']='skipped'
    elif mutant=='required_job_missing':
        del meta['runs']['security']['jobs'][EVIDENCE_POLICY['required_jobs']['security'][2]]
    elif mutant=='fork_same_sha':meta['repository']='attacker/pbt-site'
    elif mutant=='run_of_another_pull_request':meta['runs']['soak']['pull_requests']=[99]
    elif mutant in ('osv_vulnerability_with_success','osv_empty_output'):
        d=json.loads(contents['osv']['osv-receipt.json'])
        out={'dependencies':[{'name':'a','version':'1','vulns':[{'id':'CVE-1'}]}]} if mutant=='osv_vulnerability_with_success' else {'dependencies':[]}
        d['scanner_output']=json.dumps(out);d['scanner_output_sha256']=sha(d['scanner_output'].encode())
        contents['osv']['osv-receipt.json']=json.dumps(d).encode();rewrite('osv')
    elif mutant=='png_bad_crc_with_matching_manifest':
        # Every digest in the chain is recomputed by the forger: only the CRC walk can catch this.
        raw=bytearray(contents['visual']['shots/00.png']);raw[-20]^=0xff;raw=bytes(raw)
        contents['visual']['shots/00.png']=raw
        manifest_doc=json.loads(contents['visual']['shots/manifest.json'])
        manifest_doc['captures'][0]['sha256']=sha(raw)
        manifest_raw=json.dumps(manifest_doc).encode()
        contents['visual']['shots/manifest.json']=manifest_raw
        receipt=json.loads(contents['visual']['evidence-verification.json'])
        receipt['evidence']['shots_manifest']={'bytes':len(manifest_raw),'sha256':sha(manifest_raw)}
        contents['visual']['evidence-verification.json']=json.dumps(receipt).encode();rewrite('visual')
    elif mutant=='soak_coherent_over_latency_budget':
        d=json.loads(contents['soak']['soak-evidence.json']);v=float(policy['budgets']['maximum_p99_lead_ms']+1)
        d['api_latency_samples_ms']=[v]*d['accepted_leads']
        d.update(api_p50_ms=v,api_p95_ms=v,api_p99_ms=v,api_max_ms=v)
        contents['soak']['soak-evidence.json']=json.dumps(d).encode();rewrite('soak')
    elif mutant.startswith('mutant_survived') or mutant.startswith('mutation_'):
        d=json.loads(contents['mutation']['mutation-ledger.json'])
        if mutant=='mutant_survived_but_status_pass':d['results'][0]['verdict']='SURVIVED'
        if mutant=='mutation_catalog_diluted':d['results']=d['results'][:5]
        if mutant=='mutation_invented_rows':d['results']=[{'id':f'X{i}','verdict':'KILLED'} for i in range(60)]
        if mutant=='mutation_slice':d['results']=d['results'][:-1]
        if mutant=='mutation_other_catalog':d['catalog_sha256']='0'*64
        if mutant=='mutation_killed_untestable_swap':d['results'][0]['verdict']='UNTESTABLE'
        if mutant=='mutation_other_revision':d['head_sha']='c'*40
        contents['mutation']['mutation-ledger.json']=json.dumps(d).encode();rewrite('mutation')
    elif mutant.startswith('sast_') or mutant.startswith('sbom_') or mutant.startswith('provenance_'):
        name={'sast':'sast.json','sbom':'sbom.json','prov':'provenance.json'}[mutant[:4].rstrip('_')]
        d=json.loads(contents['sast'][name])
        if mutant=='sast_open_finding':d['open']=[{'id':'x'}]
        if mutant=='sast_scanned_nothing':d['files_scanned']=0
        if mutant=='sbom_other_revision':d['metadata']['component']['version']='c'*40
        if mutant=='provenance_other_revision':d['head_sha']='c'*40
        contents['sast'][name]=json.dumps(d).encode();rewrite('sast')
    elif mutant=='junit_utf16_doctype':
        raw=contents['release']['artifacts/full-junit.xml'].decode()
        contents['release']['artifacts/full-junit.xml']=('<!DOCTYPE x>'+raw).encode('utf-16');rewrite('release')
    elif mutant=='historic_pr8_v1_schema':
        meta['schema']='pbt-exact-head-evidence-matrix-v1';meta['pr_number']=8;meta['draft']=True
    elif mutant=='unsupported_event':meta['target']['kind']='schedule'
    elif mutant=='pr_number_on_main_target':meta['target']={'kind':'push','pr_number':14,'ref':'refs/heads/main'}
    elif mutant=='required_test_removed':
        # Total count stays far above the minimum: only identity can catch this.
        contents['release']['artifacts/full-junit.xml']=junit(2000,'release',
            'tests.test_data_integrity::test_process_death_at_each_acceptance_cutpoint')
        rewrite('release')
    elif mutant=='required_test_skipped':
        raw=contents['release']['artifacts/full-junit.xml'].decode()
        raw=raw.replace('name="test_process_death_at_each_acceptance_cutpoint[0]" />',
                        'name="test_process_death_at_each_acceptance_cutpoint[0]"><skipped/></testcase>')
        contents['release']['artifacts/full-junit.xml']=raw.encode();rewrite('release')
    elif mutant.startswith('mobile_'):
        d=json.loads(contents['mobile']['dual-theme-mobile.json']);m=d['themes']['sky']
        if mutant=='mobile_lcp_over_budget_coherent_summary':
            m['raw']=[{**x,'lcp_ms':2700} for x in m['raw']];m['p75_lcp_ms']=2700
        if mutant=='mobile_cls_over_budget_coherent_summary':
            m['raw']=[{**x,'cls':0.2} for x in m['raw']];m['p75_cls']=0.2
        if mutant=='mobile_forged_budget_flag':
            m['raw']=[{**x,'lcp_ms':9000} for x in m['raw']];m['p75_lcp_ms']=9000;m['synthetic_budget_met']=True
        if mutant=='mobile_late_switch_shift':
            m['raw']=[{**x,'switch_unprompted_shift_sum':0.2} for x in m['raw']]
        if mutant=='mobile_wrong_execution_sha':d['execution_sha']='c'*40
        if mutant=='mobile_event_sha_as_execution':d['execution_sha']=d['event_sha']
        contents['mobile']['dual-theme-mobile.json']=json.dumps(d).encode();rewrite('mobile')
    elif mutant=='wrong_source_revision_all_artifacts':
        for role,member_name,key in (('soak','soak-evidence.json','source_sha'),('static','scoped-static.json','head_sha'),
                                     ('osv','osv-receipt.json','head_sha')):
            d=json.loads(contents[role][member_name]);d[key]='c'*40
            contents[role][member_name]=json.dumps(d).encode();rewrite(role)
    with pytest.raises((gate.Rejected,ValueError,KeyError)):
        verify(meta,directory,policy)


def test_baseline_job_is_required_for_pull_requests_and_not_for_main(state):
    meta,policy,directory,_=state
    meta=copy.deepcopy(meta)
    del meta['runs']['full']['jobs']['Independent exact-main make gate (no main mutation)']
    with pytest.raises(gate.Rejected,match='required_job_missing_full'):
        verify(meta,directory,policy)


def test_main_target_uses_push_receipts_and_needs_no_baseline(state):
    meta,policy,directory,_=state
    meta=copy.deepcopy(meta)
    meta['target']={'kind':'push','pr_number':None,'ref':'refs/heads/main'}
    del meta['artifacts']['baseline']
    for run in meta['runs'].values():
        run['event']='push'
        run['jobs'].pop('Independent exact-main make gate (no main mutation)',None)
    meta['runs']['soak']['event']='workflow_dispatch'
    assert verify(meta,directory,policy)['status']=='PASS'


def test_pull_request_receipts_never_certify_main(state):
    meta,policy,directory,_=state
    meta=copy.deepcopy(meta)
    meta['target']={'kind':'push','pr_number':None,'ref':'refs/heads/main'}
    del meta['artifacts']['baseline']
    with pytest.raises(gate.Rejected,match='receipt_from_other_target_event'):
        verify(meta,directory,policy)


def test_main_receipts_never_certify_a_pull_request(state):
    meta,policy,directory,_=state
    meta=copy.deepcopy(meta)
    for run in meta['runs'].values():
        run['event']='push'
    with pytest.raises(gate.Rejected,match='receipt_from_other_target_event'):
        verify(meta,directory,policy)


def test_required_inventory_names_tests_that_really_exist():
    """A typo here would make the gate reject everything, or an empty rule certify nothing."""
    for rules in REQUIRED_TESTS['required'].values():
        for rule in rules:
            module,name=rule['id'].split('::')
            source=(ROOT/(module.replace('.','/')+'.py')).read_text(encoding='utf-8')
            assert f'def {name}(' in source,rule['id']
            assert rule['min_cases']>=1,rule['id']
