"""Read/classify/record only. No network logs, waits, writes to DOM, or actions."""
import math

UNKNOWN = 'UNKNOWN'
PATHS = ('LOGIN_GET_PATH','LOGIN_ACTION_PATH','MENU_PATH','OTHER_SAME_ORIGIN','OTHER_ORIGIN',UNKNOWN)
BOOLS = ('document_ready origin_match login_form_present username_field_present '
         'password_field_present submit_element_present authenticated_marker_present '
         'identity_source_present document_transition_observed navigation_observed '
         'login_page_present login_page_exit').split()
STAGES = ('pre_submit','post_submit','post_wait','identity_reacquired','menu_ready_entry','terminal')

# Selectors/structure are copied from current FORM_SCRIPT / authoritative identity
# snapshot. No values/text are returned. timeOrigin stays in memory, never evidence.
SNAPSHOT_SCRIPT = r'''/* STAGEC_TRANSITION_SNAPSHOT */
const q=s=>Array.from(document.querySelectorAll(s));
const ns=q('#UserName,input[name="UserName"]'),ps=q('#Password,input[name="Password"],input[type="password"]'),bs=q('input.btn_conform');
const cs=q('#logindisplay'),hs=q('#logindisplay > div.atomsv-header-customer'),fs=q('#logindisplay > div.atomsv-header-customer > span:first-child');
const h=hs.length===1?hs[0]:null,f=fs.length===1?fs[0]:null,children=h?Array.from(h.children):[];
const visible=e=>{if(!e)return false;const s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility==='visible'&&s.opacity!=='0'&&r.width>0&&r.height>0;};
const structure=cs.length===1&&hs.length===1&&fs.length===1&&children.length===2&&children.every(e=>e.tagName==='SPAN')&&children[0]===f&&f.childElementCount===0&&Array.from(h.childNodes).every(n=>n.nodeType===1||(n.nodeType===3&&n.textContent.trim()===''));
const origin=location.origin==='https://www5.e-atoms.jp';
const path=!origin?'OTHER_ORIGIN':location.pathname==='/DSPWebUser/Account/LogIn'?'LOGIN_GET_PATH':location.pathname==='/DSPWebUser/Account/Login'?'LOGIN_ACTION_PATH':location.pathname==='/DSPWebUser/LESSON'?'MENU_PATH':'OTHER_SAME_ORIGIN';
return {document_ready:document.readyState==='complete',origin_match:origin,path_class:path,
 login_form_present:[...ns,...ps,...bs].some(e=>!!e.form),username_field_present:ns.length>0,password_field_present:ps.length>0,submit_element_present:bs.length>0,
 authenticated_marker_present:structure&&visible(f),identity_source_present:fs.length>0,
 _generation:typeof performance==='object'&&Number.isFinite(performance.timeOrigin)?performance.timeOrigin:null};
'''

def identity_script(original):
    # Original return/exception semantics retained; supplementary reads cannot
    # throw into the predicate. Both reads execute synchronously in one document.
    return ('/* STAGEC_TRANSITION_IDENTITY */ const value=(function(){'+original+
            '}).apply(null,arguments);let snapshot={};try{snapshot=(function(){'+
            SNAPSHOT_SCRIPT+'}).apply(null,arguments);}catch(e){}return {value:value,snapshot:snapshot};')

def tri(value):
    return value if type(value) is bool else UNKNOWN

def generation(value):
    return value if type(value) in (int,float) and math.isfinite(value) and value>0 else None

