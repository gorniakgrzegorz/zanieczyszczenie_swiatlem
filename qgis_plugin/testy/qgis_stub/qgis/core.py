"""Minimalne zaślepki qgis.core do testu okna bez QGIS."""
import os, shutil
from PyQt5.QtCore import QSettings

class Qgis:
    pass

class QgsWkbTypes:
    class GeometryType:
        PolygonGeometry = 2

class QgsApplication:
    @staticmethod
    def qgisSettingsDirPath():
        return os.environ.get('ZSN_TEST_PROFILE', '/tmp/zsn_profile') + '/'
    @staticmethod
    def locale():
        return os.environ.get('ZSN_TEST_LOCALE', 'pl_PL')

_S = {}
class QgsSettings:
    def value(self, k, d=None):
        return _S.get(k, d)
    def setValue(self, k, v):
        _S[k] = v

class _Ext:
    def __init__(self): pass

class QgsGeometry:
    @staticmethod
    def fromRect(r): return r

class QgsDistanceArea:
    def setSourceCrs(self, *a): pass
    def setEllipsoid(self, *a): pass
    def measureArea(self, r): return 123456789.0

class QgsMapLayer:
    def __init__(self, name):
        self._name = name
    def name(self): return self._name

class QgsVectorLayer(QgsMapLayer):
    def __init__(self, path=None, name='x', provider='ogr', polygon=True, nfeat=2):
        super().__init__(name)
        self.path = path; self.polygon = polygon; self.nfeat = nfeat; self.src = None
    def isValid(self): return True
    def geometryType(self): return 2 if self.polygon else 0
    def crs(self): return None
    def extent(self): return None
    def featureCount(self): return self.nfeat
    def selectedFeatureCount(self): return 0

class QgsRasterLayer(QgsMapLayer):
    def __init__(self, path, name, provider='gdal'):
        super().__init__(name); self.path = path
    def isValid(self): return os.path.isfile(self.path)

class _Node:
    def __init__(self, layer=None): self.layer = layer; self.checked = True
    def setItemVisibilityChecked(self, v): self.checked = bool(v)

class _Group:
    def __init__(self, name): self.name = name; self.nodes = []
    def addLayer(self, layer):
        n = _Node(layer); self.nodes.append(n); return n

class _Root:
    def __init__(self): self.groups = []
    def insertGroup(self, i, name):
        g = _Group(name); self.groups.insert(i, g); return g

class _Project:
    def __init__(self):
        self.layers = {}; self.root = _Root(); self.n = 0
    def mapLayers(self): return dict(self.layers)
    def mapLayer(self, lid): return self.layers.get(lid)
    def addMapLayer(self, layer, add=True):
        self.n += 1; self.layers['l%d' % self.n] = layer; return layer
    def layerTreeRoot(self): return self.root
    def transformContext(self): return None
    def ellipsoid(self): return 'WGS84'

_P = _Project()
class QgsProject:
    @staticmethod
    def instance(): return _P

class QgsVectorFileWriter:
    NoError = 0
    class SaveVectorOptions:
        pass
    @staticmethod
    def writeAsVectorFormatV3(layer, path, ctx, opts):
        shutil.copy(os.environ['ZSN_TEST_AOI'], path)
        return (0, '', path, '')
