#!/usr/bin/env python3
"""Independent consistency/limit re-evaluation of a measured synthetic soak report."""
import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / 'config' / 'runtime-soak-budgets.json'


def percentile(numbers, p):
    nums = sorted(numbers)
    return nums[math.ceil(len(nums) * p / 100) - 1]


def verify(report, budget, expected):
    profile = report['profile']
    if profile not in ('soak', 'smoke'):
        raise ValueError('profile')
    required = budget[profile]
    limits = budget['budgets']
    if report['source_sha'] != expected or report['status'] != 'PASS' or report['violations']:
        raise ValueError('provenance_or_status')
    n, observed = report['accepted_leads'], report['observed_duration_s']
    if n < required['minimum_accepted'] or observed < required['minimum_duration_s']:
        raise ValueError('insufficient_work')
    times = report['api_latency_samples_ms']
    if len(times) != n or any(not isinstance(x, (int, float)) or not math.isfinite(x) or x < 0 for x in times):
        raise ValueError('missing_or_invalid_latency_samples')
    p99 = percentile(times, 99)
    if abs(p99 - report['api_p99_ms']) > .002 or p99 > limits['maximum_p99_lead_ms']:
        raise ValueError('latency_provenance_or_budget')
    rss = report['rss_sample_epochs_kib']
    if len(rss) != 2 or any(not group for group in rss):
        raise ValueError('missing_crash_restart_memory_epoch')
    peak = max(max(group) for group in rss)
    growth = max(max(group) - group[0] for group in rss)
    if peak != report['rss_peak_kib'] or growth != report['rss_growth_max_kib']:
        raise ValueError('memory_provenance')
    if peak > limits['maximum_rss_kib'] or growth > limits['maximum_rss_growth_kib_per_process']:
        raise ValueError('memory_budget')
    if report['resource_scope'] != 'sampled_server_plus_descendants_sum_vm_rss_not_cgroup_peak':
        raise ValueError('resource_scope')
    child_rss = report['child_rss_sample_epochs_kib']
    child_n = report['child_process_sample_epochs']
    if len(child_rss) != len(rss) or len(child_n) != len(rss):
        raise ValueError('missing_child_epochs')
    if any(len(rss[i]) != len(child_rss[i]) or len(rss[i]) != len(child_n[i])
           for i in range(len(rss))):
        raise ValueError('inconsistent_tree_sample_lengths')
    all_rss = [rss_epoch[j] + child_rss[i][j]
               for i, rss_epoch in enumerate(rss)
               for j in range(len(rss_epoch))]
    all_children = [v for epoch in child_n for v in epoch]
    if (not all_rss or any(type(v) is not int or v < 0 for e in child_rss for v in e)
            or any(type(v) is not int or v < 0 for v in all_children)):
        raise ValueError('invalid_tree_samples')
    if (report['tree_vm_rss_sum_peak_kib'] != max(all_rss)
            or report['observed_child_processes_peak'] != max(all_children)):
        raise ValueError('falsified_tree_memory_or_child_peak')
    if max(all_rss) > limits['maximum_tree_vm_rss_sum_kib'] or max(all_children) > limits['maximum_delivery_descendants']:
        raise ValueError('resource_tree_budget')
    if profile == 'soak' and not max(all_children):
        raise ValueError('no_measured_outbound_children')
    if report['threads_peak'] > limits['maximum_thread_count'] or report['pending_outbox_peak'] > limits['maximum_pending_outbox']:
        raise ValueError('bounded_resources')
    if not report['process_crash_and_restart'] or report['backup_checkpoints'] < limits['minimum_backup_checkpoints']:
        raise ValueError('recovery_evidence')
    if report['drain_elapsed_s'] > limits['maximum_drain_s'] or report['final_sqlite_integrity'] != 'ok':
        raise ValueError('drain_or_integrity')
    if report['outbox'] != {'leads': n, 'pending': 0, 'delivered': n, 'failed': 0}:
        raise ValueError('lost_accepted_lead_or_outbox_state')
    crm = report['crm']
    if crm['invalid_hmac'] != 0 or crm['observed_distinct_leads'] != n:
        raise ValueError('signature_or_crm_coverage')
    if crm['invalid_payloads'] != 0 or crm['unexpected_transport_aborts'] != 0:
        raise ValueError('invalid_webhook_or_unexpected_transport_abort')
    if type(crm['expected_crash_aborts']) is not int or not 0 <= crm['expected_crash_aborts'] <= 4:
        raise ValueError('unbounded_crash_transport_aborts')
    if profile == 'soak':
        if not all(crm['http_status_counts'].get(str(x), 0) > 0 for x in (408, 429, 503)):
            raise ValueError('missing_adversarial_fault_class')
        if crm['total_webhook_attempts'] <= n:
            raise ValueError('missing_retry_evidence')
    if report['field_inp'] != 'NOT_MEASURED' or report['scope'] != 'synthetic_local_http_sqlite_not_production':
        raise ValueError('claim_boundary')
    return True


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--expected-head', required=True)
    args = p.parse_args(argv)
    try:
        content = json.loads(args.report.read_text())
        budget = json.loads(CONFIG.read_text())
        verify(content, budget, args.expected_head)
    except (OSError, KeyError, TypeError, ValueError, IndexError, ZeroDivisionError) as exc:
        print(f"soak-verification FAIL: {type(exc).__name__}", file=sys.stderr)
        return 1
    print('soak-verification PASS: independent measured-sample and policy check')
    return 0


if __name__ == '__main__':
    sys.exit(main())
