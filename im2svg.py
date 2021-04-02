# image to svg converter
# loic landrieu 2020

import numpy as np
import sys, os
import matplotlib.image as mpimg
import argparse
import ast

file_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(file_path, "grid-graph/python/bin"))
sys.path.append(os.path.join(file_path, "parallel-cut-pursuit/python/wrappers"))
sys.path.append(os.path.join(file_path, "multilabel-potrace/python/bin"))

from grid_graph import grid_to_graph, edge_list_to_forward_star
from cp_kmpp_d0_dist import cp_kmpp_d0_dist
from multilabel_potrace_svg import multilabel_potrace_svg


def tostr(f):
    return "%5.1f" % f


def tochar(f):
    return int(255 * f)

def char2col(c):
    switcher = {
        "r": [255,0,0],
        "g": [0,255,0],
        "b": [0,0,255],
        "k": [0, 0, 0],
        "w": [255, 255, 255]
    }
    return np.array(switcher.get(c)).astype('uint8')


def main():
    parser = argparse.ArgumentParser(description='IMG TO VECTOR')
    # path and filenames
    parser.add_argument('-f', '--file', default='lola.jpeg', required=False, help='Input file name')
    parser.add_argument('-p', '--out_path', default='', help='Path of svg outputfile default = empty : inputfile.svg ')
    parser.add_argument('-o', '--out_size', type=float, default=500, help='Size of svg outputfile')
    #cosmetic
    parser.add_argument('-lc', '--line_color', default='', help='Color of contour, default = none. supported (r,g,b,k,w), or a char triplet')
    parser.add_argument('-lw', '--line_width', default=1,
                        help='Width of contour in pixels. Default: 1')
    # optimization parameters
    parser.add_argument('-a', '--apply', default='',
                        help='Function to apply before partition: sqrt, log,none (default)')
    parser.add_argument('-r', '--reg', default=1.0, type=float,
                        help='Regularization strength: the higher the lfewer components. Default = 1.0.')
    parser.add_argument('-s', '--smooth', default=1.0, type=float,
                        help='Smoothing term. 0  = polygonal, >0 cubic Bezier curves. Default = 1.0')
    parser.add_argument('-lt', '--line_tolerance', default=1.0, type=float,
                        help='how far are lines allowed to deviate from the borders')
    parser.add_argument('-ct', '--curve_tolerance', default=0.2, type=float,
                        help='max difference area ratio diff between original and simplified polygons. Default=0.2')

    args = parser.parse_args()

    if len(args.out_path) > 3 and args.out_path[-4:] != '.svg':
        args.out_path = args.out_path + '.svg'

    try:
        args.out_size = [float(args.out_size), float(args.out_size)]
    except ValueError:
        args.out_size = ast.literal_eval(args.out_size)



    # input raster
    filename, file_extension = os.path.splitext(args.file)
    if file_extension in '.png.jpg.jpeg':
        img = mpimg.imread(args.file).astype('f4')
        if file_extension == '.png':
            img = img[:, :, :3]
        print(img.max())
        if img.max() > 1:
            img = img / 255.0
    elif file_extension == '.npy':
        img = np.load(args.file).astype('f4')[:, :, 0]
    elif file_extension in '.tif.tiff':
        from PIL import Image
        img = np.array(Image.open(args.file)).astype('f4')
        img[img != img] = 0.0
        nodata = True
        img = img / img.max()
    else:
        raise NotImplementedError('unknown file extension %s' % file_extension)

    img = np.asfortranarray(img)

    if 'log' in args.apply:
        img = np.log(np.maximum(img, 0) + 1e-4)
        print(img.shape)
    elif 'sqrt' in args.apply:
        img = np.sqrt(np.maximum(img, 0))

    args.lin = img.shape[0]
    args.col = img.shape[1]
    max_side = max(args.lin, args.col)
    args.scale_x, args.scale_y = args.out_size[1] / max_side, args.out_size[0] / max_side
    args.n_chan = img.shape[-1] if len(img.shape) > 2 else 1
    args.n_ver = args.lin * args.col
    print('Reading image of size %d by %d with %d channels' % (args.lin, args.col, args.n_chan))

    # compute grid
    shape = np.array([args.lin, args.col], dtype='uint32')
    first_edge, adj_vertices, connectivities = grid_to_graph(shape, 2, True, True, True)
    # edge weights
    edg_weights = np.ones(connectivities.shape, dtype=img.dtype)
    edg_weights[connectivities == 2] = 1 / np.sqrt(2)

    # cut pursuit
    reg_strength = args.reg * np.std(img) ** 2
    comp, rX, dump = cp_kmpp_d0_dist(1, img.reshape((args.n_ver, args.n_chan)).T, first_edge, adj_vertices,
                                     edge_weights=reg_strength * edg_weights, cp_it_max=10, cp_dif_tol=1e-1)
    print('cp done')

    if 'log' in args.apply:
        rX = np.exp(rX)
    if 'sqrt' in args.apply:
        rX = rX ** 2

    # potrace
    # polygons = multilabel_potrace_shp(comp.reshape([args.lin, args.col]).astype('uint16'), args.tolerance)

    print('potrace done')

    # format output
    output_path = args.out_path if len(args.out_path) > 0 else filename + '.svg'
    if len(args.line_color) == 0:
        line_color = None
    elif len(args.line_color) == 1:
        line_color = char2col(args.line_color)
    else:
        try:
            line_color = np.array(ast.literal_eval(args.line_color)).astype('uint8')
        except SyntaxError:
            print("line_color should be either empty, r,g,b,k,w or a char triplet.")

    multilabel_potrace_svg(np.resize(comp, (args.lin, args.col)), output_path, straight_line_tol=args.line_tolerance, \
                           smoothing=args.smooth, curve_fusion_tol=args.curve_tolerance, \
                           comp_colors=(255 * rX).astype('uint8'), line_color=line_color, line_width=args.line_width)

    # write_svg(polygons, rX, output_path, args)


if __name__ == "__main__":
    main()
