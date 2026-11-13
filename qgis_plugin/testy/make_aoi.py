import sys, numpy as np, geopandas as gpd
from shapely.geometry import Point
CX, CY = 500000, 500000
out = sys.argv[1]; wariant = sys.argv[2] if len(sys.argv) > 2 else 'atrybut'
park = Point(CX, CY).buffer(5000, 64); ot = Point(CX, CY).buffer(7000, 64).difference(park)
if wariant == 'atrybut':
    g = gpd.GeoDataFrame({'nazwa': ['Park testowy', 'Otulina parku testowego']}, geometry=[park, ot], crs='EPSG:2180')
elif wariant == 'jeden':
    g = gpd.GeoDataFrame({'nazwa': ['AOI']}, geometry=[Point(CX, CY).buffer(7000, 64)], crs='EPSG:2180')
elif wariant == 'dowolny':       # dowolny obszar poza Polską (okolice Barcelony), dwa rozłączne nieregularne obiekty bez atrybutów park/otulina
    from shapely.geometry import Polygon
    import os
    A = Polygon([(2.10, 41.35), (2.22, 41.33), (2.27, 41.40), (2.20, 41.46), (2.11, 41.43)])
    B = Polygon([(2.30, 41.42), (2.36, 41.42), (2.36, 41.47), (2.30, 41.47)])
    g = gpd.GeoDataFrame({'id': [1, 2], 'opis': ['pole A', 'pole B']}, geometry=[A, B], crs='EPSG:4326')
    c = gpd.GeoSeries([A.union(B).centroid], crs='EPSG:4326').to_crs('EPSG:32631').iloc[0]
    open(os.path.join(os.path.dirname(out), 'center.txt'), 'w').write(f'EPSG:32631 {c.x:.0f} {c.y:.0f}')
else:
    g = gpd.GeoDataFrame({'id': [1, 2]}, geometry=[Point(CX, CY).buffer(7000, 64), ot], crs='EPSG:2180')   # bez atrybutu: większy = park
g.to_file(out, layer='aoi', driver='GPKG'); print('AOI zapisano', out)
