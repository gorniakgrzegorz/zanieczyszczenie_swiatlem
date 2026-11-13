# -*- coding: utf-8 -*-
"""Okno wtyczki: analiza, dostęp do GEE, wyniki, dziennik, pomoc (polski i angielski).
Plugin window: analysis, GEE access, results, log, help (Polish and English)."""
import os
import re
import glob
import json
import time
import datetime
import pathlib

from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtGui import QDesktopServices, QGuiApplication, QTextCursor
from qgis.PyQt.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout, QTabWidget, QWidget, QLabel, QPushButton, QLineEdit, QComboBox,
                                 QCheckBox, QRadioButton, QSpinBox, QGroupBox, QProgressBar, QPlainTextEdit, QTextBrowser, QTreeWidget, QTreeWidgetItem,
                                 QFileDialog, QMessageBox, QScrollArea, QFrame, QSizePolicy)
from qgis.core import QgsApplication, QgsProject, QgsSettings

from . import runner
from .jobs import ProcJob
from .i18n import tr
from .help_content import help_html, gee_html

VERSION = '1.0.0'
KEY = 'zanieczyszczenie_swiatla_nocnego/'
OK, BAD, UNK = '✔', '✘', '○'      # ✔ ✘ ○


def default_lang():
    try:
        loc = str(QgsSettings().value('locale/userLocale', '') or '')
        if not loc:
            loc = str(QgsApplication.locale())
    except Exception:
        loc = ''
    return 'pl' if loc.lower().startswith('pl') else 'en'


def is_polygon_layer(layer):
    try:
        from qgis.core import Qgis
        return layer.geometryType() == Qgis.GeometryType.Polygon
    except Exception:
        pass
    try:
        from qgis.core import QgsWkbTypes
        return layer.geometryType() == QgsWkbTypes.PolygonGeometry
    except Exception:
        return False


def export_layer(layer, path, only_selected):
    """Zapis warstwy z projektu do GPKG (dla silnika). Zwraca (ok, komunikat)."""
    from qgis.core import QgsVectorFileWriter
    if os.path.exists(path):
        os.remove(path)
    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = 'GPKG'
    opts.layerName = 'area'
    opts.fileEncoding = 'UTF-8'
    opts.onlySelectedFeatures = bool(only_selected)
    ctx = QgsProject.instance().transformContext()
    fn = getattr(QgsVectorFileWriter, 'writeAsVectorFormatV3', None) or QgsVectorFileWriter.writeAsVectorFormatV2
    res = fn(layer, path, ctx, opts)
    err, msg = res[0], res[1]
    no_error = getattr(QgsVectorFileWriter, 'NoError', None)
    if no_error is None:
        no_error = QgsVectorFileWriter.WriterError.NoError
    return (err == no_error), str(msg)


class NightLightDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.settings = QgsSettings()
        self.lang = str(self.settings.value(KEY + 'lang', 'auto'))
        if self.lang not in ('pl', 'en'):
            self.lang = default_lang()
        self._tr = []                    # (setter, klucz) do przełączania języka
        self.job = None
        self.job_kind = None
        self.libs_ok = None
        self.conn_ok = None
        self.logged_in = None
        self.last_gee_error = None
        self.last_error = None
        self.last_result = None
        self.last_lines = []
        self.python = None
        self.python_version = None
        self.libs = runner.libs_dir(QgsApplication.qgisSettingsDirPath())
        self._syncing = False
        self._build()
        self._load_settings()
        self.apply_language()
        self.refresh_layers()

    # ------------------------------------------------------------------ pomocnicze
    def t(self, key, **kw):
        return tr(key, self.lang, **kw)

    def reg(self, setter, key):
        self._tr.append((setter, key))
        setter(self.t(key))

    def apply_language(self):
        for setter, key in self._tr:
            setter(self.t(key))
        self.tabs.setTabText(0, self.t('tab_run'))
        self.tabs.setTabText(1, self.t('tab_gee'))
        self.tabs.setTabText(2, self.t('tab_results'))
        self.tabs.setTabText(3, self.t('tab_log'))
        self.tabs.setTabText(4, self.t('tab_help'))
        self.setWindowTitle(self.t('window_title'))
        self.gee_text.setHtml(gee_html(self.lang))
        self.help_text.setHtml(help_html(self.lang, VERSION, self.libs, runner.pip_command_text(self.python or 'python', self.libs)))
        self.refresh_status()

    def _group(self, key):
        g = QGroupBox()
        self.reg(g.setTitle, key)
        return g

    def _label(self, key):
        lb = QLabel()
        lb.setWordWrap(True)
        self.reg(lb.setText, key)
        return lb

    def _button(self, key, slot):
        b = QPushButton()
        self.reg(b.setText, key)
        b.clicked.connect(slot)
        return b

    def _check(self, key, checked=True):
        c = QCheckBox()
        self.reg(c.setText, key)
        c.setChecked(checked)
        return c

    # ------------------------------------------------------------------ budowa interfejsu
    def _build(self):
        self.resize(820, 780)
        root = QVBoxLayout(self)
        top = QHBoxLayout()
        title = QLabel()
        title.setStyleSheet('font-size: 15px; font-weight: bold;')
        self.reg(title.setText, 'title')
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(self._label('language'))
        self.cb_lang = QComboBox()
        self.cb_lang.addItem('Polski', 'pl')
        self.cb_lang.addItem('English', 'en')
        self.cb_lang.setCurrentIndex(0 if self.lang == 'pl' else 1)
        self.cb_lang.currentIndexChanged.connect(self._lang_changed)
        top.addWidget(self.cb_lang)
        root.addLayout(top)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)
        self.tabs.addTab(self._build_run(), '')
        self.tabs.addTab(self._build_gee(), '')
        self.tabs.addTab(self._build_results(), '')
        self.tabs.addTab(self._build_log(), '')
        self.tabs.addTab(self._build_help(), '')
        bottom = QVBoxLayout()
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.status = QLabel('')
        self.status.setWordWrap(True)
        bottom.addWidget(self.progress)
        bottom.addWidget(self.status)
        root.addLayout(bottom)

    def _build_run(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        # --- obszar
        g = self._group('grp_area')
        gl = QGridLayout(g)
        self.rb_layer = QRadioButton()
        self.reg(self.rb_layer.setText, 'area_layer')
        self.rb_layer.setChecked(True)
        self.cb_layer = QComboBox()
        self.cb_layer.currentIndexChanged.connect(self._area_hint)
        self.chk_sel = self._check('only_selected', False)
        self.rb_file = QRadioButton()
        self.reg(self.rb_file.setText, 'area_file')
        self.le_file = QLineEdit()
        self.btn_file = self._button('browse', self._choose_file)
        self.le_file_layer = QLineEdit()
        self.reg(self.le_file_layer.setPlaceholderText, 'file_layer_hint')
        gl.addWidget(self.rb_layer, 0, 0)
        gl.addWidget(self.cb_layer, 0, 1, 1, 2)
        gl.addWidget(self.chk_sel, 1, 1, 1, 2)
        gl.addWidget(self.rb_file, 2, 0)
        gl.addWidget(self.le_file, 2, 1)
        gl.addWidget(self.btn_file, 2, 2)
        gl.addWidget(self.le_file_layer, 3, 1, 1, 2)
        self.le_name = QLineEdit()
        self.reg(self.le_name.setPlaceholderText, 'name_hint')
        gl.addWidget(self._label('area_name'), 4, 0)
        gl.addWidget(self.le_name, 4, 1, 1, 2)
        self.lbl_area = QLabel('')
        self.lbl_area.setWordWrap(True)
        gl.addWidget(self.lbl_area, 5, 0, 1, 3)
        lay.addWidget(g)
        # --- parametry
        g = self._group('grp_params')
        f = QFormLayout(g)
        self.le_project = QLineEdit()
        self.reg(self.le_project.setPlaceholderText, 'project_hint')
        self.le_project.textChanged.connect(self._project_changed)
        prow = QHBoxLayout()
        prow.addWidget(self.le_project)
        prow.addWidget(self._button('how_get_project', lambda: self.tabs.setCurrentIndex(1)))
        f.addRow(self._label('project_id'), prow)
        yrow = QHBoxLayout()
        self.sp_y0 = QSpinBox()
        self.sp_y0.setRange(2014, 2100)
        self.sp_y1 = QSpinBox()
        self.sp_y1.setRange(2014, 2100)
        self.sp_y0.setValue(2014)
        self.sp_y1.setValue(max(2015, datetime.date.today().year - 1))
        yrow.addWidget(self.sp_y0)
        yrow.addWidget(QLabel('–'))
        yrow.addWidget(self.sp_y1)
        yrow.addStretch(1)
        f.addRow(self._label('years'), yrow)
        self.le_rings = QLineEdit('5000')
        self.reg(self.le_rings.setToolTip, 'rings_tip')
        f.addRow(self._label('rings'), self.le_rings)
        orow = QHBoxLayout()
        self.le_out = QLineEdit()
        orow.addWidget(self.le_out)
        orow.addWidget(self._button('browse', self._choose_out))
        f.addRow(self._label('out_dir'), orow)
        lay.addWidget(g)
        # --- zaawansowane
        self.gb_adv = QGroupBox()
        self.gb_adv.setCheckable(True)
        self.gb_adv.setChecked(False)
        self.reg(self.gb_adv.setTitle, 'grp_adv')
        al = QFormLayout(self.gb_adv)
        self.cb_scale = QComboBox()
        self.cb_scale.addItem('480 m', 480)
        self.cb_scale.addItem('960 m', 960)
        self.cb_tile = QComboBox()
        for v in (256, 512, 1024):
            self.cb_tile.addItem(str(v), v)
        self.cb_tile.setCurrentIndex(1)
        self.sp_threads = QSpinBox()
        self.sp_threads.setRange(1, 16)
        self.sp_threads.setValue(8)
        self.le_thr = QLineEdit()
        self.reg(self.le_thr.setPlaceholderText, 'thr_hint')
        self.chk_monthly = self._check('opt_monthly', True)
        self.chk_anim = self._check('opt_anim', True)
        self.chk_anim_m = self._check('opt_anim_monthly', True)
        self.chk_bg = self._check('opt_bg', True)
        self.sp_bg = QSpinBox()
        self.sp_bg.setRange(2017, 2100)
        self.sp_bg.setValue(max(2018, datetime.date.today().year - 1))
        bgrow = QHBoxLayout()
        bgrow.addWidget(self.chk_bg)
        bgrow.addWidget(self.sp_bg)
        bgrow.addStretch(1)
        self.cb_dpi = QComboBox()
        for v in (100, 150, 200, 300):
            self.cb_dpi.addItem(str(v), v)
        self.cb_dpi.setCurrentIndex(1)
        self.le_python = QLineEdit()
        self.reg(self.le_python.setPlaceholderText, 'python_hint')
        self.le_python.textChanged.connect(self._python_changed)
        self.chk_load = self._check('opt_load', True)
        al.addRow(self._label('adv_scale'), self.cb_scale)
        al.addRow(self._label('adv_tile'), self.cb_tile)
        al.addRow(self._label('adv_threads'), self.sp_threads)
        al.addRow(self._label('adv_thr'), self.le_thr)
        al.addRow(self.chk_monthly)
        al.addRow(self.chk_anim)
        al.addRow(self.chk_anim_m)
        al.addRow(bgrow)
        al.addRow(self._label('adv_dpi'), self.cb_dpi)
        al.addRow(self._label('adv_python'), self.le_python)
        al.addRow(self.chk_load)
        lay.addWidget(self.gb_adv)
        self.gb_adv.toggled.connect(self._adv_toggled)
        self._adv_toggled(False)
        # --- przyciski
        row = QHBoxLayout()
        self.btn_run = self._button('run', self.run_analysis)
        self.btn_run.setStyleSheet('font-weight: bold; padding: 6px 18px;')
        self.btn_stop = self._button('stop', self.stop_job)
        self.btn_stop.setEnabled(False)
        row.addWidget(self.btn_run)
        row.addWidget(self.btn_stop)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(page)
        return scroll

    def _adv_toggled(self, on):
        for i in range(self.gb_adv.layout().count()):
            it = self.gb_adv.layout().itemAt(i)
            w = it.widget() if it is not None else None
            if w is not None:
                w.setVisible(bool(on))
            elif it is not None and it.layout() is not None:
                for j in range(it.layout().count()):
                    ww = it.layout().itemAt(j).widget()
                    if ww is not None:
                        ww.setVisible(bool(on))

    def _build_gee(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        g = self._group('grp_status')
        gl = QGridLayout(g)
        self.status_rows = {}
        for r, key in enumerate(('st_python', 'st_libs', 'st_login', 'st_project', 'st_conn')):
            icon = QLabel(UNK)
            icon.setFixedWidth(22)
            icon.setStyleSheet('font-size: 15px;')
            text = QLabel('')
            text.setWordWrap(True)
            gl.addWidget(icon, r, 0)
            gl.addWidget(text, r, 1)
            self.status_rows[key] = (icon, text)
        lay.addWidget(g)
        f = QFormLayout()
        self.le_project2 = QLineEdit()
        self.reg(self.le_project2.setPlaceholderText, 'project_hint')
        self.le_project2.textChanged.connect(self._project2_changed)
        f.addRow(self._label('project_id'), self.le_project2)
        lay.addLayout(f)
        row = QHBoxLayout()
        self.btn_install = self._button('btn_install', self.install_libs)
        self.btn_login = self._button('btn_login', self.login_gee)
        self.btn_test = self._button('btn_test', self.test_connection)
        row.addWidget(self.btn_install)
        row.addWidget(self.btn_login)
        row.addWidget(self.btn_test)
        lay.addLayout(row)
        row2 = QHBoxLayout()
        row2.addWidget(self._button('btn_copycmd', self.copy_command))
        row2.addWidget(self._button('btn_open_console', lambda: QDesktopServices.openUrl(QUrl('https://console.cloud.google.com/projectcreate'))))
        row2.addStretch(1)
        lay.addLayout(row2)
        self.gee_text = QTextBrowser()
        self.gee_text.setOpenExternalLinks(True)
        lay.addWidget(self.gee_text, 1)
        return page

    def _build_results(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        self.lbl_out = QLabel('')
        self.lbl_out.setWordWrap(True)
        lay.addWidget(self.lbl_out)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemDoubleClicked.connect(self._open_item)
        lay.addWidget(self.tree, 1)
        g = self._group('grp_layers')
        gl = QVBoxLayout(g)
        self.ld_annual = self._check('ld_annual', True)
        self.ld_trend = self._check('ld_trend', True)
        self.ld_monthly = self._check('ld_monthly', False)
        self.ld_bg = self._check('ld_bg', False)
        self.ld_zones = self._check('ld_zones', True)
        self.ld_tables = self._check('ld_tables', False)
        for c in (self.ld_annual, self.ld_trend, self.ld_monthly, self.ld_bg, self.ld_zones, self.ld_tables):
            gl.addWidget(c)
        lay.addWidget(g)
        row = QHBoxLayout()
        row.addWidget(self._button('btn_add_layers', self.add_layers))
        row.addWidget(self._button('btn_open_folder', self.open_folder))
        row.addWidget(self._button('btn_open_prev', self.choose_previous))
        row.addStretch(1)
        lay.addLayout(row)
        return page

    def _build_log(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(20000)
        lay.addWidget(self.log)
        row = QHBoxLayout()
        row.addWidget(self._button('btn_clear_log', self.log.clear))
        row.addWidget(self._button('btn_copy_log', lambda: QGuiApplication.clipboard().setText(self.log.toPlainText())))
        row.addStretch(1)
        lay.addLayout(row)
        return page

    def _build_help(self):
        self.help_text = QTextBrowser()
        self.help_text.setOpenExternalLinks(True)
        return self.help_text

    # ------------------------------------------------------------------ ustawienia
    def _load_settings(self):
        s = self.settings
        self.le_project.setText(str(s.value(KEY + 'project', '') or ''))
        self.le_out.setText(str(s.value(KEY + 'out_dir', '') or ''))
        self.le_rings.setText(str(s.value(KEY + 'rings', '5000') or '5000'))
        self.le_python.setText(str(s.value(KEY + 'python', '') or ''))
        try:
            self.sp_y0.setValue(int(s.value(KEY + 'y0', self.sp_y0.value())))
            self.sp_y1.setValue(int(s.value(KEY + 'y1', self.sp_y1.value())))
        except (TypeError, ValueError):
            pass

    def _save_settings(self):
        s = self.settings
        s.setValue(KEY + 'project', self.le_project.text().strip())
        s.setValue(KEY + 'out_dir', self.le_out.text().strip())
        s.setValue(KEY + 'rings', self.le_rings.text().strip())
        s.setValue(KEY + 'python', self.le_python.text().strip())
        s.setValue(KEY + 'y0', self.sp_y0.value())
        s.setValue(KEY + 'y1', self.sp_y1.value())
        s.setValue(KEY + 'lang', self.lang)

    def closeEvent(self, e):
        self._save_settings()
        super().closeEvent(e)

    def _lang_changed(self, idx):
        self.lang = self.cb_lang.itemData(idx)
        self.settings.setValue(KEY + 'lang', self.lang)
        self.apply_language()
        self._area_hint()

    def _python_changed(self, _text):
        self.python = None
        self.python_version = None
        self._python_checked = False
        self.libs_ok = None

    def _project_changed(self, text):
        if not self._syncing:
            self._syncing = True
            self.le_project2.setText(text)
            self._syncing = False
        self.conn_ok = None
        self.refresh_status()

    def _project2_changed(self, text):
        if not self._syncing:
            self._syncing = True
            self.le_project.setText(text)
            self._syncing = False
        self.conn_ok = None
        self.refresh_status()

    # ------------------------------------------------------------------ obszar
    def showEvent(self, e):
        super().showEvent(e)
        self.refresh_layers()
        self.le_project2.setText(self.le_project.text())
        if self.libs_ok is None and not self._busy():
            self.check_libs()
        else:
            self.refresh_status()

    def refresh_layers(self):
        cur = self.cb_layer.currentData()
        self.cb_layer.blockSignals(True)
        self.cb_layer.clear()
        from qgis.core import QgsVectorLayer
        for lid, layer in QgsProject.instance().mapLayers().items():
            try:
                if isinstance(layer, QgsVectorLayer) and is_polygon_layer(layer):
                    self.cb_layer.addItem(layer.name(), lid)
            except Exception:
                continue
        i = self.cb_layer.findData(cur) if cur else -1
        if i >= 0:
            self.cb_layer.setCurrentIndex(i)
        self.cb_layer.blockSignals(False)
        self._area_hint()

    def _selected_layer(self):
        lid = self.cb_layer.currentData()
        return QgsProject.instance().mapLayer(lid) if lid else None

    def _area_hint(self, *_):
        text = ''
        try:
            layer = self._selected_layer()
            if layer is not None:
                from qgis.core import QgsDistanceArea, QgsGeometry
                da = QgsDistanceArea()
                da.setSourceCrs(layer.crs(), QgsProject.instance().transformContext())
                da.setEllipsoid(QgsProject.instance().ellipsoid() or 'WGS84')
                km2 = da.measureArea(QgsGeometry.fromRect(layer.extent())) / 1e6
                text = self.t('area_hint', km2=f'{km2:,.0f}'.replace(',', ' '), n=layer.featureCount())
                if km2 > 3000:
                    text += ' ' + self.t('area_big')
        except Exception:
            text = ''
        self.lbl_area.setText(text)

    def _choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, self.t('choose_area_file'), self.le_file.text() or '', 'Vector (*.gpkg *.shp *.geojson *.json *.fgb *.gml);;*')
        if path:
            self.le_file.setText(path)
            self.rb_file.setChecked(True)

    def _choose_out(self):
        path = QFileDialog.getExistingDirectory(self, self.t('choose_out'), self.le_out.text() or '')
        if path:
            self.le_out.setText(path)

    # ------------------------------------------------------------------ stan i procesy
    def _busy(self):
        return self.job is not None and self.job.running()

    def set_status_row(self, key, ok, text):
        icon, label = self.status_rows[key]
        icon.setText(UNK if ok is None else (OK if ok else BAD))
        icon.setStyleSheet('font-size: 15px; color: %s;' % ('#888' if ok is None else ('#1a7f37' if ok else '#c62828')))
        label.setText(text)

    def refresh_status(self):
        py = self.python
        self.set_status_row('st_python', None if py is None and self.python_version is None and not self._python_checked else bool(py),
                            self.t('py_ok', path=py, ver=self.python_version) if py else self.t('py_none'))
        self.set_status_row('st_libs', self.libs_ok, self.t('libs_ok' if self.libs_ok else ('libs_bad' if self.libs_ok is False else 'libs_unk')))
        has_cred = os.path.isfile(runner.credentials_path())
        self.set_status_row('st_login', True if has_cred else (None if self.logged_in is None else False), self.t('login_ok' if has_cred else 'login_no'))
        proj = self.le_project.text().strip()
        proj_ok = bool(proj) and 'TWOJ' not in proj.upper() and 'YOUR' not in proj.upper()
        self.set_status_row('st_project', proj_ok, self.t('proj_ok', p=proj) if proj_ok else self.t('proj_no'))
        self.set_status_row('st_conn', self.conn_ok, self.t('conn_ok' if self.conn_ok else ('conn_bad' if self.conn_ok is False else 'conn_unk')))

    _python_checked = False

    def ensure_python(self):
        if self.python is None:
            self.python, self.python_version = runner.find_python(self.le_python.text().strip() or None)
            self._python_checked = True
        return self.python

    def set_busy(self, busy, status=None):
        for b in (self.btn_run, self.btn_install, self.btn_login, self.btn_test):
            b.setEnabled(not busy)
        self.btn_stop.setEnabled(busy)
        if status is not None:
            self.status.setText(status)

    def log_line(self, text):
        self.log.appendPlainText(text)
        self.log.moveCursor(QTextCursor.MoveOperation.End)

    def _start(self, kind, args, extra_env=None, status=''):
        py = self.ensure_python()
        if not py:
            self.refresh_status()
            QMessageBox.warning(self, self.t('window_title'), self.t('py_none_msg'))
            return False
        env = runner.process_env(self.libs, extra_pythonpath=os.environ.get('ZSN_EXTRA_PYTHONPATH'))
        if extra_env:
            env.update(extra_env)
        self.job_kind = kind
        self.last_gee_error = self.last_error = self.last_result = None
        self.last_lines = []
        self.job = ProcJob(self)
        self.job.line.connect(self._on_line)
        self.job.done.connect(self._on_done)
        self.set_busy(True, status)
        self.log_line('$ ' + ' '.join([py] + [str(a) for a in args]))
        self.job.start(py, args, env)
        return True

    def stop_job(self):
        if self.job is not None:
            self.job.kill()
            self.log_line(self.t('stopped'))

    def check_libs(self):
        if not self.ensure_python():
            self.refresh_status()
            return
        self._start('libs', ['-c', runner.IMPORT_CHECK], status=self.t('checking_libs'))

    def install_libs(self):
        if not self.ensure_python():
            self.refresh_status()
            QMessageBox.warning(self, self.t('window_title'), self.t('py_none_msg'))
            return
        os.makedirs(self.libs, exist_ok=True)
        cmd = runner.pip_command(self.python, self.libs)
        self.progress.setRange(0, 0)
        self._start('install', cmd[1:], status=self.t('installing'))

    def copy_command(self):
        QGuiApplication.clipboard().setText(runner.pip_command_text(self.python or 'python', self.libs))
        self.status.setText(self.t('cmd_copied'))

    def login_gee(self):
        if not self.libs_ok:
            QMessageBox.information(self, self.t('window_title'), self.t('need_libs'))
            return
        self._start('login', [runner.ENGINE, '--auth', '--lang', self.lang], status=self.t('login_wait'))

    def test_connection(self):
        proj = self.le_project.text().strip()
        if not self.libs_ok:
            QMessageBox.information(self, self.t('window_title'), self.t('need_libs'))
            return
        self._start('test', [runner.ENGINE, '--check', '--project', proj, '--lang', self.lang], status=self.t('testing'))

    # ------------------------------------------------------------------ analiza
    def _collect_config(self):
        """Walidacja i budowa konfiguracji; zwraca (cfg, błąd)."""
        proj = self.le_project.text().strip()
        if not proj or 'TWOJ' in proj.upper() or 'YOUR' in proj.upper():
            return None, self.t('err_project')
        out = self.le_out.text().strip()
        if not out:
            return None, self.t('err_out')
        try:
            os.makedirs(out, exist_ok=True)
            probe = os.path.join(out, '.zsn_probe')
            with open(probe, 'w') as f:
                f.write('x')
            os.remove(probe)
        except Exception as e:
            return None, self.t('err_out_write', e=str(e))
        try:
            rings = runner.parse_rings(self.le_rings.text())
        except ValueError:
            return None, self.t('err_rings')
        try:
            thr = runner.parse_thresholds(self.le_thr.text())
        except ValueError:
            return None, self.t('err_thr')
        y0, y1 = self.sp_y0.value(), self.sp_y1.value()
        if y1 < y0:
            return None, self.t('err_years')
        name = self.le_name.text().strip() or None
        cfg = {'lang': self.lang, 'project': proj, 'out_dir': out, 'years': [y0, y1], 'rings_m': rings, 'thresholds': thr, 'name': name,
               'scale_m': self.cb_scale.currentData(), 'tile_px': self.cb_tile.currentData(), 'threads': self.sp_threads.value(),
               'monthly': self.chk_monthly.isChecked(), 'animations': self.chk_anim.isChecked(), 'anim_monthly': self.chk_anim_m.isChecked() and self.chk_monthly.isChecked(),
               'background': self.chk_bg.isChecked(), 'background_year': self.sp_bg.value(), 'dpi': self.cb_dpi.currentData(), 'mp4': False, 'aoi_layer': None}
        if self.rb_file.isChecked():
            path = self.le_file.text().strip()
            if not path or not os.path.isfile(path):
                return None, self.t('err_file')
            cfg['aoi_gpkg'] = path
            cfg['aoi_layer'] = self.le_file_layer.text().strip() or None
            if not name:
                cfg['name'] = os.path.splitext(os.path.basename(path))[0]
        else:
            layer = self._selected_layer()
            if layer is None:
                return None, self.t('err_layer')
            if self.chk_sel.isChecked() and layer.selectedFeatureCount() == 0:
                return None, self.t('err_selected')
            if layer.featureCount() == 0:
                return None, self.t('err_empty')
            safe = re.sub(r'[^\w\-. ]+', '_', name or layer.name()).strip(' ._') or 'obszar'
            cfg['name'] = name or safe
            os.makedirs(os.path.join(out, '_wejscie'), exist_ok=True)
            path = os.path.join(out, '_wejscie', f'{safe}.gpkg')
            ok, msg = export_layer(layer, path, self.chk_sel.isChecked())
            if not ok:
                return None, self.t('err_export', e=msg)
            cfg['aoi_gpkg'] = path
        return cfg, None

    def run_analysis(self):
        if self._busy():
            return
        if not self.ensure_python():
            self.refresh_status()
            QMessageBox.warning(self, self.t('window_title'), self.t('py_none_msg'))
            return
        if not self.libs_ok:
            self.tabs.setCurrentIndex(1)
            QMessageBox.information(self, self.t('window_title'), self.t('need_libs'))
            return
        cfg, err = self._collect_config()
        if err:
            QMessageBox.warning(self, self.t('window_title'), err)
            return
        self._save_settings()
        cfg_path = os.path.join(cfg['out_dir'], '_zsn_konfiguracja.json')
        with open(cfg_path, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=1)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.tabs.setCurrentIndex(3)
        self._stage = (1, 8)
        self._start('run', [runner.ENGINE, '--config', cfg_path], status=self.t('running'))

    # ------------------------------------------------------------------ zdarzenia procesu
    def _on_line(self, text):
        ev = runner.parse_line(text)
        kind = ev['type']
        if kind == 'prog':
            n, total = self._stage if hasattr(self, '_stage') else (1, 8)
            self.progress.setValue(runner.progress_value(n, total, ev['done'], ev['total']))
            self.status.setText(f"{self.status.property('stage_text') or ''} ({ev['done']}/{ev['total']})")
            return
        if kind == 'stage':
            self._stage = (ev['n'], ev['total'])
            self.status.setProperty('stage_text', ev['text'])
            self.status.setText(f"[{ev['n']}/{ev['total']}] {ev['text']}")
            self.progress.setValue(runner.progress_value(ev['n'], ev['total']))
            self.log_line(text)
            return
        if kind == 'gee_error':
            self.last_gee_error = (ev['kind'], ev['text'])
        elif kind == 'error':
            self.last_error = (ev['kind'], ev['text'])
        elif kind == 'result':
            self.last_result = ev['path']
        elif kind in ('auth_ok', 'check_ok'):
            self.last_lines.append(kind)
        self.last_lines.append(text)
        self.last_lines = self.last_lines[-40:]
        self.log_line(text)

    def _gee_hint(self, kind, detail):
        return self.t('gee_err_' + kind if kind in ('auth', 'api_disabled', 'not_registered', 'permission', 'project', 'network') else 'gee_err_other') + '\n\n' + detail

    def _on_done(self, code, crashed):
        kind = self.job_kind
        self.set_busy(False)
        self.progress.setRange(0, 100)
        if kind == 'libs':
            self.libs_ok = (code == 0 and any('DEPS_OK' in ln for ln in self.last_lines))
            self.status.setText(self.t('libs_ok') if self.libs_ok else self.t('libs_bad'))
            self.refresh_status()
        elif kind == 'install':
            self.log_line(self.t('install_done', code=code))
            self.progress.setValue(0)
            self.libs_ok = None
            self.check_libs()
        elif kind == 'login':
            ok = any(x == 'auth_ok' for x in self.last_lines)
            self.logged_in = ok
            self.status.setText(self.t('login_done') if ok else self.t('login_failed'))
            if not ok and self.last_gee_error:
                QMessageBox.warning(self, self.t('window_title'), self._gee_hint(*self.last_gee_error))
            self.refresh_status()
        elif kind == 'test':
            ok = any(x == 'check_ok' for x in self.last_lines)
            self.conn_ok = ok
            self.status.setText(self.t('conn_ok') if ok else self.t('conn_bad'))
            if not ok:
                QMessageBox.warning(self, self.t('window_title'), self._gee_hint(*(self.last_gee_error or ('other', '\n'.join(self.last_lines[-6:])))))
            self.refresh_status()
        elif kind == 'run':
            self._run_finished(code, crashed)

    def _run_finished(self, code, crashed):
        if code in (0, 2) and self.last_result:
            self.progress.setValue(100)
            self.conn_ok = True
            self.refresh_status()
            self.status.setText(self.t('run_done') if code == 0 else self.t('run_done_errors'))
            self.populate_results(self.last_result)
            if self.chk_load.isChecked():
                self.add_layers()
            self.tabs.setCurrentIndex(2)
            if code == 2:
                QMessageBox.information(self, self.t('window_title'), self.t('run_done_errors_msg'))
            return
        self.progress.setValue(0)
        self.status.setText(self.t('run_failed'))
        if code == 3 and self.last_gee_error:
            self.conn_ok = False
            self.refresh_status()
            self.tabs.setCurrentIndex(1)
            QMessageBox.warning(self, self.t('window_title'), self._gee_hint(*self.last_gee_error))
        elif code == 4 and self.last_error:
            QMessageBox.warning(self, self.t('window_title'), self.last_error[1])
        else:
            if crashed and not self.last_lines:
                self.last_lines = [self.t('stopped')]
            tail = '\n'.join(ln for ln in self.last_lines[-8:])
            hint = self.t('run_crash_hint') if any(('ModuleNotFoundError' in ln or 'ImportError' in ln) for ln in self.last_lines) else ''
            QMessageBox.warning(self, self.t('window_title'), self.t('run_failed_msg', code=code) + '\n\n' + tail + ('\n\n' + hint if hint else ''))

    # ------------------------------------------------------------------ wyniki
    def populate_results(self, out):
        self.last_out = out
        self.lbl_out.setText(self.t('results_in', p=out))
        self.tree.clear()
        names = {'01_tabele': 'folder_tables', '02_ryciny': 'folder_figures', '03_animacje': 'folder_anims', '04_rastry': 'folder_rasters', '05_wektory': 'folder_vectors', '06_raport': 'folder_report'}
        for sub in sorted(names):
            d = os.path.join(out, sub)
            if not os.path.isdir(d):
                continue
            top = QTreeWidgetItem([self.t(names[sub])])
            self.tree.addTopLevelItem(top)
            for fn in sorted(os.listdir(d)):
                it = QTreeWidgetItem([fn])
                it.setData(0, Qt.ItemDataRole.UserRole, os.path.join(d, fn))
                top.addChild(it)
            top.setExpanded(sub in ('02_ryciny', '03_animacje', '06_raport'))

    def _open_item(self, item, _col=0):
        p = item.data(0, Qt.ItemDataRole.UserRole)
        if p:
            QDesktopServices.openUrl(QUrl.fromLocalFile(p))

    def open_folder(self):
        out = getattr(self, 'last_out', None) or self.le_out.text().strip()
        if out and os.path.isdir(out):
            QDesktopServices.openUrl(QUrl.fromLocalFile(out))

    def choose_previous(self):
        path = QFileDialog.getExistingDirectory(self, self.t('choose_prev'), self.le_out.text() or '')
        if path:
            if not os.path.isdir(os.path.join(path, '04_rastry')):
                subs = [d for d in glob.glob(os.path.join(path, '*')) if os.path.isdir(os.path.join(d, '04_rastry'))]
                if len(subs) == 1:
                    path = subs[0]
                else:
                    QMessageBox.information(self, self.t('window_title'), self.t('prev_invalid'))
                    return
            self.populate_results(path)

    def add_layers(self):
        out = getattr(self, 'last_out', None)
        if not out or not os.path.isdir(out):
            QMessageBox.information(self, self.t('window_title'), self.t('no_results'))
            return
        from qgis.core import QgsRasterLayer, QgsVectorLayer
        proj = QgsProject.instance()
        root = proj.layerTreeRoot()
        group = root.insertGroup(0, self.t('group_name', name=os.path.basename(out)))
        added = 0

        def add(layer, visible=True):
            nonlocal added
            if not layer.isValid():
                self.log_line(self.t('layer_invalid', n=layer.name()))
                return
            proj.addMapLayer(layer, False)
            node = group.addLayer(layer)
            if not visible and node is not None:
                node.setItemVisibilityChecked(False)
            added += 1

        rast = sorted(glob.glob(os.path.join(out, '04_rastry', '*.tif')))
        for p in rast:
            b = os.path.basename(p)
            if 'viirs_roczne' in b and self.ld_annual.isChecked():
                add(QgsRasterLayer(p, self.t('lyr_annual'), 'gdal'))
            elif 'viirs_trend' in b and self.ld_trend.isChecked():
                add(QgsRasterLayer(p, self.t('lyr_trend'), 'gdal'), False)
            elif 'viirs_miesieczne' in b and self.ld_monthly.isChecked():
                add(QgsRasterLayer(p, self.t('lyr_monthly_cf') if 'liczba' in b else self.t('lyr_monthly'), 'gdal'), False)
            elif 'tlo_sentinel2' in b and self.ld_bg.isChecked():
                add(QgsRasterLayer(p, self.t('lyr_bg'), 'gdal'), False)
        if self.ld_zones.isChecked():
            for p in sorted(glob.glob(os.path.join(out, '05_wektory', '*_strefy.gpkg'))):
                add(QgsVectorLayer(p, self.t('lyr_zones'), 'ogr'))
        if self.ld_tables.isChecked():
            for p in sorted(glob.glob(os.path.join(out, '01_tabele', '*.csv'))):
                uri = pathlib.Path(p).as_uri() + '?delimiter=,&encoding=UTF-8&detectTypes=yes&geomType=none'
                add(QgsVectorLayer(uri, os.path.basename(p), 'delimitedtext'), False)
        self.status.setText(self.t('layers_added', n=added))
        try:
            self.iface.mapCanvas().refresh()
        except Exception:
            pass
