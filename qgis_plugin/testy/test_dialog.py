"""[Wymaga PyQt5, geopandas i zaślepek z tego katalogu; /tmp/zsnlibs = folder z bibliotekami, /tmp/pt/AOI.gpkg = obszar testowy z make_aoi.py] Test okna wtyczki na zaślepkach qgis (PyQt5, tryb offscreen) z prawdziwym silnikiem i zaślepką ee."""
import os, sys, time, glob, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ.setdefault('ZSN_TEST_AOI', '/tmp/pt/AOI.gpkg')
os.environ.setdefault('ZSN_EXTRA_PYTHONPATH', os.path.join(HERE, 'stub'))
PROFILE = '/tmp/zsn_profile'
os.environ['ZSN_TEST_PROFILE'] = PROFILE
os.makedirs(PROFILE, exist_ok=True)
lib = os.path.join(PROFILE, 'zanieczyszczenie_swiatla_nocnego_libs')
if not os.path.exists(lib):
    os.symlink('/tmp/zsnlibs', lib)
sys.path.insert(0, os.path.join(HERE, 'qgis_stub')); sys.path.insert(0, os.path.dirname(HERE)); 

from PyQt5.QtWidgets import QApplication, QMessageBox
app = QApplication([])
# okna komunikatów nie mogą blokować testu
shown = []
for n in ('warning', 'information'):
    setattr(QMessageBox, n, staticmethod(lambda *a, _n=n: shown.append((_n, a[2] if len(a) > 2 else '')) or QMessageBox.Ok))

import importlib
pkg = importlib.import_module('zanieczyszczenie_swiatla_nocnego')
from zanieczyszczenie_swiatla_nocnego import dialog as D, i18n
from qgis.core import QgsProject, QgsVectorLayer

used = set()
orig_tr = D.tr
def rec(key, lang, **kw):
    used.add(key); return orig_tr(key, lang, **kw)
D.tr = rec

class Iface:
    def mapCanvas(self):
        class C:
            def refresh(self): pass
        return C()

def wait(cond, timeout=120):
    t = time.time()
    while time.time() - t < timeout:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.05)
    return False

QgsProject.instance().addMapLayer(QgsVectorLayer(None, 'Park testowy', 'ogr', polygon=True, nfeat=2))
QgsProject.instance().addMapLayer(QgsVectorLayer(None, 'Punkty', 'ogr', polygon=False))
dlg = D.NightLightDialog(Iface())
dlg.show(); app.processEvents()
assert dlg.cb_layer.count() == 1, dlg.cb_layer.count()          # tylko poligony
print('warstwy poligonowe:', dlg.cb_layer.count(), '| język:', dlg.lang)
# przełączanie języka
for i in (1, 0, 1, 0):
    dlg.cb_lang.setCurrentIndex(i); app.processEvents()
print('przełączanie języka OK; tytuł zakładki:', dlg.tabs.tabText(0))

# biblioteki
assert wait(lambda: dlg.libs_ok is not None and not dlg._busy(), 90), 'sprawdzenie bibliotek'
print('libs_ok =', dlg.libs_ok)
assert dlg.libs_ok
# test połączenia (zaślepka ee)
dlg.le_project.setText('moj-projekt-123456')
dlg.test_connection()
assert wait(lambda: not dlg._busy(), 60)
print('conn_ok =', dlg.conn_ok)
assert dlg.conn_ok
# analiza
out = '/tmp/zsn_ui_out'
shutil.rmtree(out, ignore_errors=True)
dlg.le_out.setText(out)
dlg.sp_y0.setValue(2019); dlg.sp_y1.setValue(2021)
dlg.chk_anim_m.setChecked(False); dlg.chk_bg.setChecked(False)
dlg.cb_scale.setCurrentIndex(0)
dlg.run_analysis()
assert wait(lambda: not dlg._busy(), 300), 'analiza'
print('status:', dlg.status.text(), '| result:', dlg.last_result)
print('okna komunikatów:', shown)
assert dlg.last_result and os.path.isdir(dlg.last_result)
grp = QgsProject.instance().layerTreeRoot().groups
print('grupy:', [(g.name, [(n.layer.name(), n.checked) for n in g.nodes]) for g in grp])
assert grp and len(grp[0].nodes) >= 2
# brak identyfikatora projektu -> komunikat
shown.clear(); dlg.le_project.setText(''); dlg.run_analysis(); print('bez projektu:', shown[-1][1][:60])
# brakujące klucze
missing = sorted(k for k in used if k not in i18n.S)
print('użyte klucze:', len(used), '| brakujące:', missing)
bad = [k for k, (pl, en) in i18n.S.items() if not pl or not en]
print('puste tłumaczenia:', bad)
unused = sorted(k for k in i18n.S if k not in used)
print('nieużyte (info):', unused)
assert not missing and not bad
print('TEST OK')
