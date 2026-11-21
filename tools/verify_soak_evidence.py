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


def measurement(value, name, *, integer=False, minimum=0):
    valid_type = type(value) is int if integer else type(value) in (int, float)
    if (not valid_type or (type(value) is float and not math.isfinite(value))
            or value < minimum):
        raise ValueError('invalid_' + name)
    return value


def strict_json(raw):
    def nonfinite(value):
        raise ValueError('non_finite_json_constant_' + value)

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate_json_key')
            result[key] = value
        return result

    return json.loads(raw, parse_constant=nonfinite, object_pairs_hook=unique)


def verify(report, budget, expected):
    if report['schema'] != 'pbt-soak-evidence-v1':
        raise ValueError('schema')
    profile = report['profile']
    if profile not in ('soak', 'smoke'):
        raise ValueError('profile')
    required = budget[profile]
    limits = budget['budgets']
    if report['source_sha'] != expected or report['status'] != 'PASS' or report['violations'] != []:
        raise ValueError('provenance_or_status')
    n = measurement(report['accepted_leads'], 'accepted_leads', integer=True, minimum=1)
    observed = measurement(report['observed_duration_s'], 'duration')
    if n < required['minimum_accepted'] or observed < required['minimum_duration_s']:
        raise ValueError('insufficient_work')
    times = report['api_latency_samples_ms']
    if type(times) is not list or len(times) != n:
        raise ValueError('missing_or_invalid_latency_samples')
    for value in times:
        measurement(value, 'latency_sample')
    p99 = percentile(times, 99)
    if abs(p99 - measurement(report['api_p99_ms'], 'p99')) > .002 or p99 > limits['maximum_p99_lead_ms']:
        raise ValueError('latency_provenance_or_budget')
    rss = report['rss_sample_epochs_kib']
    if type(rss) is not list or len(rss) != 2 or any(type(group) is not list or not group for group in rss):
        raise ValueError('missing_crash_restart_memory_epoch')
    for group in rss:
        for value in group:
            measurement(value, 'parent_rss_sample', integer=True, minimum=1)
    peak = max(max(group) for group in rss)
    growth = max(max(group) - group[0] for group in rss)
    if (peak != measurement(report['rss_peak_kib'], 'rss_peak', integer=True)
            or growth != measurement(report['rss_growth_max_kib'], 'rss_growth', integer=True)):
        raise ValueError('memory_provenance')
    if peak > limits['maximum_rss_kib'] or growth > limits['maximum_rss_growth_kib_per_process']:
        raise ValueError('memory_budget')
    if report['resource_scope'] != 'sampled_server_plus_descendants_sum_vm_rss_not_cgroup_peak':
        raise ValueError('resource_scope')
    child_rss = report['child_rss_sample_epochs_kib']
    child_n = report['child_process_sample_epochs']
    if (type(child_rss) is not list or type(child_n) is not list
            or len(child_rss) != len(rss) or len(child_n) != len(rss)
            or any(type(group) is not list for group in child_rss + child_n)):
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
    if any(memory > 0 and count == 0 for memories, counts in zip(child_rss, child_n)
           for memory, count in zip(memories, counts)):
        raise ValueError('child_memory_without_process')
    if (measurement(report['tree_vm_rss_sum_peak_kib'], 'tree_rss_peak', integer=True) != max(all_rss)
            or measurement(report['observed_child_processes_peak'], 'child_peak', integer=True) != max(all_children)):
        raise ValueError('falsified_tree_memory_or_child_peak')
    if max(all_rss) > limits['maximum_tree_vm_rss_sum_kib'] or max(all_children) > limits['maximum_delivery_descendants']:
        raise ValueError('resource_tree_budget')
    if profile == 'soak' and not max(all_children):
        raise ValueError('no_measured_outbound_children')
    if (measurement(report['threads_peak'], 'threads_peak', integer=True, minimum=1) > limits['maximum_thread_count']
            or measurement(report['pending_outbox_peak'], 'pending_peak', integer=True) > limits['maximum_pending_outbox']):
        raise ValueError('bounded_resources')
    if (report['process_crash_and_restart'] is not True
            or measurement(report['backup_checkpoints'], 'backups', integer=True) < limits['minimum_backup_checkpoints']):
        raise ValueError('recovery_evidence')
    if measurement(report['drain_elapsed_s'], 'drain') > limits['maximum_drain_s'] or report['final_sqlite_integrity'] != 'ok':
        raise ValueError('drain_or_integrity')
    for key in ('leads', 'pending', 'delivered', 'failed'):
        measurement(report['outbox'][key], 'outbox_' + key, integer=True)
    if report['outbox'] != {'leads': n, 'pending': 0, 'delivered': n, 'failed': 0}:
        raise ValueError('lost_accepted_lead_or_outbox_state')
    crm = report['crm']
    for key in ('observed_distinct_leads', 'total_webhook_attempts', 'invalid_hmac',
                'invalid_payloads', 'unexpected_transport_aborts', 'expected_crash_aborts'):
        measurement(crm[key], 'crm_' + key, integer=True)
    if crm['invalid_hmac'] != 0 or crm['observed_distinct_leads'] != n:
        raise ValueError('signature_or_crm_coverage')
    if crm['invalid_payloads'] != 0 or crm['unexpected_transport_aborts'] != 0:
        raise ValueError('invalid_webhook_or_unexpected_transport_abort')
    if type(crm['expected_crash_aborts']) is not int or not 0 <= crm['expected_crash_aborts'] <= 4:
        raise ValueError('unbounded_crash_transport_aborts')
    statuses = crm['http_status_counts']
    if type(statuses) is not dict or set(statuses) - {'200', '400', '408', '429', '503'}:
        raise ValueError('invalid_crm_statuses')
    for count in statuses.values():
        measurement(count, 'http_status_count', integer=True)
    # Valid-body attempts and crash-aborted bodies are separate producer counters.
    # A timed-out 200 can be retried, so successful responses may exceed leads.
    if (sum(statuses.values()) != crm['total_webhook_attempts'] + crm['expected_crash_aborts']
            or statuses.get('400', 0) != crm['expected_crash_aborts']
            or statuses.get('200', 0) < n):
        raise ValueError('inconsistent_crm_accounting')
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
        content = strict_json(args.report.read_text())
        budget = strict_json(CONFIG.read_text())
        verify(content, budget, args.expected_head)
    except (OSError, KeyError, TypeError, ValueError, IndexError, ZeroDivisionError) as exc:
        print(f"soak-verification FAIL: {type(exc).__name__}", file=sys.stderr)
        return 1
    print('soak-verification PASS: independent measured-sample and policy check')
    return 0


if __name__ == '__main__':
    sys.exit(main())
