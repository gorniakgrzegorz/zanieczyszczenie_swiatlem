"""Atrapa Google Earth Engine do testu notatnika bez dostępu do GEE: zwraca syntetyczne dane o właściwych nazwach pasm i typach."""
import os, json
import numpy as np
__version__ = 'stub-test'
CX, CY = float(os.environ.get('T_CX', 500000)), float(os.environ.get('T_CY', 500000))
LOG = []

def Initialize(**k): pass
def Authenticate(**k): pass

class _Z:
    def __init__(self, chain=(), meta=None):
        self._chain = tuple(chain); self._meta = dict(meta or {})
    def __getattr__(self, n):
        if n.startswith('__'):
            raise AttributeError(n)
        if n == 'getInfo':
            return lambda: _getinfo(self)
        if n == 'serialize':
            return lambda: json.dumps([list(self._chain), self._meta], sort_keys=True)
        def f(*a, **k):
            meta = dict(self._meta)
            if n == 'filterDate' and a and isinstance(a[0], str):
                meta['year'] = int(a[0][:4]); meta['month'] = int(a[0][5:7])
            if n == 'map' and a and callable(a[0]):
                a[0](_Z(('elem',)))                         # kontrola, że lambda nie zgłasza wyjątku
            return _Z(self._chain + (n,), meta)
        return f

def _ctor(name):
    def f(*a, **k):
        meta = {}
        if name == 'ImageCollection' or name == 'Image' or name == 'FeatureCollection':
            LOG.append((name, a[:1]))
        return _Z((name,), meta)
    return f
class _Ns:
    def __init__(self, name): self._n = name
    def __call__(self, *a, **k): return _ctor(self._n)(*a, **k)
    def __getattr__(self, m):
        if m.startswith('__'): raise AttributeError(m)
        def f(*a, **k):
            meta = {}
            if self._n == 'Image' and m == 'cat' and a and isinstance(a[0], (list, tuple)) and a[0]:
                meta = dict(a[0][0]._meta)
            return _Z((self._n, m), meta)
        return f
ImageCollection = _Ns('ImageCollection'); Image = _Ns('Image'); FeatureCollection = _Ns('FeatureCollection')
Filter = _Ns('Filter'); Geometry = _Ns('Geometry'); Feature = _Ns('Feature'); Reducer = _Ns('Reducer'); Algorithms = _Ns('Algorithms')

def _poly(r, dx=0, dy=0, n=64):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return [(CX + dx + r * np.cos(a), CY + dy + r * np.sin(a)) for a in t]

def _getinfo(z):
    if 'aggregate_array' in z._chain:
        ts = []
        import datetime
        for y in range(2014, 2027):
            for m in range(1, 13):
                if (y, m) > (2026, 9):
                    break
                ts.append(int(datetime.datetime(y, m, 15).timestamp() * 1000))
        return ts
    if 'FeatureCollection' in z._chain:
        import geopandas as gpd
        from shapely.geometry import Polygon
        specs = [('Special Area of Conservation (Habitats Directive)', _poly(2500, -3000, 2000), 'SOO test'),
                 ('Special Protection Area (Birds Directive)', _poly(3000, 4000, -3000), 'OSO test'),
                 ('Nature Reserve', _poly(700, 0, 0), 'Rezerwat test')]
        g = gpd.GeoDataFrame({'NAME': [s[2] for s in specs], 'DESIG': ['x'] * 3, 'DESIG_ENG': [s[0] for s in specs], 'WDPAID': [1, 2, 3], 'STATUS_YR': [2004, 2004, 1990], 'REP_AREA': [1.0, 2.0, 3.0]},
                             geometry=[Polygon(s[1]) for s in specs], crs='EPSG:2180').to_crs(4326)
        return json.loads(g.to_json())
    return 1

NCALL = [0]
import atexit; atexit.register(lambda: print('LICZBA ZAPYTAN computePixels:', NCALL[0]))
class data:
    @staticmethod
    def computePixels(zad):
        NCALL[0] += 1
        g = zad['grid']; w = g['dimensions']['width']; h = g['dimensions']['height']; at = g['affineTransform']
        s, x0, y1 = at['scaleX'], at['translateX'], at['translateY']
        xs = x0 + (np.arange(w) + 0.5) * s; ys = y1 - (np.arange(h) + 0.5) * s
        X, Y = np.meshgrid(xs, ys)
        meta = zad['expression']._meta; bands = zad['bandIds']
        d_city = np.hypot(X - (CX + 10000), Y - CY)               # miasto 10 km na wschód (w pierścieniu presji)
        d_park = np.hypot(X - CX, Y - CY)
        rng = np.random.RandomState(int(abs(x0 + y1)) % 99991)
        out = np.zeros((h, w), dtype=[(b, 'f8') for b in bands])
        for b in bands:
            if b == 'rad':
                yr = meta.get('year', 2020)
                v = (0.3 + 12 * np.exp(-(d_city / 1800) ** 2)) * (1 + 0.04 * (yr - 2014)) + rng.randn(h, w) * 0.05
                v = np.round(v * 100); v[rng.rand(h, w) < 0.01] = -999999; out[b] = v
            elif re.match(r'^[rc]\d\d$', b):
                yr = meta.get('year', 2020); mm = int(b[1:])
                cf = (np.exp(-((mm - 6.5) / 2.5) ** 2) * 0 + 8 + 6 * np.cos((mm - 1) / 12 * 2 * np.pi)).clip(0, None)
                cf = np.where(np.isin(mm, [6, 7]), 0, cf) + 0 * X
                if b[0] == 'c':
                    out[b] = np.round(cf)
                else:
                    v = np.round(((0.3 + 12 * np.exp(-(d_city / 1800) ** 2)) * (1 + 0.04 * (yr - 2014)) * (0.8 + 0.4 * np.cos((mm - 1) / 12 * 2 * np.pi))) * 100)
                    out[b] = np.where(cf > 0, v, -999999)
            elif b == 'ghm':
                out[b] = np.round((0.25 + 0.7 * np.exp(-(d_city / 6000) ** 2) + 0.2 * (d_park > 7000)) * 1000).clip(0, 1000)
            elif b == 'sac':
                out[b] = (np.hypot(X - (CX - 3000), Y - (CY + 2000)) < 2500).astype(float)
            elif b == 'spa':
                out[b] = (np.hypot(X - (CX + 4000), Y - (CY - 3000)) < 3000).astype(float)
            elif b.startswith('dw_'):
                yr = int(b[3:]); lab = np.full((h, w), 2.0)       # trawy
                lab[d_park < 6500] = 1                              # las
                lab[(d_park >= 6500) & ((X + Y) % 4000 < 1800)] = 4  # uprawy
                lab[d_city < 900 + 150 * (yr - 2016)] = 6          # zabudowa rośnie
                lab[(np.hypot(X - (CX - 2000), Y - (CY - 1000)) < 500)] = 0   # woda
                lab[(np.hypot(X - (CX + 1000), Y - (CY + 1500)) < 400 + 40 * (yr - 2016)) & (yr > 2020)] = 7   # wyrąb
                out[b] = lab + 1
            elif b in ('r', 'g', 'b'):
                base = {'r': 90, 'g': 120, 'b': 80}[b]
                out[b] = np.clip(base + 60 * np.sin(X / 3000) * np.cos(Y / 2500) + (d_city < 2000) * 60, 0, 255)
            else:
                raise RuntimeError(f'Image has no band named {b}')
        return out
import re
