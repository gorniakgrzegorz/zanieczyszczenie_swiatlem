"""[Wymaga PyQt5, geopandas i zaślepek z tego katalogu; /tmp/zsnlibs = folder z bibliotekami, /tmp/pt/AOI.gpkg = obszar testowy z make_aoi.py] Ścieżki błędów okna wtyczki: zły projekt, brak logowania, instalacja, błędny plik obszaru, zatrzymanie."""
import os, sys, time, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['ZSN_TEST_AOI'] = '/tmp/pt/AOI.gpkg'
os.environ['ZSN_EXTRA_PYTHONPATH'] = os.path.join(HERE, 'stub')
PROFILE = '/tmp/zsn_profile'
os.environ['ZSN_TEST_PROFILE'] = PROFILE
sys.path.insert(0, os.path.join(HERE, 'qgis_stub')); sys.path.insert(0, os.path.dirname(HERE))
from PyQt5.QtWidgets import QApplication, QMessageBox
app = QApplication([])
shown = []
for n in ('warning', 'information'):
    setattr(QMessageBox, n, staticmethod(lambda *a, _n=n: shown.append(a[2] if len(a) > 2 else '') or QMessageBox.Ok))
from zanieczyszczenie_swiatla_nocnego import dialog as D, runner
from qgis.core import QgsProject, QgsVectorLayer

class Iface:
    def mapCanvas(self):
        class C:
            def refresh(self): pass
        return C()

def wait(cond, timeout=120):
    t = time.time()
    while time.time() - t < timeout:
        app.processEvents()
        if cond(): return True
        time.sleep(0.05)
    return False

QgsProject.instance().addMapLayer(QgsVectorLayer(None, 'Park', 'ogr'))
dlg = D.NightLightDialog(Iface()); dlg.lang = 'pl'; dlg.show()
assert wait(lambda: dlg.libs_ok is not None and not dlg._busy(), 90) and dlg.libs_ok
out = '/tmp/zsn_ui_err'; shutil.rmtree(out, ignore_errors=True)
dlg.le_out.setText(out); dlg.le_project.setText('moj-projekt-1')

# 1. brak logowania
os.environ['T_EE_FAIL'] = 'Earth Engine client library not initialized. Please authorize access'
dlg.test_connection(); assert wait(lambda: not dlg._busy())
print('1 conn_ok', dlg.conn_ok, '|', shown[-1][:70]); assert dlg.conn_ok is False and 'logowania' in shown[-1]

# 2. API wyłączone podczas analizy -> kod 3, zakładka GEE
os.environ['T_EE_FAIL'] = 'Google Earth Engine API has not been used in project 123 before or it is disabled.'
dlg.tabs.setCurrentIndex(0); shown.clear()
dlg.run_analysis(); assert wait(lambda: not dlg._busy(), 120)
print('2 tab', dlg.tabs.currentIndex(), '|', shown[-1][:70]); assert dlg.tabs.currentIndex() == 1 and 'API' in shown[-1]

# 3. zły identyfikator projektu
os.environ['T_EE_FAIL'] = 'Project not found: 404'
shown.clear(); dlg.test_connection(); assert wait(lambda: not dlg._busy())
print('3', shown[-1][:60]); assert 'identyfikator' in shown[-1].lower()
os.environ.pop('T_EE_FAIL')

# 4. logowanie (zaślepka) i porażka logowania
dlg.login_gee(); assert wait(lambda: not dlg._busy(), 60)
print('4 login ok:', dlg.logged_in); assert dlg.logged_in is True
os.environ['T_AUTH_FAIL'] = 'browser failed'; shown.clear()
dlg.login_gee(); assert wait(lambda: not dlg._busy(), 60)
print('4b login fail:', dlg.logged_in, '|', shown[-1][:50]); assert dlg.logged_in is False and shown
os.environ.pop('T_AUTH_FAIL')

# 5. błędny plik obszaru -> kod 4 lub komunikat
bad = '/tmp/zsn_bad.gpkg'; open(bad, 'w').write('to nie jest geopackage')
dlg.rb_file.setChecked(True); dlg.le_file.setText(bad); shown.clear()
dlg.run_analysis(); assert wait(lambda: not dlg._busy(), 120)
print('5 błędny plik:', shown[-1][:100].replace('\n', ' '), '| status:', dlg.status.text()); assert shown
# nieistniejący plik
shown.clear(); dlg.le_file.setText('/nie/ma/pliku.gpkg'); dlg.run_analysis(); print('5b', shown[-1][:50]); assert 'plik' in shown[-1].lower()
dlg.rb_layer.setChecked(True)

# 6. zatrzymanie w trakcie
shown.clear(); dlg.sp_y0.setValue(2014); dlg.sp_y1.setValue(2023)
dlg.run_analysis(); wait(lambda: dlg._busy() and len(dlg.last_lines) > 2, 60); time.sleep(0.5)
dlg.stop_job(); assert wait(lambda: not dlg._busy(), 30)
print('6 po zatrzymaniu:', dlg.status.text(), '| przyciski:', dlg.btn_run.isEnabled(), dlg.btn_stop.isEnabled())
assert dlg.btn_run.isEnabled() and not dlg.btn_stop.isEnabled()

# 7. instalacja bibliotek (mały pakiet) do osobnego profilu
P2 = '/tmp/zsn_profile2'; shutil.rmtree(P2, ignore_errors=True); os.makedirs(P2)
os.environ['ZSN_TEST_PROFILE'] = P2
runner.PACKAGES[:] = ['pyjokes']
runner.IMPORT_CHECK = 'import pyjokes; print("DEPS_OK")'
d2 = D.NightLightDialog(Iface()); d2.show()
assert wait(lambda: d2.libs_ok is not None and not d2._busy(), 60)
print('7 przed instalacją libs_ok =', d2.libs_ok); assert d2.libs_ok is False
d2.install_libs(); assert wait(lambda: not d2._busy() and d2.libs_ok is not None, 240)
print('7 po instalacji libs_ok =', d2.libs_ok, '| folder:', os.listdir(d2.libs)[:4]); assert d2.libs_ok
print('TEST BŁĘDÓW OK')
