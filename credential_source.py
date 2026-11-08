"""Compile the locked source without its historical credential constants.

The on-disk Authority is unchanged. Only nonempty password dictionary literals
are replaced; all other AST nodes remain identical. No bytecode is persisted.
"""
import ast
import contextlib
import importlib.util
import os
import sys
from pathlib import Path
from runtime_config import require


def sanitized_tree(source):
    tree = ast.parse(source)
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value == 'password':
                    require(isinstance(value, ast.Constant) and isinstance(value.value, str),
                            'CREDENTIAL_SOURCE_SHAPE_CHANGED')
                    if value.value:
                        value.value = ''
                        count += 1
    require(count == 2, 'CREDENTIAL_SOURCE_SHAPE_CHANGED')
    return tree


def load(name, path):
    # runtime.verify_package verifies the locked file before this call.
    from package_authority import OPERATIONAL_ROOT
    expected = str(OPERATIONAL_ROOT)
    expected_journal = str(OPERATIONAL_ROOT / 'runtime/reservation_journal/schema-v1')
    for key, value in (('LESSON_RESERVATION_PROJECT_ROOT', expected), ('LESSON_RESERVATION_JOURNAL_DIR', expected_journal)):
        require(key not in os.environ or Path(os.environ[key]) == Path(value), 'STATE_ENV_OVERRIDE_FORBIDDEN')
        os.environ[key] = value
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    # __file__ retains the locked module's directory contract; executable code
    # comes exclusively from the manifest-bound sanitized replacement.
    replacement = Path(__file__).with_name('credential_free_locked.py')
    code = compile(replacement.read_text(encoding='utf-8'), '<credential-free-locked-source>', 'exec')
    sys.modules[name] = module
    try:
        with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            exec(code, module.__dict__)
    except Exception:
        sys.modules.pop(name, None)
        raise ValueError('CREDENTIAL_FREE_SOURCE_LOAD_FAILED') from None
    return module
