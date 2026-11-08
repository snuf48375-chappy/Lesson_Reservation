"""Only the OBS-2 Detail -> Schedule and OBS-1 Schedule -> Menu edges."""
import time
from urllib.parse import urlsplit

ORIGIN = 'https://www5.e-atoms.jp'
SCHEDULE = '/DSPWebUser/LESSON/ReserveLessonSchedule/ReserveList'
DETAIL = '/DSPWebUser/LESSON/ReserveLessonSchedule/Detail'
MENU = '/DSPWebUser/LESSON'
INQUIRY = '/DSPWebUser/LESSON/ReserveLessonSchedule/Inquiry'


def state(m, driver, user, request):
    if m._cla1_identity_guard(driver, user) is not None:
        return 'UNKNOWN'
    u = urlsplit(driver.current_url)
    if u.scheme + '://' + u.netloc != ORIGIN or u.query or u.fragment:
        return 'UNKNOWN'
    if u.path == SCHEDULE:
        result = m.classify_reservation_page_state(driver)
        return 'SCHEDULE' if result.code == 'OK' and result.state == 'RESERVATION_PAGE_READY' else 'UNKNOWN'
    if u.path == INQUIRY:
        proof = getattr(driver, '_request_local_inquiry', None)
        if proof and proof.get('request') == request and proof.get('verified') is True:
            import inquiry_reserved
            fresh = inquiry_reserved.probe(m, driver, user, request, proof['click_binding'])
            return 'INQUIRY' if inquiry_reserved.positive(fresh) else 'UNKNOWN'
    if u.path == DETAIL:
        result = m._phase7_4_classify_detail(m._phase7_4_detail_probe(driver), user, request)
        unselected = driver.execute_script("/* AG01_NO_POSITION */ return document.querySelectorAll('input[id^=LessonPosNo]:checked').length === 0;")
        if result.state in ('DETAIL_READY', 'DETAIL_NOT_RESERVABLE') and unselected is True:
            return 'DETAIL'
    if u.path == MENU:
        value = m._cla1_normal_ui_state(driver, MENU, 'レッスン予約メニュー')
        if all(value.get(k) is True for k in ('origin', 'path', 'title', 'ready', 'element')):
            return 'MENU'
    return 'UNKNOWN'


def back(m, driver, user, request, source, deadline, evidence):
    """One native site click; no retry after an uncertain click outcome."""
    expected = {'DETAIL': 'SCHEDULE', 'INQUIRY': 'SCHEDULE', 'SCHEDULE': 'MENU'}
    row = dict(source=source, destination=expected.get(source), clicks=0,
               source_verified=False, destination_verified=False)
    evidence.append(row)
    try:
        if source not in expected or time.monotonic() >= deadline or state(m, driver, user, request) != source:
            return False
        row['source_verified'] = True
        buttons = driver.find_elements('css selector', 'button#backsubmit')
        if len(buttons) != 1:
            row['failure'] = 'BACK_CONTROL_NOT_UNIQUE'
            return False
        button = buttons[0]
        binding = driver.execute_script('''/* AG01_BACK_BINDING */
          const b=arguments[0], f=b.form, path=arguments[1];
          const u=f?new URL(f.action,location.href):null;
          return b.isConnected && document.querySelectorAll('button#backsubmit').length===1 &&
            b.tagName==='BUTTON' && b.id==='backsubmit' && b.name==='backsubmit' &&
            b.type==='submit' && b.innerText.trim()==='戻る' &&
            !b.hasAttribute('onclick') && !b.hasAttribute('formaction') &&
            !b.hasAttribute('formmethod') && !b.hasAttribute('formtarget') &&
            b.getAttribute('aria-disabled')!=='true' && !!f && f.id==='main' &&
            f.method.toUpperCase()==='POST' && !f.target &&
            location.origin==='https://www5.e-atoms.jp' && location.pathname===path &&
            u.origin===location.origin && u.pathname===path && !u.search && !u.hash;
        ''', button, {'DETAIL': DETAIL, 'INQUIRY': INQUIRY, 'SCHEDULE': SCHEDULE}[source])
        if binding is not True or not button.is_displayed() or not button.is_enabled():
            row['failure'] = 'BACK_BINDING_UNVERIFIED'
            return False
        if state(m, driver, user, request) != source or time.monotonic() >= deadline:
            return False
        driver.set_page_load_timeout(min(9.0, deadline-time.monotonic()))
        row['clicks'] = 1
        button.click()
        while time.monotonic() < deadline:
            if state(m, driver, user, request) == expected[source]:
                row['destination_verified'] = True
                return True
            # Read-only observation only; no additional Back on unexpected pages.
            time.sleep(min(.05, max(0, deadline-time.monotonic())))
        row['failure'] = 'DESTINATION_UNVERIFIED'
    except Exception as exc:
        row['failure'] = 'BACK_OBSERVATION_OR_CLICK_' + type(exc).__name__
    return False


def to_menu(m, driver, user, request, deadline, evidence):
    current = state(m, driver, user, request)
    if current == 'DETAIL':
        if not back(m, driver, user, request, 'DETAIL', deadline, evidence):
            return False
        current = state(m, driver, user, request)
    if current == 'SCHEDULE':
        if not back(m, driver, user, request, 'SCHEDULE', deadline, evidence):
            return False
    return state(m, driver, user, request) == 'MENU'
