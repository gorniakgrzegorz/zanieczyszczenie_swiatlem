# Zanieczyszczenie światłem i presje zewnętrzne na obszar z pliku GPKG

Notatnik `Presje_zewnetrzne_AOI.ipynb` (Google Colab, Google Earth Engine) to samodzielna wersja sekcji 35 notatnika „Pokrycie terenu AOI RF DW”: sztuczne światło nocą (VIIRS DNB), globalna modyfikacja przez człowieka (gHM) i obszary Natura 2000.

## Użycie

1. Otwórz notatnik w Colabie i w komórce **1. Ustawienia** wskaż plik GPKG (`aoi_gpkg`), folder wyników (`folder_wynikow`) i projekt GEE (`projekt_gee`).
2. Uruchom wszystkie komórki. Wyniki trafiają do `<folder_wynikow>/<nazwa AOI>/`: `01_tabele`, `02_ryciny`, `03_animacje`, `04_rastry`, `05_wektory`, `06_raport`.

## Co robi

- **Masowo pobiera** dla obszaru z GPKG: roczne mediany VIIRS, wszystkie miesięczne kompozyty VIIRS (radiancja i liczba obserwacji), gHM, raster Natura 2000 (WDPA), tło Sentinel-2, mapy Dynamic World. Wszystko zapisuje jako GeoTIFF (`04_rastry`) i w pamięci podręcznej `_cache` (przerwane pobieranie wznawia się bez ponownych zapytań do GEE).
- Liczy tabele (średnia, mediana i suma radiancji w AOI, parku, otulinie i pierścieniu, trend Theila-Sena z testem Manna-Kendalla, gHM, udział Natura 2000, zmiany pokrycia terenu w sieci Natura 2000 i poza nią).
- Rysuje ryciny i animacje (roczna i miesięczna animacja światła nocą).
- Zmiany pokrycia terenu: z map RF 5 klas notatnika głównego (`<nazwa>_rf5_epoki.tif`, gdy plik istnieje i siatka się zgadza), w przeciwnym razie z Dynamic World.

## Testy

Katalog `testy/` zawiera atrapę modułu `ee` z syntetycznymi danymi i skrypt uruchamiający wszystkie komórki bez dostępu do GEE:

```bash
pip install geopandas rasterio pyogrio shapely scipy matplotlib imageio tqdm ipython
python testy/make_aoi.py /tmp/t/AOI.gpkg atrybut
python testy/run_nb.py Presje_zewnetrzne_AOI.ipynb /tmp/t szybki
```

Test sprawdza przepływ danych, kafle, pamięć podręczną, zapis GeoTIFF, tabele, ryciny i animacje. Nie zastępuje uruchomienia na prawdziwym GEE.
