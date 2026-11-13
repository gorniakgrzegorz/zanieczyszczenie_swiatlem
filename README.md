# zanieczyszczenie_swiatlem

Presje zewnętrzne na dowolny obszar z pliku GPKG: sztuczne światło nocą, modyfikacja przez człowieka i obszary Natura 2000.

**Strona z opisem metody, podstawami naukowymi i przewodnikiem krok po kroku:** https://gorniakgrzegorz.github.io/zanieczyszczenie_swiatlem/

**Nigdy nie programowałeś?** Zacznij od [przewodnika krok po kroku](https://gorniakgrzegorz.github.io/zanieczyszczenie_swiatlem/#przewodnik): konto Google, własny projekt Earth Engine, plik z obszarem, Colab.

Dwie wersje tego samego kodu: notatnik `zanieczyszczenie_swiatlem.ipynb` (Colab) i skrypt `zanieczyszczenie_swiatlem.py` (terminal).

Notatnik `zanieczyszczenie_swiatlem.ipynb` (Google Colab, Google Earth Engine) to samodzielna wersja sekcji 35 notatnika „Pokrycie terenu AOI RF DW”: sztuczne światło nocą (VIIRS DNB), globalna modyfikacja przez człowieka (gHM) i obszary Natura 2000.

## Użycie

1. Otwórz notatnik w Colabie i w komórce **1. Ustawienia** wskaż zakres pracy, czyli plik GPKG (`aoi_gpkg`), folder wyników (`folder_wynikow`) i projekt GEE (`projekt_gee`). Zakresem jest suma wszystkich obiektów wskazanej warstwy: dowolny obszar (park, gmina, zlewnia, pole badań, także kilka rozłącznych obiektów), niekoniecznie park krajobrazowy. Układ metryczny wybierany jest automatycznie (PL-1992 w Polsce, w innych miejscach strefa UTM).
   Opcjonalnie można podzielić zakres na dwie części (np. park i otulina) przez `aoi_kolumna_typu`; domyślnie podziału nie ma.
2. Uruchom wszystkie komórki. Wyniki trafiają do `<folder_wynikow>/<nazwa AOI>/`: `01_tabele`, `02_ryciny`, `03_animacje`, `04_rastry`, `05_wektory`, `06_raport`.

### Skrypt Python (bez notatnika)

Trzy pola wymagane są na górze skryptu (sekcja `USTAWIENIA DO WPISANIA`): `PROJEKT_GEE` (albo zmienna środowiskowa `GEE_PROJECT`), `PLIK_GPKG`, `FOLDER_WYNIKOW`. Można je też podać w wierszu poleceń. Przed pobieraniem skrypt sprawdza ustawienia, a `--tylko-sprawdz` kończy po sprawdzeniu ustawień i połączenia z Earth Engine.

```bash
pip install -r requirements.txt
earthengine authenticate
python zanieczyszczenie_swiatlem.py --gpkg obszar.gpkg --out wyniki --projekt MOJ_PROJEKT_GEE --tylko-sprawdz
python zanieczyszczenie_swiatlem.py --gpkg obszar.gpkg --out wyniki --projekt MOJ_PROJEKT_GEE
python zanieczyszczenie_swiatlem.py --gpkg obszar.gpkg --out wyniki --projekt MOJ_PROJEKT_GEE --ustaw animacje.miesieczna=false --ustaw presje.skala_m=960
```

Opcja `--ustaw klucz.podklucz=WARTOŚĆ` (JSON) nadpisuje dowolne ustawienie ze słownika `USTAWIENIA`. Kod wyjścia 2 oznacza błąd któregoś modułu (raport i reszta wyników są zapisane).

## Co robi

- **Masowo pobiera** dla obszaru z GPKG: roczne mediany VIIRS, wszystkie miesięczne kompozyty VIIRS (radiancja i liczba obserwacji), gHM, raster Natura 2000 (WDPA), tło Sentinel-2, mapy Dynamic World. Wszystko zapisuje jako GeoTIFF (`04_rastry`) i w pamięci podręcznej `_cache` (przerwane pobieranie wznawia się bez ponownych zapytań do GEE).
- Liczy tabele (średnia, mediana i suma radiancji w AOI, w jego częściach przy ustawionym podziale i w pierścieniu, trend Theila-Sena z testem Manna-Kendalla, gHM, udział Natura 2000, zmiany pokrycia terenu w sieci Natura 2000 i poza nią).
- Rysuje ryciny i animacje (roczna i miesięczna animacja światła nocą).
- Zmiany pokrycia terenu: z map RF 5 klas notatnika głównego (`<nazwa>_rf5_epoki.tif`, gdy plik istnieje i siatka się zgadza), w przeciwnym razie z Dynamic World.

## Testy

Katalog `testy/` zawiera atrapę modułu `ee` z syntetycznymi danymi i skrypt uruchamiający wszystkie komórki bez dostępu do GEE:

```bash
pip install geopandas rasterio pyogrio shapely scipy matplotlib imageio tqdm ipython
python testy/make_aoi.py /tmp/t/AOI.gpkg atrybut
python testy/run_nb.py zanieczyszczenie_swiatlem.ipynb /tmp/t szybki
# skrypt z atrapą ee (PYTHONPATH wskazuje atrapę)
PYTHONPATH=testy/stub python zanieczyszczenie_swiatlem.py --gpkg /tmp/t/AOI.gpkg --out /tmp/t/Wyniki --projekt test --ustaw animacje.miesieczna=false
```

Test sprawdza przepływ danych, kafle, pamięć podręczną, zapis GeoTIFF, tabele, ryciny i animacje. Nie zastępuje uruchomienia na prawdziwym GEE. Obszary Natura 2000 istnieją tylko w UE, więc dla obszarów spoza UE tabele Natura 2000 są puste (notatnik zapisuje o tym uwagę i liczy dalej).


Licencja kodu: MIT (plik `LICENSE`). Dane źródłowe (VIIRS, gHM, WDPA, Sentinel-2, Dynamic World) podlegają licencjom dostawców. Cytowanie: `CITATION.cff`; archiwum wydania v1.0.0 w Zenodo: https://doi.org/10.5281/zenodo.24186500
