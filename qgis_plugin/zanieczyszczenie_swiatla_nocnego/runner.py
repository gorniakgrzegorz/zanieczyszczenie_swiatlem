# -*- coding: utf-8 -*-
"""Logika niezależna od Qt: wyszukiwanie interpretera Pythona, środowisko procesu, polecenia pip, parsowanie komunikatów silnika.

Qt-independent logic: finding a Python interpreter, process environment, pip commands, parsing engine messages.
Analiza działa w OSOBNYM procesie Pythona z własnym zestawem bibliotek (folder "libs" w profilu QGIS), więc nie koliduje z bibliotekami QGIS (GDAL, PROJ).
The analysis runs in a SEPARATE Python process with its own set of libraries ("libs" folder in the QGIS profile), so it cannot clash with QGIS libraries (GDAL, PROJ).
"""
import os
import sys
import shutil
import subprocess  # nosec B404

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(PLUGIN_DIR, 'engine', 'night_light.py')

# pakiety instalowane do folderu libs (koła binarne; bez kompilacji) / packages installed into the libs folder (binary wheels only)
PACKAGES = ['earthengine-api', 'numpy', 'pandas', 'geopandas', 'shapely', 'pyogrio', 'rasterio', 'matplotlib', 'pillow']
IMPORT_CHECK = 'import ee, numpy, pandas, geopandas, shapely, pyogrio, rasterio, matplotlib, PIL; print("DEPS_OK")'

# zmienne środowiska QGIS, które psują osobny Python (inne wersje PROJ/GDAL) / QGIS variables that break a separate Python (other PROJ/GDAL versions)
DROP_ENV = ('PYTHONHOME', 'PYTHONPATH', 'PYTHONSTARTUP', 'PYTHONEXECUTABLE', 'PROJ_LIB', 'PROJ_DATA', 'GDAL_DATA', 'GDAL_DRIVER_PATH', 'GDAL_PLUGINS',
            'GEOTIFF_CSV', 'GDAL_FILENAME_IS_UTF8', 'QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH', 'PYTHONNOUSERSITE')


def libs_dir(settings_dir):
    """Folder z bibliotekami wtyczki (w profilu użytkownika QGIS, przetrwa aktualizację wtyczki)."""
    return os.path.join(settings_dir, 'zanieczyszczenie_swiatla_nocnego_libs')


