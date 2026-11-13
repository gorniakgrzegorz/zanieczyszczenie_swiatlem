"""zanieczyszczenie_swiatlem: presje zewnętrzne na dowolny obszar z pliku GPKG.

Sztuczne światło nocą (VIIRS DNB), globalna modyfikacja przez człowieka (gHM) i obszary Natura 2000 (WDPA)
dla zakresu pracy wskazanego plikiem GeoPackage. Masowe pobieranie z Google Earth Engine, GeoTIFF, tabele, ryciny, animacje.

Co wpisać przed uruchomieniem: w sekcji "USTAWIENIA DO WPISANIA" poniżej trzy pola WYMAGANE (PROJEKT_GEE, PLIK_GPKG, FOLDER_WYNIKOW);
resztę ustawień można zostawić. Te same pola można podać w wierszu poleceń, bez edycji pliku.

Użycie:
    python zanieczyszczenie_swiatlem.py --projekt MOJ_PROJEKT_GEE --gpkg obszar.gpkg --out wyniki
    python zanieczyszczenie_swiatlem.py --tylko-sprawdz            # sprawdza ustawienia i połączenie z GEE, niczego nie pobiera
    python zanieczyszczenie_swiatlem.py --gpkg obszar.gpkg --ustaw animacje.miesieczna=false --ustaw presje.skala_m=960

Pierwsze logowanie: earthengine authenticate (albo skrypt sam poprosi o zalogowanie). Projekt GEE można też podać zmienną środowiskową GEE_PROJECT.
Ustawienia pozostałe są w słowniku USTAWIENIA; opcja --ustaw klucz.podklucz=WARTOŚĆ (JSON) nadpisuje dowolne z nich.
Plik ma format Jupytext (komórki "# %%"), więc można go też otworzyć jako notatnik (VS Code, Jupyter, Colab).
"""
import matplotlib
matplotlib.use("Agg")   # bez okien: ryciny trafiają tylko do plików
import os

# %% [markdown]
# # Presje zewnętrzne na dowolny obszar z pliku GPKG: sztuczne światło nocą, modyfikacja przez człowieka i obszary Natura 2000
#
# Samodzielny notatnik (odpowiada sekcji 35 notatnika głównego „Pokrycie terenu AOI RF DW”). Zakresem pracy jest dowolny obszar z pliku GeoPackage (park, gmina, zlewnia, pole badań, także kilka obiektów naraz; nie musi to być park krajobrazowy). Notatnik **masowo pobiera z Google Earth Engine** zdjęcia i warstwy dla tego obszaru (VIIRS DNB: roczne mediany i wszystkie miesięczne kompozyty, Global Human Modification, obszary Natura 2000 z WDPA, tło Sentinel-2) i zapisuje je jako GeoTIFF. Następnie liczy tabele, trendy, ryciny i animacje.
#
# **Jak uruchomić.** Edytuj tylko komórkę z ustawieniami (sekcja 1): na górze jest zakres pracy (plik GPKG, `aoi_gpkg`) i folder wyników. Zakres to suma wszystkich obiektów wskazanej warstwy; podział na dwie części (np. park i otulina) jest opcjonalny. Potem uruchom wszystkie komórki. Błąd jednego modułu jest zapisywany w raporcie, a notatnik liczy dalej. Pobrane obrazy trafiają do pamięci podręcznej (`_cache`), więc ponowne uruchomienie po przerwaniu nie pobiera ich od nowa.
#
# **Pierwszy raz i bez wiedzy informatycznej?** Przewodnik krok po kroku (konto Google, własny projekt Google Earth Engine, plik z obszarem, uruchomienie w Colabie): https://gorniakgrzegorz.github.io/zanieczyszczenie_swiatlem/#przewodnik
#
# **W wersji skryptowej** trzy pola wymagane (PROJEKT_GEE, PLIK_GPKG, FOLDER_WYNIKOW) są na górze, w sekcji USTAWIENIA DO WPISANIA; można je też podać w wierszu poleceń (--projekt, --gpkg, --out). Opcja --tylko-sprawdz testuje ustawienia i połączenie z Earth Engine bez pobierania.

# %% [markdown]
# ## 1. Ustawienia
#
# Jedyna komórka do edycji. Pierwszy blok to zakres pracy: plik GPKG z dowolnym obszarem i folder wyników. Dalej: Google Earth Engine, parametry presji (kolekcje, lata, skala, porównanie w Natura 2000), masowe pobieranie, tło map, animacje i wydajność.

# %%
# ============================================================================================
# USTAWIENIA DO WPISANIA
# ============================================================================================
# --- WYMAGANE: bez tych trzech pól skrypt się zatrzyma z komunikatem (przed pobieraniem) ---
PROJEKT_GEE = os.environ.get('GEE_PROJECT', 'TWOJ-PROJEKT-GEE')   # identyfikator projektu Google Cloud z włączonym Earth Engine
                                                                    # (https://console.cloud.google.com/earth-engine/configuration)
PLIK_GPKG = 'obszar.gpkg'            # plik GeoPackage z zakresem pracy: dowolny obszar (suma wszystkich obiektów warstwy), z nadanym układem współrzędnych
FOLDER_WYNIKOW = 'wyniki'            # folder wyników; w nim powstanie folder <nazwa obszaru> z 01_tabele ... 06_raport

# --- OPCJONALNE (najczęściej zmieniane; None lub wartość domyślna wystarczą) ---
WARSTWA_GPKG = None                  # nazwa warstwy w pliku GPKG; None = pierwsza warstwa
NAZWA_OBSZARU = None                 # nazwa w tytułach rycin i plikach wyników; None = nazwa pliku GPKG
PROMIEN_PRESJI_M = 5000              # promień pierścienia wokół obszaru (otoczenie, z którego dociera rozproszone światło), w metrach
LATA_VIIRS = (2014, 2026)            # zakres lat VIIRS; niepełny rok bieżący warto wyłączyć (np. (2014, 2025))
# Reszta (skala siatki, źródło map pokrycia terenu dla Natura 2000, tło Sentinel-2, animacje, równoległość, ZIP) jest w słowniku USTAWIENIA poniżej
# albo w wierszu poleceń: --ustaw klucz.podklucz=WARTOŚĆ.

# %%
# WYMAGANE (wpisz przed uruchomieniem): 'aoi_gpkg' (plik GPKG), 'folder_wynikow' (gdzie zapisać wyniki) i 'projekt_gee' (identyfikator projektu Google Cloud z włączonym Earth Engine).
# Pozostałe ustawienia mają sensowne wartości domyślne.
USTAWIENIA = {
    # ============ 1. ZAKRES PRACY (plik GPKG, dowolny obszar) ============
    # Zakres pracy (AOI) = suma wszystkich obiektów wskazanej warstwy pliku GPKG. Może to być dowolny obszar: park, gmina, zlewnia, pole badań,
    # także kilka rozłącznych obiektów. Plik nie wymaga żadnego szczególnego przygotowania; potrzebny jest tylko układ współrzędnych (CRS).
    'aoi_gpkg': PLIK_GPKG,
    'aoi_warstwa': WARSTWA_GPKG,                 # None = pierwsza warstwa pliku
    'nazwa': NAZWA_OBSZARU,                       # nazwa obszaru w tytułach rycin i plikach wyników; None = nazwa pliku GPKG
    # Opcjonalny podział zakresu na dwie części do osobnych tabel i granic na mapach (np. park i otulina, jądro i strefa buforowa).
    # None = bez podziału (domyślnie). Gdy podano kolumnę atrybutu, obiekty, których wartość zawiera podany tekst, tworzą część dodatkową.
    'aoi_kolumna_typu': None, 'aoi_wartosc_czesci_dodatkowej': 'otulin', 'aoi_nazwy_czesci': ('część główna', 'część dodatkowa'),
    'bufory_m': [PROMIEN_PRESJI_M],                  # pierścienie wokół AOI (porównanie z otoczeniem)
    'ramka_m': 500,                      # margines mapy wokół obszaru (kontekst na rycinach)
    'presja_promien_m': PROMIEN_PRESJI_M,            # promień pierścienia presji (ramka mapy jest powiększana do tego promienia)
    'folder_wynikow': FOLDER_WYNIKOW,   # w nim folder <nazwa AOI> z podfolderami 01_tabele ... 06_raport

    # ============ 2. GOOGLE EARTH ENGINE ============
    'projekt_gee': PROJEKT_GEE,    # WYMAGANE: identyfikator projektu Google Cloud z włączonym Earth Engine (https://console.cloud.google.com/earth-engine/configuration)

    # ============ 3. DANE I ANALIZA PRESJI ZEWNĘTRZNYCH ============
    'presje': {
        'wlacz': True,
        'skala_m': 480,                  # siatka VIIRS i gHM: wielokrotność 30 m (480 m = 16 pikseli 30 m; natywnie około 460 m)
        'viirs': 'NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG', 'viirs_lata': LATA_VIIRS,   # lata bez żadnego miesiąca w kolekcji są pomijane
        'progi_radiancji': [],           # brak zweryfikowanego progu ekologicznego radiancji; ewentualne progi tylko jako umowne
        'ghm': 'CSP/HM/GlobalHumanModification',
        'wdpa': 'WCMC/WDPA/current/polygons',     # do publikacji wersja datowana: WCMC/WDPA/RRRRMM/polygons
        # porównanie zmian pokrycia terenu w Natura 2000 i poza nią
        'natura': {
            # 'auto': mapy RF 5 klas z notatnika głównego (plik <nazwa>_rf5_epoki.tif), a gdy go nie ma, Dynamic World;
            # 'rf_geotiff': tylko plik RF (a gdy go nie ma lub siatka się różni, Dynamic World); 'dw': zawsze Dynamic World
            'zrodlo_zmian': 'auto',
            'rf5_geotiff': None,         # None = <folder_wynikow>/<nazwa>/04_rastry/<nazwa>_rf5_epoki.tif
            'lata_dw': (2016, 2026),     # epoki Dynamic World (rok pierwszy i ostatni); 2015 ma mało scen
            'miesiace_dw': (6, 9),       # sezon dla mody etykiet Dynamic World
            # kod Dynamic World (etykieta 0–8) -> klasa 5: 1 zabudowa, 2 lasy i drzewa, 3 wody, 4 trawy i krzewy, 5 uprawy.
            # Gleba odkryta i śnieg trafiają do klasy 4, bo inaczej świeże wyręby (w Dynamic World: gleba odkryta) wypadałyby z porównania.
            'mapowanie_dw': {0: 3, 1: 2, 2: 4, 3: 4, 4: 5, 5: 4, 6: 1, 7: 4, 8: 4},
            'min_pikseli_grupy': 100,    # grupy (strefa × w/poza Natura 2000) mniejsze od tylu pikseli 30 m są pomijane
        },
    },

    # ============ 4. MASOWE POBIERANIE ZDJĘĆ I WARSTW DLA AOI ============
    # Wszystko jest pobierane z GEE kaflami (z ponawianiem) i zapisywane lokalnie: pamięć podręczna .npz oraz GeoTIFF w 04_rastry.
    'pobieranie': {
        'geotiff': True,                 # zapis pobranych warstw jako GeoTIFF (układ AOI, np. EPSG:2180)
        'viirs_miesieczne': True,        # wszystkie dostępne miesięczne kompozyty VIIRS (radiancja i liczba obserwacji), nie tylko mediany roczne
        'tlo_s2_geotiff': True,          # tło Sentinel-2 (RGB) jako GeoTIFF
        'przytnij_do_stref': False,      # True = wartości poza AOI i pierścieniem zapisane jako brak danych (inaczej cała ramka mapy)
        'rownolegle_obrazy': 4,          # liczba obrazów pobieranych równocześnie (każdy dzielony na kafle)
        'zip': False,                    # spakowanie 04_rastry do jednego archiwum ZIP w folderze wyników
    },

    # ============ 5. TŁO MAP: SENTINEL-2 ============
    'tlo': {'wlacz': True, 'rok': 2025, 'miesiace': (6, 9), 'skala_m': 30,   # skala 10, 15 lub 30 m (30 m wystarcza do tła; 10 m = 9 razy więcej danych)
            'prog_cs': 0.6, 'max_zachmurzenie_sceny': 60},

    # ============ 6. ANIMACJE I RYCINY ============
    'animacje': {'wlacz': True, 'czas_ms': 700, 'mp4': True,
                 'miesieczna': True},    # dodatkowa animacja ze wszystkich miesięcznych kompozytów VIIRS (wymaga viirs_miesieczne)
    'dpi': 200,

    # ============ 7. WYDAJNOŚĆ ============
    'skala_dw_m': None,                  # None = 10 m dla ramek do 1500 km², 30 m dla większych
    'kafel_px': 512,                     # bok kafla pobierania (piksele); przy błędach pamięci GEE zmniejsz do 256
    'watki': 8,                          # równoległe żądania do GEE
}

