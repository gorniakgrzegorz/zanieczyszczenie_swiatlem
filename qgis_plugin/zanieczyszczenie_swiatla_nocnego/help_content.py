# -*- coding: utf-8 -*-
"""Treść pomocy w dwóch językach (HTML dla QTextBrowser) / Help content in two languages (HTML for QTextBrowser).

Znaczniki do podmiany w oknie: @@LIBS@@ (folder bibliotek), @@CMD@@ (polecenie instalacji), @@VERSION@@.
"""

GEE_STEPS = {
'pl': """
<h3>Jak uzyskać dostęp do Google Earth Engine (jednorazowo, bezpłatnie do zastosowań niekomercyjnych)</h3>
<p>Wtyczka pobiera zdjęcia satelitarne z serwisu <b>Google Earth Engine</b>. Serwis wymaga konta Google i własnego <b>projektu</b>; jego <b>identyfikator</b> wpisujesz we wtyczce. Nie jest to hasło ani klucz: to krótki napis w rodzaju <code>swiatlo-nocne-123456</code>.
Według oficjalnej instrukcji Google dostęp wymaga projektu w Google Cloud, włączonego interfejsu Earth Engine API i zarejestrowania projektu; do użytku niekomercyjnego nie trzeba konfigurować płatności. Interfejsy Google się zmieniają, więc nazwy przycisków mogą się nieco różnić. Aktualna instrukcja: <a href="https://developers.google.com/earth-engine/guides/access">developers.google.com/earth-engine/guides/access</a>.</p>
<ol>
<li><b>Konto Google.</b> Zaloguj się (lub załóż konto) na <a href="https://accounts.google.com">accounts.google.com</a>. Używaj tego samego konta w całej procedurze.</li>
<li><b>Utwórz projekt.</b> Wejdź na <a href="https://console.cloud.google.com/projectcreate">console.cloud.google.com/projectcreate</a>, wpisz dowolną nazwę (np. <i>swiatlo-nocne</i>) i kliknij <i>Utwórz</i>. Google nada projektowi <b>identyfikator</b> (zwykle nazwa z dopisanym numerem), widoczny pod polem nazwy i na liście projektów u góry strony. Zapisz identyfikator, a nie samą nazwę.</li>
<li><b>Włącz Earth Engine API.</b> Wejdź na <a href="https://console.cloud.google.com/apis/library/earthengine.googleapis.com">stronę interfejsu Earth Engine API</a>, upewnij się, że u góry wybrany jest Twój projekt, i kliknij <i>Włącz</i> (<i>Enable</i>).</li>
<li><b>Zarejestruj projekt w Earth Engine.</b> Wejdź na <a href="https://console.cloud.google.com/earth-engine/configuration">console.cloud.google.com/earth-engine/configuration</a>. Do badań, nauki i innych zastosowań niekomercyjnych wypełnij krótką ankietę (kwalifikowalność jest weryfikowana). Zastosowania komercyjne mają osobne, płatne zasady; sprawdź je na stronie Google.</li>
<li><b>W QGIS</b>, na karcie <i>Dostęp do GEE</i>: (a) <i>Zainstaluj biblioteki</i> (jednorazowo, kilka minut, kilkaset MB, wymaga internetu); (b) <i>Zaloguj do Earth Engine</i>: otworzy się przeglądarka, wybierz to samo konto Google, zezwól na dostęp i zamknij kartę po komunikacie o powodzeniu; (c) wpisz <i>identyfikator projektu</i>; (d) kliknij <i>Testuj połączenie</i>. Gdy wszystkie cztery wskaźniki są zielone, możesz uruchamiać analizę.</li>
</ol>
<p>Hasła do konta Google nigdy nie wpisujesz we wtyczce: logowanie odbywa się w przeglądarce, a Earth Engine zapisuje token dostępu w Twoim profilu użytkownika (folder <code>.config/earthengine</code>).</p>
""",
'en': """
<h3>How to get access to Google Earth Engine (one-time, free for non-commercial use)</h3>
<p>The plugin downloads satellite imagery from <b>Google Earth Engine</b>. The service needs a Google account and your own <b>project</b>; you enter its <b>ID</b> in the plugin. It is neither a password nor a key: it is a short string such as <code>night-light-123456</code>.
According to Google's official instructions, access requires a Google Cloud project, the Earth Engine API enabled and the project registered; non-commercial use does not require billing setup. Google interfaces change, so button names may differ slightly. Current instructions: <a href="https://developers.google.com/earth-engine/guides/access">developers.google.com/earth-engine/guides/access</a>.</p>
<ol>
<li><b>Google account.</b> Sign in (or create an account) at <a href="https://accounts.google.com">accounts.google.com</a>. Use the same account throughout.</li>
<li><b>Create a project.</b> Go to <a href="https://console.cloud.google.com/projectcreate">console.cloud.google.com/projectcreate</a>, enter any name (e.g. <i>night-light</i>) and click <i>Create</i>. Google assigns the project an <b>ID</b> (usually the name with a number appended), shown under the name field and in the project list at the top of the page. Write down the ID, not just the name.</li>
<li><b>Enable the Earth Engine API.</b> Open the <a href="https://console.cloud.google.com/apis/library/earthengine.googleapis.com">Earth Engine API page</a>, make sure your project is selected at the top and click <i>Enable</i>.</li>
<li><b>Register the project for Earth Engine.</b> Go to <a href="https://console.cloud.google.com/earth-engine/configuration">console.cloud.google.com/earth-engine/configuration</a>. For research, education and other non-commercial use, fill in the short questionnaire (eligibility is verified). Commercial use has separate, paid terms; check them on Google's site.</li>
<li><b>In QGIS</b>, on the <i>GEE access</i> tab: (a) <i>Install libraries</i> (one-time, a few minutes, several hundred MB, needs internet); (b) <i>Log in to Earth Engine</i>: a browser opens, choose the same Google account, allow access and close the tab after the success message; (c) enter the <i>project ID</i>; (d) click <i>Test connection</i>. When all four indicators are green you can run the analysis.</li>
</ol>
<p>You never type your Google password into the plugin: sign-in happens in the browser and Earth Engine stores an access token in your user profile (folder <code>.config/earthengine</code>).</p>
""",
}

