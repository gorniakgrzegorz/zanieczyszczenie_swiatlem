# -*- coding: utf-8 -*-
"""Silnik wtyczki QGIS "Zanieczyszczenie światłem nocnym" / engine of the QGIS plugin "Night-time light pollution".

Działa w osobnym procesie Pythona (uruchamia go wtyczka); można go też uruchomić samodzielnie:
    python night_light.py --config konfiguracja.json     # pełna analiza
    python night_light.py --check --project MOJ_PROJEKT  # test połączenia z Google Earth Engine
    python night_light.py --auth                         # logowanie do Google Earth Engine (otwiera przeglądarkę)

Analiza: sztuczne światło nocą z miesięcznych kompozytów VIIRS DNB (NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG) dla obszaru z pliku GPKG
i jego otoczenia: pobieranie z Google Earth Engine, GeoTIFF, tabele, trend Theila-Sena z testem Manna-Kendalla, ryciny i animacje.

Kody wyjścia / exit codes: 0 = OK, 2 = któryś moduł przerwany błędem (reszta wyników zapisana), 3 = błąd Earth Engine, 4 = błąd danych wejściowych.
Linie "@@..." na standardowym wyjściu to komunikaty dla wtyczki (etap, postęp, błąd).
"""
import os, sys, io, re, json, time, math, hashlib, datetime, warnings, traceback, argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

LANG = 'pl'


def T(pl, en):
    """Tekst w języku wybranym w konfiguracji (pl lub en)."""
    return en if LANG == 'en' else pl


def say(*a):
    print(*a, flush=True)


def stage(n, total, text):
    say(f'@@STAGE|{n}|{total}|{text}')


def prog(done, total, text):
    say(f'@@PROG|{done}|{total}|{text}')


def fail(code, kind, text):
    say(f'@@ERROR|{kind}|{text}')
    raise SystemExit(code)


DEFAULTS = {
    'lang': 'pl', 'project': '', 'aoi_gpkg': '', 'aoi_layer': None, 'name': None, 'out_dir': '',
    'years': [2014, 2025],            # zakres lat VIIRS (lata bez miesięcy w kolekcji są pomijane)
    'rings_m': [5000],                # pierścienie wokół obszaru (promienie zewnętrzne, m): otoczenie, z którego dociera rozproszone światło
    'scale_m': 480,                   # siatka VIIRS: wielokrotność 30 m (480 m = 16 pikseli 30 m; natywnie około 460 m)
    'thresholds': [],                 # opcjonalne progi radiancji [nW/cm2/sr] do tabeli udziału powierzchni (umowne)
    'viirs': 'NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG',
    'monthly': True,                  # pobierz wszystkie miesięczne kompozyty (sezonowość, kompletność danych)
    'animations': True, 'anim_monthly': True, 'mp4': True, 'anim_ms': 700,
    'background': True, 'background_year': 2025, 'background_months': [6, 9], 'background_scale_m': 30,
    'background_cs': 0.6, 'background_max_cloud': 60,
    'dpi': 150, 'tile_px': 512, 'threads': 8, 'parallel_images': 4, 'geotiff': True,
}

# ------------------------------------------------------------------------------------------------
# klasyfikacja błędów Google Earth Engine (do czytelnych podpowiedzi we wtyczce)
# ------------------------------------------------------------------------------------------------


def classify_ee_error(e):
    t = str(e).lower()
    if 'has not been used in project' in t or 'service_disabled' in t or 'accessnotconfigured' in t or ('api' in t and 'disabled' in t):
        return 'api_disabled'
    if 'not registered' in t or 'not signed up' in t or 'sign up for earth engine' in t or 'register' in t and 'earth engine' in t:
        return 'not_registered'
    if 'please authorize' in t or 'authenticate' in t or 'invalid_grant' in t or 'reauth' in t or 'default credentials' in t or 'not initialized' in t \
            or 'credentials' in t and 'permission' not in t:
        return 'auth'
    if 'permission' in t or '403' in t or 'forbidden' in t:
        return 'permission'
    if 'not found' in t or '404' in t or ('project' in t and ('invalid' in t or 'deleted' in t)):
        return 'project'
    if any(s in t for s in ('connection', 'timed out', 'timeout', 'resolve', 'proxy', 'ssl', 'max retries', 'unreachable')):
        return 'network'
    return 'other'


def init_ee(project):
    """Inicjalizacja Earth Engine z prawdziwym zapytaniem testowym; błąd kończy proces kodem 3 z komunikatem @@GEE_ERROR."""
    import ee
    if not project or 'TWOJ' in project.upper() or 'YOUR' in project.upper():
        say(f'@@GEE_ERROR|project|{T("Nie wpisano identyfikatora projektu Google Earth Engine.", "No Google Earth Engine project ID entered.")}')
        raise SystemExit(3)
    try:
        ee.Initialize(project=project)
        ee.Number(1).add(1).getInfo()
    except Exception as e:
        say(f'@@GEE_ERROR|{classify_ee_error(e)}|{str(e)[:700].replace(chr(10), " ").replace("|", "/")}')
        raise SystemExit(3)
    return ee


def do_auth():
    """Logowanie do Earth Engine: otwiera przeglądarkę i zapisuje poświadczenia w profilu użytkownika (~/.config/earthengine)."""
    import ee
    try:
        try:
            ee.Authenticate(auth_mode='localhost')
        except TypeError:
            ee.Authenticate()
    except Exception as e:
        say(f'@@GEE_ERROR|auth|{str(e)[:700].replace(chr(10), " ").replace("|", "/")}')
        raise SystemExit(3)
    say('@@AUTH_OK')


# ------------------------------------------------------------------------------------------------
# stan analizy (ustawiany w setup)
# ------------------------------------------------------------------------------------------------
C = dict(DEFAULTS)
NOTES, TABLES, FIGURES, FILES, DL_ERRORS, MODULE_ERRORS = [], {}, [], [], {}, []
_BG = None  # wyblakłe tło Sentinel-2 do map


def module_error(name, e):
    """Błąd w module analizy: komunikat i kontynuacja (moduły są niezależne); w teście (ZSN_TEST) błąd leci dalej."""
    if os.environ.get('ZSN_TEST'):
        raise e
    traceback.print_exc()
    MODULE_ERRORS.append({'module': name, 'error': f'{type(e).__name__}: {e}'})
    NOTES.append(T(f'Moduł "{name}" przerwany błędem {type(e).__name__}: {e}; kolejne moduły policzone bez jego wyników.',
                   f'Module "{name}" stopped with {type(e).__name__}: {e}; later modules were computed without its results.'))
    say(T(f'*** Moduł "{name}" przerwany: {type(e).__name__}: {e}. Analiza trwa dalej.', f'*** Module "{name}" stopped: {type(e).__name__}: {e}. Continuing.'))