# %%
import argparse, json as _json, sys as _sys
_ap = argparse.ArgumentParser(description='Presje zewnętrzne na dowolny obszar z GPKG (światło nocą, gHM, Natura 2000).')
_ap.add_argument('--projekt', help='identyfikator projektu Google Earth Engine (WYMAGANE, jeśli nie wpisano PROJEKT_GEE ani GEE_PROJECT)')
_ap.add_argument('--gpkg', help='plik GeoPackage z zakresem pracy (nadpisuje PLIK_GPKG)')
_ap.add_argument('--out', help='folder wyników (nadpisuje FOLDER_WYNIKOW)')
_ap.add_argument('--warstwa', help='warstwa w pliku GPKG (domyślnie pierwsza)')
_ap.add_argument('--nazwa', help='nazwa obszaru w tytułach i plikach wyników')
_ap.add_argument('--ustaw', action='append', default=[], metavar='KLUCZ.PODKLUCZ=JSON',
                 help='dowolne ustawienie, np. animacje.miesieczna=false, presje.skala_m=960, bufory_m=[2000,5000]; można powtarzać')
_ap.add_argument('--tylko-sprawdz', action='store_true', help='sprawdź ustawienia i połączenie z Earth Engine, po czym zakończ (nic nie jest pobierane)')
_arg, _ = _ap.parse_known_args()
for _k, _v in (('projekt_gee', _arg.projekt), ('aoi_gpkg', _arg.gpkg), ('folder_wynikow', _arg.out), ('aoi_warstwa', _arg.warstwa), ('nazwa', _arg.nazwa)):
    if _v is not None:
        USTAWIENIA[_k] = _v
for _u in _arg.ustaw:
    if '=' not in _u:
        _ap.error(f'--ustaw wymaga postaci klucz=wartość, otrzymano: {_u}')
    _sciezka, _txt = _u.split('=', 1)
    try:
        _wart = _json.loads(_txt)
    except ValueError:
        _wart = _txt                       # tekst bez cudzysłowów traktujemy jako napis
    _cel = USTAWIENIA
    _klucze = _sciezka.split('.')
    for _k in _klucze[:-1]:
        if not isinstance(_cel.get(_k), dict):
            _ap.error(f'nieznany klucz ustawień: {_sciezka}')
        _cel = _cel[_k]
    if _klucze[-1] not in _cel:
        _ap.error(f'nieznany klucz ustawień: {_sciezka}')
    _cel[_klucze[-1]] = _wart

# %% [markdown]
# ## 2. Środowisko
#
# Biblioteki, podłączenie Dysku Google i logowanie do Google Earth Engine.

# %%
import importlib.util, subprocess, sys
for _pakiet, _modul, _wymagany in [('earthengine-api', 'ee', True), ('geopandas', 'geopandas', True), ('rasterio', 'rasterio', True),
                                   ('pyogrio', 'pyogrio', True), ('imageio', 'imageio', True), ('imageio-ffmpeg', 'imageio_ffmpeg', False)]:
    if importlib.util.find_spec(_modul) is None:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', _pakiet], check=_wymagany)

import os, re, io, json, time, hashlib, datetime, warnings, traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import pandas as pd
import geopandas as gpd
import ee
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_origin
from scipy.special import ndtr
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from PIL import Image
try:
    from IPython.display import display, Image as IPImage
except ImportError:                                  # uruchomienie jako skrypt z terminala, bez IPython
    def display(*obiekty, **k):
        for o in obiekty:
            if o is not None:
                print(o)
    def IPImage(*a, **k):
        return None
try:
    import imageio.v2 as imageio
except ImportError:
    imageio = None
try:
    from tqdm.auto import tqdm
except ImportError:
    def tqdm(x, **k):
        return x
warnings.filterwarnings('ignore', category=RuntimeWarning)
plt.rcParams.update({'font.size': 9, 'figure.dpi': 100})

try:
    from google.colab import drive
    drive.mount('/content/drive')
except ModuleNotFoundError:
    pass

U = USTAWIENIA

def sprawdz_ustawienia():
    """Sprawdza pola wymagane przed logowaniem do GEE i pobieraniem; zatrzymuje bieg z czytelnym komunikatem zamiast błędu w połowie pracy."""
    bledy = []
    projekt = str(U.get('projekt_gee') or '').strip()
    if not projekt or 'TWOJ' in projekt.upper():
        bledy.append("projekt_gee: wpisz identyfikator projektu Google Cloud z włączonym Earth Engine "
                     "(https://console.cloud.google.com/earth-engine/configuration; w skrypcie także zmienna środowiskowa GEE_PROJECT lub opcja --projekt).")
    gpkg = str(U.get('aoi_gpkg') or '')
    if not gpkg or not os.path.isfile(gpkg):
        bledy.append(f"aoi_gpkg: nie znaleziono pliku GPKG ({gpkg!r}). Wskaż plik z zakresem pracy (w Colabie sprawdź też, czy Dysk Google jest podłączony).")
    folder = str(U.get('folder_wynikow') or '')
    try:
        os.makedirs(folder, exist_ok=True)
        _probe = os.path.join(folder, '.zapis_test')
        open(_probe, 'w').close(); os.remove(_probe)
    except Exception as e:
        bledy.append(f"folder_wynikow: brak możliwości zapisu w {folder!r} ({type(e).__name__}).")
    if bledy:
        komunikat = 'Popraw ustawienia i uruchom ponownie:\n - ' + '\n - '.join(bledy)
        if sys.modules.get('ipykernel') is not None:
            raise ValueError(komunikat)
        sys.exit('BŁĄD USTAWIEŃ. ' + komunikat)
    print('Ustawienia: projekt GEE =', projekt, '| AOI =', gpkg, '| wyniki =', folder)

sprawdz_ustawienia()
try:
    ee.Initialize(project=U['projekt_gee'])
except Exception:
    ee.Authenticate()
    try:
        ee.Initialize(project=U['projekt_gee'])
    except Exception as e:
        raise RuntimeError(f"Nie udało się połączyć z Earth Engine (projekt {U['projekt_gee']!r}). Sprawdź, czy projekt istnieje, ma włączone Earth Engine API "
                           f"i czy konto ma do niego dostęp. Szczegóły: {e}") from e
print('Google Earth Engine:', ee.__version__, '| projekt:', U['projekt_gee'])

# %%
# opcja --tylko-sprawdz: ustawienia i logowanie już sprawdzone w poprzedniej komórce; test zapytania do Earth Engine i koniec
if _arg.tylko_sprawdz:
    try:
        _odp = ee.Number(1).add(1).getInfo()
        print('Połączenie z Earth Engine działa (test zapytania: 1 + 1 =', _odp, '). Wszystko gotowe do uruchomienia pełnego biegu.')
    except Exception as e:
        raise SystemExit(f'Połączenie z Earth Engine nie działa: {type(e).__name__}: {e}')
    raise SystemExit(0)

# %% [markdown]
# ## 3. Zakres pracy (AOI), strefy i siatka analizy
#
# Wczytanie GPKG, wybór układu metrycznego (PL-1992 w Polsce, w innych miejscach strefa UTM), strefy (AOI, opcjonalnie jego dwie części, pierścień presji) oraz siatka 30 m wyrównana tak samo jak w notatniku głównym, więc rastry z obu notatników się pokrywają.

# %%
U = USTAWIENIA
if not os.path.exists(U['aoi_gpkg']):
    raise FileNotFoundError(f"Brak pliku AOI: {U['aoi_gpkg']}. Sprawdź ścieżkę w USTAWIENIA['aoi_gpkg'] i czy Dysk Google jest podłączony.")
try:
    _warstwy = gpd.list_layers(U['aoi_gpkg'])['name'].tolist()
except Exception:
    _warstwy = []
if len(_warstwy) > 1 and not U['aoi_warstwa']:
    print(f"Plik AOI ma {len(_warstwy)} warstwy {_warstwy}; użyta zostanie pierwsza ({_warstwy[0]}). Wskaż inną w USTAWIENIA['aoi_warstwa'].")
gdf = gpd.read_file(U['aoi_gpkg'], layer=U['aoi_warstwa']) if U['aoi_warstwa'] else gpd.read_file(U['aoi_gpkg'])
if gdf.crs is None:
    raise ValueError('Plik AOI nie ma układu współrzędnych; nadaj go w QGIS i zapisz ponownie.')
gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
if not len(gdf):
    raise ValueError('Warstwa AOI nie zawiera żadnych geometrii.')
NAZWA = U['nazwa'] or os.path.splitext(os.path.basename(U['aoi_gpkg']))[0]

# układ metryczny: PL-1992 dla obszarów w Polsce, w pozostałych przypadkach strefa UTM
def _scal(g):
    return g.union_all() if hasattr(g, 'union_all') else g.unary_union
_c = _scal(gdf.to_crs(4326)).centroid
CRS = 'EPSG:2180' if (14.0 <= _c.x <= 24.2 and 49.0 <= _c.y <= 55.0) else gdf.estimate_utm_crs().to_string()
aoi = _scal(gdf.to_crs(CRS)).buffer(0)

# opcjonalny podział zakresu na część główną i dodatkową (np. park i otulina); bez podziału zakres to cały plik
CZ_GLOWNA = CZ_DODATK = None
NAZWY_CZESCI = tuple(U.get('aoi_nazwy_czesci') or ('część główna', 'część dodatkowa'))
_g = gdf.to_crs(CRS).reset_index(drop=True)
print(f'Zakres pracy: {len(_g)} obiekt(ów) w pliku {os.path.basename(U["aoi_gpkg"])}; powierzchnia {aoi.area / 1e4:.1f} ha ({aoi.area / 1e6:.2f} km²).')
if U.get('aoi_kolumna_typu'):
    if U['aoi_kolumna_typu'] not in _g.columns:
        raise ValueError(f"Kolumna '{U['aoi_kolumna_typu']}' nie istnieje w warstwie AOI; dostępne: {[c for c in _g.columns if c != 'geometry']}.")
    _dod = _g[U['aoi_kolumna_typu']].astype(str).str.lower().str.contains(str(U['aoi_wartosc_czesci_dodatkowej']).lower())
    if _dod.any() and (~_dod).any():
        CZ_GLOWNA = _scal(_g[~_dod].geometry).buffer(0); CZ_DODATK = _scal(_g[_dod].geometry).buffer(0).difference(CZ_GLOWNA)
        print(f'Podział zakresu: {NAZWY_CZESCI[0]} {CZ_GLOWNA.area / 1e4:.1f} ha; {NAZWY_CZESCI[1]} {CZ_DODATK.area / 1e4:.1f} ha.')
    else:
        print(f"Podział zakresu pominięty: wartość '{U['aoi_wartosc_czesci_dodatkowej']}' w kolumnie '{U['aoi_kolumna_typu']}' nie rozdziela obiektów na dwie grupy.")

# strefy: kod 1 = AOI, kolejne kody = pierścienie buforów
strefy = [('AOI', 1, aoi)]
_poprz = aoi
for i, b in enumerate(sorted(U['bufory_m'])):
    pierscien = aoi.buffer(b).difference(_poprz)
    strefy.append((f'bufor {(sorted(U["bufory_m"])[i - 1] if i else 0) / 1000:g}–{b / 1000:g} km'.replace('.', ','), i + 2, pierscien))
    _poprz = aoi.buffer(b)
STREFY = {n: k for n, k, _ in strefy}
gdf_strefy = gpd.GeoDataFrame({'strefa': [n for n, _, _ in strefy], 'kod': [k for _, k, _ in strefy]},
                              geometry=[g for _, _, g in strefy], crs=CRS)

