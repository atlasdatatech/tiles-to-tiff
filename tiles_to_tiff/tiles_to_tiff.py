from itertools import count
import urllib.request
import os
import glob
import shutil
from tile_convert import bbox_to_xyz, tile_edges
from osgeo import gdal

from urllib.error import HTTPError, URLError
from urllib.request import urlopen

temp_dir = os.path.join(os.path.dirname(__file__), 'temp')

def make_request(url):
    try:
        with urlopen(url, timeout=10) as response:
            print(response.status)
            return response.read(), response
    except HTTPError as error:
        print(error.status, error.reason)
    except URLError as error:
        print(error.reason)
    except TimeoutError:
        print("Request timed out")

def fetch_tile(x, y, z, tile_source):
    url = tile_source.replace(
        "{x}", str(x)).replace(
        "{y}", str(y)).replace(
        "{z}", str(z))

    if not tile_source.startswith("http"):
        return url.replace("file:///", "")

    path = f'{temp_dir}/{x}_{y}_{z}'
    req = urllib.request.Request(
        url,
        data=None,
        headers={
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) tiles-to-tiff/1.0 (+https://github.com/jimutt/tiles-to-tiff)'
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            with open(path, 'b+w') as f:
                f.write(response.read())
                response.close()
    except HTTPError as error:
        print(error.status, error.reason)
    except URLError as error:
        print(error.reason)
    except TimeoutError:
        print("Request timed out")
    # g = urllib.request.urlopen(req)
    # with open(path, 'b+w') as f:
    #     f.write(g.read())
    #     g.close()
    #     print('file write finished')
    return path


def merge_tiles(input_pattern, output_path):
    vrt_path = temp_dir + "/tiles.vrt"
    gdal.BuildVRT(vrt_path, glob.glob(input_pattern))
    gdal.Translate(output_path, vrt_path)


def georeference_raster_tile(x, y, z, path):
    bounds = tile_edges(x, y, z)
    gdal.Translate(os.path.join(temp_dir, f'{temp_dir}/{x}_{y}_{z}.tif'),
                   path,
                   outputSRS='EPSG:4326',
                   outputBounds=bounds)

def convert(tile_source, output_dir, bounding_box, zoom): 
    lon_min, lat_min, lon_max, lat_max = bounding_box

    # Script start:
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    x_min, x_max, y_min, y_max = bbox_to_xyz(
        lon_min, lon_max, lat_min, lat_max, zoom)

    total = (x_max - x_min + 1) * (y_max - y_min + 1)
    print(f"Fetching & georeferencing {total} tiles")
    counter = 1
    for x in range(x_min, x_max + 1):
        for y in range(y_min, y_max + 1):
            try:
                print(f"{x},{y} fetching")
                png_path = fetch_tile(x, y, zoom, tile_source)
                print(f"{x},{y} fetched")
                georeference_raster_tile(x, y, zoom, png_path)
                print(f"{x},{y} georeferenced")
                counter=counter+1
            except OSError:
                print(f"Error, failed to get {x},{y}")
                pass
            print(f"{counter}{'/'}{total},{counter/total*100:.2f}% completed")


    print("Resolving and georeferencing of raster tiles complete")

    print("Merging tiles")
    merge_tiles(temp_dir + '/*.tif', output_dir + '/merged.tif')
    print("Merge complete")

    shutil.rmtree(temp_dir)
