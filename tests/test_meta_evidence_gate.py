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


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def pack(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as z:
        for path, data in files.items():
            z.writestr(path, data)
    return stream.getvalue()


def junit(n):
    cases = ''.join(f'<testcase classname="T" name="case_{i}" />' for i in range(n))
    return f'<testsuites><testsuite tests="{n}" errors="0" failures="0" skipped="0">{cases}</testsuite></testsuites>'.encode()


def png():
    def chunk(kind, data):
        return struct.pack('>I', len(data))+kind+data+struct.pack('>I', zlib.crc32(kind+data)&0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB',1,1,8,6,0,0,0))
            + chunk(b'IDAT', zlib.compress(b'\x00\xff\x00\x00\xff')) + chunk(b'IEND',b''))


@pytest.fixture
def state(tmp_path):
    # A synthetic fixture does not claim to be an actual GitHub workflow run.
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
    mobile={'branch_head_sha':HEAD,'field_vitals_verified':False,'inp_ms':None,
            'kind':'synthetic_chromium_lab_not_field_data',
            'themes':{theme:{'raw':[{'lcp_ms':1200,'cls':0.01}]*3,
                              'p75_lcp_ms':1200,'p75_cls':0.01} for theme in ('sky','precision')}}
    osv={'head_sha':HEAD,'outcome':'success','require_hashes':True,'no_deps':True,
         'service':'OSV','scanner_output':'','scanner_output_sha256':sha(b'')}
    static={'head_sha':HEAD,'status':'PASS','findings':[],'files_scanned':6,
            'scanned_roots':['server','ops']}
    contents={
        'release':{'artifacts/full-junit.xml':junit(390),
                   'artifacts/offline-bundles.sha256':sha_lines,**raw_html},
        'baseline':{'base-junit.xml':junit(191),'base-commit.txt':(BASE+'\n').encode()},
        'http':{'http-junit.xml':junit(160)},
        'visual':{'shots/manifest.json':manifest,'media-budget.json':media,
                  'evidence-verification.json':visual_receipt,**shots},
        'static':{'scoped-static.json':json.dumps(static).encode()},
        'osv':{'osv-receipt.json':json.dumps(osv).encode()},
        'soak':{'soak-evidence.json':json.dumps(soak).encode()},
        'mobile':{'dual-theme-mobile.json':json.dumps(mobile).encode()},
    }
    runs={x:{'id':i+1,'head_sha':HEAD,'event':'pull_request','status':'completed',
             'conclusion':'success','attempt':1} for i,x in enumerate(sorted(gate.WORKFLOWS))}
    artifacts={}
    for i,(role,owner) in enumerate(gate.ARTIFACT_TO_WORKFLOW.items()):
        path=tmp_path/(role+'.zip');path.write_bytes(pack(contents[role]))
        artifacts[role]={'id':100+i,'run_id':runs[owner]['id'],
                         'filename':role+'.zip','sha256':sha(path.read_bytes())}
    meta={'schema':'pbt-exact-head-evidence-matrix-v1','head_sha':HEAD,'base_sha':BASE,
          'pr_number':8,'draft':True,'runs':runs,'artifacts':artifacts}
    return meta,policy,tmp_path,contents


def test_complete_matrix_accepts_consistent_evidence(state):
    meta,policy,directory,_=state
    result=gate.verify_manifest(meta,directory,policy,HEAD,BASE)
    assert result['status']=='PASS'
    assert result['junit_tests']=={'release':390,'baseline':191,'http':160}
    assert result['verified_png']==32 and result['soak']['accepted']==3000


@pytest.mark.parametrize('mutant',[
    'stale_head','run_cancelled','run_reused','missing_role','artifact_wrong_run',
    'artifact_reused','zip_tampered','junit_falsified','latency_forged',
    'tree_rss_forged','child_rss_missing','outbox_lost','hmac_failure',
    'field_inp_forged','visual_crc_corruption','osv_outcome',
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
    with pytest.raises((gate.Rejected,ValueError)):
        gate.verify_manifest(meta,directory,policy,HEAD,BASE)
