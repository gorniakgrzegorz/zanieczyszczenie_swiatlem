# -*- coding: utf-8 -*-
"""Punkt wejścia wtyczki: menu, pasek narzędzi, okno. / Plugin entry point: menu, toolbar, dialog."""
import os

from qgis.PyQt.QtGui import QIcon
try:
    from qgis.PyQt.QtGui import QAction          # Qt6 / QGIS 4
except ImportError:
    from qgis.PyQt.QtWidgets import QAction      # Qt5 / QGIS 3

NAME = 'Zanieczyszczenie światłem nocnym / Night-time Light Pollution'


class NightLightPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None
        self.dir = os.path.dirname(os.path.abspath(__file__))

    def initGui(self):
        icon = QIcon(os.path.join(self.dir, 'icon.png'))
        self.action = QAction(icon, NAME, self.iface.mainWindow())
        self.action.setToolTip(NAME)
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu(NAME, self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        if self.action is not None:
            self.iface.removePluginMenu(NAME, self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action = None
        if self.dialog is not None:
            try:
                if self.dialog.job is not None and self.dialog.job.running():
                    self.dialog.job.kill()
            except Exception:
                pass
            self.dialog.close()
            self.dialog.deleteLater()
            self.dialog = None

    def run(self):
        if self.dialog is None:
            from .dialog import NightLightDialog
            self.dialog = NightLightDialog(self.iface, self.iface.mainWindow())
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