def _run_ok(exe, timeout=20):
    """Czy exe to działający Python 3.9+ (zwraca wersję lub None)."""
    try:
        r = subprocess.run([exe, '-c', 'import sys; print("%d.%d" % sys.version_info[:2])'], capture_output=True, text=True, timeout=timeout,  # nosec B603
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if r.returncode != 0:
            return None
        ver = r.stdout.strip().splitlines()[-1]
        major, minor = (int(x) for x in ver.split('.')[:2])
        return ver if (major, minor) >= (3, 9) else None
    except Exception:
        return None


def python_candidates(override=None):
    """Kolejność: wskazany ręcznie, Python wbudowany w QGIS (ten sam, w którym działa wtyczka), potem Python z PATH."""
    cands = []
    if override:
        cands.append(override)
    base = os.path.basename(sys.executable).lower()
    if base.startswith('python'):
        cands.append(sys.executable)
    for prefix in {sys.prefix, sys.exec_prefix, getattr(sys, 'base_prefix', sys.prefix)}:
        if os.name == 'nt':
            cands += [os.path.join(prefix, 'python.exe'), os.path.join(prefix, 'python3.exe')]
        else:
            cands += [os.path.join(prefix, 'bin', 'python3'), os.path.join(prefix, 'bin', 'python')]
    be = getattr(sys, '_base_executable', None)
    if be:
        cands.append(be)
    for name in ('python3', 'python'):
        w = shutil.which(name)
        if w:
            cands.append(w)
    seen, out = set(), []
    for c in cands:
        if c and c not in seen and os.path.isfile(c):
            seen.add(c)
            out.append(c)
    return out


def find_python(override=None):
    """Zwraca (ścieżka, wersja) pierwszego działającego interpretera Python 3.9+ albo (None, None)."""
    for c in python_candidates(override):
        v = _run_ok(c)
        if v:
            return c, v
    return None, None


def process_env(libs, extra_pythonpath=None, base_env=None):
    """Środowisko procesu pomocniczego jako słownik: bez zmiennych QGIS psujących Python, z folderem libs w PYTHONPATH."""
    env = dict(os.environ if base_env is None else base_env)
    for k in DROP_ENV:
        env.pop(k, None)
    paths = ([extra_pythonpath] if extra_pythonpath else []) + [libs]
    env['PYTHONPATH'] = os.pathsep.join(paths)
    env['PYTHONNOUSERSITE'] = '1'
    env['PYTHONUTF8'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUNBUFFERED'] = '1'
    env['MPLBACKEND'] = 'Agg'
    return env


def pip_command(py, libs):
    """Polecenie instalacji bibliotek do folderu libs (tylko koła binarne)."""
    return [py, '-m', 'pip', 'install', '--disable-pip-version-check', '--no-warn-script-location', '--only-binary=:all:', '--upgrade', '--target', libs] + PACKAGES


def pip_command_text(py, libs):
    """To samo polecenie jako tekst do wklejenia w terminalu (OSGeo4W Shell, terminal)."""
    return ' '.join(f'"{x}"' if (' ' in x) else x for x in pip_command(py, libs))


def parse_line(line):
    """Komunikaty silnika: @@STAGE|n|N|tekst, @@PROG|k|K|tekst, @@GEE_ERROR|rodzaj|tekst, @@ERROR|rodzaj|tekst, @@RESULT|folder, @@AUTH_OK, @@CHECK_OK."""
    line = line.rstrip('\r\n')
    if not line.startswith('@@'):
        return {'type': 'log', 'text': line}
    parts = line[2:].split('|', 3)
    tag = parts[0]
    try:
        if tag == 'STAGE':
            return {'type': 'stage', 'n': int(parts[1]), 'total': int(parts[2]), 'text': parts[3] if len(parts) > 3 else ''}
        if tag == 'PROG':
            return {'type': 'prog', 'done': int(parts[1]), 'total': max(1, int(parts[2])), 'text': parts[3] if len(parts) > 3 else ''}
        if tag in ('GEE_ERROR', 'ERROR'):
            rest = line[2:].split('|', 2)
            return {'type': tag.lower(), 'kind': rest[1] if len(rest) > 1 else 'other', 'text': rest[2] if len(rest) > 2 else ''}
        if tag == 'RESULT':
            return {'type': 'result', 'path': line[2:].split('|', 1)[1]}
        if tag in ('AUTH_OK', 'CHECK_OK'):
            return {'type': tag.lower()}
    except (IndexError, ValueError):
        pass
    return {'type': 'log', 'text': line}


def progress_value(stage_n, stage_total, done=0, total=1):
    """Postęp ogólny 0–100 z etapu i postępu w etapie."""
    stage_total = max(1, stage_total)
    frac = (max(stage_n, 1) - 1 + (done / total if total else 0)) / stage_total
    return int(max(0, min(100, round(frac * 100))))


def credentials_path():
    """Plik z poświadczeniami Earth Engine zapisywany po zalogowaniu (profil użytkownika, nie wtyczka)."""
    return os.path.join(os.path.expanduser('~'), '.config', 'earthengine', 'credentials')


def parse_rings(text):
    """'2000, 5000' -> [2000.0, 5000.0]; ValueError przy błędnym wpisie."""
    vals = []
    for p in str(text).replace(';', ',').split(','):
        p = p.strip().replace(' ', '')
        if not p:
            continue
        v = float(p.replace(',', '.')) if p.count(',') == 1 and '.' not in p else float(p)
        if v <= 0:
            raise ValueError('ring radius must be positive')
        vals.append(v)
    if not vals:
        raise ValueError('no ring radius')
    return sorted(set(vals))


def parse_thresholds(text):
    vals = []
    for p in str(text).replace(';', ',').split(','):
        p = p.strip()
        if p:
            vals.append(float(p))
    return vals