class Transition:
    def __init__(self, raw, trace):
        self.raw,self.trace=raw,trace
        self.before_generation=None
        self.identity_generation=None
        self.data=dict(schema_version='POST_SUBMIT_V1',timeline=[],snapshots={},
            login_click_invoked=False,selenium_click_returned=UNKNOWN,post_request_observed=UNKNOWN,
            identity_reacquired_after_submit=UNKNOWN,identity_reacquired_after_document_transition=UNKNOWN,
            identity_reacquired_after_login_page_exit=UNKNOWN,identity_exact_match=UNKNOWN,
            post_submit_authenticated_transition='NOT ESTABLISHED',
            menu_ready_entry_reached=False,menu_ready_entry_login_page_present=UNKNOWN,
            menu_ready_entry_authenticated_marker_present=UNKNOWN,menu_ready_entry_identity_verified=UNKNOWN,
            menu_ready_entry_path_class=UNKNOWN,menu_ready_result=UNKNOWN)
        trace.data['transition']=self.data
        trace.transition=self

    def snapshot(self, stage, raw=None):
        if stage not in STAGES: return
        if raw is None:
            try: raw=self.raw.execute_script(SNAPSHOT_SCRIPT)
            except Exception: raw={}
        raw=raw if type(raw) is dict else {}
        s={k:tri(raw.get(k)) for k in BOOLS}
        s['path_class']=raw.get('path_class') if type(raw.get('path_class')) is str and raw['path_class'] in PATHS else UNKNOWN
        g=generation(raw.get('_generation'))
        if stage=='pre_submit': self.before_generation=g
        elif self.before_generation is not None and g is not None:
            s['document_transition_observed']=g!=self.before_generation
        # A new time origin is a document navigation signal. Same generation
        # cannot exclude same-document navigation or a missed intermediate page.
        if s['document_transition_observed'] is True: s['navigation_observed']=True
        before=self.data['snapshots'].get('pre_submit',{})
        known=('LOGIN_GET_PATH','LOGIN_ACTION_PATH','MENU_PATH')
        if before.get('path_class') in known and s['path_class'] in known and before['path_class']!=s['path_class']:
            s['navigation_observed']=True
        markers=[s[k] for k in ('login_form_present','username_field_present','password_field_present','submit_element_present')]
        if s['path_class'] in ('LOGIN_GET_PATH','LOGIN_ACTION_PATH') or any(x is True for x in markers):
            s['login_page_present']=True
        elif s['origin_match'] is True and s['path_class'] in ('MENU_PATH','OTHER_SAME_ORIGIN') and all(x is False for x in markers):
            s['login_page_present']=False
        if stage!='pre_submit' and before.get('login_page_present') is True and type(s['login_page_present']) is bool:
            s['login_page_exit']=not s['login_page_present']
        self.data['snapshots'][stage]=s
        if stage=='identity_reacquired':
            self.identity_generation=g
            self.data['identity_reacquired_after_submit']=self.data['selenium_click_returned']
            self.data['identity_reacquired_after_document_transition']=s['document_transition_observed']
            self.data['identity_reacquired_after_login_page_exit']=s['login_page_exit']
        if stage=='menu_ready_entry':
            self.data['menu_ready_entry_reached']=True
            self.data['menu_ready_entry_login_page_present']=s['login_page_present']
            self.data['menu_ready_entry_authenticated_marker_present']=s['authenticated_marker_present']
            self.data['menu_ready_entry_identity_verified']=self.data['identity_exact_match']
            self.data['menu_ready_entry_path_class']=s['path_class']
        self.data['timeline'].append(stage.upper())

    def event(self, event, checkpoint=None):
        if event=='before_click': self.snapshot('pre_submit')
        elif event=='click_invoked':
            self.data['login_click_invoked']=True
            self.data['timeline'].append('LOGIN_CLICK_INVOKED')
        elif event=='click_returned':
            self.data['selenium_click_returned']=True
            self.data['timeline'].append('SELENIUM_CLICK_RETURNED')
            self.snapshot('post_submit')
        elif event=='done' and checkpoint=='POST_LOGIN_PAGE_WAIT': self.snapshot('post_wait')
        elif event=='start' and checkpoint=='MENU_READY':
            # Peer re-verification reuses this checkpoint. Preserve the first
            # entry context rather than replacing it with the later Menu page.
            if not self.data['menu_ready_entry_reached']: self.snapshot('menu_ready_entry')
        elif event=='done' and checkpoint=='IDENTITY_EXACT_MATCH':
            self.data['identity_exact_match']=True
            self.data['timeline'].append('IDENTITY_EXACT_MATCH')
            s=self.data['snapshots'].get('identity_reacquired',{})
            if (self.data['selenium_click_returned'] is True and
                all(s.get(k) is True for k in ('document_transition_observed','login_page_exit','origin_match','document_ready','authenticated_marker_present','identity_source_present'))):
                self.data['post_submit_authenticated_transition']='ESTABLISHED'
        elif event=='done' and checkpoint=='MENU_READY':
            self.data['menu_ready_result']=True
            self.data['timeline'].append('MENU_READY_RESULT')
        elif event=='fail':
            # An exception is not a negative DOM/identity observation.
            if checkpoint=='MENU_READY': self.data['menu_ready_result']=False
            self.snapshot('terminal')

def notify(trace, event, checkpoint=None):
    try:
        observer=getattr(trace,'transition',None)
        if observer is not None: observer.event(event,checkpoint)
    except Exception:
        pass  # Observe-only: do not affect original action/control semantics.

def record_identity(trace, raw):
    try: trace.transition.snapshot('identity_reacquired',raw if type(raw) is dict else {})
    except Exception: pass
