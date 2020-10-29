#image to svg converter
#loic landrieu 2020

import numpy as np
import sys, os
import math
import matplotlib.image as mpimg
import svgwrite
import argparse
import ast

file_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(file_path, "grid-graph/python/bin"))
sys.path.append(os.path.join(file_path, "parallel-cut-pursuit/python/wrappers"))
sys.path.append(os.path.join(file_path, "multilabel-potrace/python/bin"))

from grid_graph import grid_to_graph, edge_list_to_forward_star
from cp_kmpp_d0_dist import cp_kmpp_d0_dist
from multilabel_potrace_shp import multilabel_potrace_shp, Shape
  
def tostr(f):
  return "%5.1f" % f
  
def tochar(f):
  return int(255*f) 
  
def write_svg(polygons, rX, filename, args):
  """
  draw a aset of polygons
  """
  dwg = svgwrite.Drawing(filename=filename, debug=True)
  for i_poly in range(len(polygons)):
    s = []
    for i_part in range(polygons[i_poly].number_of_parts):
      point_indices = range(polygons[i_poly].parts[i_part], polygons[i_poly].parts[i_part+1] if i_part < polygons[i_poly].number_of_parts-1 else polygons[i_poly].points.shape[1])
      xy = [[args.scale_x * (polygons[i_poly].points[0,i]), args.scale_y * (args.lin-polygons[i_poly].points[1,i])] for i in point_indices]
      string_ring = ['M ' + str(xy[0][0]) + " " + str(xy[0][1])]
      string_ring = string_ring + [[tostr(p[0]) + " " + tostr(p[1])] for p in xy[1:] ]
      string_ring = string_ring + ['z']
      s = s + string_ring
    
    if rX.shape[0] == 1:
      color = "rgb(%d,%d,%d)" % (tochar(rX[0,i_poly]), tochar(rX[0,i_poly]), tochar(rX[0,i_poly]))
    elif rX.shape[0] == 3:
      color = "rgb(%d,%d,%d)" % (tochar(rX[0,i_poly]), tochar(rX[1,i_poly]), tochar(rX[2,i_poly]))
    else:
      color = "rgb(%d,%d,%d)" % (tochar(np.random.rand()), tochar(np.random.rand()), tochar(np.random.rand()))

    path = dwg.path(s, stroke_width=args.width, stroke=color if args.contour == '' else args.contour)
    path.fill(color)
    dwg.add(path)
  dwg.save()

def main():
  parser = argparse.ArgumentParser(description='IMG TO VECTOR')
  
  parser.add_argument('-f', '--file', default='lola.jpeg', required=False, help='Input file name')
  parser.add_argument('-r', '--reg', default=1.0, type=float, help='Regularization strength')
  parser.add_argument('-s', '--smooth', default=0.0, type=float, help='Smoothong term. 0 (default) = polygonal, >0 cubic Bezier curves')
  parser.add_argument('-c', '--contour', default='', help='Color of contour, default = none')
  parser.add_argument('-w', '--width', default=2, help='Width of contours')
  parser.add_argument('-o', '--out_size',  type=float, default=500, help='Size of svg outputfile')
  parser.add_argument('-p', '--out_path',  default='', help='Path of svg outputfile default = empty : inputfile.svg ')
  parser.add_argument('-a', '--apply',  default='', help='Function to apply before partition: sqrt, log,')
  parser.add_argument('-t', '--tolerance',  default=1.0, type=float, help= 'how far are lines allowed to deviate from the borders')
  
  args = parser.parse_args()

  if args.out_path[-4:] != '.svg':
    args.out_path = args.out_path + '.svg'
  
  try:
    args.out_size = [float(args.out_size), float(args.out_size)]
  except ValueError:
    args.out_size = ast.literal_eval(args.out_size)
  
  #input raster
  filename, file_extension = os.path.splitext(args.file)
  if file_extension in '.png.jpg.jpeg':
    img = mpimg.imread(args.file).astype('f4')
    if file_extension == '.png':
      img = img[:,:,:3]
    print(img.max())  
    if img.max()>1:
      img = img / 255.0
  elif  file_extension == '.npy':
    img = np.load(args.file).astype('f4')[:,:,0]
  elif file_extension in '.tif.tiff':
    from PIL import Image
    img = np.array(Image.open(args.file)).astype('f4')
    img[img!=img]=0.0
    nodata = True
    img = img / img.max()
  else:
    raise NotImplementedError('unknown file extension %s' % file_extension)
    
  img = np.asfortranarray(img)

  if 'log' in args.apply:
    img = np.log(np.maximum(img,0)+1e-4)
    print(img.shape)
  elif 'sqrt' in args.apply:
    img = np.sqrt(np.maximum(img,0))
    
  args.lin = img.shape[0]
  args.col = img.shape[1]
  max_side = max(args.lin, args.col) 
  args.scale_x, args.scale_y = args.out_size[1]/max_side , args.out_size[0] / max_side 
  args.n_chan = img.shape[-1] if len(img.shape)>2 else 1
  args.n_ver = args.lin * args.col 
  print('Reading image of size %d by %d with %d channels' % (args.lin, args.col, args.n_chan))

  #compute grid
  shape = np.array([args.lin, args.col], dtype = 'uint32')
  first_edge, adj_vertices, connectivities = grid_to_graph(shape, 2, True, True, True)
  #edge weights
  edg_weights = np.ones(connectivities.shape, dtype=img.dtype)
  edg_weights[connectivities==2] = 1/np.sqrt(2)

  #cut pursuit
  reg_strength = args.reg * np.std(img)**2
  comp, rX, dump = cp_kmpp_d0_dist(1, img.reshape((args.n_ver,args.n_chan)).T , first_edge, adj_vertices, edge_weights = reg_strength * edg_weights, cp_it_max=10, cp_dif_tol = 5e-1) 
  print('cp done')

  if 'log' in args.apply:
    rX = np.exp(rX)
  if 'sqrt' in args.apply:
    rX = rX ** 2
  
  #potrace
  polygons = multilabel_potrace_shp(comp.reshape([args.lin, args.col]).astype('uint16'), args.tolerance)
  print('potrace done')

  #format output
  output_path = args.out_path if len(args.out_path)>0 else filename+'.svg'
  write_svg(polygons, rX, output_path, args)

if __name__ == "__main__": 
    main()

