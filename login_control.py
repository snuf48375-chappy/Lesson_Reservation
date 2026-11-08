"""Login/menu orchestration only. No reservation action or retry dispatcher."""
import time
from urllib.parse import urlsplit
from runtime_config import require
from credentials import binding_for
from selected_contracts import selected_menu_state

ORIGIN = 'https://www5.e-atoms.jp'
MENU = '/DSPWebUser/LESSON'
TITLE = 'レッスン予約メニュー'

# Return booleans and WebElements only, never values, HTML, action URL or body.
FORM_SCRIPT = r'''/* STAGEC_LOGIN_FORM */
const q=s=>Array.from(document.querySelectorAll(s));
const ns=q('#UserName,input[name="UserName"]'), ps=q('#Password,input[name="Password"],input[type="password"]');
const bs=q('input.btn_conform');
if(ns.length!==1||ps.length!==1||bs.length!==1) return false;
const [n,p,b]=[ns[0],ps[0],bs[0]], f=n.form;
const visible=e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();return r.width>0&&r.height>0&&s.visibility==='visible'&&s.display!=='none'&&!e.disabled;};
if(!f) return false;
const u=new URL(f.action,location.href);
return location.href===arguments[0] && document.readyState==='complete' &&
 n.id==='UserName'&&n.name==='UserName'&&['text','tel','email'].includes(n.type)&&
 p.id==='Password'&&p.name==='Password'&&p.type==='password'&&
 p.form===f&&b.form===f&&b.type==='submit'&&f.method.toUpperCase()==='POST'&&
 u.origin===location.origin&&u.pathname==='/DSPWebUser/Account/Login'&&!u.search&&!u.hash&&
 !f.target&&!b.hasAttribute('formaction')&&!b.hasAttribute('formmethod')&&!b.hasAttribute('formtarget')&&
 [n,p,b].every(visible) ? [n,p,b] : false;
'''

HEALTH_SCRIPT = r'''/* STAGEC_SESSION_HEALTH */
const visible=e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&s.opacity!=='0'&&r.width>0&&r.height>0;};
const text=String(document.body?document.body.innerText:'');
return {origin:location.origin===arguments[0],complete:document.readyState==='complete',
 exact_title:document.title===arguments[1],clean_url:!location.search&&!location.hash,
 no_login:document.querySelectorAll('#UserName,#Password,input[name="UserName"],input[name="Password"],input[type="password"]').length===0,
 session_valid:!['セッションの有効期限','再度ログイン','認証が必要','ユーザー名またはパスワード','ログインに失敗','認証に失敗'].some(x=>text.includes(x)),
 clear:!Array.from(document.querySelectorAll('.blockUI,.blockOverlay,.modal-backdrop,.loading,.overlay,[aria-busy="true"],[role="dialog"],[aria-modal="true"]')).some(e=>visible(e)&&getComputedStyle(e).pointerEvents!=='none')};
'''

MENU_LINK_SCRIPT = r'''/* STAGEC_MENU_LINK */
// PC-03 only. Never return a rewritten URL or change a DOM attribute.
const menuEntryPathMatches=(raw,pathname,expected)=>{
 if(expected!=='/DSPWebUser/LESSON'||typeof raw!=='string'||typeof pathname!=='string') return false;
 // Inspect the original href path as well: URL parsing may hide dot segments.
 if(/[\x00-\x20\x7f\\]/.test(raw)) return false;
 let rawPath=raw.split(/[?#]/,1)[0];
 const absolute=/^[A-Za-z][A-Za-z0-9+.-]*:\/\//.exec(rawPath);
 const authorityStart=absolute?absolute[0].length:rawPath.startsWith('//')?2:-1;
 if(authorityStart!==-1){
  const slash=rawPath.indexOf('/',authorityStart);
  if(slash===-1||rawPath.slice(authorityStart,slash).includes('@')) return false;
  rawPath=rawPath.slice(slash);
 }
 // Empty relative references retain the base pathname; search/hash guards below
 // still decide their query/fragment semantics. An empty pathname remains invalid.
 if(/[^A-Za-z/]/.test(rawPath)||rawPath.includes('//')) return false;
 if(/[^A-Za-z/]/.test(pathname)||!/^\/[A-Za-z]+\/[A-Za-z]+\/?$/.test(pathname)) return false;
 const body=pathname.endsWith('/')?pathname.slice(0,-1):pathname;
 const asciiLower=s=>s.replace(/[A-Z]/g,c=>String.fromCharCode(c.charCodeAt(0)+32));
 return asciiLower(body)===asciiLower(expected);
};
const links=Array.from(document.querySelectorAll('a[href]')).filter(a=>{
 const rawHref=a.getAttribute('href'),u=new URL(rawHref,location.href);
 return u.origin===arguments[0]&&menuEntryPathMatches(rawHref,u.pathname,arguments[1])&&!u.search&&!u.hash;
});
if(links.length!==1) return false;
const a=links[0];
return !a.target&&!a.hasAttribute('download')&&!a.hasAttribute('onclick')&&
 !a.hasAttribute('disabled')&&a.getAttribute('aria-disabled')!=='true'&&
 a.getClientRects().length>0&&getComputedStyle(a).visibility==='visible'?a:false;
'''


def check_identity(module, driver, user):
    raw = module._phase810_read_raw_snapshot(driver)
    require(not raw.get('login_fields_present') and
            module._cla1_identity_ok(raw.get('member_identity'), user.get('expected_member_identifier')),
            'IDENTITY_EXACT_MISMATCH')