def setup(cfg):
    """Wczytanie obszaru, układ metryczny, strefy, siatka 30 m, foldery."""
    global C, LANG, np, pd, gpd, rasterio, rasterize, from_origin, plt, matplotlib, Image, imageio, ee
    global gdf, NAME, CRS, aoi, ZONES, ZONES_GDF, S30, X0, Y1, W30, H30, FRAME_KM2, GRID30, EXTENT, ZONE30, FC, GRID_C, EXT_C, ZONES_C, DOMAIN_C
    global DIR_TAB, DIR_FIG, DIR_ANIM, DIR_RAST, DIR_VEC, DIR_REP, DIR_CACHE, OUT, GEOM, _ramka
    C = {**DEFAULTS, **{k: v for k, v in cfg.items() if v is not None or k in ('aoi_layer', 'name')}}
    LANG = 'en' if str(C['lang']).lower().startswith('en') else 'pl'
    os.environ.setdefault('MPLBACKEND', 'Agg')
    warnings.filterwarnings('ignore')
    import numpy as np, pandas as pd, geopandas as gpd, rasterio
    from rasterio.features import rasterize
    from rasterio.transform import from_origin
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    try:
        import imageio.v2 as imageio
    except ImportError:
        imageio = None
    plt.rcParams.update({'font.size': 9, 'figure.dpi': 100})

    path = C['aoi_gpkg']
    if not path or not os.path.isfile(path):
        fail(4, 'input', T(f'Nie znaleziono pliku z obszarem: {path!r}.', f'Area file not found: {path!r}.'))
    if not C['out_dir']:
        fail(4, 'input', T('Nie wskazano folderu wyników.', 'No output folder given.'))
    try:
        layers = gpd.list_layers(path)['name'].tolist()
    except Exception:
        layers = []
    if len(layers) > 1 and not C['aoi_layer']:
        say(T(f'Plik ma {len(layers)} warstw {layers}; użyta zostanie pierwsza ({layers[0]}).', f'The file has {len(layers)} layers {layers}; the first one ({layers[0]}) is used.'))
    try:
        gdf = gpd.read_file(path, layer=C['aoi_layer']) if C['aoi_layer'] else gpd.read_file(path)
    except Exception as e:
        fail(4, 'input', T(f'Nie można odczytać pliku z obszarem ({os.path.basename(path)}): {str(e)[:300]}. Sprawdź, czy to poprawny plik GPKG, SHP lub GeoJSON i czy nazwa warstwy jest właściwa.',
                           f'Cannot read the area file ({os.path.basename(path)}): {str(e)[:300]}. Check that it is a valid GPKG, SHP or GeoJSON file and that the layer name is correct.').replace('\n', ' '))
    if gdf.crs is None:
        fail(4, 'input', T('Warstwa nie ma układu współrzędnych (CRS); nadaj go w QGIS.', 'The layer has no coordinate reference system (CRS); assign one in QGIS.'))
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
    gdf = gdf[gdf.geom_type.isin(['Polygon', 'MultiPolygon'])]
    if not len(gdf):
        fail(4, 'input', T('Warstwa nie zawiera poligonów. Wskaż warstwę powierzchniową (granica obszaru).', 'The layer contains no polygons. Choose a polygon layer (area boundary).'))
    NAME = re.sub(r'[^\w\-. ]+', '_', str(C['name'] or os.path.splitext(os.path.basename(path))[0])).strip(' ._') or 'obszar'

    def union(g):
        return g.union_all() if hasattr(g, 'union_all') else g.unary_union
    c = union(gdf.to_crs(4326)).centroid
    CRS = 'EPSG:2180' if (14.0 <= c.x <= 24.2 and 49.0 <= c.y <= 55.0) else gdf.estimate_utm_crs().to_string()
    aoi = union(gdf.to_crs(CRS)).buffer(0)
    say(T(f'Obszar: {len(gdf)} obiekt(ów), powierzchnia {aoi.area / 1e6:.3f} km²; układ {CRS}.', f'Area: {len(gdf)} feature(s), {aoi.area / 1e6:.3f} km²; CRS {CRS}.'))

    rings = sorted({float(r) for r in C['rings_m'] if float(r) > 0})
    ZONES = [(T('Obszar', 'Area'), 1, aoi)]
    prev, prev_r = aoi, 0.0
    for i, r in enumerate(rings):
        ZONES.append((T(f'Pierścień {prev_r / 1000:g}–{r / 1000:g} km', f'Ring {prev_r / 1000:g}–{r / 1000:g} km'), i + 2, aoi.buffer(r).difference(prev)))
        prev, prev_r = aoi.buffer(r), r
    ZONES_GDF = gpd.GeoDataFrame({'zone': [n for n, _, _ in ZONES], 'code': [k for _, k, _ in ZONES]}, geometry=[g for _, _, g in ZONES], crs=CRS)

    S30 = 30
    minx, miny, maxx, maxy = ZONES_GDF.total_bounds
    m = max(500, (rings[-1] if rings else 0) + 2 * S30)
    X0 = np.floor((minx - m) / S30) * S30
    Y1 = np.ceil((maxy + m) / S30) * S30
    W30 = int(np.ceil((maxx + m - X0) / S30))
    H30 = int(np.ceil((Y1 - (miny - m)) / S30))
    FRAME_KM2 = W30 * H30 * S30 * S30 / 1e6
    GRID30 = {'x0': X0, 'y1': Y1, 's': S30, 'w': W30, 'h': H30}
    EXTENT = (X0, X0 + W30 * S30, Y1 - H30 * S30, Y1)
    tr = from_origin(X0, Y1, S30, S30)
    ZONE30 = rasterize([(g, k) for _, k, g in reversed(ZONES)], out_shape=(H30, W30), transform=tr, fill=0, dtype='uint8')  # obszar na końcu: nadpisuje pierścienie

    FC = max(1, int(C['scale_m']) // S30)
    GRID_C, EXT_C = coarse_grid(FC)
    ZONES_C = []
    for name, k, _ in ZONES:
        frac = block((ZONE30 == k).astype(np.float32), FC, 'mean', 0)
        msk = frac >= 0.5
        if not msk.any() and frac.max() > 0:
            msk = frac >= frac.max() * 0.999   # bardzo mały obszar: piksele o największym udziale
            NOTES.append(T(f'Strefa "{name}" jest mniejsza niż piksel VIIRS ({FC * S30} m): użyto pikseli o największym udziale strefy. Wynik opisuje także światło spoza strefy.',
                           f'Zone "{name}" is smaller than a VIIRS pixel ({FC * S30} m): the pixels with the largest zone share were used. The result also reflects light outside the zone.'))
        ZONES_C.append((name, msk))
    DOMAIN_C = np.any([m_ for _, m_ in ZONES_C], axis=0)

    import ee as _ee
    ee = _ee
    fr = gpd.GeoSeries.from_xy([X0, X0 + W30 * S30], [Y1 - H30 * S30, Y1], crs=CRS).to_crs(4326)
    _ramka = fr
    GEOM = ee.Geometry.Rectangle([float(fr.x.min()), float(fr.y.min()), float(fr.x.max()), float(fr.y.max())], 'EPSG:4326', False)

    OUT = os.path.join(C['out_dir'], NAME)
    DIR_TAB, DIR_FIG, DIR_ANIM, DIR_RAST, DIR_VEC, DIR_REP, DIR_CACHE = [os.path.join(OUT, d) for d in
        ('01_tabele', '02_ryciny', '03_animacje', '04_rastry', '05_wektory', '06_raport', '_cache')]
    for d in (DIR_TAB, DIR_FIG, DIR_ANIM, DIR_RAST, DIR_VEC, DIR_REP, DIR_CACHE):
        os.makedirs(d, exist_ok=True)
    ZONES_GDF.to_file(os.path.join(DIR_VEC, f'{NAME}_strefy.gpkg'), driver='GPKG')
    say(T(f'Ramka {W30} × {H30} px (30 m), {FRAME_KM2:.0f} km²; siatka VIIRS {FC * S30} m ({GRID_C["w"]} × {GRID_C["h"]} px).',
          f'Frame {W30} × {H30} px (30 m), {FRAME_KM2:.0f} km²; VIIRS grid {FC * S30} m ({GRID_C["w"]} × {GRID_C["h"]} px).'))
    if FRAME_KM2 > 10000:
        say(T('UWAGA: bardzo duża ramka; pobieranie potrwa długo. Rozważ mniejszy obszar albo mniejszy pierścień.', 'WARNING: very large frame; downloading will take long. Consider a smaller area or ring.'))
    say(T('Wyniki w:', 'Results in:'), OUT)


# ------------------------------------------------------------------------------------------------
# siatki i strefy
# ------------------------------------------------------------------------------------------------
def block(a, f, fun='mean', fill=None):
    """Agregacja tablicy 30 m do bloków f × f (mean, sum, max) z dopełnieniem krawędzi."""
    fill = np.nan if fill is None else fill
    h, w = int(np.ceil(a.shape[0] / f)) * f, int(np.ceil(a.shape[1] / f)) * f
    b = np.full((h, w), fill, np.float32)
    b[:a.shape[0], :a.shape[1]] = a
    b = b.reshape(h // f, f, w // f, f)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', category=RuntimeWarning)
        return {'mean': np.nanmean, 'sum': np.nansum, 'max': np.nanmax}[fun](b, axis=(1, 3))


def coarse_grid(f):
    """Siatka o kroku f × 30 m wyrównana do lewego górnego rogu ramki 30 m."""
    h, w = int(np.ceil(H30 / f)), int(np.ceil(W30 / f))
    return {'x0': X0, 'y1': Y1, 's': S30 * f, 'w': w, 'h': h}, (X0, X0 + w * S30 * f, Y1 - h * S30 * f, Y1)


def month_bounds(year, m1, m2):
    return f'{year}-{m1:02d}-01', (f'{year}-{m2 + 1:02d}-01' if m2 < 12 else f'{year + 1}-01-01')


# ------------------------------------------------------------------------------------------------
# pobieranie z GEE kaflami (ponawianie błędów przejściowych, atomowa pamięć podręczna .npz)
# ------------------------------------------------------------------------------------------------
def _tiles(grid, size):
    for ty in range(0, grid['h'], size):
        for tx in range(0, grid['w'], size):
            yield ty, tx, min(size, grid['h'] - ty), min(size, grid['w'] - tx)


def _permanent(e):
    t = str(e).lower()
    return any(s in t for s in ('not found', 'does not exist', 'permission', 'not been used', 'has no bands', 'band pattern', 'invalid', 'must be', 'no such', 'not registered'))


def _get_tile(img, bands, grid, ty, tx, h, w, tries=5):
    s = grid['s']
    req = {'expression': img, 'fileFormat': 'NUMPY_NDARRAY', 'bandIds': bands,
           'grid': {'dimensions': {'width': w, 'height': h}, 'crsCode': CRS,
                    'affineTransform': {'scaleX': s, 'shearX': 0, 'translateX': grid['x0'] + tx * s, 'shearY': 0, 'scaleY': -s, 'translateY': grid['y1'] - ty * s}}}
    for p in range(tries):
        try:
            return ee.data.computePixels(req)
        except Exception as e:
            if p == tries - 1 or _permanent(e):
                raise RuntimeError(T(f'kafel ({ty}, {tx}): {e}. Przy przekroczeniu czasu lub pamięci zmniejsz rozmiar kafla w ustawieniach zaawansowanych (np. 256).',
                                     f'tile ({ty}, {tx}): {e}. On a timeout or memory error reduce the tile size in the advanced settings (e.g. 256).')) from e
            time.sleep(2 ** p + float(np.random.rand()))


def _cache_key(img, bands, grid, name):
    try:
        desc = img.serialize()          # cały graf obliczeń GEE: zmiana kolekcji lub parametru unieważnia pamięć podręczną
    except Exception:
        desc = repr(img)
    return hashlib.md5(json.dumps([name, bands, grid, CRS, desc], sort_keys=True, default=str).encode()).hexdigest()[:10]


def download(img, bands, grid, name, dtype=None, tile=None, threads=None, show=False):
    """Obraz GEE -> {pasmo: tablica 2D} na siatce; wynik w pamięci podręcznej .npz (przerwane pobieranie wznawia się)."""
    dtype = dtype or np.uint8
    tile = int(tile or C['tile_px'])
    path = os.path.join(DIR_CACHE, f'{name}_{_cache_key(img, bands, grid, name)}.npz')
    if os.path.exists(path):
        try:
            with np.load(path) as z:
                return {b: z[b] for b in bands}
        except Exception:
            os.remove(path)             # uszkodzony plik (przerwany zapis)
    out = {b: np.zeros((grid['h'], grid['w']), dtype=dtype) for b in bands}
    tiles = list(_tiles(grid, tile))
    done = 0
    with ThreadPoolExecutor(max_workers=max(1, min(int(threads or C['threads']), len(tiles)))) as ex:
        fut = {ex.submit(_get_tile, img, bands, grid, *t): t for t in tiles}
        for f in as_completed(fut):
            ty, tx, h, w = fut[f]
            a = f.result()
            for b in bands:
                out[b][ty:ty + h, tx:tx + w] = a[b].astype(dtype)
            done += 1
            if show and len(tiles) > 1:
                prog(done, len(tiles), name)
    tmp = path + '.tmp.npz'
    np.savez_compressed(tmp, **out)
    os.replace(tmp, path)               # zapis atomowy
    return out


def download_many(jobs, label):
    """Równoległe pobieranie wielu obrazów; błąd jednego nie przerywa reszty. Zwraca ({nazwa: wynik|None}, {nazwa: błąd})."""
    res, errs = {}, {}
    if not jobs:
        return res, errs

    def one(j):
        return download(j['img'], j['bands'], j['grid'], j['name'], j.get('dtype', np.uint8), threads=2)
    done = 0
    with ThreadPoolExecutor(max_workers=max(1, int(C['parallel_images']))) as ex:
        fut = {ex.submit(one, j): j['name'] for j in jobs}
        for f in as_completed(fut):
            n = fut[f]
            try:
                res[n] = f.result()
            except Exception as e:
                res[n] = None
                errs[n] = f'{type(e).__name__}: {e}'
            done += 1
            prog(done, len(jobs), label)
    return res, errs


def save_geotiff(name, layers, grid, dtype='float32', nodata=None, desc=''):
    """GeoTIFF (LZW, kafelkowany) w 04_rastry; layers = lista (opis pasma, tablica 2D)."""
    if not C['geotiff']:
        return None
    nodata = np.nan if nodata is None else nodata
    p = os.path.join(DIR_RAST, f'{NAME}_{name}.tif')
    with rasterio.open(p, 'w', driver='GTiff', height=grid['h'], width=grid['w'], count=len(layers), dtype=dtype, crs=CRS,
                       transform=from_origin(grid['x0'], grid['y1'], grid['s'], grid['s']), nodata=nodata, compress='lzw', tiled=True, blockxsize=256, blockysize=256) as d:
        for i, (label, a) in enumerate(layers, 1):
            d.write(a.astype(dtype), i)
            d.set_band_description(i, str(label))
    FILES.append({'file': os.path.basename(p), 'description': desc, 'bands': len(layers), 'cell_m': grid['s'], 'size_px': f"{grid['w']} x {grid['h']}", 'size_mb': round(os.path.getsize(p) / 1e6, 2)})
    return p


# ------------------------------------------------------------------------------------------------
# statystyka: trend Theila-Sena i test Manna-Kendalla
# ------------------------------------------------------------------------------------------------
def _two_sided_p(z):
    erfc = np.vectorize(math.erfc, otypes=[np.float64])
    return erfc(np.abs(z) / math.sqrt(2.0))


def trend_sen_mk(stack, years, chunk=40000, min_years=8, mask=None):
    """Nachylenie Theila-Sena [jednostki/rok] i test Manna-Kendalla (z, p dwustronne) dla każdego piksela stosu (t, h, w); NaN = brak obserwacji.
    Bez poprawki na wiązania, na autokorelację czasową i przestrzenną ani na wielokrotne testowanie: wynik opisowy."""
    t, h, w = stack.shape
    years = np.asarray(years, np.float32)
    X = stack.reshape(t, -1)
    i, j = np.triu_indices(t, 1)
    dt = (years[j] - years[i])[:, None]
    n_obs = np.isfinite(X).sum(axis=0)
    ok = n_obs >= min_years
    if mask is not None:
        ok &= mask.ravel()
    idx = np.flatnonzero(ok)
    slope = np.full(h * w, np.nan, np.float32)
    z = np.full(h * w, np.nan, np.float32)
    for a in range(0, idx.size, chunk):
        k = idx[a:a + chunk]
        Y = X[:, k].astype(np.float32)
        d = Y[j] - Y[i]
        with np.errstate(all='ignore'):
            slope[k] = np.nanmedian(d / dt, axis=0)
        S = np.nansum(np.sign(d), axis=0)
        n = n_obs[k].astype(np.float64)
        sd = np.sqrt(n * (n - 1) * (2 * n + 5) / 18.0)
        z[k] = np.where(S > 0, (S - 1) / sd, np.where(S < 0, (S + 1) / sd, 0.0))
    p = _two_sided_p(z).astype(np.float32)
    p[~np.isfinite(z)] = np.nan
    return slope.reshape(h, w), z.reshape(h, w), p.reshape(h, w)


# ------------------------------------------------------------------------------------------------
# tabele, mapy, ryciny, animacje
# ------------------------------------------------------------------------------------------------
def table(name, df):
    """Zapis tabeli (CSV, UTF-8 z BOM: poprawnie otwiera się w Excelu); pusta tabela dostaje wiersz z wyjaśnieniem."""
    df = pd.DataFrame() if df is None else df
    TABLES[name] = df
    out = df
    if not len(df):
        out = pd.DataFrame([{T('Uwaga', 'Note'): T('brak wyników: za mało danych spełniających kryteria', 'no results: not enough data meeting the criteria')}])
        NOTES.append(T(f'Tabela {name}: brak wyników.', f'Table {name}: no results.'))
    out.to_csv(os.path.join(DIR_TAB, f'{NAME}_{name}.csv'), index=False, encoding='utf-8-sig')
    return df


def outlines(ax):
    """Granice na mapie: obszar linią ciągłą, pierścienie cienką szarą linią; zakres ramki, bez osi."""
    if len(ZONES_GDF) > 1:
        ZONES_GDF[ZONES_GDF.code > 1].boundary.plot(ax=ax, color='#7f7f7f', linewidth=0.5)
    gpd.GeoSeries([aoi.boundary], crs=CRS).plot(ax=ax, color='black', linewidth=0.9)
    ax.set_xlim(EXTENT[0], EXTENT[1])
    ax.set_ylim(EXTENT[2], EXTENT[3])
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel('')
    ax.set_ylabel('')


def scalebar(ax):
    import matplotlib.patheffects as pe
    width, height = EXTENT[1] - EXTENT[0], EXTENT[3] - EXTENT[2]
    ln = 10 ** np.floor(np.log10(width / 4))
    ln = 5 * ln if width / ln > 25 else (2 * ln if width / ln > 12 else ln)
    x, y, k = EXTENT[0] + width * 0.05, EXTENT[2] + height * 0.05, height * 0.012
    halo = [pe.withStroke(linewidth=3.5, foreground='white')]
    ax.plot([x, x + ln], [y, y], color='black', lw=2, solid_capstyle='butt', path_effects=halo, zorder=20)
    for xx in (x, x + ln):
        ax.plot([xx, xx], [y - k, y + k], color='black', lw=1.2, path_effects=halo, zorder=20)
    label = f'{ln / 1000:g} km'
    ax.annotate(label.replace('.', ',') if LANG == 'pl' else label, (x + ln / 2, y + k), xytext=(0, 4), textcoords='offset points', ha='center', va='bottom', fontsize=7.5,
                path_effects=[pe.withStroke(linewidth=2.5, foreground='white')], zorder=21)


def draw_map(ax, a, cmap, vmin=None, vmax=None, title='', ext=None, label=None, norm=None, background=True):
    if background and _BG is not None:
        ax.imshow(_BG, extent=EXTENT, interpolation='nearest')
    im = ax.imshow(a, cmap=cmap, vmin=None if norm else vmin, vmax=None if norm else vmax, norm=norm, extent=ext or EXTENT, interpolation='nearest')
    outlines(ax)
    scalebar(ax)
    ax.set_title(title, fontsize=9)
    if label:
        plt.colorbar(im, ax=ax, fraction=0.035, pad=0.02, shrink=0.85).set_label(label, fontsize=8)
    return im


def save_fig(fig, name):
    if fig._suptitle is not None:
        try:
            fig.tight_layout(rect=(0, 0, 1, 0.95))
            fig._suptitle.set_y(0.995)
        except Exception:
            pass
    p = os.path.join(DIR_FIG, f'{NAME}_{name}.png')
    fig.savefig(p, dpi=int(C['dpi']), bbox_inches='tight', facecolor='white')
    plt.close(fig)
    FIGURES.append(p)
    return p


def animate(frames, name, draw, ms=None):
    """Animacja GIF (i MP4, gdy dostępny ffmpeg); draw(fig, ax, element) rysuje jedną klatkę."""
    if not C['animations']:
        return None
    ms = ms or int(C['anim_ms'])
    imgs = []
    for el in frames:
        fig, ax = plt.subplots(figsize=(6.4, 6.4 * H30 / W30 + 1.3))
        draw(fig, ax, el)
        fig.subplots_adjust(bottom=0.08, top=0.93)
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=105, facecolor='white')
        plt.close(fig)
        buf.seek(0)
        imgs.append(Image.open(buf).convert('RGB'))
    if not imgs:
        return None
    w_, h_ = min(k.size[0] for k in imgs) // 2 * 2, min(k.size[1] for k in imgs) // 2 * 2
    imgs = [k.crop((0, 0, w_, h_)) for k in imgs]
    p = os.path.join(DIR_ANIM, f'{NAME}_{name}.gif')
    imgs[0].save(p, save_all=True, append_images=imgs[1:], duration=[ms] * (len(imgs) - 1) + [ms * 3], loop=0)
    if C['mp4'] and imageio is not None:
        try:
            imageio.mimsave(p.replace('.gif', '.mp4'), [np.asarray(k) for k in imgs] + [np.asarray(imgs[-1])] * 2, fps=max(1000 / ms, 1), macro_block_size=1)
        except Exception as e:
            NOTES.append(T(f'MP4 nie powstał ({type(e).__name__}); jest GIF.', f'MP4 was not created ({type(e).__name__}); the GIF exists.'))
    say(T('animacja:', 'animation:'), os.path.basename(p))
    return p


# ------------------------------------------------------------------------------------------------
# dane: tło Sentinel-2 i VIIRS
# ------------------------------------------------------------------------------------------------
def fetch_background():
    global _BG
    if not C['background']:
        return None
    if S30 % int(C['background_scale_m']):
        raise ValueError('background_scale_m must divide 30 (10, 15 or 30)')
    y = int(C['background_year'])
    d1, d2 = month_bounds(y, *C['background_months'])
    cs = ee.ImageCollection('GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED')
    col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(GEOM).filterDate(d1, d2)
           .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', C['background_max_cloud'])).linkCollection(cs, ['cs_cdf'])
           .map(lambda im: im.updateMask(im.select('cs_cdf').gte(C['background_cs'])).divide(10000)))
    vis = col.select(['B4', 'B3', 'B2']).median().visualize(min=0, max=0.25).rename(['r', 'g', 'b'])
    sc = int(C['background_scale_m'])
    grid = {'x0': X0, 'y1': Y1, 's': sc, 'w': W30 * S30 // sc, 'h': H30 * S30 // sc}
    a = download(vis, ['r', 'g', 'b'], grid, f's2_rgb_{y}_{sc}m', show=True)
    rgb = np.dstack([a['r'], a['g'], a['b']])
    _BG = (rgb.astype(np.float32).mean(axis=2, keepdims=True) * 0.45 + 255 * 0.55).repeat(3, axis=2).astype(np.uint8)   # wyblakłe tło (skala szarości)
    save_geotiff(f'tlo_sentinel2_{y}_rgb', [('R', rgb[:, :, 0]), ('G', rgb[:, :, 1]), ('B', rgb[:, :, 2])], grid, 'uint8', 0,
                 desc=T(f'Sentinel-2 {y}, mediana z maską Cloud Score+, RGB 8-bit', f'Sentinel-2 {y}, median with Cloud Score+ mask, 8-bit RGB'))
    say(T(f'Tło Sentinel-2 {y}: {rgb.shape[1]} × {rgb.shape[0]} px ({sc} m)', f'Sentinel-2 {y} background: {rgb.shape[1]} × {rgb.shape[0]} px ({sc} m)'))


def available_months():
    y0, y1 = int(C['years'][0]), int(C['years'][1])
    t = ee.ImageCollection(C['viirs']).filterDate(f'{y0}-01-01', f'{y1 + 1}-01-01').aggregate_array('system:time_start').getInfo()
    return sorted({(d.year, d.month) for d in pd.to_datetime(list(t), unit='ms')})


def viirs_year(r):
    """Mediana roczna miesięcznych radiancji (avg_rad), piksele z obserwacjami (cf_cvg > 0); wartość x 100, brak danych = -999999."""
    col = ee.ImageCollection(C['viirs']).filterDate(f'{r}-01-01', f'{r + 1}-01-01')
    im = col.map(lambda m: m.select('avg_rad').updateMask(m.select('cf_cvg').gt(0))).median()
    return im.multiply(100).round().unmask(-999999).toInt32().rename('rad')


def viirs_months(r, months):
    """Obraz z pasmami r01…r12 (radiancja x 100, brak = -999999) i c01…c12 (liczba obserwacji) dla miesięcy roku."""
    parts = []
    for m_ in months:
        d1, d2 = month_bounds(r, m_, m_)
        im = ee.ImageCollection(C['viirs']).filterDate(d1, d2).select(['avg_rad', 'cf_cvg']).mosaic()
        parts.append(im.select('avg_rad').updateMask(im.select('cf_cvg').gt(0)).multiply(100).round().unmask(-999999).toInt32().rename(f'r{m_:02d}'))
        parts.append(im.select('cf_cvg').unmask(0).toInt32().rename(f'c{m_:02d}'))
    return ee.Image.cat(parts)


ANNUAL, MONTHLY, MONTHLY_CF = {}, {}, {}


def fetch_viirs():
    months = available_months()
    if not months:
        raise RuntimeError(T(f"kolekcja {C['viirs']} nie ma obrazów w latach {C['years']}", f"collection {C['viirs']} has no images in {C['years']}"))
    years = sorted({r for r, _ in months})
    say(T(f'VIIRS: {len(months)} miesięcy w {len(years)} latach ({months[0][0]}-{months[0][1]:02d} … {months[-1][0]}-{months[-1][1]:02d})',
          f'VIIRS: {len(months)} months in {len(years)} years ({months[0][0]}-{months[0][1]:02d} … {months[-1][0]}-{months[-1][1]:02d})'))
    stage(4, 8, T('Pobieranie VIIRS: mediany roczne', 'Downloading VIIRS: annual medians'))
    jobs = [{'img': viirs_year(r), 'bands': ['rad'], 'grid': GRID_C, 'name': f'viirs_{r}', 'dtype': np.int32} for r in years]
    res, errs = download_many(jobs, T('VIIRS roczne', 'VIIRS annual'))
    DL_ERRORS.update(errs)
    for r in years:
        if res.get(f'viirs_{r}') is None:
            continue
        a = res[f'viirs_{r}']['rad'].astype(np.float32)
        a[a == -999999] = np.nan
        a /= 100                                  # ujemne radiancje (szum w ciemnych miejscach) zachowane
        if np.isfinite(a).any():
            ANNUAL[r] = a
    if errs and not ANNUAL:
        raise RuntimeError(T('nie pobrano żadnego roku VIIRS: ', 'no VIIRS year could be downloaded: ') + next(iter(errs.values())))
    if ANNUAL:
        save_geotiff(f'viirs_roczne_{min(ANNUAL)}_{max(ANNUAL)}', [(f'{r}: ' + T('mediana miesięcznych radiancji [nW/cm2/sr]', 'median of monthly radiance [nW/cm2/sr]'), ANNUAL[r]) for r in sorted(ANNUAL)], GRID_C,
                     desc=T('VIIRS DNB: mediana roczna miesięcznych radiancji (avg_rad), nW/cm2/sr', 'VIIRS DNB: annual median of monthly radiance (avg_rad), nW/cm2/sr'))
    if C['monthly']:
        stage(5, 8, T('Pobieranie VIIRS: kompozyty miesięczne', 'Downloading VIIRS: monthly composites'))
        by_year = {r: [m_ for rr, m_ in months if rr == r] for r in years}
        jobs = [{'img': viirs_months(r, mm), 'bands': [f'r{m_:02d}' for m_ in mm] + [f'c{m_:02d}' for m_ in mm], 'grid': GRID_C, 'name': f'viirs_mies_{r}', 'dtype': np.int32}
                for r, mm in by_year.items()]
        res, errs = download_many(jobs, T('VIIRS miesięczne', 'VIIRS monthly'))
        DL_ERRORS.update(errs)
        for r, mm in by_year.items():
            a = res.get(f'viirs_mies_{r}')
            if a is None:
                continue
            for m_ in mm:
                rad = a[f'r{m_:02d}'].astype(np.float32)
                rad[rad == -999999] = np.nan
                rad /= 100
                MONTHLY[(r, m_)] = rad
                MONTHLY_CF[(r, m_)] = a[f'c{m_:02d}'].astype(np.float32)
        if MONTHLY:
            keys = sorted(MONTHLY)
            save_geotiff('viirs_miesieczne_radiancja', [(f'{r}-{m_:02d} ' + T('radiancja [nW/cm2/sr]', 'radiance [nW/cm2/sr]'), MONTHLY[(r, m_)]) for r, m_ in keys], GRID_C,
                         desc=T(f'VIIRS DNB: {len(keys)} miesięcznych kompozytów avg_rad [nW/cm2/sr] (brak danych = NaN)', f'VIIRS DNB: {len(keys)} monthly composites of avg_rad [nW/cm2/sr] (no data = NaN)'))
            save_geotiff('viirs_miesieczne_liczba_obserwacji', [(f'{r}-{m_:02d} cf_cvg ' + T('(liczba obserwacji bez chmur)', '(number of cloud-free observations)'), MONTHLY_CF[(r, m_)]) for r, m_ in keys], GRID_C,
                         desc=T('VIIRS DNB: liczba obserwacji (cf_cvg) w miesięcznych kompozytach', 'VIIRS DNB: number of observations (cf_cvg) in monthly composites'))
    say(T(f'VIIRS: roczne {len(ANNUAL)} z {len(years)}, miesięczne {len(MONTHLY)}', f'VIIRS: annual {len(ANNUAL)} of {len(years)}, monthly {len(MONTHLY)}'))


# ------------------------------------------------------------------------------------------------
# analiza i wyniki
# ------------------------------------------------------------------------------------------------
ZONE_COLORS = ['#7a0177', '#1b7837', '#bf812d', '#252525', '#2c7bb6']
UNIT = 'nW/cm²/sr'


def analyse_annual():
    if not ANNUAL:
        NOTES.append(T('Brak pobranych danych VIIRS.', 'No VIIRS data downloaded.'))
        return
    col_mean = T(f'Średnia radiancja [{UNIT}]', f'Mean radiance [{UNIT}]')
    col_med = T(f'Mediana [{UNIT}]', f'Median [{UNIT}]')
    col_p90 = T(f'Percentyl 90 [{UNIT}]', f'90th percentile [{UNIT}]')
    col_sum = T(f'Suma radiancji pikseli {FC * S30} m w strefie [{UNIT}]', f'Sum of {FC * S30} m pixel radiance in zone [{UNIT}]')
    col_year, col_zone, col_n = T('Rok', 'Year'), T('Strefa', 'Zone'), T('Liczba pikseli', 'Pixels')
    rows = []
    for r in sorted(ANNUAL):
        a = ANNUAL[r]
        for zn, zm in ZONES_C:
            v = a[zm & np.isfinite(a)]
            if v.size:
                row = {col_year: r, col_zone: zn, col_mean: round(float(v.mean()), 3), col_med: round(float(np.median(v)), 3), col_p90: round(float(np.percentile(v, 90)), 3),
                       col_sum: round(float(v.sum()), 1), col_n: int(v.size)}
                for p in C['thresholds']:
                    row[T(f'Powierzchnia > {p:g} {UNIT} (próg umowny) [%]', f'Area > {p:g} {UNIT} (conventional threshold) [%]')] = round(float((v > p).mean() * 100), 1)
                rows.append(row)
    if not rows:
        NOTES.append(T('Żaden piksel VIIRS nie leży w strefach.', 'No VIIRS pixel lies in the zones.'))
        return
    t = table('alan_viirs', pd.DataFrame(rows))
    years = sorted(ANNUAL)

    # trend po strefach: nachylenie Theila-Sena i test Manna-Kendalla na rocznych średnich
    trend_rows = []
    for zn, _ in ZONES_C:
        d = t[t[col_zone] == zn]
        if len(d) >= 5:
            sl, z_, p_ = trend_sen_mk(d[col_mean].to_numpy(np.float32)[:, None, None], d[col_year].tolist(), min_years=5)
            trend_rows.append({col_zone: zn, T('Okres', 'Period'): f'{d[col_year].min()}–{d[col_year].max()}', T('Liczba lat', 'Years'): len(d),
                               T(f'Średnia w pierwszym roku [{UNIT}]', f'Mean in first year [{UNIT}]'): float(d[col_mean].iloc[0]),
                               T(f'Średnia w ostatnim roku [{UNIT}]', f'Mean in last year [{UNIT}]'): float(d[col_mean].iloc[-1]),
                               T(f'Trend średniej radiancji [{UNIT} na rok]', f'Trend of mean radiance [{UNIT} per year]'): round(float(sl[0, 0]), 4),
                               T('Zmiana względna [% na rok]', 'Relative change [% per year]'): round(float(sl[0, 0] / d[col_mean].mean() * 100), 2) if d[col_mean].mean() else np.nan,
                               T('p (Mann–Kendall)', 'p (Mann–Kendall)'): round(float(p_[0, 0]), 4)})
    if trend_rows:
        table('alan_viirs_trend', pd.DataFrame(trend_rows))
    else:
        NOTES.append(T('Trend: mniej niż 5 lat danych w strefie; tabela trendów pominięta.', 'Trend: fewer than 5 years of data in the zone; trend table skipped.'))

    # rycina 1: mapa pierwszego i ostatniego roku, zmiana, szereg czasowy
    vmax = max(float(np.nanpercentile(ANNUAL[years[-1]], 99)), 1.0)
    lg = matplotlib.colors.LogNorm(0.1, vmax)
    fig, axs = plt.subplots(1, 4, figsize=(22, 5.6))
    draw_map(axs[0], np.clip(ANNUAL[years[0]], 0.1, None), 'magma', title=T(f'Światło nocą {years[0]} (VIIRS)', f'Night-time light {years[0]} (VIIRS)'), ext=EXT_C,
             label=T(f'radiancja [{UNIT}]', f'radiance [{UNIT}]'), norm=lg)
    draw_map(axs[1], np.clip(ANNUAL[years[-1]], 0.1, None), 'magma', title=T(f'Światło nocą {years[-1]} (VIIRS)', f'Night-time light {years[-1]} (VIIRS)'), ext=EXT_C,
             label=T(f'radiancja [{UNIT}]', f'radiance [{UNIT}]'), norm=lg)
    diff = ANNUAL[years[-1]] - ANNUAL[years[0]]
    lim = max(0.5, float(np.nanpercentile(np.abs(diff[DOMAIN_C]), 98))) if np.isfinite(diff[DOMAIN_C]).any() else 1.0
    draw_map(axs[2], diff, 'RdBu_r', -lim, lim, T(f'Zmiana {years[0]}–{years[-1]}', f'Change {years[0]}–{years[-1]}'), EXT_C, T(f'Δ radiancji [{UNIT}]', f'Δ radiance [{UNIT}]'))
    for k, (zn, _) in enumerate(ZONES_C):
        d = t[t[col_zone] == zn]
        axs[3].plot(d[col_year], d[col_mean], ('-', '--', ':', '-.', '-')[k % 5], marker='o', ms=3, color=ZONE_COLORS[k % len(ZONE_COLORS)], label=zn)
    axs[3].set_ylabel(col_mean)
    axs[3].set_xlabel(col_year)
    axs[3].grid(alpha=0.3)
    axs[3].legend(frameon=False, fontsize=8)
    axs[3].set_title(T('Światło nocą w strefach analizy', 'Night-time light by analysis zone'), fontsize=10)
    fig.suptitle(T(f'{NAME}: sztuczne światło nocą (VIIRS DNB, mediana roczna miesięcznych kompozytów, siatka {FC * S30} m)',
                   f'{NAME}: artificial night-time light (VIIRS DNB, annual median of monthly composites, {FC * S30} m grid)'), fontsize=11)
    fig.tight_layout()
    save_fig(fig, 'alan_viirs')

    # rycina 2 i raster: trend w każdym pikselu (opisowy, bez poprawek)
    if len(years) >= 5:
        stack = np.stack([ANNUAL[r] for r in years])
        sl, z_, p_ = trend_sen_mk(stack, years, min_years=max(5, min(8, len(years))), mask=DOMAIN_C)
        if np.isfinite(sl).any():
            save_geotiff('viirs_trend_theil_sen', [(T(f'nachylenie Theila-Sena [{UNIT} na rok]', f'Theil–Sen slope [{UNIT} per year]'), sl), ('p (Mann–Kendall)', p_)], GRID_C,
                         desc=T('Trend radiancji w każdym pikselu: nachylenie Theila-Sena i p testu Manna-Kendalla (opisowo, bez poprawek na wielokrotne testowanie i autokorelację)',
                                'Per-pixel radiance trend: Theil–Sen slope and Mann–Kendall p (descriptive, no correction for multiple testing or autocorrelation)'))
            lim2 = max(0.05, float(np.nanpercentile(np.abs(sl[DOMAIN_C]), 98)))
            sig = np.where(p_ < 0.05, sl, np.nan)
            fig, axs = plt.subplots(1, 2, figsize=(12, 5.6))
            draw_map(axs[0], sl, 'RdBu_r', -lim2, lim2, T('Trend w pikselu (nachylenie Theila-Sena)', 'Per-pixel trend (Theil–Sen slope)'), EXT_C, T(f'{UNIT} na rok', f'{UNIT} per year'))
            draw_map(axs[1], sig, 'RdBu_r', -lim2, lim2, T('Tylko piksele z p < 0,05 (Mann–Kendall)', 'Only pixels with p < 0.05 (Mann–Kendall)'), EXT_C, T(f'{UNIT} na rok', f'{UNIT} per year'))
            fig.suptitle(T(f'{NAME}: trend światła nocą {years[0]}–{years[-1]} (opisowo: bez poprawki na wielokrotne testowanie i autokorelację)',
                           f'{NAME}: night-time light trend {years[0]}–{years[-1]} (descriptive: no correction for multiple testing or autocorrelation)'), fontsize=10)
            save_fig(fig, 'alan_viirs_trend_mapa')
    animate(years, 'animacja_alan_viirs', lambda fig, ax, r: draw_map(ax, np.clip(ANNUAL[r], 0.1, None), 'magma', title=T(f'{NAME}: sztuczne światło nocą {r}', f'{NAME}: artificial night-time light {r}'),
                                                                 ext=EXT_C, label=T(f'radiancja [{UNIT}]', f'radiance [{UNIT}]'), norm=matplotlib.colors.LogNorm(0.1, vmax)))


def analyse_monthly():
    if not MONTHLY:
        return
    keys = sorted(MONTHLY)
    col_year, col_month, col_zone = T('Rok', 'Year'), T('Miesiąc', 'Month'), T('Strefa', 'Zone')
    col_mean = T(f'Średnia radiancja [{UNIT}]', f'Mean radiance [{UNIT}]')
    col_cov = T('Udział pikseli z obserwacją [%]', 'Share of pixels with observation [%]')
    col_obs = T('Średnia liczba obserwacji', 'Mean number of observations')
    rows = []
    for (r, m_) in keys:
        a, cf = MONTHLY[(r, m_)], MONTHLY_CF[(r, m_)]
        for zn, zm in ZONES_C:
            v = a[zm & np.isfinite(a)]
            rows.append({col_year: r, col_month: m_, col_zone: zn, col_mean: round(float(v.mean()), 3) if v.size else np.nan,
                         col_cov: round(float((cf[zm] > 0).mean() * 100), 1), col_obs: round(float(cf[zm].mean()), 1)})
    tm = table('alan_viirs_miesieczne', pd.DataFrame(rows))
    years = sorted({r for r, _ in keys})
    zn0 = ZONES_C[0][0]
    d0 = tm[tm[col_zone] == zn0]
    H_rad = d0.pivot(index=col_year, columns=col_month, values=col_mean).reindex(index=years, columns=range(1, 13))
    H_cov = d0.pivot(index=col_year, columns=col_month, values=col_cov).reindex(index=years, columns=range(1, 13))
    fig, axs = plt.subplots(1, 2, figsize=(14, 0.45 * len(years) + 2.2))
    for ax, H, title, lab, cm in ((axs[0], H_rad, T(f'Średnia radiancja, strefa {zn0}', f'Mean radiance, zone {zn0}'), UNIT, 'magma'),
                                  (axs[1], H_cov, T(f'Udział pikseli z obserwacją, strefa {zn0}', f'Share of pixels with observation, zone {zn0}'), '%', 'Blues')):
        im = ax.imshow(H.to_numpy(float), aspect='auto', cmap=cm, vmin=0, vmax=100 if cm == 'Blues' else None)
        ax.set_xticks(range(12))
        ax.set_xticklabels(range(1, 13))
        ax.set_yticks(range(len(years)))
        ax.set_yticklabels(years)
        ax.set_xlabel(col_month)
        ax.set_title(title, fontsize=10)
        plt.colorbar(im, ax=ax, fraction=0.04, pad=0.02).set_label(lab, fontsize=8)
    fig.suptitle(T(f'{NAME}: miesięczne kompozyty VIIRS: sezonowość i kompletność danych (białe pola: brak kompozytu lub obserwacji)',
                   f'{NAME}: monthly VIIRS composites: seasonality and data completeness (white cells: no composite or observations)'), fontsize=11)
    save_fig(fig, 'alan_viirs_miesieczne')
    if C['anim_monthly'] and C['animations']:
        last = keys[-12:]
        vals = np.concatenate([MONTHLY[k][np.isfinite(MONTHLY[k])] for k in last])
        vmax = max(float(np.nanpercentile(vals, 99)), 1.0) if vals.size else 1.0
        animate(keys, 'animacja_alan_viirs_miesieczna', lambda fig, ax, k: draw_map(ax, np.clip(MONTHLY[k], 0.1, None), 'magma', title=T(f'{NAME}: światło nocą {k[0]}-{k[1]:02d}', f'{NAME}: night-time light {k[0]}-{k[1]:02d}'),
                                                                                     ext=EXT_C, label=T(f'radiancja [{UNIT}]', f'radiance [{UNIT}]'), norm=matplotlib.colors.LogNorm(0.1, vmax)), ms=250)


def write_report():
    notes = list(dict.fromkeys(NOTES))
    params = {'name': NAME, 'run': datetime.datetime.now().isoformat(timespec='seconds'), 'area_file': C['aoi_gpkg'], 'crs': CRS, 'area_km2': round(aoi.area / 1e6, 4),
              'zones': [n for n, _ in ZONES_C], 'grid_30m': GRID30, 'grid_viirs': GRID_C, 'years_with_data': sorted(ANNUAL), 'months_with_data': len(MONTHLY),
              'settings': {k: v for k, v in C.items() if k not in ('aoi_gpkg',)}, 'notes': notes, 'module_errors': MODULE_ERRORS, 'download_errors': DL_ERRORS,
              'files': {os.path.basename(d): sorted(os.listdir(d)) for d in (DIR_TAB, DIR_FIG, DIR_ANIM, DIR_RAST, DIR_VEC)},
              'versions': {'earthengine-api': ee.__version__, 'numpy': np.__version__, 'pandas': pd.__version__, 'geopandas': gpd.__version__, 'rasterio': rasterio.__version__}}
    with open(os.path.join(DIR_REP, f'{NAME}_parametry_biegu.json'), 'w', encoding='utf-8') as f:
        json.dump(params, f, ensure_ascii=False, indent=1, default=str)
    pl = [f'# {NAME}: sztuczne światło nocą (VIIRS DNB)', '', f'Data biegu: {params["run"]}. Plik obszaru: {C["aoi_gpkg"]}. Układ: {CRS}.', '',
          '## Dane', '',
          f'- VIIRS DNB, miesięczne kompozyty z korektą światła rozproszonego: `{C["viirs"]}` (pasma avg_rad i cf_cvg). Radiancja w nW/cm²/sr.',
          f'- Wartość roczna: mediana miesięcznych radiancji z miesięcy, w których piksel ma obserwacje (cf_cvg > 0). Siatka {FC * S30} m.',
          f'- Strefy: obszar z pliku GPKG i pierścienie wokół niego (promienie zewnętrzne: {", ".join(f"{r:g} m" for r in sorted(C["rings_m"]))}). Piksel VIIRS należy do strefy, gdy ≥ 50% jego powierzchni leży w strefie.',
          *([f'- Tło map: Sentinel-2 {C["background_year"]} (`COPERNICUS/S2_SR_HARMONIZED` z maską Cloud Score+).'] if _BG is not None else []), '',
          '## Metody', '',
          '- Tabele: średnia, mediana, percentyl 90 i suma radiancji pikseli w strefie dla każdego roku.',
          '- Trend w strefie: nachylenie Theila-Sena i test Manna-Kendalla na rocznych średnich (co najmniej 5 lat). Trend w pikselu: ta sama metoda w każdym pikselu (co najmniej 8 lat albo wszystkie dostępne, gdy lat jest mniej).',
          '- Testy bez poprawki na wiązania, autokorelację czasową i przestrzenną ani na wielokrotne testowanie: wyniki mają charakter opisowy.', '',
          '## Ograniczenia', '',
          '- VIIRS (około 500 m) nie rozróżnia pojedynczych źródeł światła, a jego pasmo (ok. 500–900 nm) słabo rejestruje światło niebieskie, np. z diod LED o zimnej barwie: wzrost udziału LED może być niedoszacowany.',
          '- Radiancja z satelity nie jest jasnością nieba mierzoną z ziemi (np. SQM) ani natężeniem światła na gruncie.',
          '- Latem na wysokich szerokościach część miesięcy może nie mieć danych; kompletność pokazuje rycina sezonowości.',
          '- Ujemne i bliskie zeru wartości w ciemnych miejscach to szum pomiarowy; pozostawiono je w danych.', '']
    en = [f'# {NAME}: artificial night-time light (VIIRS DNB)', '', f'Run date: {params["run"]}. Area file: {C["aoi_gpkg"]}. CRS: {CRS}.', '',
          '## Data', '',
          f'- VIIRS DNB monthly composites with stray-light correction: `{C["viirs"]}` (bands avg_rad and cf_cvg). Radiance in nW/cm²/sr.',
          f'- Annual value: median of the monthly radiances from the months in which the pixel has observations (cf_cvg > 0). Grid {FC * S30} m.',
          f'- Zones: the area from the GPKG file and rings around it (outer radii: {", ".join(f"{r:g} m" for r in sorted(C["rings_m"]))}). A VIIRS pixel belongs to a zone when ≥ 50% of its area lies in the zone.',
          *([f'- Map background: Sentinel-2 {C["background_year"]} (`COPERNICUS/S2_SR_HARMONIZED` with Cloud Score+ mask).'] if _BG is not None else []), '',
          '## Methods', '',
          '- Tables: mean, median, 90th percentile and sum of pixel radiance in each zone for every year.',
          '- Zone trend: Theil–Sen slope and Mann–Kendall test on annual means (at least 5 years). Per-pixel trend: the same method in every pixel (at least 8 years, or all available when there are fewer).',
          '- The tests include no correction for ties, temporal or spatial autocorrelation, or multiple testing: results are descriptive.', '',
          '## Limitations', '',
          '- VIIRS (about 500 m) cannot separate individual light sources, and its band (about 500–900 nm) records blue light poorly, e.g. from cool-white LEDs: the growth of LED lighting may be underestimated.',
          '- Satellite radiance is neither sky brightness measured from the ground (e.g. SQM) nor illuminance at ground level.',
          '- In summer at high latitudes some months may have no data; the seasonality figure shows completeness.',
          '- Negative and near-zero values in dark places are measurement noise; they were left in the data.', '']
    md = pl if LANG == 'pl' else en
    if notes:
        md += [T('## Uwagi z biegu', '## Run notes'), ''] + [f'- {u}' for u in notes] + ['']
    md += [T('## Pliki (liczba)', '## Files (count)'), ''] + [f'- {k}: {len(v)}' for k, v in params['files'].items()]
    with open(os.path.join(DIR_REP, f'{NAME}_zrodla_i_metody.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(md))
    say('@@RESULT|' + OUT)


# ------------------------------------------------------------------------------------------------
# uruchomienie
# ------------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description='Night-time light analysis (VIIRS DNB) for the QGIS plugin / analiza światła nocnego dla wtyczki QGIS')
    ap.add_argument('--config', help='plik JSON z konfiguracją / JSON config file')
    ap.add_argument('--check', action='store_true', help='test połączenia z Earth Engine / test the Earth Engine connection')
    ap.add_argument('--auth', action='store_true', help='logowanie do Earth Engine / log in to Earth Engine')
    ap.add_argument('--project', help='identyfikator projektu Earth Engine (dla --check) / Earth Engine project ID (for --check)')
    ap.add_argument('--lang', default=None)
    a = ap.parse_args()
    global LANG
    if a.lang:
        LANG = 'en' if a.lang.lower().startswith('en') else 'pl'
    if a.auth:
        do_auth()
        return 0
    if a.check:
        init_ee(a.project or '')
        say('@@CHECK_OK')
        return 0
    if not a.config:
        ap.error('--config, --check or --auth')
    with open(a.config, encoding='utf-8') as f:
        cfg = json.load(f)
    LANG = 'en' if str(cfg.get('lang', 'pl')).lower().startswith('en') else 'pl'
    t0 = time.time()
    stage(1, 8, T('Test połączenia z Google Earth Engine', 'Testing the Google Earth Engine connection'))
    init_ee(str(cfg.get('project', '')).strip())
    stage(2, 8, T('Wczytanie obszaru i przygotowanie siatki', 'Reading the area and preparing the grid'))
    setup(cfg)
    try:
        stage(3, 8, T('Pobieranie tła Sentinel-2', 'Downloading the Sentinel-2 background'))
        try:
            fetch_background()
        except Exception as e:
            NOTES.append(T(f'Tło Sentinel-2 nie zostało pobrane ({type(e).__name__}: {e}); mapy bez tła.', f'Sentinel-2 background not downloaded ({type(e).__name__}: {e}); maps without background.'))
            say(T('Tło Sentinel-2 pominięte:', 'Sentinel-2 background skipped:'), e)
        try:
            fetch_viirs()
        except Exception as e:
            module_error(T('Pobieranie VIIRS', 'VIIRS download'), e)
        if DL_ERRORS:
            table('pobieranie_bledy', pd.DataFrame([{T('Obraz', 'Image'): k, T('Błąd', 'Error'): v} for k, v in DL_ERRORS.items()]))
            NOTES.append(T(f'Nie pobrano {len(DL_ERRORS)} obrazów (tabela pobieranie_bledy); uruchom ponownie: pobrane obrazy są w pamięci podręcznej.',
                           f'{len(DL_ERRORS)} images were not downloaded (table pobieranie_bledy); run again: downloaded images are cached.'))
        stage(6, 8, T('Tabele, trend i ryciny', 'Tables, trend and figures'))
        try:
            analyse_annual()
        except Exception as e:
            module_error(T('Wyniki roczne', 'Annual results'), e)
        stage(7, 8, T('Sezonowość i animacje', 'Seasonality and animations'))
        try:
            analyse_monthly()
        except Exception as e:
            module_error(T('Wyniki miesięczne', 'Monthly results'), e)
        stage(8, 8, T('Zapis raportu', 'Writing the report'))
        write_report()
    except SystemExit:
        raise
    say(T(f'GOTOWE w {time.time() - t0:.0f} s; błędy modułów: {len(MODULE_ERRORS)}.', f'DONE in {time.time() - t0:.0f} s; module errors: {len(MODULE_ERRORS)}.'))
    return 2 if MODULE_ERRORS else 0


if __name__ == '__main__':
    sys.exit(main())