# siatka 30 m wyrównana do wielokrotności 30 m (ta sama konstrukcja co w notatniku głównym, więc rastry z obu notatników się pokrywają);
# siatka Dynamic World ma krok 10 m (3 × 3 w pikselu 30 m) albo 30 m
S30 = 30
minx, miny, maxx, maxy = gdf_strefy.total_bounds
m = max(U['ramka_m'], U['presja_promien_m'] + 2 * S30)               # ramka obejmuje pierścień presji
X0 = np.floor((minx - m) / S30) * S30; Y1 = np.ceil((maxy + m) / S30) * S30
W30 = int(np.ceil((maxx + m - X0) / S30)); H30 = int(np.ceil((Y1 - (miny - m)) / S30))
POW_RAMKI_KM2 = W30 * H30 * S30 * S30 / 1e6
SDW = U['skala_dw_m'] or (10 if POW_RAMKI_KM2 <= 1500 else 30)
FDW = S30 // SDW                                     # 3 albo 1
WDW, HDW = W30 * FDW, H30 * FDW
SIATKA30 = {'x0': X0, 'y1': Y1, 's': S30, 'w': W30, 'h': H30}
SIATKADW = {'x0': X0, 'y1': Y1, 's': SDW, 'w': WDW, 'h': HDW}
EXTENT = (X0, X0 + W30 * S30, Y1 - H30 * S30, Y1)    # do imshow

def rastruj_strefy(siatka):
    tr = from_origin(siatka['x0'], siatka['y1'], siatka['s'], siatka['s'])
    ksztalty = [(g, k) for _, k, g in reversed(strefy)]       # AOI na końcu, więc nadpisuje pierścienie
    return rasterize(ksztalty, out_shape=(siatka['h'], siatka['w']), transform=tr, fill=0, dtype='uint8')
STREFA30 = rastruj_strefy(SIATKA30)
if CZ_GLOWNA is not None:
    GLOWNA30 = rasterize([(CZ_GLOWNA, 1)], out_shape=(H30, W30), transform=from_origin(X0, Y1, S30, S30), fill=0, dtype='uint8').astype(bool) & (STREFA30 == 1)
    DODATK30 = (STREFA30 == 1) & ~GLOWNA30
else:
    GLOWNA30 = STREFA30 == 1; DODATK30 = np.zeros((H30, W30), bool)
# części AOI do tabel (tylko przy podziale w ustawieniach); cały AOI jest zawsze pierwszą strefą
CZESCI_AOI = [(NAZWY_CZESCI[0], GLOWNA30), (NAZWY_CZESCI[1], DODATK30)] if DODATK30.any() else []

# pierścień presji: pas o szerokości 'presja_promien_m' wokół AOI; strefy raportowania: AOI, jego części (gdy jest podział), pierścień
_R = U['presja_promien_m']
PIER_ = rasterize([(aoi.buffer(_R).difference(aoi), 1)], out_shape=(H30, W30), transform=from_origin(X0, Y1, S30, S30), fill=0, dtype='uint8').astype(bool) & (STREFA30 != 1)
DOM_ = (STREFA30 > 0) | PIER_
STREFY_RAP = [('AOI', STREFA30 == 1)] + [(n_c, m_c) for n_c, m_c in CZESCI_AOI] + ([(f'pierścień {_R / 1000:g} km', PIER_)] if PIER_.any() else [])

# zasięg dla GEE (prostokąt ramki w WGS84)
_ramka = gpd.GeoSeries.from_xy([X0, X0 + W30 * S30], [Y1 - H30 * S30, Y1], crs=CRS).to_crs(4326)
GEOM = ee.Geometry.Rectangle([_ramka.x.min(), _ramka.y.min(), _ramka.x.max(), _ramka.y.max()], 'EPSG:4326', False)

KATALOG = os.path.join(U['folder_wynikow'], NAZWA)
DIR_TAB, DIR_RYC, DIR_ANIM, DIR_RAST, DIR_WEKT, DIR_RAP, DIR_CACHE = [os.path.join(KATALOG, d) for d in
    ('01_tabele', '02_ryciny', '03_animacje', '04_rastry', '05_wektory', '06_raport', '_cache')]
for d in (DIR_TAB, DIR_RYC, DIR_ANIM, DIR_RAST, DIR_WEKT, DIR_RAP, DIR_CACHE):
    os.makedirs(d, exist_ok=True)
gdf_strefy.to_file(os.path.join(DIR_WEKT, f'{NAZWA}_strefy.gpkg'), driver='GPKG')
if CZ_GLOWNA is not None:
    gpd.GeoDataFrame({'obiekt': list(NAZWY_CZESCI), 'pow_ha': [round(CZ_GLOWNA.area / 1e4, 1), round(CZ_DODATK.area / 1e4, 1)]}, geometry=[CZ_GLOWNA, CZ_DODATK], crs=CRS).to_file(
        os.path.join(DIR_WEKT, f'{NAZWA}_czesci_aoi.gpkg'), driver='GPKG')

POW_PIX30_HA = S30 * S30 / 1e4
print(f'{NAZWA}: układ {CRS}; AOI {aoi.area / 1e6:.2f} km²; strefy raportowania: {[n for n, _ in STREFY_RAP]}')
print(f'Ramka {W30} × {H30} px (30 m), {POW_RAMKI_KM2:.0f} km²; Dynamic World w siatce {SDW} m ({WDW} × {HDW} px)')
print('Wyniki w:', KATALOG)
if POW_RAMKI_KM2 > 10000:
    print('UWAGA: duża ramka; pobieranie potrwa dłużej. Rozważ podział obszaru albo większy kafel.')

# %% [markdown]
# ## 4. Narzędzia: pobieranie z GEE kaflami, tabele, mapy i animacje
#
# Pobieranie kaflami z ponawianiem błędów przejściowych i atomowym zapisem pamięci podręcznej, pobieranie wielu obrazów równolegle (`pobierz_wiele`), zapis GeoTIFF, trend Theila-Sena z testem Manna-Kendalla oraz funkcje rycin.

# %%
# ---------- stan wspólny ----------
TABELE, RYCINY, UWAGI, BLEDY_MODULOW, ZRODLA = {}, [], [], [], []
_TLO = None                                          # wyblakłe tło Sentinel-2 (ustawiane w sekcji 5)

def blad_modulu(nazwa, e):
    """Błąd w module analitycznym: komunikat, wpis do raportu i kontynuacja (moduły są niezależne).
    W teście syntetycznym (zmienna środowiskowa NOTATNIK_TEST) błąd jest zgłaszany dalej."""
    if os.environ.get('NOTATNIK_TEST'):
        raise e
    traceback.print_exc()
    BLEDY_MODULOW.append({'Moduł': nazwa, 'Błąd': f'{type(e).__name__}: {e}'})
    UWAGI.append(f'Moduł "{nazwa}" przerwany błędem {type(e).__name__}: {e}; kolejne moduły policzone bez jego wyników.')
    print(f'*** Moduł "{nazwa}" przerwany: {type(e).__name__}: {e}. Notatnik liczy dalej.')

# ---------- pobieranie z GEE kaflami, z ponawianiem i pamięcią podręczną ----------
def _kafle(siatka, kafel):
    for ty in range(0, siatka['h'], kafel):
        for tx in range(0, siatka['w'], kafel):
            yield ty, tx, min(kafel, siatka['h'] - ty), min(kafel, siatka['w'] - tx)

def _trwaly_blad(e):
    """Błędy, których ponawianie nie ma sensu (zła nazwa kolekcji lub pasma, brak uprawnień)."""
    t = str(e).lower()
    return any(s in t for s in ('not found', 'does not exist', 'permission', 'not been used', 'has no bands', 'band pattern', 'invalid', 'must be', 'no such'))

def _pobierz_kafel(img, pasma, siatka, ty, tx, h, w, proby=5):
    s = siatka['s']
    zad = {'expression': img, 'fileFormat': 'NUMPY_NDARRAY', 'bandIds': pasma,
           'grid': {'dimensions': {'width': w, 'height': h}, 'crsCode': CRS,
                    'affineTransform': {'scaleX': s, 'shearX': 0, 'translateX': siatka['x0'] + tx * s,
                                        'shearY': 0, 'scaleY': -s, 'translateY': siatka['y1'] - ty * s}}}
    for p in range(proby):
        try:
            return ee.data.computePixels(zad)
        except Exception as e:
            if p == proby - 1 or _trwaly_blad(e):
                raise RuntimeError(f'kafel ({ty}, {tx}): {e}. Przy przekroczeniu czasu lub pamięci zmniejsz USTAWIENIA["kafel_px"] (np. 256).') from e
            time.sleep(2 ** p + np.random.rand())

def _klucz_cache(img, pasma, siatka, nazwa):
    try:
        opis = img.serialize()                       # cały graf obliczeń GEE: zmiana kolekcji lub parametru unieważnia pamięć podręczną
    except Exception:
        opis = repr(img)
    return hashlib.md5(json.dumps([nazwa, pasma, siatka, CRS, opis], sort_keys=True, default=str).encode()).hexdigest()[:10]

def pobierz(img, pasma, siatka, nazwa, typ=np.uint8, kafel=None, watki=None):
    """Obraz GEE (pasma całkowite, 0 lub wartość specjalna = brak danych) -> {pasmo: tablica 2D} na siatce; wynik w pamięci podręcznej .npz."""
    kafel = kafel or U['kafel_px']
    plik = os.path.join(DIR_CACHE, f'{nazwa}_{_klucz_cache(img, pasma, siatka, nazwa)}.npz')
    if os.path.exists(plik):
        try:
            with np.load(plik) as z:
                return {p: z[p] for p in pasma}
        except Exception:
            os.remove(plik)                          # uszkodzony plik (przerwany zapis): pobieramy ponownie
    wyn = {p: np.zeros((siatka['h'], siatka['w']), dtype=typ) for p in pasma}
    kafle = list(_kafle(siatka, kafel))
    with ThreadPoolExecutor(max_workers=max(1, min(watki or U['watki'], len(kafle)))) as ex:
        fut = {ex.submit(_pobierz_kafel, img, pasma, siatka, *k): k for k in kafle}
        for f in tqdm(as_completed(fut), total=len(fut), desc=nazwa, leave=False, disable=len(fut) < 2):
            ty, tx, h, w = fut[f]; a = f.result()
            for p in pasma:
                wyn[p][ty:ty + h, tx:tx + w] = a[p].astype(typ)
    _tmp = plik + '.tmp.npz'
    np.savez_compressed(_tmp, **wyn); os.replace(_tmp, plik)      # zapis atomowy
    return wyn

def pobierz_wiele(zadania, opis='pobieranie'):
    """Masowe pobieranie: zadania = lista słowników {'img', 'pasma', 'siatka', 'nazwa', 'typ'}. Obrazy pobierane są równolegle;
    błąd jednego obrazu nie przerywa reszty. Zwraca ({nazwa: wynik lub None}, {nazwa: komunikat błędu})."""
    wyn, bledy = {}, {}
    if not zadania:
        return wyn, bledy
    def _jedno(z):
        return pobierz(z['img'], z['pasma'], z['siatka'], z['nazwa'], z.get('typ', np.uint8), watki=2)
    with ThreadPoolExecutor(max_workers=max(1, U['pobieranie']['rownolegle_obrazy'])) as ex:
        fut = {ex.submit(_jedno, z): z['nazwa'] for z in zadania}
        for f in tqdm(as_completed(fut), total=len(fut), desc=opis):
            n = fut[f]
            try:
                wyn[n] = f.result()
            except Exception as e:
                wyn[n] = None; bledy[n] = f'{type(e).__name__}: {e}'
    return wyn, bledy

def zapisz_geotiff(nazwa, warstwy, siatka, typ='float32', nodata=np.nan):
    """GeoTIFF (LZW, kafelkowany) w 04_rastry; warstwy = lista (opis pasma, tablica 2D) na siatce {x0, y1, s, w, h}."""
    p = os.path.join(DIR_RAST, f'{NAZWA}_{nazwa}.tif')
    with rasterio.open(p, 'w', driver='GTiff', height=siatka['h'], width=siatka['w'], count=len(warstwy), dtype=typ, crs=CRS,
                       transform=from_origin(siatka['x0'], siatka['y1'], siatka['s'], siatka['s']), nodata=nodata, compress='lzw', tiled=True,
                       blockxsize=256, blockysize=256) as d:
        for i, (opis, a) in enumerate(warstwy, 1):
            d.write(a.astype(typ), i); d.set_band_description(i, str(opis))
    return p

