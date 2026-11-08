"""C2: explicitly selected MENU_READY document contract; no URL rewriting.

PC-03's existing helper remains byte identical. This implements its same static
ASCII/two-segment/single-slash policy for parsed arrival path only. Raw entry
lexical guards stay at PC-03. The shared locked module is never patched.
"""
import ast
from pathlib import Path

SELECTED_CONTRACTS = ('MENU_ENTRY_LINK', 'MR-U17_PC-15_MENU_ARRIVAL')
EXACT_EXPRESSION = 'location.pathname === arguments[0]'
C2_EXPRESSION = 'selectedMenuArrivalPathMatches(location.pathname, arguments[0])'
POLICY_SCRIPT = r'''
const selectedMenuArrivalPathMatches=(path,expected)=>{
 if(expected!=='/DSPWebUser/LESSON'||typeof path!=='string') return false;
 // No regex, decoding, URL parsing, Unicode folding or slash normalization.
 const canonical='/dspwebuser/lesson';
 if(path.length!==canonical.length&&path.length!==canonical.length+1) return false;
 if(path.length===canonical.length+1&&path[canonical.length]!=='/') return false;
 for(let i=0;i<canonical.length;i++){
  let c=path.charCodeAt(i);
  if(c>=65&&c<=90)c+=32;
  if(c!==canonical.charCodeAt(i)) return false;
 }
 return true;
};
'''

def selected_script(original):
    if original.count(EXACT_EXPRESSION)!=1:
        raise ValueError('C2_SCRIPT_BINDING')
    return POLICY_SCRIPT+original.replace(EXACT_EXPRESSION,C2_EXPRESSION)

tree=ast.parse((Path(__file__).with_name('credential_free_locked.py')).read_text(encoding='utf-8'))
fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_cla1_normal_ui_state')
ORIGINAL_UI_SCRIPT=next(n.args[0].value for n in ast.walk(fn) if isinstance(n,ast.Call)
    and isinstance(n.func,ast.Attribute) and n.func.attr=='execute_script')
SELECTED_UI_SCRIPT=selected_script(ORIGINAL_UI_SCRIPT)

def selected_menu_state(module,driver,path,title):
    if path!='/DSPWebUser/LESSON':
        raise ValueError('C2_SELECTED_CONTRACT_BINDING')
    class SelectedDriver:
        def __getattr__(self,name):
            return getattr(driver,name)
        def execute_script(self,script,*args):
            if script!=ORIGINAL_UI_SCRIPT or args!=(path,title):
                raise ValueError('C2_UI_SCRIPT_BINDING')
            return driver.execute_script(SELECTED_UI_SCRIPT,*args)
    # Only two explicit login controller callsites select this adapter.
    # Reservation calls retain the locked function and strict original script.
    return module._cla1_normal_ui_state(SelectedDriver(),path,title)
