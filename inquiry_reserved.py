"""Observed Inquiry contract only; no navigation or reservation actions in probe."""
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit
import retry_continuation as rc
from lesson_target import names_match, range_start

PATH='/DSPWebUser/LESSON/ReserveLessonSchedule/Inquiry'
BASE='body.atomsv-body-LESSON-ReserveLessonSchedule-Inquiry form#main > div'

def probe(m,driver,user,request,click_binding):
    identity=m._cla1_identity_guard(driver,user) is None
    raw=driver.execute_script('''/* REQUEST_LOCAL_INQUIRY */
      const visible=e=>{if(!e||!e.isConnected)return false;
        for(let a=e;a;a=a.parentElement){let s=getComputedStyle(a);
          if(s.display==='none'||s.visibility==='hidden'||s.visibility==='collapse'||Number(s.opacity)===0)return false;}
        let r=e.getBoundingClientRect();return r.width>0&&r.height>0;};
      const forms=[...document.querySelectorAll('form#main')],f=forms.length===1?forms[0]:null;
      const markers=[...document.querySelectorAll(arguments[0])].filter(e=>e.textContent.trim()==='「予約中」');
      const tables=f?[...f.children].filter(e=>e.tagName==='TABLE'):[];
      const marker=markers.length===1?markers[0]:null;
      return {url:location.href,title:document.title,body_class:document.body.classList.contains('atomsv-body-LESSON-ReserveLessonSchedule-Inquiry'),
        forms:forms.length,marker_count:markers.length,marker_text:marker?marker.textContent.trim():null,
        marker_visible:visible(marker),marker_direct:!!marker&&marker.parentElement===f,
        tables:tables.map(t=>({lines:t.innerText.split(/\\r?\\n/).map(x=>x.trim()).filter(Boolean),visible:visible(t),
          after_marker:!!marker&&!!(marker.compareDocumentPosition(t)&Node.DOCUMENT_POSITION_FOLLOWING)})),
        blockers:[...document.querySelectorAll('.blockUI,[role=dialog],dialog[open]')].filter(visible).length,
        login:document.querySelectorAll('input[type=password]').length,
        document:document.documentElement};
    ''',BASE)
    u=urlsplit(raw.get('url',''))
    page=u.scheme+'://'+u.netloc=='https://www5.e-atoms.jp' and u.path==PATH and not u.query and not u.fragment and raw.get('body_class') is True and raw.get('title')=='レッスン予約内容照会' and raw.get('forms')==1
    tables=raw.get('tables',[])
    day=request['date']; date=f'{day[:4]}/{day[4:6]}/{day[6:8]}'
    def date_line(line): return re.fullmatch(re.escape(date)+r'\s*\([日月火水木金土]\)',line) is not None
    date_tables=[t for t in tables if any(date_line(x) for x in t['lines'])]
    lesson_tables=[t for t in tables if any(
        names_match(line, request['name'], day, request['start_time'], m.normalize_lesson_name)
        for line in t['lines'])]
    times=re.findall(r'\d{1,2}:\d{2}\s*[～〜~]\s*\d{1,2}:\d{2}',click_binding.get('anchor_text',''))
    compact=lambda x:re.sub(r'\s','',x).replace('〜','～').replace('~','～')
    target=(click_binding.get('identity_verified') is True and click_binding.get('date')==day and
        range_start(click_binding.get('anchor_text',''))==request.get('start_time') and
        len(times)==1 and len(date_tables)==1 and len(lesson_tables)==1 and
        any(compact(x)==compact(times[0]) and range_start(x)==request.get('start_time')
            for x in date_tables[0]['lines']))
    identity_tables=date_tables+lesson_tables
    associated=target and all(t.get('after_marker') is True for t in identity_tables)
    rendered=raw.get('blockers')==0 and raw.get('login')==0 and target and all(t.get('visible') is True for t in identity_tables)
    document=raw.pop('document',None)
    fresh=document is not None and driver.execute_script('return arguments[0] === document.documentElement && arguments[0].isConnected;',document) is True
    evidence=dict(page_verified=page,identity_verified=identity,target_verified=bool(target),render_verified=bool(rendered),
        marker_exact=raw.get('marker_count')==1 and raw.get('marker_text')=='「予約中」' and raw.get('marker_visible') is True,
        marker_associated=bool(associated and raw.get('marker_direct') is True),fresh=fresh,
        marker_text=raw.get('marker_text'),marker_count=raw.get('marker_count'),generation=uuid.uuid4().hex,
        observed_at=datetime.now(timezone.utc).isoformat(),raw=raw,click_binding=click_binding,
        target=dict(date=request['date'],lesson=request['name'],start_time=request['start_time']))
    return evidence

def positive(evidence):
    return all(evidence.get(k) is True for k in ('page_verified','identity_verified','target_verified','render_verified','marker_exact','marker_associated','fresh'))

def resolve_unknown(m,driver,user,request,click_binding):
    """Only on a separately authorized observation; never starts/resumes a worker."""
    runtime=m._rc_runtime
    runtime['store'].check()
    proof=probe(m,driver,user,request,click_binding)
    if not positive(proof): return False
    rc.reserved_result(runtime['journal'],runtime['rid'](request),proof,resolution=True)
    import ag01_ui_back as navigation
    import time
    driver._request_local_inquiry=dict(request=request,verified=True,click_binding=click_binding)
    rc.require(navigation.back(m,driver,user,request,'INQUIRY',time.monotonic()+25,[]), 'RESOLVED_UNKNOWN_INQUIRY_EXIT_FAILED')
    return True
