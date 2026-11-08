"""A-only observation navigator. No reservation worker or action API is exposed."""
import re
import time
from urllib.parse import urlsplit
import inquiry_reserved
import retry_continuation as rc

ORIGIN='https://www5.e-atoms.jp'
SCHEDULE_ENTRY=ORIGIN+'/DSPWebUser/LESSON/ReserveLessonSchedule'
SCHEDULE='/DSPWebUser/LESSON/ReserveLessonSchedule/ReserveList'


_VIEWPORT_MISSING=object()

def _viewport_status(target):
    value=target.get('in_viewport',_VIEWPORT_MISSING)
    if value is True: return 'VIEWPORT_TRUE'
    if value is False: return 'VIEWPORT_FALSE'
    if value is _VIEWPORT_MISSING: return 'VIEWPORT_MISSING'
    return 'VIEWPORT_INVALID'

_OVERLAY_PENDING=object()
_OVERLAY_MISSING=object()
OVERLAY_WAIT_SECONDS=5.0
OVERLAY_DELAY_SECONDS=0.5  # Existing Selenium WebDriverWait default poll interval.

def _overlay_status(snapshot):
    value=snapshot.get('blocking_overlay_count',_OVERLAY_MISSING)
    if value is _OVERLAY_MISSING: return 'MISSING'
    if type(value) is not int or value<0: return 'INVALID'
    return 'CLEAR' if value==0 else 'PRESENT'

# Same displayed/visibility/opacity/area predicate as wait_for_overlay_clear.
# Only the count crosses the Browser boundary; no URL or element descriptions.
OVERLAY_SINGLE_READ = """/* RESOLUTION_SINGLE_OVERLAY_READ */
    const overlays=Array.from(document.querySelectorAll('.blockUI'));
    const count=overlays.filter(element=>{
        const style=window.getComputedStyle(element), rect=element.getBoundingClientRect();
        const displayed=style.display!=='none';
        const visible=style.visibility!=='hidden' && style.opacity!=='0';
        const hasArea=rect.width>0 && rect.height>0;
        return displayed && visible && hasArea;
    }).length;
    return {blocking_overlay_count:count};
"""

def _observe_failure(exc,predicate,viewport,overlay,scroll,polls,generation,wait=None,rebind=None):
    try:
        import diagnostic
        diagnostic.fet_resolution_navigation_failure(exc,predicate,viewport,overlay,scroll,polls,generation,wait=wait,rebind=rebind)
    except BaseException:
        pass

