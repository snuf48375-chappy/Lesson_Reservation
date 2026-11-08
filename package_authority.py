"""Fixed package/state authority. No CLI or environment override."""
import json, hashlib
from pathlib import Path
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
BINDING_PATH = PACKAGE_ROOT / 'deployment-binding.json'
EXPECTED_BINDING_SHA = 'D8F2186DF669353C345EB98BDF3D14B1C07C0FC7580A1DF0ECA1A0176840EC4F'
EXPECTED_PACKAGE_ROOT = Path('C:\\Users\\Takashi\\OneDrive\\Desktop\\Lesson_Reservation\\current')
def deployment():
    if PACKAGE_ROOT != EXPECTED_PACKAGE_ROOT or PACKAGE_ROOT.resolve() != PACKAGE_ROOT.absolute():
        raise ValueError('PACKAGE_AUTHORITY_MISMATCH')
    content = BINDING_PATH.read_bytes()
    if hashlib.sha256(content).hexdigest().upper() != EXPECTED_BINDING_SHA:
        raise ValueError('DEPLOYMENT_BINDING_MISMATCH')
    value = json.loads(content)
    root = Path(value['operational_root'])
    if root.resolve() != root.absolute():
        raise ValueError('STATE_AUTHORITY_REDIRECTED')
    return value
OPERATIONAL_ROOT = Path(deployment()['operational_root'])
def package_path(relative):
    p = PACKAGE_ROOT / relative
    if Path(relative).is_absolute() or '..' in Path(relative).parts or p.resolve() != p.absolute() or not p.is_relative_to(PACKAGE_ROOT):
        raise ValueError('PACKAGE_PATH_ESCAPE')
    return p
