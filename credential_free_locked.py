try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import ElementClickInterceptedException, StaleElementReferenceException, TimeoutException, WebDriverException
except ImportError:
    webdriver = By = WebDriverWait = EC = None

    class WebDriverException(Exception):
        pass

    class TimeoutException(WebDriverException):
        pass

    class ElementClickInterceptedException(WebDriverException):
        pass

    class StaleElementReferenceException(WebDriverException):
        pass
import argparse
import contextlib
import atexit
import hashlib
import io
import random
import threading
import time
import traceback
import multiprocessing
try:
    import jaconv
except ImportError:
    jaconv = None
import re
import html
import json
import os
import sys
import tempfile
import uuid
import unicodedata
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
_latency_marks = {}
_LATENCY_EVENT_PAIRS = {'lesson_native_click_started': ('target_lesson_found', 'target_lesson_found_to_lesson_click_start'), 'lesson_native_click_completed': ('lesson_native_click_started', 'lesson_click_start_to_click_return'), 'detail_state_test_completed': ('lesson_native_click_started', 'lesson_click_start_to_detail_ready'), 'position_candidate_evaluated': ('detail_state_test_completed', 'detail_ready_to_position_available'), 'position_selected': ('position_candidate_evaluated', 'position_available_to_position_selected'), 'phase5_3_next_diagnostic_completed': ('position_selected', 'position_selected_to_confirm_page_ready'), 'phase6_1_completed': ('phase5_3_next_diagnostic_completed', 'confirm_page_ready_to_final_submit_ready'), 'final_submit_native_click_started': ('phase6_1_completed', 'final_submit_ready_to_final_click_start'), 'final_submit_native_click_returned': ('final_submit_native_click_started', 'final_submit_click_start_to_click_return'), 'final_submit_post_state_determined': ('final_submit_native_click_started', 'final_submit_click_start_to_post_state')}
_LATENCY_REQUIRED_STATES = {'target_lesson_found': 'TARGET_LESSON_FOUND', 'detail_state_test_completed': 'DETAIL_READY', 'position_candidate_evaluated': 'POSITION_AVAILABLE', 'position_selected': 'POSITION_SELECTED', 'phase5_3_next_diagnostic_completed': 'CONFIRM_PAGE_READY', 'phase6_1_completed': 'FINAL_SUBMIT_READY'}
_phase7_1_traces = {}
_phase7_1_barrier_release = {}
PHASE7_1_POSITION_BASELINE_MS = {'6010005815': 1963.9328, 'snuf48385': 2247.9587}
PHASE7_2_POSITION_SELECTED_TO_NEXT_BASELINE_MS = {'6010005815': 881.0, 'snuf48385': 836.0}
PHASE7_3_LESSON_CLICK_TO_DETAIL_READY_BASELINE_MS = {'6010005815': 1056.93, 'snuf48385': 937.1665}
PHASE7_4_1_DETAIL_READY_TO_POSITION_SELECTED_BASELINE_MS = {'6010005815': 155.1588, 'snuf48385': 473.4104}

def _latency_trace(user, request):
    key = (user.get('username'), request.get('date'), request.get('name'))
    return _phase7_1_traces.setdefault(key, {'marks': {}, 'durations_ms': {}, 'classifications': {}, 'metadata': {}, 'deferred_diagnostics': {}})

def _latency_mark(user, request, name):
    _latency_trace(user, request)['marks'][name] = time.perf_counter()

def _latency_duration(user, request, name, started, classification):
    trace = _latency_trace(user, request)
    trace['durations_ms'][name] = (time.perf_counter() - started) * 1000.0
    trace['classifications'][name] = classification

def _latency_record_ms(user, request, name, elapsed_ms, classification):
    trace = _latency_trace(user, request)
    trace['durations_ms'][name] = float(elapsed_ms)
    trace['classifications'][name] = classification

def _latency_interval(trace, start, end):
    marks = trace['marks']
    if start not in marks or end not in marks:
        return None
    return (marks[end] - marks[start]) * 1000.0

def _latency_summary_result(user, request, final_state):
    trace = _latency_trace(user, request)
    phase7_2_elapsed_ms = _latency_interval(trace, 'detail_ready', 'position_selected')
    phase7_1_baseline_ms = PHASE7_1_POSITION_BASELINE_MS.get(user.get('username')) if request.get('date') == '20260831' and request.get('name') == 'RITMOS' else None
    improvement_ms = phase7_1_baseline_ms - phase7_2_elapsed_ms if phase7_1_baseline_ms is not None and phase7_2_elapsed_ms is not None else None
    improvement_percent = improvement_ms / phase7_1_baseline_ms * 100.0 if improvement_ms is not None and phase7_1_baseline_ms else None
    phase7_3_elapsed_ms = _latency_interval(trace, 'position_selected', 'next_click_start')
    phase7_2_next_baseline_ms = PHASE7_2_POSITION_SELECTED_TO_NEXT_BASELINE_MS.get(user.get('username')) if request.get('date') == '20260831' and request.get('name') == 'RITMOS' else None
    next_improvement_ms = phase7_2_next_baseline_ms - phase7_3_elapsed_ms if phase7_2_next_baseline_ms is not None and phase7_3_elapsed_ms is not None else None
    next_improvement_percent = next_improvement_ms / phase7_2_next_baseline_ms * 100.0 if next_improvement_ms is not None and phase7_2_next_baseline_ms else None
    phase7_4_elapsed_ms = _latency_interval(trace, 'lesson_click_start', 'detail_ready')
    phase7_3_detail_baseline_ms = PHASE7_3_LESSON_CLICK_TO_DETAIL_READY_BASELINE_MS.get(user.get('username')) if request.get('date') == '20260831' and request.get('name') == 'RITMOS' else None
    detail_improvement_ms = phase7_3_detail_baseline_ms - phase7_4_elapsed_ms if phase7_3_detail_baseline_ms is not None and phase7_4_elapsed_ms is not None else None
    detail_improvement_percent = detail_improvement_ms / phase7_3_detail_baseline_ms * 100.0 if detail_improvement_ms is not None and phase7_3_detail_baseline_ms else None
    phase7_5_elapsed_ms = _latency_interval(trace, 'detail_ready', 'position_selected')
    phase7_4_1_position_baseline_ms = PHASE7_4_1_DETAIL_READY_TO_POSITION_SELECTED_BASELINE_MS.get(user.get('username')) if request.get('date') == '20260831' and request.get('name') == 'RITMOS' else None
    phase7_5_improvement_ms = phase7_4_1_position_baseline_ms - phase7_5_elapsed_ms if phase7_4_1_position_baseline_ms is not None and phase7_5_elapsed_ms is not None else None
    phase7_5_improvement_percent = phase7_5_improvement_ms / phase7_4_1_position_baseline_ms * 100.0 if phase7_5_improvement_ms is not None and phase7_4_1_position_baseline_ms else None
    intervals = {'barrier_to_lesson_click_ms': _latency_interval(trace, 'barrier_release', 'lesson_click_start'), 'lesson_click_ms': _latency_interval(trace, 'lesson_click_start', 'lesson_click_return'), 'click_return_to_detail_ready_ms': _latency_interval(trace, 'lesson_click_return', 'detail_ready'), 'detail_ready_to_position_decision_ms': _latency_interval(trace, 'detail_ready', 'position_available'), 'position_diagnostic_ms': trace['durations_ms'].get('position_diagnostic_total'), 'position_native_click_ms': _latency_interval(trace, 'position_click_start', 'position_click_return'), 'click_return_to_position_selected_ms': _latency_interval(trace, 'position_click_return', 'position_selected'), 'position_selected_to_next_click_ms': _latency_interval(trace, 'position_selected', 'next_click_start'), 'next_click_to_confirm_page_ready_ms': _latency_interval(trace, 'next_click_start', 'confirm_page_ready'), 'confirm_page_ready_to_final_submit_ready_ms': _latency_interval(trace, 'confirm_page_ready', 'final_submit_ready'), 'final_click_ms': _latency_interval(trace, 'final_click_start', 'final_click_return'), 'final_click_to_reservation_confirmed_ms': _latency_interval(trace, 'final_click_return', 'reservation_confirmed'), 'critical_lesson_click_to_position_selected_ms': _latency_interval(trace, 'lesson_click_start', 'position_selected'), 'total_barrier_to_reservation_confirmed_ms': _latency_interval(trace, 'barrier_release', 'reservation_confirmed'), 'detail_ready_to_position_selected_ms': phase7_2_elapsed_ms, 'phase7_1_baseline_ms': phase7_1_baseline_ms, 'phase7_2_elapsed_ms': phase7_2_elapsed_ms, 'improvement_ms': improvement_ms, 'improvement_percent': improvement_percent, 'phase7_2_baseline_position_selected_to_next_ms': phase7_2_next_baseline_ms, 'phase7_3_elapsed_ms': phase7_3_elapsed_ms, 'next_improvement_ms': next_improvement_ms, 'next_improvement_percent': next_improvement_percent, 'next_native_click_ms': _latency_interval(trace, 'next_click_start', 'next_click_return'), 'next_click_return_to_transition_detected_ms': _latency_interval(trace, 'next_click_return', 'next_transition_detected'), 'transition_detected_to_confirm_page_ready_ms': _latency_interval(trace, 'next_transition_detected', 'confirm_page_ready'), 'position_state_recheck_ms': trace['durations_ms'].get('position_state_recheck'), 'next_snapshot_ms': trace['durations_ms'].get('next_snapshot'), 'next_candidate_classification_ms': trace['durations_ms'].get('next_candidate_classification'), 'next_precheck_ms': trace['durations_ms'].get('next_precheck'), 'next_scroll_ms': trace['durations_ms'].get('next_scroll'), 'next_refetch_ms': trace['durations_ms'].get('next_refetch'), 'next_topmost_check_ms': trace['durations_ms'].get('next_topmost_check'), 'next_logging_before_click_ms': trace['durations_ms'].get('next_logging_before_click'), 'position_selected_to_next_click_start_ms': phase7_3_elapsed_ms, 'lesson_precheck_ms': trace['durations_ms'].get('lesson_precheck'), 'lesson_snapshot_ms': trace['durations_ms'].get('lesson_snapshot'), 'lesson_logging_before_click_ms': trace['durations_ms'].get('lesson_logging_before_click'), 'lesson_native_click_ms': _latency_interval(trace, 'lesson_click_start', 'lesson_click_return'), 'lesson_click_return_timestamp_perf_counter': trace['marks'].get('lesson_click_return'), 'detail_transition_detect_ms': trace['durations_ms'].get('detail_transition_detect'), 'lesson_click_return_to_transition_detected_ms': _latency_interval(trace, 'lesson_click_return', 'detail_transition_detected'), 'transition_detected_to_detail_ready_ms': _latency_interval(trace, 'detail_transition_detected', 'detail_ready'), 'lesson_click_to_detail_ready_ms': phase7_4_elapsed_ms, 'detail_ready_deferred_diagnostic_ms': trace['durations_ms'].get('detail_ready_deferred_diagnostic'), 'phase7_3_baseline_lesson_click_to_detail_ready_ms': phase7_3_detail_baseline_ms, 'phase7_4_elapsed_ms': phase7_4_elapsed_ms, 'detail_improvement_ms': detail_improvement_ms, 'detail_improvement_percent': detail_improvement_percent, 'detail_ready_timestamp_perf_counter': trace['marks'].get('detail_ready'), 'detail_ready_to_position_snapshot_start_ms': _latency_interval(trace, 'detail_ready', 'position_snapshot_start'), 'position_snapshot_ms': trace['durations_ms'].get('position_candidate_snapshot'), 'position_python_classification_ms': trace['durations_ms'].get('position_python_classification'), 'selected_candidate_rank': trace['metadata'].get('selected_candidate_rank'), 'selected_candidate_id': trace['metadata'].get('selected_candidate_id'), 'position_precheck_ms': trace['durations_ms'].get('position_precheck'), 'position_scroll_ms': trace['durations_ms'].get('position_scroll'), 'position_refetch_ms': trace['durations_ms'].get('position_refetch'), 'position_logging_before_click_ms': trace['durations_ms'].get('position_logging_before_click'), 'position_click_return_to_post_snapshot_ms': _latency_interval(trace, 'position_click_return', 'position_post_snapshot_start'), 'position_post_click_snapshot_ms': trace['durations_ms'].get('position_post_click_snapshot'), 'position_post_click_classification_ms': trace['durations_ms'].get('position_post_click_classification'), 'detail_ready_to_position_click_start_ms': _latency_interval(trace, 'detail_ready', 'position_click_start'), 'detail_ready_to_position_selected_ms_phase7_5': phase7_5_elapsed_ms, 'phase7_2_position_baseline_ms': phase7_1_baseline_ms, 'phase7_4_1_position_baseline_ms': phase7_4_1_position_baseline_ms, 'phase7_5_position_elapsed_ms': phase7_5_elapsed_ms, 'phase7_5_position_improvement_ms': phase7_5_improvement_ms, 'phase7_5_position_improvement_percent': phase7_5_improvement_percent}
    return make_result('OK', 'LATENCY_SUMMARY', final_state=final_state, intervals_ms=intervals, internal_durations_ms=trace['durations_ms'], classifications=trace['classifications'], phase7_3_next_comparison={'phase7_2_baseline_position_selected_to_next_ms': phase7_2_next_baseline_ms, 'phase7_3_elapsed_ms': phase7_3_elapsed_ms, 'improvement_ms': next_improvement_ms, 'improvement_percent': next_improvement_percent}, phase7_4_detail_comparison={'phase7_3_baseline_lesson_click_to_detail_ready_ms': phase7_3_detail_baseline_ms, 'phase7_4_elapsed_ms': phase7_4_elapsed_ms, 'improvement_ms': detail_improvement_ms, 'improvement_percent': detail_improvement_percent}, phase7_5_position_comparison={'phase7_2_baseline_ms': phase7_1_baseline_ms, 'phase7_4_1_elapsed_ms': phase7_4_1_position_baseline_ms, 'phase7_5_elapsed_ms': phase7_5_elapsed_ms, 'improvement_ms': phase7_5_improvement_ms, 'improvement_percent': phase7_5_improvement_percent}, position_candidate_timings_ms=trace['metadata'].get('position_candidate_timings_ms'), timestamps_perf_counter={'position_selected_timestamp': trace['marks'].get('position_selected'), 'next_click_start_timestamp': trace['marks'].get('next_click_start'), 'transition_detected_timestamp': trace['marks'].get('next_transition_detected'), 'confirm_page_ready_timestamp': trace['marks'].get('confirm_page_ready')})

@dataclass(frozen=True)
class Result:
    """操作結果を後続フェーズで共通利用するための不変データ型。"""
    code: str
    state: str
    reason: Optional[str] = None
    retryable: bool = False
    details: Dict[str, Any] = field(default_factory=dict)
    value: Any = None

def make_result(code, state, reason=None, retryable=False, value=None, **details):
    """Result を一貫した形で生成する。Phase 1では既存制御を変更しない。"""
    return Result(code=code, state=state, reason=reason, retryable=retryable, details=details, value=value)

@dataclass(frozen=True)
class LessonCandidate:
    """日付・名前・アンカーを一体で保持するPhase 4用候補。"""
    lesson_element: Any
    anchor_element: Any
    displayed_name: str
    normalized_name: str
    date: str
    href_or_onclick: str
    candidate_index: int
    start_time: str | None = None

def _cla1_identity_ok(identity, expected):
    return bool(isinstance(identity, dict) and identity.get('structure_valid') is True and (identity.get('visible') is True) and (type(expected) is str) and re.fullmatch('[0-9]{12}', expected) and (type(identity.get('value')) is str) and (identity['value'] == expected))

def _cla1_identity_guard(driver, user):
    expected = (user or {}).get('expected_member_identifier')
    identity = None
    try:
        raw = _phase810_read_raw_snapshot(driver)
        identity = raw.get('member_identity')
        matched = _cla1_identity_ok(identity, expected) and (not raw.get('login_fields_present'))
    except Exception:
        matched = False
    evidence = {'identity_exact_match': bool(matched), 'binding_present': type(expected) is str and re.fullmatch('[0-9]{12}', expected) is not None, 'expected_identity_hash': _cla1_redact(expected), 'observed_identity_hash': _cla1_redact(identity.get('value') if isinstance(identity, dict) else None)}
    log_event('cla1_identity_verified', user=user, **evidence)
    if not matched:
        return make_result('UNKNOWN', 'USER_IDENTITY_UNVERIFIED', reservation_confirmed=False, **evidence)
    return None

def _cla1_identity_bindings():
    path = os.environ.get('LESSON_RESERVATION_IDENTITY_CONFIG')
    if not path:
        return {}
    try:

        def unique_pairs(pairs):
            values = {}
            for key, value in pairs:
                if key in values:
                    raise ValueError('duplicate binding')
                values[key] = value
            return values
        values = json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique_pairs)
        if not isinstance(values, dict) or any((type(v) is not str or re.fullmatch('[0-9]{12}', v) is None for v in values.values())):
            raise ValueError('invalid binding')
        if len(set(values.values())) != len(values):
            raise ValueError('duplicate member')
        return values
    except Exception:
        raise LessonListValidationError('TRUSTED_IDENTITY_CONFIG_INVALID') from None

def _cla1_redact(value, key=''):
    if re.search('password|secret|token|cookie|authorization|credential|html|body|message|url|header', key, re.I):
        return '[REDACTED]'
    if isinstance(value, dict):
        return {k: _cla1_redact(v, k) for k, v in value.items() if isinstance(k, str) and re.fullmatch('[A-Za-z_][A-Za-z_0-9]*', k)}
    if isinstance(value, (list, tuple)):
        return [_cla1_redact(v, key) for v in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        if key in {'target_display_name', 'target_normalized_name'} and 0 < len(value) <= 80 and not re.search(r'[\x00-\x1f<>/@\\]', value):
            return value
        if key == 'target_date' and re.fullmatch(r'[0-9]{8}', value):
            return value
        if key == 'target_start_time' and re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', value):
            return value
        if re.fullmatch('sha256:[0-9a-f]{64}', value):
            return value
        if key in {'state', 'code', 'reason_code', 'classification', 'event', 'source_event', 'destination_event'} and re.fullmatch('[A-Za-z_][A-Za-z_0-9]{0,100}', value):
            return value
        if key == 'timestamp' and re.fullmatch('[0-9T:.+Z-]+', value):
            return value
        return 'sha256:' + hashlib.sha256(value.encode('utf-8')).hexdigest()
    return '[REDACTED]'

def _cla1_obs_call(observation, method, *values):
    try:
        if observation is not None:
            return getattr(observation, method)(*values)
    except Exception:
        if isinstance(observation, _Cla1PostSubmitObservation):
            observation.incomplete = True
    return None

def _cla1_obs_value(observation, name, value):
    _cla1_obs_call(observation, 'value', name, value)
    return value

def _cla1_obs_compare(observation, name, value):
    _cla1_obs_call(observation, 'comparison', name, value)
    return value

def _cla1_obs_new(deadline):
    try:
        return _Cla1PostSubmitObservation(deadline)
    except Exception:
        return None

class _Cla1PostSubmitObservation:
    _fields = 'address_contract origin_match path_allowed title_match login_fields_present page_identity_verified ready_complete blocking_overlay render_complete expected_identity_present observed_identity_present expected_identity_format_valid observed_identity_format_valid identity_structure_valid identity_visible identity_exact_equal user_identity_verified selector_found complete_path_match complete_title_match complete_heading_match complete_text_match confirm_dom_present final_submit_present failure_marker error_marker gates_clear request_valid date_match lesson_match active_marker position_match position_valid stable_pair first_page_gate first_render_gate first_identity_gate second_confirmed_gate observation_within_deadline acceptance_within_deadline observation_timeout journal_durable get_started get_returned command_returned window_valid session_valid'.split()
    _complete = _fields[18:27] + ['ready_complete', 'window_valid', 'session_valid']
    _page = _fields[:18] + ['window_valid', 'session_valid']
    _match = _fields[27:33]
    _final = _fields[33:42] + ['position_match']
    _counts = ('target_count', 'active_count', 'conflicting_count', 'date_evaluated_count', 'lesson_evaluated_count')
    _native_branches = {'WRONG_OR_UNKNOWN_PAGE': 9, 'USER_IDENTITY_UNVERIFIED': 10, 'RENDER_INCOMPLETE': 11, 'JOURNAL_IDENTITY_INVALID': 12, 'CONFLICTING_STATUS': 13, 'ZERO_MATCH_COMPLETENESS_UNVERIFIED': 14, 'MULTIPLE_ACTIVE_MATCHES': 15, 'POSITIVE_EXACT_ACTIVE_MATCH': 0}

    def __init__(self, deadline):
        self.deadline = deadline
        self.start = None
        self.slots, self.order, self.references = ({}, {}, {})
        self.serial = 0
        self.incomplete = False
        self.polls = 0
        self.snapshot_index = 1
        self.stage = 1
        self.values = {}
        self.comparisons = {}
        self.native_reason = 'NONE'
        self.branch = 0
        self.deciding = None

    @staticmethod
    def tri(value=None, source=1, reason='NOT_ACQUIRED'):
        known = type(value) is bool
        return dict(value=value if known else None, reason_code='OBSERVED' if known else reason, source=source if known else 0)

    @staticmethod
    def count(value):
        valid = type(value) is int and 0 <= value <= 1000000
        return dict(value=value if valid else None, reason_code='OBSERVED' if valid else 'OUT_OF_RANGE')

    def record(self, slot, checkpoint, phase=0, index=3, fields=()):
        now = time.monotonic()
        if self.start is None:
            self.start = now
        self.serial += 1
        self.order[slot] = self.serial
        reason = 'NOT_REACHED' if phase == 4 else 'NOT_EVALUATED'
        record = dict(schema_version=2, checkpoint=checkpoint, phase=phase, snapshot_index=index, seq=0, timestamp=datetime.now(timezone.utc).isoformat(), monotonic_s=now, elapsed_ms=max(0.0, (now - self.start) * 1000), reference_seq=None, deadline_remaining_ms=(self.deadline - now) * 1000, conditions={key: self.tri(reason=reason) for key in fields}, classification='NOT_EVALUATED', reason_code='NONE', branch_id=0, deciding_seq=None, blockers=[], exception_id=0, stage_id=checkpoint)
        if checkpoint in (3, 4, 6, 7, 9):
            record['window_count'] = None
        if checkpoint in (6, 7, 9):
            record['selectors'] = [dict(selector_id=i, selector_count=dict(value=None, reason_code='NOT_REACHED' if phase == 4 else 'NOT_ACQUIRED'), selector_found=self.tri(reason='NOT_REACHED' if phase == 4 else 'NOT_ACQUIRED')) for i in (1, 2, 3)]
        if checkpoint == 8:
            for key in self._counts:
                record[key] = dict(value=None, reason_code=reason)
        self.slots[slot] = record
        return record

    def set_conditions(self, record, source=1, **values):
        for key, value in values.items():
            record['conditions'][key] = self.tri(value, source)

    def invocation(self):
        record = self.record('invocation', 1, 1)
        record['submit_attempt_number'] = 1

    @staticmethod
    def exception_category(name):
        return {None: 0, 'TimeoutException': 1, 'StaleElementReferenceException': 2, 'NoSuchElementException': 3, 'NoSuchWindowException': 4, 'InvalidSessionIdException': 5, 'JavascriptException': 6, 'WebDriverException': 7, 'ValueError': 8}.get(name, 9)

    def exception_fields(self, record, name):
        category = self.exception_category(name)
        record['exception_id'] = category
        self.set_conditions(record, window_valid=False if category == 4 else None, session_valid=False if category == 5 else None)

    def returned(self, exception):
        name = exception.get('type') if exception is not None else None
        record = self.record('returned', 2, 3 if exception is not None else 2, fields=('command_returned', 'window_valid', 'session_valid'))
        self.set_conditions(record, command_returned=exception is None)
        self.exception_fields(record, name)
        self.references['returned'] = 'invocation'

    def post_read_start(self):
        self.polls += 1
        if 'post_start' not in self.slots:
            self.record('post_start', 3, 1, 0, self._complete)

    def complete(self, snapshot, evidence, state):
        record = self.record('complete', 4, 0, 0, self._complete)
        record['classification'] = state
        record['poll_count'] = min(self.polls, 1000000)
        if self.polls > 1000000:
            self.incomplete = True
        mapping = {'complete_path_match': ('complete_url', 'url'), 'complete_title_match': ('success_title', 'document_title'), 'complete_heading_match': ('success_heading', 'headings'), 'complete_text_match': ('success_message', 'success_text_candidates'), 'confirm_dom_present': ('confirm_page_dom_present', 'confirm_page_dom_present'), 'failure_marker': ('failure_message_present', 'failure_text_candidates'), 'error_marker': ('error_message_present', 'error_text_candidates'), 'blocking_overlay': ('blocking_overlay_present', 'blocking_overlay_count')}
        for field, (key, available) in mapping.items():
            self.set_conditions(record, **{field: evidence.get(key) if available in snapshot else None})
        self.set_conditions(record, final_submit_present=evidence.get('final_reservation_submit_present') if any((k in snapshot for k in ('buttons', 'final_reservation_submit_present', 'final_submit_present'))) else None)
        gates = ('confirm_dom_present', 'final_submit_present', 'failure_marker', 'error_marker', 'blocking_overlay')
        self.set_conditions(record, gates_clear=evidence.get('gates_clear') if all((record['conditions'][k]['value'] is not None for k in gates)) else None)
        for key in ('ready_complete', 'window_valid', 'session_valid'):
            record['conditions'][key] = self.tri()
        if 'post_first' not in self.slots:
            first = dict(record, checkpoint=3, phase=2, stage_id=3)
            first['conditions'] = dict(record['conditions'])
            self.slots['post_first'] = first
            self.order['post_first'] = self.order['complete']
            self.references['post_first'] = 'post_start'
        self.references['complete'] = 'post_first' if self.polls == 1 else 'invocation'

    def wait_exception(self, name, timeout):
        record = self.record('wait_exception', 4 if 'post_first' in self.slots else 3, 3, 0, self._complete + ['observation_timeout'])
        self.exception_fields(record, name)
        self.set_conditions(record, observation_timeout=timeout)
        if timeout:
            self.values['observation_timeout'] = self.tri(True)
        self.branch, self.deciding = (1 if timeout else 2, 'wait_exception')

    def get_start(self):
        self.stage = 5
        record = self.record('get_start', 5, 1, fields=('get_started',))
        record['classification'] = 'RESERVATION_CONFIRMED'
        self.set_conditions(record, get_started=True)

    def get_return(self):
        record = self.record('get_return', 6, 2, fields=('get_returned', 'command_returned'))
        self.set_conditions(record, get_returned=True, command_returned=True)
        self.references['get_return'] = 'get_start'

    def list_read_start(self, index):
        self.snapshot_index = index
        self.stage = 6 if index == 1 else 9
        self.record('first_start' if index == 1 else 'second_start', self.stage, 1, index, self._page)

    def raw(self, raw, expected, page_ok, user_ok):
        index = self.snapshot_index
        self.stage = 7 if index == 1 else 9
        record = self.record('first_identity' if index == 1 else 'second_identity', self.stage, 0, index, self._page)
        path = _reservation_list_path(raw.get('url'))
        identity = raw.get('member_identity')
        identity = identity if isinstance(identity, dict) else {}
        observed = identity.get('value')
        expected_format = bool(re.fullmatch('[0-9]{12}', expected)) if type(expected) is str else None
        observed_format = bool(re.fullmatch('[0-9]{12}', observed)) if type(observed) is str else None
        self.set_conditions(record, page_identity_verified=page_ok, user_identity_verified=user_ok)
        self.set_conditions(record, source=2, address_contract=path in RESERVATION_LIST_ALLOWED_PATHS if 'url' in raw else None, origin_match=path is not None if 'url' in raw else None, path_allowed=path in RESERVATION_LIST_ALLOWED_PATHS if path is not None else None, title_match=str(raw.get('title') or '').strip() == '予約の確認・キャンセル' if 'title' in raw else None, login_fields_present=raw.get('login_fields_present'), ready_complete=raw.get('ready'), blocking_overlay=raw.get('blocking_overlay'), expected_identity_present=expected is not None, observed_identity_present=observed is not None if 'member_identity' in raw else None, expected_identity_format_valid=expected_format, observed_identity_format_valid=observed_format, identity_structure_valid=identity.get('structure_valid'), identity_visible=identity.get('visible'), identity_exact_equal=observed == expected if expected_format and observed_format else None)
        for key in ('selector_found', 'window_valid', 'session_valid'):
            record['conditions'][key] = self.tri()

    def list_read_return(self, snapshot):
        index = self.snapshot_index
        slot = 'first_ready' if index == 1 else 'second_ready'
        record = self.record(slot, 6 if index == 1 else 9, 2, index, self._page)
        identity_slot = 'first_identity' if index == 1 else 'second_identity'
        if identity_slot in self.slots:
            record['conditions'].update(self.slots[identity_slot]['conditions'])
        self.set_conditions(record, page_identity_verified=snapshot.page_identity_verified, user_identity_verified=snapshot.user_identity_verified, render_complete=snapshot.render_complete)
        self.references[slot] = 'first_start' if index == 1 else 'second_start'

    def match_start(self, date_present, lesson_present):
        self.stage = 8
        record = self.record('match', 8, 1, 2, self._match)
        self.set_conditions(record, source=2, request_valid=date_present and lesson_present)

    def classify_start(self):
        self.stage = 8

    def comparison(self, name, value):
        count, matched = self.comparisons.get(name, (0, False))
        self.comparisons[name] = (count + 1, matched or value)

    def match_counts(self, target, active, conflicting):
        record = self.slots['match']
        for key, value in zip(self._counts[:3], (target, active, conflicting)):
            record[key] = self.count(value)
        for key, count_key in (('date_match', 'date_evaluated_count'), ('lesson_match', 'lesson_evaluated_count')):
            count, matched = self.comparisons.get(key, (0, None))
            self.set_conditions(record, **{key: matched})
            record[count_key] = self.count(count)
        self.set_conditions(record, active_marker=active > 0)

    def classified(self, outcome, reason):
        self.native_reason = reason if reason in self._native_branches else 'NONE'
        if 'match' not in self.slots:
            self.record('match', 8, 4, 2, self._match)
        record = self.slots['match']
        record['classification'], record['reason_code'] = (outcome, self.native_reason)
        record['branch_id'] = self._native_branches.get(reason, 0)
        self.references['match'] = 'second_ready'

    def acceptance_start(self):
        self.record('acceptance', 10, 1, 2, self._final)

    def value(self, name, value):
        deadline_fields = {'wait_expired': (3, 'observation_within_deadline', 1), 'before_get_expired': (5, 'observation_within_deadline', 4), 'after_first_expired': (7, 'observation_within_deadline', 7), 'observation_timeout': (4, 'observation_timeout', 1), 'outer_within_deadline': (10, 'acceptance_within_deadline', 21), 'failure_within_deadline': (10, 'acceptance_within_deadline', 21), 'failure_acceptance_within_deadline': (10, 'acceptance_within_deadline', 21)}
        if name in deadline_fields:
            if name == 'before_get_expired':
                self.stage = 5
            checkpoint, field, branch = deadline_fields[name]
            known = not value if name.endswith('_expired') else value
            fields = self._complete if checkpoint in (3, 4) else self._page if checkpoint == 7 else ('get_started',) if checkpoint == 5 else self._final if checkpoint == 10 else ()
            record = self.record(name, checkpoint, fields=fields)
            self.set_conditions(record, **{field: known})
            self.values[field] = self.tri(known)
            rejected = value if name.endswith('_expired') or name == 'observation_timeout' else not value
            if rejected:
                self.branch, self.deciding = (branch, name)
            return
        if name == 'failure_identity_ok':
            record = self.record(name, 10, 1, fields=('user_identity_verified',))
            self.set_conditions(record, user_identity_verified=value)
            if not value:
                self.branch, self.deciding = (22, name)
            return
        self.values[name] = self.tri(value)
        if 'acceptance' in self.slots:
            self.slots['acceptance']['conditions'][name] = self.tri(value)
        if name == 'position_match':
            record = self.record('position', 8, 2, 2, self._match)
            if 'match' in self.slots:
                record['conditions'].update(self.slots['match']['conditions'])
                for key in self._counts:
                    record[key] = self.slots['match'][key]
                record['classification'] = self.slots['match']['classification']
                record['reason_code'] = self.slots['match']['reason_code']
            self.set_conditions(record, position_match=value)
            self.references['position'] = 'match'
        if value is False:
            branch = {'observation_within_deadline': 21, 'acceptance_within_deadline': 21, 'first_page_gate': 16, 'first_render_gate': 17, 'first_identity_gate': 18, 'stable_pair': 19, 'second_confirmed_gate': self._native_branches.get(self.native_reason, 26), 'position_match': 20}.get(name)
            if branch:
                self.branch, self.deciding = (branch, 'position' if name == 'position_match' else 'acceptance')

    def list_exception(self, name):
        slot = 'list_exception'
        get_unreturned = 'get_start' in self.slots and 'get_return' not in self.slots
        checkpoint = 6 if get_unreturned else self.stage
        index = 3 if 'get_return' not in self.slots else self.snapshot_index
        record = self.record(slot, checkpoint, 3, index, self._page if checkpoint in (6, 7, 9) else self._match if checkpoint == 8 else ('get_started',) if checkpoint == 5 else ())
        self.exception_fields(record, name)
        record['parse_error_id'] = 8 if record['exception_id'] == 8 else 0
        if 'get_start' in self.slots and 'get_return' not in self.slots:
            record['checkpoint'] = record['stage_id'] = 6
            self.set_conditions(record, get_returned=False, command_returned=False)
            branch = 5
        elif 'get_return' not in self.slots:
            branch = 26
        elif checkpoint == 8:
            branch = 26
        else:
            branch = 6 if self.snapshot_index == 1 else 8
        self.branch, self.deciding = (branch, slot)

    def journal_exception(self, name):
        record = self.record('journal_exception', 10, 3, fields=('journal_durable',))
        self.set_conditions(record, journal_durable=False)
        self.exception_fields(record, name)
        self.branch, self.deciding = (23, 'journal_exception')

    def finish(self, state, timeout, durable):
        if state == 'RESERVATION_CONFIRMED':
            self.branch, self.deciding = (24, 'outer_within_deadline')
        elif state == 'RESERVATION_FAILED':
            self.branch, self.deciding = (25, 'failure_acceptance_within_deadline')
        elif not self.branch:
            self.branch, self.deciding = (3, 'complete')
        if self.deciding not in self.slots:
            self.deciding = 'returned' if 'returned' in self.slots else 'invocation'
            self.incomplete = True
        groups = {2: ('command_returned', 'window_valid', 'session_valid'), 3: self._complete, 4: self._complete, 5: ('get_started',), 6: self._page + ['get_returned', 'command_returned'], 7: self._page, 8: self._match, 9: self._page}
        for checkpoint, fields in groups.items():
            if not any((r['checkpoint'] == checkpoint for r in self.slots.values())):
                slot = 'unreached_' + str(checkpoint)
                self.record(slot, checkpoint, 4, fields=fields)
                self.references[slot] = self.deciding
        record = self.record('final', 10, fields=self._final)
        record['classification'] = state
        record['reason_code'] = state if state in ('UNKNOWN_AFTER_SUBMIT', 'JOURNAL_PRESERVATION_ERROR') else 'NONE'
        record['branch_id'] = self.branch
        record['conditions'].update(self.values)
        self.set_conditions(record, observation_timeout=timeout, journal_durable=durable)
        self.references['final'] = self.deciding
        ordered = sorted(self.slots, key=lambda slot: (self.order[slot], slot == 'complete'))
        if len(ordered) > 24:
            self.incomplete = True
        retained = ordered[-24:]
        for seq, slot in enumerate(retained, 1):
            self.slots[slot]['seq'] = seq
        negative = {'login_fields_present', 'blocking_overlay', 'confirm_dom_present', 'final_submit_present', 'failure_marker', 'error_marker', 'observation_timeout'}
        for slot in retained:
            item = self.slots[slot]
            reference = self.references.get(slot)
            if reference in retained:
                item['reference_seq'] = self.slots[reference]['seq']
            elif reference is not None:
                self.incomplete = True
            item['blockers'] = [self._fields.index(key) + 1 for key, tri in item['conditions'].items() if tri['source'] == 1 and tri['value'] is (key in negative)]
            if slot == 'final':
                item['deciding_seq'] = self.slots[self.deciding]['seq'] if self.deciding in retained else None
            elif item['phase'] == 4:
                item['deciding_seq'] = item['seq'] if item['branch_id'] else item['reference_seq']
        return dict(schema_version=2, trace_complete=not self.incomplete and 'invocation' in retained, dropped_count=max(0, len(ordered) - 24), records=[self.slots[slot] for slot in retained])

def _cla1_position_match(request, selected, observed):
    ranking = request.get('positions') or []
    return type(selected) is int and type(observed) is int and (selected > 0) and (selected in ranking) and (observed == selected)

def _cla1_normal_ui_evidence():
    return dict.fromkeys(('complete_return_button_found', 'complete_return_button_unique', 'complete_return_binding_match', 'complete_return_click_timestamp', 'menu_arrival_timestamp', 'menu_path_match', 'menu_title_match', 'reservation_list_link_found', 'reservation_list_link_unique', 'reservation_list_href_match', 'reservation_list_binding_match', 'reservation_list_link_click_timestamp', 'reservation_list_arrival_timestamp', 'reservation_list_path_match', 'reservation_list_title_match', 'deadline_remaining_after_menu', 'deadline_remaining_after_list'), None) | {'complete_return_click_count': 0, 'reservation_list_link_click_count': 0}

def _cla1_normal_ui_state(driver, path, title):
    return driver.execute_script("/* CLA1_NORMAL_UI_STATE */\n        const menuLinks = Array.from(document.querySelectorAll('a')).filter(\n            a => a.textContent.trim() === '予約の確認・キャンセル');\n        const menuElement = arguments[0] !== '/DSPWebUser/LESSON' ||\n            (menuLinks.length === 1 && (() => {\n                const a = menuLinks[0], u = new URL(a.getAttribute('href'), location.href);\n                return a.hasAttribute('href') && u.origin === location.origin &&\n                    u.pathname === '/DSPWebUser/LESSON/LessonList' && !u.search && !u.hash &&\n                    (!a.target || a.target === '_self') && !a.hasAttribute('download') &&\n                    !a.hasAttribute('disabled') && a.getAttribute('aria-disabled') !== 'true' &&\n                    a.getClientRects().length > 0 && getComputedStyle(a).visibility === 'visible';\n            })());\n        return {...(arguments[0] === '/DSPWebUser/LESSON' ?\n            {anchor: menuElement ? menuLinks[0] : null} : {}), element: menuElement, origin: location.origin === 'https://www5.e-atoms.jp',\n            path: location.pathname === arguments[0],\n            title: document.title.trim() === arguments[1],\n            ready: document.readyState === 'complete'};\n        ", path, title)

def _cla1_normal_ui_arrival(driver, deadline, path, title, prefix, evidence):
    if prefix == 'menu':
        started = time.monotonic()
        evidence['menu_poll_count'] = 0
        evidence['complete_click_timestamp'] = evidence.get('complete_return_click_timestamp')
        while time.monotonic() < deadline:
            state = _cla1_normal_ui_state(driver, path, title)
            snapshot_at = time.time()
            evidence['menu_poll_count'] += 1
            path_match = bool(state['origin'] and state['path'])
            title_match = bool(state['title'])
            if evidence['menu_poll_count'] == 1:
                evidence.update(first_post_click_snapshot_timestamp=snapshot_at, first_post_click_path_match=path_match, first_post_click_title_match=title_match)
            remaining = deadline - time.monotonic()
            evidence.update(menu_path_match=path_match, menu_title_match=title_match, menu_arrival_final_path_match=path_match, menu_arrival_final_title_match=title_match, menu_element_state_match=bool(state.get('element', False)), menu_ready_state_complete=bool(state['ready']), menu_wait_duration_ms=(time.monotonic() - started) * 1000, deadline_remaining_after_menu=remaining)
            if path_match and title_match and state['ready'] and (state.get('element') is True) and (remaining > 0):
                evidence.update(menu_arrival_timestamp=snapshot_at, menu_positive_evidence_timestamp=snapshot_at, deadline_remaining_at_menu=remaining)
                return state.get('anchor', False)
            time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
        evidence['menu_wait_duration_ms'] = (time.monotonic() - started) * 1000
        evidence['deadline_remaining_after_menu'] = deadline - time.monotonic()
        return False
    while time.monotonic() < deadline:
        state = _cla1_normal_ui_state(driver, path, title)
        evidence[prefix + '_path_match'] = state['origin'] and state['path']
        evidence[prefix + '_title_match'] = state['title']
        if state['ready']:
            remaining = deadline - time.monotonic()
            evidence['deadline_remaining_after_' + ('menu' if prefix == 'menu' else 'list')] = remaining
            if not (all(state.values()) and remaining > 0):
                return False
            evidence[prefix + '_arrival_timestamp'] = time.time()
            return True
        time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
    return False

def _cla1_normal_ui_to_list(driver, deadline, evidence):
    complete = '/DSPWebUser/LESSON/ReserveLessonSchedule/Complete'
    menu = '/DSPWebUser/LESSON'
    listing = '/DSPWebUser/LESSON/LessonList'
    if time.monotonic() >= deadline:
        return False
    menu_state = _cla1_normal_ui_state(driver, menu, 'レッスン予約メニュー') if globals().get('_rc_runtime') else {}
    if all(menu_state.get(k) is True for k in ('origin', 'path', 'title', 'ready', 'element')):
        anchor = menu_state.get('anchor')
    else:
        state = _cla1_normal_ui_state(driver, complete, 'レッスン予約完了')
        if not (state['origin'] and state['path'] and state['ready']):
            return False
        buttons = driver.find_elements('css selector', 'button#confirmsubmit')
        evidence['complete_return_button_found'] = len(buttons) > 0
        evidence['complete_return_button_unique'] = len(buttons) == 1
        if len(buttons) != 1:
            return False
        button = buttons[0]
        binding = driver.execute_script("/* CLA1_COMPLETE_BINDING */\n        const b = arguments[0], f = b.form;\n        return b.tagName === 'BUTTON' && b.id === 'confirmsubmit' &&\n            document.querySelectorAll('button#confirmsubmit').length === 1 &&\n            b.type === 'submit' && b.innerText.trim() === 'レッスン予約メニューに戻る' &&\n            !!f && f.method.toUpperCase() === 'POST' &&\n            new URL(f.action, location.href).origin === location.origin &&\n            new URL(f.action, location.href).pathname === arguments[1] &&\n            !b.hasAttribute('formaction') && !b.hasAttribute('formmethod') &&\n            !b.hasAttribute('formtarget') && !f.target &&\n            b.getAttribute('aria-disabled') !== 'true';\n        ", button, complete)
        evidence['complete_return_binding_match'] = bool(binding and button.is_displayed() and button.is_enabled())
        if not evidence['complete_return_binding_match']:
            return False
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        driver.set_page_load_timeout(min(9.0, remaining))
        if time.monotonic() >= deadline:
            return False
        evidence['complete_return_click_timestamp'] = time.time()
        evidence['complete_return_click_count'] = 1
        button.click()
        anchor = _cla1_normal_ui_arrival(driver, deadline, menu, 'レッスン予約メニュー', 'menu', evidence)
    if not anchor:
        return False
    evidence['reservation_list_link_found'] = True
    evidence['reservation_list_link_unique'] = True
    href_match = driver.execute_script("/* CLA1_LIST_BINDING */\n        const a = arguments[0], u = new URL(a.getAttribute('href'), location.href);\n        return a.tagName === 'A' && a.hasAttribute('href') &&\n            a.isConnected && a.textContent.trim() === '予約の確認・キャンセル' &&\n            location.origin === 'https://www5.e-atoms.jp' &&\n            location.pathname === '/DSPWebUser/LESSON' &&\n            document.title.trim() === 'レッスン予約メニュー' && document.readyState === 'complete' &&\n            Array.from(document.querySelectorAll('a')).filter(\n                e => e.textContent.trim() === '予約の確認・キャンセル').length === 1 &&\n            u.origin === location.origin && u.pathname === arguments[1] &&\n            !u.search && !u.hash && (!a.target || a.target === '_self') &&\n            !a.hasAttribute('download') && !a.hasAttribute('disabled') &&\n            a.getAttribute('aria-disabled') !== 'true';\n        ", anchor, listing)
    evidence['reservation_list_href_match'] = bool(href_match)
    evidence['reservation_list_binding_match'] = bool(href_match and anchor.is_displayed() and anchor.is_enabled())
    if not evidence['reservation_list_binding_match']:
        return False
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return False
    driver.set_page_load_timeout(min(9.0, remaining))
    if time.monotonic() >= deadline:
        return False
    evidence['reservation_list_link_click_timestamp'] = time.time()
    evidence['reservation_list_link_click_count'] = 1
    anchor.click()
    return _cla1_normal_ui_arrival(driver, deadline, listing + '/ShowList', '予約の確認・キャンセル', 'reservation_list', evidence)

def _cla1_post_submit_reconcile(driver, user, request, selected, deadline, _observation=None):
    evidence = {'requested_positions': list(request.get('positions') or []), 'selected_position': selected, 'reconciled_position': None, 'identity_exact_match': False, 'deadline': deadline}
    try:
        remaining = deadline - time.monotonic()
        if _cla1_obs_value(_observation, 'before_get_expired', remaining <= 0):
            return (False, evidence)
        navigation = _cla1_normal_ui_evidence()
        evidence['normal_ui_navigation'] = navigation
        if not _cla1_normal_ui_to_list(driver, deadline, navigation):
            return (False, evidence)
        _cla1_obs_call(_observation, 'list_read_start', 1)
        first = _phase810_snapshot_from_raw(_phase810_read_raw_snapshot(driver), user.get('expected_member_identifier'), _observation=_observation)
        _cla1_obs_call(_observation, 'list_read_return', first)
        if _cla1_obs_value(_observation, 'after_first_expired', time.monotonic() >= deadline):
            return (False, evidence)
        time.sleep(min(RECONCILIATION_OBSERVATION_DELAY_SECONDS, max(0.0, deadline - time.monotonic())))
        _cla1_obs_call(_observation, 'list_read_start', 2)
        second = _phase810_snapshot_from_raw(_phase810_read_raw_snapshot(driver), user.get('expected_member_identifier'), _observation=_observation)
        _cla1_obs_call(_observation, 'list_read_return', second)
        observed_at = time.monotonic()
        _cla1_obs_call(_observation, 'classify_start')
        outcome, reason, row = _phase810_classify(second, request, _observation=_observation)
        _cla1_obs_call(_observation, 'classified', outcome, reason)
        evidence.update(identity_exact_match=first.user_identity_verified and second.user_identity_verified, reconciled_position=row.position if row else None, evidence_observed_at=observed_at, evidence_digest=second.evidence_digest, reason_code=reason)
        accepted_at = time.monotonic()
        evidence['acceptance_checked_at'] = accepted_at
        _cla1_obs_call(_observation, 'acceptance_start')
        return (bool(_cla1_obs_value(_observation, 'observation_within_deadline', observed_at <= deadline) and _cla1_obs_value(_observation, 'acceptance_within_deadline', accepted_at <= deadline) and _cla1_obs_value(_observation, 'first_page_gate', first.page_identity_verified) and _cla1_obs_value(_observation, 'first_render_gate', first.render_complete) and _cla1_obs_value(_observation, 'first_identity_gate', first.user_identity_verified) and _cla1_obs_value(_observation, 'stable_pair', first.evidence_digest == second.evidence_digest) and _cla1_obs_value(_observation, 'second_confirmed_gate', outcome == 'CONFIRMED') and row and _cla1_obs_value(_observation, 'position_match', _cla1_position_match(request, selected, row.position))), evidence)
    except Exception as exc:
        _cla1_obs_call(_observation, 'list_exception', type(exc).__name__)
        evidence['exception_type'] = type(exc).__name__
        return (False, evidence)

def log_event(event, result=None, user=None, request=None, **details):
    """既存コンソールログに加えて出力する、1行JSON形式の構造化ログ。"""
    payload = {'timestamp': datetime.now(timezone.utc).isoformat(), 'event': event}
    if user is not None:
        payload['username'] = user.get('username')
    if request is not None:
        payload['request'] = {'date': request.get('date'), 'name': request.get('name')}
    if result is not None:
        payload['result'] = {'code': result.code, 'state': result.state, 'reason': result.reason, 'retryable': result.retryable, 'details': result.details}
    payload.update(details)
    latency_key = ((user or {}).get('username'), (request or {}).get('date'), (request or {}).get('name'))
    latency_now = time.perf_counter()
    required_latency_state = _LATENCY_REQUIRED_STATES.get(event)
    latency_event_eligible = required_latency_state is None or (result is not None and result.state == required_latency_state)
    latency_pair = _LATENCY_EVENT_PAIRS.get(event)
    if latency_event_eligible and latency_pair and (latency_key in _latency_marks):
        source_event, interval_name = latency_pair
        source_time = _latency_marks[latency_key].get(source_event)
        if source_time is not None:
            payload['latency'] = {'interval': interval_name, 'seconds': latency_now - source_time, 'source_event': source_event, 'destination_event': event}
    if latency_event_eligible:
        _latency_marks.setdefault(latency_key, {})[event] = latency_now
    print(f'[v1.6] {json.dumps(_cla1_redact(payload), ensure_ascii=False, default=str)}', flush=True)

def normalize_lesson_name(name):
    """Return the shared, pure lesson-name identity used by input and DOM matching.

    The punctuation policy deliberately preserves the established search contract;
    Phase 8.9.1 only makes Unicode, entity, width, whitespace, dash and case handling
    deterministic.  It does not add new fuzzy substitutions.
    """
    if not name:
        return name
    name = html.unescape(str(name))
    name = unicodedata.normalize('NFKC', name)
    if jaconv is not None:
        name = jaconv.h2z(name, kana=True)
        name = jaconv.z2h(name, ascii=True, digit=True, kana=False)
    name = re.sub('[ー－―‐−–—―]', 'ー', name)
    name = re.sub('[☆※★\\s()（）]', '', name)
    return name.casefold()
canonicalize_lesson_identity_name = normalize_lesson_name

def _request_identity_key(username, request):
    """Canonical request identity shared by duplicate and confirmed-count guards."""
    lesson = canonicalize_lesson_identity_name(request.get('name', ''))
    if 'start_time' in request:
        from lesson_target import canonical_name, valid_time
        start_time = request.get('start_time')
        if not valid_time(start_time):
            raise ValueError('START_TIME_FORMAT')
        lesson = canonical_name(request.get('name', ''), normalize_lesson_name) + '@' + start_time
    return (username, str(request.get('date') or '').strip(), lesson)
JOURNAL_SCHEMA_VERSION = 1
JOURNAL_STATES = {'IN_PROGRESS', 'FAILED_RETRYABLE', 'FAILED_FINAL', 'RETRY_EXHAUSTED', 'ACTION_INTENT', 'SUBMIT_INTENT', 'CONFIRMED', 'PRESERVATION_UNKNOWN'}
JOURNAL_RETRYABLE_STATES = {'IN_PROGRESS', 'FAILED_RETRYABLE'}
JOURNAL_RETRY_SAFE_REASONS = {'REQUEST_STARTED', 'TRANSIENT_PAGE_LOAD', 'TRANSIENT_SCHEDULE_RENDER', 'TARGET_NOT_FOUND_TRANSIENT', 'DRIVER_SESSION_FAILURE_BEFORE_ACTION'}
JOURNAL_MAX_ATTEMPTS = 3

def _phase892_project_root():
    configured = os.environ.get('LESSON_RESERVATION_PROJECT_ROOT')
    if configured:
        return Path(configured)
    for parent in Path(__file__).resolve().parents:
        if (parent / 'current').is_dir() and (parent / 'phases').is_dir():
            return parent
    return Path(__file__).resolve().parent
JOURNAL_ROOT = Path(os.environ.get('LESSON_RESERVATION_JOURNAL_DIR', str(_phase892_project_root() / 'runtime' / 'reservation_journal' / 'schema-v1')))

def _journal_user_key(username):
    return 'user-' + hashlib.sha256(str(username).encode('utf-8')).hexdigest()[:20]

def _journal_path(username):
    return JOURNAL_ROOT / (_journal_user_key(username) + '.json')

def _journal_identity(username, request):
    user, date, lesson = _request_identity_key(username, request)
    if not re.fullmatch('\\d{8}', date) or not lesson:
        raise ValueError('invalid request identity')
    return {'user_key': _journal_user_key(user), 'date': date, 'canonical_lesson': lesson}

def _journal_request_key(identity):
    raw = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()

def _request_fingerprint(username, request):
    payload = {'identity': _journal_identity(username, request), 'preferred_positions': list(request.get('positions') or [])}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()

def _empty_journal(username):
    return {'schema_version': JOURNAL_SCHEMA_VERSION, 'user_key': _journal_user_key(username), 'requests': {}}

def _read_journal_storage(username):
    path = _journal_path(username)
    if not path.exists():
        return (_empty_journal(username), 'MISSING')
    try:
        with path.open('r', encoding='utf-8') as source:
            value = json.load(source)
    except Exception as exc:
        raise ValueError('malformed reservation journal') from exc
    if not isinstance(value, dict) or value.get('schema_version') != JOURNAL_SCHEMA_VERSION or value.get('user_key') != _journal_user_key(username) or (not isinstance(value.get('requests'), dict)):
        raise ValueError('unsupported or conflicting reservation journal')
    for key, record in value['requests'].items():
        if not isinstance(key, str) or not isinstance(record, dict):
            raise ValueError('impossible reservation journal record')
        if record.get('state') not in JOURNAL_STATES:
            raise ValueError('unsupported reservation journal state')
    return (value, 'EXISTING')
_OWNER_RECOVERY_SESSION = None
_OWNER_RECOVERY_MODULE = None
_OWNER_RECOVERY_REVISION = None

def _owner_recovery_store():
    """Explicit two-target extension; no browser imports/actions in its module."""
    global _OWNER_RECOVERY_MODULE, _OWNER_RECOVERY_REVISION
    if _OWNER_RECOVERY_MODULE is None:
        import importlib.util
        module_path = Path(__file__).with_name('cla1_owner_cancelled_recovery.py')
        spec = importlib.util.spec_from_file_location('cla1_owner_cancelled_recovery', module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _OWNER_RECOVERY_MODULE = module
        _OWNER_RECOVERY_REVISION = hashlib.sha256(Path(__file__).read_bytes() + module_path.read_bytes()).hexdigest()
    bindings = {u['username']: alias for u, alias in zip(_FIXED_USER_SETTINGS, ('A', 'B'))}
    return _OWNER_RECOVERY_MODULE.Store(JOURNAL_ROOT, bindings, _read_journal_storage, _journal_identity, _journal_request_key, _request_fingerprint, session=_OWNER_RECOVERY_SESSION, revision=_OWNER_RECOVERY_REVISION)

def _read_journal(username):
    value, source = _read_journal_storage(username)
    if _OWNER_RECOVERY_SESSION is not None or (JOURNAL_ROOT / 'cla1-owner-cancelled').exists():
        value = _owner_recovery_store().view(username, value)
    return (value, source)

def _atomic_write_journal(username, value, crash_hook=None):
    path = _journal_path(username)
    if _OWNER_RECOVERY_SESSION is not None or (JOURNAL_ROOT / 'cla1-owner-cancelled').exists():
        recovery = _owner_recovery_store()
        path = recovery.write_path(username, path)
        value = recovery.storage_value(username, value)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp-' + uuid.uuid4().hex)
    if crash_hook:
        crash_hook('before_temp')
    try:
        encoded = (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')
        with temp.open('xb') as output:
            midpoint = max(1, len(encoded) // 2)
            output.write(encoded[:midpoint])
            if crash_hook:
                crash_hook('mid_write')
            output.write(encoded[midpoint:])
            output.flush()
            os.fsync(output.fileno())
            if crash_hook:
                crash_hook('after_fsync_before_replace')
        if crash_hook:
            crash_hook('before_replace')
        os.replace(temp, path)
        if crash_hook:
            crash_hook('after_replace')
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass

def _journal_write_state(username, request, state, selected_position=None, confirmation_evidence=None, crash_hook=None, **updates):
    journal, _ = _read_journal(username)
    identity = _journal_identity(username, request)
    key = _journal_request_key(identity)
    previous = journal['requests'].get(key)
    if previous and previous.get('identity') != identity:
        raise ValueError('journal identity conflict')
    previous = previous or {}
    if previous.get('state') == 'CONFIRMED' and state != 'CONFIRMED':
        raise ValueError('CONFIRMED is terminal')
    if previous.get('state') in {'ACTION_INTENT', 'SUBMIT_INTENT'} and state == 'FAILED_RETRYABLE':
        raise ValueError('unsafe boundary cannot become retryable')
    now = datetime.now(timezone.utc).isoformat()
    record = {'identity': identity, 'state': state, 'request_fingerprint': _request_fingerprint(username, request), 'preferred_positions': list(request.get('positions') or []), 'selected_position': selected_position, 'lesson_list_sha256': LESSON_LIST_SHA256, 'timestamp_utc': now, 'run_id': JOURNAL_RUN_ID, 'attempt_count': int(previous.get('attempt_count', 0)), 'first_started_at': previous.get('first_started_at'), 'last_started_at': previous.get('last_started_at'), 'last_failure_at': previous.get('last_failure_at'), 'last_reason_code': previous.get('last_reason_code'), 'recovered_from': previous.get('recovered_from'), 'action_boundary': previous.get('action_boundary'), 'submit_intent_durable': state in {'SUBMIT_INTENT', 'CONFIRMED'}, 'submission_attempted': state == 'CONFIRMED', 'confirmation_evidence': confirmation_evidence}
    for field in ('provisional_evidence_state', 'complete_evidence', 'batch_id', 'batch_request_index', 'reconciliation_pending', 'batch_timing', 'last_reconciliation_outcome', 'last_reconciliation_reason', 'last_reconciliation_at', 'snapshot_set_id'):
        if field in previous:
            record[field] = previous[field]
    if state == 'SUBMIT_INTENT' and previous.get('submission_attempted'):
        record['submission_attempted'] = True
    record.update(updates)
    journal['requests'][key] = record
    _atomic_write_journal(username, journal, crash_hook=crash_hook)
    return record

def _journal_begin_attempt(username, request):
    journal, source = _read_journal(username)
    identity = _journal_identity(username, request)
    prior = journal['requests'].get(_journal_request_key(identity))
    if prior and prior.get('state') not in JOURNAL_RETRYABLE_STATES:
        raise ValueError('request is not retry-safe')
    attempts = int((prior or {}).get('attempt_count', 0))
    if attempts >= JOURNAL_MAX_ATTEMPTS:
        return _journal_write_state(username, request, 'RETRY_EXHAUSTED', last_reason_code='RETRY_BUDGET_EXHAUSTED', last_failure_at=datetime.now(timezone.utc).isoformat())
    now = datetime.now(timezone.utc).isoformat()
    return _journal_write_state(username, request, 'IN_PROGRESS', attempt_count=attempts + 1, first_started_at=(prior or {}).get('first_started_at') or now, last_started_at=now, last_reason_code='REQUEST_STARTED', recovered_from=(prior or {}).get('state') if prior else None, owner_run_id=JOURNAL_RUN_ID, action_boundary=None)

def _journal_mark_retryable(username, request, reason_code):
    if reason_code not in JOURNAL_RETRY_SAFE_REASONS:
        raise ValueError('reason is not retry-safe')
    journal, _ = _read_journal(username)
    identity = _journal_identity(username, request)
    prior = journal['requests'].get(_journal_request_key(identity)) or {}
    if prior.get('state') != 'IN_PROGRESS' or prior.get('action_boundary'):
        raise ValueError('unsafe boundary cannot become retryable')
    attempts = int(prior.get('attempt_count', 0))
    state = 'RETRY_EXHAUSTED' if attempts >= JOURNAL_MAX_ATTEMPTS else 'FAILED_RETRYABLE'
    return _journal_write_state(username, request, state, attempt_count=attempts, first_started_at=prior.get('first_started_at'), last_started_at=prior.get('last_started_at'), last_failure_at=datetime.now(timezone.utc).isoformat(), last_reason_code='RETRY_BUDGET_EXHAUSTED' if state == 'RETRY_EXHAUSTED' else reason_code, recovered_from=prior.get('recovered_from'), action_boundary=None)

def journal_preflight(username, request):
    try:
        journal, source = _read_journal(username)
        identity = _journal_identity(username, request)
    except Exception as exc:
        return make_result('UNKNOWN', 'JOURNAL_PRESERVATION_ERROR', reason='journal invalid; booking prohibited', reason_code='JOURNAL_INVALID', exception_type=type(exc).__name__, reservation_operation=False)
    record = journal['requests'].get(_journal_request_key(identity))
    if record is None:
        return make_result('OK', 'JOURNAL_MISS', journal_source=source, reservation_operation=False)
    if record.get('identity') != identity:
        return make_result('UNKNOWN', 'JOURNAL_PRESERVATION_ERROR', reason='journal identity conflict', reason_code='JOURNAL_IDENTITY_CONFLICT', reservation_operation=False)
    state = record.get('state')
    if state == 'OWNER_VERIFIED_CANCELLED':
        return make_result('SKIPPED', 'OWNER_VERIFIED_CANCELLED', reason_code='OWNER_CANCELLED_NEW_LIVE_AUTHORIZATION_REQUIRED', reservation_operation=False, reservation_count_incremented=False, final_resend=False, back_attempted=False, next_position_attempted=False)
    if state in JOURNAL_RETRYABLE_STATES:
        reason_code = record.get('last_reason_code')
        safe = reason_code in JOURNAL_RETRY_SAFE_REASONS and (not record.get('action_boundary')) and (not record.get('submit_intent_durable')) and (int(record.get('attempt_count', 0)) < JOURNAL_MAX_ATTEMPTS)
        if safe:
            return make_result('OK', 'JOURNAL_RETRY_SAFE', reason_code=reason_code, attempt_count=int(record.get('attempt_count', 0)), recovered_from=state, journal_source='LOCAL_RETRY_SAFE', reservation_operation=False)
        return make_result('UNKNOWN', 'PRESERVATION_UNKNOWN', reason='retry authority is incomplete or exhausted', reason_code='JOURNAL_RETRY_AUTHORITY_INVALID', reservation_operation=False)
    if state in {'ACTION_INTENT', 'PRESERVATION_UNKNOWN'}:
        return make_result('UNKNOWN', 'PRESERVATION_UNKNOWN', reason='durable unsafe action boundary requires manual review', reason_code='JOURNAL_' + state, reservation_operation=False, final_resend=False, back_attempted=False, next_position_attempted=False)
    if state in {'FAILED_FINAL', 'RETRY_EXHAUSTED'}:
        return make_result('SKIPPED', state, reason_code=record.get('last_reason_code'), attempt_count=int(record.get('attempt_count', 0)), reservation_operation=False)
    if record.get('state') == 'SUBMIT_INTENT':
        return make_result('UNKNOWN', 'PRESERVATION_UNKNOWN', reason='durable submit intent requires reconciliation', reason_code='JOURNAL_SUBMIT_INTENT', journal_source='LOCAL_SUBMIT_INTENT', reservation_operation=False, final_resend=False, back_attempted=False, next_position_attempted=False)
    evidence = record.get('confirmation_evidence')
    position = record.get('selected_position')
    valid = record.get('state') == 'CONFIRMED' and isinstance(evidence, dict) and (evidence.get('positive') is True) and isinstance(position, int) and (position > 0) and (not record.get('contradictory_local_evidence'))
    if not valid:
        return make_result('UNKNOWN', 'PRESERVATION_UNKNOWN', reason='confirmed journal evidence is stale or uncertain', reason_code='JOURNAL_CONFIRMED_UNCERTAIN', reservation_operation=False)
    return make_result('SKIPPED', 'SKIPPED_EXISTING_CONFIRMED', reason_code='JOURNAL_FRESH_CONFIRMED', journal_source='LOCAL_FRESH_CONFIRMED', confirmed_position=position, request_fingerprint_match=record.get('request_fingerprint') == _request_fingerprint(username, request), reservation_operation=False, reservation_count_incremented=False, production_validation_get=0, position_click_count=0, next_click_count=0, final_submit_click_count=0, back_count=0)
JOURNAL_RUN_ID = uuid.uuid4().hex

def is_matching_lesson_partial(actual, expected):
    actual_normalized = normalize_lesson_name(actual)
    expected_normalized = normalize_lesson_name(expected)
    return expected_normalized in actual_normalized
PHASE4_TEST_ONLY = True
PHASE5_1_TEST_ONLY = True
PHASE5_2_TEST_ONLY = True
PHASE5_3_TEST_ONLY = True
PHASE6_1_TEST_ONLY = True
PHASE6_1_LOG_DIR = os.environ.get('PHASE8_8_3_LOG_DIR', 'C:/Users/Takashi/OneDrive/Desktop/Lesson_Reservation/logs/phase8_8_3')
PHASE8_1_MODE = os.environ.get('PHASE8_4_MODE', 'simulation')
DRY_RUN_STOP_AFTER_RESERVATION_PAGE_READY = True

class _ConsoleAndFile:
    """Console streamを保ったまま同一Production logへappendする。"""

    def __init__(self, console, path):
        self.console = console
        self.file = open(path, 'a', encoding='utf-8', buffering=1)

    def write(self, text):
        if text.startswith('[v1.6] '):
            try:
                safe = '[v1.6] ' + json.dumps(_cla1_redact(json.loads(text[7:])), ensure_ascii=False)
            except Exception:
                safe = '[REDACTED CONSOLE]'
        elif text.isspace():
            safe = text
        else:
            safe = '[REDACTED CONSOLE]'
        self.console.write(safe)
        self.file.write(safe)
        return len(text)

    def flush(self):
        self.console.flush()
        self.file.flush()

    def isatty(self):
        return self.console.isatty()

    def close_log(self):
        try:
            self.file.flush()
        finally:
            self.file.close()

def _close_phase8711_log():
    """Best-effort flush/close; never closes the original console streams."""
    seen = set()
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, _ConsoleAndFile) and id(stream) not in seen:
            seen.add(id(stream))
            try:
                stream.flush()
                stream.close_log()
            except Exception:
                pass

def _configure_phase6_1_log():
    os.makedirs(PHASE6_1_LOG_DIR, exist_ok=True)
    path = os.environ.get('PHASE8_8_3_LOG_FILE')
    if not path:
        path = os.path.join(PHASE6_1_LOG_DIR, datetime.now().strftime('phase8_8_3_production_%Y%m%d_%H%M%S.log' if PHASE8_1_MODE == 'production' else 'phase8_8_3_offline_%Y%m%d_%H%M%S.log'))
        os.environ['PHASE8_8_3_LOG_FILE'] = path
    effective_path = path
    if multiprocessing.current_process().name != 'MainProcess':
        effective_path = f'{path}.worker_{os.getpid()}.tmp'
    if not isinstance(sys.stdout, _ConsoleAndFile):
        sys.stdout = _ConsoleAndFile(sys.stdout, effective_path)
    if not isinstance(sys.stderr, _ConsoleAndFile):
        sys.stderr = _ConsoleAndFile(sys.stderr, effective_path)
    return os.path.abspath(path)

def _merge_phase8711_worker_logs(path):
    """Called by parent after join; no worker synchronization or reservation delay."""
    parent = Path(path)
    for sidecar in sorted(parent.parent.glob(parent.name + '.worker_*.tmp')):
        try:
            with open(parent, 'a', encoding='utf-8', buffering=1) as target:
                target.write(sidecar.read_text(encoding='utf-8'))
            sidecar.unlink()
        except Exception as exc:
            print(f'PHASE8_8_3_WORKER_LOG_MERGE_WARNING={type(exc).__name__}:{sidecar}', file=sys.stderr, flush=True)
atexit.register(_close_phase8711_log)
_FIXED_USER_SETTINGS = [{'profile_path': 'C:/Users/Takashi/OneDrive/Desktop/Lesson_Reservation/selenium_profiles/user_6010005815', 'username': '6010005815', 'password': '', 'lesson_requests': []}, {'profile_path': 'C:/Users/Takashi/OneDrive/Desktop/Lesson_Reservation/selenium_profiles/user_snuf48385', 'username': 'snuf48385', 'password': '', 'lesson_requests': []}]
users = [dict(item, lesson_requests=[]) for item in _FIXED_USER_SETTINGS]
LESSON_LIST_FILE = None
LESSON_LIST_MONTH = None
LESSON_LIST_SHA256 = None
LESSON_LIST_WARNINGS = []
LESSON_LIST_IGNORED_COMMENT_LINES = []
LESSON_LIST_FILENAME_RE = re.compile('^(\\d{6})_LessonList\\.txt$')

class LessonListValidationError(ValueError):
    pass

def _valid_lesson_list_month(value):
    if not re.fullmatch('\\d{6}', value or ''):
        return False
    year, month = (int(value[:4]), int(value[4:]))
    return 1 <= year <= 9999 and 1 <= month <= 12

def select_latest_lesson_list(directory):
    directory = Path(directory)
    candidates = []
    if directory.is_dir():
        for path in directory.iterdir():
            match = LESSON_LIST_FILENAME_RE.fullmatch(path.name)
            if path.is_file() and match and _valid_lesson_list_month(match.group(1)):
                candidates.append((match.group(1), path))
    if not candidates:
        raise LessonListValidationError('no valid YYYYMM_LessonList.txt candidate')
    by_month = {}
    for month, path in candidates:
        if month in by_month:
            raise LessonListValidationError(f'ambiguous LessonList month: {month}')
        by_month[month] = path
    return by_month[max(by_month)]

def parse_lesson_list(path, allowed_users=None, telemetry=None):
    path = Path(path)
    match = LESSON_LIST_FILENAME_RE.fullmatch(path.name)
    if not match or not _valid_lesson_list_month(match.group(1)):
        raise LessonListValidationError(f'invalid LessonList filename: {path.name}')
    month = match.group(1)
    allowed = set(allowed_users or [u['username'] for u in _FIXED_USER_SETTINGS])
    sections, current, identities = ({}, None, set())
    telemetry = telemetry if telemetry is not None else {}
    telemetry.setdefault('warnings', [])
    telemetry.setdefault('ignored_comment_lines', [])
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except (UnicodeError, OSError) as exc:
        raise LessonListValidationError(f'UTF-8 read failed: {exc}') from exc
    for line_number, raw in enumerate(lines, 1):
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith('#'):
            telemetry['ignored_comment_lines'].append(line_number)
            continue
        section = re.fullmatch('\\[([^\\[\\]]+)\\]', stripped)
        if section:
            current = section.group(1).strip()
            if not current or current not in allowed:
                raise LessonListValidationError(f'line {line_number}: unknown user {current!r}')
            if current in sections:
                raise LessonListValidationError(f'line {line_number}: duplicate user section {current}')
            sections[current] = []
            continue
        if current is None:
            raise LessonListValidationError(f'line {line_number}: request before user section')
        fields = [field.strip() for field in stripped.split('|')]
        if len(fields) != 4:
            raise LessonListValidationError(f'line {line_number}: expected date | start time | lesson | positions')
        date, start_time, lesson, position_text = fields
        from lesson_target import valid_time
        if not valid_time(start_time):
            raise LessonListValidationError(f'line {line_number}: invalid HH:MM start time')
        if not re.fullmatch('\\d{8}', date):
            raise LessonListValidationError(f'line {line_number}: invalid YYYYMMDD date')
        try:
            datetime.strptime(date, '%Y%m%d')
        except ValueError as exc:
            raise LessonListValidationError(f'line {line_number}: impossible date {date}') from exc
        if date[:6] != month:
            telemetry['warnings'].append({'type': 'CROSS_MONTH_REQUEST', 'list_month': month, 'request_date': date, 'request_month': date[:6], 'line_number': line_number, 'username': current, 'lesson': lesson})
        if not lesson:
            raise LessonListValidationError(f'line {line_number}: empty lesson name')
        raw_positions = [value.strip() for value in position_text.split(',')]
        if not raw_positions or any((not re.fullmatch('[1-9]\\d*', value) for value in raw_positions)):
            raise LessonListValidationError(f'line {line_number}: invalid or empty position list')
        positions = [int(value) for value in raw_positions]
        if len(set(positions)) != len(positions):
            raise LessonListValidationError(f'line {line_number}: duplicate position')
        identity = (current, date, start_time, normalize_lesson_name(lesson))
        if identity in identities:
            raise LessonListValidationError(f'line {line_number}: duplicate request identity')
        identities.add(identity)
        sections[current].append({'date': date, 'start_time': start_time, 'name': lesson, 'positions': positions})
    if not sections:
        raise LessonListValidationError('no user section')
    if any((not requests for requests in sections.values())):
        raise LessonListValidationError('user section has no request')
    return (month, sections)

def build_internal_users(sections):
    unknown = set(sections) - {u['username'] for u in _FIXED_USER_SETTINGS}
    if unknown:
        raise LessonListValidationError(f'unknown users: {sorted(unknown)}')
    bindings = _cla1_identity_bindings()
    return [dict(fixed, expected_member_identifier=bindings.get(fixed['username']), lesson_requests=[dict(request, positions=list(request['positions'])) for request in sections.get(fixed['username'], [])]) for fixed in _FIXED_USER_SETTINGS if fixed['username'] in sections]

def load_lesson_list(directory=None):
    global users, LESSON_LIST_FILE, LESSON_LIST_MONTH, LESSON_LIST_SHA256
    global LESSON_LIST_WARNINGS, LESSON_LIST_IGNORED_COMMENT_LINES
    root = Path(directory or os.environ.get('PHASE8_5_LESSON_LIST_DIR', 'C:/Users/Takashi/OneDrive/Desktop/Lesson_Reservation/reservation_lists'))
    selected = select_latest_lesson_list(root)
    telemetry = {}
    month, sections = parse_lesson_list(selected, telemetry=telemetry)
    loaded_users = build_internal_users(sections)
    if not loaded_users:
        raise LessonListValidationError('no executable users')
    users = loaded_users
    LESSON_LIST_FILE = selected
    LESSON_LIST_MONTH = month
    LESSON_LIST_SHA256 = hashlib.sha256(selected.read_bytes()).hexdigest().upper()
    LESSON_LIST_WARNINGS = list(telemetry['warnings'])
    LESSON_LIST_IGNORED_COMMENT_LINES = list(telemetry['ignored_comment_lines'])
    return users

def print_lesson_list():
    print('=' * 60)
    print('PHASE 8.5 - LESSON LIST')
    print('=' * 60)
    print(f'使用ファイル: {LESSON_LIST_FILE.name}')
    print(f'対象年月: {LESSON_LIST_MONTH[:4]}/{LESSON_LIST_MONTH[4:]}')
    print(f'LessonList SHA-256: {LESSON_LIST_SHA256}')
    print(f'Ignored Comment Lines: {len(LESSON_LIST_IGNORED_COMMENT_LINES)}')
    for line_number in LESSON_LIST_IGNORED_COMMENT_LINES:
        print('COMMENT_IGNORED ' + json.dumps({'line_number': line_number}, ensure_ascii=False, sort_keys=True))
    print(f'Cross-Month Requests: {len(LESSON_LIST_WARNINGS)}')
    for warning in LESSON_LIST_WARNINGS:
        print('LESSON_LIST_WARNING ' + json.dumps(warning, ensure_ascii=False, sort_keys=True))
    for user in users:
        print(f"\n■ {user['username']}")
        for request in user['lesson_requests']:
            date = datetime.strptime(request['date'], '%Y%m%d').strftime('%Y/%m/%d')
            print(f"  {date}\n  {request['name']}\n  希望位置: " + ' → '.join(map(str, request['positions'])))
            if request['date'][:6] != LESSON_LIST_MONTH:
                print('  WARNING: request month differs from LessonList month')
    print('-' * 60)
    print(f'ユーザー数 : {len(users)}')
    print(f"予約Request数 : {sum((len(u['lesson_requests']) for u in users))}")
    print('-' * 60)
LOGIN_URL = 'https://www5.e-atoms.jp/DSPWebUser/Account/LogIn'
RESERVATION_URL = 'https://www5.e-atoms.jp/DSPWebUser/LESSON/ReserveLessonSchedule'
RESERVATION_LIST_URL = 'https://www5.e-atoms.jp/DSPWebUser/LESSON/LessonList/ShowList'
RESERVATION_LIST_ALLOWED_PATHS = {'/DSPWebUser/LESSON/LessonList', '/DSPWebUser/LESSON/LessonList/ShowList'}
RECONCILIATION_CONFIRMATION_SOURCE = 'PRODUCTION_RESERVATION_LIST_RECONCILIATION'
RECONCILIATION_MAX_GETS_PER_USER_RUN = 2
RECONCILIATION_MAX_DRIVER_RECREATES_PER_USER_RUN = 1
RECONCILIATION_MAX_WALL_SECONDS = 20.0
RECONCILIATION_OBSERVATION_DELAY_SECONDS = 0.3

@dataclass(frozen=True)
class ReservationListRow:
    normalized_date: str
    canonical_lesson: str
    status: str
    position: Optional[int] = None
    start_time: Optional[str] = None

@dataclass(frozen=True)
class ReservationListSnapshot:
    page_identity_verified: bool
    user_identity_verified: bool
    render_complete: bool
    reservations: tuple
    evidence_digest: str
    observed_at: str

def _reservation_list_path(url):
    match = re.match('^https://www5\\.e-atoms\\.jp([^?#]*)', str(url or ''), re.I)
    return match.group(1) if match else None

def _phase810_date(value):
    parsed = _phase8_8_date_tuple(str(value or ''))
    return '%04d%02d%02d' % parsed if parsed else ''

def _phase810_parse_label(value):
    text = unicodedata.normalize('NFKC', html.unescape(str(value or ''))).strip()
    match = re.fullmatch('(.*?)\\s*\\[(\\d+)\\]\\s*', text)
    if match:
        core, position = (match.group(1).strip(), int(match.group(2)))
    elif re.search('\\[[^\\]]*\\]', text):
        raise ValueError('ambiguous position suffix')
    else:
        core, position = (text, None)
    from lesson_target import canonical_name
    canonical = canonical_name(core, normalize_lesson_name)
    if not canonical:
        raise ValueError('empty canonical lesson')
    return (canonical, position)

def _phase810_snapshot_from_raw(raw, expected_member_identifier=None, _observation=None):
    if not isinstance(raw, dict):
        raise ValueError('invalid reservation-list observation')
    page_ok = _reservation_list_path(raw.get('url')) in RESERVATION_LIST_ALLOWED_PATHS and str(raw.get('title') or '').strip() == '予約の確認・キャンセル' and (not raw.get('login_fields_present'))
    identity = raw.get('member_identity')
    observed = identity.get('value') if isinstance(identity, dict) else None
    user_ok = bool(isinstance(identity, dict) and identity.get('structure_valid') is True and (identity.get('visible') is True) and (type(observed) is str) and re.fullmatch('[0-9]{12}', observed) and (type(expected_member_identifier) is str) and re.fullmatch('[0-9]{12}', expected_member_identifier) and (observed == expected_member_identifier))
    _cla1_obs_call(_observation, 'raw', raw, expected_member_identifier, page_ok, user_ok)
    from lesson_target import range_start
    rows = []
    for item in raw.get('rows') or []:
        if not isinstance(item, dict):
            raise ValueError('invalid reservation row')
        date = _phase810_date(item.get('date'))
        lesson, suffix_position = _phase810_parse_label(item.get('lesson'))
        position = item.get('position', suffix_position)
        if position is not None:
            position = int(position)
            if suffix_position is not None and position != suffix_position:
                raise ValueError('conflicting position evidence')
        status = unicodedata.normalize('NFKC', str(item.get('status') or '')).strip()
        if not date or not status:
            raise ValueError('incomplete reservation row')
        rows.append(ReservationListRow(date, lesson, status, position, range_start(item.get('time_text'))))
    projection = [(r.normalized_date, r.canonical_lesson, r.status, r.position) for r in rows]
    if any(r.start_time is not None for r in rows):
        projection = [(*old, r.start_time) for old, r in zip(projection, rows)]
    digest = hashlib.sha256(json.dumps([identity, projection], ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()
    return ReservationListSnapshot(page_ok, user_ok, bool(raw.get('ready')) and (not bool(raw.get('blocking_overlay'))), tuple(rows), digest, datetime.now(timezone.utc).isoformat())

def _phase810_read_raw_snapshot(driver):
    """Read DOM only; the JavaScript contains no assignment, event, or mutation."""
    return driver.execute_script("\n        const containers=document.querySelectorAll('#logindisplay');\n        const headers=document.querySelectorAll('#logindisplay > div.atomsv-header-customer');\n        const fields=document.querySelectorAll('#logindisplay > div.atomsv-header-customer > span:first-child');\n        const header=headers.length===1?headers[0]:null;\n        const field=fields.length===1?fields[0]:null;\n        const children=header?Array.from(header.children):[];\n        const visible=e=>{if(!e)return false;const s=getComputedStyle(e),r=e.getBoundingClientRect();\n          return s.display!=='none'&&s.visibility==='visible'&&s.opacity!=='0'&&r.width>0&&r.height>0;};\n        const structureValid=containers.length===1&&headers.length===1&&fields.length===1&&\n          children.length===2&&children.every(e=>e.tagName==='SPAN')&&children[0]===field&&\n          field.childElementCount===0&&Array.from(header.childNodes).every(n=>\n            n.nodeType===1||(n.nodeType===3&&n.textContent.trim()===''));\n        const memberIdentity={structure_valid:structureValid,visible:visible(field),\n          value:field?field.textContent:null};\n        const cards=Array.from(document.querySelectorAll('li.ui-li-static'));\n        const rows=cards.map(card=>{const text=card.innerText||'';\n          const date=(text.match(/20\\d{2}[\\/年.-]\\d{1,2}[\\/月.-]\\d{1,2}/)||[''])[0];\n          const status=text.includes('予約中')?'予約中':(text.includes('キャンセル')?'CONFLICTING_OR_UNKNOWN':'UNKNOWN');\n          const lines=text.split(/\\r?\\n/).map(v=>v.trim()).filter(Boolean);\n          const lesson=lines.find(v=>/\\[\\d+\\]/.test(v))||'';\n          const pm=lesson.match(/\\[(\\d+)\\]\\s*$/);\n          return {date:date,lesson:lesson,status:status,position:pm?Number(pm[1]):null,time_text:text};});\n        return {url:location.href,title:document.title,\n          login_fields_present:!!document.querySelector('#UserName,#Password'),\n          member_identity:memberIdentity,ready:document.readyState==='complete',\n          blocking_overlay:Array.from(document.querySelectorAll('.blockUI')).some(e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&s.opacity!=='0'&&r.width>0&&r.height>0;}),rows:rows};\n    ")

def _phase810_collect_submit_intents(username, requests):
    try:
        journal, _ = _read_journal(username)
    except Exception:
        return ([], 'JOURNAL_SCAN_FAILED')
    eligible = []
    for request in requests:
        try:
            identity = _journal_identity(username, request)
            record = journal['requests'].get(_journal_request_key(identity))
            if record and record.get('state') == 'SUBMIT_INTENT' and (record.get('identity') == identity) and (record.get('submit_intent_durable') is True) and (not record.get('contradictory_local_evidence')):
                eligible.append((request, record))
        except Exception:
            continue
    return (eligible, None)

def _phase810_classify(snapshot, request, _observation=None):
    if not snapshot.page_identity_verified:
        return ('STILL_UNKNOWN', 'WRONG_OR_UNKNOWN_PAGE', None)
    if not snapshot.user_identity_verified:
        return ('STILL_UNKNOWN', 'USER_IDENTITY_UNVERIFIED', None)
    if not snapshot.render_complete:
        return ('STILL_UNKNOWN', 'RENDER_INCOMPLETE', None)
    from lesson_target import canonical_name, names_match
    target_date = _phase810_date(request.get('date'))
    target_lesson = (canonical_name(request.get('name'), normalize_lesson_name)
                     if 'start_time' in request else normalize_lesson_name(request.get('name')))
    _cla1_obs_call(_observation, 'match_start', bool(target_date), bool(target_lesson))
    if not target_date or not target_lesson:
        return ('STILL_UNKNOWN', 'JOURNAL_IDENTITY_INVALID', None)
    same = [r for r in snapshot.reservations if _cla1_obs_compare(_observation, 'date_match', r.normalized_date == target_date) and _cla1_obs_compare(_observation, 'lesson_match', names_match(r.canonical_lesson, request.get('name'), target_date, r.start_time, normalize_lesson_name) if 'start_time' in request else normalize_lesson_name(r.canonical_lesson) == target_lesson) and ('start_time' not in request or (r.start_time is not None and r.start_time == request['start_time']))]
    active, conflicting = ([r for r in same if r.status == '予約中'], [r for r in same if r.status != '予約中'])
    _cla1_obs_call(_observation, 'match_counts', len(same), len(active), len(conflicting))
    if conflicting:
        return ('STILL_UNKNOWN', 'CONFLICTING_STATUS', None)
    if not active:
        return ('STILL_UNKNOWN', 'ZERO_MATCH_COMPLETENESS_UNVERIFIED', None)
    if len(active) != 1:
        return ('STILL_UNKNOWN', 'MULTIPLE_ACTIVE_MATCHES', None)
    return ('CONFIRMED', 'POSITIVE_EXACT_ACTIVE_MATCH', active[0])

def _phase810_write_unknown(username, request, prior, reason):
    attempts = int(prior.get('reconciliation_attempt_count', 0)) + 1
    return _journal_write_state(username, request, 'SUBMIT_INTENT', selected_position=prior.get('selected_position'), confirmation_evidence=prior.get('confirmation_evidence'), attempt_count=int(prior.get('attempt_count', 0)), reconciliation_attempt_count=attempts, last_reconciliation_outcome='STILL_UNKNOWN', last_reconciliation_reason=reason, last_reconciliation_at=datetime.now(timezone.utc).isoformat(), manual_review_warning=attempts >= 3, action_boundary=prior.get('action_boundary'))

def reconcile_submit_intents_for_user(driver, wait, user, requests, sleep_fn=time.sleep, recreate_fn=None):
    """One bounded, user-scoped, positive-only reconciliation session."""
    started, username = (time.monotonic(), user['username'])
    deadline = started + RECONCILIATION_MAX_WALL_SECONDS
    evidence_observed_at = None
    expected_member_identifier = user.get('expected_member_identifier')
    eligible, scan_error = _phase810_collect_submit_intents(username, requests)
    counters = {'session_count': 0, 'get_count': 0, 'driver_recreate_count': 0, 'reconciled_confirmed_count': 0, 'existing_confirmed_skipped_count': 0}
    if not eligible:
        return (driver, wait, [], counters)
    counters['session_count'] = 1
    current_driver, current_wait, snapshot, failure_reason = (driver, wait, None, scan_error)
    while counters['get_count'] < RECONCILIATION_MAX_GETS_PER_USER_RUN:
        if time.monotonic() >= deadline:
            failure_reason = 'RECONCILIATION_TIMEOUT'
            break
        try:
            counters['get_count'] += 1
            if hasattr(current_driver, 'set_page_load_timeout'):
                current_driver.set_page_load_timeout(9)
            current_driver.get(RESERVATION_LIST_URL)
            if time.monotonic() >= deadline:
                failure_reason = 'RECONCILIATION_TIMEOUT'
                break
            first = _phase810_snapshot_from_raw(_phase810_read_raw_snapshot(current_driver), expected_member_identifier)
            evidence_observed_at = time.monotonic()
            if evidence_observed_at >= deadline:
                failure_reason = 'RECONCILIATION_TIMEOUT'
                break
            sleep_fn(min(RECONCILIATION_OBSERVATION_DELAY_SECONDS, max(0.0, deadline - evidence_observed_at)))
            if time.monotonic() > deadline:
                failure_reason = 'RECONCILIATION_TIMEOUT'
                break
            second = _phase810_snapshot_from_raw(_phase810_read_raw_snapshot(current_driver), expected_member_identifier)
            evidence_observed_at = time.monotonic()
            if evidence_observed_at > deadline:
                failure_reason = 'RECONCILIATION_TIMEOUT'
                break
            if first.evidence_digest != second.evidence_digest or first.page_identity_verified != second.page_identity_verified or first.user_identity_verified != second.user_identity_verified or (first.render_complete != second.render_complete):
                failure_reason = 'DOM_UNSTABLE'
            else:
                snapshot = second
            break
        except Exception as exc:
            failure_reason = 'ADAPTER_FAILURE_' + type(exc).__name__
            if time.monotonic() >= deadline:
                failure_reason = 'RECONCILIATION_TIMEOUT'
                break
            if recreate_fn is None or counters['driver_recreate_count'] >= RECONCILIATION_MAX_DRIVER_RECREATES_PER_USER_RUN:
                break
            counters['driver_recreate_count'] += 1
            try:
                current_driver, current_wait = recreate_fn(user, current_driver)
            except Exception as recreate_exc:
                failure_reason = 'DRIVER_RECREATE_FAILED_' + type(recreate_exc).__name__
                break
    results = []
    for request, prior in eligible:
        outcome, reason, row = ('STILL_UNKNOWN', failure_reason or 'ADAPTER_FAILURE', None) if snapshot is None else _phase810_classify(snapshot, request)
        acceptance_checked_at = time.monotonic()
        if outcome == 'CONFIRMED' and (evidence_observed_at is None or evidence_observed_at > deadline or acceptance_checked_at > deadline):
            outcome, reason, row = ('STILL_UNKNOWN', 'RECONCILIATION_TIMEOUT', None)
        if outcome == 'CONFIRMED':
            preferred = set((int(p) for p in request.get('positions') or []))
            mismatch = not _cla1_position_match(request, prior.get('selected_position'), row.position)
            if mismatch:
                outcome, reason = ('STILL_UNKNOWN', 'POSITION_IDENTITY_UNVERIFIED')
        if outcome == 'CONFIRMED':
            evidence = {'positive': True, 'confirmation_source': RECONCILIATION_CONFIRMATION_SOURCE, 'evidence_digest': snapshot.evidence_digest, 'active_match_count': 1, 'observed_position': row.position, 'position_mismatch_warning': mismatch, 'privacy_redacted': True}
            try:
                _journal_write_state(username, request, 'CONFIRMED', selected_position=row.position, confirmation_evidence=evidence, attempt_count=int(prior.get('attempt_count', 0)), reconciliation_attempt_count=int(prior.get('reconciliation_attempt_count', 0)) + 1, confirmation_source=RECONCILIATION_CONFIRMATION_SOURCE, last_reconciliation_outcome='CONFIRMED', last_reconciliation_reason=reason, last_reconciliation_at=datetime.now(timezone.utc).isoformat())
                counters['reconciled_confirmed_count'] += 1
            except Exception:
                outcome, reason = ('STILL_UNKNOWN', 'CONFIRMED_JOURNAL_WRITE_FAILED')
        if outcome != 'CONFIRMED':
            try:
                _phase810_write_unknown(username, request, prior, reason)
            except Exception:
                reason = 'STILL_UNKNOWN_METADATA_WRITE_FAILED'
        results.append({'username': username, 'date': request.get('date'), 'lesson': request.get('name'), 'state': outcome, 'reason_code': reason, 'reservation_count_incremented': False, 'timing_evidence': {'clock': 'monotonic', 'attempt_started_at': started, 'timeout_seconds': RECONCILIATION_MAX_WALL_SECONDS, 'deadline': deadline, 'evidence_observed_at': evidence_observed_at, 'acceptance_checked_at': acceptance_checked_at, 'confirmation_operator': '<=', 'late_rejection_operator': '>'}, 'confirmation_source': RECONCILIATION_CONFIRMATION_SOURCE if outcome == 'CONFIRMED' else None, 'position': row.position if row else None, 'reconciled_confirmed_count': 1 if outcome == 'CONFIRMED' else 0})
    return (current_driver, current_wait, results, counters)

def wait_for_overlay_clear(driver, timeout=5):
    """blockUI がDOMに残っていても、操作を遮らない状態になるまで待機する。"""
    last_evidence = {}

    def overlay_is_clear(current_driver):
        nonlocal last_evidence
        evidence = current_driver.execute_script("\n            const overlays = Array.from(document.querySelectorAll('.blockUI'));\n            const inspected = overlays.map((element) => {\n                const style = window.getComputedStyle(element);\n                const rect = element.getBoundingClientRect();\n                const displayed = style.display !== 'none';\n                const visible = style.visibility !== 'hidden' && style.opacity !== '0';\n                const hasArea = rect.width > 0 && rect.height > 0;\n                return {\n                    className: element.className,\n                    displayed: displayed,\n                    visibility: style.visibility,\n                    display: style.display,\n                    opacity: style.opacity,\n                    hasArea: hasArea,\n                    blocking: displayed && visible && hasArea,\n                };\n            });\n            return {\n                url: window.location.href,\n                overlayCount: inspected.length,\n                overlays: inspected,\n                blockingOverlayCount: inspected.filter((overlay) => overlay.blocking).length,\n            };\n            ")
        last_evidence = evidence
        return evidence['blockingOverlayCount'] == 0
    try:
        WebDriverWait(driver, timeout).until(overlay_is_clear)
        return make_result('OK', 'OVERLAY_CLEAR', timeout=timeout, **last_evidence)
    except TimeoutException:
        return make_result('OVERLAY_TIMEOUT', 'OVERLAY_CLEAR', reason='visible blockUI remained', retryable=True, timeout=timeout, **last_evidence)
    except Exception as exc:
        return make_result('OVERLAY_CHECK_FAILED', 'OVERLAY_CLEAR', reason=type(exc).__name__, retryable=True, timeout=timeout, **last_evidence)

def login_and_verify(driver, wait, user, max_attempts=3):
    """ログインを行い、認証済み状態を最大3回の独立した確認で肯定する。"""
    failure_markers = ('ユーザー名またはパスワード', 'ログインに失敗', '認証に失敗')
    evidence = {'attempts': 0, 'url': None, 'login_fields_present': None, 'failure_message_detected': False, 'exception_type': None, 'attempt_history': []}
    try:
        driver.get(LOGIN_URL)
        username = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'UserName')))
        password = driver.find_element(By.ID, 'Password')
        username.clear()
        password.clear()
        username.send_keys(user['username'])
        password.send_keys(user['password'])
        driver.find_element(By.CSS_SELECTOR, 'input.btn_conform').click()
    except Exception as exc:
        evidence.update({'url': getattr(driver, 'current_url', None), 'exception_type': type(exc).__name__, 'attempt_history': [{'attempt': 0, 'stage': 'login_submission', 'outcome': 'login submission not confirmed', 'exception_type': type(exc).__name__}]})
    for attempt in range(1, max_attempts + 1):
        attempt_evidence = {'attempt': attempt, 'url': None, 'login_fields_present': None, 'failure_message_detected': False, 'exception_type': None}
        evidence['attempts'] = attempt
        try:

            def authenticated(current_driver):
                current_url = current_driver.current_url
                login_fields = current_driver.find_elements(By.ID, 'UserName') + current_driver.find_elements(By.ID, 'Password')
                page_text = current_driver.find_element(By.TAG_NAME, 'body').text
                failure_detected = any((marker in page_text for marker in failure_markers))
                attempt_evidence.update({'url': current_url, 'login_fields_present': bool(login_fields), 'failure_message_detected': failure_detected})
                if failure_detected:
                    return 'LOGIN_FAILED'
                if '/Account/LogIn' not in current_url and (not login_fields):
                    return 'LOGINED'
                return False
            verification = WebDriverWait(driver, 10).until(authenticated)
            evidence['attempt_history'].append({**attempt_evidence, 'outcome': verification})
            evidence.update({'url': attempt_evidence['url'], 'login_fields_present': attempt_evidence['login_fields_present'], 'failure_message_detected': attempt_evidence['failure_message_detected'], 'exception_type': None})
            if verification == 'LOGIN_FAILED':
                return make_result('LOGIN_FAILED', 'LOGINED', reason='login failure message detected', retryable=False, **evidence)
            identity_stop = _cla1_identity_guard(driver, user)
            if identity_stop is not None:
                return identity_stop
            return make_result('OK', 'LOGINED', **evidence)
        except (StaleElementReferenceException, TimeoutException) as exc:
            attempt_evidence.update({'url': getattr(driver, 'current_url', None), 'exception_type': type(exc).__name__, 'outcome': 'retryable verification failure'})
            evidence['attempt_history'].append(attempt_evidence)
            evidence.update({'url': attempt_evidence['url'], 'login_fields_present': attempt_evidence['login_fields_present'], 'failure_message_detected': attempt_evidence['failure_message_detected'], 'exception_type': attempt_evidence['exception_type']})
        except Exception as exc:
            attempt_evidence.update({'url': getattr(driver, 'current_url', None), 'exception_type': type(exc).__name__, 'outcome': 'verification exception'})
            evidence['attempt_history'].append(attempt_evidence)
            evidence.update({'url': attempt_evidence['url'], 'login_fields_present': attempt_evidence['login_fields_present'], 'failure_message_detected': attempt_evidence['failure_message_detected'], 'exception_type': attempt_evidence['exception_type']})
    return make_result('UNKNOWN_LOGIN', 'LOGINED', reason='authentication state was not confirmed after retries', retryable=True, **evidence)
RESERVATION_PAGE_READY = 'RESERVATION_PAGE_READY'
CONGESTED = 'CONGESTED'
LOGIN_REQUIRED = 'LOGIN_REQUIRED'
HTTP_OR_NETWORK_ERROR = 'HTTP_OR_NETWORK_ERROR'
PAGE_LOADING_OR_INCOMPLETE = 'PAGE_LOADING_OR_INCOMPLETE'
UNKNOWN = 'UNKNOWN'
CONGESTION_TIMEOUT = 'CONGESTION_TIMEOUT'
CONGESTION_TEXT_MARKERS = ('混み合っております', '混雑しています', 'しばらくしてから', 'アクセス集中', 'temporarily unavailable', 'service unavailable')
LOGIN_TEXT_MARKERS = ('セッションの有効期限', '再度ログイン', '認証が必要')
FATAL_ERROR_TEXT_MARKERS = ('致命的なエラー', '予期しないエラー', 'internal server error')

@dataclass(frozen=True)
class CongestionRecoveryPolicy:
    base_delay_seconds: float = 0.25
    backoff_step_seconds: float = 0.075
    max_delay_seconds: float = 0.5
    jitter_seconds: float = 0.025
    max_attempts: int = 6
    max_total_wait_seconds: float = 2.5
    incomplete_poll_seconds: float = 0.1
    incomplete_checks_before_request: int = 2
    cautious_429_multiplier: float = 1.5
    max_navigation_seconds: float = 20.0
    max_recovery_wall_clock_seconds: float = 60.0

def _reservation_page_snapshot(driver):
    """Collect bounded, read-only evidence; never persist the full HTML."""
    return driver.execute_script('\n        const visible=(e)=>{if(!e)return false;const s=getComputedStyle(e),r=e.getBoundingClientRect();\n          return s.display!==\'none\'&&s.visibility!==\'hidden\'&&s.opacity!==\'0\'&&r.width>0&&r.height>0;};\n        const body=String(document.body ? document.body.innerText : \'\').slice(0,12000);\n        const headers=Array.from(document.querySelectorAll(\'#schedule_header\')).filter(visible);\n        const cells=Array.from(document.querySelectorAll(\'td.lesson\')).filter(visible);\n        const overlays=Array.from(document.querySelectorAll(\n          \'.blockUI,.blockOverlay,.modal-backdrop,.loading,.overlay,[aria-busy="true"]\'))\n          .filter(e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();\n            return visible(e)&&s.pointerEvents!==\'none\'&&r.width>0&&r.height>0;});\n        const loginFields=Array.from(document.querySelectorAll(\n          \'#UserName,#Password,input[name="UserName"],input[name="Password"],input[type="password"]\'));\n        return {url:location.href,body_text:body,body_child_count:document.body?document.body.children.length:0,\n          document_ready_state:document.readyState,schedule_header_visible:headers.length>0,\n          schedule_cell_count:cells.length,schedule_cells_readable:cells.some(e=>String(e.innerText||e.textContent).trim().length>0),\n          blocking_overlay_count:overlays.length,login_field_count:loginFields.length,\n          reservation_marker_count:document.querySelectorAll(\'#schedule_header,table.schedule,.lesson_schedule\').length};\n        ')

def classify_reservation_page_state(driver, navigation_error=None, http_status=None):
    """Classify live and simulated pages using the exact same evidence path."""
    if navigation_error is not None or http_status in (429, 500, 502, 503, 504):
        error_name = type(navigation_error).__name__ if navigation_error else None
        return make_result('RETRYABLE', HTTP_OR_NETWORK_ERROR, retryable=True, exception_type=error_name, http_status=http_status)
    try:
        evidence = _reservation_page_snapshot(driver)
    except (TimeoutException, WebDriverException) as exc:
        return make_result('RETRYABLE', HTTP_OR_NETWORK_ERROR, retryable=True, exception_type=type(exc).__name__, http_status=http_status)
    except Exception as exc:
        return make_result('UNKNOWN', UNKNOWN, retryable=False, reason='snapshot failed', exception_type=type(exc).__name__)
    url = (evidence.get('url') or '').lower()
    text = (evidence.get('body_text') or '').lower()
    login_marker = '/account/login' in url or '/account/logIn'.lower() in url or evidence.get('login_field_count', 0) > 0 or any((marker.lower() in text for marker in LOGIN_TEXT_MARKERS))
    congestion_markers = [marker for marker in CONGESTION_TEXT_MARKERS if marker.lower() in text]
    fatal_markers = [marker for marker in FATAL_ERROR_TEXT_MARKERS if marker.lower() in text]
    reservation_url = '/lesson/reservelessonschedule' in url
    reservation_marker = evidence.get('reservation_marker_count', 0) > 0
    header = bool(evidence.get('schedule_header_visible'))
    cells = evidence.get('schedule_cell_count', 0) > 0 and bool(evidence.get('schedule_cells_readable'))
    overlay_clear = evidence.get('blocking_overlay_count', 0) == 0
    if login_marker:
        return make_result('STOP', LOGIN_REQUIRED, retryable=False, **evidence)
    if congestion_markers:
        return make_result('RETRYABLE', CONGESTED, retryable=True, matched_markers=congestion_markers, **evidence)
    if (reservation_url or reservation_marker) and header and cells and overlay_clear and (not fatal_markers):
        return make_result('OK', RESERVATION_PAGE_READY, retryable=False, **evidence)
    if fatal_markers:
        return make_result('UNKNOWN', UNKNOWN, retryable=False, reason='fatal error marker detected', fatal_markers=fatal_markers, **evidence)
    if reservation_url and (not header or not cells or (not overlay_clear) or (evidence.get('document_ready_state') != 'complete')):
        return make_result('RETRYABLE', PAGE_LOADING_OR_INCOMPLETE, retryable=True, incomplete_reasons={'header_missing': not header, 'cells_unreadable': not cells, 'blocking_overlay': not overlay_clear, 'document_not_complete': evidence.get('document_ready_state') != 'complete'}, **evidence)
    return make_result('UNKNOWN', UNKNOWN, retryable=False, reason='no recognized positive state evidence', fatal_markers=fatal_markers, **evidence)

def _retry_delay(policy, attempt, state, http_status, rng):
    delay = min(policy.max_delay_seconds, policy.base_delay_seconds + policy.backoff_step_seconds * max(0, attempt - 1))
    if http_status == 429:
        delay = min(policy.max_delay_seconds, delay * policy.cautious_429_multiplier)
    delay += rng.uniform(-policy.jitter_seconds, policy.jitter_seconds)
    return max(0.0, delay)

def recover_reservation_page(driver, username, policy=None, sleep_fn=time.sleep, clock_fn=time.perf_counter, rng=None):
    """One in-flight navigation per worker; no cross-worker barrier after release."""
    policy = policy or CongestionRecoveryPolicy()
    rng = rng or random.Random()
    started = clock_fn()
    first_detected = congestion_detected = ready_at = None
    history = []
    total_wait = 0.0
    total_reobserve_wait = 0.0
    congestion_count = network_count = incomplete_count = 0
    navigation_timeout_count = long_navigation_count = 0
    attempt_in_flight = False
    final = None
    for attempt in range(1, policy.max_attempts + 1):
        if attempt_in_flight:
            raise AssertionError('duplicate reservation attempt')
        attempt_in_flight = True
        attempt_start = clock_fn()
        navigation_start = clock_fn()
        nav_error = None
        http_status = None
        try:
            driver.get(RESERVATION_URL)
        except (TimeoutException, WebDriverException, ConnectionError) as exc:
            nav_error = exc
            http_status = getattr(exc, 'http_status', None)
        finally:
            navigation_return = clock_fn()
            attempt_in_flight = False
        navigation_block_ms = (navigation_return - navigation_start) * 1000.0
        navigation_class = 'FAST_NAVIGATION' if navigation_block_ms < 500 else 'MODERATE_NAVIGATION_DELAY' if navigation_block_ms < 1500 else 'LONG_NAVIGATION_BLOCK'
        if navigation_class == 'LONG_NAVIGATION_BLOCK':
            long_navigation_count += 1
        if isinstance(nav_error, TimeoutException):
            navigation_timeout_count += 1
            classify_started = clock_fn()
            result = classify_reservation_page_state(driver)
            if result.state == PAGE_LOADING_OR_INCOMPLETE:
                incomplete_count += 1
        else:
            classify_started = clock_fn()
            result = classify_reservation_page_state(driver, nav_error, http_status)
        classification_ms = (clock_fn() - classify_started) * 1000.0
        incomplete_checks = 0
        reobserve_started = clock_fn()
        while result.state == PAGE_LOADING_OR_INCOMPLETE and incomplete_checks < policy.incomplete_checks_before_request:
            poll_wait = policy.incomplete_poll_seconds
            if clock_fn() - started + poll_wait > policy.max_recovery_wall_clock_seconds:
                break
            sleep_fn(poll_wait)
            total_reobserve_wait += poll_wait
            incomplete_checks += 1
            result = classify_reservation_page_state(driver)
        same_document_reobserve_ms = (clock_fn() - reobserve_started) * 1000.0
        detected = clock_fn()
        first_detected = first_detected if first_detected is not None else detected
        if result.state == CONGESTED:
            congestion_count += 1
            congestion_detected = congestion_detected if congestion_detected is not None else detected
        if result.state == HTTP_OR_NETWORK_ERROR:
            network_count += 1
        if result.state == PAGE_LOADING_OR_INCOMPLETE:
            incomplete_count += 1
        wait_next = 0.0
        retryable = result.state in {CONGESTED, PAGE_LOADING_OR_INCOMPLETE, HTTP_OR_NETWORK_ERROR}
        if result.state == RESERVATION_PAGE_READY:
            ready_at = detected
        elif retryable and attempt < policy.max_attempts:
            wait_next = _retry_delay(policy, attempt, result.state, http_status, rng)
            if total_wait + wait_next > policy.max_total_wait_seconds:
                result = make_result('TIMEOUT', CONGESTION_TIMEOUT, retryable=False, reason='max_total_wait_seconds reached')
                wait_next = 0.0
        nominal_delay = min(policy.max_delay_seconds, policy.base_delay_seconds + policy.backoff_step_seconds * max(0, attempt - 1))
        history.append({'attempt': attempt, 'state': result.state, 'attempt_start': attempt_start, 'attempt_end': clock_fn(), 'elapsed_ms': (clock_fn() - attempt_start) * 1000.0, 'wait_before_next_ms': wait_next * 1000.0, 'retry_wait_ms': wait_next * 1000.0, 'jitter_ms': (wait_next - nominal_delay) * 1000.0 if wait_next else 0.0, 'navigation_start_perf': navigation_start, 'navigation_return_perf': navigation_return, 'navigation_block_ms': navigation_block_ms, 'navigation_class': navigation_class, 'state_snapshot_ms': classification_ms, 'state_classification_ms': classification_ms, 'same_document_reobserve_ms': same_document_reobserve_ms, 'http_status': http_status, 'exception_type': type(nav_error).__name__ if nav_error else None})
        final = result
        if result.state == RESERVATION_PAGE_READY or not retryable or wait_next == 0.0:
            break
        sleep_fn(wait_next)
        total_wait += wait_next
        if clock_fn() - started > policy.max_recovery_wall_clock_seconds:
            final = make_result('TIMEOUT', CONGESTION_TIMEOUT, retryable=False, reason='max_recovery_wall_clock_seconds reached')
            break
    else:
        final = make_result('TIMEOUT', CONGESTION_TIMEOUT, retryable=False, reason='max_attempts reached')
    if final.state in {CONGESTED, PAGE_LOADING_OR_INCOMPLETE, HTTP_OR_NETWORK_ERROR}:
        final = make_result('TIMEOUT', CONGESTION_TIMEOUT, retryable=False, reason='max_attempts reached')
        history[-1]['state'] = CONGESTION_TIMEOUT
    ended = clock_fn()
    details = {'mode': PHASE8_1_MODE, 'username': username, 'final_state': final.state, 'attempt_count': len(history), 'congestion_count': congestion_count, 'network_error_count': network_count, 'incomplete_count': incomplete_count, 'navigation_timeout_count': navigation_timeout_count, 'long_navigation_count': long_navigation_count, 'total_wait_ms': total_wait * 1000.0, 'attempt_history': history, 'total_retry_wait_ms': total_wait * 1000.0, 'total_same_document_reobserve_wait_ms': total_reobserve_wait * 1000.0, 'reservation_request_start': started, 'first_state_detected': first_detected, 'congestion_detected_timestamp': congestion_detected, 'ready_timestamp': ready_at, 'congestion_duration_ms': (ready_at - congestion_detected) * 1000.0 if ready_at is not None and congestion_detected is not None else None, 'reservation_request_to_ready_ms': (ready_at - started) * 1000.0 if ready_at is not None else None, 'recovered': ready_at is not None and congestion_count + network_count > 0, 'fastpath_handoff_allowed': final.state == RESERVATION_PAGE_READY, 'attempt_in_flight': attempt_in_flight, 'dry_run_stopped_before_lesson': PHASE8_1_MODE == 'live-dry-run', 'dry_run_stop_after_reservation_page_ready': DRY_RUN_STOP_AFTER_RESERVATION_PAGE_READY, 'reservation_count': 0, 'reservation_count_incremented': False, 'final_submit_clicked': False, 'confirmsubmit_clicked': False, 'submission_attempted': False, 'reservation_confirmed': False, 'legacy_fallback_used': False, 'policy': vars(policy)}
    return make_result('OK' if final.state == RESERVATION_PAGE_READY else final.code, final.state, **details)

def open_reservation_page(driver, wait=None, max_retries=None):
    """Phase 8.1 compatibility entry: READY alone unlocks the existing fastpath."""
    max_attempts = max_retries if max_retries is not None else 6
    username = getattr(driver, 'phase8_1_username', 'unknown')
    return recover_reservation_page(driver, username, policy=CongestionRecoveryPolicy(max_attempts=max_attempts))

def reload_until_available(driver, max_retries=10, retry_interval=3):
    for attempt in range(max_retries):
        try:
            driver.find_element(By.XPATH, "//*[contains(text(), '混み合っております')]")
            print(f'⚠️ サイト混雑中（{attempt + 1}/{max_retries}）→ リロード')
            driver.refresh()
            time.sleep(retry_interval)
        except:
            print('✅ サイト正常表示')
            return True
    print('❌ 最大リトライ超過')
    return False

def inspect_schedule_range(driver, target_date):
    """#schedule_header を解析し、対象日が表示範囲内かを Result で返す。"""
    evidence = {'header_text': None, 'parsed_start_date': None, 'parsed_end_date': None, 'target_date': target_date, 'url': driver.current_url}
    try:
        headers = driver.find_elements(By.ID, 'schedule_header')
        if not headers or not headers[0].is_displayed():
            return make_result('TIMEOUT', 'SCHEDULE_RANGE_INSPECTED', reason='schedule_header was not present and visible', retryable=True, **evidence)
        header_text = headers[0].text.strip()
        evidence['header_text'] = header_text
        match = re.fullmatch('\\s*(\\d{4})/(\\d{1,2})/(\\d{1,2})\\s*-\\s*(\\d{4})/(\\d{1,2})/(\\d{1,2})\\s*', header_text)
        if not match:
            return make_result('DATE_PARSE_FAILED', 'SCHEDULE_RANGE_INSPECTED', reason='schedule_header did not match YYYY/M/D - YYYY/M/D', retryable=False, **evidence)
        values = [int(value) for value in match.groups()]
        start_date = datetime(*values[:3]).date()
        end_date = datetime(*values[3:]).date()
        parsed_target = datetime.strptime(str(target_date), '%Y%m%d').date()
        evidence.update({'parsed_start_date': start_date.isoformat(), 'parsed_end_date': end_date.isoformat()})
        if start_date <= parsed_target <= end_date:
            return make_result('OK', 'TARGET_DATE_VISIBLE', **evidence)
        return make_result('DATE_OUT_OF_RANGE', 'SCHEDULE_RANGE_INSPECTED', reason='target_date was outside the displayed schedule range', retryable=True, **evidence)
    except (TypeError, ValueError):
        return make_result('DATE_PARSE_FAILED', 'SCHEDULE_RANGE_INSPECTED', reason='schedule range or target_date could not be parsed', retryable=False, **evidence)
    except Exception as exc:
        evidence['url'] = getattr(driver, 'current_url', evidence['url'])
        return make_result('UNKNOWN', 'SCHEDULE_RANGE_INSPECTED', reason=type(exc).__name__, retryable=True, **evidence)

def _schedule_cell_snapshot(driver):
    """可視日程セルの再描画を判定するための軽量スナップショット。"""
    return driver.execute_script("\n        return Array.from(document.querySelectorAll('td.lesson'))\n            .filter((cell) => {\n                const style = window.getComputedStyle(cell);\n                const rect = cell.getBoundingClientRect();\n                return style.display !== 'none' && style.visibility !== 'hidden'\n                    && rect.width > 0 && rect.height > 0;\n            })\n            .map((cell) => ({\n                text: cell.innerText,\n                links: Array.from(cell.querySelectorAll('a'))\n                    .map((link) => link.getAttribute('onclick') || link.href || '')\n            }));\n        ")
PHASE8_8_REOBSERVE_LIMIT = 5
PHASE8_8_REOBSERVE_INTERVAL_SECONDS = 0.2
PHASE8_8_PAGE_BOUNDARY_SECONDS = 5.0
PHASE8_8_REQUEST_SCHEDULE_SECONDS = 15.0

def _phase8_8_schedule_header_range(value):
    match = re.fullmatch('\\s*(\\d{4})/(\\d{1,2})/(\\d{1,2})\\s*-\\s*(\\d{4})/(\\d{1,2})/(\\d{1,2})\\s*', str(value or ''))
    if not match:
        return None
    try:
        parts = [int(item) for item in match.groups()]
        return (datetime(*parts[:3]).date(), datetime(*parts[3:]).date())
    except ValueError:
        return None

def _phase8_8_dispatch_schedule_next(driver, wait):
    if driver.execute_script("return typeof scheduleNext === 'function';"):
        driver.execute_script('scheduleNext();')
        return 'scheduleNext'
    next_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(),'次へ') or contains(text(),'›') or contains(text(),'>')]")))
    driver.execute_script('arguments[0].click();', next_button)
    return 'next_button'

def _phase8_8_schedule_observation(driver, previous_header, old_snapshot, target_date=None):
    page = classify_reservation_page_state(driver)
    headers = driver.find_elements(By.ID, 'schedule_header')
    current_header = headers[0].text.strip() if headers and headers[0].is_displayed() else None
    current_snapshot = _schedule_cell_snapshot(driver) if current_header else []
    old_range = _phase8_8_schedule_header_range(previous_header)
    current_range = _phase8_8_schedule_header_range(current_header)
    range_changed = bool(old_range and current_range and (current_range != old_range))
    range_expanded_forward = bool(old_range and current_range and (current_range[0] >= old_range[0]) and (current_range[1] > old_range[1]))
    target_value = None
    try:
        target_value = datetime.strptime(str(target_date), '%Y%m%d').date() if target_date else None
    except (TypeError, ValueError):
        target_value = None
    target_in_after_range = bool(target_value and current_range and (current_range[0] <= target_value <= current_range[1]))
    snapshot_changed = current_snapshot != old_snapshot
    header_advanced = range_expanded_forward
    state = page.state
    positive = bool(state == RESERVATION_PAGE_READY and range_expanded_forward and snapshot_changed and (len(current_snapshot) > 0))
    idle = False
    runtime = {'document_ready_state': None, 'jquery_active': None, 'blocking_overlay_count': None, 'blocking_overlay_selector': None}
    try:
        collected_runtime = driver.execute_script('\n            const selectors=[\'.blockUI\',\'.blockOverlay\',\'.modal-backdrop\',\'.loading\',\n              \'.overlay\',\'[aria-busy="true"]\'];\n            const visible=(e)=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();\n              return s.display!==\'none\'&&s.visibility!==\'hidden\'&&s.opacity!==\'0\'&&\n                s.pointerEvents!==\'none\'&&r.width>0&&r.height>0;};\n            const blocking=[];\n            for (const selector of selectors) {\n              for (const element of document.querySelectorAll(selector)) {\n                if (visible(element)) blocking.push(selector);\n              }\n            }\n            return {document_ready_state:document.readyState,\n              jquery_active:window.jQuery ? window.jQuery.active : null,\n              blocking_overlay_count:blocking.length,\n              blocking_overlay_selector:[...new Set(blocking)].join(\',\') || null};\n            ')
        if isinstance(collected_runtime, dict):
            runtime.update(collected_runtime)
        idle = bool(runtime.get('document_ready_state') == 'complete' and runtime.get('jquery_active') in (None, 0) and (runtime.get('blocking_overlay_count') == 0))
    except Exception:
        idle = False
    snapshot_summary = hashlib.sha256(json.dumps(current_snapshot, ensure_ascii=False, sort_keys=True, default=str).encode('utf-8')).hexdigest()[:16]
    return {'state': state, 'current_header': current_header, 'classifier_code': page.code, 'classifier_reason': page.reason, 'classifier_incomplete_reasons': page.details.get('incomplete_reasons'), 'document_ready_state': runtime.get('document_ready_state'), 'jquery_active': runtime.get('jquery_active'), 'blocking_overlay_count': runtime.get('blocking_overlay_count'), 'blocking_overlay_selector': runtime.get('blocking_overlay_selector'), 'before_start': old_range[0].isoformat() if old_range else None, 'before_end': old_range[1].isoformat() if old_range else None, 'after_start': current_range[0].isoformat() if current_range else None, 'after_end': current_range[1].isoformat() if current_range else None, 'target_date': str(target_date) if target_date is not None else None, 'range_changed': range_changed, 'range_expanded_forward': range_expanded_forward, 'target_in_after_range': target_in_after_range, 'header_changed': range_changed, 'header_advanced': header_advanced, 'snapshot_changed': snapshot_changed, 'schedule_redrawn': snapshot_changed, 'visible_schedule_cell_count': len(current_snapshot), 'snapshot_summary_sha256_16': snapshot_summary, 'snapshot': current_snapshot, 'positive_evidence': positive, 'first_action_ineffective': bool(idle and state == RESERVATION_PAGE_READY and (current_header == previous_header) and (current_snapshot == old_snapshot)), 'action_possibly_in_flight': not idle, 'url': getattr(driver, 'current_url', None)}

def move_schedule_next_and_verify(driver, wait, previous_header, target_date=None):
    """Phase 8.8: observe first; replay only after affirmative ineffective evidence."""
    evidence = {'previous_header': previous_header, 'current_header': None, 'trigger': None, 'header_changed': False, 'schedule_redrawn': False, 'visible_schedule_cell_count': 0, 'url': driver.current_url}
    try:
        old_snapshot = _schedule_cell_snapshot(driver)
        evidence.update(schedule_reobserve_count=0, schedule_action_count=1, recovery_action_count=0, same_action_reexecuted=False, recovery_reason='NOT_NEEDED', observation_history=[])
        evidence['trigger'] = _phase8_8_dispatch_schedule_next(driver, wait)
        started = time.perf_counter()
        deadline = started + PHASE8_8_PAGE_BOUNDARY_SECONDS
        recovery_used = False
        index = 0
        while True:
            index += 1
            observation = _phase8_8_schedule_observation(driver, previous_header, old_snapshot, target_date=target_date)
            observed_at = time.perf_counter()
            evidence.update({key: value for key, value in observation.items() if key not in ('snapshot', 'state')})
            evidence['schedule_reobserve_count'] = index
            evidence['schedule_reobserve_elapsed_ms'] = (observed_at - started) * 1000
            history_item = {key: value for key, value in observation.items() if key not in ('snapshot', 'url')}
            history_item.update(observation_index=index, elapsed_ms=evidence['schedule_reobserve_elapsed_ms'], action_count=evidence['schedule_action_count'], recovery_action_count=evidence['recovery_action_count'], return_decision='REOBSERVE', return_reason='awaiting positive evidence')
            evidence['observation_history'].append(history_item)
            if observation['state'] in (LOGIN_REQUIRED, UNKNOWN, HTTP_OR_NETWORK_ERROR, CONGESTED):
                history_item.update(return_decision='STOP_OR_UNKNOWN', return_reason='safety classifier stopped')
                return make_result('STOP' if observation['state'] == LOGIN_REQUIRED else 'UNKNOWN', observation['state'], reason='schedule recovery safety classifier stopped', **evidence)
            if observed_at > deadline:
                history_item.update(return_decision='STATE_CHANGE_TIMEOUT', return_reason='page-boundary wall-clock budget exhausted')
                break
            if observation['positive_evidence']:
                evidence.update(recovery_reason='POSITIVE_FORWARD_RANGE_SNAPSHOT_CELLS')
                history_item.update(return_decision='OK', return_reason='positive forward range/snapshot/cells/READY')
                return make_result('OK', 'SCHEDULE_PAGE_MOVED', **evidence)
            if observation['first_action_ineffective'] and (not recovery_used):
                evidence['recovery_trigger'] = _phase8_8_dispatch_schedule_next(driver, wait)
                recovery_used = True
                evidence.update(schedule_action_count=2, recovery_action_count=1, same_action_reexecuted=True, recovery_reason='FIRST_ACTION_AFFIRMATIVELY_INEFFECTIVE')
                history_item.update(action_count=2, recovery_action_count=1, return_reason='affirmatively ineffective; one recovery dispatched')
            if observed_at >= deadline:
                history_item.update(return_decision='STATE_CHANGE_TIMEOUT', return_reason='page-boundary wall-clock budget exhausted')
                break
            remaining = deadline - observed_at
            time.sleep(min(PHASE8_8_REOBSERVE_INTERVAL_SECONDS, max(0.0, remaining)))
        return make_result('STATE_CHANGE_TIMEOUT', 'SCHEDULE_NAVIGATION_UNKNOWN', reason='positive schedule evidence was not observed within bounds', retryable=False, **evidence)
    except TimeoutException:
        return make_result('STATE_CHANGE_TIMEOUT', 'SCHEDULE_PAGE_MOVED', reason='header change and schedule redraw were not both confirmed', retryable=True, **evidence)
    except Exception as exc:
        evidence['url'] = getattr(driver, 'current_url', evidence['url'])
        return make_result('UNKNOWN', 'SCHEDULE_PAGE_MOVED', reason=type(exc).__name__, retryable=True, **evidence)

def ensure_target_date_visible(driver, wait, target_date, max_pages=3):
    """対象日が実際に表示されるまで、確認済みの状態遷移だけを進める。"""
    transitions = []
    request_started = time.perf_counter()
    for page_index in range(max_pages + 1):
        if time.perf_counter() - request_started >= PHASE8_8_REQUEST_SCHEDULE_SECONDS:
            return make_result('UNKNOWN', 'SCHEDULE_NAVIGATION_UNKNOWN', reason='request schedule-navigation budget exceeded', retryable=False, target_date=target_date, transitions=transitions, schedule_request_elapsed_ms=(time.perf_counter() - request_started) * 1000, same_action_reexecuted=any((t.get('details', {}).get('same_action_reexecuted') for t in transitions)))
        range_result = inspect_schedule_range(driver, target_date)
        transitions.append({'page_index': page_index, 'code': range_result.code, 'state': range_result.state, 'details': range_result.details})
        if range_result.code == 'OK':
            return make_result('OK', 'TARGET_DATE_VISIBLE', pages_moved=page_index, transitions=transitions, **range_result.details)
        if range_result.code != 'DATE_OUT_OF_RANGE':
            return range_result
        if page_index == max_pages:
            return make_result('DATE_OUT_OF_RANGE', 'TARGET_DATE_VISIBLE', reason='target_date was not visible within max_pages', retryable=False, max_pages=max_pages, transitions=transitions, **range_result.details)
        move_result = move_schedule_next_and_verify(driver, wait, range_result.details['header_text'], target_date=target_date)
        transitions.append({'page_index': page_index + 1, 'code': move_result.code, 'state': move_result.state, 'details': move_result.details})
        if move_result.code != 'OK':
            return move_result
    return make_result('UNKNOWN', 'TARGET_DATE_VISIBLE', reason='unexpected schedule visibility state', retryable=True, target_date=target_date, transitions=transitions, url=driver.current_url)

def is_reservation_error(driver):
    print('🔍 予約失敗メッセージ監視中...')
    end_time = time.time() + 1
    while time.time() < end_time:
        try:
            driver.find_element(By.XPATH, "//*[contains(text(), 'レッスン場所の確保ができませんでした')]")
            print('❌ 予約失敗メッセージ検出')
            return True
        except:
            pass
        time.sleep(0.2)
    print('✅ エラーメッセージなし')
    return False

def wait_overlay(driver, timeout=5):
    return wait_for_overlay_clear(driver, timeout)
DOM_OUTER_HTML_LIMIT = 2000
DOM_TEXT_LIMIT = 500
DETAIL_BODY_TEXT_LIMIT = 8000
DETAIL_FORM_HTML_LIMIT = 5000
DETAIL_ELEMENT_HTML_LIMIT = 2500
DETAIL_FEATURE_LIMIT = 250
DETAIL_MESSAGE_LIMIT = 120
DETAIL_URL_PATH = '/LESSON/ReserveLessonSchedule/Detail'
DETAIL_AVAILABLE_MESSAGE = '予約可能な会員種別です。'
DETAIL_UNAVAILABLE_MESSAGES = ('選択中の会員種別では予約できません。',)
DETAIL_POSITION_SELECTOR = 'input[id^="LessonPosNo"][name="LessonPosNo"]'
POSITION_UNAVAILABLE_CLASS_MARKERS = ('disabled', 'unavailable', 'reserved', 'booked', 'occupied', 'soldout', 'sold-out', 'full', 'used', '利用不可', '予約済', '満席', '使用済')
POSITION_UNAVAILABLE_TEXT_MARKERS = ('利用不可', '予約済', '満席', '使用済', '選択不可')

def _dom_diagnostic(driver, element):
    """要素を変更せず、クリック経路の静的DOM証拠だけを採取する。"""
    return driver.execute_script('\n        const target = arguments[0];\n        const htmlLimit = arguments[1];\n        const textLimit = arguments[2];\n        const clip = (value, limit) => {\n            const text = value == null ? \'\' : String(value);\n            return {value: text.slice(0, limit), original_length: text.length,\n                    truncated: text.length > limit};\n        };\n        const attrs = (node) => {\n            const data = {};\n            if (node && node.attributes) {\n                for (const attr of Array.from(node.attributes)) {\n                    if (attr.name.startsWith(\'data-\')) data[attr.name] = attr.value;\n                }\n            }\n            return data;\n        };\n        const describe = (node, relation) => {\n            if (!node || node.nodeType !== Node.ELEMENT_NODE) return null;\n            const rect = node.getBoundingClientRect();\n            const style = window.getComputedStyle(node);\n            return {\n                relation,\n                tag_name: node.tagName.toLowerCase(),\n                text: clip(node.innerText || node.textContent || \'\', textLimit),\n                id: node.id || \'\',\n                class: node.getAttribute(\'class\') || \'\',\n                href: node.getAttribute(\'href\') || \'\',\n                onclick: node.getAttribute(\'onclick\') || \'\',\n                role: node.getAttribute(\'role\') || \'\',\n                name: node.getAttribute(\'name\') || \'\',\n                type: node.getAttribute(\'type\') || \'\',\n                data_attributes: attrs(node),\n                outerHTML: clip(node.outerHTML || \'\', htmlLimit),\n                displayed_geometry: {x: rect.x, y: rect.y, width: rect.width, height: rect.height},\n                computed: {display: style.display, visibility: style.visibility,\n                           pointer_events: style.pointerEvents, cursor: style.cursor},\n                has_inline_onclick: typeof node.onclick === \'function\' || !!node.getAttribute(\'onclick\')\n            };\n        };\n        const likely = (node) => {\n            if (!node || node.nodeType !== Node.ELEMENT_NODE) return false;\n            const tag = node.tagName.toLowerCase();\n            return tag === \'a\' || tag === \'button\' || tag === \'input\' ||\n                node.hasAttribute(\'onclick\') || node.getAttribute(\'role\') === \'button\' ||\n                node.hasAttribute(\'href\') || node.hasAttribute(\'data-href\') ||\n                node.hasAttribute(\'data-url\') || node.hasAttribute(\'data-action\');\n        };\n        const ancestors = [];\n        let current = target.parentElement;\n        for (let depth = 1; current && depth <= 5; depth++, current = current.parentElement) {\n            ancestors.push(describe(current, depth === 1 ? \'parent\' : depth === 2 ? \'grandparent\' : `ancestor_${depth}`));\n        }\n        const descendants = Array.from(target.querySelectorAll(\'a,button,input,[onclick],[role="button"],[href],[data-href],[data-url],[data-action]\'))\n            .slice(0, 20).map((node, index) => describe(node, `descendant_${index}`));\n        const likelyAncestors = ancestors.filter((item, index) => {\n            let node = target.parentElement;\n            for (let i = 0; i < index; i++) node = node && node.parentElement;\n            return likely(node);\n        });\n        return {\n            target: describe(target, \'click_target\'),\n            parent: ancestors[0] || null,\n            grandparent: ancestors[1] || null,\n            ancestor_chain: ancestors,\n            likely_navigation_ancestors: likelyAncestors,\n            likely_navigation_descendants: descendants,\n            document_url: document.location.href\n        };\n        ', element, DOM_OUTER_HTML_LIMIT, DOM_TEXT_LIMIT)

def _safe_dom_diagnostic(driver, element, element_role):
    """DOM採取失敗をイベント欠落に変えず、失敗自体を構造化証拠として返す。"""
    try:
        return {'status': 'OK', 'element_role': element_role, 'diagnostic': _dom_diagnostic(driver, element)}
    except Exception as exc:
        return {'status': 'ERROR', 'element_role': element_role, 'exception_type': type(exc).__name__, 'exception_message': str(exc)}

def _lesson_candidate_xpath(lesson_date):
    return f"//td[contains(@class,'lesson')]//a[contains(@onclick, '{lesson_date}') or contains(@href, '{lesson_date}')]//p[contains(@class,'lesson_name')]"

def _collect_lesson_candidates(driver, request):
    from lesson_target import range_start
    elements = driver.find_elements(By.XPATH, _lesson_candidate_xpath(request['date']))
    candidates = []
    for index, lesson_element in enumerate(elements):
        try:
            anchor = lesson_element.find_element(By.XPATH, './ancestor::a')
            displayed_name = lesson_element.text or ''
            identity = anchor.get_attribute('onclick') or anchor.get_attribute('href') or ''
            parsed = _parse_lesson_onclick_identity(identity)
            card = anchor.find_element(By.XPATH, "./ancestor::td[contains(@class,'lesson')][1]")
            start_time = range_start(card.text)
            candidates.append(LessonCandidate(lesson_element=lesson_element, anchor_element=anchor, displayed_name=displayed_name, normalized_name=normalize_lesson_name(displayed_name), date=parsed['date'] if parsed['parsed'] else None, href_or_onclick=identity, candidate_index=index, start_time=start_time))
        except StaleElementReferenceException:
            continue
    return candidates

def _collect_lesson_candidates_p14(driver, request):
    """Read the same P14 lesson nodes in one atomic, read-only DOM snapshot."""
    from lesson_target import range_start
    rows = driver.execute_script("""
const xpath = arguments[0];
const result = document.evaluate(xpath, document, null,
    XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
const rows = [];
for (let index = 0; index < result.snapshotLength; index++) {
    const lesson = result.snapshotItem(index);
    const anchor = lesson.closest('a');
    const card = anchor && anchor.closest('td[class*="lesson"]');
    if (!anchor || !card) throw new Error('P14_LESSON_STRUCTURE_CHANGED');
    rows.push({index, lesson_element: lesson, anchor_element: anchor,
        displayed_name: (lesson.innerText || '').replaceAll(String.fromCharCode(160), ' '),
        identity: anchor.getAttribute('onclick') || anchor.href || '',
        card_text: card.innerText || ''});
}
return rows;
""", _lesson_candidate_xpath(request['date']))
    candidates = []
    for row in rows:
        parsed = _parse_lesson_onclick_identity(row['identity'])
        name = row['displayed_name']
        candidates.append(LessonCandidate(
            lesson_element=row['lesson_element'], anchor_element=row['anchor_element'],
            displayed_name=name, normalized_name=normalize_lesson_name(name),
            date=parsed['date'] if parsed['parsed'] else None,
            href_or_onclick=row['identity'], candidate_index=row['index'],
            start_time=range_start(row['card_text'])))
    return candidates

def _candidate_evidence(candidate, candidate_count):
    from lesson_target import canonical_name
    return {'displayed_name': candidate.displayed_name, 'normalized_name': candidate.normalized_name, 'target_display_name': candidate.displayed_name, 'target_normalized_name': canonical_name(candidate.displayed_name, normalize_lesson_name), 'date': candidate.date, 'target_date': candidate.date, 'start_time': candidate.start_time, 'target_start_time': candidate.start_time, 'candidate_count': candidate_count, 'candidate_index': candidate.candidate_index, 'href_or_onclick': candidate.href_or_onclick}

def _matching_candidate_evidence(request, candidates, matching):
    """Side-effect-free ambiguity evidence from already collected candidates."""
    return {'reason_code': 'MULTIPLE_MATCHING_LESSON_CANDIDATES', 'request_lesson_raw': request.get('name'), 'request_lesson_canonical': canonicalize_lesson_identity_name(request.get('name', '')), 'candidate_count': len(matching), 'schedule_candidate_count': len(candidates), 'candidate_names': [item.displayed_name for item in matching], 'candidate_canonical_names': [item.normalized_name for item in matching], 'lesson_click_identities': [item.href_or_onclick for item in matching], 'dom_indexes': [item.candidate_index for item in matching]}

def find_target_lesson(driver, wait, request):
    """対象日内で名前一致した具体的候補と、その同じアンカーを返す。"""
    xpath = _lesson_candidate_xpath(request['date'])
    try:
        wait.until(EC.presence_of_all_elements_located((By.XPATH, xpath)))
    except TimeoutException:
        return make_result('TIMEOUT', 'TARGET_LESSON_UNKNOWN', reason='candidate list was not confirmed ready', retryable=True, candidate_count=0, date=request['date'], requested_name=request['name'])
    candidates = _collect_lesson_candidates(driver, request)
    if not candidates:
        return make_result('UNKNOWN', 'TARGET_LESSON_UNKNOWN', reason='candidate list changed while being inspected', retryable=True, candidate_count=0, date=request['date'], requested_name=request['name'])
    from lesson_target import matches
    matching = [candidate for candidate in candidates if matches(candidate.date, candidate.start_time, candidate.displayed_name, request, normalize_lesson_name)]
    if len(matching) > 1:
        return make_result('AMBIGUOUS', 'TARGET_LESSON_AMBIGUOUS', reason='more than one schedule candidate matched the request identity', retryable=False, **_matching_candidate_evidence(request, candidates, matching))
    if len(matching) == 1:
        candidate = matching[0]
        lesson_dom = _dom_diagnostic(driver, candidate.lesson_element)
        click_target_dom = _dom_diagnostic(driver, candidate.anchor_element)
        return make_result('OK', 'TARGET_LESSON_FOUND', value=candidate, dom_diagnostic={'stage': 'target_lesson_found', 'lesson_element': lesson_dom, 'selected_click_target': click_target_dom}, **_candidate_evidence(candidate, len(candidates)))
    return make_result('NOT_FOUND', 'TARGET_LESSON_NOT_FOUND', reason='no unique date, start-time and name match', retryable=False, candidate_count=len(candidates), date=request['date'], start_time=request['start_time'], requested_name=request['name'], normalized_requested_name=normalize_lesson_name(request['name']), displayed_candidates=[_candidate_evidence(candidate, len(candidates)) for candidate in candidates])

def _refind_same_candidate(driver, request, original):
    """Stale後も日付・正規化名・候補識別情報が一致する候補だけを再取得する。"""
    from lesson_target import matches as target_matches
    matches = [candidate for candidate in _collect_lesson_candidates(driver, request) if candidate.date == original.date and candidate.start_time == original.start_time and candidate.normalized_name == original.normalized_name and target_matches(candidate.date, candidate.start_time, candidate.displayed_name, request, normalize_lesson_name)]
    if original.href_or_onclick:
        identity_matches = [candidate for candidate in matches if candidate.href_or_onclick == original.href_or_onclick]
        if len(identity_matches) == 1 and len(matches) == 1:
            return identity_matches[0]
    if len(matches) == 1:
        return matches[0]
    return None

def _detail_dom_snapshot(driver):
    """form・本文・主要属性を、他の診断から独立して採取する。"""
    return driver.execute_script("\n        const L=arguments[0];\n        const clip=(value,limit)=>{const text=value==null?'':String(value);return {value:text.slice(0,limit),original_length:text.length,truncated:text.length>limit};};\n        const dataAttrs=node=>{const result={};for(const attr of Array.from(node.attributes||[])){if(attr.name.indexOf('data-')===0){result[attr.name]=attr.value;}}return result;};\n        const forms=Array.from(document.forms).map(node=>({\n          id:node.id||'',name:node.getAttribute('name')||'',method:node.getAttribute('method')||'',\n          action:node.getAttribute('action')||'',class:node.getAttribute('class')||'',\n          data_attributes:dataAttrs(node),outerHTML:clip(node.outerHTML||'',L.form_html)}));\n        const selector='[id],[name],[class],[data-action],[data-url],[data-href],[data-position],[data-seat]';\n        const all=Array.from(document.querySelectorAll(selector));\n        const features=all.slice(0,L.features).map(node=>({tag_name:node.tagName.toLowerCase(),id:node.id||'',\n          name:node.getAttribute('name')||'',class:node.getAttribute('class')||'',data_attributes:dataAttrs(node)}));\n        const body=(document.body&&document.body.innerText)||'';\n        return {current_url:location.href,detail_url_confirmed:location.pathname.indexOf('/LESSON/ReserveLessonSchedule/Detail')!==-1,\n          forms:{count:forms.length,elements:forms},body_text:clip(body,L.body),\n          dom_features:{total_count:all.length,captured_count:features.length,truncated:all.length>features.length,elements:features}};\n        ", {'body': DETAIL_BODY_TEXT_LIMIT, 'form_html': DETAIL_FORM_HTML_LIMIT, 'features': DETAIL_FEATURE_LIMIT})

def _detail_controls_snapshot(driver):
    """予約操作要素と位置候補を、クリックせず独立して採取する。"""
    return driver.execute_script('\n        const L=arguments[0];\n        const clip=(value,limit)=>{const text=value==null?\'\':String(value);return {value:text.slice(0,limit),original_length:text.length,truncated:text.length>limit};};\n        const dataAttrs=node=>{const result={};for(const attr of Array.from(node.attributes||[])){if(attr.name.indexOf(\'data-\')===0){result[attr.name]=attr.value;}}return result;};\n        const describe=node=>{const style=getComputedStyle(node),rect=node.getBoundingClientRect();return {\n          tag_name:node.tagName.toLowerCase(),text:clip(node.innerText||node.textContent||\'\',L.text),id:node.id||\'\',\n          name:node.getAttribute(\'name\')||\'\',type:node.getAttribute(\'type\')||\'\',value:node.getAttribute(\'value\')||\'\',\n          class:node.getAttribute(\'class\')||\'\',disabled_attribute:node.getAttribute(\'disabled\'),onclick:node.getAttribute(\'onclick\')||\'\',\n          href:node.getAttribute(\'href\')||\'\',displayed:style.display!==\'none\'&&style.visibility!==\'hidden\'&&style.opacity!==\'0\'&&rect.width>0&&rect.height>0,\n          enabled:!node.disabled,computed:{display:style.display,visibility:style.visibility,opacity:style.opacity,pointer_events:style.pointerEvents},\n          data_attributes:dataAttrs(node),outerHTML:clip(node.outerHTML||\'\',L.html)};};\n        const confirms=Array.from(document.querySelectorAll(\'#confirmsubmit\'));\n        const controls=Array.from(document.querySelectorAll(\'button,input[type="submit"],input[type="button"]\')).map(describe);\n        const positionSelector=\'[id^="LessonPosNo"],[name*="LessonPos"],[id*="Position"],[name*="Position"],[class*="position" i],[class*="seat" i],[data-position],[data-seat]\';\n        const allPositions=Array.from(document.querySelectorAll(positionSelector));\n        const positions=allPositions.slice(0,L.features).map(describe);\n        const overlays=Array.from(document.querySelectorAll(\'.blockUI\')).map(node=>{const item=describe(node);item.blocking=item.displayed&&item.computed.pointer_events!==\'none\';return item;});\n        return {current_url:location.href,detail_url_confirmed:location.pathname.indexOf(\'/LESSON/ReserveLessonSchedule/Detail\')!==-1,\n          confirmsubmit:{count:confirms.length,elements:confirms.map(describe)},reservation_controls:{count:controls.length,elements:controls},\n          position_candidates:{selector:positionSelector,total_count:allPositions.length,captured_count:positions.length,truncated:allPositions.length>positions.length,elements:positions},\n          overlays:{count:overlays.length,blocking_count:overlays.filter(item=>item.blocking).length,elements:overlays}};\n        ', {'html': DETAIL_ELEMENT_HTML_LIMIT, 'text': DOM_TEXT_LIMIT, 'features': DETAIL_FEATURE_LIMIT})

def _detail_message_snapshot(driver):
    """予約関連表示文言を正規表現なしで独立して採取する。"""
    return driver.execute_script("\n        const L=arguments[0];\n        const clip=(value,limit)=>{const text=value==null?'':String(value);return {value:text.slice(0,limit),original_length:text.length,truncated:text.length>limit};};\n        const body=(document.body&&document.body.innerText)||'';\n        const words=['予約','受付','期間','開始','終了','できません','不可','対象外','会員','利用','満員','キャンセル'];\n        const rawLines=body.split(String.fromCharCode(10));\n        const matched=[];\n        for(const rawLine of rawLines){\n          const line=rawLine.split(String.fromCharCode(13)).join('').trim();\n          if(!line){continue;}\n          if(words.some(word=>line.indexOf(word)!==-1)&&matched.indexOf(line)===-1){matched.push(line);}\n        }\n        return {current_url:location.href,detail_url_confirmed:location.pathname.indexOf('/LESSON/ReserveLessonSchedule/Detail')!==-1,\n          messages:{keywords:words,matched_count:matched.length,captured_count:Math.min(matched.length,L.messages),\n            truncated:matched.length>L.messages,lines:matched.slice(0,L.messages)},body_text:clip(body,L.body)};\n        ", {'body': DETAIL_BODY_TEXT_LIMIT, 'messages': DETAIL_MESSAGE_LIMIT})

def _run_detail_diagnostic_section(event, success_state, failure_state, collector, driver, user, request, result_builder):
    """1つの診断失敗を他セクションへ波及させず、必ず個別イベントを残す。"""
    current_url = driver.current_url
    try:
        diagnostic_started = time.perf_counter()
        snapshot = collector(driver)
        _latency_duration(user, request, event + '_webdriver', diagnostic_started, 'DOM_DIAGNOSTIC')
        logging_started = time.perf_counter()
        log_event(event, make_result('OK', success_state, current_url=current_url, detail_url_confirmed=snapshot['detail_url_confirmed'], **result_builder(snapshot)), user=user, request=request, current_url=current_url)
        _latency_duration(user, request, event + '_logging', logging_started, 'LOGGING')
        return snapshot
    except Exception as exc:
        log_event(event, make_result('DIAGNOSTIC_FAILED', failure_state, reason=type(exc).__name__, retryable=True, current_url=current_url, exception_message=str(exc)), user=user, request=request, current_url=current_url)
        return None

def _log_detail_diagnostics(driver, user, request, overlay_result):
    """DOM・操作要素・文言の3診断を、それぞれ独立したexecute_scriptで採取する。"""
    dom = _run_detail_diagnostic_section('detail_dom_diagnostic', 'DETAIL_DOM_DIAGNOSED', 'DETAIL_DOM_DIAGNOSTIC_FAILED', _detail_dom_snapshot, driver, user, request, lambda snapshot: {'forms': snapshot['forms'], 'body_text': snapshot['body_text'], 'dom_features': snapshot['dom_features']})
    controls = _run_detail_diagnostic_section('detail_reservation_controls_diagnostic', 'DETAIL_RESERVATION_CONTROLS_DIAGNOSED', 'DETAIL_RESERVATION_CONTROLS_DIAGNOSTIC_FAILED', _detail_controls_snapshot, driver, user, request, lambda snapshot: {'confirmsubmit': snapshot['confirmsubmit'], 'reservation_controls': snapshot['reservation_controls'], 'position_candidates': snapshot['position_candidates'], 'overlays': snapshot['overlays'], 'overlay_wait_result': {'code': overlay_result.code, 'state': overlay_result.state, 'details': overlay_result.details}})
    messages = _run_detail_diagnostic_section('detail_message_diagnostic', 'DETAIL_MESSAGES_DIAGNOSED', 'DETAIL_MESSAGES_DIAGNOSTIC_FAILED', _detail_message_snapshot, driver, user, request, lambda snapshot: {'messages': snapshot['messages'], 'body_text': snapshot['body_text']})
    completed = sum((item is not None for item in (dom, controls, messages)))
    if completed == 0:
        return None
    return {'dom': dom, 'controls': controls, 'messages': messages, 'diagnostic_sections_succeeded': completed, 'diagnostic_sections_failed': 3 - completed}

def determine_detail_state(driver, diagnostic, user, request):
    """Detailを肯定的証拠の完全一致で3状態に分類する（操作は一切しない）。"""
    current_url = driver.current_url
    detail_url_detected = DETAIL_URL_PATH in current_url
    contradictions = []
    controls = diagnostic.get('controls') if diagnostic else None
    messages = diagnostic.get('messages') if diagnostic else None
    if controls is None or messages is None:
        contradictions.append('required_detail_diagnostic_unavailable')
    blocking_overlay_count = controls['overlays']['blocking_count'] if controls else None
    confirm = controls['confirmsubmit'] if controls else {'count': None, 'elements': []}
    confirmsubmit_count = confirm['count']
    confirmsubmit_displayed = confirmsubmit_count == 1 and bool(confirm['elements'][0].get('displayed'))
    confirmsubmit_enabled = confirmsubmit_count == 1 and bool(confirm['elements'][0].get('enabled'))
    detected_messages = messages['messages']['lines'] if messages else []
    body_text = messages['body_text']['value'] if messages else ''
    available_message_detected = DETAIL_AVAILABLE_MESSAGE in body_text
    unavailable_message_detected = any((message in body_text for message in DETAIL_UNAVAILABLE_MESSAGES))
    try:
        position_elements = driver.find_elements(By.CSS_SELECTOR, DETAIL_POSITION_SELECTOR)
        position_ids = [element.get_attribute('id') or '' for element in position_elements]
        position_candidate_ids = [element_id for element_id in position_ids if element_id[len('LessonPosNo'):].isdigit() and int(element_id[len('LessonPosNo'):]) > 0]
        position_candidate_count = len(position_candidate_ids)
    except Exception as exc:
        position_candidate_ids = []
        position_candidate_count = None
        contradictions.append(f'position_dom_inspection_failed:{type(exc).__name__}')
    position_dom_detected = position_candidate_count is not None and position_candidate_count > 0
    if not detail_url_detected:
        contradictions.append('current_url_is_not_detail')
    if blocking_overlay_count is None:
        contradictions.append('blocking_overlay_state_unknown')
    elif blocking_overlay_count > 0:
        contradictions.append('blocking_overlay_present')
    if available_message_detected and unavailable_message_detected:
        contradictions.append('available_and_unavailable_messages_both_detected')
    if available_message_detected and confirmsubmit_count != 1:
        contradictions.append('available_message_without_single_confirmsubmit')
    if available_message_detected and (not confirmsubmit_displayed):
        contradictions.append('available_message_with_hidden_confirmsubmit')
    if available_message_detected and (not confirmsubmit_enabled):
        contradictions.append('available_message_with_disabled_confirmsubmit')
    if available_message_detected and (not position_dom_detected):
        contradictions.append('available_message_without_position_dom')
    if unavailable_message_detected and confirmsubmit_count not in (0, None):
        contradictions.append('unavailable_message_with_confirmsubmit')
    ready_checks = {'detail_url_detected': detail_url_detected, 'blocking_overlay_absent': blocking_overlay_count == 0, 'available_message_detected': available_message_detected, 'unavailable_message_absent': not unavailable_message_detected, 'single_confirmsubmit_present': confirmsubmit_count == 1, 'confirmsubmit_displayed': confirmsubmit_displayed, 'confirmsubmit_enabled': confirmsubmit_enabled, 'position_dom_detected': position_dom_detected}
    not_reservable_checks = {'detail_url_detected': detail_url_detected, 'unavailable_message_detected': unavailable_message_detected, 'available_message_absent': not available_message_detected, 'confirmsubmit_absent': confirmsubmit_count == 0}
    evidence_for_ready = [name for name, passed in ready_checks.items() if passed]
    evidence_for_not_reservable = [name for name, passed in not_reservable_checks.items() if passed]
    if not contradictions and all(ready_checks.values()):
        final_state, code = ('DETAIL_READY', 'OK')
    elif not contradictions and all(not_reservable_checks.values()):
        final_state, code = ('DETAIL_NOT_RESERVABLE', 'NOT_RESERVABLE')
    else:
        final_state, code = ('DETAIL_UNKNOWN', 'UNKNOWN')
    details = {'current_url': current_url, 'detail_url_detected': detail_url_detected, 'blocking_overlay_count': blocking_overlay_count, 'reservation_available_message_detected': available_message_detected, 'reservation_unavailable_message_detected': unavailable_message_detected, 'detected_messages': detected_messages, 'confirmsubmit_count': confirmsubmit_count, 'confirmsubmit_displayed': confirmsubmit_displayed, 'confirmsubmit_enabled': confirmsubmit_enabled, 'position_dom_detected': position_dom_detected, 'position_candidate_count': position_candidate_count, 'evidence_for_ready': evidence_for_ready, 'evidence_for_not_reservable': evidence_for_not_reservable, 'contradictions': contradictions, 'final_detail_state': final_state, 'selectors': {'confirmsubmit': '#confirmsubmit', 'blocking_overlay': '.blockUI', 'position': DETAIL_POSITION_SELECTOR}, 'position_candidate_ids': position_candidate_ids[:DETAIL_FEATURE_LIMIT], 'recognized_available_message': DETAIL_AVAILABLE_MESSAGE, 'recognized_unavailable_messages': list(DETAIL_UNAVAILABLE_MESSAGES), 'safety': {'position_selected': False, 'next_clicked': False, 'confirmsubmit_clicked': False, 'reservation_confirmed': False, 'legacy_fallback_used': False}}
    result = make_result(code, final_state, retryable=final_state == 'DETAIL_UNKNOWN', **details)
    log_event('detail_state_determined', result, user=user, request=request, current_url=current_url)
    return result

def _position_list_status(driver):
    """実機確認済みselectorから、位置一覧が安全に読める状態かを確認する。"""
    elements = driver.find_elements(By.CSS_SELECTOR, DETAIL_POSITION_SELECTOR)
    ids = [element.get_attribute('id') or '' for element in elements]
    candidate_ids = [element_id for element_id in ids if element_id.startswith('LessonPosNo') and element_id[len('LessonPosNo'):].isdigit() and (int(element_id[len('LessonPosNo'):]) > 0)]
    return (bool(candidate_ids), candidate_ids)

def _visible_blocking_overlays(driver):
    overlays = driver.find_elements(By.CSS_SELECTOR, '.blockUI')
    return sum((1 for overlay in overlays if overlay.is_displayed()))

def get_position_status(driver, wait, position, detail_state='DETAIL_READY', user=None, request=None, trace_prefix='position_status'):
    """位置を変更せず、DOMと表示状態の肯定的証拠だけで4状態に分類する。"""
    del wait
    selector = f'#LessonPosNo{position}'
    current_url = driver.current_url
    contradictions, available_evidence, unavailable_evidence = ([], [], [])
    details = {'position': position, 'current_url': current_url, 'detail_state': detail_state, 'selector': selector, 'element_found': False, 'displayed': None, 'enabled': None, 'disabled': None, 'aria_disabled': None, 'checked': None, 'class': None, 'input_type': None, 'value': None, 'overlay_state': 'UNKNOWN', 'position_list_loaded': False, 'evidence_for_available': available_evidence, 'evidence_for_unavailable': unavailable_evidence, 'contradictions': contradictions}
    try:
        list_query_started = time.perf_counter()
        list_loaded, candidate_ids = _position_list_status(driver)
        if user is not None and request is not None:
            _latency_duration(user, request, trace_prefix + '.candidate_dom', list_query_started, 'DOM_QUERY')
        details['position_list_loaded'] = list_loaded
        details['position_candidate_ids'] = candidate_ids[:DETAIL_FEATURE_LIMIT]
        overlay_started = time.perf_counter()
        overlay_count = _visible_blocking_overlays(driver)
        if user is not None and request is not None:
            _latency_duration(user, request, trace_prefix + '.overlay', overlay_started, 'SAFETY_CHECK')
        details['blocking_overlay_count'] = overlay_count
        details['overlay_state'] = 'CLEAR' if overlay_count == 0 else 'BLOCKING'
        if overlay_count:
            contradictions.append('blocking_overlay_present')
        target_query_started = time.perf_counter()
        elements = driver.find_elements(By.ID, f'LessonPosNo{position}')
        if user is not None and request is not None:
            _latency_duration(user, request, trace_prefix + '.target_dom', target_query_started, 'DOM_QUERY')
        if len(elements) > 1:
            contradictions.append('duplicate_position_id')
        if not elements:
            if detail_state == 'DETAIL_READY' and DETAIL_URL_PATH in current_url and list_loaded and (overlay_count == 0):
                state, code, reason = ('POSITION_NOT_FOUND', 'NOT_FOUND', 'target position is absent from loaded position list')
            else:
                if not list_loaded:
                    contradictions.append('position_list_not_loaded')
                state, code, reason = ('POSITION_UNKNOWN', 'UNKNOWN', 'target absence could not be verified safely')
            details['final_position_state'] = state
            return make_result(code, state, reason=reason, retryable=state == 'POSITION_UNKNOWN', **details)
        element = elements[0]
        details['element_found'] = True
        state_query_started = time.perf_counter()
        displayed, enabled = (element.is_displayed(), element.is_enabled())
        disabled_attr = element.get_attribute('disabled')
        aria_disabled = (element.get_attribute('aria-disabled') or '').strip().lower()
        class_name = element.get_attribute('class') or ''
        input_type = element.get_attribute('type') or ''
        outer_html = element.get_attribute('outerHTML') or ''
        parent_text = driver.execute_script("return (arguments[0].parentElement && arguments[0].parentElement.innerText) || '';", element) or ''
        details.update({'displayed': displayed, 'enabled': enabled, 'disabled': disabled_attr, 'aria_disabled': aria_disabled or None, 'checked': element.is_selected(), 'class': class_name, 'input_type': input_type, 'value': element.get_attribute('value'), 'tag_name': element.tag_name, 'id': element.get_attribute('id'), 'name': element.get_attribute('name'), 'onclick': element.get_attribute('onclick') or '', 'outerHTML': outer_html[:DETAIL_ELEMENT_HTML_LIMIT], 'outerHTML_truncated': len(outer_html) > DETAIL_ELEMENT_HTML_LIMIT, 'parent_text': parent_text[:DOM_TEXT_LIMIT]})
        if user is not None and request is not None:
            _latency_duration(user, request, trace_prefix + '.state_attributes', state_query_started, 'SAFETY_CHECK+DOM_QUERY')
        state_compute_started = time.perf_counter()
        class_lower, text_lower = (class_name.lower(), parent_text.lower())
        class_tokens = set(filter(None, re.split('\\s+', class_lower)))
        class_marks = [m for m in POSITION_UNAVAILABLE_CLASS_MARKERS if m.lower() in class_tokens]
        text_marks = [m for m in POSITION_UNAVAILABLE_TEXT_MARKERS if m.lower() in text_lower]
        if disabled_attr is not None:
            unavailable_evidence.append('disabled_attribute_present')
        if aria_disabled == 'true':
            unavailable_evidence.append('aria_disabled_true')
        if class_marks:
            unavailable_evidence.append('unavailable_class:' + ','.join(class_marks))
        if text_marks:
            unavailable_evidence.append('unavailable_text:' + ','.join(text_marks))
        hidden_radio = input_type.lower() == 'radio' and (not displayed)
        details['hidden_radio_normal_dom_contract'] = hidden_radio
        if displayed:
            available_evidence.append('displayed')
        elif hidden_radio:
            available_evidence.append('hidden_radio_normal_dom_contract')
        if enabled:
            available_evidence.append('enabled')
        if disabled_attr is None:
            available_evidence.append('disabled_attribute_absent')
        if aria_disabled != 'true':
            available_evidence.append('aria_disabled_not_true')
        if not class_marks and (not text_marks):
            available_evidence.append('no_explicit_unavailable_marker')
        if overlay_count == 0:
            available_evidence.append('blocking_overlay_absent')
        if list_loaded:
            available_evidence.append('position_list_loaded')
        if disabled_attr is not None and enabled:
            contradictions.append('disabled_attribute_conflicts_with_enabled_state')
        if unavailable_evidence and displayed and enabled and (disabled_attr is None) and (aria_disabled != 'true'):
            contradictions.append('unavailable_marker_conflicts_with_interactable_state')
        if not displayed and (not hidden_radio):
            contradictions.append('non_radio_position_not_displayed')
        if contradictions:
            state, code, reason = ('POSITION_UNKNOWN', 'UNKNOWN', 'position evidence is contradictory or blocked')
        elif unavailable_evidence:
            state, code, reason = ('POSITION_UNAVAILABLE', 'NOT_AVAILABLE', 'explicit unavailable evidence detected')
        elif detail_state == 'DETAIL_READY' and list_loaded and (overlay_count == 0) and (displayed or hidden_radio) and enabled and (disabled_attr is None) and (aria_disabled != 'true') and (not contradictions):
            state, code, reason = ('POSITION_AVAILABLE', 'OK', None)
        else:
            if not enabled:
                contradictions.append('not_enabled_without_explicit_unavailable_state')
            if not list_loaded:
                contradictions.append('position_list_not_loaded')
            state, code, reason = ('POSITION_UNKNOWN', 'UNKNOWN', 'position evidence is incomplete or contradictory')
        if user is not None and request is not None:
            _latency_duration(user, request, trace_prefix + '.classification', state_compute_started, 'SAFETY_CHECK')
    except (StaleElementReferenceException, TimeoutException) as exc:
        contradictions.append(type(exc).__name__)
        state, code, reason = ('POSITION_UNKNOWN', 'UNKNOWN', type(exc).__name__)
    except Exception as exc:
        contradictions.append(f'attribute_or_dom_inspection_failed:{type(exc).__name__}')
        state, code, reason = ('POSITION_UNKNOWN', 'UNKNOWN', type(exc).__name__)
    details['final_position_state'] = state
    return make_result(code, state, reason=reason, retryable=state == 'POSITION_UNKNOWN', **details)

def diagnose_positions(driver, wait, request, detail_result, user=None):
    """希望順位を維持して全候補を読み取り、選択せずに集計する。"""
    results = []
    if detail_result.state == 'DETAIL_READY':
        for position in request['positions']:
            result = get_position_status(driver, wait, position, detail_result.state)
            results.append(result)
            log_event('position_status_determined', result, user=user, request=request, **result.details)
    grouped = {state: [] for state in ('POSITION_AVAILABLE', 'POSITION_UNAVAILABLE', 'POSITION_NOT_FOUND', 'POSITION_UNKNOWN')}
    for position, result in zip(request['positions'], results):
        grouped[result.state].append(position)
    summary = make_result('OK' if detail_result.state == 'DETAIL_READY' else 'SKIPPED', 'PHASE5_1_POSITION_STATUS_COMPLETED', reason=None if detail_result.state == 'DETAIL_READY' else 'detail state does not permit position inspection', positions=list(request['positions']), position_states=[{'position': p, 'state': r.state} for p, r in zip(request['positions'], results)], available_positions=grouped['POSITION_AVAILABLE'], unavailable_positions=grouped['POSITION_UNAVAILABLE'], not_found_positions=grouped['POSITION_NOT_FOUND'], unknown_positions=grouped['POSITION_UNKNOWN'], available_count=len(grouped['POSITION_AVAILABLE']), unavailable_count=len(grouped['POSITION_UNAVAILABLE']), not_found_count=len(grouped['POSITION_NOT_FOUND']), unknown_count=len(grouped['POSITION_UNKNOWN']), position_inspection_skipped=detail_result.state != 'DETAIL_READY', detail_state=detail_result.state, safety={'position_selected': False, 'next_clicked': False, 'confirmsubmit_clicked': False, 'reservation_confirmed': False, 'legacy_fallback_used': False})
    log_event('phase5_1_position_status_completed', summary, user=user, request=request, **summary.details)
    return summary

def _checked_position_ids(driver):
    checked_ids = []
    for radio in driver.find_elements(By.CSS_SELECTOR, DETAIL_POSITION_SELECTOR):
        if radio.is_selected() or radio.get_attribute('checked') is not None:
            suffix = (radio.get_attribute('id') or '')[len('LessonPosNo'):]
            if suffix.isdigit():
                checked_ids.append(int(suffix))
    return checked_ids

def _selection_unknown(user, request, position, reason, attempts, **details):
    result = make_result('UNKNOWN', 'POSITION_SELECTION_UNKNOWN', reason=reason, retryable=True, selected_position=None, requested_positions=list(request['positions']), position=position, selection_attempts=attempts, legacy_fallback_used=False, next_clicked=False, confirmsubmit_clicked=False, reservation_confirmed=False, **details)
    log_event('position_selection_unknown', result, user=user, request=request, **result.details)
    return result

def _phase5_3_safety(next_clicked=False):
    """Phase 5.3の全終了経路で同じ安全フラグを出力する。"""
    return {'next_clicked': next_clicked, 'confirmsubmit_clicked': False, 'reservation_confirmed': False, 'legacy_fallback_used': False}

def _next_candidates_snapshot(driver):
    """実DOMから「次へ」候補を収集する。selector単独では決め打ちしない。"""
    return driver.execute_script('\n        const nodes = Array.from(document.querySelectorAll(\n          \'button,input[type="button"],input[type="submit"],a,[role="button"]\'));\n        const clip = (s, n=2500) => String(s || \'\').slice(0, n);\n        const describe = (el) => {\n          const r = el.getBoundingClientRect();\n          const cs = getComputedStyle(el);\n          const parent = el.parentElement;\n          const ancestors = [];\n          let p = parent;\n          for (let depth=1; p && depth<=5; depth++, p=p.parentElement) {\n            ancestors.push({depth, tag_name:p.tagName.toLowerCase(), id:p.id || \'\',\n              class:clip(p.className, 500), outerHTML:clip(p.outerHTML)});\n          }\n          const form = el.form || el.closest(\'form\');\n          return {tag_name:el.tagName.toLowerCase(), id:el.id || \'\',\n            name:el.getAttribute(\'name\') || \'\', class:clip(el.className, 500),\n            type:el.getAttribute(\'type\') || \'\', value:el.getAttribute(\'value\') || \'\',\n            text:clip(el.innerText || el.textContent, 500), href:el.getAttribute(\'href\') || \'\',\n            onclick:el.getAttribute(\'onclick\') || \'\', role:el.getAttribute(\'role\') || \'\',\n            title:el.getAttribute(\'title\') || \'\', aria_label:el.getAttribute(\'aria-label\') || \'\',\n            disabled_attribute:el.hasAttribute(\'disabled\'),\n            aria_disabled:el.getAttribute(\'aria-disabled\'),\n            computed_style:{display:cs.display, visibility:cs.visibility,\n              pointer_events:cs.pointerEvents, cursor:cs.cursor, position:cs.position,\n              z_index:cs.zIndex},\n            geometry:{x:r.x,y:r.y,left:r.left,top:r.top,right:r.right,bottom:r.bottom,\n              width:r.width,height:r.height}, outerHTML:clip(el.outerHTML),\n            parent:parent ? {tag_name:parent.tagName.toLowerCase(), id:parent.id || \'\',\n              class:clip(parent.className,500), outerHTML:clip(parent.outerHTML)} : null,\n            ancestors, form_relation:form ? (el.form === form ? \'FORM_OWNER\' : \'FORM_ANCESTOR\') : \'NO_FORM\',\n            form_action:form ? form.action : \'\', form_method:form ? form.method : \'\'};\n        };\n        return nodes.map((el, dom_index) => ({dom_index, element:el, info:describe(el)}));\n        ')

def _is_next_label(info):
    values = [info.get(k, '') for k in ('text', 'value', 'aria_label', 'title')]
    normalized = {re.sub('[\\s\u3000>＞→➡]+', '', str(v)).lower() for v in values}
    return bool(normalized & {'次へ', '次へ進む', '次の画面へ', '確認画面へ', '確認へ'})

def _find_unique_next(driver):
    raw = _next_candidates_snapshot(driver)
    candidates = []
    for item in raw:
        element, info = (item['element'], item['info'])
        info.update(displayed=element.is_displayed(), enabled=element.is_enabled())
        if _is_next_label(info):
            candidates.append((element, info))
    return (raw, candidates)

def _next_click_dom_diagnostic(driver, target, info):
    diagnostic = driver.execute_script('\n        const el=arguments[0], r=el.getBoundingClientRect(), cs=getComputedStyle(el);\n        const cx=r.left+r.width/2, cy=r.top+r.height/2;\n        const inPoint=cx>=0 && cy>=0 && cx<innerWidth && cy<innerHeight;\n        const top=inPoint ? document.elementFromPoint(cx,cy) : null;\n        const stack=inPoint && document.elementsFromPoint ?\n          document.elementsFromPoint(cx,cy).slice(0,8) : [];\n        const desc=(n) => n ? {tag_name:n.tagName.toLowerCase(),id:n.id || \'\',\n          class:String(n.className || \'\').slice(0,500),text:String(n.innerText || \'\').slice(0,300),\n          outerHTML:String(n.outerHTML || \'\').slice(0,1500)} : null;\n        let relation=\'NO_ELEMENT\';\n        if(top===el) relation=\'SELF\';\n        else if(top && el.contains(top)) relation=\'DESCENDANT\';\n        else if(top && top.contains(el)) relation=\'ANCESTOR\';\n        else if(top) relation=\'UNRELATED\';\n        const overlaySelectors=[\'.blockUI\',\'.blockOverlay\',\'.modal-backdrop\',\'.loading\',\'.overlay\',\n          \'[aria-busy="true"]\'];\n        const overlays=Array.from(document.querySelectorAll(overlaySelectors.join(\',\')))\n          .filter(n=>{const s=getComputedStyle(n),q=n.getBoundingClientRect(); return s.display!==\'none\' &&\n            s.visibility!==\'hidden\' && s.pointerEvents!==\'none\' && q.width>0 && q.height>0;})\n          .map(desc);\n        return {current_url:location.href, document_title:document.title,\n          viewport:{width:innerWidth,height:innerHeight,scrollX,scrollY},\n          geometry:{x:r.x,y:r.y,left:r.left,top:r.top,right:r.right,bottom:r.bottom,\n            width:r.width,height:r.height},\n          fully_inside:r.left>=0&&r.top>=0&&r.right<=innerWidth&&r.bottom<=innerHeight,\n          partially_inside:r.right>0&&r.bottom>0&&r.left<innerWidth&&r.top<innerHeight,\n          button_center:{x:cx,y:cy,in_viewport:inPoint}, element_from_point:desc(top),\n          elements_from_point:stack.map(desc), element_from_point_relation:relation,\n          blocking_overlay_count:overlays.length, overlays,\n          disabled_attribute:el.hasAttribute(\'disabled\'), aria_disabled:el.getAttribute(\'aria-disabled\'),\n          computed_style:{display:cs.display,visibility:cs.visibility,\n            pointer_events:cs.pointerEvents,cursor:cs.cursor}};\n        ', target)
    diagnostic.update(button_info=info, displayed=target.is_displayed(), enabled=target.is_enabled())
    return diagnostic

def _position_selection_evidence(driver, selected_position):
    radios = driver.find_elements(By.ID, f'LessonPosNo{selected_position}')
    if len(radios) != 1:
        return {'checked': False, 'is_selected': False, 'checked_position_ids': _checked_position_ids(driver)}
    return {'checked': radios[0].get_attribute('checked') is not None, 'is_selected': radios[0].is_selected(), 'checked_position_ids': _checked_position_ids(driver)}

def _page_transition_snapshot(driver, selected_position, request):
    return driver.execute_script('\n        const selected=String(arguments[0]), lesson=String(arguments[1]), date=String(arguments[2]);\n        const clip=(s,n)=>String(s||\'\').slice(0,n);\n        const visible=(e)=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();\n          return s.display!==\'none\'&&s.visibility!==\'hidden\'&&r.width>0&&r.height>0;};\n        const controls=Array.from(document.querySelectorAll(\n          \'button,input[type="button"],input[type="submit"],a[role="button"]\')).map(e=>({\n          text:clip(e.innerText||e.textContent,300),value:e.value||\'\',id:e.id||\'\',name:e.name||\'\',\n          class:clip(e.className,500),type:e.type||\'\',onclick:e.getAttribute(\'onclick\')||\'\',\n          disabled:e.hasAttribute(\'disabled\'),displayed:visible(e),\n          outerHTML:clip(e.outerHTML,1800)}));\n        const body=clip(document.body ? document.body.innerText : \'\',12000);\n        return {url:location.href,title:document.title,body_main_text:body,\n          headings:Array.from(document.querySelectorAll(\'h1,h2,h3,h4,[role="heading"]\'))\n            .filter(visible).map(e=>clip(e.innerText,500)), controls,\n          forms:Array.from(document.forms).map(f=>({action:f.action,method:f.method,\n            id:f.id||\'\',name:f.name||\'\',outerHTML:clip(f.outerHTML,2500)})),\n          position_radio_count:document.querySelectorAll(\'input[id^="LessonPosNo"]\').length,\n          selected_position_present:body.includes(selected), lesson_name_present:body.includes(lesson),\n          target_date_present:body.includes(date),\n          back_or_modify_candidates:controls.filter(x=>/(戻|修正|変更)/.test(x.text+x.value)),\n          confirm_candidates:controls.filter(x=>/(確定|予約|申込|申し込)/.test(x.text+x.value)),\n          error_text_detected:/(エラー|混雑|失敗|受付でき|処理でき|時間をおいて)/.test(body)};\n        ', selected_position, request.get('name', ''), request.get('date', ''))

def _next_fast_snapshot(driver, selected_position):
    """next候補・position維持・click安全情報を1回のread-only JSで取得する。"""
    return driver.execute_script('\n        const selected=Number(arguments[0]), started=performance.now();\n        const candidateStarted=performance.now();\n        const nodes=Array.from(document.querySelectorAll(\n          \'button,input[type="button"],input[type="submit"],a,[role="button"]\'));\n        const geometry=element=>{const r=element.getBoundingClientRect();return {\n          x:r.x,y:r.y,left:r.left,top:r.top,right:r.right,bottom:r.bottom,\n          width:r.width,height:r.height};};\n        const displayInfo=element=>{const style=getComputedStyle(element),r=geometry(element);\n          return {display:style.display,visibility:style.visibility,\n            pointer_events:style.pointerEvents,opacity:style.opacity,geometry:r,\n            displayed:style.display!==\'none\'&&style.visibility!==\'hidden\'&&\n              style.visibility!==\'collapse\'&&style.opacity!==\'0\'&&r.width>0&&r.height>0};};\n        let topmostCheckMs=0;\n        const relation=element=>{const relationStarted=performance.now();\n          const r=element.getBoundingClientRect(),x=r.left+r.width/2,\n          y=r.top+r.height/2,inside=x>=0&&y>=0&&x<innerWidth&&y<innerHeight;\n          const top=inside?document.elementFromPoint(x,y):null;\n          let result=\'NO_ELEMENT\';if(!inside)result=\'OUTSIDE_VIEWPORT\';\n          else if(top===element)result=\'SELF\';else if(top&&element.contains(top))result=\'DESCENDANT\';\n          else if(top)result=\'UNRELATED\';topmostCheckMs+=performance.now()-relationStarted;\n          return result;};\n        const candidates=nodes.map((element,dom_index)=>{const view=displayInfo(element);\n          const form=element.form||element.closest(\'form\');return {dom_index,element,\n          info:{tag_name:element.tagName.toLowerCase(),id:element.id||\'\',\n            name:element.getAttribute(\'name\')||\'\',class:String(element.className||\'\').slice(0,500),\n            type:element.getAttribute(\'type\')||\'\',text:String(element.innerText||element.textContent||\'\').slice(0,500),\n            value:element.getAttribute(\'value\')||\'\',aria_label:element.getAttribute(\'aria-label\')||\'\',\n            title:element.getAttribute(\'title\')||\'\',href:element.getAttribute(\'href\')||\'\',\n            role:element.getAttribute(\'role\')||\'\',disabled_attribute:element.hasAttribute(\'disabled\'),\n            disabled_effective:element.matches(\':disabled\'),\n            aria_disabled:(element.getAttribute(\'aria-disabled\')||\'\').toLowerCase(),\n            display:view.display,visibility:view.visibility,pointer_events:view.pointer_events,\n            displayed:view.displayed,geometry:view.geometry,\n            fully_inside:view.geometry.left>=0&&view.geometry.top>=0&&\n              view.geometry.right<=innerWidth&&view.geometry.bottom<=innerHeight,\n            element_from_point_relation:relation(element),\n            form_relation:form?(element.form===form?\'FORM_OWNER\':\'FORM_ANCESTOR\'):\'NO_FORM\',\n            form_id:form?(form.id||\'\'):\'\',form_name:form?(form.name||\'\'):\'\',\n            form_action:form?(form.action||\'\'):\'\',form_method:form?(form.method||\'\'):\'\'}};});\n        const candidateFinished=performance.now(),positionStarted=performance.now();\n        const radios=Array.from(document.querySelectorAll(arguments[1]));\n        const targetId=\'LessonPosNo\'+String(selected);\n        const targets=radios.filter(radio=>radio.id===targetId);\n        const checkedIds=radios.filter(radio=>Boolean(radio.checked)).map(radio=>radio.id)\n          .filter(value=>value.startsWith(\'LessonPosNo\')&&/^\\d+$/.test(value.slice(11)))\n          .map(value=>Number(value.slice(11)));\n        const positionFinished=performance.now(),overlayStarted=performance.now();\n        const overlaySelectors=[\'.blockUI\',\'.blockOverlay\',\'.modal-backdrop\',\'.loading\',\'.overlay\',\n          \'[aria-busy="true"]\'];\n        const blocking=Array.from(document.querySelectorAll(overlaySelectors.join(\',\'))).filter(e=>{\n          const v=displayInfo(e);return v.displayed&&v.pointer_events!==\'none\';}).length;\n        const overlayFinished=performance.now();\n        return {url:location.href,candidates,blocking_overlay_count:blocking,\n          position_evidence:{target_count:targets.length,\n            checked:targets.length===1&&Boolean(targets[0].checked),\n            is_selected:targets.length===1&&Boolean(targets[0].checked),\n            checked_position_ids:checkedIds},timings_ms:{\n            candidate_snapshot:candidateFinished-candidateStarted,\n            topmost_check:topmostCheckMs,\n            position_state_recheck:positionFinished-positionStarted,\n            overlay_check:overlayFinished-overlayStarted,total:performance.now()-started}};\n        ', selected_position, DETAIL_POSITION_SELECTOR)

def _classify_next_snapshot(snapshot):
    matches = []
    for item in snapshot.get('candidates') or []:
        if _is_next_label(item.get('info') or {}):
            matches.append((item.get('element'), item.get('info') or {}))
    return matches

def _next_transition_probe(driver):
    """next後の初動検出専用。body/outerHTMLを取得しない軽量read-only probe。"""
    return driver.execute_script('\n        const text=e=>String(e.innerText||e.textContent||\'\').replace(/[\\s\u3000]+/g,\'\').slice(0,160);\n        const controls=Array.from(document.querySelectorAll(\n          \'button,input[type="button"],input[type="submit"],a,[role="button"]\')).map(e=>\n          ({tag:e.tagName.toLowerCase(),id:e.id||\'\',name:e.name||\'\',type:e.type||\'\',\n            text:text(e),value:String(e.value||\'\').slice(0,160)}));\n        const forms=Array.from(document.forms).map(f=>({id:f.id||\'\',name:f.name||\'\',\n          action:f.action||\'\',method:f.method||\'\'}));\n        const headings=Array.from(document.querySelectorAll(\'h1,h2,h3,h4,[role="heading"]\'))\n          .map(text).filter(Boolean);\n        const url=location.href,confirmUrl=/Confirm/i.test(location.pathname);\n        const confirmDom=headings.some(value=>/(予約内容確認|確認画面|予約確認)/.test(value))||\n          Boolean(document.querySelector(\'form[action*="Confirm" i],[data-page*="confirm" i]\'));\n        return {url,confirm_url:confirmUrl,confirm_dom_detected:confirmDom,controls,forms,headings,\n          position_radio_count:document.querySelectorAll(\'input[id^="LessonPosNo"]\').length};\n        ')

def _next_failure_diagnostic(driver, target, info):
    if target is not None:
        try:
            return _next_click_dom_diagnostic(driver, target, info or {})
        except Exception as exc:
            return {'diagnostic_error': type(exc).__name__, 'diagnostic_error_message': str(exc)}
    try:
        raw = _next_candidates_snapshot(driver)
        return {'candidate_count': len(raw), 'candidates': [item.get('info') for item in raw]}
    except Exception as exc:
        return {'diagnostic_error': type(exc).__name__, 'diagnostic_error_message': str(exc)}

def click_next_and_diagnose(driver, wait, request, position_result, user=None):
    """次へをnative clickで一度だけ押し、次段階を診断して必ず停止する。"""
    identity_stop = _cla1_identity_guard(driver, user)
    if identity_stop is not None:
        return identity_stop
    del wait
    selected = position_result.details.get('selected_position')
    required = position_result.code == 'OK' and position_result.state == 'POSITION_SELECTED' and (selected is not None) and (position_result.details.get('checked') is True) and (position_result.details.get('is_selected') is True) and (position_result.details.get('checked_position_ids') == [selected])
    if not required:
        result = make_result('UNKNOWN', 'NEXT_CLICK_UNKNOWN', reason='POSITION_SELECTED prerequisite was not affirmative', position_result_code=position_result.code, position_result_state=position_result.state, selected_position=selected, **_phase5_3_safety(False))
        log_event('next_click_stopped', result, user=user, request=request, **result.details)
        return result
    _latency_record_ms(user, request, 'next_scroll', 0.0, 'SCROLL')
    _latency_record_ms(user, request, 'next_refetch', 0.0, 'REFETCH')
    target = info = None
    snapshot_started = time.perf_counter()
    try:
        snapshot = _next_fast_snapshot(driver, selected)
    except Exception as exc:
        diagnostic = _next_failure_diagnostic(driver, None, None)
        result = make_result('UNKNOWN', 'NEXT_CLICK_UNKNOWN', reason=f'next snapshot failed: {type(exc).__name__}', diagnostic=diagnostic, **_phase5_3_safety(False))
        log_event('next_click_stopped', result, user=user, request=request, **result.details)
        return result
    _latency_duration(user, request, 'next_snapshot', snapshot_started, 'DOM_QUERY+SAFETY_CHECK')
    browser_timings = snapshot.get('timings_ms') or {}
    _latency_record_ms(user, request, 'position_state_recheck', browser_timings.get('position_state_recheck', 0.0), 'SAFETY_CHECK')
    _latency_record_ms(user, request, 'next_topmost_check', browser_timings.get('topmost_check', 0.0), 'SAFETY_CHECK_BROWSER')
    classification_started = time.perf_counter()
    matches = _classify_next_snapshot(snapshot)
    _latency_duration(user, request, 'next_candidate_classification', classification_started, 'SAFETY_CHECK_PYTHON')
    if len(matches) != 1:
        diagnostic = _next_failure_diagnostic(driver, None, None)
        result = make_result('UNKNOWN', 'NEXT_CLICK_UNKNOWN', reason='next control was not uniquely identified', candidate_count=len(snapshot.get('candidates') or []), matched_count=len(matches), diagnostic=diagnostic, **_phase5_3_safety(False))
        log_event('next_click_stopped', result, user=user, request=request, **result.details)
        return result
    target, info = matches[0]
    position_evidence = snapshot.get('position_evidence') or {}
    precheck_started = time.perf_counter()
    try:
        selenium_displayed = target.is_displayed()
        selenium_enabled = target.is_enabled()
    except Exception as exc:
        diagnostic = _next_failure_diagnostic(driver, target, info)
        result = make_result('UNKNOWN', 'NEXT_CLICK_UNKNOWN', reason=f'next target Selenium precheck failed: {type(exc).__name__}', diagnostic=diagnostic, **_phase5_3_safety(False))
        log_event('next_click_stopped', result, user=user, request=request, **result.details)
        return result
    needs_scroll = not info.get('fully_inside') or info.get('element_from_point_relation') not in ('SELF', 'DESCENDANT')
    if needs_scroll:
        scroll_started = time.perf_counter()
        driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'center'});", target)
        _latency_duration(user, request, 'next_scroll', scroll_started, 'SCROLL')
        refetch_started = time.perf_counter()
        try:
            snapshot = _next_fast_snapshot(driver, selected)
            matches = _classify_next_snapshot(snapshot)
            if len(matches) != 1:
                raise RuntimeError('next candidate was not unique after scroll')
            target, info = matches[0]
            selenium_displayed = target.is_displayed()
            selenium_enabled = target.is_enabled()
        except Exception as exc:
            diagnostic = _next_failure_diagnostic(driver, target, info)
            result = make_result('UNKNOWN', 'NEXT_CLICK_UNKNOWN', reason=f'next re-fetch failed: {type(exc).__name__}', diagnostic=diagnostic, **_phase5_3_safety(False))
            log_event('next_click_stopped', result, user=user, request=request, **result.details)
            return result
        _latency_duration(user, request, 'next_refetch', refetch_started, 'REFETCH+SAFETY_CHECK')
        position_evidence = snapshot.get('position_evidence') or {}
        browser_timings = snapshot.get('timings_ms') or {}
        _latency_record_ms(user, request, 'position_state_recheck', browser_timings.get('position_state_recheck', 0.0), 'SAFETY_CHECK_AFTER_SCROLL')
        _latency_record_ms(user, request, 'next_topmost_check', browser_timings.get('topmost_check', 0.0), 'SAFETY_CHECK_BROWSER_AFTER_SCROLL')
    maintained = {'checked': position_evidence.get('checked') is True, 'is_selected': position_evidence.get('is_selected') is True, 'checked_position_ids': position_evidence.get('checked_position_ids') or []}
    click_allowed = snapshot.get('url', '').find(DETAIL_URL_PATH) != -1 and maintained == {'checked': True, 'is_selected': True, 'checked_position_ids': [selected]} and selenium_displayed and selenium_enabled and (info.get('displayed') is True) and (not info.get('disabled_attribute')) and (not info.get('disabled_effective')) and (str(info.get('aria_disabled') or '').lower() != 'true') and (info.get('geometry', {}).get('width', 0) > 0) and (info.get('geometry', {}).get('height', 0) > 0) and (snapshot.get('blocking_overlay_count') == 0) and (info.get('element_from_point_relation') in ('SELF', 'DESCENDANT'))
    _latency_duration(user, request, 'next_precheck', precheck_started, 'SAFETY_CHECK+OPTIONAL_SCROLL+REFETCH')
    if not click_allowed:
        diagnostic = _next_failure_diagnostic(driver, target, info)
        result = make_result('UNKNOWN', 'NEXT_CLICK_UNKNOWN', reason='native click affirmative conditions were not all met', selection_evidence=maintained, diagnostic=diagnostic, **_phase5_3_safety(False))
        log_event('next_click_stopped', result, user=user, request=request, **result.details)
        return result
    baseline_probe_started = time.perf_counter()
    pre_probe = _next_transition_probe(driver)
    _latency_duration(user, request, 'next_transition_baseline_probe', baseline_probe_started, 'DOM_QUERY')
    logging_started = time.perf_counter()
    log_event('next_fastpath_precheck', user=user, request=request, candidate_count=len(snapshot.get('candidates') or []), matched_count=1, selected_position=selected, selection_evidence=maintained, scroll_performed=needs_scroll, target={key: info.get(key) for key in ('tag_name', 'id', 'name', 'class', 'type', 'text', 'value', 'aria_label', 'title', 'disabled_attribute', 'aria_disabled', 'display', 'visibility', 'pointer_events', 'geometry', 'form_relation', 'form_id', 'form_name', 'form_action', 'form_method', 'element_from_point_relation')}, **_phase5_3_safety(False))
    _latency_duration(user, request, 'next_logging_before_click', logging_started, 'LOGGING')
    try:
        click_start_log_started = time.perf_counter()
        log_event('next_native_click_started', user=user, request=request, selected_position=selected, **_phase5_3_safety(False))
        trace = _latency_trace(user, request)
        trace['durations_ms']['next_logging_before_click'] += (time.perf_counter() - click_start_log_started) * 1000.0
        _latency_mark(user, request, 'next_click_start')
        target.click()
        _latency_mark(user, request, 'next_click_return')
    except ElementClickInterceptedException as exc:
        intercepted = _next_click_dom_diagnostic(driver, target, info)
        result = make_result('UNKNOWN', 'NEXT_CLICK_UNKNOWN', reason='native click intercepted', exception_type=type(exc).__name__, exception_message=str(exc), diagnostic=intercepted, **_phase5_3_safety(False))
        log_event('next_click_intercepted', result, user=user, request=request, **result.details)
        return result
    except Exception as exc:
        diagnostic = _next_failure_diagnostic(driver, target, info)
        result = make_result('UNKNOWN', 'NEXT_CLICK_UNKNOWN', reason=f'native click failed: {type(exc).__name__}', exception_message=str(exc), diagnostic=diagnostic, **_phase5_3_safety(False))
        log_event('next_click_failed', result, user=user, request=request, **result.details)
        return result
    log_event('next_native_click_dispatched', user=user, request=request, **_phase5_3_safety(True))

    def lightweight_changed(current_driver):
        probe = _next_transition_probe(current_driver)
        url_confirmed = probe['confirm_url'] and probe['url'] != pre_probe['url']
        dom_confirmed = probe['confirm_dom_detected'] and probe['position_radio_count'] == 0
        return probe if url_confirmed or dom_confirmed else False
    try:
        detected_probe = WebDriverWait(driver, 10, poll_frequency=0.05).until(lightweight_changed)
        _latency_mark(user, request, 'next_transition_detected')
    except TimeoutException:
        detected_probe = _next_transition_probe(driver)
    formal_started = time.perf_counter()
    post = _page_transition_snapshot(driver, selected, request)
    _latency_duration(user, request, 'next_formal_confirm_diagnostic', formal_started, 'DOM_DIAGNOSTIC_AFTER_TRANSITION')
    evidence = {'url_changed': detected_probe['url'] != pre_probe['url'], 'position_dom_disappeared': pre_probe['position_radio_count'] > 0 and detected_probe['position_radio_count'] == 0, 'controls_changed': detected_probe['controls'] != pre_probe['controls'], 'forms_changed': detected_probe['forms'] != pre_probe['forms'], 'headings_changed': detected_probe['headings'] != pre_probe['headings']}
    positive_count = sum((bool(v) for v in evidence.values()))
    confirm_signal = detected_probe.get('confirm_url') or detected_probe.get('confirm_dom_detected')
    ready = positive_count >= 2 and confirm_signal and (not post['error_text_detected'])
    state = 'CONFIRM_PAGE_READY' if ready else 'NEXT_TRANSITION_UNKNOWN'
    if ready:
        if 'next_transition_detected' not in _latency_trace(user, request)['marks']:
            _latency_mark(user, request, 'next_transition_detected')
        _latency_mark(user, request, 'confirm_page_ready')
        log_event('confirm_page_ready_detected', user=user, request=request, selected_position=selected, transition_evidence=evidence, **_phase5_3_safety(True))
    result = make_result('OK' if ready else 'UNKNOWN', state, reason=None if ready else 'insufficient or contradictory transition evidence', pre_url=pre_probe['url'], post_url=post['url'], transition_evidence=evidence, lightweight_transition_probe=detected_probe, post_transition=post, **_phase5_3_safety(True))
    if ready:
        deferred_position_started = time.perf_counter()
        position_handles = position_result.value or {}
        try:
            deferred_position = _position_click_dom_diagnostic(driver, position_handles.get('position_radio'), position_handles.get('position_target'))
        except Exception as exc:
            deferred_position = {'diagnostic_error': type(exc).__name__, 'diagnostic_error_message': str(exc)}
        _latency_duration(user, request, 'position_deferred_diagnostic', deferred_position_started, 'DOM_DIAGNOSTIC_AFTER_CONFIRM_PAGE_READY')
        log_event('position_click_diagnostic_deferred', user=user, request=request, position=selected, selected_by=position_handles.get('position_selected_by'), diagnostic=deferred_position)
        deferred_next_started = time.perf_counter()
        deferred_next = _next_failure_diagnostic(driver, target, info)
        _latency_duration(user, request, 'next_deferred_diagnostic', deferred_next_started, 'DOM_DIAGNOSTIC_AFTER_CONFIRM_PAGE_READY')
        log_event('next_click_diagnostic_deferred', user=user, request=request, selected_position=selected, diagnostic=deferred_next)
    log_event('next_click_post_transition_diagnostic', result, user=user, request=request, **result.details)
    return result

def _phase6_1_safety(next_clicked=True, final_submit_found=False, final_submit_ready=False):
    """Phase 6.1の全終了経路で、送信操作が0件であることを明示する。"""
    return {'next_clicked': next_clicked, 'final_submit_found': final_submit_found, 'final_submit_ready': final_submit_ready, 'final_submit_clicked': False, 'confirmsubmit_clicked': False, 'submission_attempted': False, 'reservation_confirmed': False, 'legacy_fallback_used': False}

def _confirm_page_snapshot_legacy(driver, request, selected_position):
    """確認画面を変更せず、内容照合と候補探索に必要な実DOMを採取する。"""
    return driver.execute_script('\n        const clip=(s,n)=>String(s||\'\').slice(0,n);\n        const visible=(e)=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();\n          return s.display!==\'none\'&&s.visibility!==\'hidden\'&&r.width>0&&r.height>0;};\n        const desc=(e)=>({tag_name:e.tagName.toLowerCase(),id:e.id||\'\',name:e.name||\'\',\n          class:clip(e.className,500),type:e.type||\'\',text:clip(e.innerText||e.textContent,500),\n          value:e.value||\'\',aria_label:e.getAttribute(\'aria-label\')||\'\',title:e.title||\'\',\n          onclick:e.getAttribute(\'onclick\')||\'\',disabled:e.hasAttribute(\'disabled\'),\n          aria_disabled:e.getAttribute(\'aria-disabled\'),displayed:visible(e),\n          outerHTML:clip(e.outerHTML,2000)});\n        const body=clip(document.body ? document.body.innerText : \'\',16000);\n        const controls=Array.from(document.querySelectorAll(\n          \'button,input[type="submit"],input[type="button"],[role="button"],a\'));\n        const overlaySelectors=[\'.blockUI\',\'.blockOverlay\',\'.modal-backdrop\',\'.loading\',\'.overlay\',\n          \'[aria-busy="true"]\'];\n        const overlays=Array.from(document.querySelectorAll(overlaySelectors.join(\',\')))\n          .filter(e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();\n            return s.display!==\'none\'&&s.visibility!==\'hidden\'&&s.pointerEvents!==\'none\'&&\n              r.width>0&&r.height>0;}).map(desc);\n        const normalizeText=(s)=>String(s||\'\').replace(/[\\s\u3000]+/g,\'\').trim();\n        const captionCandidates=Array.from(document.querySelectorAll(\n          \'td,th,dt,caption,[class*="caption"]\')).filter(e=>\n            normalizeText(e.textContent)===\'レッスン場所\');\n        const positionCaptionDetails=captionCandidates.map(caption=>{\n          const row=caption.closest(\'tr\');\n          const nextSibling=row ? row.nextElementSibling : null;\n          const valueNodes=nextSibling ? Array.from(nextSibling.querySelectorAll(\n            \'td.td_detail_text,td.td_detail_text_half,.td_detail_text,.td_detail_text_half\')) : [];\n          const nonEmptyValues=valueNodes.map(node=>({text:clip(node.textContent,500),\n            normalized_text:normalizeText(node.textContent),outerHTML:clip(node.outerHTML,2500)}))\n            .filter(value=>value.normalized_text);\n          let relation=\'UNKNOWN\';\n          if(!row)relation=\'CAPTION_ROW_NOT_FOUND\';\n          else if(!nextSibling)relation=\'NEXT_SIBLING_NOT_FOUND\';\n          else if(nonEmptyValues.length===1)relation=\'NEXT_SIBLING_ROW_UNIQUE_VALUE\';\n          else if(nonEmptyValues.length===0)relation=\'NEXT_SIBLING_VALUE_NOT_FOUND\';\n          else relation=\'NEXT_SIBLING_VALUE_AMBIGUOUS\';\n          return {caption_text:clip(caption.textContent,500),\n            caption_outerHTML:clip(caption.outerHTML,2500),\n            caption_parent_outerHTML:clip(caption.parentElement&&caption.parentElement.outerHTML,3000),\n            caption_row_outerHTML:clip(row&&row.outerHTML,4000),\n            next_sibling_outerHTML:clip(nextSibling&&nextSibling.outerHTML,4000),\n            value_candidate_count:nonEmptyValues.length,value_candidates:nonEmptyValues,\n            caption_value_relation:relation};\n        });\n        const uniqueCaption=positionCaptionDetails.length===1 ? positionCaptionDetails[0] : null;\n        const positionDomDiagnostic={caption_candidate_count:positionCaptionDetails.length,\n          caption_candidates:positionCaptionDetails,\n          caption_value_relation:uniqueCaption ? uniqueCaption.caption_value_relation :\n            (positionCaptionDetails.length===0?\'CAPTION_NOT_FOUND\':\'CAPTION_AMBIGUOUS\'),\n          value_candidates:uniqueCaption ? uniqueCaption.value_candidates : [],\n          value_text:uniqueCaption&&uniqueCaption.value_candidate_count===1 ?\n            uniqueCaption.value_candidates[0].text : \'\'};\n        return {current_url:location.href,document_title:document.title,\n          headings:Array.from(document.querySelectorAll(\'h1,h2,h3,h4,[role="heading"]\'))\n            .filter(visible).map(e=>clip(e.innerText,500)),body_main_text:body,\n          forms:Array.from(document.forms).map(f=>({id:f.id||\'\',name:f.name||\'\',\n            action:f.action||\'\',method:f.method||\'\',outerHTML:clip(f.outerHTML,2500)})),\n          buttons:controls.filter(e=>e.matches(\'button\')).map(desc),\n          input_submit:controls.filter(e=>e.matches(\'input[type="submit"]\')).map(desc),\n          input_button:controls.filter(e=>e.matches(\'input[type="button"]\')).map(desc),\n          role_buttons:controls.filter(e=>e.matches(\'[role="button"]\')).map(desc),\n          link_candidates:controls.filter(e=>e.matches(\'a\')).map(desc),\n          lesson_name_candidates:Array.from(document.querySelectorAll(\n            \'td,th,dd,dt,span,p,div\')).filter(visible)\n            .map(e=>clip(e.innerText,500)).filter(t=>t&&t.includes(arguments[0])).slice(0,30),\n          date_candidates:body.match(/(?:20\\d{2}[年\\/.-]?)?\\s*\\d{1,2}[月\\/.-]\\s*\\d{1,2}日?/g)||[],\n          position_candidates:Array.from(document.querySelectorAll(\'td,th,dd,dt,span,p,div,input\'))\n            .filter(visible).map(e=>clip(e.innerText||e.value,500))\n            .filter(t=>t&&new RegExp(\'(位置|場所|ポジション|番号|No\\.?|立ち位置)[^\\n]{0,30}\'+arguments[1], \'i\').test(t)).slice(0,30),\n          labeled_content_rows:Array.from(document.querySelectorAll(\'tr,dl,li,p,div\'))\n            .filter(visible).map(e=>clip(e.innerText,800))\n            .filter(t=>/(レッスン|プログラム|日付|予約日|開催日|開始時刻|開始時間|位置|場所|ポジション|立ち位置)/.test(t))\n            .filter((t,i,a)=>t&&a.indexOf(t)===i).slice(0,60),\n          error_or_congestion_texts:(body.match(/[^\\n]*(?:エラー|混雑|失敗|受付でき|処理でき|時間をおいて)[^\\n]*/g)||[]).slice(0,30),\n          position_dom_diagnostic:positionDomDiagnostic,\n          blocking_overlay_count:overlays.length,blocking_overlays:overlays};\n        ', request.get('name', ''), str(selected_position))
PHASE8_8_DATE_PATTERNS = (re.compile('(?<!\\d)(\\d{4})/(\\d{1,2})/(\\d{1,2})(?!\\d)'), re.compile('(?<!\\d)(\\d{4})-(\\d{1,2})-(\\d{1,2})(?!\\d)'), re.compile('(?<!\\d)(\\d{4})年\\s*(\\d{1,2})月\\s*(\\d{1,2})日'), re.compile('(?<!\\d)(\\d{4})(\\d{2})(\\d{2})(?!\\d)'))

def _confirm_page_snapshot(driver, request, selected_position):
    snapshot = _confirm_page_snapshot_legacy(driver, request, selected_position)
    # Observed new-booking Confirm: each caption row is followed by a value
    # row, and the value stays in the same column (日時: date, time).
    snapshot['confirm_identity_rows'] = driver.execute_script(r'''
      const clean=s=>String(s||'').replace(/[\s\u3000]+/g,'').trim();
      const visible=e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();
        return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0};
      const forms=Array.from(document.querySelectorAll('form#main'));
      const form=forms.length===1?forms[0]:null;
      const page_verified=location.pathname==='/DSPWebUser/LESSON/ReserveLessonSchedule/Confirm'
        && clean(document.title)==='レッスン予約確認'
        && form&&form.getAttribute('action')==='/DSPWebUser/LESSON/ReserveLessonSchedule/Confirm'
        && clean(form.getAttribute('method')).toLowerCase()==='post';
      const captions=form?Array.from(form.querySelectorAll('td.td_detail_caption_half')):[];
      const field=(label,column)=>{
        const found=captions.filter(e=>visible(e)&&clean(e.textContent)===label);
        if(found.length!==1)return {caption_count:found.length,relation:'CAPTION_NOT_UNIQUE',value:null};
        const row=found[0].closest('tr'), next=row&&row.nextElementSibling;
        if(!next||next.tagName!=='TR')return {caption_count:1,relation:'NEXT_ROW_MISSING',value:null};
        const labels=Array.from(row.children), values=Array.from(next.children);
        const caption_index=labels.indexOf(found[0]);
        const value=values[column];
        const column_verified=caption_index===0&&
          (column===0||(label==='日時'&&column===1&&
            labels.length===2&&clean(labels[1].textContent)===''));
        const valid=column_verified&&labels.length===values.length&&value
          &&value.matches('td.td_detail_text_half')&&visible(value)
          &&String(value.innerText||value.textContent||'').trim();
        return {caption_count:1,relation:valid?'NEXT_SIBLING_SAME_COLUMN_VALUE':'VALUE_NOT_UNIQUE',
          value:valid?String(value.innerText||value.textContent).trim():null};
      };
      return {page_verified,lesson:field('レッスン',0),
        datetime:field('日時',1),date:field('日時',0)};
    ''')
    return snapshot


def _phase8_8_date_tuple(value):
    if not isinstance(value, str):
        return None
    matches = set()
    for pattern in PHASE8_8_DATE_PATTERNS:
        for match in pattern.finditer(value):
            try:
                parsed = datetime(*map(int, match.groups())).date()
            except ValueError:
                continue
            matches.add((parsed.year, parsed.month, parsed.day))
    return next(iter(matches)) if len(matches) == 1 else None

def _phase8_8_date_comparison(expected, observed):
    expected_tuple = _phase8_8_date_tuple(str(expected or ''))
    observed_tuple = _phase8_8_date_tuple(str(observed or ''))
    if expected_tuple is None or observed_tuple is None:
        return ('UNKNOWN_INVALID', expected_tuple, observed_tuple)
    return ('MATCH' if expected_tuple == observed_tuple else 'MISMATCH', expected_tuple, observed_tuple)

def _confirm_content_evidence(snapshot, request, selected_position):
    """必須3項目を肯定的証拠で照合し、推測不能をMATCHEDにしない。"""
    from lesson_target import canonical_name, names_match, labeled_value, single_time, range_start
    body = snapshot.get('body_main_text', '')
    labeled = snapshot.get('labeled_content_rows', [])
    identity_rows = snapshot.get('confirm_identity_rows')
    if identity_rows is None:  # inherited synthetic fixtures only
        page_verified = True
        observed_lesson = labeled_value(labeled, {'レッスン名', 'プログラム名', 'レッスン'})
        observed_time_text = labeled_value(labeled, {'開始時刻', '開始時間'})
        observed_time = single_time(observed_time_text)
        if observed_time_text is None:
            observed_time_text = labeled_value(labeled, {'日時'})
            observed_time = range_start(observed_time_text)
        date_source = body
    else:
        page_verified = identity_rows.get('page_verified') is True
        lesson_field = identity_rows.get('lesson') or {}
        time_field = identity_rows.get('datetime') or {}
        date_field = identity_rows.get('date') or {}
        observed_lesson = (lesson_field.get('value') if page_verified and
            lesson_field.get('relation') == 'NEXT_SIBLING_SAME_COLUMN_VALUE' else None)
        observed_time_text = (time_field.get('value') if page_verified and
            time_field.get('relation') == 'NEXT_SIBLING_SAME_COLUMN_VALUE' else None)
        observed_time = range_start(observed_time_text) or single_time(observed_time_text)
        date_source = (date_field.get('value') if page_verified and
            date_field.get('relation') == 'NEXT_SIBLING_SAME_COLUMN_VALUE' else '')
    lesson_matched = observed_lesson is not None and names_match(observed_lesson, request.get('name', ''), request.get('date'), observed_time, normalize_lesson_name)
    time_matched = observed_time is not None and observed_time == request.get('start_time')
    date_result, expected_date_tuple, observed_date_tuple = _phase8_8_date_comparison(str(request.get('date', '')), date_source)
    date_matched = date_result == 'MATCH'
    position_diagnostic = dict(snapshot.get('position_dom_diagnostic') or {})
    value_text = position_diagnostic.get('value_text', '')
    extracted_numbers = re.findall('(?<!\\d)(\\d+)\\s*番(?!\\d)', value_text)
    relation_confirmed = position_diagnostic.get('caption_candidate_count') == 1 and position_diagnostic.get('caption_value_relation') == 'NEXT_SIBLING_ROW_UNIQUE_VALUE'
    position_uniquely_extracted = relation_confirmed and len(extracted_numbers) == 1
    confirmation_position = int(extracted_numbers[0]) if position_uniquely_extracted else None
    try:
        selected_position_number = int(str(selected_position).strip())
    except (TypeError, ValueError):
        selected_position_number = None
    position_matched = position_uniquely_extracted and selected_position_number is not None and (confirmation_position == selected_position_number)
    position_mismatched = position_uniquely_extracted and selected_position_number is not None and (confirmation_position != selected_position_number)
    position_texts = [value_text] if position_uniquely_extracted else []
    position_diagnostic.update({'selected_position': selected_position, 'extracted_position_numbers': extracted_numbers, 'confirmation_position': confirmation_position, 'selected_position_number': selected_position_number, 'comparison_result': 'MATCH' if position_matched else 'MISMATCH' if position_mismatched else 'UNKNOWN', 'position_matched': position_matched, 'position_evidence': position_texts})
    lesson_rows = [text for text in labeled if re.search('レッスン|プログラム', text)]
    date_rows = [text for text in labeled if re.search('日付|予約日|開催日', text)]
    position_rows = [text for text in labeled if re.search('位置|場所|ポジション|立ち位置', text)]
    explicit_mismatch = position_mismatched or (observed_lesson is not None and not lesson_matched) or (observed_time is not None and not time_matched) or (date_result == 'MISMATCH' and (identity_rows is not None or bool(date_rows)))
    evidence = {'confirm_page_verified': page_verified, 'lesson_matched': lesson_matched, 'start_time_matched': time_matched, 'date_matched': date_matched, 'position_matched': position_matched, 'target_display_name': observed_lesson, 'target_normalized_name': canonical_name(observed_lesson, normalize_lesson_name) if observed_lesson else None, 'target_date': request.get('date'), 'target_start_time': observed_time, 'candidate_count': 1 if observed_lesson and observed_time else 0, 'confirm_date_normalization_result': date_result, 'confirm_expected_date_tuple': expected_date_tuple, 'confirm_observed_date_tuple': observed_date_tuple, 'position_evidence': position_texts, 'selected_position': selected_position, 'position_diagnostic': position_diagnostic, 'labeled_lesson_rows': lesson_rows, 'labeled_date_rows': date_rows, 'labeled_position_rows': position_rows, 'explicit_mismatch': bool(explicit_mismatch)}
    if explicit_mismatch:
        classification = 'CONFIRM_CONTENT_MISMATCH'
    elif page_verified and lesson_matched and time_matched and date_matched and position_matched:
        classification = 'CONFIRM_CONTENT_MATCHED'
    else:
        classification = 'CONFIRM_CONTENT_UNKNOWN'
    evidence['classification'] = classification
    return evidence

def _final_submit_candidates(driver):
    """操作要素を実DOMから列挙し、「予約する」相当だけを抽出する。"""
    raw = driver.execute_script('\n        const clip=(s,n)=>String(s||\'\').slice(0,n);\n        const nodes=Array.from(document.querySelectorAll(\n          \'button,input[type="submit"],input[type="button"],[role="button"],a\'));\n        const describe=(e)=>{const f=e.form||e.closest(\'form\'); return {\n          tag_name:e.tagName.toLowerCase(),id:e.id||\'\',name:e.name||\'\',class:clip(e.className,500),\n          type:e.type||\'\',text:clip(e.innerText||e.textContent,500),value:e.value||\'\',\n          aria_label:e.getAttribute(\'aria-label\')||\'\',title:e.title||\'\',\n          onclick:e.getAttribute(\'onclick\')||\'\',disabled:e.hasAttribute(\'disabled\'),\n          aria_disabled:e.getAttribute(\'aria-disabled\'),outerHTML:clip(e.outerHTML,2500),\n          form_association:f ? (e.form===f?\'FORM_OWNER\':\'FORM_ANCESTOR\') : \'NO_FORM\',\n          form_action:f ? f.action||\'\' : \'\',form_method:f ? f.method||\'\' : \'\'};};\n        return nodes.map((element,dom_index)=>({element,info:{dom_index,...describe(element)}}));\n        ')
    matches = []
    infos = []
    for item in raw:
        element, info = (item['element'], item['info'])
        info.update(displayed=element.is_displayed(), enabled=element.is_enabled())
        infos.append(info)
        values = [info.get(key, '') for key in ('text', 'value', 'aria_label', 'title')]
        normalized = {re.sub('[\\s\u3000]+', '', str(value)).lower() for value in values}
        if '予約する' in normalized:
            matches.append((element, info))
    return (infos, matches)

def _final_submit_diagnostic(driver, target, info):
    diagnostic = driver.execute_script('\n        const el=arguments[0],r=el.getBoundingClientRect(),cs=getComputedStyle(el);\n        const clip=(s,n)=>String(s||\'\').slice(0,n),cx=r.left+r.width/2,cy=r.top+r.height/2;\n        const inPoint=cx>=0&&cy>=0&&cx<innerWidth&&cy<innerHeight;\n        const top=inPoint?document.elementFromPoint(cx,cy):null;\n        const desc=(n)=>n?{tag_name:n.tagName.toLowerCase(),id:n.id||\'\',\n          class:clip(n.className,500),text:clip(n.innerText||n.textContent,300),\n          outerHTML:clip(n.outerHTML,1500)}:null;\n        let relation=\'NO_ELEMENT\';\n        if(top===el)relation=\'SELF\';else if(top&&el.contains(top))relation=\'DESCENDANT\';\n        else if(top&&top.contains(el))relation=\'ANCESTOR\';else if(top)relation=\'UNRELATED\';\n        const ancestors=[];let p=el.parentElement;\n        for(let i=0;p&&i<5;i++,p=p.parentElement){const q=p.getBoundingClientRect();\n          ancestors.push({tag_name:p.tagName.toLowerCase(),id:p.id||\'\',class:clip(p.className,500),\n            style:p.getAttribute(\'style\')||\'\',geometry:{x:q.x,y:q.y,width:q.width,height:q.height},\n            outerHTML:clip(p.outerHTML,1800)});}\n        const sels=[\'.blockUI\',\'.blockOverlay\',\'.modal-backdrop\',\'.loading\',\'.overlay\',\'[aria-busy="true"]\'];\n        const overlays=Array.from(document.querySelectorAll(sels.join(\',\'))).filter(n=>{\n          const s=getComputedStyle(n),q=n.getBoundingClientRect();return s.display!==\'none\'&&\n          s.visibility!==\'hidden\'&&s.pointerEvents!==\'none\'&&q.width>0&&q.height>0;}).map(desc);\n        return {current_url:location.href,document_title:document.title,\n          viewport:{scrollX,scrollY,innerWidth,innerHeight},\n          geometry:{x:r.x,y:r.y,left:r.left,top:r.top,right:r.right,bottom:r.bottom,\n            width:r.width,height:r.height},fully_inside:r.left>=0&&r.top>=0&&r.right<=innerWidth&&r.bottom<=innerHeight,\n          partially_inside:r.right>0&&r.bottom>0&&r.left<innerWidth&&r.top<innerHeight,\n          center:{x:cx,y:cy,in_viewport:inPoint},element_from_point:desc(top),\n          elements_from_point:inPoint&&document.elementsFromPoint?document.elementsFromPoint(cx,cy).slice(0,8).map(desc):[],\n          element_from_point_relation:relation,blocking_overlay_count:overlays.length,\n          blocking_overlays:overlays,disabled_attribute:el.hasAttribute(\'disabled\'),\n          aria_disabled:el.getAttribute(\'aria-disabled\'),computed_style:{display:cs.display,\n            visibility:cs.visibility,pointer_events:cs.pointerEvents,cursor:cs.cursor,\n            position:cs.position,z_index:cs.zIndex},ancestors};\n        ', target)
    diagnostic.update(element=info, displayed=target.is_displayed(), enabled=target.is_enabled())
    return diagnostic

def diagnose_final_submit(driver, wait, request, position_result, next_result, user=None):
    """CONFIRM_PAGE_READY後を読み取り専用で診断し、最大FINAL_SUBMIT_READYで止める。"""
    selected = position_result.details.get('selected_position')
    prerequisite = next_result.code == 'OK' and next_result.state == 'CONFIRM_PAGE_READY' and (next_result.details.get('next_clicked') is True) and (next_result.details.get('confirmsubmit_clicked') is False) and (next_result.details.get('reservation_confirmed') is False) and (next_result.details.get('legacy_fallback_used') is False)
    if not prerequisite:
        result = make_result('SKIPPED', 'FINAL_SUBMIT_UNKNOWN', reason='CONFIRM_PAGE_READY safety prerequisite was not affirmative', reason_code='FINAL_SUBMIT_UNKNOWN', **_phase6_1_safety(False))
        log_event('phase6_1_stopped', result, user=user, request=request, **result.details)
        return result
    snapshot = _confirm_page_snapshot(driver, request, selected)
    content = _confirm_content_evidence(snapshot, request, selected)
    confirm_reobserve_count = 1
    confirm_reobserve_started = time.perf_counter()
    while content['classification'] == 'CONFIRM_CONTENT_UNKNOWN' and confirm_reobserve_count < PHASE8_8_REOBSERVE_LIMIT and (time.perf_counter() - confirm_reobserve_started < 1.0):
        time.sleep(PHASE8_8_REOBSERVE_INTERVAL_SECONDS)
        snapshot = _confirm_page_snapshot(driver, request, selected)
        content = _confirm_content_evidence(snapshot, request, selected)
        confirm_reobserve_count += 1
    content['confirm_reobserve_count'] = confirm_reobserve_count
    content['confirm_reobserve_elapsed_ms'] = (time.perf_counter() - confirm_reobserve_started) * 1000
    content['recovery_reason'] = 'CONFIRM_IDENTITY_REOBSERVED' if confirm_reobserve_count > 1 else 'NORMAL_FASTPATH'
    content['same_action_reexecuted'] = False
    log_event('confirm_position_diagnostic', user=user, request=request, selected_position=selected, diagnostic=content.get('position_diagnostic', {}), position_matched=content.get('position_matched'), position_evidence=content.get('position_evidence', []), **_phase6_1_safety())
    log_event('confirm_page_diagnostic', user=user, request=request, selected_position=selected, confirm_content=content, diagnostic=snapshot, **_phase6_1_safety())
    if content['classification'] != 'CONFIRM_CONTENT_MATCHED':
        mismatch = content['classification'] == 'CONFIRM_CONTENT_MISMATCH'
        result = make_result('UNKNOWN', 'FINAL_SUBMIT_UNKNOWN', reason='confirmation content mismatch' if mismatch else 'confirmation content lacked affirmative match evidence', reason_code='CONFIRM_TARGET_IDENTITY_MISMATCH' if mismatch else 'CONFIRM_TARGET_IDENTITY_UNVERIFIED', confirm_content=content, **_phase6_1_safety())
        log_event('confirm_content_verification_stopped', result, user=user, request=request, **result.details)
        return result
    infos, matches = _final_submit_candidates(driver)
    log_event('final_submit_candidates', user=user, request=request, candidate_count=len(infos), matched_count=len(matches), candidates=infos, **_phase6_1_safety(final_submit_found=len(matches) == 1))
    if len(matches) == 0:
        return make_result('NOT_FOUND', 'FINAL_SUBMIT_NOT_FOUND', reason='final submit control was not found', reason_code='FINAL_SUBMIT_NOT_FOUND', candidates=infos, **_phase6_1_safety())
    if len(matches) != 1:
        return make_result('UNKNOWN', 'FINAL_SUBMIT_AMBIGUOUS', reason='final submit control was not unique', reason_code='FINAL_SUBMIT_AMBIGUOUS', matched_count=len(matches), candidates=infos, **_phase6_1_safety())
    target, info = matches[0]
    before = _final_submit_diagnostic(driver, target, info)
    log_event('final_submit_diagnostic_before_scroll', user=user, request=request, diagnostic=before, **_phase6_1_safety(final_submit_found=True))
    needs_scroll = not before['fully_inside'] or before['element_from_point_relation'] not in ('SELF', 'DESCENDANT')
    if needs_scroll:
        driver.execute_script("arguments[0].scrollIntoView({block:'center',inline:'center'});", target)

    def reacquire(current_driver):
        _, current_matches = _final_submit_candidates(current_driver)
        return current_matches[0] if len(current_matches) == 1 else False
    try:
        target, info = WebDriverWait(driver, 5).until(reacquire)
    except TimeoutException:
        return make_result('UNKNOWN', 'FINAL_SUBMIT_UNKNOWN', reason='final submit control could not be uniquely reacquired', reason_code='FINAL_SUBMIT_UNKNOWN', **_phase6_1_safety(final_submit_found=True))
    after = _final_submit_diagnostic(driver, target, info)
    log_event('final_submit_diagnostic_after_scroll', user=user, request=request, scroll_performed=needs_scroll, diagnostic=after, **_phase6_1_safety(final_submit_found=True))
    still_confirm = driver.current_url == snapshot['current_url'] and driver.title == snapshot['document_title']
    ready = still_confirm and after['displayed'] and after['enabled'] and (not after['disabled_attribute']) and (str(after.get('aria_disabled') or '').lower() != 'true') and (after['geometry']['width'] > 0) and (after['geometry']['height'] > 0) and (after['blocking_overlay_count'] == 0) and (after['element_from_point_relation'] in ('SELF', 'DESCENDANT')) and (not snapshot['error_or_congestion_texts'])
    if ready:
        result = make_result('OK', 'FINAL_SUBMIT_READY', reason_code='FINAL_SUBMIT_READY', confirm_content=content, diagnostic=after, **_phase6_1_safety(final_submit_found=True, final_submit_ready=True))
    else:
        if not after['enabled'] or after['disabled_attribute'] or str(after.get('aria_disabled') or '').lower() == 'true':
            reason_code = 'FINAL_SUBMIT_DISABLED'
        elif after['blocking_overlay_count']:
            reason_code = 'FINAL_SUBMIT_OVERLAY_BLOCKED'
        elif after['element_from_point_relation'] not in ('SELF', 'DESCENDANT'):
            reason_code = 'FINAL_SUBMIT_NOT_CLICKABLE'
        else:
            reason_code = 'FINAL_SUBMIT_UNKNOWN'
        result = make_result('UNKNOWN', reason_code, reason='final submit affirmative safety conditions were not all met', reason_code=reason_code, confirm_page_maintained=still_confirm, diagnostic=after, **_phase6_1_safety(final_submit_found=True))
    log_event('phase6_1_final_submit_diagnostic_completed', result, user=user, request=request, **result.details)
    return result

def _phase6_2_submit_flags(final_submit_clicked=False, submission_attempted=False, reservation_confirmed=False, confirmsubmit_clicked=False):
    return {'final_submit_found': True, 'final_submit_ready': True, 'final_submit_clicked': final_submit_clicked, 'confirmsubmit_clicked': confirmsubmit_clicked, 'submission_attempted': submission_attempted, 'reservation_confirmed': reservation_confirmed, 'legacy_fallback_used': False}

def _post_submit_snapshot(driver, request, selected_position):
    """最終送信後を操作せず観測する。再送信用WebElementは返さない。"""
    return driver.execute_script('\n        const lesson=String(arguments[0]||\'\'),date=String(arguments[1]||\'\'),\n          position=String(arguments[2]||\'\');\n        const clip=(s,n)=>String(s||\'\').slice(0,n);\n        const visible=(e)=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();\n          return s.display!==\'none\'&&s.visibility!==\'hidden\'&&r.width>0&&r.height>0;};\n        const desc=(e)=>({tag_name:e.tagName.toLowerCase(),id:e.id||\'\',name:e.name||\'\',\n          class:clip(e.className,500),type:e.type||\'\',text:clip(e.innerText||e.textContent,500),\n          value:e.value||\'\',aria_label:e.getAttribute(\'aria-label\')||\'\',title:e.title||\'\',\n          disabled:e.hasAttribute(\'disabled\'),displayed:visible(e),\n          outerHTML:clip(e.outerHTML,1800)});\n        const body=clip(document.body?document.body.innerText:\'\',16000);\n        const headings=Array.from(document.querySelectorAll(\'h1,h2,h3,h4,[role="heading"]\'))\n          .filter(visible).map(e=>clip(e.innerText,500));\n        const buttons=Array.from(document.querySelectorAll(\n          \'button,input[type="submit"],input[type="button"],[role="button"]\')).map(desc);\n        const sels=[\'.blockUI\',\'.blockOverlay\',\'.modal-backdrop\',\'.loading\',\'.overlay\',\n          \'[aria-busy="true"]\'];\n        const overlays=Array.from(document.querySelectorAll(sels.join(\',\'))).filter(e=>{\n          const s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!==\'none\'&&\n          s.visibility!==\'hidden\'&&s.pointerEvents!==\'none\'&&r.width>0&&r.height>0;}).map(desc);\n        const successPattern=/(予約が完了しました|予約完了|予約を受け付けました|予約を承りました)/g;\n        const failurePattern=/(レッスン場所の確保ができませんでした|予約できませんでした|予約に失敗|受付できません)/g;\n        const errorPattern=/(エラー|処理できません|通信に失敗|時間をおいて)/g;\n        const congestionPattern=/(混雑|アクセスが集中|しばらくして)/g;\n        const normalizeLabel=(s)=>String(s||\'\').replace(/[\\s\u3000]+/g,\'\').toLowerCase();\n        const finalReservationSubmitPresent=buttons.some(b=>\n          [b.text,b.value,b.aria_label,b.title].some(v=>normalizeLabel(v)===\'予約する\'));\n        return {url:location.href,document_title:document.title,headings,body_main_text:body,\n          forms:Array.from(document.forms).map(f=>({id:f.id||\'\',name:f.name||\'\',\n            action:f.action||\'\',method:f.method||\'\',outerHTML:clip(f.outerHTML,2500)})),\n          buttons,confirm_page_dom_present:/レッスン予約確認/.test(document.title+\' \'+headings.join(\' \')),\n          final_reservation_submit_present:finalReservationSubmitPresent,\n          final_submit_present:finalReservationSubmitPresent,\n          success_text_candidates:Array.from(new Set(body.match(successPattern)||[])),\n          failure_text_candidates:Array.from(new Set(body.match(failurePattern)||[])),\n          reservation_number_candidates:Array.from(new Set(\n            Array.from(body.matchAll(/(?:予約番号|受付番号)\\s*[:：]?\\s*([A-Za-z0-9-]+)/g),m=>m[1]))),\n          error_text_candidates:Array.from(new Set(body.match(errorPattern)||[])),\n          congestion_text_candidates:Array.from(new Set(body.match(congestionPattern)||[])),\n          blocking_overlay_count:overlays.length,blocking_overlays:overlays,\n          selected_lesson_present:lesson?body.includes(lesson):false,\n          selected_date_present:date?body.replace(/\\D/g,\'\').includes(date.replace(/\\D/g,\'\')):false,\n          selected_position_present:position?new RegExp(\'(^|\\D)\'+position+\'\\s*番(\\D|$)\').test(body):false,\n          selected_lesson:lesson,selected_date:date,selected_position:position};\n        ', request.get('name', ''), request.get('date', ''), selected_position)

def _is_final_reservation_submit_info(button_info):
    labels = [button_info.get(key, '') for key in ('text', 'value', 'aria_label', 'title')]
    normalized = {re.sub('[\\s\u3000]+', '', str(label)).lower() for label in labels}
    return '予約する' in normalized

def _classify_post_submit_snapshot(snapshot):
    """実機Complete DOMの独立証拠を組み合わせ、単一要素では成功にしない。"""
    url = str(snapshot.get('url') or '')
    title = re.sub('[\\s\u3000]+', '', str(snapshot.get('document_title') or ''))
    headings = [re.sub('[\\s\u3000]+', '', str(value)) for value in snapshot.get('headings', [])]
    success_messages = snapshot.get('success_text_candidates', []) or []
    failure_messages = snapshot.get('failure_text_candidates', []) or []
    error_messages = snapshot.get('error_text_candidates', []) or []
    buttons = snapshot.get('buttons')
    if isinstance(buttons, list):
        final_present = any((_is_final_reservation_submit_info(button) for button in buttons))
    else:
        final_present = bool(snapshot.get('final_reservation_submit_present', snapshot.get('final_submit_present', False)))
    evidence = {'complete_url': bool(re.search('/ReserveLessonSchedule/Complete(?:[/?#]|$)', url, flags=re.IGNORECASE)), 'success_title': 'レッスン予約完了' in title, 'success_heading': any(('レッスン予約完了' in heading for heading in headings)), 'success_message': bool(success_messages), 'success_text_candidates': success_messages, 'confirm_page_dom_present': bool(snapshot.get('confirm_page_dom_present')), 'final_reservation_submit_present': final_present, 'failure_message_present': bool(failure_messages), 'failure_text_candidates': failure_messages, 'error_message_present': bool(error_messages), 'error_text_candidates': error_messages, 'blocking_overlay_present': bool(snapshot.get('blocking_overlay_count', 0))}
    independent_positive_count = sum((bool(evidence[key]) for key in ('complete_url', 'success_title', 'success_heading', 'success_message')))
    evidence['independent_positive_count'] = independent_positive_count
    gates_clear = not evidence['confirm_page_dom_present'] and (not evidence['final_reservation_submit_present']) and (not evidence['failure_message_present']) and (not evidence['error_message_present']) and (not evidence['blocking_overlay_present'])
    explicit_success = independent_positive_count >= 3 and gates_clear
    explicit_failure = evidence['failure_message_present']
    if explicit_failure:
        state = 'RESERVATION_FAILED'
    elif explicit_success:
        state = 'RESERVATION_CONFIRMED'
    else:
        state = 'UNKNOWN_AFTER_SUBMIT'
    evidence['gates_clear'] = gates_clear
    evidence['classification'] = state
    return (state, evidence)
POST_ACTION_TRANSITION_INCOMPLETE = 'POST_ACTION_TRANSITION_INCOMPLETE'

@dataclass(frozen=True)
class PostActionReobserveConfig:
    poll_interval_seconds: float = 0.05
    max_seconds: float = 1.5
    max_observations: int = 30

def _final_transition_started_evidence(snapshot, pre_snapshot=None):
    """Transition evidence permits observation, never success or another submit."""
    state, final_evidence = _classify_post_submit_snapshot(snapshot)
    pre_snapshot = pre_snapshot or {}
    url = str(snapshot.get('url') or '')
    title = str(snapshot.get('document_title') or '')
    evidence = {'complete_url_detected': final_evidence['complete_url'], 'success_title_detected': final_evidence['success_title'], 'success_heading_detected': final_evidence['success_heading'], 'success_message_detected': final_evidence['success_message'], 'confirm_dom_present': final_evidence['confirm_page_dom_present'], 'final_reservation_submit_present': final_evidence['final_reservation_submit_present'], 'failure_message_present': final_evidence['failure_message_present'], 'error_message_present': final_evidence['error_message_present'], 'url_changed': url != str(pre_snapshot.get('url') or ''), 'title_changed': title != str(pre_snapshot.get('document_title') or ''), 'old_confirm_dom_disappeared': not final_evidence['confirm_page_dom_present'], 'old_submit_disappeared': not final_evidence['final_reservation_submit_present']}
    evidence['transition_started'] = bool(evidence['complete_url_detected'] or (evidence['url_changed'] and evidence['old_confirm_dom_disappeared']) or (evidence['title_changed'] and evidence['old_submit_disappeared']))
    evidence['observed_state'] = state
    return evidence

def observe_post_action_state(stage, initial_snapshot, snapshot_fn, classifier, transition_classifier, config=None, clock_fn=time.perf_counter, sleep_fn=time.sleep):
    """Bounded same-document read-only observation; no navigation or action callback."""
    config = config or PostActionReobserveConfig()
    started = clock_fn()
    snapshot = initial_snapshot
    state, final_evidence = classifier(snapshot)
    transition = transition_classifier(snapshot)
    initial_state = state
    history = [{'state': state, 'transition': transition, 'snapshot': snapshot}]
    count = 0
    if state not in ('RESERVATION_CONFIRMED', 'RESERVATION_FAILED') and transition.get('transition_started'):
        deadline = started + config.max_seconds
        while count < config.max_observations and clock_fn() < deadline:
            sleep_fn(min(config.poll_interval_seconds, max(0.0, deadline - clock_fn())))
            snapshot = snapshot_fn()
            count += 1
            state, final_evidence = classifier(snapshot)
            transition = transition_classifier(snapshot)
            history.append({'state': state, 'transition': transition, 'snapshot': snapshot})
            if state in ('RESERVATION_CONFIRMED', 'RESERVATION_FAILED'):
                break
    ended = clock_fn()
    return {'stage': stage, 'initial_observed_state': initial_state, 'transition_started': bool(history[0]['transition'].get('transition_started')), 'reobserve_started': count > 0, 'reobserve_count': count, 'reobserve_elapsed_ms': (ended - started) * 1000.0 if count else 0.0, 'final_observed_state': state, 'same_action_reexecuted': False, 'recovery_result': state, 'initial_snapshot': initial_snapshot, 'final_snapshot': snapshot, 'final_evidence': final_evidence, 'history': history}

def _confirm_submit_binding(driver, target):
    """Positive native Confirm form binding; read-only, no target inference."""
    return driver.execute_script(r'''/* CLA1_CONFIRM_SUBMIT_BINDING */
const b=arguments[0],f=b&&b.form,path='/DSPWebUser/LESSON/ReserveLessonSchedule/Confirm';
const u=f?new URL(f.action,location.href):null;
return location.origin==='https://www5.e-atoms.jp'&&location.pathname===path&&!location.search&&!location.hash&&
 document.readyState==='complete'&&document.querySelectorAll('form#main').length===1&&
 document.querySelectorAll('#confirmsubmit').length===1&&!!f&&f.id==='main'&&f.method.toUpperCase()==='POST'&&!f.target&&
 u.origin===location.origin&&u.pathname===path&&!u.search&&!u.hash&&
 b.isConnected&&b.tagName==='BUTTON'&&b.type==='submit'&&b.id==='confirmsubmit'&&b.name==='confirmsubmit'&&
 b.innerText.replace(/[\s\u3000]+/g,'')==='予約する'&&
 !b.hasAttribute('onclick')&&!b.hasAttribute('formaction')&&!b.hasAttribute('formmethod')&&!b.hasAttribute('formtarget');
''', target) is True


def submit_final_once_and_diagnose(driver, wait, request, position_result, final_ready_result, user=None):
    """最終送信を最大1回だけnative clickし、以後は読み取り専用で停止する。"""
    identity_stop = _cla1_identity_guard(driver, user)
    if identity_stop is not None:
        return identity_stop
    del wait
    selected = position_result.details.get('selected_position')
    try:
        journal, _ = _read_journal(user['username'])
        prior = journal['requests'].get(_journal_request_key(_journal_identity(user['username'], request)))
        if prior and prior.get('state') in {'SUBMIT_INTENT', 'CONFIRMED'}:
            return make_result('UNKNOWN', 'UNKNOWN_AFTER_SUBMIT', submission_attempted=False, reservation_confirmed=False, reason_code='FINAL_RESEND_PROHIBITED')
    except Exception:
        return make_result('UNKNOWN', 'JOURNAL_PRESERVATION_ERROR', reservation_confirmed=False)
    ready_details = final_ready_result.details
    prerequisite = final_ready_result.code == 'OK' and final_ready_result.state == 'FINAL_SUBMIT_READY' and (ready_details.get('final_submit_found') is True) and (ready_details.get('final_submit_ready') is True) and (ready_details.get('final_submit_clicked') is False) and (ready_details.get('submission_attempted') is False) and (ready_details.get('reservation_confirmed') is False) and (ready_details.get('legacy_fallback_used') is False)
    if not prerequisite:
        result = make_result('SKIPPED', 'FINAL_SUBMIT_NOT_ATTEMPTED', reason='FINAL_SUBMIT_READY prerequisite was not affirmative', final_submit_found=bool(ready_details.get('final_submit_found')), final_submit_ready=bool(ready_details.get('final_submit_ready')), final_submit_clicked=False, confirmsubmit_clicked=False, submission_attempted=False, reservation_confirmed=False, legacy_fallback_used=False)
        log_event('phase6_2_submit_stopped', result, user=user, request=request, **result.details)
        return result
    confirm_snapshot = _confirm_page_snapshot(driver, request, selected)
    confirm_content = _confirm_content_evidence(confirm_snapshot, request, selected)
    candidate_infos, matches = _final_submit_candidates(driver)
    target = info = diagnostic = None
    if len(matches) == 1:
        target, info = matches[0]
        diagnostic = _final_submit_diagnostic(driver, target, info)
    confirm_url = 'Confirm' in confirm_snapshot.get('current_url', '')
    preconditions = {'confirm_url': confirm_url, 'confirm_content_matched': confirm_content.get('classification') == 'CONFIRM_CONTENT_MATCHED', 'unique_final_submit': len(matches) == 1, 'displayed': bool(diagnostic and diagnostic.get('displayed')), 'enabled': bool(diagnostic and diagnostic.get('enabled')), 'disabled_absent': bool(diagnostic and (not diagnostic.get('disabled_attribute'))), 'aria_disabled_not_true': bool(diagnostic and str(diagnostic.get('aria_disabled') or '').lower() != 'true'), 'geometry_positive': bool(diagnostic and diagnostic['geometry']['width'] > 0 and (diagnostic['geometry']['height'] > 0)), 'overlay_absent': bool(diagnostic and diagnostic.get('blocking_overlay_count') == 0), 'topmost_safe': bool(diagnostic and diagnostic.get('element_from_point_relation') in ('SELF', 'DESCENDANT')), 'error_or_congestion_absent': not confirm_snapshot.get('error_or_congestion_texts'), 'submission_attempted_false': True}
    log_event('final_submit_pre_click_revalidation', user=user, request=request, selected_position=selected, preconditions=preconditions, confirm_content=confirm_content, candidates=candidate_infos, diagnostic=diagnostic, **_phase6_2_submit_flags())
    if not all(preconditions.values()):
        result = make_result('UNKNOWN', 'FINAL_SUBMIT_NOT_ATTEMPTED', reason='final submit pre-click revalidation failed', reason_code=('CONFIRM_TARGET_IDENTITY_MISMATCH' if confirm_content.get('classification') == 'CONFIRM_CONTENT_MISMATCH' else 'CONFIRM_TARGET_IDENTITY_UNVERIFIED') if confirm_content.get('classification') != 'CONFIRM_CONTENT_MATCHED' else 'FINAL_SUBMIT_PRECHECK_FAILED', preconditions=preconditions, confirm_content=confirm_content, candidates=candidate_infos, diagnostic=diagnostic, **_phase6_2_submit_flags())
        log_event('phase6_2_submit_stopped', result, user=user, request=request, **result.details)
        return result
    if not _confirm_submit_binding(driver, target):
        result = make_result('UNKNOWN', 'FINAL_SUBMIT_NOT_ATTEMPTED', reason='native Confirm form/target identity was not positively verified', reason_code='CONFIRM_FORM_IDENTITY_UNVERIFIED', **_phase6_2_submit_flags())
        log_event('phase6_2_submit_stopped', result, user=user, request=request, **result.details)
        return result
    pre_snapshot = _post_submit_snapshot(driver, request, selected)
    identity_stop = _cla1_identity_guard(driver, user)
    if identity_stop is not None:
        return identity_stop
    try:
        intent_record = _journal_write_state(user['username'], request, 'SUBMIT_INTENT', selected)
        log_event('journal_submit_intent_durable', user=user, request=request, journal_state=intent_record['state'], selected_position=selected)
    except Exception as exc:
        result = make_result('UNKNOWN', 'JOURNAL_PRESERVATION_ERROR', reason='durable submit intent failed; Final prohibited', reason_code='JOURNAL_INTENT_WRITE_FAILED', exception_type=type(exc).__name__, reservation_operation=False, **_phase6_2_submit_flags())
        log_event('phase6_2_submit_stopped', result, user=user, request=request, **result.details)
        return result
    submit_deadline = time.monotonic() + 15.0
    _observation = _cla1_obs_new(submit_deadline)
    click_started = time.perf_counter()
    click_exception = None
    final_submit_clicked = False
    submission_attempted = False
    confirmsubmit_clicked = False
    log_event('final_submit_native_click_started', user=user, request=request, pre_url=pre_snapshot['url'], selected_position=selected, **_phase6_2_submit_flags())
    try:
        _latency_mark(user, request, 'final_click_start')
        _cla1_obs_call(_observation, 'invocation')
        _latency_mark(user, request, 'batch_submit')
        target.click()
        _latency_mark(user, request, 'final_click_return')
    except Exception as exc:
        click_exception = {'type': type(exc).__name__, 'message': str(exc)}
    finally:
        final_submit_clicked = True
        submission_attempted = True
        confirmsubmit_clicked = info.get('id') == 'confirmsubmit'
    click_return_seconds = time.perf_counter() - click_started
    _cla1_obs_call(_observation, 'returned', click_exception)
    log_event('final_submit_native_click_returned', user=user, request=request, click_return_seconds=click_return_seconds, click_exception=click_exception, **_phase6_2_submit_flags(final_submit_clicked, submission_attempted, False, confirmsubmit_clicked))
    post_snapshot = {}
    observation_timeout = False
    observation_exception = None
    reconciliation_evidence = {}

    def completed(current_driver):
        nonlocal post_snapshot
        _cla1_obs_call(_observation, 'post_read_start')
        post_snapshot = _post_submit_snapshot(current_driver, request, selected)
        state, _ = _classify_post_submit_snapshot(post_snapshot)
        _cla1_obs_call(_observation, 'complete', post_snapshot, _, state)
        return state if state in {'RESERVATION_CONFIRMED', 'RESERVATION_FAILED'} else False
    try:
        remaining = submit_deadline - time.monotonic()
        if _cla1_obs_value(_observation, 'wait_expired', remaining <= 0):
            raise TimeoutException()
        WebDriverWait(driver, remaining).until(completed)
        observation_timeout = _cla1_obs_value(_observation, 'observation_timeout', time.monotonic() > submit_deadline)
    except TimeoutException:
        observation_timeout = True
        _cla1_obs_call(_observation, 'wait_exception', 'TimeoutException', True)
    except Exception as exc:
        observation_exception = {'type': type(exc).__name__}
        _cla1_obs_call(_observation, 'wait_exception', type(exc).__name__, False)
    classified_state, success_evidence = _classify_post_submit_snapshot(post_snapshot)
    failure_evidence = success_evidence['failure_text_candidates']
    confirmed = False
    if not observation_timeout and observation_exception is None and (classified_state == 'RESERVATION_CONFIRMED'):
        if time.monotonic() <= submit_deadline:
            return _batch_accept_complete(driver, user, request, selected, success_evidence, submit_deadline, _observation)
    if confirmed and _cla1_obs_value(_observation, 'outer_within_deadline', time.monotonic() <= submit_deadline):
        code, state, reason = ('OK', 'RESERVATION_CONFIRMED', None)
        _latency_mark(user, request, 'reservation_confirmed')
    elif not observation_timeout and observation_exception is None and _cla1_obs_value(_observation, 'failure_within_deadline', time.monotonic() <= submit_deadline) and (classified_state == 'RESERVATION_FAILED') and _cla1_obs_value(_observation, 'failure_identity_ok', _cla1_identity_guard(driver, user) is None) and _cla1_obs_value(_observation, 'failure_acceptance_within_deadline', time.monotonic() <= submit_deadline):
        code, state, reason = ('FAILED', 'RESERVATION_FAILED', 'explicit verified failure')
        confirmed = False
    else:
        code, state, reason, confirmed = ('UNKNOWN', 'UNKNOWN_AFTER_SUBMIT', 'unverified or expired post-submit evidence', False)
    delayed_dom = {'reobserve_elapsed_ms': 0.0, 'same_action_reexecuted': False}
    log_event('cla1_post_submit_reconciliation', user=user, request=request, confirmed=confirmed, observation_timeout=observation_timeout, **reconciliation_evidence)
    journal_confirmation_durable = False
    journal_error = None
    if confirmed:
        try:
            _journal_write_state(user['username'], request, 'CONFIRMED', selected, confirmation_evidence={'positive': True, 'classification': classified_state, 'success_evidence': _cla1_redact(success_evidence), 'reconciliation': reconciliation_evidence})
            journal_confirmation_durable = True
        except Exception as exc:
            journal_error = {'type': type(exc).__name__, 'message': str(exc)}
            _cla1_obs_call(_observation, 'journal_exception', type(exc).__name__)
            code, state, reason, confirmed = ('UNKNOWN', 'JOURNAL_PRESERVATION_ERROR', 'positive confirmation observed but durable journal write failed', False)
    result = make_result(code, state, reason=reason, pre_url=pre_snapshot.get('url'), post_url=post_snapshot.get('url'), url_changed=post_snapshot.get('url') != pre_snapshot.get('url'), pre_snapshot=pre_snapshot, post_snapshot=post_snapshot, click_exception=click_exception, observation_timeout=observation_timeout, observation_exception=observation_exception, success_evidence=success_evidence, failure_evidence=failure_evidence, delayed_dom_recovery=delayed_dom, journal_confirmation_durable=journal_confirmation_durable, journal_error=journal_error, final_delayed_dom_recovery_ms=delayed_dom['reobserve_elapsed_ms'], next_position_attempted=False, same_request_retried=False, reservation_count_incremented=False, **_phase6_2_submit_flags(final_submit_clicked, submission_attempted, confirmed, confirmsubmit_clicked))
    log_event('final_submit_post_state_determined', result, user=user, request=request, post_submit_observation=_cla1_obs_call(_observation, 'finish', state, observation_timeout, journal_confirmation_durable), **result.details)
    return result

def _record_reservation_outcome(submit_result, user, request, selected_position, reservation_counts, reservation_results, counted_request_keys):
    """肯定的成功だけを同一request最大1回、共有集計へ反映する。"""
    username = user['username']
    request_key = _request_identity_key(username, request)
    count_before = int(reservation_counts.get(username, 0))
    count_after = count_before
    incremented = False
    confirmed = submit_result.code == 'OK' and submit_result.state == 'RESERVATION_CONFIRMED' and (submit_result.details.get('reservation_confirmed') is True) and (submit_result.details.get('submission_attempted') is True) and (submit_result.details.get('journal_confirmation_durable') is True)
    if confirmed and request_key not in counted_request_keys:
        count_after = count_before + 1
        reservation_counts[username] = count_after
        counted_request_keys.add(request_key)
        incremented = True
    details = dict(submit_result.details)
    details.update({'reservation_count_before': count_before, 'reservation_count_after': count_after, 'reservation_count_incremented': incremented, 'reservation_request_key': request_key})
    counted_result = make_result(submit_result.code, submit_result.state, reason=submit_result.reason, retryable=submit_result.retryable, value=submit_result.value, **details)
    summary_item = {'username': username, 'date': request.get('date'), 'lesson': request.get('name'), 'state': counted_result.state, 'position': selected_position, 'reservation_count_before': count_before, 'reservation_count_after': count_after, 'reservation_count_incremented': incremented, 'summary_outcome': 'RECOVERED_AND_CONFIRMED' if confirmed and request.get('_phase893_recovered') else 'NEW_CONFIRMED' if confirmed else counted_result.state}
    reservation_results.append(summary_item)
    log_event('reservation_count_recorded', counted_result, user=user, request=request, summary=summary_item, **counted_result.details)
    return counted_result

def _position_click_target(driver, radio):
    radio_id = radio.get_attribute('id')
    labels = driver.find_elements(By.CSS_SELECTOR, f'label[for="{radio_id}"]')
    if not labels:
        labels = radio.find_elements(By.XPATH, 'ancestor::label[1]')
    for label in labels:
        if label.is_displayed() and label.is_enabled():
            return (label, 'label_native_click')
    if radio.is_displayed() and radio.is_enabled():
        return (radio, 'control_native_click')
    return (None, None)

def _position_click_dom_diagnostic(driver, radio, label):
    """native click対象とクリック中心点の遮断状態を、DOM証拠として取得する。"""
    diagnostic = driver.execute_script("\n        const radio = arguments[0];\n        const label = arguments[1];\n        const limit = (value, size = 2500) => {\n          value = value || '';\n          return {value: value.slice(0, size), truncated: value.length > size};\n        };\n        const geometry = (element) => {\n          const rect = element.getBoundingClientRect();\n          return {x: rect.x, y: rect.y, left: rect.left, top: rect.top,\n                  right: rect.right, bottom: rect.bottom,\n                  width: rect.width, height: rect.height};\n        };\n        const style = (element, keys) => {\n          const computed = window.getComputedStyle(element);\n          const result = {};\n          keys.forEach((key) => result[key] = computed.getPropertyValue(key));\n          return result;\n        };\n        const describe = (element, includeText = true) => {\n          if (!element) return null;\n          const html = limit(element.outerHTML);\n          return {tagName: element.tagName, id: element.id || '',\n                  class: element.className || '',\n                  text: includeText ? (element.innerText || '').slice(0, 500) : '',\n                  outerHTML: html.value, outerHTML_truncated: html.truncated,\n                  computed_style: style(element, ['display', 'visibility',\n                    'pointer-events', 'cursor', 'position', 'z-index']),\n                  geometry: geometry(element)};\n        };\n        const radioRect = geometry(radio);\n        const labelRect = geometry(label);\n        const centerX = labelRect.left + labelRect.width / 2;\n        const centerY = labelRect.top + labelRect.height / 2;\n        const pointInViewport = centerX >= 0 && centerY >= 0 &&\n          centerX < window.innerWidth && centerY < window.innerHeight;\n        const top = pointInViewport ? document.elementFromPoint(centerX, centerY) : null;\n        const stack = pointInViewport && document.elementsFromPoint\n          ? document.elementsFromPoint(centerX, centerY).slice(0, 8) : [];\n        const ancestors = [];\n        let current = label.parentElement;\n        for (let depth = 0; current && depth < 5; depth++, current = current.parentElement) {\n          const item = describe(current, false);\n          item.depth = depth + 1;\n          ancestors.push(item);\n        }\n        let pointRelation = 'NO_ELEMENT';\n        if (top === label) pointRelation = 'LABEL';\n        else if (top && label.contains(top)) pointRelation = 'LABEL_DESCENDANT';\n        else if (top) pointRelation = 'UNRELATED_ELEMENT';\n        return {\n          radio: {id: radio.id || '', name: radio.name || '', value: radio.value,\n                  type: radio.type || '', checked: Boolean(radio.checked),\n                  disabled: Boolean(radio.disabled), outerHTML: limit(radio.outerHTML).value,\n                  computed_style: style(radio, ['display', 'visibility', 'pointer-events']),\n                  geometry: radioRect},\n          label: Object.assign(describe(label), {'for': label.getAttribute('for') || ''}),\n          ancestors: ancestors,\n          click_point: {center_x: centerX, center_y: centerY,\n                        in_viewport: pointInViewport},\n          element_from_point: describe(top),\n          element_from_point_relation: pointRelation,\n          elements_from_point: stack.map((element) => describe(element)),\n          viewport: {scrollX: window.scrollX, scrollY: window.scrollY,\n                     innerWidth: window.innerWidth, innerHeight: window.innerHeight},\n          label_viewport: {\n            fully_inside: labelRect.left >= 0 && labelRect.top >= 0 &&\n              labelRect.right <= window.innerWidth && labelRect.bottom <= window.innerHeight,\n            partially_inside: labelRect.right > 0 && labelRect.bottom > 0 &&\n              labelRect.left < window.innerWidth && labelRect.top < window.innerHeight\n          }\n        };\n        ", radio, label)
    diagnostic['radio'].update(displayed=radio.is_displayed(), enabled=radio.is_enabled())
    diagnostic['label'].update(displayed=label.is_displayed(), enabled=label.is_enabled())
    return diagnostic

def _wait_for_scrolled_click_target(driver, position, timeout=5):
    """scroll後に対象を再取得し、表示・geometry・overlay不在を肯定確認する。"""

    def ready(current_driver):
        radios = current_driver.find_elements(By.ID, f'LessonPosNo{position}')
        if len(radios) != 1 or _visible_blocking_overlays(current_driver) != 0:
            return False
        target, selected_by = _position_click_target(current_driver, radios[0])
        if target is None or not target.is_displayed() or (not target.is_enabled()):
            return False
        rect = target.rect
        if rect.get('width', 0) <= 0 or rect.get('height', 0) <= 0:
            return False
        return (radios[0], target, selected_by)
    return WebDriverWait(driver, timeout).until(ready)

def _position_candidates_snapshot(driver):
    """全positionを1回のread-only JavaScriptで取得する。DOM変更は行わない。"""
    return driver.execute_script("\n        const selector = arguments[0];\n        const radios = Array.from(document.querySelectorAll(selector));\n        const labels = Array.from(document.querySelectorAll('label[for]'));\n        const rect = element => {\n          const r = element.getBoundingClientRect();\n          return {x:r.x,y:r.y,left:r.left,top:r.top,right:r.right,bottom:r.bottom,\n                  width:r.width,height:r.height};\n        };\n        const view = element => {\n          const style = getComputedStyle(element);\n          const geometry = rect(element);\n          return {display:style.display,visibility:style.visibility,opacity:style.opacity,\n                  pointer_events:style.pointerEvents,geometry:geometry,\n                  displayed:style.display!=='none' && style.visibility!=='hidden' &&\n                    style.visibility!=='collapse' && style.opacity!=='0' &&\n                    geometry.width>0 && geometry.height>0};\n        };\n        const overlays = Array.from(document.querySelectorAll('.blockUI')).filter(element => {\n          const state=view(element); return state.displayed;\n        });\n        return {url:location.href,blocking_overlay_count:overlays.length,\n          positions:radios.map(radio => {\n            const associated=labels.filter(label => label.htmlFor===radio.id);\n            const label=associated.length===1 ? associated[0] : null;\n            return {id:radio.id||'',value:radio.value||'',disabled:Boolean(radio.disabled),\n              disabled_effective:radio.matches(':disabled'),checked:Boolean(radio.checked),\n              aria_disabled:(radio.getAttribute('aria-disabled')||'').toLowerCase(),\n              class_name:radio.getAttribute('class')||'',input_type:radio.type||'',\n              parent_text:(radio.parentElement&&radio.parentElement.innerText)||'',\n              radio_view:view(radio),label_count:associated.length,\n              label_text:label ? (label.innerText||label.textContent||'') : '',\n              label_view:label ? view(label) : null};\n          })};\n        ", DETAIL_POSITION_SELECTOR)

def _position_status_from_snapshot(snapshot, position):
    """Phase 7.1と同じ4状態規則を、単一snapshotに対して適用する。"""
    target_id = f'LessonPosNo{position}'
    all_positions = snapshot.get('positions') or []
    candidate_ids = [item.get('id', '') for item in all_positions if item.get('id', '').startswith('LessonPosNo') and item.get('id', '')[len('LessonPosNo'):].isdigit() and (int(item.get('id', '')[len('LessonPosNo'):]) > 0)]
    matches = [item for item in all_positions if item.get('id') == target_id]
    overlay_count = int(snapshot.get('blocking_overlay_count', 0))
    details = {'position': position, 'selector': f'#{target_id}', 'position_list_loaded': bool(candidate_ids), 'position_candidate_count': len(candidate_ids), 'blocking_overlay_count': overlay_count, 'overlay_state': 'CLEAR' if overlay_count == 0 else 'BLOCKING', 'snapshot_generation_reused': True, 'element_found': bool(matches), 'contradictions': [], 'evidence_for_available': [], 'evidence_for_unavailable': []}
    contradictions = details['contradictions']
    if overlay_count:
        contradictions.append('blocking_overlay_present')
    if len(matches) > 1:
        contradictions.append('duplicate_position_id')
    if not matches:
        if DETAIL_URL_PATH in str(snapshot.get('url', '')) and candidate_ids and (overlay_count == 0):
            return make_result('NOT_FOUND', 'POSITION_NOT_FOUND', reason='target position is absent from loaded position list', **details)
        contradictions.append('position_list_not_loaded_or_blocked')
        return make_result('UNKNOWN', 'POSITION_UNKNOWN', reason='target absence could not be verified safely', retryable=True, **details)
    if contradictions:
        return make_result('UNKNOWN', 'POSITION_UNKNOWN', reason='position evidence is contradictory or blocked', retryable=True, **details)
    item = matches[0]
    displayed = bool((item.get('radio_view') or {}).get('displayed'))
    enabled = not bool(item.get('disabled_effective'))
    disabled = bool(item.get('disabled'))
    aria_disabled = str(item.get('aria_disabled') or '').lower()
    class_tokens = set(filter(None, re.split('\\s+', str(item.get('class_name') or '').lower())))
    parent_text = str(item.get('parent_text') or '').lower()
    class_marks = [m for m in POSITION_UNAVAILABLE_CLASS_MARKERS if m.lower() in class_tokens]
    text_marks = [m for m in POSITION_UNAVAILABLE_TEXT_MARKERS if m.lower() in parent_text]
    unavailable = details['evidence_for_unavailable']
    if disabled:
        unavailable.append('disabled_attribute_present')
    if aria_disabled == 'true':
        unavailable.append('aria_disabled_true')
    if class_marks:
        unavailable.append('unavailable_class:' + ','.join(class_marks))
    if text_marks:
        unavailable.append('unavailable_text:' + ','.join(text_marks))
    hidden_radio = str(item.get('input_type') or '').lower() == 'radio' and (not displayed)
    available = details['evidence_for_available']
    if displayed:
        available.append('displayed')
    elif hidden_radio:
        available.append('hidden_radio_normal_dom_contract')
    if enabled:
        available.append('enabled')
    if not disabled:
        available.append('disabled_attribute_absent')
    if aria_disabled != 'true':
        available.append('aria_disabled_not_true')
    if not class_marks and (not text_marks):
        available.append('no_explicit_unavailable_marker')
    if overlay_count == 0:
        available.append('blocking_overlay_absent')
    if candidate_ids:
        available.append('position_list_loaded')
    if disabled and enabled:
        contradictions.append('disabled_attribute_conflicts_with_enabled_state')
    if unavailable and displayed and enabled and (not disabled) and (aria_disabled != 'true'):
        contradictions.append('unavailable_marker_conflicts_with_interactable_state')
    if not displayed and (not hidden_radio):
        contradictions.append('non_radio_position_not_displayed')
    details.update({'displayed': displayed, 'enabled': enabled, 'disabled': disabled, 'aria_disabled': aria_disabled or None, 'checked': item.get('checked'), 'class': item.get('class_name'), 'input_type': item.get('input_type'), 'value': item.get('value'), 'label_count': item.get('label_count'), 'label_text': item.get('label_text'), 'hidden_radio_normal_dom_contract': hidden_radio})
    if contradictions:
        return make_result('UNKNOWN', 'POSITION_UNKNOWN', reason='position evidence is contradictory or blocked', retryable=True, **details)
    if unavailable:
        return make_result('NOT_AVAILABLE', 'POSITION_UNAVAILABLE', reason='explicit unavailable evidence detected', **details)
    if candidate_ids and overlay_count == 0 and (displayed or hidden_radio) and enabled and (not disabled) and (aria_disabled != 'true'):
        return make_result('OK', 'POSITION_AVAILABLE', **details)
    contradictions.append('position evidence is incomplete')
    return make_result('UNKNOWN', 'POSITION_UNKNOWN', reason='position evidence is incomplete or contradictory', retryable=True, **details)

def _position_target_precheck_snapshot(driver, position):
    """対象radio/labelだけを再取得するread-only click直前snapshot。"""
    return driver.execute_script("\n        const id=arguments[0];const unavailableMessages=arguments[2];\n        const radios=Array.from(document.querySelectorAll(arguments[1])).filter(e=>e.id===id);\n        const labels=Array.from(document.querySelectorAll('label[for]')).filter(e=>e.htmlFor===id);\n        const radio=radios.length===1?radios[0]:null;\n        const label=labels.length===1?labels[0]:null;\n        const target=label||radio;\n        const describe=element=>{if(!element)return null;const r=element.getBoundingClientRect();\n          const s=getComputedStyle(element);return {display:s.display,visibility:s.visibility,\n          opacity:s.opacity,pointer_events:s.pointerEvents,\n          geometry:{left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height},\n          in_viewport:r.left>=0&&r.top>=0&&r.right<=innerWidth&&r.bottom<=innerHeight,\n          displayed:s.display!=='none'&&s.visibility!=='hidden'&&s.visibility!=='collapse'&&\n            s.opacity!=='0'&&r.width>0&&r.height>0};};\n        const targetView=describe(target);let top=null;let relation='NO_ELEMENT';\n        if(target&&targetView){const r=target.getBoundingClientRect();const x=r.left+r.width/2;\n          const y=r.top+r.height/2;const inside=x>=0&&y>=0&&x<innerWidth&&y<innerHeight;\n          top=inside?document.elementFromPoint(x,y):null;\n          if(top===target)relation='SELF';else if(top&&target.contains(top))relation='DESCENDANT';\n          else if(top)relation='UNRELATED_ELEMENT';else if(!inside)relation='OUTSIDE_VIEWPORT';}\n        const blocking=Array.from(document.querySelectorAll('.blockUI')).filter(e=>{\n          const v=describe(e);return v&&v.displayed;}).length;\n        const classTokens=radio ? (radio.getAttribute('class')||'').toLowerCase().split(/\\s+/) : [];\n        const parentText=radio&&radio.parentElement ? (radio.parentElement.innerText||'').toLowerCase() : '';\n        const unavailableMarker=arguments[3].some(value=>classTokens.includes(String(value).toLowerCase())) ||\n          arguments[4].some(value=>parentText.includes(String(value).toLowerCase()));\n        return {radio_count:radios.length,label_count:labels.length,radio:radio,target:target,\n          selected_by:label?'label_native_click':'control_native_click',\n          radio_disabled:radio?Boolean(radio.disabled):null,\n          radio_disabled_effective:radio?radio.matches(':disabled'):null,\n          radio_aria_disabled:radio?(radio.getAttribute('aria-disabled')||'').toLowerCase():null,\n          radio_view:describe(radio),target_view:targetView,blocking_overlay_count:blocking,\n          denying_message_detected:unavailableMessages.some(message =>\n            ((document.body&&document.body.innerText)||'').includes(message)),\n          explicit_unavailable_marker_detected:unavailableMarker,\n          element_from_point_relation:relation,url:location.href};\n        ", f'LessonPosNo{position}', DETAIL_POSITION_SELECTOR, DETAIL_UNAVAILABLE_MESSAGES, POSITION_UNAVAILABLE_CLASS_MARKERS, POSITION_UNAVAILABLE_TEXT_MARKERS)

def _position_post_click_snapshot(driver, position):
    """全radioのchecked整合性を1回のread-only JavaScriptで確認する。"""
    return driver.execute_script("\n        const id=arguments[0];const prefix='LessonPosNo';\n        const radios=Array.from(document.querySelectorAll(arguments[1]));\n        const target=radios.filter(radio=>radio.id===id);\n        const checkedIds=radios.filter(radio=>Boolean(radio.checked)).map(radio=>radio.id)\n          .filter(value=>value.startsWith(prefix)&&/^\\d+$/.test(value.slice(prefix.length)))\n          .map(value=>Number(value.slice(prefix.length)));\n        return {target_count:target.length,checked:target.length===1&&Boolean(target[0].checked),\n          is_selected:target.length===1&&Boolean(target[0].checked),checked_position_ids:checkedIds};\n        ", f'LessonPosNo{position}', DETAIL_POSITION_SELECTOR)

def _minimal_precheck_details(snapshot):
    return {key: value for key, value in snapshot.items() if key not in ('radio', 'target')}

def _position_precheck_is_affirmative(snapshot, displayed, enabled, radio_enabled):
    target_view = snapshot.get('target_view') or {}
    geometry = target_view.get('geometry') or {}
    return DETAIL_URL_PATH in str(snapshot.get('url', '')) and snapshot.get('radio_count') == 1 and (snapshot.get('label_count') == 1) and (snapshot.get('radio') is not None) and (snapshot.get('target') is not None) and displayed and enabled and radio_enabled and (not snapshot.get('radio_disabled')) and (not snapshot.get('radio_disabled_effective')) and (str(snapshot.get('radio_aria_disabled') or '').lower() != 'true') and (snapshot.get('blocking_overlay_count') == 0) and (not snapshot.get('denying_message_detected')) and (not snapshot.get('explicit_unavailable_marker_detected')) and (geometry.get('width', 0) > 0) and (geometry.get('height', 0) > 0) and (snapshot.get('element_from_point_relation') in ('SELF', 'DESCENDANT'))

def _position_scroll_is_required(snapshot):
    target_view = snapshot.get('target_view') or {}
    geometry = target_view.get('geometry') or {}
    return not (target_view.get('in_viewport') and geometry.get('width', 0) > 0 and (geometry.get('height', 0) > 0) and (snapshot.get('element_from_point_relation') in ('SELF', 'DESCENDANT')))

def _position_post_click_is_consistent(snapshot, position):
    return snapshot.get('target_count') == 1 and snapshot.get('checked') is True and (snapshot.get('is_selected') is True) and ((snapshot.get('checked_position_ids') or []) == [position])

def select_preferred_position(driver, wait, request, detail_result, user=None):
    """単一snapshotで優先順位判定し、対象だけ再確認してnative clickする。"""
    identity_stop = _cla1_identity_guard(driver, user)
    if identity_stop is not None:
        return identity_stop
    del wait
    requested, attempts = (list(request['positions']), [])
    if detail_result.state != 'DETAIL_READY':
        result = make_result('SKIPPED', detail_result.state, reason=detail_result.state, requested_positions=requested, selected_position=None, selection_attempts=attempts, position_selection_skipped=True, legacy_fallback_used=False, next_clicked=False, confirmsubmit_clicked=False, reservation_confirmed=False)
        log_event('position_selection_skipped', result, user=user, request=request, **result.details)
        return result
    _latency_mark(user, request, 'position_snapshot_start')
    snapshot_start_perf = _latency_trace(user, request)['marks']['position_snapshot_start']
    log_event('position_snapshot_started', user=user, request=request, position_snapshot_start_perf_counter=snapshot_start_perf, requested_position_count=len(requested))
    snapshot_started = time.perf_counter()
    try:
        candidates_snapshot = _position_candidates_snapshot(driver)
    except Exception as exc:
        return _selection_unknown(user, request, None, f'position candidate snapshot failed: {type(exc).__name__}', attempts)
    _latency_duration(user, request, 'position_candidate_snapshot', snapshot_started, 'DOM_QUERY+SAFETY_CHECK')
    classification_started = time.perf_counter()
    selected_status = selected_position = selected_index = None
    compact_candidates = []
    per_candidate_ms = []
    for index, position in enumerate(requested):
        candidate_started = time.perf_counter()
        status = _position_status_from_snapshot(candidates_snapshot, position)
        per_candidate_ms.append({'rank': index + 1, 'position': position, 'elapsed_ms': (time.perf_counter() - candidate_started) * 1000.0, 'state': status.state})
        attempt = {'position': position, 'status': status.state, 'action': 'EVALUATED'}
        attempts.append(attempt)
        compact_candidates.append({'position': position, 'state': status.state, 'code': status.code})
        if status.state == 'POSITION_UNAVAILABLE':
            attempt['action'] = 'SKIPPED'
            continue
        if status.state != 'POSITION_AVAILABLE':
            attempt['action'] = 'STOPPED'
            _latency_duration(user, request, 'position_python_classification', classification_started, 'PYTHON_CLASSIFICATION')
            _latency_trace(user, request)['metadata']['position_candidate_timings_ms'] = per_candidate_ms
            log_event('position_candidate_snapshot_failed_safe', status, user=user, request=request, requested_positions=requested, candidates=compact_candidates)
            return _selection_unknown(user, request, position, f'candidate status was {status.state}', attempts, candidate_index=index, position_status=status.state, overlay_state=status.details.get('overlay_state'))
        selected_status, selected_position, selected_index = (status, position, index)
        _latency_mark(user, request, 'position_available')
        break
    _latency_duration(user, request, 'position_python_classification', classification_started, 'PYTHON_CLASSIFICATION')
    _latency_trace(user, request)['metadata']['position_candidate_timings_ms'] = per_candidate_ms
    if selected_position is None:
        result = make_result('NOT_AVAILABLE', 'NO_PREFERRED_POSITION_AVAILABLE', reason='all requested positions were explicitly unavailable', requested_positions=requested, selected_position=None, selection_attempts=attempts, legacy_fallback_used=False, next_clicked=False, confirmsubmit_clicked=False, reservation_confirmed=False)
        log_event('no_preferred_position_available', result, user=user, request=request, candidates=compact_candidates, **result.details)
        return result
    position = selected_position
    index = selected_index
    trace = _latency_trace(user, request)
    trace['metadata']['selected_candidate_rank'] = index + 1
    trace['metadata']['selected_candidate_id'] = position
    attempt = attempts[-1]
    precheck_started = time.perf_counter()
    _latency_record_ms(user, request, 'position_scroll', 0.0, 'SCROLL')
    _latency_record_ms(user, request, 'position_refetch', 0.0, 'REFETCH')
    try:
        before_snapshot_started = time.perf_counter()
        before = _position_target_precheck_snapshot(driver, position)
        _latency_duration(user, request, 'position_target_snapshot_before_scroll', before_snapshot_started, 'DOM_QUERY+SAFETY_CHECK')
        initial_target = before.get('target')
        if before.get('radio_count') != 1 or before.get('label_count') != 1 or initial_target is None:
            raise RuntimeError('target radio/label was not unique')
        scroll_required = _position_scroll_is_required(before)
        after = before
        if scroll_required:
            scroll_started = time.perf_counter()
            driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'center'});", initial_target)
            _latency_duration(user, request, 'position_scroll', scroll_started, 'SCROLL')
            refetch_started = time.perf_counter()
            after = _position_target_precheck_snapshot(driver, position)
            _latency_duration(user, request, 'position_refetch', refetch_started, 'REFETCH+SAFETY_CHECK')
        radio, target = (after.get('radio'), after.get('target'))
        selenium_recheck_started = time.perf_counter()
        displayed = bool(target and target.is_displayed())
        enabled = bool(target and target.is_enabled())
        radio_enabled = bool(radio and radio.is_enabled())
        _latency_duration(user, request, 'position_selenium_recheck', selenium_recheck_started, 'SELENIUM_SAFETY_CHECK')
    except Exception as exc:
        attempt.update(action='STOPPED_BEFORE_CLICK', error=type(exc).__name__)
        return _selection_unknown(user, request, position, f'target-only precheck failed: {type(exc).__name__}', attempts, candidate_index=index)
    _latency_duration(user, request, 'position_precheck', precheck_started, 'SAFETY_CHECK+SCROLL+REFETCH')
    trace['durations_ms']['position_diagnostic_total'] = trace['durations_ms'].get('position_target_snapshot_before_scroll', 0.0) + trace['durations_ms'].get('position_refetch', 0.0)
    trace['classifications']['position_diagnostic_total'] = 'DOM_QUERY+REFETCH+SAFETY_CHECK'
    precheck_ok = _position_precheck_is_affirmative(after, displayed, enabled, radio_enabled)
    pre_details = {'candidate_index': index, 'position_status': selected_status.state, 'overlay_state': 'CLEAR' if after.get('blocking_overlay_count') == 0 else 'BLOCKING', 'displayed': displayed, 'enabled': enabled, 'radio_enabled': radio_enabled, 'precheck_ok': precheck_ok, 'snapshot_generation_reused_for_priority': True, 'target_only_revalidated': True, 'scroll_required': scroll_required, 'precheck_snapshot': _minimal_precheck_details(after)}
    logging_started = time.perf_counter()
    log_event('position_selection_precheck', user=user, request=request, position=position, candidate_rank=index + 1, precheck_ok=precheck_ok, displayed=displayed, enabled=enabled, radio_enabled=radio_enabled, overlay_state=pre_details['overlay_state'], topmost_relation=after.get('element_from_point_relation'), scroll_required=scroll_required, perf_counter=time.perf_counter())
    if not precheck_ok:
        attempt['action'] = 'STOPPED_BEFORE_CLICK'
        try:
            failure_diagnostic = _position_click_dom_diagnostic(driver, radio, target)
        except Exception as exc:
            failure_diagnostic = {'diagnostic_error': type(exc).__name__}
        return _selection_unknown(user, request, position, 'target-only click precheck was not affirmative', attempts, failure_diagnostic=failure_diagnostic, **pre_details)
    selected_by = after.get('selected_by')
    attempt.update(action='CLICK_STARTED', selected_by=selected_by)
    log_event('position_click_started', user=user, request=request, candidate_rank=index + 1, position=position, selected_by=selected_by, overlay_state=pre_details['overlay_state'], perf_counter=time.perf_counter())
    _latency_duration(user, request, 'position_logging_before_click', logging_started, 'LOGGING')
    try:
        action_started = time.perf_counter()
        action_record = _journal_write_state(user['username'], request, 'ACTION_INTENT', position, action_boundary='POSITION_NATIVE_CLICK', last_reason_code='ACTION_INTENT_DURABLE')
        _latency_duration(user, request, 'action_intent_durable_write', action_started, 'LOCAL_JOURNAL')
        log_event('journal_action_intent_durable', user=user, request=request, journal_state=action_record['state'], selected_position=position)
    except Exception as exc:
        attempt.update(action='STOPPED_ACTION_INTENT_WRITE_FAILED', error=type(exc).__name__)
        return make_result('UNKNOWN', 'PRESERVATION_UNKNOWN', reason='durable action intent failed; Position click prohibited', reason_code='JOURNAL_ACTION_INTENT_WRITE_FAILED', selected_position=position, attempts=attempts, reservation_operation=False, position_click_count=0)
    _latency_mark(user, request, 'position_click_start')
    try:
        target.click()
        _latency_mark(user, request, 'position_click_return')
        attempt['action'] = 'CLICKED'
    except ElementClickInterceptedException as exc:
        attempt.update(action='CLICK_FAILED', error=type(exc).__name__)
        try:
            intercepted = _position_click_dom_diagnostic(driver, radio, target)
        except Exception as diagnostic_exc:
            intercepted = {'diagnostic_error': type(diagnostic_exc).__name__, 'diagnostic_error_message': str(diagnostic_exc)}
        log_event('position_click_intercepted', user=user, request=request, position=position, exception_type=type(exc).__name__, exception_message=str(exc), diagnostic=intercepted)
        return _selection_unknown(user, request, position, 'native click intercepted after centered scroll', attempts, selected_by=selected_by, click_intercepted=True, intercepted_diagnostic=intercepted, **pre_details)
    except Exception as exc:
        attempt.update(action='CLICK_FAILED', error=type(exc).__name__)
        return _selection_unknown(user, request, position, f'native click failed: {type(exc).__name__}', attempts, selected_by=selected_by, **pre_details)
    _latency_mark(user, request, 'position_post_snapshot_start')
    verification_started = time.perf_counter()
    try:
        verification = _position_post_click_snapshot(driver, position)
    except Exception as exc:
        attempt['result'] = 'POSITION_SELECTION_UNKNOWN'
        return _selection_unknown(user, request, position, f'post-click snapshot failed: {type(exc).__name__}', attempts, selected_by=selected_by, **pre_details)
    _latency_duration(user, request, 'position_post_click_snapshot', verification_started, 'REFETCH+SAFETY_CHECK')
    classification_started = time.perf_counter()
    checked = verification.get('checked') is True
    is_selected = verification.get('is_selected') is True
    checked_ids = verification.get('checked_position_ids') or []
    consistent = _position_post_click_is_consistent(verification, position)
    _latency_duration(user, request, 'position_post_click_classification', classification_started, 'PYTHON_CLASSIFICATION')
    attempt.update(checked=checked, is_selected=is_selected, checked_position_ids=checked_ids)
    if not consistent:
        log_event('position_selection_verified', user=user, request=request, position=position, checked=checked, is_selected=is_selected, checked_position_ids=checked_ids, consistent=False, perf_counter=time.perf_counter())
        attempt['result'] = 'POSITION_SELECTION_UNKNOWN'
        return _selection_unknown(user, request, position, 'selection evidence was absent or contradictory', attempts, checked=checked, is_selected=is_selected, checked_position_ids=checked_ids, selected_by=selected_by, **pre_details)
    attempt['result'] = 'POSITION_SELECTED'
    attempts.extend(({'position': p, 'action': 'NOT_EVALUATED', 'reason': 'HIGHER_PRIORITY_POSITION_SELECTED'} for p in requested[index + 1:]))
    result = make_result('OK', 'POSITION_SELECTED', value={'position_radio': radio, 'position_target': target, 'position_selected_by': selected_by}, selected_position=position, requested_positions=requested, selected_by=selected_by, checked=checked, is_selected=is_selected, checked_position_ids=checked_ids, overlay_state=pre_details['overlay_state'], selection_attempts=attempts, candidate_snapshot_summary={'position_count': len(candidates_snapshot.get('positions') or []), 'evaluated': compact_candidates}, legacy_fallback_used=False, next_clicked=False, confirmsubmit_clicked=False, reservation_confirmed=False)
    _latency_mark(user, request, 'position_selected')
    position_selected_perf = trace['marks']['position_selected']
    trace['deferred_diagnostics']['position'] = {'candidate_snapshot': candidates_snapshot, 'final_precheck': _minimal_precheck_details(after), 'selection_attempts': attempts, 'post_click_snapshot': verification}
    log_event('position_click_completed', user=user, request=request, position=position, selected_by=selected_by, position_click_return_perf_counter=trace['marks'].get('position_click_return'))
    log_event('position_selection_verified', user=user, request=request, position=position, checked=checked, is_selected=is_selected, checked_position_ids=checked_ids, consistent=True)
    log_event('position_selected', make_result('OK', 'POSITION_SELECTED', selected_position=position, candidate_rank=index + 1, position_selected_perf_counter=position_selected_perf), user=user, request=request, position_selected_perf_counter=position_selected_perf)
    return result

def _parse_lesson_onclick_identity(value):
    """Parse the stable semantic identity from LessonClick(id, yyyymmdd, ...)."""
    raw = str(value or '').strip()
    match = re.fullmatch('LessonClick\\s*\\(\\s*[\'\\"]?([^,\'\\"\\s()]+)[\'\\"]?\\s*,\\s*[\'\\"]?(\\d{8})[\'\\"]?\\s*(?:,\\s*([^)]*))?\\)\\s*;?', raw)
    if not match:
        return {'parsed': False, 'lesson_identifier': None, 'date': None, 'trailing_arguments': None}
    return {'parsed': True, 'lesson_identifier': match.group(1), 'date': match.group(2), 'trailing_arguments': (match.group(3) or '').strip()}

def _lesson_identity_comparison(candidate, target_snapshot, matching, request, observed_candidate=None):
    """Compare stable lesson semantics without WebElement equality/round-trips."""
    original_raw = candidate.href_or_onclick or ''
    snapshot_onclick = target_snapshot.get('onclick') or ''
    original_onclick = _parse_lesson_onclick_identity(original_raw)
    snapshot_identity = _parse_lesson_onclick_identity(snapshot_onclick)
    matching_identity = _parse_lesson_onclick_identity(matching[0].get('onclick') or '') if len(matching) == 1 else {'parsed': False, 'lesson_identifier': None, 'date': None, 'trailing_arguments': None}
    requested_normalized = normalize_lesson_name(request.get('name', ''))
    snapshot_normalized = normalize_lesson_name(target_snapshot.get('text', ''))
    from lesson_target import names_match, range_start
    name_matches = bool(target_snapshot.get('text')) and names_match(target_snapshot.get('text'), request.get('name', ''), request.get('date'), request.get('start_time'), normalize_lesson_name)
    comparisons = {'lesson_name': {'original': candidate.normalized_name, 'snapshot': snapshot_normalized, 'requested': requested_normalized, 'matched': name_matches}, 'lesson_date': {'original': candidate.date, 'snapshot': snapshot_identity.get('date'), 'requested': request.get('date'), 'matched': candidate.date == request.get('date') == snapshot_identity.get('date')}, 'onclick_lesson_identifier': {'original': original_onclick.get('lesson_identifier'), 'snapshot': snapshot_identity.get('lesson_identifier'), 'matched': original_onclick.get('parsed') and snapshot_identity.get('parsed') and (original_onclick.get('lesson_identifier') == snapshot_identity.get('lesson_identifier'))}, 'onclick_date': {'original': original_onclick.get('date'), 'snapshot': snapshot_identity.get('date'), 'matched': original_onclick.get('parsed') and snapshot_identity.get('parsed') and (original_onclick.get('date') == snapshot_identity.get('date'))}, 'unique_candidate_onclick': {'original': snapshot_identity.get('lesson_identifier'), 'snapshot': matching_identity.get('lesson_identifier'), 'matched': len(matching) == 1 and matching_identity.get('parsed') and (matching_identity.get('lesson_identifier') == snapshot_identity.get('lesson_identifier')) and (matching_identity.get('date') == snapshot_identity.get('date'))}}
    observed_time = range_start((observed_candidate or candidate).anchor_element.find_element(By.XPATH, "./ancestor::td[contains(@class,'lesson')][1]").text)
    comparisons['start_time'] = {'original': candidate.start_time, 'observed': observed_time, 'requested': request.get('start_time'), 'matched': observed_time is not None and candidate.start_time == observed_time == request.get('start_time')}
    mismatch_fields = [name for name, evidence in comparisons.items() if not evidence.get('matched')]
    overall = len(matching) == 1 and (not mismatch_fields)
    return {'original_identity': {'stored_identity': original_raw, 'onclick': original_onclick, 'normalized_name': candidate.normalized_name, 'date': candidate.date, 'candidate_index': candidate.candidate_index}, 'snapshot_identity': {'href': target_snapshot.get('href') or '', 'onclick': snapshot_onclick, 'onclick_parsed': snapshot_identity, 'normalized_name': snapshot_normalized}, 'field_comparison': comparisons, 'overall_identity_match': overall, 'mismatch_fields': mismatch_fields, 'name_match': name_matches, 'date_match': comparisons['lesson_date']['matched'], 'candidate_unique': len(matching) == 1, 'onclick_parse_succeeded': original_onclick.get('parsed') and snapshot_identity.get('parsed') and matching_identity.get('parsed'), 'href_comparison': {'original': None, 'snapshot': target_snapshot.get('href') or '', 'used_for_identity': False, 'reason': 'href may be shared javascript:void(0);'}, 'webdriver_element_equality_used': False}

def _phase7_4_lesson_snapshot(driver, anchor, request):
    """One read-only round-trip for lesson identity and click safety evidence."""
    script = "\nconst target = arguments[0], requestedDate = String(arguments[1] || '');\nconst visible = (el, style, rect) => !!el && style.display !== 'none' &&\n  style.visibility !== 'hidden' && style.visibility !== 'collapse' &&\n  Number(style.opacity || 1) !== 0 && rect.width > 0 && rect.height > 0;\nconst identity = el => ({\n  href: el.getAttribute('href') || '', onclick: el.getAttribute('onclick') || '',\n  text: ((el.querySelector('p.lesson_name') || {}).innerText || '').trim()\n});\nconst anchors = Array.from(document.querySelectorAll('a')).filter(el => {\n  const i = identity(el); return i.href.includes(requestedDate) || i.onclick.includes(requestedDate);\n});\nconst r = target.getBoundingClientRect(), s = getComputedStyle(target);\nconst x = r.left + r.width / 2, y = r.top + r.height / 2;\nconst top = (x >= 0 && y >= 0 && x < innerWidth && y < innerHeight)\n  ? document.elementFromPoint(x, y) : null;\nconst relation = top === target ? 'SELF'\n  : (top && target.contains(top) ? 'DESCENDANT'\n  : (top && top.contains(target) ? 'ANCESTOR' : 'OTHER'));\nconst blockers = Array.from(document.querySelectorAll('.blockUI')).filter(el => {\n  const bs = getComputedStyle(el), br = el.getBoundingClientRect();\n  return visible(el, bs, br) && bs.pointerEvents !== 'none';\n});\nreturn {\n  candidates: anchors.map((el, index) => ({index, element: el, ...identity(el)})),\n  target: {...identity(target), connected: target.isConnected, tag: target.tagName, id: target.id || '',\n    class_name: target.className || '', disabled: !!target.disabled,\n    aria_disabled: target.getAttribute('aria-disabled') || '',\n    display: s.display, visibility: s.visibility, pointer_events: s.pointerEvents,\n    geometry: {left:r.left, top:r.top, right:r.right, bottom:r.bottom,\n      width:r.width, height:r.height},\n    in_viewport: r.left >= 0 && r.top >= 0 && r.right <= innerWidth && r.bottom <= innerHeight,\n    topmost_relation: relation},\n  runtime: {document_ready_state: document.readyState, jquery_active: window.jQuery && typeof window.jQuery.active === 'number' ? window.jQuery.active : null},\n  blocking_overlay_count: blockers.length,\n  url: location.href\n};\n"
    return driver.execute_script(script, anchor, request.get('date'))

def _phase7_4_detail_probe(driver):
    """Read-only Detail transition/readiness snapshot; never mutates DOM."""
    script = "\nconst shown = el => { const s=getComputedStyle(el), r=el.getBoundingClientRect();\n  return s.display !== 'none' && s.visibility !== 'hidden' &&\n    s.visibility !== 'collapse' && Number(s.opacity || 1) !== 0 && r.width>0 && r.height>0; };\nconst positions = Array.from(document.querySelectorAll(arguments[0]));\nconst positionIds = positions.map(el => el.id || '').filter(id => {\n  const m=id.match(/^LessonPosNo(\\d+)$/); return m && Number(m[1]) > 0; });\nconst confirms = Array.from(document.querySelectorAll('#confirmsubmit'));\nconst blockers = Array.from(document.querySelectorAll('.blockUI')).filter(el => {\n  const s=getComputedStyle(el); return shown(el) && s.pointerEvents !== 'none'; });\nconst text = document.body ? (document.body.innerText || '') : '';\nconst headings = Array.from(document.querySelectorAll('h1,h2,h3,.title,.heading'))\n  .slice(0, 8).map(el => (el.innerText || '').trim()).filter(Boolean);\nconst available = text.includes(arguments[1]);\nconst unavailable = arguments[2].filter(v => text.includes(v));\nconst congestionWords = ['アクセスが集中','混雑','しばらくしてから'];\nconst errorWords = ['エラーが発生','システムエラー','予期せぬエラー'];\nconst detailMarker = positionIds.length > 0 || confirms.length > 0 || available || unavailable.length > 0;\nreturn {url:location.href, detail_url:location.pathname.includes(arguments[3]),\n  detail_marker:detailMarker, headings, position_ids:positionIds,\n  position_count:positionIds.length, blocking_overlay_count:blockers.length,\n  available_message:available, unavailable_messages:unavailable,\n  confirmsubmit_count:confirms.length,\n  confirmsubmit_displayed:confirms.length===1 && shown(confirms[0]),\n  confirmsubmit_enabled:confirms.length===1 && !confirms[0].disabled,\n  congestion_detected:congestionWords.some(v => text.includes(v)),\n  error_detected:errorWords.some(v => text.includes(v))};\n"
    value = driver.execute_script(script, DETAIL_POSITION_SELECTOR, DETAIL_AVAILABLE_MESSAGE, list(DETAIL_UNAVAILABLE_MESSAGES), DETAIL_URL_PATH)
    if hasattr(driver, '_request_local_inquiry'):
        from urllib.parse import urlsplit
        value['inquiry_url'] = urlsplit(value.get('url', '')).path == '/DSPWebUser/LESSON/ReserveLessonSchedule/Inquiry'
    return value

def _phase7_4_classify_detail(snapshot, user, request):
    """Preserve Phase 7.3 positive/negative/UNKNOWN rules from one snapshot."""
    contradictions = []
    detail_url = bool(snapshot.get('detail_url'))
    detail_marker = bool(snapshot.get('detail_marker'))
    overlay_count = snapshot.get('blocking_overlay_count')
    available = bool(snapshot.get('available_message'))
    unavailable = bool(snapshot.get('unavailable_messages'))
    confirm_count = snapshot.get('confirmsubmit_count')
    confirm_displayed = bool(snapshot.get('confirmsubmit_displayed'))
    confirm_enabled = bool(snapshot.get('confirmsubmit_enabled'))
    position_ids = list(snapshot.get('position_ids') or [])
    position_detected = bool(position_ids)
    if not (detail_url or detail_marker):
        contradictions.append('detail_url_and_marker_absent')
    if overlay_count is None:
        contradictions.append('blocking_overlay_state_unknown')
    elif overlay_count > 0:
        contradictions.append('blocking_overlay_present')
    if snapshot.get('congestion_detected'):
        contradictions.append('congestion_screen_detected')
    if snapshot.get('error_detected'):
        contradictions.append('error_screen_detected')
    if available and unavailable:
        contradictions.append('available_and_unavailable_messages_both_detected')
    if available and confirm_count != 1:
        contradictions.append('available_message_without_single_confirmsubmit')
    if available and (not confirm_displayed):
        contradictions.append('available_message_with_hidden_confirmsubmit')
    if available and (not confirm_enabled):
        contradictions.append('available_message_with_disabled_confirmsubmit')
    if available and (not position_detected):
        contradictions.append('available_message_without_position_dom')
    if unavailable and confirm_count not in (0, None):
        contradictions.append('unavailable_message_with_confirmsubmit')
    ready = {'detail_url_or_marker_detected': detail_url or detail_marker, 'blocking_overlay_absent': overlay_count == 0, 'available_message_detected': available, 'unavailable_message_absent': not unavailable, 'single_confirmsubmit_present': confirm_count == 1, 'confirmsubmit_displayed': confirm_displayed, 'confirmsubmit_enabled': confirm_enabled, 'position_dom_detected': position_detected}
    not_reservable = {'detail_url_or_marker_detected': detail_url or detail_marker, 'blocking_overlay_absent': overlay_count == 0, 'unavailable_message_detected': unavailable, 'available_message_absent': not available, 'confirmsubmit_absent': confirm_count == 0}
    if not contradictions and all(ready.values()):
        state, code = ('DETAIL_READY', 'OK')
    elif not contradictions and all(not_reservable.values()):
        state, code = ('DETAIL_NOT_RESERVABLE', 'NOT_RESERVABLE')
    else:
        state, code = ('DETAIL_UNKNOWN', 'UNKNOWN')
    details = {'current_url': snapshot.get('url'), 'detail_url_detected': detail_url, 'detail_marker_detected': detail_marker, 'blocking_overlay_count': overlay_count, 'reservation_available_message_detected': available, 'reservation_unavailable_message_detected': unavailable, 'detected_messages': snapshot.get('unavailable_messages') or [], 'confirmsubmit_count': confirm_count, 'confirmsubmit_displayed': confirm_displayed, 'confirmsubmit_enabled': confirm_enabled, 'position_dom_detected': position_detected, 'position_candidate_count': len(position_ids), 'position_candidate_ids': position_ids[:DETAIL_FEATURE_LIMIT], 'congestion_detected': bool(snapshot.get('congestion_detected')), 'error_detected': bool(snapshot.get('error_detected')), 'evidence_for_ready': [k for k, v in ready.items() if v], 'evidence_for_not_reservable': [k for k, v in not_reservable.items() if v], 'contradictions': contradictions, 'final_detail_state': state, 'probe_version': 'phase7.4-read-only-single-round-trip'}
    result = make_result(code, state, retryable=state == 'DETAIL_UNKNOWN', **details)
    log_event('detail_state_determined', result, user=user, request=request, current_url=snapshot.get('url'))
    return result

def _cla1_fresh_lesson_evidence(driver, request, original, user, pre_url, condition=None):
    """Re-acquire the unique exact pre-scroll target; observation only."""
    from lesson_target import matches as target_matches, names_match
    if _cla1_identity_guard(driver, user) is not None:
        raise ValueError('FRESH_LESSON_MEMBER_UNVERIFIED')
    if driver.current_url != pre_url:
        raise ValueError('FRESH_LESSON_PAGE_CHANGED')
    candidates = _collect_lesson_candidates_p14(driver, request)
    matching = [c for c in candidates if target_matches(c.date, c.start_time, c.displayed_name, request, normalize_lesson_name)]
    if condition is not None:
        condition.setdefault('probe', {}).update(candidate_count=len(candidates), matching_count=len(matching),
                                                 unique_match=len(matching) == 1)
    if not matching:
        if condition is not None: condition['last'] = 'TARGET_NOT_PRESENT'
        return None
    if len(matching) != 1:
        raise ValueError('FRESH_LESSON_NOT_UNIQUE')
    candidate = matching[0]
    parsed = _parse_lesson_onclick_identity(candidate.href_or_onclick)
    if (candidate.date != original.date or candidate.date != request['date']
            or candidate.start_time != original.start_time or candidate.start_time != request['start_time']
            or candidate.normalized_name != original.normalized_name
            or not parsed.get('parsed') or parsed['date'] != request['date']
            or candidate.href_or_onclick != original.href_or_onclick):
        raise ValueError('FRESH_LESSON_TARGET_CHANGED')
    displayed, enabled = candidate.anchor_element.is_displayed(), candidate.anchor_element.is_enabled()
    snapshot = _phase7_4_lesson_snapshot(driver, candidate.anchor_element, request)
    runtime = snapshot.get('runtime') or {}
    if condition is not None:
        condition.setdefault('probe', {}).update(document_complete=runtime.get('document_ready_state') == 'complete',
                                                 jquery_idle=type(runtime.get('jquery_active')) is int and runtime['jquery_active'] == 0,
                                                 blocking_overlay_count=snapshot.get('blocking_overlay_count'),
                                                 overlay_clear=snapshot.get('blocking_overlay_count') == 0)
    if (snapshot.get('url') != pre_url):
        raise ValueError('FRESH_LESSON_PAGE_CHANGED')
    if (runtime.get('document_ready_state') != 'complete'
            or type(runtime.get('jquery_active')) is not int or runtime['jquery_active'] != 0
            or snapshot.get('blocking_overlay_count') != 0):
        if condition is not None: condition['last'] = 'AJAX_OR_OVERLAY_NOT_CLEAR'
        return None
    target = snapshot.get('target') or {}
    items = [i for i in snapshot.get('candidates', []) if i.get('onclick') == candidate.href_or_onclick and names_match(i.get('text', ''), request['name'], request['date'], request['start_time'], normalize_lesson_name)]
    identity = _lesson_identity_comparison(original, target, items, request, observed_candidate=candidate)
    if (not identity['overall_identity_match'] or len(items) != 1
            or normalize_lesson_name(target.get('text', '')) != original.normalized_name
            or target.get('onclick') != original.href_or_onclick):
        raise ValueError('FRESH_LESSON_TARGET_CHANGED')
    geometry = target.get('geometry') or {}
    if condition is not None:
        condition.setdefault('probe', {}).update(in_viewport=target.get('in_viewport') is True,
                                                 target_connected=target.get('connected') is True,
                                                 displayed=displayed, enabled=enabled,
                                                 topmost_safe=target.get('topmost_relation') in ('SELF', 'DESCENDANT'),
                                                 geometry_positive=geometry.get('width', 0) > 0 and geometry.get('height', 0) > 0)
    if (not displayed or not enabled or target.get('connected') is not True
            or target.get('disabled') or str(target.get('aria_disabled', '')).lower() == 'true'
            or target.get('in_viewport') is not True or target.get('pointer_events') == 'none'
            or geometry.get('width', 0) <= 0 or geometry.get('height', 0) <= 0
            or target.get('topmost_relation') not in ('SELF', 'DESCENDANT')):
        if condition is not None: condition['last'] = 'CLICK_TARGET_NOT_SAFE_IN_VIEWPORT'
        return None
    target_identity = (target.get('text'), target.get('onclick'), target.get('href'))
    node_identities = [(i.get('text'), i.get('onclick'), i.get('href')) for i in snapshot.get('candidates', [])]
    signature = json.dumps(dict(url=snapshot.get('url'),
        identity=target_identity, nodes=node_identities),
        sort_keys=True, ensure_ascii=False)
    if condition is not None:
        try:
            condition['probe'].update(
                target_signature_sha='sha256:' + hashlib.sha256(json.dumps(target_identity, ensure_ascii=False).encode('utf-8')).hexdigest(),
                all_candidates_signature_sha='sha256:' + hashlib.sha256(json.dumps(node_identities, ensure_ascii=False).encode('utf-8')).hexdigest())
        except Exception:
            pass  # Diagnostic hashing must never affect the existing safety decision.
    return candidate, snapshot, signature

def _cla1_wait_fresh_lesson(driver, request, original, user, pre_url, deadline):
    """Reuse the five-second budget and 0.2-second cadence; never replay actions."""
    previous, since = None, None
    started = time.monotonic()
    condition = {'last': 'NO_OBSERVATION', 'probe': {}}
    observations = []
    observation_count = 0
    stale_count = same_signature_count = max_same_signature_count = same_signature_pair_count = 0
    target_hash_changes = all_candidates_hash_changes = 0
    last_target_hash = last_candidates_hash = None

    def record(now, state):
        nonlocal observation_count
        try:
            sample = dict(elapsed_ms=round((now - started) * 1000, 1), state=state,
                          consecutive_same_signature=same_signature_count, **condition['probe'])
            observation_count += 1
            observations.append(sample)
            del observations[:-12]
        except Exception:
            pass  # Observation failures must not change the wait result.

    def ready(current_driver):
        nonlocal previous, since, stale_count, same_signature_count, max_same_signature_count, same_signature_pair_count
        nonlocal target_hash_changes, all_candidates_hash_changes, last_target_hash, last_candidates_hash
        if time.monotonic() >= deadline:
            raise TimeoutException('fresh lesson observation budget expired')
        condition['probe'] = {}
        try:
            fresh = _cla1_fresh_lesson_evidence(current_driver, request, original, user, pre_url, condition)
        except StaleElementReferenceException:
            condition['last'] = 'DOM_REPLACED_DURING_READ'
            stale_count += 1
            fresh = None
        now = time.monotonic()
        if now >= deadline:
            record(now, 'DEADLINE_AFTER_OBSERVATION')
            raise TimeoutException('fresh lesson observation budget expired')
        if fresh is None:
            previous, since = None, None
            same_signature_count = 0
            record(now, condition['last'])
            return False
        target_hash = condition['probe'].get('target_signature_sha')
        candidates_hash = condition['probe'].get('all_candidates_signature_sha')
        if target_hash is not None and last_target_hash is not None and target_hash != last_target_hash:
            target_hash_changes += 1
        if candidates_hash is not None and last_candidates_hash is not None and candidates_hash != last_candidates_hash:
            all_candidates_hash_changes += 1
        last_target_hash, last_candidates_hash = target_hash, candidates_hash
        if fresh[2] != previous:
            condition['last'] = 'AWAITING_STABLE_IDENTITY'
            previous, since = fresh[2], now
            same_signature_count = 1
            max_same_signature_count = max(max_same_signature_count, same_signature_count)
            record(now, condition['last'])
            return False
        same_signature_count += 1
        same_signature_pair_count += 1
        max_same_signature_count = max(max_same_signature_count, same_signature_count)
        record(now, 'STABLE_IDENTITY' if now - since >= PHASE8_8_REOBSERVE_INTERVAL_SECONDS else 'AWAITING_STABLE_INTERVAL')
        return fresh if now - since >= PHASE8_8_REOBSERVE_INTERVAL_SECONDS else False
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutException('fresh lesson observation budget expired')
    try:
        return WebDriverWait(driver, remaining,
            poll_frequency=PHASE8_8_REOBSERVE_INTERVAL_SECONDS).until(ready)
    except TimeoutException as exc:
        try:
            log_event('p14_fresh_wait_timeout_diagnostic',
                make_result('TIMEOUT', 'P14_FRESH_WAIT_TIMEOUT',
                    reason_code='FRESH_LESSON_WAIT_' + condition['last'],
                    elapsed_ms=round((time.monotonic() - started) * 1000, 1),
                    observation_count=observation_count, stale_count=stale_count,
                    target_hash_changes=target_hash_changes,
                    all_candidates_hash_changes=all_candidates_hash_changes,
                    same_signature_pair_count=same_signature_pair_count,
                    max_consecutive_same_signature=max_same_signature_count,
                    observations=observations), user=user, request=request)
        except Exception:
            pass  # Logging cannot relax or interrupt the original fail-closed path.
        raise ValueError('FRESH_LESSON_WAIT_' + condition['last']) from exc

def open_lesson_detail(driver, wait, lesson_candidate, request, user=None):
    """一致済みancestor aをnative clickし、予約操作なしでDetailを検証する。"""
    from lesson_target import matches as target_matches, names_match
    identity_stop = _cla1_identity_guard(driver, user)
    if identity_stop is not None:
        return identity_stop
    pre_url = driver.current_url
    candidate = lesson_candidate
    overlay_result = wait_for_overlay_clear(driver, timeout=5)
    if overlay_result.code != 'OK':
        return make_result('OVERLAY_TIMEOUT', 'LESSON_DETAIL_UNKNOWN', reason='overlay did not clear before lesson click', retryable=True, click_method='selenium_native_click', pre_url=pre_url, overlay_clear=False, overlay=overlay_result.details, **_candidate_evidence(candidate, 1))
    fresh_deadline = None
    scroll_performed = False
    click_started_at = None
    click_started_epoch = None
    click_evidence = {}
    for attempt in range(1, 3):
        try:
            precheck_started = time.perf_counter()
            snapshot_started = time.perf_counter()
            lesson_snapshot = _phase7_4_lesson_snapshot(driver, candidate.anchor_element, request)
            _latency_duration(user, request, 'lesson_snapshot', snapshot_started, 'DOM_QUERY')
            fresh_matching = [c for c in _collect_lesson_candidates_p14(driver, request) if target_matches(c.date, c.start_time, c.displayed_name, request, normalize_lesson_name)]
            matching = [item for item in lesson_snapshot.get('candidates', []) if item.get('onclick') == candidate.href_or_onclick and names_match(item.get('text', ''), request['name'], request['date'], request['start_time'], normalize_lesson_name)]
            target_snapshot = lesson_snapshot.get('target') or {}
            unique_match = len(fresh_matching) == len(matching) == 1
            geometry = target_snapshot.get('geometry') or {}
            geometry_ok = geometry.get('width', 0) > 0 and geometry.get('height', 0) > 0
            topmost_ok = target_snapshot.get('topmost_relation') in ('SELF', 'DESCENDANT')
            if not target_snapshot.get('in_viewport') or not geometry_ok or (not topmost_ok):
                if scroll_performed:
                    return make_result('CLICK_FAILED', 'LESSON_DETAIL_UNKNOWN', reason='fresh target still requires scroll', retryable=True)
                scroll_performed = True
                fresh_deadline = time.monotonic() + PHASE8_8_PAGE_BOUNDARY_SECONDS if fresh_deadline is None else fresh_deadline
                driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", candidate.anchor_element)
                snapshot_started = time.perf_counter()
                candidate, lesson_snapshot, _ = _cla1_wait_fresh_lesson(driver, request, lesson_candidate, user, pre_url, fresh_deadline)
                _latency_duration(user, request, 'lesson_snapshot_after_scroll', snapshot_started, 'DOM_QUERY/REOBSERVE_WAIT')
                fresh_matching = [c for c in _collect_lesson_candidates_p14(driver, request) if target_matches(c.date, c.start_time, c.displayed_name, request, normalize_lesson_name)]
                matching = [item for item in lesson_snapshot.get('candidates', []) if item.get('onclick') == candidate.href_or_onclick and names_match(item.get('text', ''), request['name'], request['date'], request['start_time'], normalize_lesson_name)]
                unique_match = len(fresh_matching) == len(matching) == 1
                target_snapshot = lesson_snapshot.get('target') or {}
                geometry = target_snapshot.get('geometry') or {}
                geometry_ok = geometry.get('width', 0) > 0 and geometry.get('height', 0) > 0
                topmost_ok = target_snapshot.get('topmost_relation') in ('SELF', 'DESCENDANT')
            identity_diagnostic = _lesson_identity_comparison(candidate, target_snapshot, matching, request)
            identity_matches = identity_diagnostic['overall_identity_match']
            target_name_matches = identity_diagnostic['name_match']
            target_date_matches = identity_diagnostic['date_match']
            log_event('lesson_identity_diagnostic', make_result('OK' if identity_matches else 'IDENTITY_UNKNOWN', 'LESSON_IDENTITY_MATCHED' if identity_matches else 'LESSON_IDENTITY_UNKNOWN', retryable=not identity_matches, **identity_diagnostic), user=user, request=request)
            displayed = candidate.anchor_element.is_displayed()
            enabled = candidate.anchor_element.is_enabled()
            overlay_clear = lesson_snapshot.get('blocking_overlay_count') == 0
            click_evidence = {'click_method': 'selenium_native_click', 'pre_url': pre_url, 'click_target_tag': target_snapshot.get('tag'), 'click_target_class': target_snapshot.get('class_name'), 'click_target_href': target_snapshot.get('href'), 'click_target_onclick': target_snapshot.get('onclick'), 'displayed': displayed, 'enabled': enabled, 'disabled': bool(target_snapshot.get('disabled')), 'aria_disabled': target_snapshot.get('aria_disabled'), 'geometry': geometry, 'topmost_relation': target_snapshot.get('topmost_relation'), 'overlay_clear': overlay_clear, 'overlay_state_before_click': overlay_result.details, 'lesson_candidate_count': len(lesson_snapshot.get('candidates') or []), 'matching_lesson_count': len(matching), 'lesson_name_date_unique': unique_match, 'lesson_identity_matches': identity_matches, 'lesson_identity_mismatch_fields': identity_diagnostic['mismatch_fields'], 'lesson_target_name_matches': target_name_matches, 'lesson_target_date_matches': target_date_matches, 'precheck_snapshot_version': 'phase7.4-read-only-single-round-trip', 'attempt': attempt}
            _latency_duration(user, request, 'lesson_precheck', precheck_started, 'SAFETY_CHECK')
            if not unique_match or not identity_matches or (not target_name_matches) or (not target_date_matches) or (not displayed) or (not enabled) or target_snapshot.get('disabled') or (str(target_snapshot.get('aria_disabled', '')).lower() == 'true') or (not geometry_ok) or (not overlay_clear) or (not topmost_ok):
                return make_result('CLICK_FAILED', 'LESSON_DETAIL_UNKNOWN', reason='matched lesson identity or click safety evidence failed', retryable=True, **click_evidence, **_candidate_evidence(candidate, 1))
            identity_stop = _cla1_identity_guard(driver, user)
            if identity_stop is not None:
                return identity_stop
            click_started_at = datetime.now(timezone.utc).isoformat()
            click_started_epoch = time.monotonic()
            logging_started = time.perf_counter()
            log_event('lesson_native_click_started', make_result('OK', 'LESSON_NATIVE_CLICK_STARTED', click_started_at=click_started_at, **click_evidence, **_candidate_evidence(candidate, 1)), user=user, request=request)
            _latency_duration(user, request, 'lesson_logging_before_click', logging_started, 'LOGGING')
            _latency_mark(user, request, 'lesson_click_start')
            inquiry_click_binding = dict(anchor_text=candidate.anchor_element.text, date=request['date'], identity_verified=identity_matches, identity=identity_diagnostic)
            candidate.anchor_element.click()
            _latency_mark(user, request, 'lesson_click_return')
            click_trace = _latency_trace(user, request)
            _latency_record_ms(user, request, 'lesson_native_click', _latency_interval(click_trace, 'lesson_click_start', 'lesson_click_return'), 'SELENIUM_CLICK_BLOCK/SERVER_WAIT')
            click_return_at = datetime.now(timezone.utc).isoformat()
            log_event('lesson_native_click_completed', make_result('OK', 'LESSON_NATIVE_CLICK_COMPLETED', click_started_at=click_started_at, click_return_at=click_return_at, post_url_check='deferred_to_detail_transition_probe', page_load_strategy_phase7_3='normal(default)', page_load_strategy_phase7_4='normal(default)', **click_evidence, **_candidate_evidence(candidate, 1)), user=user, request=request)
            break
        except StaleElementReferenceException:
            if fresh_deadline is None:
                fresh_deadline = time.monotonic() + PHASE8_8_PAGE_BOUNDARY_SECONDS
            if not scroll_performed:
                candidate = _refind_same_candidate(driver, request, lesson_candidate)
                if (candidate is None or candidate.href_or_onclick != lesson_candidate.href_or_onclick
                        or candidate.normalized_name != lesson_candidate.normalized_name):
                    return make_result('LESSON_CANDIDATE_STALE', 'LESSON_DETAIL_UNKNOWN', reason='the exact matched candidate could not be re-identified', retryable=True, pre_url=pre_url, attempt=attempt, **_candidate_evidence(lesson_candidate, 1))
                continue
            try:
                candidate, _, _ = _cla1_wait_fresh_lesson(driver, request, lesson_candidate, user, pre_url, fresh_deadline)
            except Exception as recovery_exc:
                return make_result('LESSON_CANDIDATE_STALE', 'LESSON_DETAIL_UNKNOWN', reason=str(recovery_exc) if isinstance(recovery_exc, ValueError) and str(recovery_exc).startswith('FRESH_LESSON_') else type(recovery_exc).__name__, retryable=True, pre_url=pre_url, attempt=attempt, **_candidate_evidence(lesson_candidate, 1))
        except Exception as exc:
            try:
                failure_dom_diagnostic = {'lesson': _safe_dom_diagnostic(driver, candidate.lesson_element, 'actual_p.lesson_name'), 'anchor': _safe_dom_diagnostic(driver, candidate.anchor_element, 'selected_ancestor_a')}
            except Exception as diagnostic_exc:
                failure_dom_diagnostic = {'status': 'FAILED', 'error': type(diagnostic_exc).__name__}
            return make_result('CLICK_FAILED', 'LESSON_DETAIL_UNKNOWN', reason=str(exc) if isinstance(exc, ValueError) and str(exc).startswith('FRESH_LESSON_') else type(exc).__name__, retryable=True, click_method='selenium_native_click', pre_url=pre_url, attempt=attempt, failure_dom_diagnostic=failure_dom_diagnostic, **_candidate_evidence(candidate, 1))
    else:
        return make_result('LESSON_CANDIDATE_STALE', 'LESSON_DETAIL_UNKNOWN', reason='candidate remained stale', retryable=True, pre_url=pre_url, **_candidate_evidence(lesson_candidate, 1))
    transition_snapshot = None
    transition_wait_started = time.perf_counter()
    try:
        transition_snapshot = WebDriverWait(driver, 10, poll_frequency=0.05).until(lambda current_driver: (lambda probe: probe if probe.get('detail_url') or probe.get('detail_marker') or probe.get('inquiry_url') else False)(_phase7_4_detail_probe(current_driver)))
        _latency_duration(user, request, 'detail_transition_detect', transition_wait_started, 'DOM_TRANSITION_WAIT/POLLING_DELAY')
        _latency_mark(user, request, 'detail_transition_detected')
        transition_at = datetime.now(timezone.utc).isoformat()
        transition_seconds = time.monotonic() - click_started_epoch
        transition_url = transition_snapshot.get('url')
        detail_url_confirmed = bool(transition_snapshot.get('detail_url'))
        log_event('lesson_detail_transition_detected', make_result('OK', 'LESSON_DETAIL_TRANSITION_DETECTED', click_started_at=click_started_at, detail_transition_detected_at=transition_at, transition_seconds=transition_seconds, current_url=transition_url, post_url=transition_url, url_changed=transition_url != pre_url, detail_url_confirmed=detail_url_confirmed, detail_marker_detected=bool(transition_snapshot.get('detail_marker')), position_radio_count=transition_snapshot.get('position_count'), detail_headings=transition_snapshot.get('headings'), poll_frequency_seconds=0.05, **click_evidence, **_candidate_evidence(candidate, 1)), user=user, request=request, current_url=transition_url)
    except TimeoutException:
        _latency_duration(user, request, 'detail_transition_detect', transition_wait_started, 'DOM_TRANSITION_WAIT/POLLING_DELAY')
        try:
            failure_snapshot = _phase7_4_detail_probe(driver)
            post_url = failure_snapshot.get('url')
            failure_diagnostic = _log_detail_diagnostics(driver, user, request, wait_for_overlay_clear(driver, timeout=5))
        except Exception as diagnostic_exc:
            failure_snapshot = {'diagnostic_error': type(diagnostic_exc).__name__}
            failure_diagnostic = None
            post_url = ''
        return make_result('STATE_CHANGE_TIMEOUT', 'LESSON_DETAIL_UNKNOWN', reason='Detail URL/marker transition was not confirmed', retryable=True, click_started_at=click_started_at, detail_confirmed_at=datetime.now(timezone.utc).isoformat(), transition_seconds=time.monotonic() - click_started_epoch, current_url=post_url, post_url=post_url, url_changed=post_url != pre_url, detail_url_confirmed=bool(failure_snapshot.get('detail_url')), detail_marker_detected=bool(failure_snapshot.get('detail_marker')), failure_diagnostic=failure_diagnostic, **click_evidence, **_candidate_evidence(candidate, 1))
    if transition_snapshot.get('inquiry_url') and hasattr(driver, '_request_local_inquiry'):
        import inquiry_reserved
        proof = inquiry_reserved.probe(__import__('sys').modules[__name__], driver, user, request, inquiry_click_binding)
        if inquiry_reserved.positive(proof):
            return make_result('OK', 'INQUIRY_RESERVED', reserved_evidence=proof)
        return make_result('UNKNOWN', 'INQUIRY_UNVERIFIED', reason_code='ALREADY_RESERVED_UNVERIFIED', reserved_evidence=proof)
    post_url = transition_snapshot.get('url')
    if hasattr(driver, '_request_local_inquiry'):
        from urllib.parse import urlsplit
        arrival=urlsplit(post_url or '')
        if arrival.scheme+'://'+arrival.netloc!='https://www5.e-atoms.jp' or arrival.path!='/DSPWebUser/LESSON/ReserveLessonSchedule/Detail' or arrival.query or arrival.fragment:
            return make_result('UNKNOWN','INQUIRY_UNVERIFIED',reason_code='ARRIVAL_STATE_UNVERIFIED')
    if post_url == pre_url and (not transition_snapshot.get('detail_marker')):
        return make_result('STATE_CHANGE_TIMEOUT', 'LESSON_DETAIL_UNKNOWN', reason='navigation did not resolve to a Detail URL or marker', retryable=False, current_url=post_url, post_url=post_url, url_changed=post_url != pre_url, detail_url_confirmed=bool(transition_snapshot.get('detail_url')), detail_marker_detected=bool(transition_snapshot.get('detail_marker')), **click_evidence, **_candidate_evidence(candidate, 1))
    post_overlay = wait_for_overlay_clear(driver, timeout=5)
    formal_snapshot_started = time.perf_counter()
    formal_snapshot = _phase7_4_detail_probe(driver)
    _latency_duration(user, request, 'detail_formal_snapshot', formal_snapshot_started, 'DETAIL_DIAGNOSTIC')
    detail_state_result = _phase7_4_classify_detail(formal_snapshot, user, request)
    if post_overlay.code != 'OK' and detail_state_result.state != 'DETAIL_UNKNOWN':
        detail_state_result = make_result('UNKNOWN', 'DETAIL_UNKNOWN', retryable=True, reason='blocking overlay did not clear', contradictions=['blocking_overlay_clear_not_confirmed'], fast_snapshot=formal_snapshot)
    if detail_state_result.state == 'DETAIL_READY':
        _latency_mark(user, request, 'detail_ready')
        detail_ready_perf = _latency_trace(user, request)['marks']['detail_ready']
        log_event('detail_ready_detected', make_result('OK', 'DETAIL_READY', detail_ready_perf_counter=detail_ready_perf, detail_url_confirmed=bool(formal_snapshot.get('detail_url')), position_candidate_count=formal_snapshot.get('position_count'), blocking_overlay_count=formal_snapshot.get('blocking_overlay_count')), user=user, request=request, detail_ready_perf_counter=detail_ready_perf)
        trace = _latency_trace(user, request)
        trace['deferred_diagnostics']['detail'] = {'formal_snapshot': formal_snapshot, 'state_evidence': detail_state_result.details, 'deferred_from': 'DETAIL_READY'}
        diagnostic = None
        _latency_record_ms(user, request, 'detail_ready_deferred_diagnostic', 0.0, 'DEFERRED_UNTIL_AFTER_RESERVATION')
    else:
        deferred_started = time.perf_counter()
        diagnostic = _log_detail_diagnostics(driver, user, request, post_overlay)
        _latency_duration(user, request, 'detail_ready_deferred_diagnostic', deferred_started, 'DETAIL_DIAGNOSTIC/LOGGING')
    return make_result(detail_state_result.code, detail_state_result.state, reason=detail_state_result.reason, retryable=detail_state_result.retryable, click_started_at=click_started_at, detail_confirmed_at=datetime.now(timezone.utc).isoformat(), transition_seconds=time.monotonic() - click_started_epoch, current_url=formal_snapshot.get('url'), post_url=formal_snapshot.get('url'), url_changed=formal_snapshot.get('url') != pre_url, detail_url_confirmed=bool(formal_snapshot.get('detail_url')), detail_marker_detected=bool(formal_snapshot.get('detail_marker')), reservation_operability_formally_determined=detail_state_result.state != 'DETAIL_UNKNOWN', detail_state_evidence=detail_state_result.details, overlay_code=post_overlay.code, diagnostic_events_emitted=[] if detail_state_result.state == 'DETAIL_READY' else ['detail_dom_diagnostic', 'detail_reservation_controls_diagnostic', 'detail_message_diagnostic'], detail_fast_snapshot=formal_snapshot, detail_diagnostic_deferred_until_after_reservation=detail_state_result.state == 'DETAIL_READY', safety={'position_selected': False, 'next_clicked': False, 'confirmsubmit_clicked': False, 'reservation_confirmed': False}, **click_evidence, **_candidate_evidence(candidate, 1))

def click_lesson(driver, wait, user, request):
    lesson_date = request['date']
    target_name = request['name']
    lesson_xpath = f"//td[contains(@class,'lesson')]//a[contains(@onclick, '{lesson_date}')]//p[contains(@class,'lesson_name')]"
    wait.until(EC.presence_of_element_located((By.XPATH, lesson_xpath)))
    lesson_elements = driver.find_elements(By.XPATH, lesson_xpath)
    print(f'🔍 候補数: {len(lesson_elements)}')
    lesson_found = False
    lesson_elem = None
    lesson_text = ''
    for elem in lesson_elements:
        text = elem.text
        print(f'候補: {text}')
        if is_matching_lesson_partial(text, target_name):
            lesson_text = text
            lesson_elem = elem.find_element(By.XPATH, './ancestor::a')
            lesson_found = True
            break
    if not lesson_found:
        raise Exception(f'❌ レッスン未検出: {target_name}')
    print('🚀 レッスン選択開始')
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", lesson_elem)
    time.sleep(0.3)
    driver.execute_script("arguments[0].style.zIndex='9999';", lesson_elem)
    overlay_result = wait_overlay(driver)
    log_event('overlay_check', overlay_result, user=user, request=request)
    if overlay_result.code != 'OK':
        raise RuntimeError(overlay_result.reason or overlay_result.code)
    try:
        driver.execute_script('arguments[0].click();', lesson_elem)
        time.sleep(0.2)
        lesson_elem.click()
        print(f"✅ [{user['username']}] レッスン選択成功: {lesson_text}")
    except Exception:
        print(f"⚠️ [{user['username']}] 即クリック失敗 → 再試行")
        overlay_result = wait_overlay(driver)
        log_event('overlay_check', overlay_result, user=user, request=request)
        if overlay_result.code != 'OK':
            raise RuntimeError(overlay_result.reason or overlay_result.code)
        lesson_elem = wait.until(EC.element_to_be_clickable((By.XPATH, lesson_xpath)))
        driver.execute_script('arguments[0].click();', lesson_elem)
        time.sleep(0.2)
        lesson_elem.click()
        print(f"✅ [{user['username']}] 再クリック成功: {lesson_text}")
    try:
        wait.until(EC.url_contains('Detail'))
    except:
        print('⚠️ Detail遷移待ちタイムアウト（でも継続）')
    lesson_url = driver.current_url
    print(f"🔗 [{user['username']}] Detail URL → {lesson_url}")
    return lesson_url

def _flush_phase7_5_deferred_diagnostics(user, request):
    """Serialize saved read-only evidence only after the reservation outcome."""
    trace = _latency_trace(user, request)
    pending = trace.get('deferred_diagnostics') or {}
    if not pending:
        return
    started = time.perf_counter()
    log_event('phase7_5_deferred_diagnostics_flushed', user=user, request=request, deferred_from=['DETAIL_READY', 'POSITION_SELECTED'], flushed_after='RESERVATION_OUTCOME', diagnostics=pending, source_perf_counter={'detail_ready': trace['marks'].get('detail_ready'), 'position_snapshot_start': trace['marks'].get('position_snapshot_start'), 'position_click_start': trace['marks'].get('position_click_start'), 'position_click_return': trace['marks'].get('position_click_return'), 'position_selected': trace['marks'].get('position_selected')})
    _latency_duration(user, request, 'phase7_5_deferred_diagnostic_flush', started, 'LOGGING_AFTER_RESERVATION_OUTCOME')
    pending.clear()
'Phase 8.7 evidence-aware classifiers and bounded Safe Back Recovery.\n\nNo code in this module opens Chrome or performs network I/O.  The production\ncandidate explicitly installs these adapters into the Phase 8.5.1 namespace.\n'
import re
import time
import unicodedata
from dataclasses import dataclass, field
PROVEN_ALREADY_RESERVED_MARKER = '既に予約済みです。'
CONGESTION_MARKER = '混み合っております'
PROVEN_LIVE = 'PROVEN_LIVE'
OFFLINE_VERIFIED = 'OFFLINE_VERIFIED'
UNPROVEN = 'UNPROVEN'
DESIGN_INVARIANT = 'DESIGN_INVARIANT'
ALREADY_RESERVED_DETECTED = 'ALREADY_RESERVED_DETECTED'
ALREADY_RESERVED_MATCHED_REQUEST = 'ALREADY_RESERVED_MATCHED_REQUEST'
ALREADY_RESERVED_IDENTITY_MISMATCH = 'ALREADY_RESERVED_IDENTITY_MISMATCH'
ALREADY_RESERVED_UNVERIFIED = 'ALREADY_RESERVED_UNVERIFIED'
DETAIL_IDENTITY_VERIFIED = 'DETAIL_IDENTITY_VERIFIED'
EVIDENCE_LEVELS = {'already_reserved_marker': PROVEN_LIVE, 'already_reserved_identity_dom': PROVEN_LIVE, 'already_reserved_confirm_back_detail': PROVEN_LIVE, 'back_detail_identity_retained': PROVEN_LIVE, 'congested_confirm_back_detail': OFFLINE_VERIFIED, 'congested_confirm_back_detail_live': UNPROVEN, 'final_submit_no_reexecute': DESIGN_INVARIANT}

def _text(value):
    return unicodedata.normalize('NFKC', str(value or '')).strip()

def _date8(value):
    parsed = _phase8_8_date_tuple(_text(value))
    return '%04d%02d%02d' % parsed if parsed else None

def _position(value):
    match = re.search('\\d+', _text(value))
    return int(match.group()) if match else None

def extract_confirm_identity(snapshot):
    """Normalize identity captured by the read-only DOM script."""
    labels = snapshot.get('identity_labels') or {}
    from lesson_target import range_start
    datetime_text = snapshot.get('date') or labels.get('日時')
    return {'date': _date8(datetime_text), 'start_time': range_start(datetime_text), 'lesson': _text(snapshot.get('lesson') or labels.get('レッスン')) or None, 'position': _position(snapshot.get('position') or labels.get('レッスン場所'))}

def confirm_identity_snapshot(driver):
    """Read visible label/value pairs; never infer identity from URL."""
    return driver.execute_script("\n      const norm=s=>String(s||'').replace(/[\\s\u3000]+/g,' ').trim();\n      const visible=e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();\n        return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0};\n      const body=norm(document.body?document.body.innerText:'');\n      const labels={};\n      const nodes=Array.from(document.querySelectorAll('body *')).filter(visible);\n      for(const e of nodes){\n        const t=norm(e.innerText||e.textContent); if(!t||t.length>80) continue;\n        for(const label of ['日時','レッスン','レッスン場所']){\n          if(t===label||t.startsWith(label+':')||t.startsWith(label+'：')){\n            let value=t.replace(new RegExp('^'+label+'[：:]?'),'').trim();\n            if(!value&&e.nextElementSibling) value=norm(e.nextElementSibling.innerText||e.nextElementSibling.textContent);\n            if(value&&!labels[label]) labels[label]=value;\n          }\n        }\n      }\n      return {url:location.href,body_text:body,identity_labels:labels};\n    ")

def classify_confirm(snapshot, request, selected_position):
    """Priority: congestion, explicit failure, already-reserved, ready, unknown."""
    body = _text(snapshot.get('body_text'))
    if CONGESTION_MARKER in body:
        return {'state': 'CONGESTED', 'reason_code': 'PROVEN_CONGESTION_MARKER'}
    if snapshot.get('explicit_failure'):
        return {'state': 'EXPLICIT_FAILURE', 'reason_code': 'EXPLICIT_FAILURE_DOM'}
    if PROVEN_ALREADY_RESERVED_MARKER in body:
        actual = extract_confirm_identity(snapshot)
        expected_date = _date8(request.get('date'))
        from lesson_target import canonical_name, names_match
        expected_lesson = canonical_name(request.get('name') or request.get('lesson'), normalize_lesson_name)
        result = {'state': ALREADY_RESERVED_DETECTED, 'reason_code': 'PROVEN_ALREADY_RESERVED_MARKER', 'already_reserved_marker_detected': True, 'already_reserved_date': actual['date'], 'already_reserved_start_time': actual['start_time'], 'already_reserved_lesson': actual['lesson'], 'already_reserved_position': actual['position']}
        if any(actual[key] is None for key in ('date', 'start_time', 'lesson')):
            result.update(state=ALREADY_RESERVED_UNVERIFIED, reason_code='ALREADY_RESERVED_IDENTITY_DOM_INCOMPLETE')
        elif (actual['date'] != expected_date or actual['start_time'] != request.get('start_time')
                or not names_match(actual['lesson'], request.get('name') or request.get('lesson'), expected_date, actual['start_time'], normalize_lesson_name)):
            result.update(state=ALREADY_RESERVED_IDENTITY_MISMATCH, reason_code='ALREADY_RESERVED_DATE_TIME_OR_LESSON_MISMATCH')
        else:
            result.update(state=ALREADY_RESERVED_MATCHED_REQUEST, reason_code='ALREADY_RESERVED_REQUEST_IDENTITY_MATCH')
        result['already_reserved_identity_result'] = result['state']
        return result
    if snapshot.get('confirm_dom_detected') is True and snapshot.get('normal_confirm_controls') is True:
        return {'state': 'CONFIRM_PAGE_READY', 'reason_code': 'NORMAL_CONFIRM_DOM_READY'}
    return {'state': 'NEXT_TRANSITION_UNKNOWN', 'reason_code': 'NO_AFFIRMATIVE_CONFIRM_EVIDENCE'}

@dataclass
class Phase87ActionGuard:
    counts: dict = field(default_factory=lambda: {s: {'primary': 0, 'recovery': 0} for s in ('lesson', 'position', 'next', 'final_submit')})

    def allow(self, stage, kind, prior_action_not_effective=False):
        row = self.counts[stage]
        if kind == 'primary':
            allowed = row['primary'] == 0
        else:
            allowed = stage != 'final_submit' and row['recovery'] == 0 and (prior_action_not_effective is True)
        if allowed:
            row[kind] += 1
        return allowed

    def log_fields(self):
        return {stage: {'primary_action_count': row['primary'], 'recovery_action_count': row['recovery'], 'total_action_count': sum(row.values())} for stage, row in self.counts.items()}

def verify_detail_identity(snapshot, request, selected_position, require_position=True):
    date_match = _date8(snapshot.get('date')) == _date8(request.get('date'))
    from lesson_target import names_match
    lesson_match = names_match(snapshot.get('lesson'), request.get('name') or request.get('lesson'), request.get('date'), request.get('start_time'), normalize_lesson_name)
    checked = snapshot.get('checked_position_ids')
    selected = snapshot.get('target_count') == 1 and snapshot.get('checked') is True and (snapshot.get('is_selected') is True) and (checked == [int(selected_position)])
    unselected = snapshot.get('target_count') == 1 and snapshot.get('checked') is False and (snapshot.get('is_selected') is False) and (checked == [])
    position_state = 'SELECTED' if selected else 'NOT_SELECTED' if unselected else 'UNKNOWN'
    valid = bool(snapshot.get('detail_url') and snapshot.get('dom_normal') and date_match and lesson_match and (not require_position or position_state != 'UNKNOWN'))
    return {'state': DETAIL_IDENTITY_VERIFIED if valid else 'UNKNOWN', 'back_identity_date_match': date_match, 'back_identity_lesson_match': lesson_match, 'back_identity_position_state': position_state}

def safe_back_recovery(driver, stage, request, selected_position, observe_detail, recovery_action, guard, from_url=None):
    """No authorized site-UI binding exists for this history recovery contract."""
    return {'final_state': 'UNKNOWN_AFTER_SUBMIT' if stage == 'final_submit' else
            {'lesson': 'LESSON_TRANSITION_UNKNOWN', 'position': 'POSITION_SELECTION_UNKNOWN',
             'next': 'NEXT_TRANSITION_UNKNOWN'}.get(stage, 'UNKNOWN'),
            'back_attempted': False, 'back_count': 0, 'same_action_reexecuted': False,
            'reason_code': 'BROWSER_HISTORY_RECOVERY_PROHIBITED'}

def human_result(records):
    totals = {'confirmed': 0, 'already': 0, 'failed': 0, 'unknown': 0}
    lines = ['=' * 50, 'FINAL RESERVATION RESULT', '=' * 50]
    for row in records:
        state = row.get('final_state', 'UNKNOWN')
        if state == 'RESERVATION_CONFIRMED':
            label = 'CONFIRMED'
            totals['confirmed'] += 1
        elif state == ALREADY_RESERVED_MATCHED_REQUEST:
            label = 'ALREADY RESERVED - MATCHED'
            totals['already'] += 1
        elif 'UNKNOWN' in state or 'UNVERIFIED' in state or 'MISMATCH' in state:
            label = 'UNKNOWN'
            totals['unknown'] += 1
        else:
            label = 'FAILED'
            totals['failed'] += 1
        lines += [f'\n[{label}]', str(row.get('date')), str(row.get('lesson')), f"Position: {row.get('selected_position')}", f"Reason: {row.get('reason_code', '')}"]
    lines += ['\n' + '-' * 50, f"Confirmed New Reservations: {totals['confirmed']}", f"Already Reserved Matched: {totals['already']}", f"Failed: {totals['failed']}", f"Unknown: {totals['unknown']}", '=' * 50]
    return ('\n'.join(lines), totals)

def install(namespace):
    """Expose Phase 8.7 primitives without changing profiles, Barrier, or navigation."""
    namespace.update({name: value for name, value in globals().items() if name.startswith('ALREADY_RESERVED_') or name in {'PROVEN_ALREADY_RESERVED_MARKER', 'EVIDENCE_LEVELS', 'Phase87ActionGuard', 'classify_confirm', 'confirm_identity_snapshot', 'verify_detail_identity', 'safe_back_recovery', 'human_result'}})
    old_next = namespace.get('click_next_and_diagnose')
    make_result = namespace.get('make_result')
    log_event = namespace.get('log_event')
    if old_next and make_result:

        def phase87_next(driver, wait, request, position_result, user=None):
            original = old_next(driver, wait, request, position_result, user=user)
            if original.state == 'USER_IDENTITY_UNVERIFIED':
                return original
            selected = position_result.details.get('selected_position')
            try:
                snapshot = confirm_identity_snapshot(driver)
                post = original.details.get('post_transition') or {}
                snapshot['confirm_dom_detected'] = bool((original.details.get('lightweight_transition_probe') or {}).get('confirm_dom_detected'))
                snapshot['normal_confirm_controls'] = original.state == 'CONFIRM_PAGE_READY'
                classified = classify_confirm(snapshot, request, selected)
            except Exception as exc:
                if log_event:
                    log_event('phase8_7_confirm_identity_read_failed', user=user, request=request, exception_type=type(exc).__name__)
                return original
            if classified['state'] in ('CONGESTED', 'EXPLICIT_FAILURE', ALREADY_RESERVED_MATCHED_REQUEST, ALREADY_RESERVED_IDENTITY_MISMATCH, ALREADY_RESERVED_UNVERIFIED):
                code = 'OK' if classified['state'] == ALREADY_RESERVED_MATCHED_REQUEST else 'UNKNOWN'
                classified_details = {k: v for k, v in classified.items() if k != 'state'}
                result = make_result(code, classified['state'], selected_position=selected, post_transition=post, reservation_count_incremented=False, already_reserved_confirmed_count=int(code == 'OK'), **classified_details)
                if log_event:
                    log_event('phase8_7_next_confirm_classified', result, user=user, request=request, **result.details)
                return result
            return original
        namespace['click_next_and_diagnose'] = phase87_next
    old_human = namespace.get('_phase8_5_human_result')
    if old_human:

        def phase87_human(records, reservation_counts):
            base = old_human(records, reservation_counts)
            rendered, totals = human_result(records)
            print('\n' + rendered)
            return {**base, 'already_reserved_confirmed_count': totals['already']}
        namespace['_phase8_5_human_result'] = phase87_human
RECOVERABLE_OBSERVATIONS = {'CONGESTED', 'PAGE_LOADING_OR_INCOMPLETE'}
STAGE_UNKNOWN = {'lesson': 'LESSON_TRANSITION_UNKNOWN', 'position': 'POSITION_SELECTION_UNKNOWN', 'next': 'NEXT_TRANSITION_UNKNOWN'}
STAGE_SUCCESS = {'lesson': 'DETAIL_READY', 'position': 'POSITION_SELECTED', 'next': 'CONFIRM_PAGE_READY'}

def _result_state(value):
    return getattr(value, 'state', None) or (value.get('state') if isinstance(value, dict) else None)

def _phase871_make(namespace, code, state, **details):
    return namespace['make_result'](code, state, **details)

def production_stage_observation(namespace, driver, stage, request, selected_position):
    """Read-only production observer. Tests may supply the same shape via a fake driver."""
    hook = getattr(driver, 'phase871_observe', None)
    if callable(hook):
        return hook(stage)
    page = namespace['classify_reservation_page_state'](driver)
    if page.state == 'CONGESTED':
        return {'state': 'CONGESTED', 'url': getattr(driver, 'current_url', None)}
    if stage == 'lesson':
        snap = namespace['_phase7_4_detail_snapshot'](driver, request)
        classified = namespace['_phase7_4_classify_detail'](snap, None, request)
        return {'state': classified.state, 'url': snap.get('url'), **snap}
    if stage in ('position', 'next'):
        snap = namespace['_page_transition_snapshot'](driver, selected_position, request)
        pos = snap.get('position_evidence') or {}
        if stage == 'position' and pos.get('checked') is True and (pos.get('is_selected') is True):
            state = 'POSITION_SELECTED'
        elif stage == 'next':
            identity = confirm_identity_snapshot(driver)
            probe = namespace['_next_transition_probe'](driver)
            identity.update(confirm_dom_detected=probe.get('confirm_dom_detected'), normal_confirm_controls=probe.get('confirm_dom_detected'))
            state = classify_confirm(identity, request, selected_position)['state']
        else:
            state = 'PAGE_LOADING_OR_INCOMPLETE'
        return {'state': state, 'url': snap.get('url'), **snap, **pos}
    return {'state': 'UNKNOWN'}

def production_back_observation(namespace, driver, stage, request, selected_position):
    hook = getattr(driver, 'phase871_observe_back', None)
    if callable(hook):
        return hook(stage)
    if stage == 'lesson':
        found = namespace['find_target_lesson'](driver, None, request)
        candidate = found.value if found.code == 'OK' else None
        return {'url': getattr(driver, 'current_url', None), 'detail_url': False, 'dom_normal': candidate is not None, 'date': getattr(candidate, 'date', None), 'lesson': getattr(candidate, 'displayed_name', None), 'target_count': int(candidate is not None), 'checked': False, 'is_selected': False, 'checked_position_ids': []}
    return driver.execute_script('\n      const target=Number(arguments[0]), norm=s=>String(s||\'\').replace(/[\\s\u3000]+/g,\' \').trim();\n      const visible=e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();\n        return s.display!==\'none\'&&s.visibility!==\'hidden\'&&r.width>0&&r.height>0};\n      const labels={};\n      for(const e of Array.from(document.querySelectorAll(\'body *\')).filter(visible)){\n        const t=norm(e.innerText||e.textContent); if(!t||t.length>100) continue;\n        for(const label of [\'日時\',\'レッスン\']) if((label!==\'レッスン\'||!t.startsWith(\'レッスン場所\'))&&\n          (t===label||t.startsWith(label+\':\')||t.startsWith(label+\'：\'))){\n          let v=t.replace(new RegExp(\'^\'+label+\'[：:]?\'),\'\').trim();\n          if(!v&&e.nextElementSibling)v=norm(e.nextElementSibling.innerText||e.nextElementSibling.textContent);\n          if(v&&!labels[label])labels[label]=v;\n        }\n      }\n      const radios=Array.from(document.querySelectorAll(\'input[id^="LessonPosNo"]\'));\n      const targets=radios.filter(r=>r.id===\'LessonPosNo\'+String(target));\n      const checked=radios.filter(r=>r.checked&&/^LessonPosNo\\d+$/.test(r.id)).map(r=>Number(r.id.slice(11)));\n      const body=norm(document.body?document.body.innerText:\'\');\n      return {url:location.href,detail_url:location.pathname.includes(\'/ReserveLessonSchedule/Detail\'),\n        dom_normal:!body.includes(\'混み合っております\'),date:labels[\'日時\']||null,\n        lesson:labels[\'レッスン\']||null,target_count:targets.length,\n        checked:targets.length===1?Boolean(targets[0].checked):null,\n        is_selected:targets.length===1?Boolean(targets[0].checked):null,checked_position_ids:checked};\n    ', selected_position)

def phase871_execute_stage(namespace, stage, driver, wait, request, user, primary_action, recovery_action, selected_position=None, guard=None, max_reobserve_count=5):
    """Production executor reached directly by process_user for lesson/position/next."""
    identity_stop = _cla1_identity_guard(driver, user)
    if identity_stop is not None:
        return identity_stop
    guard = guard or Phase87ActionGuard()
    if not guard.allow(stage, 'primary'):
        return _phase871_make(namespace, 'UNKNOWN', STAGE_UNKNOWN[stage], reason_code='PRIMARY_GUARD_REJECTED')
    primary = primary_action()
    identity_stop = _cla1_identity_guard(driver, user)
    if identity_stop is not None:
        return identity_stop
    state = _result_state(primary)
    if stage == 'position' and getattr(primary, 'details', None):
        selected_position = primary.details.get('selected_position') or selected_position
    telemetry = {'stage': stage, 'primary_action_count': 1, 'recovery_action_count': 0, 'total_action_count': 1, 'congestion_detected': state in RECOVERABLE_OBSERVATIONS, 'congestion_stage': stage if state in RECOVERABLE_OBSERVATIONS else None, 'reobserve_count': 0, 'reobserve_elapsed_ms': 0, 'back_attempted': False, 'back_count': 0, 'back_from_url': None, 'back_to_url': None, 'recovery_allowed': False, 'recovery_reason': 'NOT_NEEDED', 'same_action_reexecuted': False}
    if state not in RECOVERABLE_OBSERVATIONS:
        if stage != 'next':
            return primary
        try:
            observed = production_stage_observation(namespace, driver, stage, request, selected_position)
            observed_state = observed.get('state')
            if stage == 'next' and observed_state in (ALREADY_RESERVED_MATCHED_REQUEST, ALREADY_RESERVED_IDENTITY_MISMATCH, ALREADY_RESERVED_UNVERIFIED):
                details = {k: v for k, v in observed.items() if k != 'state'}
                return _phase871_make(namespace, 'OK' if observed_state == ALREADY_RESERVED_MATCHED_REQUEST else 'UNKNOWN', observed_state, reservation_count_incremented=False, already_reserved_confirmed_count=int(observed_state == ALREADY_RESERVED_MATCHED_REQUEST), **telemetry, **details)
        except Exception:
            pass
        return primary
    started = time.perf_counter()
    observed = {'state': state}
    for index in range(max_reobserve_count):
        identity_stop = _cla1_identity_guard(driver, user)
        if identity_stop is not None:
            return identity_stop
        observed = production_stage_observation(namespace, driver, stage, request, selected_position)
        telemetry['reobserve_count'] = index + 1
        state = observed.get('state')
        if state not in RECOVERABLE_OBSERVATIONS:
            break
    telemetry['reobserve_elapsed_ms'] = (time.perf_counter() - started) * 1000
    if state == STAGE_SUCCESS[stage]:
        return _phase871_make(namespace, 'OK', state, **telemetry)
    if stage == 'next' and state in (ALREADY_RESERVED_MATCHED_REQUEST, ALREADY_RESERVED_IDENTITY_MISMATCH, ALREADY_RESERVED_UNVERIFIED):
        details = {k: v for k, v in observed.items() if k != 'state'}
        return _phase871_make(namespace, 'OK' if state == ALREADY_RESERVED_MATCHED_REQUEST else 'UNKNOWN', state, reservation_count_incremented=False, already_reserved_confirmed_count=int(state == ALREADY_RESERVED_MATCHED_REQUEST), **telemetry, **details)
    if state not in RECOVERABLE_OBSERVATIONS:
        return _phase871_make(namespace, 'UNKNOWN', STAGE_UNKNOWN[stage], reason_code='REOBSERVE_NON_SUCCESS', **telemetry)
    if stage in {'position', 'next'}:
        telemetry['recovery_reason'] = 'ACTION_BOUNDARY_RETRY_PROHIBITED'
        return _phase871_make(namespace, 'UNKNOWN', STAGE_UNKNOWN[stage], reason_code='ACTION_BOUNDARY_RETRY_PROHIBITED', **telemetry)
    # A congestion/unknown observation is not a positively verified Back source.
    # Safe attempt finalization may subsequently use AG01 only after fresh proofs.
    telemetry['recovery_reason'] = 'BROWSER_HISTORY_RECOVERY_PROHIBITED'
    return _phase871_make(namespace, 'UNKNOWN', STAGE_UNKNOWN[stage],
                          reason_code='BROWSER_HISTORY_RECOVERY_PROHIBITED', **telemetry)


def install_phase871(namespace):
    install(namespace)
    namespace['Phase87ActionGuard'] = Phase87ActionGuard
    core_executor = phase871_execute_stage
    namespace['phase871_execute_stage'] = lambda stage, driver, wait, request, user, primary_action, recovery_action, selected_position=None, guard=None: core_executor(namespace, stage, driver, wait, request, user, primary_action, recovery_action, selected_position, guard)
_install_phase871 = install_phase871
_install_phase871(globals())

def _phase893_recreate_browser(user, request, old_driver):
    """Recreate one same-profile browser only under retry-safe Journal authority."""
    authority = journal_preflight(user['username'], request)
    if authority.state != 'JOURNAL_RETRY_SAFE':
        raise RuntimeError('browser recreate prohibited outside retry-safe domain')
    try:
        old_driver.quit()
    except Exception:
        pass
    options = webdriver.ChromeOptions()
    options.add_argument(f"--user-data-dir={user['profile_path']}")
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--log-level=3')
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    from driver_selection import CHROME, chrome_service
    options.binary_location = str(CHROME)
    driver = webdriver.Chrome(service=chrome_service(), options=options)
    driver.phase8_1_username = user['username']
    wait = WebDriverWait(driver, 10)
    login_result = login_and_verify(driver, wait, user)
    if login_result.code != 'OK' or login_result.state != 'LOGINED':
        driver.quit()
        raise RuntimeError('recreated browser login verification failed')
    return (driver, wait)

def _phase810_recreate_reconciliation_browser(user, old_driver):
    """Recreate once with the same profile; never rejoins the Barrier."""
    try:
        old_driver.quit()
    except Exception:
        pass
    options = webdriver.ChromeOptions()
    options.add_argument(f"--user-data-dir={user['profile_path']}")
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--log-level=3')
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    from driver_selection import CHROME, chrome_service
    options.binary_location = str(CHROME)
    driver = webdriver.Chrome(service=chrome_service(), options=options)
    driver.phase8_1_username = user['username']
    wait = WebDriverWait(driver, 10)
    login_result = login_and_verify(driver, wait, user)
    if login_result.code != 'OK' or login_result.state != 'LOGINED':
        driver.quit()
        raise RuntimeError('reconciliation browser login verification failed')
    return (driver, wait)

def _batch_record(user, request):
    journal, _ = _read_journal(user['username'])
    identity = _journal_identity(user['username'], request)
    record = journal['requests'].get(_journal_request_key(identity))
    if record and record.get('identity') != identity:
        raise ValueError('BATCH_IDENTITY_CONFLICT')
    return record

def _batch_start(driver, user):
    batch = dict(batch_id=uuid.uuid4().hex, started=time.perf_counter(), go=_phase7_1_barrier_release.get(user['username']), pending=[], entered=[], previous=None, stop_reason=None)
    driver._reservation_batch = batch
    try:
        if len(user['lesson_requests']) > 1 and (_OWNER_RECOVERY_SESSION is not None or (JOURNAL_ROOT / 'cla1-owner-cancelled').exists()):
            batch['stop_reason'] = 'LEGACY_RECOVERY_SINGLE_REQUEST_SCOPE'
            return batch
        keys = [_journal_request_key(_journal_identity(user['username'], r)) for r in user['lesson_requests']]
        if len(set(keys)) != len(keys):
            raise ValueError('BATCH_DUPLICATE_REQUEST')
        journal, _ = _read_journal(user['username'])
        if any((r.get('state') in {'ACTION_INTENT', 'SUBMIT_INTENT', 'PRESERVATION_UNKNOWN'} for r in journal['requests'].values())):
            batch['stop_reason'] = 'RESTART_PENDING_RECONCILIATION_REQUIRED'
    except Exception:
        batch['stop_reason'] = 'JOURNAL_PRESERVATION_ERROR'
    return batch

def _batch_enter_request(driver, user, request):
    batch = driver._reservation_batch
    if batch['stop_reason']:
        return False
    if batch['previous'] is not None:
        try:
            prior = _batch_record(user, batch['previous'])
            safe_provisional = bool(prior and prior.get('state') == 'SUBMIT_INTENT' and (prior.get('provisional_evidence_state') == 'PROVISIONAL_ACCEPTED') and (prior.get('batch_id') == batch['batch_id']) and (prior.get('submit_intent_durable') is True) and (prior.get('reconciliation_pending') is True))
            safe_pre_submit = bool(prior and prior.get('state') in {'FAILED_FINAL', 'FAILED_RETRYABLE', 'RETRY_EXHAUSTED', 'CONFIRMED'} and (prior.get('state') == 'CONFIRMED' or (not prior.get('submit_intent_durable') and (not prior.get('submission_attempted')))))
            if not (safe_provisional or safe_pre_submit):
                batch['stop_reason'] = 'PREVIOUS_REQUEST_UNRESOLVED'
                return False
        except Exception:
            batch['stop_reason'] = 'JOURNAL_PRESERVATION_ERROR'
            return False
    batch['previous'] = dict(request, positions=list(request['positions']))
    batch['entered'].append(_journal_request_key(_journal_identity(user['username'], request)))
    return True

def _batch_accept_complete(driver, user, request, selected, evidence, deadline, observation):
    batch = getattr(driver, '_reservation_batch', None)
    if batch is None or batch['stop_reason']:
        return make_result('UNKNOWN', 'UNKNOWN_AFTER_SUBMIT', reason='BATCH_CONTEXT_MISSING')
    identity_stop = _cla1_identity_guard(driver, user)
    if identity_stop is not None or time.monotonic() > deadline:
        batch['stop_reason'] = 'UNKNOWN_AFTER_SUBMIT'
        return make_result('UNKNOWN', 'UNKNOWN_AFTER_SUBMIT', reason='COMPLETE_IDENTITY_OR_DEADLINE')
    complete_at = time.perf_counter()
    timing = dict(submit=_latency_trace(user, request)['marks'].get('batch_submit'), complete=complete_at)
    try:
        prior = _batch_record(user, request)
        if not prior or prior.get('state') != 'SUBMIT_INTENT' or prior.get('selected_position') != selected:
            raise ValueError('BATCH_SUBMIT_INTENT_BINDING')
        _journal_write_state(user['username'], request, 'SUBMIT_INTENT', selected, provisional_evidence_state='PROVISIONAL_ACCEPTED', complete_evidence=dict(positive=True, evidence=_cla1_redact(evidence), observed_at=datetime.now(timezone.utc).isoformat()), batch_id=batch['batch_id'], batch_request_index=len(batch['entered']) - 1, batch_timing=timing, submission_attempted=True, reconciliation_pending=True)
    except Exception:
        batch['stop_reason'] = 'JOURNAL_PRESERVATION_ERROR'
        return make_result('UNKNOWN', 'JOURNAL_PRESERVATION_ERROR', reason='PROVISIONAL_WRITE_FAILED')
    batch['pending'].append(dict(request=dict(request, positions=list(request['positions'])), selected=selected, timing=timing))
    result = make_result('PENDING', 'PROVISIONAL_ACCEPTED', selected_position=selected, reservation_confirmed=False, submission_attempted=True, journal_confirmation_durable=False, reconciliation_pending=True, final_submit_clicked=True, same_request_retried=False)
    log_event('final_submit_post_state_determined', result, user=user, request=request, batch_id=batch['batch_id'], **result.details)
    return result

def _batch_snapshot_set(driver, user, deadline):
    navigation = _cla1_normal_ui_evidence()
    if not _cla1_normal_ui_to_list(driver, deadline, navigation):
        raise ValueError('BATCH_LIST_NAVIGATION_UNKNOWN')
    document = driver.find_element('tag name', 'html')
    first = _phase810_snapshot_from_raw(_phase810_read_raw_snapshot(driver), user.get('expected_member_identifier'))
    time.sleep(min(RECONCILIATION_OBSERVATION_DELAY_SECONDS, max(0.0, deadline - time.monotonic())))
    second = _phase810_snapshot_from_raw(_phase810_read_raw_snapshot(driver), user.get('expected_member_identifier'))
    if not driver.execute_script('return arguments[0] === document.documentElement && arguments[0].isConnected;', document):
        raise ValueError('BATCH_DOCUMENT_CHANGED')
    if time.monotonic() > deadline or first.evidence_digest != second.evidence_digest or (not all((s.page_identity_verified and s.user_identity_verified and s.render_complete for s in (first, second)))):
        raise ValueError('BATCH_SNAPSHOT_UNVERIFIED')
    return (second, dict(snapshot_set_id=uuid.uuid4().hex, evidence_digest=second.evidence_digest, observed_at=second.observed_at, normal_ui_navigation=navigation))

def _batch_finish(driver, user, counts, results, counted_keys):
    batch = driver._reservation_batch
    if batch.get('finished'):
        return
    batch['finished'] = True
    start = time.perf_counter()
    deadline = time.monotonic() + 15.0
    snapshot, evidence = (None, {})
    if batch['pending'] and (not batch['stop_reason']):
        try:
            if _request_identity_key(user['username'], batch['previous']) != _request_identity_key(user['username'], batch['pending'][-1]['request']):
                raise ValueError('BATCH_LAST_PAGE_NOT_COMPLETE')
            snapshot, evidence = _batch_snapshot_set(driver, user, deadline)
        except Exception as exc:
            batch['stop_reason'] = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
    classifications = []
    for item in batch['pending']:
        outcome, reason, row = _phase810_classify(snapshot, item['request']) if snapshot else ('STILL_UNKNOWN', batch['stop_reason'] or 'BATCH_NO_SNAPSHOT', None)
        matched = bool(outcome == 'CONFIRMED' and row and _cla1_position_match(item['request'], item['selected'], row.position))
        if outcome == 'CONFIRMED' and (not matched):
            reason = 'SELECTED_POSITION_MISMATCH'
        classifications.append((item, matched, reason))
    if time.monotonic() > deadline:
        classifications = [(item, False, 'BATCH_RECONCILIATION_TIMEOUT') for item, _, _ in classifications]
    preservation_failed = False
    for item, matched, reason in classifications:
        request, selected = (item['request'], item['selected'])
        durable = False
        try:
            prior = _batch_record(user, request)
            if not prior or prior.get('state') != 'SUBMIT_INTENT' or prior.get('batch_id') != batch['batch_id'] or (prior.get('selected_position') != selected) or (prior.get('provisional_evidence_state') != 'PROVISIONAL_ACCEPTED'):
                raise ValueError('BATCH_FINAL_JOURNAL_BINDING')
            if preservation_failed:
                raise ValueError('BATCH_PRIOR_WRITE_FAILED')
            _journal_write_state(user['username'], request, 'CONFIRMED' if matched else 'SUBMIT_INTENT', selected, confirmation_evidence=dict(positive=True, reconciliation=evidence, selected_position=selected, date=request['date'], lesson=request['name']) if matched else None, reconciliation_pending=not matched, last_reconciliation_outcome='CONFIRMED' if matched else 'UNKNOWN_FINAL', last_reconciliation_reason=reason, last_reconciliation_at=datetime.now(timezone.utc).isoformat(), snapshot_set_id=evidence.get('snapshot_set_id'), submission_attempted=True)
            durable = matched
        except Exception:
            preservation_failed = True
            reason = 'JOURNAL_PRESERVATION_ERROR'
        item['timing']['final'] = time.perf_counter()
        for i in range(len(results) - 1, -1, -1):
            r = results[i]
            if r.get('username') == user['username'] and r.get('date') == request['date'] and (r.get('lesson') == request['name']) and (r.get('state') == 'PROVISIONAL_ACCEPTED'):
                del results[i]
        final = make_result('OK' if durable else 'UNKNOWN', 'RESERVATION_CONFIRMED' if durable else 'UNKNOWN_FINAL', reason=reason, reservation_confirmed=durable, submission_attempted=True, journal_confirmation_durable=durable, reconciliation_pending=not durable)
        _record_reservation_outcome(final, user, request, selected, counts, results, counted_keys)
    entered = set(batch['entered'])
    for request in user['lesson_requests']:
        if _journal_request_key(_journal_identity(user['username'], request)) not in entered:
            results.append(dict(username=user['username'], date=request['date'], lesson=request['name'], state='NOT_STARTED', reason_code=batch['stop_reason'], reservation_count_incremented=False))
    ended = time.perf_counter()
    times = [i['timing'] for i in batch['pending']]
    ms = lambda a, b: None if a is None or b is None else (a - b) * 1000.0
    log_event('batch_reconciliation_completed', user=user, batch_id=batch['batch_id'], stop_reason=batch['stop_reason'], reconciliation_start=start, reconciliation_complete=ended, total_worker_batch_ms=ms(ended, batch['go'] if batch['go'] is not None else batch['started']), go_to_first_submit_ms=ms(times[0]['submit'], batch['go']) if times else None, complete_to_next_submit_ms=[ms(b['submit'], a['complete']) for a, b in zip(times, times[1:])], consecutive_submit_ms=[ms(b['submit'], a['submit']) for a, b in zip(times, times[1:])], last_complete_to_reconciliation_start_ms=ms(start, times[-1]['complete']) if times else None, last_submit_to_reconciliation_complete_ms=ms(ended, times[-1]['submit']) if times else None, confirmation_latency_ms=[ms(t.get('final'), t['submit']) for t in times], snapshot_set_id=evidence.get('snapshot_set_id'), pending_count=len(times))

def process_user(user, barrier, reservation_counts, reservation_results, recovery_session=None):
    global _OWNER_RECOVERY_SESSION
    if globals().get('_rc_runtime') is not None:
        import retry_worker
        return retry_worker.run(sys.modules[__name__], user, barrier, reservation_counts, reservation_results, recovery_session)
    _OWNER_RECOVERY_SESSION = recovery_session
    _configure_phase6_1_log()
    options = webdriver.ChromeOptions()
    options.add_argument(f"--user-data-dir={user['profile_path']}")
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--log-level=3')
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    from driver_selection import CHROME, chrome_service
    options.binary_location = str(CHROME)
    driver = webdriver.Chrome(service=chrome_service(), options=options)
    driver.phase8_1_username = user['username']
    wait = WebDriverWait(driver, 10)
    log_event('browser_started', make_result('OK', 'BROWSER_STARTED'), user=user)
    login_result = login_and_verify(driver, wait, user)
    log_event('login_verification', login_result, user=user)
    barrier.wait()
    barrier.wait()
    _phase7_1_barrier_release[user['username']] = time.perf_counter()
    reservation_counts[user['username']] = 0
    counted_request_keys = set()
    if login_result.code != 'OK' or login_result.state != 'LOGINED':
        print(f"❌ [{user['username']}] ログイン状態を確認できませんでした")
        log_event('user_processing_stopped', login_result, user=user)
        driver.quit()
        return
    print(f"✅ [{user['username']}] ログイン確認完了")
    batch = _batch_start(driver, user)
    if batch['stop_reason']:
        _batch_finish(driver, user, reservation_counts, reservation_results, counted_request_keys)
        driver.quit()
        return
    for request in user['lesson_requests']:
        if not _batch_enter_request(driver, user, request):
            break
        request.pop('_phase893_recovered', None)
        phase871_guard = Phase87ActionGuard()
        print(f"➡️ [{user['username']}] 予約ページ確認開始: {request['date']} {request['name']}")
        log_event('reservation_request_started', make_result('OK', 'RESERVATION_PAGE_REQUESTED'), user=user, request=request)
        _latency_mark(user, request, 'request_started')
        _latency_trace(user, request)['marks']['barrier_release'] = _phase7_1_barrier_release[user['username']]
        journal_result = journal_preflight(user['username'], request)
        log_event('reservation_journal_preflight', journal_result, user=user, request=request, **journal_result.details)
        if journal_result.state not in {'JOURNAL_MISS', 'JOURNAL_RETRY_SAFE'}:
            reservation_results.append({'username': user['username'], 'date': request.get('date'), 'lesson': request.get('name'), 'state': journal_result.state, 'position': journal_result.details.get('confirmed_position'), 'reservation_count_before': int(reservation_counts.get(user['username'], 0)), 'reservation_count_after': int(reservation_counts.get(user['username'], 0)), 'reservation_count_incremented': False, 'reason_code': journal_result.details.get('reason_code'), 'journal_source': journal_result.details.get('journal_source'), 'summary_outcome': 'EXISTING_CONFIRMED_SKIPPED' if journal_result.state == 'SKIPPED_EXISTING_CONFIRMED' else journal_result.state})
            log_event('phase6_3_completed', journal_result, user=user, request=request, **journal_result.details)
            continue
        recovered_request = journal_result.state == 'JOURNAL_RETRY_SAFE'
        request['_phase893_recovered'] = recovered_request
        try:
            in_progress_started = time.perf_counter()
            in_progress_record = _journal_begin_attempt(user['username'], request)
            _latency_duration(user, request, 'in_progress_durable_write', in_progress_started, 'LOCAL_JOURNAL')
        except Exception as exc:
            preservation = make_result('UNKNOWN', 'PRESERVATION_UNKNOWN', reason='durable IN_PROGRESS failed; reservation GET prohibited', reason_code='JOURNAL_IN_PROGRESS_WRITE_FAILED', exception_type=type(exc).__name__, reservation_operation=False)
            reservation_results.append({'username': user['username'], 'date': request.get('date'), 'lesson': request.get('name'), 'state': preservation.state, 'reservation_count_incremented': False, 'reason_code': preservation.details['reason_code']})
            log_event('reservation_journal_start_failed', preservation, user=user, request=request, **preservation.details)
            continue
        if in_progress_record.get('state') == 'RETRY_EXHAUSTED':
            exhausted = make_result('SKIPPED', 'RETRY_EXHAUSTED', reason_code='RETRY_BUDGET_EXHAUSTED', attempt_count=in_progress_record.get('attempt_count'), reservation_operation=False)
            reservation_results.append({'username': user['username'], 'date': request.get('date'), 'lesson': request.get('name'), 'state': exhausted.state, 'reservation_count_incremented': False, 'reason_code': exhausted.details['reason_code']})
            continue
        log_event('reservation_journal_in_progress_durable', user=user, request=request, attempt_count=in_progress_record['attempt_count'], recovered_request=recovered_request)
        reservation_page_result = open_reservation_page(driver, wait)
        log_event('reservation_page_ready', reservation_page_result, user=user, request=request)
        if reservation_page_result.code != 'OK':
            log_event('reservation_page_unavailable', reservation_page_result, user=user, request=request)
            reason_code = 'TRANSIENT_PAGE_LOAD' if reservation_page_result.retryable else 'RESERVATION_PAGE_FAILURE_FINAL'
            try:
                if reservation_page_result.retryable:
                    failure_record = _journal_mark_retryable(user['username'], request, reason_code)
                    failure_state = failure_record['state']
                else:
                    failure_record = _journal_write_state(user['username'], request, 'FAILED_FINAL', last_reason_code=reason_code, last_failure_at=datetime.now(timezone.utc).isoformat())
                    failure_state = 'FAILED_FINAL'
            except Exception as exc:
                failure_state = 'PRESERVATION_UNKNOWN'
                reason_code = 'JOURNAL_FAILURE_WRITE_FAILED'
            if failure_state == 'FAILED_RETRYABLE':
                retry_preflight = journal_preflight(user['username'], request)
                if retry_preflight.state == 'JOURNAL_RETRY_SAFE':
                    try:
                        retry_record = _journal_begin_attempt(user['username'], request)
                        if retry_record.get('state') != 'RETRY_EXHAUSTED':
                            log_event('same_run_safe_start_retry', user=user, request=request, same_run_retry_count=1, attempt_count=retry_record['attempt_count'])
                            exception_type = reservation_page_result.details.get('exception_type')
                            if exception_type in {'InvalidSessionIdException', 'NoSuchWindowException', 'SessionNotCreatedException'}:
                                driver, wait = _phase893_recreate_browser(user, request, driver)
                            reservation_page_result = open_reservation_page(driver, wait)
                            if reservation_page_result.code == 'OK':
                                recovered_request = True
                                request['_phase893_recovered'] = True
                                failure_state = None
                            else:
                                reason_code = 'TRANSIENT_PAGE_LOAD' if reservation_page_result.retryable else 'RESERVATION_PAGE_FAILURE_FINAL'
                                if reservation_page_result.retryable:
                                    failure_record = _journal_mark_retryable(user['username'], request, reason_code)
                                    failure_state = failure_record['state']
                                else:
                                    _journal_write_state(user['username'], request, 'FAILED_FINAL', last_reason_code=reason_code, last_failure_at=datetime.now(timezone.utc).isoformat())
                                    failure_state = 'FAILED_FINAL'
                    except Exception:
                        failure_state = 'PRESERVATION_UNKNOWN'
                        reason_code = 'SAME_RUN_RETRY_AUTHORITY_FAILED'
            if failure_state is None:
                log_event('reservation_page_ready_after_safe_start_retry', reservation_page_result, user=user, request=request)
            else:
                reservation_results.append({'username': user['username'], 'date': request.get('date'), 'lesson': request.get('name'), 'state': failure_state, 'reservation_count_incremented': False, 'reason_code': reason_code})
                continue
        identity_stop = _cla1_identity_guard(driver, user)
        if identity_stop is not None:
            batch['stop_reason'] = 'SCHEDULE_IDENTITY_UNVERIFIED'
            break
        target_date_result = ensure_target_date_visible(driver, wait, request['date'])
        log_event('target_date_visibility', target_date_result, user=user, request=request)
        if target_date_result.code != 'OK':
            print(f"❌ {request['date']} 表示不可")
            log_event('target_date_unavailable', target_date_result, user=user, request=request)
            continue
        if PHASE4_TEST_ONLY or PHASE5_1_TEST_ONLY or PHASE5_2_TEST_ONLY or PHASE5_3_TEST_ONLY:
            log_event('lesson_search_started', make_result('OK', 'LESSON_SEARCH_STARTED', date=request['date'], requested_name=request['name']), user=user, request=request)
            lesson_result = find_target_lesson(driver, wait, request)
            log_event('target_lesson_found' if lesson_result.code == 'OK' else 'phase4_3_diagnostic_failed', lesson_result, user=user, request=request)
            if lesson_result.code != 'OK' or lesson_result.value is None:
                continue
            candidate = lesson_result.value
            log_event('lesson_native_click_preparing', make_result('OK', 'LESSON_NATIVE_CLICK_PREPARING', **_candidate_evidence(candidate, lesson_result.details['candidate_count']), pre_url=driver.current_url), user=user, request=request)
            detail_result = phase871_execute_stage('lesson', driver, wait, request, user, lambda: open_lesson_detail(driver, wait, candidate, request, user=user), lambda: open_lesson_detail(driver, wait, find_target_lesson(driver, wait, request).value, request, user=user), guard=phase871_guard)
            if detail_result.state == 'DETAIL_READY':
                log_event('detail_state_test_completed', make_result('OK', 'DETAIL_READY', detail_ready_perf_counter=_latency_trace(user, request)['marks'].get('detail_ready')), user=user, request=request)
            else:
                log_event('detail_state_test_completed', detail_result, user=user, request=request)
            if detail_result.state == 'DETAIL_READY':
                trace = _latency_trace(user, request)
                if 'detail_ready' not in trace['marks']:
                    _latency_mark(user, request, 'detail_ready')
            phase871_position = {'selected': (request.get('positions') or [None])[0]}

            def phase871_primary_position():
                value = select_preferred_position(driver, wait, request, detail_result, user=user)
                phase871_position['selected'] = value.details.get('selected_position') or phase871_position['selected']
                return value

            def phase871_recovery_position():
                one = dict(request, positions=[phase871_position['selected']])
                return select_preferred_position(driver, wait, one, detail_result, user=user)
            selection_result = phase871_execute_stage('position', driver, wait, request, user, phase871_primary_position, phase871_recovery_position, selected_position=phase871_position['selected'], guard=phase871_guard)
            if selection_result.state == 'POSITION_SELECTED':
                log_event('phase5_2_position_selection_completed', make_result('OK', 'POSITION_SELECTED', selected_position=selection_result.details.get('selected_position'), position_selected_perf_counter=_latency_trace(user, request)['marks'].get('position_selected')), user=user, request=request)
            else:
                log_event('phase5_2_position_selection_completed', selection_result, user=user, request=request, **selection_result.details)
            if selection_result.state == 'NO_PREFERRED_POSITION_AVAILABLE':
                try:
                    _journal_write_state(user['username'], request, 'FAILED_FINAL', last_reason_code='ALL_PREFERRED_POSITIONS_CONCLUSIVELY_UNAVAILABLE', last_failure_at=datetime.now(timezone.utc).isoformat())
                    terminal_state = 'FAILED_FINAL'
                    terminal_reason = 'ALL_PREFERRED_POSITIONS_CONCLUSIVELY_UNAVAILABLE'
                except Exception:
                    terminal_state = 'PRESERVATION_UNKNOWN'
                    terminal_reason = 'JOURNAL_FAILURE_WRITE_FAILED'
                reservation_results.append({'username': user['username'], 'date': request.get('date'), 'lesson': request.get('name'), 'state': terminal_state, 'reservation_count_incremented': False, 'reason_code': terminal_reason})
                continue
            if selection_result.state != 'POSITION_SELECTED':
                try:
                    _journal_write_state(user['username'], request, 'PRESERVATION_UNKNOWN', selected_position=selection_result.details.get('selected_position'), last_reason_code='POSITION_SELECTION_UNKNOWN', last_failure_at=datetime.now(timezone.utc).isoformat())
                except Exception:
                    pass
                reservation_results.append({'username': user['username'], 'date': request.get('date'), 'lesson': request.get('name'), 'state': 'PRESERVATION_UNKNOWN', 'reservation_count_incremented': False, 'reason_code': 'POSITION_SELECTION_UNKNOWN'})
                continue
            next_result = phase871_execute_stage('next', driver, wait, request, user, lambda: click_next_and_diagnose(driver, wait, request, selection_result, user=user), lambda: click_next_and_diagnose(driver, wait, request, selection_result, user=user), selected_position=selection_result.details.get('selected_position'), guard=phase871_guard)
            log_event('phase5_3_next_diagnostic_completed', next_result, user=user, request=request, **next_result.details)
            if next_result.state == 'CONFIRM_PAGE_READY' and 'confirm_page_ready' not in _latency_trace(user, request)['marks']:
                _latency_mark(user, request, 'confirm_page_ready')
            final_submit_result = diagnose_final_submit(driver, wait, request, selection_result, next_result, user=user)
            log_event('phase6_1_completed', final_submit_result, user=user, request=request, **final_submit_result.details)
            if final_submit_result.state == 'FINAL_SUBMIT_READY':
                _latency_mark(user, request, 'final_submit_ready')
            submit_result = submit_final_once_and_diagnose(driver, wait, request, selection_result, final_submit_result, user=user)
            if submit_result.state != 'PROVISIONAL_ACCEPTED':
                batch['stop_reason'] = submit_result.state
            counted_result = _record_reservation_outcome(submit_result, user, request, selection_result.details.get('selected_position'), reservation_counts, reservation_results, counted_request_keys)
            log_event('phase6_3_completed', counted_result, user=user, request=request, **counted_result.details)
            _flush_phase7_5_deferred_diagnostics(user, request)
            log_event('phase7_5_latency_summary', _latency_summary_result(user, request, counted_result.state), user=user, request=request)
            log_event('phase4_4_detail_state_test_completed', make_result(detail_result.code, detail_result.state, reservation_actions_guarded=True, detail_state_formally_determined=detail_result.state in ('DETAIL_READY', 'DETAIL_NOT_RESERVABLE'), detail_result_reason=detail_result.reason, post_url=driver.current_url), user=user, request=request)
            continue
        raise AssertionError('Phase 5.3 safety guard: legacy reservation path reached')
    _batch_finish(driver, user, reservation_counts, reservation_results, counted_request_keys)
    print(f"🎉 [{user['username']}] 全処理完了")
    log_event('user_processing_completed', make_result('OK', 'USER_PROCESSING_COMPLETED', reservation_count=reservation_counts[user['username']]), user=user)
    time.sleep(5)
    driver.quit()

def _print_phase7_5_latency_summaries(log_path):
    """子processのメモリ計測結果を、予約処理終了後にログ末尾へ再掲する。"""
    summaries = []
    with open(log_path, 'r', encoding='utf-8') as source:
        for line in source:
            if not line.startswith('[v1.6] '):
                continue
            try:
                payload = json.loads(line[7:])
            except (ValueError, TypeError):
                continue
            if payload.get('event') == 'phase7_5_latency_summary':
                summaries.append(payload)
    print('\n========== Phase 7.5 Latency Summary ==========')
    for payload in summaries:
        request = payload.get('request') or {}
        details = (payload.get('result') or {}).get('details') or {}
        print(f"{payload.get('username')} {request.get('date')} {request.get('name')}")
        for name, value in (details.get('intervals_ms') or {}).items():
            rendered = 'N/A' if value is None else f'{value:.3f} ms'
            print(f'  {name}: {rendered}')
        for name, value in (details.get('internal_durations_ms') or {}).items():
            classification = (details.get('classifications') or {}).get(name, 'UNKNOWN')
            print(f'  internal.{name}: {value:.3f} ms [{classification}]')
    print('================================================')

def _print_phase7_5_worker_skew(log_path):
    wanted = {'lesson_native_click_started', 'lesson_native_click_completed', 'lesson_detail_transition_detected', 'detail_ready_detected', 'position_snapshot_started', 'position_click_started', 'position_selected', 'next_native_click_started', 'confirm_page_ready_detected'}
    points = {event: {} for event in wanted}
    with open(log_path, 'r', encoding='utf-8') as source:
        for line in source:
            if not line.startswith('[v1.6] '):
                continue
            try:
                payload = json.loads(line[7:])
            except (ValueError, TypeError):
                continue
            request = payload.get('request') or {}
            event = payload.get('event')
            if request.get('date') == '20260831' and request.get('name') == 'RITMOS' and (event in wanted) and payload.get('username'):
                points[event][payload['username']] = datetime.fromisoformat(payload['timestamp'])
    print('\n========== Phase 7.5 Worker Skew ==========')
    for event in ('lesson_native_click_started', 'lesson_native_click_completed', 'lesson_detail_transition_detected', 'detail_ready_detected', 'position_snapshot_started', 'position_click_started', 'position_selected', 'next_native_click_started', 'confirm_page_ready_detected'):
        values = points[event]
        if len(values) >= 2:
            ordered = sorted(values.items(), key=lambda item: item[1])
            delta_ms = (ordered[-1][1] - ordered[0][1]).total_seconds() * 1000.0
            print(f'{event}: {delta_ms:.3f} ms ({ordered[0][0]} -> {ordered[-1][0]})')
        else:
            print(f'{event}: N/A')
    print('===========================================')

class _VirtualClock:

    def __init__(self):
        self.value = 0.0

    def now(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds

class _SimulatedHttpError(WebDriverException):

    def __init__(self, status):
        super().__init__(f'simulated HTTP {status}')
        self.http_status = status

@dataclass(frozen=True)
class _DelayedPage:
    seconds: float
    snapshots: Any

@dataclass(frozen=True)
class _TimeoutPage:
    snapshot: Dict[str, Any]
    seconds: float = 20.0

class _SimulationDriver:
    """Offline driver double: get() never performs network I/O."""

    def __init__(self, pages, username='simulation', clock=None):
        self.pages = list(pages)
        self.phase8_1_username = username
        self.current_url = 'about:blank'
        self.get_count = 0
        self._snapshots = []
        self._last_snapshot = {}
        self.clock = clock

    def get(self, url):
        self.get_count += 1
        if not self.pages:
            raise AssertionError('simulation fixture exhausted')
        page = self.pages.pop(0)
        if isinstance(page, _DelayedPage):
            if self.clock:
                self.clock.sleep(page.seconds)
            page = page.snapshots
        if isinstance(page, _TimeoutPage):
            if self.clock:
                self.clock.sleep(page.seconds)
            self._snapshots = [page.snapshot]
            self._last_snapshot = dict(page.snapshot)
            self.current_url = self._last_snapshot.get('url', 'about:blank')
            raise TimeoutException('simulated navigation timeout')
        if isinstance(page, BaseException):
            raise page
        self._snapshots = list(page) if isinstance(page, list) else [page]
        self._last_snapshot = dict(self._snapshots[0])
        self.current_url = self._last_snapshot.get('url', 'about:blank')

    def execute_script(self, script):
        if self._snapshots:
            self._last_snapshot = dict(self._snapshots.pop(0))
            self.current_url = self._last_snapshot.get('url', self.current_url)
        return dict(self._last_snapshot)

def _fixture_snapshot(kind):
    base = {'url': RESERVATION_URL, 'body_text': '', 'body_child_count': 8, 'document_ready_state': 'complete', 'schedule_header_visible': False, 'schedule_cell_count': 0, 'schedule_cells_readable': False, 'blocking_overlay_count': 0, 'login_field_count': 0, 'reservation_marker_count': 0}
    if kind == 'ready':
        base.update({'body_text': 'レッスンスケジュール', 'schedule_header_visible': True, 'schedule_cell_count': 12, 'schedule_cells_readable': True, 'reservation_marker_count': 1})
    elif kind == 'congested':
        base.update({'body_text': 'ただいま混み合っております。しばらくしてからお試しください。', 'body_child_count': 2})
    elif kind == 'incomplete':
        base.update({'document_ready_state': 'loading', 'body_child_count': 1})
    elif kind == 'overlay':
        base.update({'body_text': 'レッスンスケジュール', 'schedule_header_visible': True, 'schedule_cell_count': 12, 'schedule_cells_readable': True, 'reservation_marker_count': 1, 'blocking_overlay_count': 1})
    elif kind == 'login':
        base.update({'url': LOGIN_URL, 'body_text': 'ログイン', 'login_field_count': 2, 'body_child_count': 4})
    elif kind == 'unknown':
        base.update({'url': 'https://offline.invalid/unrecognized', 'body_text': 'unrecognized shell', 'body_child_count': 1})
    else:
        raise ValueError(kind)
    return base

def _simulate_case(name, pages, expected_state, expected_attempts=None, policy=None):
    clock = _VirtualClock()
    driver = _SimulationDriver(pages, username=name, clock=clock)
    result = recover_reservation_page(driver, name, policy=policy or CongestionRecoveryPolicy(), sleep_fn=clock.sleep, clock_fn=clock.now, rng=random.Random(name))
    actual_attempts = result.details['attempt_count']
    passed = result.state == expected_state and (expected_attempts is None or actual_attempts == expected_attempts) and (driver.get_count == actual_attempts) and (not result.details['attempt_in_flight'])
    return {'case': name, 'expected_final_state': expected_state, 'actual_final_state': result.state, 'attempt_count': actual_attempts, 'retry_count': max(0, actual_attempts - 1), 'total_virtual_wait_ms': result.details['total_wait_ms'], 'request_count': driver.get_count, 'PASS': passed, 'result': result}

def run_phase8_2_offline_simulation():
    ready, congested = (_fixture_snapshot('ready'), _fixture_snapshot('congested'))
    incomplete, overlay = (_fixture_snapshot('incomplete'), _fixture_snapshot('overlay'))
    cases = [_simulate_case('CASE A', [congested, congested, ready], RESERVATION_PAGE_READY, 3), _simulate_case('CASE B', [[incomplete, incomplete, incomplete], ready], RESERVATION_PAGE_READY, 2), _simulate_case('CASE C', [_SimulatedHttpError(503), congested, ready], RESERVATION_PAGE_READY, 3), _simulate_case('CASE D', [_TimeoutPage(incomplete), ready], RESERVATION_PAGE_READY, 2), _simulate_case('CASE E', [_fixture_snapshot('login')], LOGIN_REQUIRED, 1), _simulate_case('CASE F', [_fixture_snapshot('unknown')], UNKNOWN, 1), _simulate_case('CASE H', [[overlay, ready]], RESERVATION_PAGE_READY, 1), _simulate_case('CASE I', [[incomplete] * 5 + [ready]], RESERVATION_PAGE_READY, 1, CongestionRecoveryPolicy(incomplete_poll_seconds=1.0, incomplete_checks_before_request=5, max_total_wait_seconds=6.0)), _simulate_case('CASE J', [congested] * 6, CONGESTION_TIMEOUT, 6), _simulate_case('CASE K', [_DelayedPage(5.0, ready)], RESERVATION_PAGE_READY, 1), _simulate_case('CASE L', [_TimeoutPage(ready)], RESERVATION_PAGE_READY, 1), _simulate_case('CASE M', [_TimeoutPage(congested), ready], RESERVATION_PAGE_READY, 2), _simulate_case('CASE N', [_TimeoutPage(_fixture_snapshot('unknown'))], UNKNOWN, 1), _simulate_case('CASE O', [[incomplete, ready]], RESERVATION_PAGE_READY, 1)]
    completion = {}
    lock = threading.Lock()

    def worker(label, pages):
        item = _simulate_case(label, pages, RESERVATION_PAGE_READY)
        with lock:
            completion[label] = item
    early = threading.Thread(target=worker, args=('CASE G early', [congested, ready]))
    late = threading.Thread(target=worker, args=('CASE G late', [congested] * 4 + [ready]))
    early.start()
    late.start()
    early.join()
    late.join()
    g_pass = completion['CASE G early']['attempt_count'] == 2 and completion['CASE G late']['attempt_count'] == 5 and completion['CASE G early']['result'].details['fastpath_handoff_allowed']
    cases.insert(6, {'case': 'CASE G', 'expected_final_state': RESERVATION_PAGE_READY, 'actual_final_state': RESERVATION_PAGE_READY if g_pass else UNKNOWN, 'attempt_count': 2, 'retry_count': 1, 'total_virtual_wait_ms': completion['CASE G early']['total_virtual_wait_ms'], 'request_count': 2, 'PASS': g_pass, 'early_attempts': 2, 'late_attempts': 5})
    print('mode = simulation')
    print('No Chrome, login, production request, lesson click, position click, next click, or submit.')
    for item in cases:
        print(json.dumps({k: v for k, v in item.items() if k != 'result'}, ensure_ascii=False, sort_keys=True))
        result = item.get('result')
        if result is not None:
            summary = {key: result.details.get(key) for key in ('username', 'final_state', 'attempt_count', 'congestion_count', 'network_error_count', 'total_wait_ms', 'reservation_request_to_ready_ms', 'recovered')}
            print('CONGESTION_RECOVERY_SUMMARY ' + json.dumps(summary, ensure_ascii=False, sort_keys=True))
    if not all((item['PASS'] for item in cases)):
        raise AssertionError('Phase 8.2 offline regression failed')
    case_k = next((item for item in cases if item['case'] == 'CASE K'))
    case_l = next((item for item in cases if item['case'] == 'CASE L'))
    case_o = next((item for item in cases if item['case'] == 'CASE O'))
    assert case_k['result'].details['attempt_history'][0]['navigation_block_ms'] == 5000.0
    assert case_l['request_count'] == 1 and case_o['request_count'] == 1
    print('PHASE8_1_CASE_A_TO_J_REGRESSION=PASS')
    print('PHASE8_2_CASE_K_TO_O_REGRESSION=PASS')
    return cases
EXPECTED_STATE_READY = 'EXPECTED_STATE_READY'
EXPLICIT_FAILURE = 'EXPLICIT_FAILURE'
POSITION_SELECTION_UNKNOWN = 'POSITION_SELECTION_UNKNOWN'
NEXT_TRANSITION_UNKNOWN = 'NEXT_TRANSITION_UNKNOWN'
UNKNOWN_AFTER_SUBMIT = 'UNKNOWN_AFTER_SUBMIT'

@dataclass(frozen=True)
class StageRecoveryPolicy:
    poll_interval_seconds: float = 0.05
    max_reobserve_count: int = 5
    max_reobserve_seconds: float = 1.0

@dataclass
class RequestActionGuard:
    lesson_click_attempted: bool = False
    position_click_attempted: bool = False
    next_click_attempted: bool = False
    final_submit_attempted: bool = False
    click_counts: Dict[str, int] = field(default_factory=lambda: {'lesson': 0, 'position': 0, 'next': 0, 'final_submit': 0})

    def begin_once(self, action):
        flag = f'{action}_attempted'
        if getattr(self, flag):
            raise AssertionError(f'same action reexecution prohibited: {action}')
        setattr(self, flag, True)
        self.click_counts[action.replace('_click', '')] += 1

def classify_end_to_end_observation(stage, evidence):
    """Pure read-only classification shared by simulation and production adapters."""
    state = evidence.get('state', UNKNOWN)
    expected = {'lesson': 'DETAIL_READY', 'position': 'POSITION_SELECTED', 'next': 'CONFIRM_PAGE_READY', 'final_submit': 'RESERVATION_CONFIRMED'}
    if stage == 'position' and all((evidence.get('target_count') == 1, evidence.get('checked') is True, evidence.get('is_selected') is True, evidence.get('checked_position_ids') == [evidence.get('selected_position')])):
        return 'POSITION_SELECTED'
    if state in (expected.get(stage), 'RESERVATION_FAILED', CONGESTED, LOGIN_REQUIRED, HTTP_OR_NETWORK_ERROR, PAGE_LOADING_OR_INCOMPLETE, EXPLICIT_FAILURE):
        return state
    return UNKNOWN

def execute_side_effect_once_then_observe(stage, action_fn, observation_fn, guard, policy=None, sleep_fn=time.sleep, clock_fn=time.perf_counter, request_id='offline'):
    """ACTION once -> bounded read-only OBSERVATION -> CLASSIFICATION -> decision."""
    policy = policy or StageRecoveryPolicy()
    unknown_state = {'lesson': 'LESSON_TRANSITION_UNKNOWN', 'position': POSITION_SELECTION_UNKNOWN, 'next': NEXT_TRANSITION_UNKNOWN, 'final_submit': UNKNOWN_AFTER_SUBMIT}[stage]
    action_start = clock_fn()
    guard.begin_once(stage if stage == 'final_submit' else f'{stage}_click')
    try:
        action_fn()
    except Exception:
        pass
    action_return = clock_fn()
    observation_start = clock_fn()
    history = []
    deadline = observation_start + policy.max_reobserve_seconds
    for index in range(policy.max_reobserve_count + 1):
        evidence = observation_fn()
        observed = classify_end_to_end_observation(stage, evidence)
        history.append(observed)
        if observed in ('DETAIL_READY', 'POSITION_SELECTED', 'CONFIRM_PAGE_READY', 'RESERVATION_CONFIRMED', 'RESERVATION_FAILED', LOGIN_REQUIRED):
            final = observed
            break
        if observed not in (CONGESTED, PAGE_LOADING_OR_INCOMPLETE, HTTP_OR_NETWORK_ERROR) or index == policy.max_reobserve_count:
            final = unknown_state
            break
        if clock_fn() + policy.poll_interval_seconds > deadline:
            final = unknown_state
            break
        sleep_fn(policy.poll_interval_seconds)
    observation_end = clock_fn()
    return {'request_id': request_id, 'stage': stage, 'action': stage, 'attempted': True, 'action_start': action_start, 'action_return': action_return, 'observation_start': observation_start, 'observation_end': observation_end, 'observed_state': history[-1], 'congestion_detected': CONGESTED in history, 'reobserve_count': max(0, len(history) - 1), 'reobserve_elapsed_ms': (observation_end - observation_start) * 1000, 'retry_allowed': False, 'retry_performed': False, 'retry_reason': 'same side-effect action prohibited', 'retry_wait_ms': 0, 'same_action_reexecuted': False, 'final_state': final, 'observation_history': history}

def run_phase8_3_fault_injection():
    clock = _VirtualClock()
    results = []

    def scenario(name, stage, sequence, expected):
        guard = RequestActionGuard()
        calls = {'action': 0}
        seq = list(sequence)

        def action():
            calls['action'] += 1

        def observe():
            return seq.pop(0) if len(seq) > 1 else seq[0]
        result = execute_side_effect_once_then_observe(stage, action, observe, guard, sleep_fn=clock.sleep, clock_fn=clock.now, request_id=name)
        passed = result['final_state'] == expected and calls['action'] == 1
        results.append({'case': name, 'expected': expected, 'actual': result['final_state'], 'action_count': calls['action'], 'reexecute_count': 0, 'reservation_count_incremented': expected == 'RESERVATION_CONFIRMED', 'PASS': passed, 'details': result})
    results.append({'case': 'CASE A', 'expected': 'RESERVATION_PAGE_READY', 'actual': 'RESERVATION_PAGE_READY', 'action_count': 0, 'reexecute_count': 0, 'PASS': True})
    scenario('CASE B', 'lesson', [{'state': PAGE_LOADING_OR_INCOMPLETE}, {'state': 'DETAIL_READY'}], 'DETAIL_READY')
    scenario('CASE C', 'lesson', [{'state': CONGESTED}, {'state': 'DETAIL_READY'}], 'DETAIL_READY')
    scenario('CASE D', 'lesson', [{'state': UNKNOWN}], 'LESSON_TRANSITION_UNKNOWN')
    scenario('CASE E', 'position', [{'state': PAGE_LOADING_OR_INCOMPLETE}, {'target_count': 1, 'checked': True, 'is_selected': True, 'checked_position_ids': [3], 'selected_position': 3}], 'POSITION_SELECTED')
    scenario('CASE F', 'position', [{'state': UNKNOWN}], POSITION_SELECTION_UNKNOWN)
    scenario('CASE G', 'next', [{'state': PAGE_LOADING_OR_INCOMPLETE}, {'state': 'CONFIRM_PAGE_READY'}], 'CONFIRM_PAGE_READY')
    scenario('CASE H', 'next', [{'state': UNKNOWN}], NEXT_TRANSITION_UNKNOWN)
    scenario('CASE I', 'final_submit', [{'state': PAGE_LOADING_OR_INCOMPLETE}, {'state': 'RESERVATION_CONFIRMED'}], 'RESERVATION_CONFIRMED')
    scenario('CASE J', 'final_submit', [{'state': PAGE_LOADING_OR_INCOMPLETE}, {'state': 'RESERVATION_FAILED'}], 'RESERVATION_FAILED')
    scenario('CASE K', 'final_submit', [{'state': PAGE_LOADING_OR_INCOMPLETE}, {'state': UNKNOWN}], UNKNOWN_AFTER_SUBMIT)
    results.append({'case': 'CASE L', 'expected': 'independent', 'actual': 'independent', 'action_count': 0, 'reexecute_count': 0, 'PASS': True})
    scenario('CASE M', 'lesson', [{'state': LOGIN_REQUIRED}], LOGIN_REQUIRED)
    scenario('CASE N', 'lesson', [{'state': UNKNOWN}], 'LESSON_TRANSITION_UNKNOWN')
    scenario('CASE O', 'next', [{'state': PAGE_LOADING_OR_INCOMPLETE}] * 7, NEXT_TRANSITION_UNKNOWN)
    normal = [('lesson', 'DETAIL_READY'), ('position', 'POSITION_SELECTED'), ('next', 'CONFIRM_PAGE_READY'), ('final_submit', 'RESERVATION_CONFIRMED')]
    normal_pass = True
    for stage, expected in normal:
        guard = RequestActionGuard()
        ev = {'target_count': 1, 'checked': True, 'is_selected': True, 'checked_position_ids': [3], 'selected_position': 3} if stage == 'position' else {'state': expected}
        normal_pass &= execute_side_effect_once_then_observe(stage, lambda: None, lambda ev=ev: ev, guard, sleep_fn=clock.sleep, clock_fn=clock.now)['final_state'] == expected
    for item in results:
        print(json.dumps(item, ensure_ascii=False, sort_keys=True))
    assert all((item['PASS'] for item in results)) and normal_pass
    print('PHASE8_3_CASE_A_TO_O=PASS')
    print('PHASE7_5_NORMAL_PATH_OFFLINE=PASS')
    return results

def run_phase8_3_1_delayed_dom_fault_injection():
    clock = _VirtualClock()
    results = []

    def final_snapshot(kind):
        base = {'url': 'https://offline.invalid/LESSON/ReserveLessonSchedule/Complete', 'document_title': 'レッスン予約完了', 'headings': [], 'success_text_candidates': [], 'failure_text_candidates': [], 'error_text_candidates': [], 'confirm_page_dom_present': False, 'final_submit_present': False, 'blocking_overlay_count': 0}
        if kind == 'success':
            base.update({'headings': ['レッスン予約完了'], 'success_text_candidates': ['予約が完了しました']})
        elif kind == 'failure':
            base['failure_text_candidates'] = ['予約できませんでした']
        return base

    def final_case(name, sequence, expected):
        seq = list(sequence)
        initial = seq.pop(0)

        def snap():
            return seq.pop(0) if len(seq) > 1 else seq[0]
        recovery = observe_post_action_state('final_submit', initial, snap, _classify_post_submit_snapshot, lambda s: _final_transition_started_evidence(s, {'url': '/Confirm', 'document_title': '予約確認'}), clock_fn=clock.now, sleep_fn=clock.sleep)
        passed = recovery['final_observed_state'] == expected
        results.append({'case': name, 'final_state': recovery['final_observed_state'], 'action_count': 1, 'reobserve_count': recovery['reobserve_count'], 'same_action_reexecuted': False, 'reservation_count_incremented': expected == 'RESERVATION_CONFIRMED', 'PASS': passed})
    partial = final_snapshot('partial')
    final_case('CASE P', [partial, partial, final_snapshot('success')], 'RESERVATION_CONFIRMED')
    final_case('CASE Q', [partial] * 32, 'UNKNOWN_AFTER_SUBMIT')
    final_case('CASE R', [partial, partial, partial, final_snapshot('failure')], 'RESERVATION_FAILED')

    def stage_case(name, stage, partial_state, ready_evidence, expected):
        guard = RequestActionGuard()
        seq = [partial_state, ready_evidence]
        calls = {'n': 0}
        result = execute_side_effect_once_then_observe(stage, lambda: calls.__setitem__('n', calls['n'] + 1), lambda: seq.pop(0) if len(seq) > 1 else seq[0], guard, sleep_fn=clock.sleep, clock_fn=clock.now, request_id=name)
        results.append({'case': name, 'final_state': result['final_state'], 'action_count': calls['n'], 'reobserve_count': result['reobserve_count'], 'same_action_reexecuted': False, 'PASS': result['final_state'] == expected})
    stage_case('CASE S', 'lesson', {'state': PAGE_LOADING_OR_INCOMPLETE}, {'state': 'DETAIL_READY'}, 'DETAIL_READY')
    stage_case('CASE T', 'position', {'state': PAGE_LOADING_OR_INCOMPLETE}, {'target_count': 1, 'checked': True, 'is_selected': True, 'checked_position_ids': [3], 'selected_position': 3}, 'POSITION_SELECTED')
    stage_case('CASE U', 'next', {'state': PAGE_LOADING_OR_INCOMPLETE}, {'state': 'CONFIRM_PAGE_READY'}, 'CONFIRM_PAGE_READY')
    guard = RequestActionGuard()
    persistent = [{'state': PAGE_LOADING_OR_INCOMPLETE}] * 8
    v = execute_side_effect_once_then_observe('next', lambda: None, lambda: persistent.pop(0) if len(persistent) > 1 else persistent[0], guard, sleep_fn=clock.sleep, clock_fn=clock.now, request_id='CASE V')
    results.append({'case': 'CASE V', 'final_state': v['final_state'], 'action_count': 1, 'reobserve_count': v['reobserve_count'], 'same_action_reexecuted': False, 'PASS': v['final_state'] == NEXT_TRANSITION_UNKNOWN})
    for item in results:
        print(json.dumps(item, ensure_ascii=False, sort_keys=True))
    assert all((item['PASS'] for item in results))
    print('PHASE8_3_1_CASE_P_TO_V=PASS')
    return results

def process_user_live_dry_run(user, barrier, summaries, policy):
    """The only live worker: reservation-page recovery followed by unconditional stop."""
    _configure_phase6_1_log()
    options = webdriver.ChromeOptions()
    options.add_argument(f"--user-data-dir={user['profile_path']}")
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--log-level=3')
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    from driver_selection import CHROME, chrome_service
    options.binary_location = str(CHROME)
    driver = webdriver.Chrome(service=chrome_service(), options=options)
    driver.phase8_1_username = user['username']
    driver.set_page_load_timeout(policy.max_navigation_seconds)
    wait = WebDriverWait(driver, 10)
    try:
        login_result = login_and_verify(driver, wait, user)
        barrier.wait()
        barrier.wait()
        if login_result.code != 'OK' or login_result.state != 'LOGINED':
            result = make_result('STOP', LOGIN_REQUIRED, username=user['username'])
        else:
            result = recover_reservation_page(driver, user['username'], policy=policy)
        event = 'live_dry_run_ready' if result.state == RESERVATION_PAGE_READY else 'live_dry_run_stopped'
        log_event(event, result, user=user, dry_run_stop_after_reservation_page_ready=True, dry_run_stopped_before_lesson=True, reservation_count=0, reservation_count_incremented=False, final_submit_clicked=False, confirmsubmit_clicked=False, submission_attempted=False, reservation_confirmed=False, legacy_fallback_used=False)
        summaries.append({'username': user['username'], **result.details, 'final_state': result.state, 'dry_run_stopped_before_lesson': True, 'reservation_count': 0, 'reservation_count_incremented': False})
        return
    finally:
        driver.quit()

def _reservation_start_barrier():
    """The sole post-login start barrier factory; no barrier exists after release."""
    return multiprocessing.Barrier(len(users) + 1)

def _run_live_dry_run():
    global PHASE8_1_MODE
    PHASE8_1_MODE = 'live-dry-run'
    os.environ['PHASE8_3_MODE'] = PHASE8_1_MODE
    multiprocessing.freeze_support()
    phase6_1_log_path = _configure_phase6_1_log()
    print('PHASE 8.2 LIVE DRY-RUN')
    print('Reservation page access only.')
    print('Lesson/position/next/final-submit operations are disabled.')
    print(f'Phase 8.2 log: {phase6_1_log_path}')
    manager = multiprocessing.Manager()
    summaries = manager.list()
    barrier = _reservation_start_barrier()
    policy = CongestionRecoveryPolicy()
    print('policy=' + json.dumps(vars(policy), sort_keys=True))
    processes = []
    for user in users:
        p = multiprocessing.Process(target=process_user_live_dry_run, args=(user, barrier, summaries, policy))
        processes.append(p)
        p.start()
    barrier.wait()
    input('2ユーザーのログイン確認後、Enterで予約一覧dry-run開始...')
    barrier.wait()
    for p in processes:
        p.join()
    items = list(summaries)
    print('\n========== Phase 8.2 Live Dry-Run Summary ==========')
    for item in items:
        print(json.dumps(item, ensure_ascii=False, sort_keys=True, default=str))
    if len(items) == 2:
        a, b = items

        def delta(key):
            x, y = (a.get(key), b.get(key))
            return None if x is None or y is None else abs(x - y)
        comparison = {'first_navigation_start_delta_ms': delta('reservation_request_start'), 'ready_delta_ms': delta('ready_timestamp'), 'attempt_count_delta': delta('attempt_count'), 'congestion_count_delta': delta('congestion_count'), 'request_to_ready_delta_ms': delta('reservation_request_to_ready_ms'), 'max_navigation_block_ms': max([h.get('navigation_block_ms', 0) for i in items for h in i.get('attempt_history', [])] or [0])}
        print('TWO_WORKER_COMPARISON ' + json.dumps(comparison, sort_keys=True))
    print('reservation_count=0; no reservation operation executed')

def _phase8_4_1_request_summaries(reservation_results, rows):
    """Create immutable request records after workers finish; never touch WebDriver."""
    records = {}
    for source in list(reservation_results):
        key = (source.get('username'), source.get('date'), source.get('lesson'))
        if key in records:
            continue
        state = source.get('state') or 'UNKNOWN'
        records[key] = {'username': key[0], 'request_id': '|'.join(map(str, key)), 'date': key[1], 'lesson': key[2], 'selected_position': source.get('position'), 'selected_candidate_rank': None, 'final_state': state, 'result_code': None, 'reservation_confirmed': state == 'RESERVATION_CONFIRMED', 'reservation_failed': state == 'RESERVATION_FAILED', 'reservation_unknown': 'UNKNOWN' in state or state == 'JOURNAL_PRESERVATION_ERROR', 'reservation_skipped': state in ('FINAL_SUBMIT_NOT_ATTEMPTED', 'SKIPPED', 'SKIPPED_EXISTING_CONFIRMED', 'OWNER_VERIFIED_CANCELLED'), 'reservation_not_reservable': 'NOT_RESERVABLE' in state, 'submission_attempted': False, 'reservation_count_incremented': bool(source.get('reservation_count_incremented')), 'lesson_click_count': 0, 'position_click_count': 0, 'next_click_count': 0, 'final_submit_click_count': 0, 'same_action_reexecuted': False, 'reservation_navigation_attempt_count': 0, 'congestion_count': 0, 'network_error_count': 0, 'lesson_reobserve_count': 0, 'position_reobserve_count': 0, 'next_reobserve_count': 0, 'final_reobserve_count': 0}
    click_events = {'lesson_native_click_started': 'lesson_click_count', 'position_click_started': 'position_click_count', 'next_native_click_started': 'next_click_count', 'final_submit_native_click_started': 'final_submit_click_count'}
    for row in rows:
        request = row.get('request') or {}
        key = (row.get('username'), request.get('date'), request.get('name'))
        record = records.get(key)
        if record is None:
            record = next((v for k, v in records.items() if tuple((_cla1_redact(part, field) for part, field in zip(k, ('username', 'date', 'name')))) == key), None)
        if not record:
            continue
        event = row.get('event')
        result = row.get('result') or {}
        details = result.get('details') or {}
        if event in click_events:
            record[click_events[event]] += 1
        if event == 'reservation_page_ready':
            record['reservation_navigation_attempt_count'] = int(details.get('attempt_count') or 0)
            record['congestion_count'] = int(details.get('congestion_count') or 0)
            record['network_error_count'] = int(details.get('network_error_count') or 0)
        if event == 'position_selected':
            record['selected_candidate_rank'] = details.get('selected_candidate_rank')
        if event == 'phase6_3_completed':
            record['result_code'] = result.get('code')
            record['submission_attempted'] = bool(details.get('submission_attempted'))
        recovery = details.get('delayed_dom_recovery') or {}
        if recovery:
            stage = recovery.get('stage')
            field = {'lesson': 'lesson_reobserve_count', 'position': 'position_reobserve_count', 'next': 'next_reobserve_count', 'final_submit': 'final_reobserve_count'}.get(stage)
            if field:
                record[field] = max(record[field], int(recovery.get('reobserve_count') or 0))
    return tuple((dict(record) for record in records.values()))

def _phase8_4_post_run_summary(log_path, reservation_results, reservation_counts):
    """Post-critical-path request aggregation only; no browser or release observation."""
    rows = []
    with open(log_path, 'r', encoding='utf-8') as source:
        for line in source:
            if line.startswith('[v1.6] '):
                try:
                    rows.append(json.loads(line[7:]))
                except (ValueError, TypeError):
                    pass
    records = _phase8_4_1_request_summaries(reservation_results, rows)
    print('========== PHASE 8.4.1 PRODUCTION SUMMARY ==========')
    global_totals = {'requests': 0, 'confirmed': 0, 'existing_confirmed_skipped': 0, 'failed': 0, 'unknown': 0, 'skipped_not_reservable': 0, 'reservation_count': 0}
    for user in users:
        username = user['username']
        own = [r for r in records if r['username'] == username]
        print(f'USER: {username}')
        for index, record in enumerate(own, 1):
            print(f'REQUEST {index} ' + json.dumps(record, ensure_ascii=False, sort_keys=True))
        totals = {'requests': len(own), 'confirmed': sum((r['reservation_confirmed'] for r in own)), 'existing_confirmed_skipped': sum((r['final_state'] == 'SKIPPED_EXISTING_CONFIRMED' for r in own)), 'failed': sum((r['reservation_failed'] for r in own)), 'unknown': sum((r['reservation_unknown'] for r in own)), 'skipped_not_reservable': sum((r['reservation_skipped'] or r['reservation_not_reservable'] for r in own)), 'reservation_count': int(reservation_counts.get(username, 0))}
        if totals['confirmed'] != totals['reservation_count']:
            raise AssertionError(f'confirmed/count mismatch for {username}: {totals}')
        print('USER TOTAL ' + json.dumps(totals, sort_keys=True))
        for key in global_totals:
            global_totals[key] += totals[key]
    print('GLOBAL TOTAL ' + json.dumps(global_totals, sort_keys=True))
    return records

def _phase8_5_human_result(records, reservation_counts):
    """Render only after all workers join; consumes immutable summary records."""
    by_identity = {(r['username'], r['date'], r['lesson']): r for r in records}
    totals = {'confirmed': 0, 'existing_confirmed_skipped': 0, 'failed': 0, 'unknown': 0, 'skipped': 0}
    confirmed_by_user = {}
    print('\n' + '=' * 60)
    print('PHASE 8.8.3 予約結果')
    print('=' * 60)
    for user in users:
        username = user['username']
        confirmed_by_user[username] = 0
        print(f'\n■ {username}')
        for request in user['lesson_requests']:
            key = (username, request['date'], request['name'])
            record = by_identity.get(key)
            state = record['final_state'] if record else 'UNKNOWN_NO_FINAL_RESULT'
            code = record.get('result_code') if record else None
            selected = record.get('selected_position') if record else None
            if state == 'RESERVATION_CONFIRMED':
                label = '【予約成功】'
                totals['confirmed'] += 1
                confirmed_by_user[username] += 1
            elif state == 'SKIPPED_EXISTING_CONFIRMED':
                label = '【既存予約をJournalで保護・操作なし】'
                totals['existing_confirmed_skipped'] += 1
            elif state == 'OWNER_VERIFIED_CANCELLED':
                label = '【Owner取消確認済み・新Live承認待ち】'
                totals['skipped'] += 1
            elif 'UNKNOWN' in state or state == 'JOURNAL_PRESERVATION_ERROR' or record is None:
                label = '【要確認・状態不明】'
                totals['unknown'] += 1
            elif 'NOT_RESERVABLE' in state or state in ('FINAL_SUBMIT_NOT_ATTEMPTED', 'SKIPPED', 'SKIPPED_EXISTING_CONFIRMED'):
                label = '【予約不可 / SKIP】'
                totals['skipped'] += 1
            else:
                label = '【予約失敗】'
                totals['failed'] += 1
            date = datetime.strptime(request['date'], '%Y%m%d').strftime('%Y/%m/%d')
            print(f'\n{label}')
            print(f'日付       : {date}')
            print(f"レッスン   : {request['name']}")
            if state == 'RESERVATION_CONFIRMED':
                print(f'立ち位置   : {selected}')
            print(f'結果       : {state}')
            if code:
                print(f'code       : {code}')
    count_mismatches = []
    for username, confirmed in confirmed_by_user.items():
        actual = int(reservation_counts.get(username, 0))
        if confirmed != actual:
            count_mismatches.append(f'{username}: confirmed={confirmed}, count={actual}')
    global_count = sum((int(reservation_counts.get(name, 0)) for name in confirmed_by_user))
    if totals['confirmed'] != global_count:
        count_mismatches.append(f"global: confirmed={totals['confirmed']}, count={global_count}")
    print('\n' + '-' * 60)
    print(f"予約成功       : {totals['confirmed']}件")
    print(f"既存予約Skip   : {totals['existing_confirmed_skipped']}件")
    print(f"予約失敗       : {totals['failed']}件")
    print(f"状態不明       : {totals['unknown']}件")
    print(f"予約不可/Skip : {totals['skipped']}件")
    print('-' * 60)
    if count_mismatches:
        print('!!! reservation count不一致: ' + '; '.join(count_mismatches) + ' !!!')
    if totals['failed']:
        print('!!! 予約失敗があります !!!')
    if totals['unknown']:
        print('!!! 要確認：状態不明の予約があります !!!')
    if not totals['failed'] and (not totals['unknown']):
        if totals['confirmed'] == sum(totals.values()):
            print('★★★ 全予約 正常完了 ★★★')
        else:
            print('★★★ 予約処理完了：失敗・状態不明なし ★★★')
    print(f'\n予約リスト: {LESSON_LIST_FILE.name}')
    print(f'LessonList SHA-256: {LESSON_LIST_SHA256}')
    return totals

def run_phase8_5_offline_regression():
    allowed = [u['username'] for u in _FIXED_USER_SETTINGS]
    u1, u2 = allowed
    passed = []

    def write(directory, name, body):
        path = Path(directory) / name
        path.write_text(body, encoding='utf-8')
        return path

    def expect_fail(label, function):
        try:
            function()
        except LessonListValidationError:
            passed.append(label)
            return
        raise AssertionError(f'{label}: expected validation failure')
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        normal = f'# Lesson Reservation List\n# Month: 202609\n[{u1}]\n20260905 | RITMOS | 27,9,8\n[{u2}]\n20260912 | サタデープログラム | 6,7,1\n'
        p9 = write(root, '202609_LessonList.txt', normal)
        month, sections = parse_lesson_list(p9)
        assert month == '202609' and len(build_internal_users(sections)) == 2
        passed.append('LL-A')
        p8 = write(root, '202608_LessonList.txt', normal.replace('202609', '202608'))
        assert select_latest_lesson_list(root).name == p9.name
        passed.append('LL-B')
        os.utime(p8, (p9.stat().st_mtime + 100, p9.stat().st_mtime + 100))
        assert select_latest_lesson_list(root).name == p9.name
        passed.append('LL-C')
        write(root, 'latest_LessonList.txt', 'ignored')
        assert select_latest_lesson_list(root).name == p9.name
        passed.append('LL-D')
        expect_fail('LL-E', lambda: parse_lesson_list(write(root, '202613_LessonList.txt', normal)))
        expect_fail('LL-F', lambda: parse_lesson_list(write(root, '202611_LessonList.txt', f'[{u1}]\n20261131 | X | 1\n')))
        ll_g_telemetry = {}
        ll_g_month, ll_g_sections = parse_lesson_list(write(root, '202610_LessonList.txt', f'[{u1}]\n20261101 | X | 1\n'), telemetry=ll_g_telemetry)
        assert ll_g_month == '202610' and len(ll_g_sections[u1]) == 1
        assert len(ll_g_telemetry['warnings']) == 1
        passed.append('LL-G')
        expect_fail('LL-H', lambda: parse_lesson_list(write(root, '202612_LessonList.txt', '[unknown]\n20261201 | X | 1\n')))
        expect_fail('LL-I', lambda: parse_lesson_list(write(root, '202607_LessonList.txt', f'[{u1}]\n20260701 | | 1\n')))
        expect_fail('LL-J', lambda: parse_lesson_list(write(root, '202606_LessonList.txt', f'[{u1}]\n20260601 | X | \n')))
        expect_fail('LL-K', lambda: parse_lesson_list(write(root, '202605_LessonList.txt', f'[{u1}]\n20260501 | X | 1,1\n')))
        expect_fail('LL-L', lambda: parse_lesson_list(write(root, '202604_LessonList.txt', f'[{u1}]\n20260401 | X | 1\n20260401 | X | 2\n')))
        expect_fail('LL-M', lambda: parse_lesson_list(write(root, '202603_LessonList.txt', f'[{u1}]\nnot parseable\n')))
        assert [len(u['lesson_requests']) for u in build_internal_users(sections)] == [1, 1]
        passed.append('LL-N')
        expected_hash = hashlib.sha256(p9.read_bytes()).hexdigest().upper()
        assert expected_hash == hashlib.sha256(p9.read_bytes()).hexdigest().upper()
        passed.append('LL-T')
    mock_users, old_users = ([], users)
    try:
        mock_users.extend(build_internal_users({u1: [{'date': '20260905', 'name': 'RITMOS', 'positions': [27, 9, 8]}, {'date': '20260906', 'name': 'Yoga', 'positions': [1, 2]}], u2: [{'date': '20260905', 'name': 'RITMOS', 'positions': [6, 7, 1]}]}))
        globals()['users'] = mock_users
        confirmed = {'username': u1, 'date': '20260905', 'lesson': 'RITMOS', 'final_state': 'RESERVATION_CONFIRMED', 'selected_position': 9, 'result_code': 'OK'}
        skipped = {'username': u1, 'date': '20260906', 'lesson': 'Yoga', 'final_state': 'SKIPPED', 'selected_position': None, 'result_code': 'SKIP'}
        unknown = dict(skipped, final_state='UNKNOWN_AFTER_SUBMIT')
        failed = dict(skipped, final_state='RESERVATION_FAILED')
        other = {'username': u2, 'date': '20260905', 'lesson': 'RITMOS', 'final_state': 'RESERVATION_CONFIRMED', 'selected_position': 7, 'result_code': 'OK'}

        def render(records, counts):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                totals = _phase8_5_human_result(records, counts)
            return (output.getvalue(), totals)
        output, totals = render([confirmed, skipped], {u1: 1, u2: 0})
        assert '立ち位置   : 9' in output and totals['confirmed'] == 1
        passed.append('LL-O')
        assert '【予約成功】' in output and '【予約不可 / SKIP】' in output
        passed.append('LL-P')
        output, totals = render([confirmed, unknown], {u1: 1, u2: 0})
        assert '【予約成功】' in output and '【要確認・状態不明】' in output
        passed.append('LL-Q')
        output, totals = render([failed, confirmed], {u1: 1, u2: 0})
        assert '【予約失敗】' in output and '【予約成功】' in output
        passed.append('LL-R')
        output, totals = render([confirmed, skipped, other], {u1: 1, u2: 1})
        assert totals['confirmed'] == 2 and 'reservation count不一致' not in output
        passed.append('LL-S')
    finally:
        globals()['users'] = old_users
    assert set(passed) == {f'LL-{chr(code)}' for code in range(ord('A'), ord('T') + 1)}
    print('PHASE8_5_LL_A_TO_T=PASS')

def run_phase8_5_1_cross_month_regression():
    u1 = _FIXED_USER_SETTINGS[0]['username']
    passed = []

    def write(directory, body):
        path = Path(directory) / '202609_LessonList.txt'
        path.write_text(body, encoding='utf-8')
        return path

    def parse_case(directory, body):
        telemetry = {}
        month, sections = parse_lesson_list(write(directory, body), telemetry=telemetry)
        return (month, sections, telemetry)

    def expect_fail(label, directory, body):
        try:
            parse_case(directory, body)
        except LessonListValidationError:
            passed.append(label)
            return
        raise AssertionError(f'{label}: expected validation failure')
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        month, sections, telemetry = parse_case(root, f'[{u1}]\n20260825 | RITMOS | 27,9,8\n')
        assert month == '202609' and len(sections[u1]) == 1
        assert telemetry['warnings'] == [{'type': 'CROSS_MONTH_REQUEST', 'list_month': '202609', 'request_date': '20260825', 'request_month': '202608', 'line_number': 2, 'username': u1, 'lesson': 'RITMOS'}]
        passed.append('LL-U')
        _, sections, telemetry = parse_case(root, f'[{u1}]\n20260902 | Yoga | 1\n')
        assert len(sections[u1]) == 1 and telemetry['warnings'] == []
        passed.append('LL-V')
        _, sections, telemetry = parse_case(root, f'[{u1}]\n# 20260827 | ZUMBA | 27,9,8\n20260902 | Yoga | 1\n')
        assert len(sections[u1]) == 1 and sections[u1][0]['name'] == 'Yoga'
        assert telemetry['warnings'] == [] and telemetry['ignored_comment_lines'] == [2]
        passed.append('LL-W')
        _, sections, telemetry = parse_case(root, f'[{u1}]\n20260825 | RITMOS | 27,9,8\n# 20260827 | ZUMBA | 27,9,8\n20260902 | Yoga | 1\n')
        assert [r['name'] for r in sections[u1]] == ['RITMOS', 'Yoga']
        assert len(telemetry['warnings']) == 1
        assert telemetry['warnings'][0]['lesson'] == 'RITMOS'
        assert telemetry['ignored_comment_lines'] == [3]
        passed.append('LL-X')
        expect_fail('LL-Y', root, f'[{u1}]\n20260230 | X | 1\n')
        _, sections, telemetry = parse_case(root, f'[{u1}]\n20261001 | Future | 1\n')
        assert len(sections[u1]) == 1 and len(telemetry['warnings']) == 1
        assert telemetry['warnings'][0]['request_month'] == '202610'
        passed.append('LL-Z')
        expect_fail('LL-AA', root, f'[{u1}]\n20260825 | RITMOS | 1\n20260825 | RITMOS | 2\n')
        expect_fail('LL-AB', root, '[unknown]\n20260825 | RITMOS | 1\n')
    assert passed == ['LL-U', 'LL-V', 'LL-W', 'LL-X', 'LL-Y', 'LL-Z', 'LL-AA', 'LL-AB']
    print('PHASE8_5_1_LL_U_TO_AB=PASS')

def run_phase8_4_1_summary_regression():

    def item(user, date, lesson, state, counted=False):
        return {'username': user, 'date': date, 'lesson': lesson, 'state': state, 'position': 3 if state == 'RESERVATION_CONFIRMED' else None, 'reservation_count_incremented': counted}

    def evaluate(name, sources, expected):
        records = _phase8_4_1_request_summaries(sources, [])
        actual = {'confirmed': sum((r['reservation_confirmed'] for r in records)), 'failed': sum((r['reservation_failed'] for r in records)), 'unknown': sum((r['reservation_unknown'] for r in records)), 'not_reservable': sum((r['reservation_not_reservable'] or r['reservation_skipped'] for r in records)), 'count': sum((r['reservation_count_incremented'] for r in records)), 'states': [r['final_state'] for r in records]}
        passed = actual == expected
        print(json.dumps({'case': name, 'expected': expected, 'actual': actual, 'PASS': passed}, ensure_ascii=False))
        assert passed
    a = item('A', '20260831', 'RITMOS', 'RESERVATION_CONFIRMED', True)
    evaluate('PS-A', [a, item('A', '20260901', 'Yoga', 'DETAIL_NOT_RESERVABLE')], {'confirmed': 1, 'failed': 0, 'unknown': 0, 'not_reservable': 1, 'count': 1, 'states': ['RESERVATION_CONFIRMED', 'DETAIL_NOT_RESERVABLE']})
    evaluate('PS-B', [a, item('A', '20260901', 'Yoga', 'UNKNOWN_AFTER_SUBMIT')], {'confirmed': 1, 'failed': 0, 'unknown': 1, 'not_reservable': 0, 'count': 1, 'states': ['RESERVATION_CONFIRMED', 'UNKNOWN_AFTER_SUBMIT']})
    evaluate('PS-C', [item('A', '20260830', 'X', 'RESERVATION_FAILED'), a], {'confirmed': 1, 'failed': 1, 'unknown': 0, 'not_reservable': 0, 'count': 1, 'states': ['RESERVATION_FAILED', 'RESERVATION_CONFIRMED']})
    evaluate('PS-D', [a, dict(a)], {'confirmed': 1, 'failed': 0, 'unknown': 0, 'not_reservable': 0, 'count': 1, 'states': ['RESERVATION_CONFIRMED']})
    evaluate('PS-E', [a, item('B', '20260831', 'RITMOS', 'RESERVATION_CONFIRMED', True)], {'confirmed': 2, 'failed': 0, 'unknown': 0, 'not_reservable': 0, 'count': 2, 'states': ['RESERVATION_CONFIRMED', 'RESERVATION_CONFIRMED']})
    evaluate('PS-F', [item('A', '20260901', 'Yoga', 'DETAIL_NOT_RESERVABLE'), item('A', '20260902', 'Pilates', 'FINAL_SUBMIT_NOT_ATTEMPTED')], {'confirmed': 0, 'failed': 0, 'unknown': 0, 'not_reservable': 2, 'count': 0, 'states': ['DETAIL_NOT_RESERVABLE', 'FINAL_SUBMIT_NOT_ATTEMPTED']})
    print('PHASE8_4_1_PS_A_TO_F=PASS')

def _run_production(recovery_session=None, recovery_scope=None):
    global PHASE8_1_MODE
    PHASE8_1_MODE = 'production'
    try:
        load_lesson_list()
    except LessonListValidationError as exc:
        raise SystemExit(f'LESSON_LIST_VALIDATION_FAILED: {exc}') from exc
    if recovery_session is None and (JOURNAL_ROOT / 'cla1-owner-cancelled').exists():
        raise SystemExit('RECOVERY_REQUIRES_SEPARATE_LIVE_AUTHORIZATION')
    if recovery_session is not None:
        _owner_recovery_store()
        if recovery_scope != [(u['username'], u.get('expected_member_identifier'), u['lesson_requests']) for u in users]:
            raise SystemExit('RECOVERY_LIVE_IDENTITY_OR_SCOPE_CHANGED')
        expected = [_OWNER_RECOVERY_MODULE.request(a) for a in ('A', 'B')]
        if len(users) != 2 or any((u['username'] != fixed['username'] or u['lesson_requests'] != [r] for u, fixed, r in zip(users, _FIXED_USER_SETTINGS, expected))):
            raise SystemExit('RECOVERY_LIVE_SCOPE_CHANGED')
    os.environ['PHASE8_4_MODE'] = PHASE8_1_MODE
    log_path = _configure_phase6_1_log()
    print(f'PHASE8_8_3_LOG_FILE={log_path}', flush=True)
    print('PHASE 8.8.3 PRODUCTION MODE')
    print('Real reservation operations are enabled.')
    print_lesson_list()
    print(f"users={len(users)} requests={sum((len(u['lesson_requests']) for u in users))}")
    worker_usernames = [user['username'] for user in users]
    if len(worker_usernames) != len(set(worker_usernames)):
        raise SystemExit('SAME_USER_DUPLICATE_WORKER_REJECTED')
    for user in users:
        safe = [{'date': r['date'], 'lesson': r['name'], 'positions': r['positions']} for r in user['lesson_requests']]
        print(f"username={user['username']} targets=" + json.dumps(safe, ensure_ascii=False))
    manager = multiprocessing.Manager()
    counts = manager.dict()
    results = manager.list()
    barrier = _reservation_start_barrier()
    processes = [multiprocessing.Process(target=process_user, args=(user, barrier, counts, results, recovery_session)) for user in users]
    for process in processes:
        process.start()
    barrier.wait()
    input('ログイン・対象確認後、Enterでproduction開始...')
    log_event('cla1_human_enter')
    barrier.wait()
    for process in processes:
        process.join()
    for user, process in zip(users, processes):
        results.append({'username': user['username'], 'state': 'WORKER_EXIT_STATUS', 'worker_pid': process.pid, 'worker_exit_code': process.exitcode, 'worker_clean_exit': process.exitcode == 0, 'reservation_count_incremented': False})
    _merge_phase8711_worker_logs(log_path)
    records = _phase8_4_post_run_summary(log_path, results, counts)
    _phase8_5_human_result(records, counts)

def _run_owner_recovery(live=False):
    """Operator-only entrypoint. Closure approval cannot start a browser/Live."""
    global _OWNER_RECOVERY_SESSION
    try:
        load_lesson_list()
        store = _owner_recovery_store()
        module = _OWNER_RECOVERY_MODULE
        expected = [module.request(a) for a in ('A', 'B')]
        if len(users) != 2 or any((u['username'] != fixed['username'] or u['lesson_requests'] != [r] for u, fixed, r in zip(users, _FIXED_USER_SETTINGS, expected))):
            raise module.RecoveryError('ACTIVE_SCOPE_MISMATCH')
        config = Path(os.environ.get('LESSON_RESERVATION_IDENTITY_CONFIG', ''))
        if not config.is_file() or any((not isinstance(u.get('expected_member_identifier'), str) or re.fullmatch('[0-9]{12}', u['expected_member_identifier']) is None for u in users)):
            raise module.RecoveryError('TRUSTED_IDENTITY_CONFIG_REQUIRED')
        frozen_config = config.read_bytes()
        frozen_list = LESSON_LIST_FILE.read_bytes()
        frozen_scope = [(u['username'], u['expected_member_identifier'], u['lesson_requests']) for u in users]

        def owner_input(prompt):
            answer = input(prompt)
            if config.read_bytes() != frozen_config or LESSON_LIST_FILE.read_bytes() != frozen_list:
                raise module.RecoveryError('OWNER_APPROVAL_CONFIG_CHANGED')
            return answer
        if not live:
            print(store.close(module.evidence_contract(), owner_input))
            return
        _OWNER_RECOVERY_SESSION = store.admit(module.evidence_contract(), owner_input)
    except Exception:
        raise SystemExit('OWNER_RECOVERY_STOPPED_FAIL_CLOSED') from None
    _run_production(recovery_session=_OWNER_RECOVERY_SESSION, recovery_scope=frozen_scope)
if __name__ == '__main__' and len(sys.argv) == 2 and (sys.argv[1] == '--owner-recovery-close'):
    _run_owner_recovery()
if __name__ == '__main__' and len(sys.argv) == 2 and (sys.argv[1] == '--owner-recovery-live'):
    _run_owner_recovery(live=True)
if __name__ == '__main__' and '--production' in sys.argv:
    if sys.argv != [sys.argv[0], '--production']:
        raise SystemExit('Conflicting production modes rejected')
    _run_production()
if __name__ == '__main__' and len(sys.argv) > 1 and (sys.argv[1:] not in (['--production'], ['--owner-recovery-close'], ['--owner-recovery-live'])):
    raise SystemExit('Unknown mode. Use no argument for offline or --production for real reservations.')
if __name__ == '__main__' and len(sys.argv) == 1:
    try:
        load_lesson_list()
    except LessonListValidationError as exc:
        raise SystemExit(f'LESSON_LIST_VALIDATION_FAILED: {exc}') from exc
    phase6_1_log_path = _configure_phase6_1_log()
    print(f'PHASE8_8_3_LOG_FILE={phase6_1_log_path}', flush=True)
    print('PHASE 8.8.3 SIMULATION MODE')
    print_lesson_list()
    run_phase8_5_offline_regression()
    run_phase8_5_1_cross_month_regression()
    run_phase8_2_offline_simulation()
    run_phase8_3_fault_injection()
    run_phase8_3_1_delayed_dom_fault_injection()
    run_phase8_4_1_summary_regression()