class Inquiry:
    def __init__(self,module,driver,user,deadline,check):
        self.m,self.driver,self.user=module,driver,user
        self.deadline,self.check=deadline,check
        # Budgets reset only when a distinct request follows a successful observation.
        self._request_complete=True
        self._seen_requests=set()
        self._scroll_used=False
        self._overlay_wait_used=False
        self._rebind_used=False
        self._rebind_result=None

    def guard(self):
        self.check()
        remaining=self.deadline-time.monotonic()
        rc.require(remaining>0, 'RESOLUTION_DEADLINE')
        self.driver.set_page_load_timeout(min(10,remaining))
        self.driver.set_script_timeout(min(5,remaining))
        rc.require(self.m._cla1_identity_guard(self.driver,self.user) is None, 'RESOLUTION_IDENTITY')

    def observe(self,request):
        # A failure remains terminal for this Inquiry: no same/other-request retry.
        rc.require(self._request_complete, 'RESOLUTION_OBSERVATION_TERMINATED')
        key=(request['date'],request['name'])
        rc.require(key not in self._seen_requests, 'RESOLUTION_REQUEST_REPEATED')
        self._request_complete=False
        self._seen_requests.add(key)
        self._scroll_used=False
        self._overlay_wait_used=False
        self._rebind_used=False
        self._rebind_result=None
        proof=self._observe_request(request)
        self._request_complete=True
        return proof

    def _observe_request(self,request):
        self.guard()
        rc.require(self.m.RESERVATION_URL==SCHEDULE_ENTRY, 'RESOLUTION_SCHEDULE_SOURCE')
        # Existing fixed schedule GET is navigation, never a lesson form POST.
        # One attempt; no congestion recovery, reload, or worker fallback.
        self.driver.get(SCHEDULE_ENTRY)
        self.guard()
        u=urlsplit(self.driver.current_url)
        rc.require(u.scheme+'://'+u.netloc==ORIGIN and u.path==SCHEDULE and not u.query and not u.fragment,
                   'RESOLUTION_SCHEDULE_ARRIVAL')
        state=self.m.classify_reservation_page_state(self.driver)
        rc.require(state.code=='OK' and state.state=='RESERVATION_PAGE_READY', 'RESOLUTION_SCHEDULE_READY')
        wait=self.m.WebDriverWait(self.driver,min(5,self.deadline-time.monotonic()))
        # Reuse non-reservation schedule-page navigation and its positive redraw proof.
        date=self.m.ensure_target_date_visible(self.driver,wait,request['date'])
        rc.require(date.code=='OK', 'RESOLUTION_DATE_UNREACHABLE')
        self.guard()
        candidates=self.m._collect_lesson_candidates(self.driver,request)
        matches=[c for c in candidates if c.date==request['date'] and
                 c.normalized_name==self.m.normalize_lesson_name(request['name'])]
        rc.require(len(matches)==1, 'RESOLUTION_TARGET_AMBIGUOUS')
        c=matches[0]
        scroll_attempted=False
        handler=self._navigation_binding(c,request,False)
        c=self._active_candidate
        if handler is None:
            # Exactly one scroll of the same bound anchor, never a refind or retry loop.
            self.check()
            rc.require(time.monotonic()<self.deadline, 'RESOLUTION_DEADLINE')
            self._scroll_used=True
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});",c.anchor_element)
            self.check()
            rc.require(time.monotonic()<self.deadline, 'RESOLUTION_DEADLINE')
            scroll_attempted=True
            handler=self._navigation_binding(c,request,True)
            c=self._active_candidate
        if handler is _OVERLAY_PENDING:
            self._bounded_overlay_wait(scroll_attempted)
            handler=self._navigation_binding(c,request,scroll_attempted,post_overlay_poll=True)
            c=self._active_candidate
        binding=dict(anchor_text=c.anchor_element.text,date=request['date'],identity_verified=True)
        self.guard()
        rc.require(self.driver.execute_script('''/* RESOLUTION_FINAL_NAV_BINDING */
            const a=arguments[0],r=a.getBoundingClientRect(),s=getComputedStyle(a);
            const top=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);
            return location.origin===arguments[2] && location.pathname===arguments[3] && !location.search && !location.hash &&
              a.isConnected && a.tagName==='A' && a.getAttribute('onclick')===arguments[1] &&
              a.getAttribute('href')==='javascript:void(0);' && !a.hasAttribute('download') && !a.target &&
              !a.hasAttribute('disabled') && a.getAttribute('aria-disabled')!=='true' &&
              r.width>0 && r.height>0 && s.visibility==='visible' && s.display!=='none' && Number(s.opacity)!==0 &&
              (top===a || a.contains(top));
        ''',c.anchor_element,handler,ORIGIN,SCHEDULE) is True, 'RESOLUTION_NAVIGATION_CHANGED')
        c.anchor_element.click()  # one schedule lesson navigation; never a position/control click
        self.guard()
        # Detail, Confirm, or any unknown arrival fails here, without interacting with it.
        u=urlsplit(self.driver.current_url)
        rc.require(u.scheme+'://'+u.netloc==ORIGIN and u.path==inquiry_reserved.PATH and not u.query and not u.fragment,
                   'RESOLUTION_NOT_INQUIRY')
        proof=inquiry_reserved.probe(self.m,self.driver,self.user,request,binding)
        rc.require(inquiry_reserved.positive(proof), 'RESOLUTION_INQUIRY_NOT_POSITIVE')
        self.check()
        rc.require(time.monotonic()<self.deadline, 'RESOLUTION_DEADLINE')
        return proof

    def _bounded_overlay_wait(self,scroll_attempted):
        generation='POST_SCROLL' if scroll_attempted else 'INITIAL'
        attempted=False; status='PRESENT'; result='CHECK_FAILED'
        try:
            self.check()
            rc.require(not self._overlay_wait_used, 'RESOLUTION_OVERLAY_WAIT_EXHAUSTED')
            rc.require(time.monotonic()<self.deadline, 'RESOLUTION_DEADLINE')
            self._overlay_wait_used=True; attempted=True
            end=min(self.deadline,time.monotonic()+OVERLAY_WAIT_SECONDS)
            while True:
                self.check()
                now=time.monotonic()
                if now>=end:
                    result='TIMEOUT'
                    rc.require(now<self.deadline, 'RESOLUTION_DEADLINE')
                    rc.require(False, 'RESOLUTION_OVERLAY_TIMEOUT')
                self.driver.set_script_timeout(min(5,end-now))
                status=None
                observed=self.driver.execute_script(OVERLAY_SINGLE_READ)
                status=_overlay_status(observed) if type(observed) is dict else 'INVALID'
                self.check()
                now=time.monotonic()
                if now>=end:
                    result='TIMEOUT'
                    rc.require(now<self.deadline, 'RESOLUTION_DEADLINE')
                    rc.require(False, 'RESOLUTION_OVERLAY_TIMEOUT')
                if status=='CLEAR':
                    return
                rc.require(status=='PRESENT', 'RESOLUTION_OVERLAY_CHECK_FAILED')
                time.sleep(min(OVERLAY_DELAY_SECONDS,end-now))
        except BaseException as exc:
            _observe_failure(exc,None,None,status,scroll_attempted,int(attempted),generation,
                (attempted,result,generation),self._rebind_result)
            raise

    def _fresh_snapshot(self,request):
        try:
            return self.m._phase7_4_lesson_snapshot(self.driver,self._active_candidate.anchor_element,request)
        except BaseException as exc:
            if not isinstance(exc,getattr(self.m,'StaleElementReferenceException',())): raise
            if self._rebind_used:
                self._rebind_result='FAILED'
                raise
        # Leave the stale exception handler before recollection; no click/action retry.
        self._rebind_used=True
        self._rebind_result='FAILED'
        old=self._active_candidate
        original=(old.date,old.normalized_name,getattr(old,'href_or_onclick',None))
        stale_anchor=old.anchor_element
        self._active_candidate=None
        try:
            self.check()
            rc.require(time.monotonic()<self.deadline, 'RESOLUTION_DEADLINE')
            rc.require(self.m._cla1_identity_guard(self.driver,self.user) is None, 'RESOLUTION_IDENTITY')
            candidates=self.m._collect_lesson_candidates(self.driver,request)
            self.check()
            rc.require(time.monotonic()<self.deadline, 'RESOLUTION_DEADLINE')
            matching=[c for c in candidates if c.date==request['date'] and
                c.normalized_name==self.m.normalize_lesson_name(request['name'])]
            if not matching:
                self._rebind_result='NOT_FOUND' if not candidates else 'IDENTITY_MISMATCH'
                rc.require(False, 'RESOLUTION_REBIND_TARGET')
            if len(matching)!=1:
                self._rebind_result='MULTIPLE'
                rc.require(False, 'RESOLUTION_REBIND_TARGET')
            fresh=matching[0]
            identity=getattr(fresh,'href_or_onclick',None)
            valid=(type(original[2]) is str and type(identity) is str and
                re.fullmatch(r'LessonClick\([0-9]+,'+re.escape(request['date'])+r',1\);',original[2]) is not None and
                (fresh.date,fresh.normalized_name,identity)==original)
            if not valid:
                self._rebind_result='IDENTITY_MISMATCH'
                rc.require(False, 'RESOLUTION_REBIND_IDENTITY')
            rc.require(fresh.anchor_element is not None and fresh.anchor_element is not stale_anchor,
                'RESOLUTION_REBIND_ELEMENT')
            # Old elements are never queried/clicked; only scalar identity was compared.
            self._active_candidate=fresh
            snapshot=self.m._phase7_4_lesson_snapshot(self.driver,fresh.anchor_element,request)
            self.check()
            rc.require(time.monotonic()<self.deadline, 'RESOLUTION_DEADLINE')
            target=snapshot.get('target') or {}
            observed=[x for x in snapshot.get('candidates',[]) if self.m.is_matching_lesson_partial(x.get('text',''),request['name'])]
            identity_check=self.m._lesson_identity_comparison(fresh,target,observed,request)
            if (len(observed)!=1 or target.get('onclick')!=original[2] or
                not all(identity_check.get(k) is True for k in ('overall_identity_match','name_match','date_match'))):
                self._rebind_result='IDENTITY_MISMATCH'
                rc.require(False, 'RESOLUTION_REBIND_IDENTITY')
            self._rebind_result='SUCCESS'
            return snapshot
        except BaseException:
            self._active_candidate=None
            raise

    def _navigation_binding(self,c,request,scroll_attempted,post_overlay_poll=False):
        generation='POST_OVERLAY_POLL' if post_overlay_poll else ('POST_SCROLL' if scroll_attempted else 'INITIAL')
        polls=int(post_overlay_poll)
        wait=(True,'CLEAR','POST_SCROLL' if scroll_attempted else 'INITIAL') if post_overlay_poll else None
        self._active_candidate=c
        try:
            s=self._fresh_snapshot(request)
            c=self._active_candidate
        except BaseException as exc:
            _observe_failure(exc,None,None,None,scroll_attempted,polls,generation,wait,self._rebind_result)
            raise
        t=s.get('target') or {}
        observed=[x for x in s.get('candidates',[]) if self.m.is_matching_lesson_partial(x.get('text',''),request['name'])]
        identity=self.m._lesson_identity_comparison(c,t,observed,request)
        geometry=t.get('geometry') or {}
        # This is the observed navigation-only LessonClick shape, not an arbitrary onclick.
        handler=t.get('onclick','')
        viewport_status=None  # P8 not evaluated yet; do not inspect it early.
        overlay_status=None  # P7 not evaluated yet.
        # Mark only predicates actually reached by the original short-circuit AND.
        # Truthy local labels add no browser call and never inspect predicate values.
        try:
            rc.require(
                ((predicate := 'P1') and (re.fullmatch(r'LessonClick\([0-9]+,'+re.escape(request['date'])+r',1\);',handler) is not None))
                and ((predicate := 'P2') and (t.get('href')=='javascript:void(0);'))
                and ((predicate := 'P3') and (len(observed)==1))
                and ((predicate := 'P4') and (identity.get('overall_identity_match') is True))
                and ((predicate := 'P5') and (identity.get('name_match') is True))
                and ((predicate := 'P6') and (identity.get('date_match') is True))
                and ((predicate := 'P7') and ((overlay_status := _overlay_status(s)) == 'CLEAR'))
                and ((predicate := 'P8') and ((viewport_status := _viewport_status(t)) == 'VIEWPORT_TRUE'))
                and ((predicate := 'P9') and (geometry.get('width',0)>0))
                and ((predicate := 'P10') and (geometry.get('height',0)>0))
                and ((predicate := 'P11') and (t.get('topmost_relation') in ('SELF','DESCENDANT')))
                and ((predicate := 'P12') and (not t.get('disabled')))
                and ((predicate := 'P13') and (t.get('aria_disabled')!='true'))
                and ((predicate := 'P14') and (c.anchor_element.is_displayed()))
                and ((predicate := 'P15') and (c.anchor_element.is_enabled())),
                'RESOLUTION_NAVIGATION_BINDING')
        except BaseException as exc:
            tail=exc.__traceback__.tb_next
            own_failure=(type(exc) is ValueError and exc.args==('RESOLUTION_NAVIGATION_BINDING',)
                and tail is not None and tail.tb_frame.f_code is rc.require.__code__
                and tail.tb_next is None)
            if (own_failure and predicate=='P8' and viewport_status=='VIEWPORT_FALSE'
                and not scroll_attempted and not self._scroll_used and not post_overlay_poll):
                return None  # Eligibility only. Scroll runs outside this exception handler.
            if (own_failure and predicate=='P7' and overlay_status=='PRESENT'
                and not self._overlay_wait_used and not post_overlay_poll):
                return _OVERLAY_PENDING
            _observe_failure(exc,predicate if own_failure else None,viewport_status,overlay_status,
                scroll_attempted,polls,generation,wait,self._rebind_result)
            raise  # Evaluation exceptions remain exceptions, never viewport FALSE.
        return handler

    def close(self):
        self.driver.quit()
