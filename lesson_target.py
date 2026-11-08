"""Pure, fail-closed CLA-1 date/time/name target checks.

The caller supplies the existing lesson-name normalizer. This module never
opens a browser, reads Production, or treats a time range as a start time.
"""
import re
import html
import unicodedata
from datetime import datetime

TIME = re.compile(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]\Z')
TIME_TOKEN = re.compile(r'(?<![0-9])(?:[01][0-9]|2[0-3]):[0-5][0-9](?![0-9])')
TIME_RANGE = re.compile(r'(?<![0-9])((?:[01][0-9]|2[0-3]):[0-5][0-9])\s*[～〜~]\s*((?:[01][0-9]|2[0-3]):[0-5][0-9])(?![0-9])')


def valid_time(value):
    return isinstance(value, str) and TIME.fullmatch(value) is not None


def canonical_name(value, normalize):
    name = unicodedata.normalize('NFKC', html.unescape(str(value or ''))).casefold()
    name = re.sub(r'\s+', '', name)
    name = re.sub('[－‐‑‒–—―−]', '-', name)
    for roman, reading in (('ritmos', 'リトモス'), ('zumba', 'ズンバ')):
        if name == roman + '(' + reading + ')':
            name = roman
    return name


SUNDAY_START = {'1': frozenset(('10:00', '10:30')), '2': frozenset(('11:30',))}
BODY_BALANCE_ST = frozenset(('ボディバランスst', 'ボディバランス※st'))


def names_match(displayed, requested, date, start_time, normalize):
    web, owner = canonical_name(displayed, normalize), canonical_name(requested, normalize)
    if not web or not owner:
        return False
    prefix = 'サンデープログラム'
    if web.startswith(prefix) or owner.startswith(prefix):
        if not (web.startswith(prefix) and owner.startswith(prefix)):
            return False
        web_suffix, owner_suffix = web[len(prefix):], owner[len(prefix):]
        if web_suffix not in ('', '1', '2') or owner_suffix not in ('', '1', '2'):
            return False
        if web_suffix and owner_suffix and web_suffix != owner_suffix:
            return False
        number = web_suffix or owner_suffix
        if number:
            try:
                sunday = datetime.strptime(str(date), '%Y%m%d').weekday() == 6
            except ValueError:
                return False
            return sunday and start_time in SUNDAY_START[number]
        return True
    # Only this observed notation pair is an alias; retain all other symbols.
    if frozenset((web, owner)) == BODY_BALANCE_ST:
        return True
    if web == owner:
        return True
    return False


def single_time(text):
    """Return one displayed HH:MM token; absent or multiple tokens fail closed."""
    values = TIME_TOKEN.findall(text or '')
    return values[0] if len(values) == 1 else None


def range_start(text):
    """Read the start of exactly one displayed time range, with no stray times."""
    value = str(text or '')
    ranges = TIME_RANGE.findall(value)
    tokens = TIME_TOKEN.findall(value)
    return ranges[0][0] if len(ranges) == 1 and len(tokens) == 2 else None


def matches(date, start_time, displayed_name, request, normalize):
    return (date == request.get('date') and valid_time(start_time)
            and start_time == request.get('start_time')
            and bool(displayed_name)
            and names_match(displayed_name, request.get('name'), date,
                            start_time, normalize))


def labeled_value(rows, labels):
    """Accept one explicit label/value row, with no extra content."""
    values = []
    for row in rows or []:
        lines = [part.strip() for part in str(row).splitlines() if part.strip()]
        if len(lines) == 2 and lines[0].rstrip('：:').strip() in labels:
            values.append(lines[1])
        elif len(lines) == 1:
            for label in labels:
                match = re.fullmatch(re.escape(label) + r'\s*[：:]\s*(.+)', lines[0])
                if match:
                    values.append(match.group(1).strip())
    return values[0] if len(values) == 1 else None