# ---------- siatki grube i strefy ----------
def blok(a, f, fun='mean', wypelnij=np.nan):
    """Agregacja tablicy 30 m do bloków f × f (mean, sum, max) z dopełnieniem krawędzi."""
    h, w = int(np.ceil(a.shape[0] / f)) * f, int(np.ceil(a.shape[1] / f)) * f
    b = np.full((h, w), wypelnij, np.float32); b[:a.shape[0], :a.shape[1]] = a
    b = b.reshape(h // f, f, w // f, f)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', category=RuntimeWarning)
        return {'mean': np.nanmean, 'sum': np.nansum, 'max': np.nanmax}[fun](b, axis=(1, 3))

def siatka_gruba(f):
    """Siatka o kroku f × 30 m wyrównana do lewego górnego rogu ramki 30 m."""
    h, w = int(np.ceil(H30 / f)), int(np.ceil(W30 / f))
    s = {'x0': X0, 'y1': Y1, 's': S30 * f, 'w': w, 'h': h}
    return s, (X0, X0 + w * S30 * f, Y1 - h * S30 * f, Y1)

def strefy_grube(f):
    """Strefy raportowania na siatce grubej: piksel należy do strefy, gdy ≥ 50% jego pikseli 30 m leży w strefie."""
    return [(n, blok(m.astype(np.float32), f, 'mean', 0) >= 0.5) for n, m in STREFY_RAP]

def _daty(rok, m1, m2):
    """Granice okresu (początek włącznie, koniec wyłącznie) dla miesięcy m1–m2 roku."""
    return f'{rok}-{m1:02d}-01', (f'{rok}-{m2 + 1:02d}-01' if m2 < 12 else f'{rok + 1}-01-01')

# ---------- statystyka: trend Theila-Sena i test Manna-Kendalla ----------
def trend_sen_mk(stos, lata, blok=40000, min_lat=8, maska=None):
    """Nachylenie Theila-Sena [jednostki/rok] i test Manna-Kendalla (z, p dwustronne) dla każdego piksela stosu (t, h, w);
    NaN = brak obserwacji; liczone tylko dla pikseli w masce z co najmniej min_lat latami danych."""
    t, h, w = stos.shape
    lata = np.asarray(lata, np.float32)
    X = stos.reshape(t, -1)
    i, j = np.triu_indices(t, 1)
    dt = (lata[j] - lata[i])[:, None]
    n_obs = np.isfinite(X).sum(axis=0)
    wazne = n_obs >= min_lat
    if maska is not None:
        wazne &= maska.ravel()
    idx = np.flatnonzero(wazne)
    nach = np.full(h * w, np.nan, np.float32); z = np.full(h * w, np.nan, np.float32)
    for a in range(0, idx.size, blok):
        k = idx[a:a + blok]
        Y = X[:, k].astype(np.float32)
        roz = Y[j] - Y[i]
        with np.errstate(all='ignore'):
            nach[k] = np.nanmedian(roz / dt, axis=0)
        S = np.nansum(np.sign(roz), axis=0)
        n = n_obs[k].astype(np.float64)
        sd = np.sqrt(n * (n - 1) * (2 * n + 5) / 18.0)
        z[k] = np.where(S > 0, (S - 1) / sd, np.where(S < 0, (S + 1) / sd, 0.0))
    p = 2 * ndtr(-np.abs(z))
    return nach.reshape(h, w), z.reshape(h, w), p.reshape(h, w).astype(np.float32)

# ---------- tabele ----------
def tabela(nazwa, df, pokaz=True):
    """Zapis tabeli wynikowej (CSV) i rejestracja w TABELE; pusta tabela dostaje wiersz z wyjaśnieniem zamiast pustego pliku."""
    df = pd.DataFrame() if df is None else df; TABELE[nazwa] = df; df_zap = df
    if df is None or not len(df):
        df_zap = pd.DataFrame([{'Uwaga': 'brak wyników: za mało danych spełniających kryteria (szczegóły w uwagach raportu)'}])
        UWAGI.append(f'Tabela {nazwa}: brak wyników spełniających kryteria.')
    df_zap.to_csv(os.path.join(DIR_TAB, f'{NAZWA}_{nazwa}.csv'), index=False)
    if pokaz:
        display(df_zap)
    return df

# ---------- mapy, ryciny, animacje ----------
def granice(ax, kolor='black'):
    """Granice na mapie: zakres pracy linią ciągłą (przy podziale na części: część główna linią ciągłą, zewnętrzna granica AOI przerywaną),
    pierścienie cienką szarą linią; zakres ramki, bez osi i opisów osi."""
    if len(gdf_strefy) > 1:
        gdf_strefy[gdf_strefy.kod > 1].boundary.plot(ax=ax, color='#7f7f7f' if kolor == 'black' else kolor, linewidth=0.5)
    if CZ_GLOWNA is not None:
        gpd.GeoSeries([aoi.boundary], crs=CRS).plot(ax=ax, color=kolor, linewidth=0.7, linestyle=(0, (4, 2.5)))
        gpd.GeoSeries([CZ_GLOWNA.boundary], crs=CRS).plot(ax=ax, color=kolor, linewidth=0.8)
    else:
        gpd.GeoSeries([aoi.boundary], crs=CRS).plot(ax=ax, color=kolor, linewidth=0.9)
    ax.set_xlim(EXTENT[0], EXTENT[1]); ax.set_ylim(EXTENT[2], EXTENT[3]); ax.set_xticks([]); ax.set_yticks([]); ax.set_xlabel(''); ax.set_ylabel('')

def skala_mapy(ax):
    """Podziałka liniowa w lewym dolnym rogu: odcinek z kreskami na końcach, etykieta nad odcinkiem, biała obwódka."""
    import matplotlib.patheffects as _pe
    szer = EXTENT[1] - EXTENT[0]; wys = EXTENT[3] - EXTENT[2]
    dl = 10 ** np.floor(np.log10(szer / 4)); dl = 5 * dl if szer / dl > 25 else (2 * dl if szer / dl > 12 else dl)
    x = EXTENT[0] + szer * 0.05; y = EXTENT[2] + wys * 0.05; k = wys * 0.012
    obw = [_pe.withStroke(linewidth=3.5, foreground='white')]
    ax.plot([x, x + dl], [y, y], color='black', lw=2, solid_capstyle='butt', path_effects=obw, zorder=20)
    for xx in (x, x + dl):
        ax.plot([xx, xx], [y - k, y + k], color='black', lw=1.2, path_effects=obw, zorder=20)
    ax.annotate(f'{dl / 1000:g} km'.replace('.', ','), (x + dl / 2, y + k), xytext=(0, 4), textcoords='offset points', ha='center', va='bottom', fontsize=7.5,
                path_effects=[_pe.withStroke(linewidth=2.5, foreground='white')], zorder=21)

def panel(ax, klasy=None, kolory=None, tytul='', alfa=0.85):
    """Mapa: wyblakłe tło Sentinel-2, klasy (0 = przezroczyste), granice stref, ramka bez osi."""
    if _TLO is not None:
        ax.imshow(_TLO, extent=EXTENT, interpolation='nearest')
    if klasy is not None:
        cmap = ListedColormap(['#00000000'] + list(kolory)); cmap.set_bad('#00000000')
        ax.imshow(np.ma.masked_equal(klasy, 0), cmap=cmap, vmin=0, vmax=len(kolory), extent=EXTENT, interpolation='nearest', alpha=alfa)
    granice(ax)
    ax.set_title(tytul, fontsize=9)

def mapa(ax, a, cmap, vmin=None, vmax=None, tytul='', ext=None, etykieta=None, norm=None, tlo=True):
    """Mapa ciągła z granicami stref i skalą; zwraca obiekt imshow (do paska barw)."""
    if tlo and _TLO is not None:
        ax.imshow(_TLO, extent=EXTENT, interpolation='nearest')
    im = ax.imshow(a, cmap=cmap, vmin=None if norm else vmin, vmax=None if norm else vmax, norm=norm, extent=ext or EXTENT, interpolation='nearest')
    granice(ax); skala_mapy(ax); ax.set_title(tytul, fontsize=9)
    if etykieta:
        plt.colorbar(im, ax=ax, fraction=0.035, pad=0.02, shrink=0.85).set_label(etykieta, fontsize=8)
    return im

def zapisz(fig, nazwa):
    """Zapis ryciny (PNG, dpi z ustawień); gdy jest tytuł nadrzędny, panele są przesuwane w dół."""
    if fig._suptitle is not None and not fig.get_constrained_layout() and not getattr(fig, '_uklad', False):
        try:
            fig.tight_layout(rect=(0, 0, 1, 0.95)); fig._suptitle.set_y(0.995)
        except Exception:
            pass
    p = os.path.join(DIR_RYC, f'{NAZWA}_{nazwa}.png'); fig.savefig(p, dpi=U['dpi'], bbox_inches='tight', facecolor='white')
    if 'agg' not in matplotlib.get_backend().lower():
        plt.show()
    plt.close(fig); return p

def legenda_dol(fig, pary, ncol=5):
    fig.legend(handles=[Patch(facecolor=c, edgecolor='none', label=n) for n, c in pary], loc='lower center', ncol=ncol, frameon=False, bbox_to_anchor=(0.5, -0.02))

def anim_mapy(klatki, nazwa, rysuj, czas_ms=None, rozmiar=(6.4, None), pokaz=True):
    """Animacja GIF (i MP4, gdy dostępny ffmpeg) z dowolnych map: rysuj(fig, ax, element) rysuje jedną klatkę."""
    AN = U['animacje']
    if not AN['wlacz']:
        return None
    czas_ms = czas_ms or AN['czas_ms']
    kl_ = []
    for el in klatki:
        fig, ax = plt.subplots(figsize=(rozmiar[0], rozmiar[1] or rozmiar[0] * H30 / W30 + 1.3))
        rysuj(fig, ax, el); fig.subplots_adjust(bottom=0.08, top=0.93)
        buf = io.BytesIO(); fig.savefig(buf, format='png', dpi=105, facecolor='white'); plt.close(fig); buf.seek(0)
        kl_.append(Image.open(buf).convert('RGB'))
    if not kl_:
        return None
    w_, h_ = min(k.size[0] for k in kl_) // 2 * 2, min(k.size[1] for k in kl_) // 2 * 2
    kl_ = [k.crop((0, 0, w_, h_)) for k in kl_]
    p = os.path.join(DIR_ANIM, f'{NAZWA}_{nazwa}.gif')
    kl_[0].save(p, save_all=True, append_images=kl_[1:], duration=[czas_ms] * (len(kl_) - 1) + [czas_ms * 3], loop=0)
    if AN['mp4'] and imageio is not None:
        try:
            imageio.mimsave(p.replace('.gif', '.mp4'), [np.asarray(k) for k in kl_] + [np.asarray(kl_[-1])] * 2, fps=max(1000 / czas_ms, 1), macro_block_size=1)
        except Exception:
            pass
    print('animacja:', p)
    if pokaz:
        display(IPImage(filename=p))
    return p

# ---------- mapa zmian pokrycia terenu (5 klas) ----------
LEGENDA_5 = {1: 'Zabudowa', 2: 'Lasy i drzewa', 3: 'Wody', 4: 'Trawy i krzewy', 5: 'Uprawy'}
KLASY_5 = (1, 2, 3, 4, 5)
KAT_ZMIAN = {1: ('Nowa zabudowa', '#d7301f'), 2: ('Wylesienie (las -> trawy, krzewy lub uprawy)', '#fdae61'), 3: ('Zarastanie i zalesienie (-> las)', '#1a9641'),
             4: ('Zaoranie (trawy i krzewy -> uprawy)', '#bf812d'), 5: ('Porzucenie upraw (uprawy -> trawy i krzewy)', '#a6d96a'),
             6: ('Zmiana wód', '#2c7bb6'), 7: ('Inne zmiany', '#b2abd2')}
def mapa_zmian(a, b):
    z = np.zeros(a.shape, np.uint8); w = (a > 0) & (b > 0) & (a != b)
    z[w] = 7; z[w & ((a == 3) | (b == 3))] = 6; z[w & (a == 5) & (b == 4)] = 5; z[w & (a == 4) & (b == 5)] = 4
    z[w & np.isin(a, [4, 5]) & (b == 2)] = 3; z[w & (a == 2) & np.isin(b, [4, 5])] = 2; z[w & (b == 1)] = 1
    return z
print('Narzędzia gotowe: kafle', U['kafel_px'], 'px,', U['watki'], 'wątków,', U['pobieranie']['rownolegle_obrazy'], 'obrazy równolegle.')

# %% [markdown]
# ## 5. Dane: tło, formy ochrony, masowe pobieranie i pokrycie terenu
#
# (a) Tło Sentinel-2 i granice form ochrony przyrody z WDPA. (b) Masowe pobieranie VIIRS (roczne i miesięczne), gHM i rastra Natura 2000 wraz z zapisem GeoTIFF do `04_rastry`. (c) Mapy pokrycia terenu do porównania zmian w Natura 2000 i poza nią: z notatnika głównego (plik `<nazwa>_rf5_epoki.tif`, gdy jest i siatka się zgadza), a w przeciwnym razie z Dynamic World. Na końcu tabela z listą zapisanych plików.

# %%
SP_ = U['presje']; PB = U['pobieranie']; TL = U['tlo']
# skala grubej siatki VIIRS i gHM (wielokrotność 30 m), jej strefy raportowania i maska sumy stref
f16 = max(1, SP_['skala_m'] // S30); SIATKA_P, EXT_P = siatka_gruba(f16); STR_P = strefy_grube(f16)
MASKA_P = np.any([m_ for _, m_ in STR_P], axis=0)

# ---------- tło: mediana Sentinel-2 z maską Cloud Score+ (RGB 8-bit) ----------
TLO = None; SIATKA_TLA = None
def tlo_s2():
    if S30 % TL['skala_m']:
        raise ValueError('USTAWIENIA["tlo"]["skala_m"] musi dzielić 30 bez reszty (10, 15 lub 30).')
    d1, d2 = _daty(TL['rok'], *TL['miesiace'])
    cs = ee.ImageCollection('GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED')
    kol = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(GEOM).filterDate(d1, d2)
           .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', TL['max_zachmurzenie_sceny'])).linkCollection(cs, ['cs_cdf'])
           .map(lambda im: im.updateMask(im.select('cs_cdf').gte(TL['prog_cs'])).divide(10000)))
    vis = kol.select(['B4', 'B3', 'B2']).median().visualize(min=0, max=0.25).rename(['r', 'g', 'b'])
    siatka = {'x0': X0, 'y1': Y1, 's': TL['skala_m'], 'w': W30 * S30 // TL['skala_m'], 'h': H30 * S30 // TL['skala_m']}
    a = pobierz(vis, ['r', 'g', 'b'], siatka, f's2_rgb_{TL["rok"]}_{TL["skala_m"]}m')
    return np.dstack([a['r'], a['g'], a['b']]), siatka

if TL['wlacz']:
    try:
        TLO, SIATKA_TLA = tlo_s2()
        _TLO = (TLO.astype(np.float32).mean(axis=2, keepdims=True) * 0.45 + 255 * 0.55).repeat(3, axis=2).astype(np.uint8)
        print(f'Tło Sentinel-2 {TL["rok"]}: {TLO.shape[1]} × {TLO.shape[0]} px ({TL["skala_m"]} m)')
    except Exception as _e:
        UWAGI.append(f'Tło Sentinel-2: nie pobrano ({type(_e).__name__}: {_e}); mapy bez tła.')
        print('Tło Sentinel-2 pominięte:', _e)

# ---------- formy ochrony przyrody z WDPA (wektory): rezerwaty i obszary Natura 2000 w ramce; kopia GeoJSON w pamięci podręcznej ----------
def formy_ochrony():
    klucz = hashlib.md5(json.dumps([SP_['wdpa'], [round(float(v), 5) for v in (_ramka.x.min(), _ramka.y.min(), _ramka.x.max(), _ramka.y.max())]]).encode()).hexdigest()[:8]
    plik = os.path.join(DIR_CACHE, f'wdpa_formy_ochrony_{klucz}.geojson')
    if os.path.exists(plik):
        return gpd.read_file(plik)
    fc = ee.FeatureCollection(SP_['wdpa']).filterBounds(GEOM)
    fc = fc.filter(ee.Filter.Or(ee.Filter.stringContains('DESIG_ENG', 'Nature Reserve'), ee.Filter.stringContains('DESIG', 'Rezerwat'),
                                ee.Filter.stringContains('DESIG_ENG', 'Habitats Directive'), ee.Filter.stringContains('DESIG_ENG', 'Birds Directive')))
    fc = fc.map(lambda f: ee.Feature(f.geometry().simplify(15)).copyProperties(f, ['NAME', 'DESIG', 'DESIG_ENG', 'WDPAID', 'STATUS_YR', 'REP_AREA']))
    cechy_ = fc.getInfo().get('features', [])
    if not cechy_:
        return gpd.GeoDataFrame({'forma': []}, geometry=[], crs=CRS)
    g = gpd.GeoDataFrame.from_features(cechy_, crs='EPSG:4326').to_crs(CRS)
    g['forma'] = np.where(g['DESIG_ENG'].astype(str).str.contains('Habitats'), 'Natura 2000 siedliskowa (SOO)',
                 np.where(g['DESIG_ENG'].astype(str).str.contains('Birds'), 'Natura 2000 ptasia (OSO)', 'rezerwat przyrody'))
    g.to_file(plik, driver='GeoJSON')
    return g

STYL_OCHRONY = {'aoi': dict(color='#1b7837', linewidth=2.0), 'aoi_zewn': dict(color='#1b7837', linewidth=1.7, linestyle=(0, (6, 3))),
                'rezerwat przyrody': dict(color='#d7191c', linewidth=1.4), 'Natura 2000 siedliskowa (SOO)': dict(color='#e7298a', linewidth=1.5, linestyle=(0, (5, 2.5))),
                'Natura 2000 ptasia (OSO)': dict(color='#f768a1', linewidth=1.5, linestyle=(0, (1.5, 2)))}
FORMY_OCHRONY = None
try:
    FORMY_OCHRONY = formy_ochrony()
    print('Formy ochrony (WDPA) w ramce:', FORMY_OCHRONY['forma'].value_counts().to_dict() if len(FORMY_OCHRONY) else 'brak')
except Exception as _e:
    UWAGI.append(f'Formy ochrony (WDPA): nie wczytano ({type(_e).__name__}: {_e}).')
    print('Formy ochrony (WDPA) pominięte:', _e)

def warstwy_ochrony(ax, legenda=True, tylko=None):
    """Formy ochrony na mapie: zakres pracy (gruba zielona linia; przy podziale na części: część główna ciągła, zewnętrzna granica AOI przerywana),
    rezerwaty (czerwone), Natura 2000 (różowe przerywane: siedliskowe kreski, ptasie kropki)."""
    uchwyty = []
    if FORMY_OCHRONY is not None and len(FORMY_OCHRONY):
        for forma in ('Natura 2000 siedliskowa (SOO)', 'Natura 2000 ptasia (OSO)', 'rezerwat przyrody'):
            g = FORMY_OCHRONY[FORMY_OCHRONY.forma == forma]
            if len(g) and (tylko is None or forma in tylko):
                g.boundary.plot(ax=ax, zorder=6, **STYL_OCHRONY[forma])
                uchwyty.append(plt.Line2D([], [], label=forma, **STYL_OCHRONY[forma]))
    if CZ_GLOWNA is not None:
        gpd.GeoSeries([aoi.boundary], crs=CRS).plot(ax=ax, zorder=7, **STYL_OCHRONY['aoi_zewn'])
        gpd.GeoSeries([CZ_GLOWNA.boundary], crs=CRS).plot(ax=ax, zorder=8, **STYL_OCHRONY['aoi'])
        uchwyty = [plt.Line2D([], [], label=NAZWY_CZESCI[0], **STYL_OCHRONY['aoi']), plt.Line2D([], [], label=f'granica AOI (wraz z: {NAZWY_CZESCI[1]})', **STYL_OCHRONY['aoi_zewn'])] + uchwyty
    else:
        gpd.GeoSeries([aoi.boundary], crs=CRS).plot(ax=ax, zorder=8, **STYL_OCHRONY['aoi'])
        uchwyty = [plt.Line2D([], [], label=f'zakres pracy ({NAZWA})', **STYL_OCHRONY['aoi'])] + uchwyty
    ax.set_xlim(EXTENT[0], EXTENT[1]); ax.set_ylim(EXTENT[2], EXTENT[3]); ax.set_xticks([]); ax.set_yticks([]); ax.set_xlabel(''); ax.set_ylabel('')
    if legenda and uchwyty:
        ax.legend(handles=uchwyty, loc='upper center', bbox_to_anchor=(0.5, -0.01), ncol=3, frameon=False, fontsize=8)
    return uchwyty

# %%
# ======== MASOWE POBIERANIE: VIIRS (roczne i miesięczne), gHM, Natura 2000 (raster) ========
PLIKI = []                                           # manifest zapisanych GeoTIFF
BLEDY_POBIERANIA = {}
ALAN, ALAN_M, ALAN_CF, HM, N2, NAT = {}, {}, {}, None, None, None

def _maskuj(a):
    """Przycięcie do sumy stref (poza AOI i pierścieniem brak danych), gdy włączone w ustawieniach."""
    if PB['przytnij_do_stref'] and a.shape == MASKA_P.shape:
        a = a.astype(np.float32).copy(); a[~MASKA_P] = np.nan
    return a

def _zapisz_tif(nazwa, warstwy, siatka, typ='float32', nodata=np.nan, opis=''):
    if not PB['geotiff']:
        return None
    p = zapisz_geotiff(nazwa, warstwy, siatka, typ, nodata)
    PLIKI.append({'Plik': os.path.basename(p), 'Zawartość': opis, 'Pasma': len(warstwy), 'Siatka [m]': siatka['s'], 'Rozmiar [px]': f"{siatka['w']} × {siatka['h']}",
                  'Rozmiar pliku [MB]': round(os.path.getsize(p) / 1e6, 2)})
    return p

def dostepne_miesiace_viirs():
    """Miesiące (rok, miesiąc) dostępne w kolekcji VIIRS w zakresie lat z ustawień: jedno zapytanie do GEE; sprawdza też nazwę kolekcji."""
    y0, y1 = SP_['viirs_lata']
    t = ee.ImageCollection(SP_['viirs']).filterDate(f'{y0}-01-01', f'{y1 + 1}-01-01').aggregate_array('system:time_start').getInfo()
    return sorted({(d.year, d.month) for d in pd.to_datetime(list(t), unit='ms')})

def viirs_roku(r):
    """Mediana roczna miesięcznych radiancji (pasmo avg_rad), piksele z liczbą obserwacji cf_cvg > 0; wartość × 100, brak danych = -999999."""
    kol = ee.ImageCollection(SP_['viirs']).filterDate(f'{r}-01-01', f'{r + 1}-01-01')
    im = kol.map(lambda m: m.select('avg_rad').updateMask(m.select('cf_cvg').gt(0))).median()
    return im.multiply(100).round().unmask(-999999).toInt32().rename('rad')

def viirs_miesiace_roku(r, miesiace):
    """Jeden obraz z pasmami r01…r12 (radiancja × 100, brak danych = -999999) i c01…c12 (liczba obserwacji) dla dostępnych miesięcy roku."""
    obrazy = []
    for m_ in miesiace:
        d1, d2 = _daty(r, m_, m_)
        im = ee.ImageCollection(SP_['viirs']).filterDate(d1, d2).select(['avg_rad', 'cf_cvg']).mosaic()
        obrazy.append(im.select('avg_rad').updateMask(im.select('cf_cvg').gt(0)).multiply(100).round().unmask(-999999).toInt32().rename(f'r{m_:02d}'))
        obrazy.append(im.select('cf_cvg').unmask(0).toInt32().rename(f'c{m_:02d}'))
    return ee.Image.cat(obrazy)

if SP_['wlacz']:
    # ---- 1) sztuczne światło nocą (VIIRS DNB) ----
    try:
        MIES = dostepne_miesiace_viirs()
        if not MIES:
            raise RuntimeError(f"kolekcja {SP_['viirs']} nie ma obrazów w latach {SP_['viirs_lata']}; sprawdź nazwę kolekcji i zakres lat")
        LATA_V = sorted({r for r, _ in MIES})
        print(f'VIIRS: {len(MIES)} miesięcy w {len(LATA_V)} latach ({MIES[0][0]}-{MIES[0][1]:02d} … {MIES[-1][0]}-{MIES[-1][1]:02d})')
        # roczne mediany: podstawa tabel, trendów i animacji
        zad = [{'img': viirs_roku(r), 'pasma': ['rad'], 'siatka': SIATKA_P, 'nazwa': f'viirs_{r}', 'typ': np.int32} for r in LATA_V]
        wyn, bl = pobierz_wiele(zad, 'VIIRS roczne')
        for r in LATA_V:
            if wyn.get(f'viirs_{r}') is None:
                continue
            a = wyn[f'viirs_{r}']['rad'].astype(np.float32)
            a[a == -999999] = np.nan; a /= 100                                      # ujemne radiancje (szum w ciemnych miejscach) zachowane
            if np.isfinite(a).any():
                ALAN[r] = a
        BLEDY_POBIERANIA.update(bl)
        if ALAN:
            _zapisz_tif(f'viirs_roczne_{min(ALAN)}_{max(ALAN)}', [(f'{r}: mediana miesięcznych radiancji [nW/cm2/sr]', _maskuj(ALAN[r])) for r in sorted(ALAN)], SIATKA_P,
                        opis='VIIRS DNB: mediana roczna miesięcznych radiancji (avg_rad), nW/cm2/sr, float32')
        # wszystkie miesięczne kompozyty: radiancja i liczba obserwacji
        if PB['viirs_miesieczne']:
            miesiace_roku = {r: [m_ for rr, m_ in MIES if rr == r] for r in LATA_V}
            zad = [{'img': viirs_miesiace_roku(r, mm), 'pasma': [f'r{m_:02d}' for m_ in mm] + [f'c{m_:02d}' for m_ in mm], 'siatka': SIATKA_P, 'nazwa': f'viirs_mies_{r}', 'typ': np.int32}
                   for r, mm in miesiace_roku.items()]
            wyn, bl = pobierz_wiele(zad, 'VIIRS miesięczne')
            BLEDY_POBIERANIA.update(bl)
            for r, mm in miesiace_roku.items():
                a = wyn.get(f'viirs_mies_{r}')
                if a is None:
                    continue
                for m_ in mm:
                    rad = a[f'r{m_:02d}'].astype(np.float32); rad[rad == -999999] = np.nan; rad /= 100
                    ALAN_M[(r, m_)] = rad; ALAN_CF[(r, m_)] = a[f'c{m_:02d}'].astype(np.float32)
            if ALAN_M:
                klucze = sorted(ALAN_M)
                _zapisz_tif('viirs_miesieczne_radiancja', [(f'{r}-{m_:02d} radiancja [nW/cm2/sr]', _maskuj(ALAN_M[(r, m_)])) for r, m_ in klucze], SIATKA_P,
                            opis=f'VIIRS DNB: {len(klucze)} miesięcznych kompozytów, avg_rad [nW/cm2/sr] (brak danych = NaN)')
                _zapisz_tif('viirs_miesieczne_liczba_obserwacji', [(f'{r}-{m_:02d} cf_cvg (liczba obserwacji bez chmur)', _maskuj(ALAN_CF[(r, m_)])) for r, m_ in klucze], SIATKA_P,
                            opis='VIIRS DNB: liczba obserwacji (cf_cvg) w miesięcznych kompozytach')
        print(f'VIIRS: roczne {len(ALAN)} z {len(LATA_V)}, miesięczne {len(ALAN_M)} z {len(MIES) if PB["viirs_miesieczne"] else 0}')
    except Exception as _e:
        blad_modulu('Pobieranie: VIIRS', _e)

    # ---- 2) globalna modyfikacja przez człowieka (gHM) ----
    try:
        hm = pobierz(ee.ImageCollection(SP_['ghm']).mosaic().select('gHM').multiply(1000).round().unmask(-1).toInt16().rename('ghm'), ['ghm'], SIATKA_P, 'ghm', typ=np.int16)['ghm'].astype(np.float32)
        hm[hm < 0] = np.nan; hm /= 1000; HM = hm
        _zapisz_tif('ghm', [('gHM (0–1), ok. 2016', _maskuj(HM))], SIATKA_P, opis='Global Human Modification, 0–1 (stan ok. 2016)')
    except Exception as _e:
        UWAGI.append(f'gHM: pominięty ({type(_e).__name__}: {_e}).')
        print('gHM pominięty:', _e)

    # ---- 3) Natura 2000 (WDPA): raster 30 m obszarów siedliskowych (SOO) i ptasich (OSO) ----
    try:
        fc = ee.FeatureCollection(SP_['wdpa']).filterBounds(GEOM)
        sac = ee.Image().byte().paint(fc.filter(ee.Filter.stringContains('DESIG_ENG', 'Habitats Directive')), 1).unmask(0).rename('sac')
        spa = ee.Image().byte().paint(fc.filter(ee.Filter.stringContains('DESIG_ENG', 'Birds Directive')), 1).unmask(0).rename('spa')
        N2 = pobierz(sac.addBands(spa), ['sac', 'spa'], SIATKA30, 'natura2000_wdpa', typ=np.uint8)
        NAT = (N2['sac'] > 0) | (N2['spa'] > 0)
        _zapisz_tif('natura2000_raster', [('SOO (dyrektywa siedliskowa), 1 = obszar', N2['sac']), ('OSO (dyrektywa ptasia), 1 = obszar', N2['spa'])], SIATKA30, 'uint8', 0,
                    opis='Natura 2000 z WDPA, rasteryzacja 30 m')
    except Exception as _e:
        blad_modulu('Pobieranie: Natura 2000', _e)

# ---- 4) zawsze: strefy analizy (do przycinania i kontroli w QGIS) ----
_warstwy_stref = [('kod strefy (1 AOI, 2+ pierścienie buforów)', STREFA30)]
if CZESCI_AOI:
    _warstwy_stref += [(n_, m_.astype(np.uint8)) for n_, m_ in CZESCI_AOI]
_warstwy_stref.append((f'pierścień presji {U["presja_promien_m"] / 1000:g} km', PIER_.astype(np.uint8)))
_zapisz_tif('strefy_analizy', _warstwy_stref, SIATKA30, 'uint8', 0, opis='strefy raportowania na siatce 30 m')
if TLO is not None and PB['tlo_s2_geotiff']:
    _zapisz_tif(f'tlo_sentinel2_{TL["rok"]}_rgb', [('czerwony', TLO[:, :, 0]), ('zielony', TLO[:, :, 1]), ('niebieski', TLO[:, :, 2])], SIATKA_TLA, 'uint8', 0,
                opis=f'Sentinel-2 {TL["rok"]}, mediana z maską Cloud Score+, RGB 8-bit (min 0, max 0,25)')

# %%
# ======== POKRYCIE TERENU DO PORÓWNANIA W NATURA 2000 I POZA NIĄ: K5[epoka] = mapa 5 klas na siatce 30 m ========
NZ = SP_['natura']
K5, EPOKI, ZRODLO_K5, DW = {}, [], None, {}

def k5_z_rf_geotiff(sciezka):
    """Mapy RF 5 klas z notatnika głównego (<nazwa>_rf5_epoki.tif, opisy pasm 'rf5_<rok> ...'); siatka musi być identyczna jak w tym notatniku."""
    with rasterio.open(sciezka) as d:
        if d.crs is None or (d.crs.to_string().upper() != CRS.upper() and d.crs.to_epsg() != int(CRS.split(':')[1])):
            raise ValueError(f'inny układ współrzędnych pliku ({d.crs}) niż w tym notatniku ({CRS})')
        if (d.height, d.width) != (H30, W30) or abs(d.transform.a - S30) > 1e-6 or abs(d.transform.c - X0) > 1e-3 or abs(d.transform.f - Y1) > 1e-3:
            raise ValueError('siatka pliku różni się od siatki tego notatnika (użyj tych samych bufory_m, ramka_m i presja_promien_m co w notatniku głównym)')
        out = {}
        for i, opis in enumerate(d.descriptions, 1):
            mt = re.match(r'rf5_(\d{4})', opis or '')
            if mt:
                out[int(mt.group(1))] = d.read(i).astype(np.uint8)
    if len(out) < 2:
        raise ValueError('w pliku nie znaleziono co najmniej dwóch pasm rf5_<rok>')
    return out

def klasa5_z_dw(a):
    """Mapa Dynamic World (kod etykiety + 1, 0 = brak) -> klasy 5 na siatce 30 m (większość pikseli 10 m w pikselu 30 m)."""
    lut = np.zeros(10, np.uint8)
    for k, v in NZ['mapowanie_dw'].items():
        lut[int(k) + 1] = v
    a5 = lut[np.clip(a, 0, 9)]
    if FDW == 1:
        return a5
    h, w = a5.shape
    b = a5.reshape(h // FDW, FDW, w // FDW, FDW)
    licz = np.stack([(b == k).sum(axis=(1, 3)) for k in KLASY_5]).astype(np.uint8)
    out = (licz.argmax(0) + 1).astype(np.uint8); out[licz.max(0) == 0] = 0
    return out

def k5_z_dynamic_world():
    r0, r1 = NZ['lata_dw']; m1_, m2_ = NZ['miesiace_dw']
    def img_dw(r):
        d1, d2 = _daty(r, m1_, m2_)
        kol = ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1').filterBounds(GEOM).filterDate(d1, d2)
        return kol.select('label').mode().add(1).unmask(0).toUint8().rename(f'dw_{r}')
    zad = [{'img': img_dw(r), 'pasma': [f'dw_{r}'], 'siatka': SIATKADW, 'nazwa': f'dw_{r}_{SDW}m', 'typ': np.uint8} for r in (r0, r1)]
    wyn, bl = pobierz_wiele(zad, 'Dynamic World')
    BLEDY_POBIERANIA.update(bl)
    if any(wyn.get(z['nazwa']) is None for z in zad):
        raise RuntimeError('nie pobrano map Dynamic World: ' + '; '.join(f'{k}: {v}' for k, v in bl.items()))
    for r in (r0, r1):
        DW[r] = wyn[f'dw_{r}_{SDW}m'][f'dw_{r}']
    return {r: klasa5_z_dw(DW[r]) for r in (r0, r1)}

if SP_['wlacz']:
    try:
        zr = NZ['zrodlo_zmian']
        sciezka_rf = NZ['rf5_geotiff'] or os.path.join(DIR_RAST, f'{NAZWA}_rf5_epoki.tif')
        if zr in ('auto', 'rf_geotiff'):
            if os.path.exists(sciezka_rf):
                try:
                    K5 = k5_z_rf_geotiff(sciezka_rf); ZRODLO_K5 = 'mapy RF 5 klas (Landsat), notatnik główny'
                except Exception as _e:
                    UWAGI.append(f'Mapy RF z pliku {sciezka_rf} nie zostały użyte ({_e}); porównanie na Dynamic World.')
                    print('Mapy RF niedostępne:', _e)
            elif zr == 'rf_geotiff':
                UWAGI.append(f'Brak pliku {sciezka_rf}; porównanie na Dynamic World.')
        if not K5:
            K5 = k5_z_dynamic_world(); ZRODLO_K5 = 'Dynamic World 10 m (moda etykiet), agregacja do 30 m'
        EPOKI = sorted(K5)
        print(f'Pokrycie terenu do porównania: {ZRODLO_K5}; epoki {EPOKI[0]} i {EPOKI[-1]}')
        if DW and PB['geotiff']:
            _zapisz_tif('dw_epoki_natura', [(f'dw_{r} (kod etykiety DW + 1; 0 = brak)', DW[r]) for r in sorted(DW)], SIATKADW, 'uint8', 0,
                        opis='Dynamic World: moda etykiet z sezonu ' + f"{NZ['miesiace_dw'][0]}–{NZ['miesiace_dw'][1]}")
            _zapisz_tif('pokrycie_5_klas_epoki_dw', [(f'dw5_{r} (1 zabudowa, 2 las, 3 woda, 4 trawy i krzewy, 5 uprawy)', K5[r]) for r in EPOKI], SIATKA30, 'uint8', 0,
                        opis='pokrycie terenu 5 klas z Dynamic World, 30 m')
    except Exception as _e:
        blad_modulu('Pokrycie terenu do porównania z Natura 2000', _e)

# ---- manifest pobranych plików ----
if PLIKI:
    tabela('pobieranie_manifest', pd.DataFrame(PLIKI))
if BLEDY_POBIERANIA:
    tabela('pobieranie_bledy', pd.DataFrame([{'Obraz': k, 'Błąd': v} for k, v in BLEDY_POBIERANIA.items()]))
    UWAGI.append(f'Nie pobrano {len(BLEDY_POBIERANIA)} obrazów (tabela pobieranie_bledy); uruchom komórkę ponownie: pobrane wcześniej obrazy są w pamięci podręcznej.')
if PB['zip'] and PLIKI:
    import shutil
    print('Archiwum ZIP:', shutil.make_archive(os.path.join(KATALOG, f'{NAZWA}_rastry'), 'zip', DIR_RAST))
print(f'Pobrane warstwy: VIIRS roczne {len(ALAN)}, miesięczne {len(ALAN_M)}, gHM {"tak" if HM is not None else "nie"}, Natura 2000 {"tak" if NAT is not None else "nie"}, tło S2 {"tak" if TLO is not None else "nie"}')

# %% [markdown]
# ## 6. Presje zewnętrzne: sztuczne światło nocą, modyfikacja przez człowieka i obszary Natura 2000
#
# **Co liczymy.** (1) Sztuczne światło nocą (ALAN) z miesięcznych kompozytów VIIRS DNB z korektą światła rozproszonego (radiancja, mediana roczna miesięcy z obserwacjami): średnia, mediana i suma radiancji w AOI (i jego częściach, gdy ustawiono podział) oraz w pierścieniu (suma jak w ocenie polskich parków, Ściężor i in. 2025), trend roczny; (2) globalny wskaźnik modyfikacji przez człowieka (gHM, stan około 2016) w strefach; (3) obszary Natura 2000 (siedliskowe SOO i ptasie OSO z bazy WDPA) w AOI i pierścieniu oraz porównanie zmian (nowa zabudowa, ubytek i przyrost lasu) wewnątrz i na zewnątrz sieci Natura 2000.
#
# **Co oznacza wynik.** Rosnące światło przy granicy to presja na gatunki nocne i zaburzenie rytmów dobowych; różnica zmian w Natura 2000 i poza nią to opis, nie efekt przyczynowy ochrony.
#
# **Ograniczenia.** VIIRS (około 500 m) nie rozróżnia pojedynczych źródeł i nie widzi światła niebieskiego LED; latem w Polsce brakuje części miesięcy (krótkie noce, światło rozproszone); gHM to jeden stan, nie szereg; granice WDPA mogą odbiegać od rejestrów krajowych (dla Polski: GDOŚ); obszary Natura 2000 istnieją tylko w UE, więc poza nią tabele Natura 2000 będą puste. Porównanie zmian w Natura 2000 opiera się na mapach wskazanych w ustawieniach (Dynamic World albo RF z notatnika głównego); kolumn o jakości siedlisk i zaburzeniach lasu z notatnika głównego tu nie ma, bo wymagają jego innych sekcji.
#
# ### 6.1 Sztuczne światło nocą (VIIRS DNB)

# %%
# ======== 1) SZTUCZNE ŚWIATŁO NOCĄ (VIIRS DNB): tabele, trend, ryciny i animacja ========
KOLORY_STREF = ['#7a0177', '#1b7837', '#bf812d', '#252525', '#2c7bb6']
KOL_SR, KOL_MED, KOL_SUMA = 'Średnia radiancja [nW/cm²/sr]', 'Mediana [nW/cm²/sr]', 'Suma radiancji pikseli 480 m w strefie [nW/cm²/sr]'
try:
    if SP_['wlacz'] and ALAN:
        w = []
        for r in sorted(ALAN):
            a = ALAN[r]
            for sn, sm in STR_P:
                v = a[sm & np.isfinite(a)]
                if v.size:
                    w.append({'Rok': r, 'Strefa': sn, KOL_SR: round(float(v.mean()), 3), KOL_MED: round(float(np.median(v)), 3),
                              f'Suma radiancji pikseli {f16 * S30} m w strefie [nW/cm²/sr]': round(float(v.sum()), 1),           # miara jak w ocenie parków Polski (Ściężor i in. 2025)
                              **{f'Powierzchnia > {p:g} nW/cm²/sr (próg umowny) [%]': round(float((v > p).mean() * 100), 1) for p in SP_['progi_radiancji']}})
        if w:
            t = tabela('alan_viirs', pd.DataFrame(w))
            lata_a = sorted(ALAN); w2 = []
            for sn, _ in STR_P:
                d_ = t[t.Strefa == sn]
                if len(d_) >= 5:
                    nach, z_, p_ = trend_sen_mk(d_[KOL_SR].to_numpy(np.float32)[:, None, None], d_.Rok.tolist(), min_lat=5)
                    w2.append({'Strefa': sn, 'Okres': f'{d_.Rok.min()}–{d_.Rok.max()}', 'Trend średniej radiancji [nW/cm²/sr na rok]': round(float(nach[0, 0]), 4),
                               'Zmiana względna [% na rok]': round(float(nach[0, 0] / d_[KOL_SR].mean() * 100), 2), 'p (Mann–Kendall)': round(float(p_[0, 0]), 4)})
            if w2:
                tabela('alan_viirs_trend', pd.DataFrame(w2))
            else:
                UWAGI.append('Trend światła nocą: mniej niż 5 lat danych w strefie; tabela trendów pominięta.')
            vmax_ = max(np.nanpercentile(ALAN[lata_a[-1]], 99), 1)
            fig, axs = plt.subplots(1, 4, figsize=(22, 5.6)); lg = matplotlib.colors.LogNorm(0.1, vmax_)
            mapa(axs[0], np.clip(ALAN[lata_a[0]], 0.1, None), 'magma', tytul=f'Światło nocą {lata_a[0]} (VIIRS)', ext=EXT_P, etykieta='radiancja [nW/cm²/sr]', norm=lg)
            mapa(axs[1], np.clip(ALAN[lata_a[-1]], 0.1, None), 'magma', tytul=f'Światło nocą {lata_a[-1]} (VIIRS)', ext=EXT_P, etykieta='radiancja [nW/cm²/sr]', norm=lg)
            mapa(axs[2], ALAN[lata_a[-1]] - ALAN[lata_a[0]], 'RdBu_r', -2, 2, f'Zmiana {lata_a[0]}–{lata_a[-1]}', EXT_P, 'Δ radiancji [nW/cm²/sr]')
            for k_, (sn, _) in enumerate(STR_P):                                     # wszystkie strefy raportowania
                d_ = t[t.Strefa == sn]
                axs[3].plot(d_.Rok, d_[KOL_SR], ('-', '--', ':', '-.', '-')[k_ % 5], marker='o', ms=3, color=KOLORY_STREF[k_ % len(KOLORY_STREF)], label=sn)
            axs[3].set_ylabel('Średnia radiancja [nW/cm²/sr]'); axs[3].set_xlabel('Rok'); axs[3].grid(alpha=0.3); axs[3].legend(frameon=False, fontsize=8)
            axs[3].set_title('Sztuczne światło nocą w strefach analizy', fontsize=10)
            fig.suptitle(f'{NAZWA}: sztuczne światło nocą (VIIRS DNB, mediana roczna miesięcznych kompozytów, siatka {f16 * S30} m)', fontsize=11)
            fig.tight_layout(); RYCINY.append(zapisz(fig, 'alan_viirs'))
            anim_mapy(lata_a, 'animacja_alan_viirs', lambda fig, ax, r: mapa(ax, np.clip(ALAN[r], 0.1, None), 'magma', tytul=f'{NAZWA}: sztuczne światło nocą {r}', ext=EXT_P,
                                                                           etykieta='radiancja [nW/cm²/sr]', norm=matplotlib.colors.LogNorm(0.1, vmax_)), czas_ms=700)
            ZRODLA.append(('alan_', f'VIIRS DNB miesięczne kompozyty ({SP_["viirs"]}), mediana roczna, siatka {f16 * S30} m'))
    elif SP_['wlacz']:
        UWAGI.append('Światło nocą: brak pobranych danych VIIRS (sekcja 5).')
except Exception as _e:
    blad_modulu('Sztuczne światło nocą (VIIRS), wyniki roczne', _e)

# ---- wyniki miesięczne: sezonowość i kompletność danych (rycina, tabela, animacja z wszystkich miesięcy) ----
try:
    if SP_['wlacz'] and ALAN_M:
        klucze = sorted(ALAN_M); w = []
        for (r, m_) in klucze:
            a, cf = ALAN_M[(r, m_)], ALAN_CF[(r, m_)]
            for sn, sm in STR_P:
                v = a[sm & np.isfinite(a)]
                w.append({'Rok': r, 'Miesiąc': m_, 'Strefa': sn, 'Średnia radiancja [nW/cm²/sr]': round(float(v.mean()), 3) if v.size else np.nan,
                          'Udział pikseli z obserwacją [%]': round(float((cf[sm] > 0).mean() * 100), 1), 'Średnia liczba obserwacji': round(float(cf[sm].mean()), 1)})
        tm = tabela('alan_viirs_miesieczne', pd.DataFrame(w), pokaz=False)
        lata_m = sorted({r for r, _ in klucze})
        sn0 = STR_P[0][0]; d0 = tm[tm.Strefa == sn0]
        H_rad = d0.pivot(index='Rok', columns='Miesiąc', values='Średnia radiancja [nW/cm²/sr]').reindex(index=lata_m, columns=range(1, 13))
        H_cov = d0.pivot(index='Rok', columns='Miesiąc', values='Udział pikseli z obserwacją [%]').reindex(index=lata_m, columns=range(1, 13))
        fig, axs = plt.subplots(1, 2, figsize=(14, 0.45 * len(lata_m) + 2.2))
        for ax_, H_, tyt, et, cm in ((axs[0], H_rad, f'Średnia radiancja, strefa {sn0}', 'nW/cm²/sr', 'magma'), (axs[1], H_cov, f'Udział pikseli z obserwacją, strefa {sn0}', '%', 'Blues')):
            im = ax_.imshow(H_.to_numpy(float), aspect='auto', cmap=cm, vmin=0, vmax=100 if cm == 'Blues' else None)
            ax_.set_xticks(range(12)); ax_.set_xticklabels(range(1, 13)); ax_.set_yticks(range(len(lata_m))); ax_.set_yticklabels(lata_m)
            ax_.set_xlabel('Miesiąc'); ax_.set_title(tyt, fontsize=10); plt.colorbar(im, ax=ax_, fraction=0.04, pad=0.02).set_label(et, fontsize=8)
        fig.suptitle(f'{NAZWA}: miesięczne kompozyty VIIRS: sezonowość i kompletność danych (białe pola: brak kompozytu lub obserwacji)', fontsize=11)
        fig.tight_layout(); RYCINY.append(zapisz(fig, 'alan_viirs_miesieczne'))
        if U['animacje']['miesieczna']:
            vmax_m = max(np.nanpercentile(np.concatenate([ALAN_M[k][np.isfinite(ALAN_M[k])] for k in klucze[-12:]]), 99), 1)
            anim_mapy(klucze, 'animacja_alan_viirs_miesieczna', lambda fig, ax, k: mapa(ax, np.clip(ALAN_M[k], 0.1, None), 'magma', tytul=f'{NAZWA}: światło nocą {k[0]}-{k[1]:02d}', ext=EXT_P,
                                                                                      etykieta='radiancja [nW/cm²/sr]', norm=matplotlib.colors.LogNorm(0.1, vmax_m)),
                      czas_ms=250, pokaz=False)
except Exception as _e:
    blad_modulu('Sztuczne światło nocą (VIIRS), wyniki miesięczne', _e)

# %% [markdown]
# ### 6.2 Globalna modyfikacja przez człowieka (gHM)

# %%
# ======== 2) GLOBALNA MODYFIKACJA PRZEZ CZŁOWIEKA (gHM) ========
try:
    if SP_['wlacz'] and HM is not None:
        wg = [{'Strefa': sn, 'Średni gHM (0–1)': round(float(np.nanmean(HM[sm])), 3), 'Udział gHM > 0,4 (silna modyfikacja) [%]': round(float((HM[sm] > 0.4).mean() * 100), 1)}
              for sn, sm in STR_P if np.isfinite(HM[sm]).any()]
        tg = tabela('ghm_modyfikacja', pd.DataFrame(wg))
        fig, axs = plt.subplots(1, 2, figsize=(14, 5.6), gridspec_kw={'width_ratios': [1.25, 1]})
        mapa(axs[0], HM, 'YlOrRd', 0, 1, 'Globalna modyfikacja przez człowieka (gHM, stan ok. 2016)', EXT_P, 'gHM (0–1)')
        if len(tg):
            axs[1].bar(tg['Strefa'], tg['Średni gHM (0–1)'], color=[KOLORY_STREF[i % len(KOLORY_STREF)] for i in range(len(tg))])
            axs[1].axhline(0.4, color='#d7191c', lw=1, ls='--'); axs[1].text(-0.45, 0.41, 'próg silnej modyfikacji 0,4', ha='left', va='bottom', fontsize=8, color='#d7191c')
            axs[1].set_ylim(0, 1); axs[1].set_ylabel('Średni gHM (0–1)'); axs[1].set_title('Średnia modyfikacja w strefach analizy', fontsize=10); axs[1].grid(axis='y', alpha=0.3)
        fig.suptitle(f'{NAZWA}: modyfikacja przez człowieka (gHM, siatka {f16 * S30} m)', fontsize=11)
        fig.tight_layout(); RYCINY.append(zapisz(fig, 'ghm_modyfikacja'))
        ZRODLA.append(('ghm_', f'Global Human Modification ({SP_["ghm"]}), siatka {f16 * S30} m'))
    elif SP_['wlacz']:
        UWAGI.append('gHM: brak pobranych danych (sekcja 5).')
except Exception as _e:
    blad_modulu('Globalna modyfikacja przez człowieka (gHM)', _e)

# %% [markdown]
# ### 6.3 Obszary Natura 2000 i zmiany pokrycia terenu

# %%
# ======== 3) NATURA 2000: udział w strefach, mapa i porównanie zmian pokrycia terenu w sieci i poza nią ========
try:
    if SP_['wlacz'] and NAT is not None:
        w = []
        for sn, sm in STREFY_RAP:
            w.append({'Strefa': sn, 'Powierzchnia strefy [ha]': round(float(sm.sum() * POW_PIX30_HA), 1),
                      'Natura 2000 siedliskowa (SOO) [% strefy]': round(float((N2['sac'][sm] > 0).mean() * 100), 1), 'Natura 2000 ptasia (OSO) [% strefy]': round(float((N2['spa'][sm] > 0).mean() * 100), 1),
                      'Natura 2000 łącznie [% strefy]': round(float(NAT[sm].mean() * 100), 1)})
        tabela('natura2000_udzial', pd.DataFrame(w))
        # zmiany pokrycia terenu wewnątrz i na zewnątrz sieci Natura 2000 (opis, nie efekt przyczynowy ochrony)
        Z_ = None; e0 = e1 = None
        if K5 and len(EPOKI) >= 2 and NAT.any() and (~NAT & DOM_).any():
            e0, e1 = EPOKI[0], EPOKI[-1]; w = []
            for sn, sm in STREFY_RAP:
                for nn, mm in (('w Natura 2000', NAT), ('poza Natura 2000', ~NAT)):
                    m_ = sm & mm & (K5[e0] > 0) & (K5[e1] > 0)
                    if m_.sum() < NZ['min_pikseli_grupy']:
                        continue
                    las0 = (K5[e0] == 2) & m_; nz0 = (K5[e0] != 1) & m_
                    w.append({'Strefa': sn, 'Obszar': nn, 'Powierzchnia [ha]': round(float(m_.sum() * POW_PIX30_HA), 1),
                              f'Nowa zabudowa {e0}–{e1} [% terenu niezabudowanego]': round(float(((K5[e1] == 1) & nz0).sum() / max(nz0.sum(), 1) * 100), 2),
                              f'Ubytek lasu {e0}–{e1} [% lasu]': round(float(((K5[e1] != 2) & las0).sum() / max(las0.sum(), 1) * 100), 2),
                              f'Przyrost lasu {e0}–{e1} [% powierzchni]': round(float(((K5[e1] == 2) & (K5[e0] != 2) & m_).sum() / m_.sum() * 100), 2)})
            if w:
                tabela('natura2000_zmiany', pd.DataFrame(w))
            Z_ = mapa_zmian(K5[e0], K5[e1])
        elif K5:
            UWAGI.append('Natura 2000: w ramce analizy nie ma obszarów sieci Natura 2000 (WDPA zawiera je tylko w UE); porównanie zmian pominięte.' if not NAT.any()
                         else 'Natura 2000: cała ramka analizy leży w sieci Natura 2000; porównanie zmian pominięte.')

        # mapa: formy ochrony (WDPA), a gdy są mapy pokrycia, także zmiany pokrycia terenu
        fig, ax = plt.subplots(figsize=(9, 9 * H30 / W30 + 0.8))
        tyt = f'{NAZWA}: obszary Natura 2000 (WDPA)' + (f' i zmiany pokrycia {e0}–{e1}' if Z_ is not None else '')
        panel(ax, None, None, tyt)
        ax.imshow(np.ma.masked_equal(NAT.astype(np.uint8), 0), cmap=ListedColormap(['#e7298a']), vmin=0, vmax=1, extent=EXTENT, interpolation='nearest', alpha=0.15)
        if Z_ is not None:
            ax.imshow(np.ma.masked_equal(Z_, 0), cmap=ListedColormap(['#00000000'] + [c for _, c in KAT_ZMIAN.values()]), vmin=0, vmax=len(KAT_ZMIAN), extent=EXTENT, interpolation='nearest', alpha=0.9)
        if FORMY_OCHRONY is not None:
            h_ = warstwy_ochrony(ax, legenda=False)                                       # zakres pracy, rezerwaty, Natura 2000 (wektory WDPA)
        else:
            ax.contour(N2['sac'] > 0, levels=[0.5], colors='#e7298a', linewidths=1.4, linestyles='--', extent=EXTENT, origin='upper')
            ax.contour(N2['spa'] > 0, levels=[0.5], colors='#f768a1', linewidths=1.4, linestyles=':', extent=EXTENT, origin='upper')
            h_ = [plt.Line2D([], [], color='#e7298a', ls='--', label='Natura 2000 siedliskowa (SOO)'), plt.Line2D([], [], color='#f768a1', ls=':', label='Natura 2000 ptasia (OSO)')]
        if Z_ is not None:
            h_ += [Patch(color=c, label=n) for n, c in KAT_ZMIAN.values()]
        ax.legend(handles=h_, loc='lower center', bbox_to_anchor=(0.5, -0.2), ncol=3, frameon=False, fontsize=7); skala_mapy(ax)
        fig.tight_layout(); RYCINY.append(zapisz(fig, 'natura2000_zmiany' if Z_ is not None else 'natura2000_mapa'))

        # wykres: wskaźniki zmian w Natura 2000 i poza nią w strefach
        if 'natura2000_zmiany' in TABELE and len(TABELE['natura2000_zmiany']):
            tz = TABELE['natura2000_zmiany']; kol = [c for c in tz.columns if c.startswith(('Nowa zabudowa', 'Ubytek lasu', 'Przyrost lasu'))]
            kol_ob = [o for o in ('w Natura 2000', 'poza Natura 2000') if o in set(tz['Obszar'])]
            fig, axs = plt.subplots(1, len(kol), figsize=(5.2 * len(kol), 4.4), squeeze=False)
            for ax_, c in zip(axs.ravel(), kol):
                p = tz.pivot(index='Strefa', columns='Obszar', values=c).reindex(index=[n for n, _ in STREFY_RAP if n in set(tz['Strefa'])], columns=kol_ob)
                p.plot.bar(ax=ax_, color=['#e7298a', '#999999'][:len(kol_ob)], rot=20, width=0.8); ax_.set_xlabel(''); ax_.set_title(c, fontsize=9); ax_.grid(axis='y', alpha=0.3)
                ax_.legend(frameon=False, fontsize=8)
            fig.suptitle(f'{NAZWA}: zmiany pokrycia terenu w Natura 2000 i poza nią (opis, nie efekt przyczynowy ochrony; źródło: {ZRODLO_K5})', fontsize=10)
            fig.tight_layout(); RYCINY.append(zapisz(fig, 'natura2000_zmiany_wykres'))
        ZRODLA.append(('natura2000', f'WDPA ({SP_["wdpa"]}): obszary Natura 2000, rasteryzacja 30 m; pokrycie terenu: {ZRODLO_K5}'))
    elif SP_['wlacz']:
        UWAGI.append('Natura 2000: brak pobranych danych (sekcja 5).')
except Exception as _e:
    blad_modulu('Obszary Natura 2000', _e)

# %% [markdown]
# ## 7. Zapis wyników
#
# Parametry biegu (JSON), opis źródeł i ograniczeń (Markdown) oraz lista tabel, rycin i plików GeoTIFF w folderze wyników.

# %%
# ======== ZAPIS WYNIKÓW: parametry biegu, źródła i metody, lista plików ========
UWAGI_DEDUP = list(dict.fromkeys(UWAGI))
raport = {'nazwa': NAZWA, 'data_biegu': datetime.datetime.now().isoformat(timespec='seconds'), 'plik_aoi': U['aoi_gpkg'], 'uklad': CRS,
          'aoi_km2': round(aoi.area / 1e6, 3), 'strefy_raportowania': [n for n, _ in STREFY_RAP], 'siatka_30m': SIATKA30, 'siatka_viirs_gHM': SIATKA_P,
          'lata_viirs': sorted(ALAN), 'miesiace_viirs': len(ALAN_M), 'zrodlo_pokrycia_terenu': ZRODLO_K5, 'epoki_pokrycia': EPOKI,
          'ustawienia': {k: v for k, v in U.items() if k != 'aoi_gpkg'}, 'uwagi': UWAGI_DEDUP, 'bledy_modulow': BLEDY_MODULOW, 'bledy_pobierania': BLEDY_POBIERANIA,
          'pliki': {os.path.basename(d): sorted(os.listdir(d)) for d in (DIR_TAB, DIR_RYC, DIR_ANIM, DIR_RAST, DIR_WEKT)},
          'wersje': {'earthengine-api': ee.__version__, 'numpy': np.__version__, 'pandas': pd.__version__, 'geopandas': gpd.__version__}}
with open(os.path.join(DIR_RAP, f'{NAZWA}_parametry_biegu.json'), 'w', encoding='utf-8') as f:
    json.dump(raport, f, ensure_ascii=False, indent=1, default=str)

OPIS = [f'# {NAZWA}: presje zewnętrzne (światło nocą, modyfikacja przez człowieka, Natura 2000)', '',
        f'Data biegu: {raport["data_biegu"]}. Plik AOI: {U["aoi_gpkg"]}. Układ: {CRS}.', '',
        '## Źródła danych', '',
        f'- VIIRS DNB, miesięczne kompozyty z korektą światła rozproszonego: `{SP_["viirs"]}` (pasma avg_rad, cf_cvg); mediana roczna miesięcy z obserwacjami; siatka {f16 * S30} m.',
        f'- Global Human Modification: `{SP_["ghm"]}` (jeden stan, ok. 2016).',
        f'- Obszary chronione (Natura 2000: SOO i OSO, rezerwaty): `{SP_["wdpa"]}`.',
        f'- Pokrycie terenu do porównania w Natura 2000 i poza nią: {ZRODLO_K5}.',
        f'- Tło map: Sentinel-2 {TL["rok"]} (`COPERNICUS/S2_SR_HARMONIZED` z maską Cloud Score+).', '',
        '## Ograniczenia', '',
        '- VIIRS (około 500 m) nie rozróżnia pojedynczych źródeł i nie widzi światła niebieskiego LED; latem w Polsce brakuje części miesięcy (krótkie noce, światło rozproszone).',
        '- gHM to jeden stan, nie szereg czasowy; granice WDPA mogą odbiegać od rejestru krajowego (GDOŚ).',
        '- Różnica zmian w Natura 2000 i poza nią jest opisem, nie efektem przyczynowym ochrony.', '']
if UWAGI_DEDUP:
    OPIS += ['## Uwagi z biegu', ''] + [f'- {u}' for u in UWAGI_DEDUP] + ['']
OPIS += ['## Pliki', ''] + [f'- {k}: {len(v)} plików' for k, v in raport['pliki'].items()]
with open(os.path.join(DIR_RAP, f'{NAZWA}_presje_zrodla_i_metody.md'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(OPIS))

print('Tabele:', *sorted(TABELE), sep='\n  ')
print('Ryciny:', *[os.path.basename(p) for p in RYCINY], sep='\n  ')
print('GeoTIFF:', *[x['Plik'] for x in PLIKI], sep='\n  ')
if BLEDY_MODULOW:
    print('\nBŁĘDY MODUŁÓW:'); display(pd.DataFrame(BLEDY_MODULOW))
if UWAGI_DEDUP:
    print('\nUWAGI:', *UWAGI_DEDUP, sep='\n  - ')
print('\nWyniki w:', KATALOG)

# %%
# koniec: kod wyjścia 2, gdy któryś moduł przerwał się błędem (raport i pozostałe wyniki są zapisane)
if BLEDY_MODULOW:
    raise SystemExit(2)
