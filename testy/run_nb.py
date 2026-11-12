import sys, os, json, time, re
os.environ['MPLBACKEND'] = 'Agg'; os.environ['NOTATNIK_TEST'] = '1'
nbp, tmp, scen = sys.argv[1], sys.argv[2], sys.argv[3]
if os.path.exists(os.path.join(tmp, 'center.txt')):
    _crs, _cx, _cy = open(os.path.join(tmp, 'center.txt')).read().split(); os.environ.update(T_CRS=_crs, T_CX=_cx, T_CY=_cy)
if 'nowdpa' in scen:
    os.environ['T_NOWDPA'] = '1'
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stub'))
import warnings; warnings.filterwarnings('ignore')
nb = json.load(open(nbp, encoding='utf-8'))
kody = [''.join(c['source']) for c in nb['cells'] if c['cell_type'] == 'code']
ns = {'__name__': '__main__'}
t0 = time.time()
for i, k in enumerate(kody):
    if i == 1:                                              # po ustawieniach: nadpisanie ścieżek i wydajności na potrzeby testu
        U = ns['USTAWIENIA']; U['aoi_gpkg'] = os.path.join(tmp, 'AOI.gpkg'); U['folder_wynikow'] = os.path.join(tmp, 'Wyniki'); U['dpi'] = 80; U['watki'] = 4
        U['kafel_px'] = 512
        if scen == 'dw_zip':
            U['pobieranie']['zip'] = True; U['pobieranie']['przytnij_do_stref'] = True; U['presje']['natura']['zrodlo_zmian'] = 'dw'
        if 'podzial' in scen:
            U['aoi_kolumna_typu'] = 'nazwa'
        if scen.startswith('szybki') or 'podzial' in scen or 'nowdpa' in scen:
            U['animacje']['miesieczna'] = False
    if i == 4 and scen.startswith('rf'):                    # po komórce AOI: sztuczny plik RF z notatnika głównego na tej samej siatce
        pass
    t1 = time.time()
    print(f'--- komórka {i} ---', flush=True)
    try:
        exec(compile(k, f'komorka_{i}', 'exec'), ns)
    except Exception:
        import traceback; traceback.print_exc(); print('BŁĄD w komórce', i); sys.exit(1)
    if i == 3 and scen.startswith('rf'):                    # po komórce 3 (AOI i siatka) zapisujemy rf5_epoki.tif
        import numpy as np, rasterio
        from rasterio.transform import from_origin
        h, w = ns['H30'], ns['W30']; yy, xx = np.mgrid[0:h, 0:w]
        def mapa(e): 
            a = np.full((h, w), 4, np.uint8); a[(xx - w / 2) ** 2 + (yy - h / 2) ** 2 < (h / 4) ** 2] = 2
            a[(xx > w * 0.7 + 3 * (e - 1985) / 10) & (yy < h * 0.4)] = 1; return a
        ep = [1979, 1985, 2000, 2026] if scen == 'rf' else [1985, 2026]
        with rasterio.open(os.path.join(ns['DIR_RAST'], f"{ns['NAZWA']}_rf5_epoki.tif"), 'w', driver='GTiff', height=h, width=(w - 5 if scen == 'rf_zla_siatka' else w), count=len(ep), dtype='uint8', crs=ns['CRS'],
                           transform=from_origin(ns['X0'], ns['Y1'], 30, 30)) as d:
            for j, e in enumerate(ep, 1):
                d.write(mapa(e)[:, :(w - 5 if scen == 'rf_zla_siatka' else w)], j); d.set_band_description(j, f'rf5_{e} (1 zabudowa, 2 las, 3 woda, 4 trawy i krzewy, 5 uprawy)')
    print(f'    {time.time() - t1:.1f} s', flush=True)
print(f'GOTOWE w {time.time() - t0:.0f} s; BLEDY_MODULOW={ns["BLEDY_MODULOW"]}; UWAGI={ns["UWAGI"]}')