HELP = {
'pl': """
<h2>Zanieczyszczenie światłem nocnym (wersja @@VERSION@@)</h2>
<p>Wtyczka analizuje <b>sztuczne światło nocą</b> w dowolnym obszarze i jego otoczeniu na podstawie miesięcznych kompozytów satelity VIIRS DNB (kolekcja <code>NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG</code>, Google Earth Engine). Dla obszaru z warstwy QGIS lub pliku liczy jasność nocnego światła w obszarze i w pierścieniach wokół niego, trend w latach, sezonowość, rysuje mapy, tworzy animacje i zapisuje GeoTIFF-y, które od razu dodaje do projektu QGIS.</p>

<h3>Szybki start</h3>
<ol>
<li>Karta <i>Dostęp do GEE</i>: zrób jednorazowo kroki z instrukcji poniżej (konto, projekt, API, rejestracja), potem zainstaluj biblioteki, zaloguj się i przetestuj połączenie.</li>
<li>Karta <i>Analiza</i>: wybierz warstwę poligonową z projektu (albo plik), wpisz identyfikator projektu GEE, wskaż folder wyników i kliknij <i>Uruchom analizę</i>.</li>
<li>Poczekaj (czas zależy od wielkości obszaru, pierścienia i liczby lat; typowo od kilku do kilkudziesięciu minut). Postęp widać na pasku, szczegóły w karcie <i>Dziennik</i>. Przerwane pobieranie wznawia się: pobrane dane są w pamięci podręcznej w folderze wyników.</li>
<li>Karta <i>Wyniki</i>: warstwy są dodane do projektu, a tabele (CSV), ryciny (PNG), animacje (GIF) i raport otwierasz podwójnym kliknięciem.</li>
</ol>
<p>Za pierwszym razem wybierz <b>niewielki obszar</b> (np. gminę), żeby sprawdzić, że wszystko działa.</p>

@@GEE@@

<h3>Rozwiązywanie problemów</h3>
<table border="1" cellpadding="4" cellspacing="0">
<tr><th>Komunikat / objaw</th><th>Przyczyna i co zrobić</th></tr>
<tr><td>Wskaźnik „Biblioteki” czerwony, instalacja się nie udaje</td><td>Brak internetu, zapora lub serwer proxy, zbyt mało miejsca na dysku albo Python bez pip. Przeczytaj dziennik. Możesz zainstalować ręcznie: otwórz <i>OSGeo4W Shell</i> (Windows) lub terminal i wklej polecenie z przycisku <i>Kopiuj polecenie instalacji</i> (poniżej). Biblioteki trafiają do folderu <code>@@LIBS@@</code>.</td></tr>
<tr><td>„Nie znaleziono Pythona”</td><td>Na karcie <i>Analiza</i> w ustawieniach zaawansowanych wskaż plik <code>python</code> (wersja 3.9 lub nowsza, z pip).</td></tr>
<tr><td>Błąd: nie zalogowano / „authorize”</td><td>Kliknij <i>Zaloguj do Earth Engine</i> i dokończ logowanie w przeglądarce (to samo konto, które utworzyło projekt).</td></tr>
<tr><td>Błąd: interfejs API wyłączony (<i>has not been used</i> / <i>disabled</i>)</td><td>Włącz Earth Engine API dla projektu (krok 3 powyżej), poczekaj minutę i spróbuj ponownie.</td></tr>
<tr><td>Błąd: projekt niezarejestrowany (<i>not registered</i>)</td><td>Zarejestruj projekt (krok 4 powyżej).</td></tr>
<tr><td>Błąd: brak uprawnień (<i>permission</i>, 403)</td><td>Zalogowano innym kontem niż to, które ma dostęp do projektu, albo konto nie ma roli użytkownika usług w projekcie. Zaloguj się właściwym kontem.</td></tr>
<tr><td>Błąd: nie znaleziono projektu</td><td>Wpisano nazwę zamiast identyfikatora albo literówkę. Identyfikator sprawdź na liście projektów w Google Cloud.</td></tr>
<tr><td>Błąd sieci / przekroczenie czasu</td><td>Sprawdź internet, proxy i zaporę (dostęp do <code>earthengine.googleapis.com</code>). W ustawieniach zaawansowanych zmniejsz rozmiar kafla do 256 px.</td></tr>
<tr><td>Bardzo mały obszar</td><td>Piksel VIIRS ma około 500 m. Dla obszarów mniejszych niż piksel wynik opisuje także światło z otoczenia (wtyczka ostrzega o tym w raporcie).</td></tr>
<tr><td>Bardzo duży obszar</td><td>Pobieranie trwa długo i zużywa limity Earth Engine. Zmniejsz obszar lub pierścień, albo w ustawieniach zaawansowanych wybierz siatkę 960 m.</td></tr>
</table>

<h3>Jak czytać wyniki</h3>
<ul>
<li><b>Radiancja</b> to jasność nocnego światła widziana z satelity, w nW/cm²/sr: większa liczba oznacza jaśniej. Wartość roczna to mediana miesięcznych kompozytów z miesięcy z obserwacjami.</li>
<li><b>Strefy</b>: <i>Obszar</i> (suma obiektów warstwy) i <i>pierścienie</i> wokół niego. Pierścień pokazuje światło otoczenia, z którego dociera rozproszone światło. Piksel należy do strefy, gdy co najmniej połowa jego powierzchni leży w strefie.</li>
<li><b>Trend</b>: nachylenie Theila-Sena (zmiana radiancji na rok) i test Manna-Kendalla (p). Małe p oznacza, że monotoniczny trend trudno uznać za przypadek, ale nie wyjaśnia przyczyny. Testy nie uwzględniają autokorelacji ani wielokrotnego testowania: traktuj je opisowo. Mapa trendu pokazuje nachylenie w każdym pikselu.</li>
<li><b>Sezonowość i kompletność</b>: rycina z siatką rok × miesiąc pokazuje średnią radiancję i udział pikseli z obserwacją. Białe pola to brak kompozytu lub obserwacji.</li>
<li><b>Warstwy w QGIS</b>: GeoTIFF <i>viirs_roczne</i> ma jedno pasmo na rok (zmień pasmo w <i>Symbolizacji</i>), <i>viirs_trend_theil_sen</i> ma pasma: nachylenie i p, <i>viirs_miesieczne_*</i> mają pasmo na miesiąc.</li>
</ul>

<h3>Ograniczenia</h3>
<ul>
<li>VIIRS (ok. 500 m) nie rozróżnia pojedynczych źródeł światła, a jego pasmo (ok. 500–900 nm) słabo rejestruje światło niebieskie, np. z diod LED o zimnej barwie, więc wzrost udziału LED może być niedoszacowany.</li>
<li>Radiancja z satelity nie jest jasnością nieba mierzoną z ziemi (np. miernikiem SQM) ani natężeniem światła na gruncie.</li>
<li>Latem na wysokich szerokościach część miesięcy może nie mieć danych.</li>
<li>Ujemne i bliskie zeru wartości w ciemnych miejscach to szum pomiarowy.</li>
</ul>

<h3>Prywatność i dane</h3>
<ul>
<li>Granice Twojego obszaru <b>nie są wysyłane</b> do Google: zapytania zawierają tylko współrzędne prostokąta obejmującego obszar i jego pierścień.</li>
<li>Hasła nie są przechowywane. Identyfikator projektu zapisuje się w ustawieniach QGIS.</li>
<li>Dane VIIRS (NOAA) i Sentinel-2 (Copernicus) mają własne licencje dostawców; sprawdź je przed publikacją wyników.</li>
</ul>

<h3>Polecenie ręcznej instalacji bibliotek</h3>
<p><code>@@CMD@@</code></p>

<h3>O wtyczce i cytowanie</h3>
<p>Kod: <a href="https://github.com/gorniakgrzegorz/zanieczyszczenie_swiatlem">github.com/gorniakgrzegorz/zanieczyszczenie_swiatlem</a>; opis metody: <a href="https://gorniakgrzegorz.github.io/zanieczyszczenie_swiatlem/">gorniakgrzegorz.github.io/zanieczyszczenie_swiatlem</a>. Licencja MIT. Cytowanie wersji archiwalnej: G. Górniak, „zanieczyszczenie_swiatlem”, Zenodo, doi: <a href="https://doi.org/10.5281/zenodo.24186500">10.5281/zenodo.24186500</a>. Zgłoszenia błędów: <a href="https://github.com/gorniakgrzegorz/zanieczyszczenie_swiatlem/issues">Issues</a>.</p>
""",
'en': """
<h2>Night-time Light Pollution (version @@VERSION@@)</h2>
<p>The plugin analyses <b>artificial night-time light</b> in any area and its surroundings from the monthly VIIRS DNB composites (collection <code>NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG</code>, Google Earth Engine). For an area from a QGIS layer or a file it computes the brightness of night-time light in the area and in rings around it, the trend over the years and seasonality, draws maps, makes animations and saves GeoTIFFs, which it adds straight to the QGIS project.</p>

<h3>Quick start</h3>
<ol>
<li><i>GEE access</i> tab: do the one-time steps below (account, project, API, registration), then install the libraries, log in and test the connection.</li>
<li><i>Analysis</i> tab: choose a polygon layer from the project (or a file), enter the GEE project ID, choose the output folder and click <i>Run analysis</i>.</li>
<li>Wait (time depends on area size, ring size and number of years; typically a few to a few dozen minutes). Progress is shown on the bar, details in the <i>Log</i> tab. An interrupted download resumes: downloaded data is cached in the output folder.</li>
<li><i>Results</i> tab: layers are added to the project, and tables (CSV), figures (PNG), animations (GIF) and the report open with a double click.</li>
</ol>
<p>The first time, choose a <b>small area</b> (e.g. a municipality) to check that everything works.</p>

@@GEE@@

<h3>Troubleshooting</h3>
<table border="1" cellpadding="4" cellspacing="0">
<tr><th>Message / symptom</th><th>Cause and what to do</th></tr>
<tr><td>"Libraries" indicator red, installation fails</td><td>No internet, firewall or proxy, too little disk space, or a Python without pip. Read the log. You can install manually: open <i>OSGeo4W Shell</i> (Windows) or a terminal and paste the command from the <i>Copy install command</i> button (below). The libraries go to <code>@@LIBS@@</code>.</td></tr>
<tr><td>"Python not found"</td><td>On the <i>Analysis</i> tab, in the advanced settings, point to a <code>python</code> executable (version 3.9 or newer, with pip).</td></tr>
<tr><td>Error: not logged in / "authorize"</td><td>Click <i>Log in to Earth Engine</i> and finish the sign-in in the browser (the same account that created the project).</td></tr>
<tr><td>Error: API disabled (<i>has not been used</i> / <i>disabled</i>)</td><td>Enable the Earth Engine API for the project (step 3 above), wait a minute and try again.</td></tr>
<tr><td>Error: project not registered (<i>not registered</i>)</td><td>Register the project (step 4 above).</td></tr>
<tr><td>Error: permission denied (<i>permission</i>, 403)</td><td>You are logged in with a different account than the one with access to the project, or the account lacks the service-usage role in the project. Log in with the right account.</td></tr>
<tr><td>Error: project not found</td><td>You entered the name instead of the ID, or a typo. Check the ID in the project list in Google Cloud.</td></tr>
<tr><td>Network error / timeout</td><td>Check internet, proxy and firewall (access to <code>earthengine.googleapis.com</code>). In the advanced settings reduce the tile size to 256 px.</td></tr>
<tr><td>Very small area</td><td>A VIIRS pixel is about 500 m. For areas smaller than a pixel the result also reflects light from the surroundings (the plugin notes this in the report).</td></tr>
<tr><td>Very large area</td><td>Downloading takes long and uses Earth Engine quotas. Reduce the area or ring, or choose the 960 m grid in the advanced settings.</td></tr>
</table>

<h3>How to read the results</h3>
<ul>
<li><b>Radiance</b> is the brightness of night-time light seen from the satellite, in nW/cm²/sr: a larger number means brighter. The annual value is the median of the monthly composites from months with observations.</li>
<li><b>Zones</b>: the <i>Area</i> (union of the layer features) and <i>rings</i> around it. A ring shows the surrounding light that scatters into the area. A pixel belongs to a zone when at least half of its area lies in the zone.</li>
<li><b>Trend</b>: Theil–Sen slope (change of radiance per year) and the Mann–Kendall test (p). A small p means a monotonic trend is hard to dismiss as chance, but does not explain the cause. The tests ignore autocorrelation and multiple testing: treat them as descriptive. The trend map shows the slope in every pixel.</li>
<li><b>Seasonality and completeness</b>: the year × month grid shows mean radiance and the share of pixels with an observation. White cells mean no composite or no observations.</li>
<li><b>Layers in QGIS</b>: the GeoTIFF <i>viirs_roczne</i> has one band per year (change the band in <i>Symbology</i>), <i>viirs_trend_theil_sen</i> has bands slope and p, <i>viirs_miesieczne_*</i> have one band per month.</li>
</ul>

<h3>Limitations</h3>
<ul>
<li>VIIRS (about 500 m) cannot separate individual light sources, and its band (about 500–900 nm) records blue light poorly, e.g. from cool-white LEDs, so growth of LED lighting may be underestimated.</li>
<li>Satellite radiance is neither sky brightness measured from the ground (e.g. with an SQM meter) nor illuminance at ground level.</li>
<li>In summer at high latitudes some months may have no data.</li>
<li>Negative and near-zero values in dark places are measurement noise.</li>
</ul>

<h3>Privacy and data</h3>
<ul>
<li>Your area boundary is <b>not sent</b> to Google: requests contain only the coordinates of the rectangle enclosing the area and its ring.</li>
<li>Passwords are not stored. The project ID is saved in the QGIS settings.</li>
<li>VIIRS (NOAA) and Sentinel-2 (Copernicus) data have their own provider licences; check them before publishing results.</li>
</ul>

<h3>Manual library install command</h3>
<p><code>@@CMD@@</code></p>

<h3>About and citation</h3>
<p>Code: <a href="https://github.com/gorniakgrzegorz/zanieczyszczenie_swiatlem">github.com/gorniakgrzegorz/zanieczyszczenie_swiatlem</a>; method description: <a href="https://gorniakgrzegorz.github.io/zanieczyszczenie_swiatlem/">gorniakgrzegorz.github.io/zanieczyszczenie_swiatlem</a>. MIT licence. Cite the archived version: G. Górniak, "zanieczyszczenie_swiatlem", Zenodo, doi: <a href="https://doi.org/10.5281/zenodo.24186500">10.5281/zenodo.24186500</a>. Bug reports: <a href="https://github.com/gorniakgrzegorz/zanieczyszczenie_swiatlem/issues">Issues</a>.</p>
""",
}


def help_html(lang, version, libs, cmd):
    lang = 'en' if lang == 'en' else 'pl'
    return (HELP[lang].replace('@@GEE@@', GEE_STEPS[lang]).replace('@@VERSION@@', version).replace('@@LIBS@@', libs).replace('@@CMD@@', cmd))


def gee_html(lang):
    return GEE_STEPS['en' if lang == 'en' else 'pl']
