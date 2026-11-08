"""Prepare a compatible local ChromeDriver before Live; never download at login."""
import json
import os
import re
import subprocess
from pathlib import Path

from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.selenium_manager import SeleniumManager

ROOT = Path(r'C:\Users\Takashi\OneDrive\Desktop\Lesson_Reservation')
CHROME = Path(r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe')
CACHE = ROOT / 'runtime/drivers/selenium-cache'
SELECTION = ROOT / 'runtime/drivers/cla1-driver-selection.json'


def require(ok, code):
    if not ok:
        raise RuntimeError(code)


def version(path, label):
    require(path.is_file(), label + '_MISSING')
    try:
        result = subprocess.run([str(path), '--version'], capture_output=True,
                                timeout=10, check=True)
        match = re.search(rb'\b(\d+)\.\d+\.\d+\.\d+\b', result.stdout)
    except (OSError, subprocess.SubprocessError):
        match = None
    require(match is not None, label + '_VERSION_UNKNOWN')
    return int(match.group(1)), match.group(0).decode('ascii')


def checked_cache():
    require(CACHE.resolve() == CACHE.absolute(), 'CLA1_DRIVER_CACHE_REDIRECTED')
    require(SELECTION.resolve() == SELECTION.absolute(), 'CLA1_DRIVER_SELECTION_REDIRECTED')


def cached_for(browser_major, browser_version):
    """Use a verified local driver without invoking Selenium Manager or network."""
    base = CACHE / 'chromedriver/win64'
    if not base.is_dir():
        return None
    matches = []
    for candidate in base.glob('*/chromedriver.exe'):
        if not candidate.is_file() or not candidate.resolve().is_relative_to(CACHE.resolve()):
            continue
        try:
            major, found = version(candidate, 'DRIVER')
        except RuntimeError:
            continue
        if major == browser_major:
            matches.append((found == browser_version, tuple(map(int, found.split('.'))), candidate, found))
    if not matches:
        return None
    _, _, path, found = max(matches)
    return path, found


def prepare_driver():
    checked_cache()
    browser_major, browser_version = version(CHROME, 'CHROME')
    CACHE.mkdir(parents=True, exist_ok=True)
    try:
        cached = cached_for(browser_major, browser_version)
        if cached is None:
            require(not os.getenv('SE_MANAGER_PATH'), 'CLA1_SELENIUM_MANAGER_OVERRIDE')
            found = SeleniumManager().binary_paths([
                '--browser', 'chrome', '--browser-path', str(CHROME),
                '--cache-path', str(CACHE), '--skip-driver-in-path',
                '--avoid-browser-download', '--timeout', '20'])
            driver = Path(found['driver_path']).resolve()
            require(Path(found['browser_path']).resolve() == CHROME.resolve(),
                    'CLA1_BROWSER_REDIRECTED')
            require(driver.is_relative_to(CACHE.resolve()), 'CLA1_DRIVER_REDIRECTED')
            driver_major, driver_version = version(driver, 'DRIVER')
            require(driver_major == browser_major, 'CLA1_CHROME_DRIVER_MISMATCH')
        else:
            driver, driver_version = cached
        require(version(CHROME, 'CHROME')[1] == browser_version,
                'CLA1_CHROME_UPDATED_DURING_PREPARATION')
        selection = dict(browser=str(CHROME), browser_version=browser_version,
                         driver=str(driver), driver_version=driver_version)
        pending = SELECTION.with_suffix('.pending')
        pending.write_text(json.dumps(selection, sort_keys=True), encoding='ascii')
        pending.replace(SELECTION)
        return selection
    except Exception as exc:
        SELECTION.unlink(missing_ok=True)
        if isinstance(exc, RuntimeError):
            raise
        raise RuntimeError('CLA1_COMPATIBLE_DRIVER_UNAVAILABLE') from exc


def chrome_service():
    """Only local version checks at each Chrome creation, including retries."""
    checked_cache()
    try:
        selected = json.loads(SELECTION.read_text(encoding='ascii'))
        driver = Path(selected['driver']).resolve()
        require(driver.is_relative_to(CACHE.resolve()), 'CLA1_DRIVER_REDIRECTED')
        require(selected['browser'] == str(CHROME), 'CLA1_BROWSER_REDIRECTED')
        browser_major, browser_version = version(CHROME, 'CHROME')
        driver_major, driver_version = version(driver, 'DRIVER')
        require(browser_major == driver_major and
                browser_version == selected['browser_version'] and
                driver_version == selected['driver_version'],
                'CLA1_DRIVER_PREPARATION_STALE')
    except (OSError, KeyError, ValueError, TypeError) as exc:
        raise RuntimeError('CLA1_DRIVER_NOT_PREPARED') from exc
    service = Service(executable_path=str(driver),
                      driver_path_env_key='CLA1_VERIFIED_DRIVER_PATH')
    require(Path(service.path).resolve() == driver,
            'CLA1_DRIVER_ENV_REDIRECTED')
    return service
