import sys, numpy as np, geopandas as gpd
from shapely.geometry import Point
CX, CY = 500000, 500000
out = sys.argv[1]; wariant = sys.argv[2] if len(sys.argv) > 2 else 'atrybut'
park = Point(CX, CY).buffer(5000, 64); ot = Point(CX, CY).buffer(7000, 64).difference(park)
if wariant == 'atrybut':
    g = gpd.GeoDataFrame({'nazwa': ['Park testowy', 'Otulina parku testowego']}, geometry=[park, ot], crs='EPSG:2180')
elif wariant == 'jeden':
    g = gpd.GeoDataFrame({'nazwa': ['AOI']}, geometry=[Point(CX, CY).buffer(7000, 64)], crs='EPSG:2180')
else:
    g = gpd.GeoDataFrame({'id': [1, 2]}, geometry=[Point(CX, CY).buffer(7000, 64), ot], crs='EPSG:2180')   # bez atrybutu: większy = park
g.to_file(out, layer='aoi', driver='GPKG'); print('AOI zapisano', out)