def health(driver):
    return driver.execute_script(HEALTH_SCRIPT, ORIGIN, TITLE)


def menu_ready(module, driver, user, binding_check):
    binding_check()
    state = selected_menu_state(module, driver, MENU, TITLE)
    require(all(state.get(k) is True for k in ('origin', 'path', 'title', 'ready', 'element')),
            'MENU_STRUCTURE_NOT_READY')
    snapshot = health(driver)
    require(set(snapshot) == set(health_keys()) and all(v is True for v in snapshot.values()),
            'MENU_SESSION_NOT_READY')
    check_identity(module, driver, user)
    binding_check()


def health_keys():
    return ('origin', 'complete', 'exact_title', 'clean_url', 'no_login', 'session_valid', 'clear')


def automatic_login(module, driver, user, alias, provider, binding_check, mark):
    from diagnostic import Trace
    observation = getattr(driver, 'observation', None) or Trace()
    try:
        observation.start('CREDENTIAL_PREVALIDATION')
        binding_check()
        binding = binding_for(module, alias, user)
        observation.data['credential'].update(worker_binding='MATCH', expected_identity_binding='MATCH')
        provider.validate(binding)  # unavailable credentials fail before navigation.
        observation.data['credential']['automatic_prevalidation_retrieval'] = 'SUCCESS'
        observation.done('CREDENTIAL_PREVALIDATION')
        observation.start('LOGIN_GET_START', 'LOGIN_GET_FAILED')
        driver.set_page_load_timeout(15)
        observation.done('LOGIN_GET_START')
        observation.start('LOGIN_GET_RETURN', 'LOGIN_GET_FAILED')
        driver.get(module.LOGIN_URL)
        observation.done('LOGIN_GET_RETURN')
        observation.start('LOGIN_PAGE_SNAPSHOT', 'UNCLASSIFIED_EXCEPTION')
        form = driver.execute_script(FORM_SCRIPT, module.LOGIN_URL)
        observation.initial_binding(isinstance(form, list) and len(form) == 3)
        require(isinstance(form, list) and len(form) == 3, 'LOGIN_FORM_EXACT_BINDING')
        observation.start('CREDENTIAL_RUNTIME_RETRIEVAL', 'CREDENTIAL_RUNTIME_RETRIEVAL_FAILED')
        provider.fill(binding, form[0], form[1])
        observation.start('LOGIN_FORM_REBIND', 'FORM_REBIND_MISMATCH')
        rebound = driver.execute_script(FORM_SCRIPT, module.LOGIN_URL)
        observation.data['rebind']['same_elements'] = rebound == form
        require(rebound == form, 'LOGIN_FORM_CHANGED')
        observation.done('LOGIN_FORM_REBIND')
        observation.start('SUBMIT_GUARD_PASS', 'SUBMIT_GUARD_FAILED')
        # Invocation count is exactly one; any click exception is UNKNOWN, no observation-to-success fallback.
        form[2].click()
        observation.done('LOGIN_SUBMIT_RETURN')
        observation.start('POST_LOGIN_PAGE_WAIT', 'POST_LOGIN_TIMEOUT')
        deadline = time.monotonic() + 15
        while True:
            state = health(driver)
            require(state.get('origin') is True and state.get('session_valid') is True, 'LOGIN_FAILED')
            if state.get('complete') is True and state.get('no_login') is True:
                break
            require(time.monotonic() < deadline, 'LOGIN_OUTCOME_UNKNOWN')
            time.sleep(0.05)
        observation.done('POST_LOGIN_PAGE_WAIT')
        observation.start('IDENTITY_EXACT_MATCH', 'IDENTITY_MISMATCH')
        check_identity(module, driver, user)
        observation.done('IDENTITY_EXACT_MATCH')
        mark('login_complete')
        observation.start('MENU_READY', 'MENU_READY_FAILED')
        if urlsplit(driver.current_url).path != MENU:
            anchor = driver.execute_script(MENU_LINK_SCRIPT, ORIGIN, MENU)
            require(anchor is not False and anchor is not None, 'MENU_LINK_EXACT_BINDING')
            anchor.click()  # normal UI once; no direct menu GET and no blind retry.
        deadline = time.monotonic() + 15
        while True:
            require(health(driver).get('session_valid') is True, 'MENU_SESSION_INVALID')
            if selected_menu_state(module, driver, MENU, TITLE).get('ready') is True:
                menu_ready(module, driver, user, binding_check)
                break
            require(time.monotonic() < deadline, 'MENU_ARRIVAL_UNKNOWN')
            time.sleep(0.05)
        mark('menu_ready')
        observation.done('MENU_READY')
        return module.make_result('OK', 'LOGINED', automatic_login=True, menu_ready=True)
    except Exception as exc:
        from diagnostic import fet_context, fet_capture
        fet_context(observation.active)
        fet_capture('RUNTIME_ORIGINAL', exc)
        if observation.active == 'CREDENTIAL_PREVALIDATION':
            observation.data['credential']['automatic_prevalidation_retrieval'] = 'FAILURE'
        observation.fail(exc)
        # Do not let Selenium exception messages or DOM diagnostics enter evidence.
        raise ValueError('AUTOMATIC_LOGIN_FAIL_CLOSED') from None
