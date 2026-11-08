"""Strict reservation-list authority. No browser imports or personal data persistence."""
import hashlib
import json
import re
from datetime import datetime
from lesson_target import valid_time

MAX_REQUESTS_PER_WORKER = 7  # Owner's next-month scope; offline gate, unchanged 15 s final budget.

def require(ok, reason):
    if not ok:
        raise ValueError(reason)

def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode('utf-8')).hexdigest().upper()

def parse(text, usernames, canonical):
    require(len(usernames) == 2 and len(set(usernames)) == 2, 'EXACT_TWO_WORKER_BINDING')
    names = dict(zip(usernames, ('A', 'B')))
    requests = {'A': [], 'B': []}
    seen, sections, order = set(), set(), []
    current = None
    month = None
    for number, line in enumerate(text.lstrip('\ufeff').splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        if line.startswith('#'):
            if re.match(r'#\s*Month\b', line):
                require(line.startswith('# Month:'), 'MONTH_HEADER')
            if line.startswith('# Month:'):
                value = line[len('# Month:'):].strip()
                require(month is None and re.fullmatch(r'[0-9]{6}', value), 'MONTH_HEADER')
                datetime.strptime(value, '%Y%m')
                month = value
            continue
        if line.startswith('['):
            require(re.fullmatch(r'\[[^\[\]]+\]', line), 'MALFORMED_SECTION')
            name = line[1:-1]
            require(name in names and name not in sections, 'UNSUPPORTED_OR_DUPLICATE_USER')
            sections.add(name)
            current = names[name]
            continue
        require(current is not None, 'REQUEST_WITHOUT_USER')
        fields = [v.strip() for v in line.split('|')]
        require(len(fields) == 4, 'UNSUPPORTED_FIELDS')
        date, start_time, lesson, ranking = fields
        require(re.fullmatch(r'[0-9]{8}', date), 'DATE_FORMAT')
        datetime.strptime(date, '%Y%m%d')
        require(valid_time(start_time), 'START_TIME_FORMAT')
        require(bool(lesson) and not any(ord(c) < 32 for c in lesson), 'LESSON_EMPTY_OR_CONTROL')
        values = [v.strip() for v in ranking.split(',')]
        require(all(re.fullmatch(r'[1-9][0-9]*', v) for v in values), 'RANKING_FORMAT')
        positions = [int(v) for v in values]
        require(len(positions) == len(set(positions)), 'RANKING_DUPLICATE')
        key = (current, date, start_time, canonical(lesson))
        require(key not in seen, 'DUPLICATE_OR_AMBIGUOUS_LESSON')
        seen.add(key)
        requests[current].append(dict(date=date, start_time=start_time, name=lesson, positions=positions))
        order.append(current + str(len(requests[current])))
        require(len(requests[current]) <= MAX_REQUESTS_PER_WORKER, 'SAFE_MAXIMUM_EXCEEDED')
    require(month is not None, 'MONTH_HEADER_MISSING')
    require(bool(sections), 'SECTIONS_MISSING')
    require(all(r['date'][:6] == month for rows in requests.values() for r in rows),
            'ACTIVE_REQUEST_MONTH_MISMATCH')
    return dict(month=month, requests=requests, order=order,
                active_users=[a for a in ('A', 'B') if requests[a]],
                active_count=len(order))
