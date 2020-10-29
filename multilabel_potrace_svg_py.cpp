/*=============================================================================
 * Python extension module for Multilabel Potrace
 * 
 * Hugo Raguet + Loic Landrieu 2020
 *===========================================================================*/
#include <cstdint>
#include <iostream> // for debugging
#include <limits>
#include <cstdio>
#define PY_SSIZE_T_CLEAN
#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include <Python.h>
/* header of Python 2 do not include it automatically */
#if PY_MAJOR_VERSION <= 2
#include <structseq.h>
#endif
#include <numpy/arrayobject.h>
#include "multilabel_potrace.hpp"
typedef uint8_t color_t; // color 0-255
#define NPY_COLOR NPY_UINT8
#define COLOR_STRING "uint8"
typedef uint16_t comp_t; // we do not expect more than 65535 components
#define NPY_COMP NPY_UINT16
#define NPY_COMP_ALT NPY_INT16 // can be safely cast as NPY_COMP
#define COMP_T_STRING "uint16 or int16"
typedef uint16_t int_coor_t; // no dimension larger than 65535
#define INT_COOR_T_STRING "uint16"
typedef float real_coor_t;
#define REAL_COOR_T_STRING "float"

/**  create the Shape type, as a struct sequence type, aka named tuple  **/

static PyStructSequence_Field Shape_fields[] = {
    {"number_of_parts", "the number of rings in the polygon"},
    {"number_of_points", "the total number of points for all rings"},
    {"parts",
     "numpy integers array of length number_of_parts; store, for each\n"
     "ring, the index of its first point in the 'points' array"},
    {"curves",
     "numpy float array of shape 3-by-2-by-number_of_points; the points for\n"
     "each ring of the polygon are stored end to end; the first point of a\n"
     "ring is repeated at the end; the points for ring 2 follow the points\n"
     "for ring 1, and so on; the 'parts' array holds the array index of the\n"
     "starting point for each ring; there is no delimiter array between\n"
     "rings"},
    {NULL}
};

static PyStructSequence_Desc Shape_desc = {
    "Shape", /* name */
    "The data structure of the polygon is a python \"named tuple\", inspired\n"
    "by the shapefile specifications [2], with the following entries:\n"
    "'number_of_parts', 'number_of_points', 'parts' and\n"
    "'points'.", /* docstring */
    Shape_fields, /* fields */
    4, /* number of fields visible to the Python side (if used as tuple) */
};

/* static global object; initialized and passed to the module at module init */
static PyTypeObject Shape;

/* static global character string for errors */
static char err_msg[1000];

/* actual interface */
#if PY_VERSION_HEX >= 0x03040000 // Py_UNUSED suppress warning from 3.4
static PyObject* multilabel_potrace(PyObject* Py_UNUSED(self),
    PyObject* args, PyObject* kwargs)
{ 
#else
static PyObject* multilabel_potrace(PyObject* self, PyObject* args, //)
    PyObject* kwargs)
{   (void) self; // suppress unused parameter warning
#endif

    /***  get and check inputs  ***/
    PyArrayObject *py_comp_assign;
    PyArrayObject *py_comp_color;
    string output_file;
    shp_real_t straight_line_tol = 1.0;
    shp_real_t curve_fusion_tol = 0.2;
    shp_real_t smoothing = 1.0;
    shp_real_t stroke_width = 0.2;
    string stroke_color = '';

    const char* keywords[] = {"", "", "output_file", "straight_line_tol", "curve_fusion_tol", "smoothing",  "stroke_width", "stroke_color", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|d", (char**) keywords,
				     &py_comp_assign, &py_comp_color, &output_file, &straight_line_tol, &curve_fusion_tol, &smoothing, &stroke_width, &stroke_color)){
        return NULL;s
    }

    if (!PyArray_Check(py_comp_assign) || !PyArray_Check(py_comp_color)){
        PyErr_SetString(PyExc_TypeError, "Multilabel potrace : argument "
            "'comp_assign' and 'color_array' must be a numpy arrays.");
        return NULL;
    }

    if (PyArray_TYPE(py_comp_assign) != NPY_COMP &&
        PyArray_TYPE(py_comp_assign) != NPY_COMP_ALT){
        PyErr_SetString(PyExc_TypeError, "Multilabel potrace : elements "
            "'comp_assign' must be a of type " COMP_T_STRING ".");
        return NULL;
    }

    if (PyArray_TYPE(py_comp_color) != NPY_COLOR){
        PyErr_SetString(PyExc_TypeError, "Multilabel potrace : elements "
            "'comp_color' must be a of type " COLOR_STRING ".");
        return NULL;
    }

    if (PyArray_NDIM(py_comp_assign) != 2){
        std::sprintf(err_msg, "Multilabel potrace : argument 'comp_assign' "
            "must be two-dimensional (%i dimensions given).", 
            PyArray_NDIM(py_comp_assign));
        PyErr_SetString(PyExc_TypeError, err_msg);
        return NULL;
    }
    
    const comp_t* comp_assign = (comp_t*) PyArray_DATA(py_comp_assign);
    const npy_intp* dims = PyArray_DIMS(py_comp_assign);
    const comp_t* comp_color = (color_t*) PyArray_DATA(py_comp_color);
    const npy_intp* dims_color = PyArray_DIMS(py_comp_color);

    if (PyArray_NDIM(py_comp_color) != 2 &&
        dims[0] != dims_color[0] &&
	dims_color[0] != 3){
        std::sprintf(err_msg, "Multilabel potrace : argument 'comp_color' "
            "must be of dimension n_comp times 3  (%i dimensions given).", 
            PyArray_NDIM(py_comp_color));
        PyErr_SetString(PyExc_TypeError, err_msg);
        return NULL;
    }

    if (dims[0] > std::numeric_limits<int_coor_t>::max() ||
        dims[1] > std::numeric_limits<int_coor_t>::max()){
        std::sprintf(err_msg, "Multilabel potrace shp: currently, integer "
            "coordinates are represented with " INT_COOR_T_STRING " type, thus"
            "no input dimension can exceed %li (%li-by-%li given)",
            (long) std::numeric_limits<int_coor_t>::max(), dims[0], dims[1]);
            PyErr_SetString(PyExc_ValueError, err_msg);
        return NULL;
    }

    /* The C++ routine assumes column-major internal memory represention of the
     * raster; but running on a row-major format is equivalent to working on
     * the transposed raster matrix; the dimensions and coordinates must be
     * transformed accordingly */
    const bool transpose = PyArray_IS_C_CONTIGUOUS(py_comp_assign);

    int_coor_t width, height;
    if (transpose){
        width = dims[0];
        height = dims[1];
    }else{
        height = dims[0];
        width = dims[1];
    }

    comp_t number_of_components = 0;
    for (size_t i = 0; i < (size_t) width*height; i++){
        if (comp_assign[i] > number_of_components){
            number_of_components = comp_assign[i];
        }
    }
    number_of_components += 1;

    /***  process the raster  ***/
    Multi_potrace_shp<comp_t, int_coor_t>* mp_shp = 
      new Multi_potrace<comp_t, int_coor_t, real_coor_t >
            (comp_assign, width, height, number_of_components);

    mp_shp->set_straight_line_tolerance(straight_line_tol);
    mp_shp->set_smoothing(smoothing, curve_fusion_tol);
    mp_shp->compute_polygons();

    /* std::cout << *mp_shp << std::endl; // for debugging */

    /***  create and fill outputs  ***/
    /* WARNING: no check for successful allocations is performed */

    PyObject* py_shp_polygons = PyList_New(number_of_components);
    for (comp_t comp = 0; comp < number_of_components; comp++){
        /**  retrieve each field  **/
        const Multi_potrace_shp<comp_t, int_coor_t>::Shp_polygon& shp_poly =
            mp_shp->get_polygon(comp);

        /* bounding box */
        npy_intp size_py_bb[] = {4};
        PyArrayObject* py_bb = (PyArrayObject*) PyArray_Zeros(1, size_py_bb,
            PyArray_DescrFromType(NPY_SHP_REAL), 1);
        shp_real_t* bbox = (shp_real_t*) PyArray_DATA(py_bb);
        bbox[0] = shp_poly.bounding_box.lower_left.x;
        bbox[1] = shp_poly.bounding_box.lower_left.y;
        bbox[2] = shp_poly.bounding_box.upper_right.x;
        bbox[3] = shp_poly.bounding_box.upper_right.y;

        /* number of parts */
        PyObject* py_nparts = PyLong_FromLong(shp_poly.number_of_parts);

        /* number of points */
        PyObject* py_npoints = PyLong_FromLong(shp_poly.number_of_points);

        /* parts */
        npy_intp size_py_parts[] = {shp_poly.number_of_parts};
        PyArrayObject* py_parts = (PyArrayObject*) PyArray_Zeros(1,
            size_py_parts, PyArray_DescrFromType(NPY_SHP_INT), 0);
        shp_int_t* parts = (shp_int_t*) PyArray_DATA(py_parts);
        for (int i = 0; i < shp_poly.number_of_parts; i++){
            parts[i] = shp_poly.parts[i];
        }

        /* points */
        npy_intp size_py_points[] = {2, shp_poly.number_of_points};
        PyArrayObject* py_points = (PyArrayObject*) PyArray_Zeros(2,
            size_py_points, PyArray_DescrFromType(NPY_SHP_REAL), 0);
        shp_real_t* points = (shp_real_t*) PyArray_DATA(py_points);
        /* last argument 0 in the call to PyArray_Zeros above specifies
         * that the points array is C-contiguous i.e. row-major format */
        shp_real_t* points_x = points;
        shp_real_t* points_y = points + shp_poly.number_of_points;
        for (int i = 0; i < shp_poly.number_of_points; i++){
            if (transpose){
            /* Since the coordinate system put the origin at the lower-left
             * corner of the raster, a transposition corresponds to a symmetry
             * along the upper-left to lower-right main diagonal, and a
             * translation; recall that width and height have been swapped */
                points_x[i] = height - shp_poly.points[i].y;
                points_y[i] = width - shp_poly.points[i].x;
            }else{
                points_x[i] = shp_poly.points[i].x;
                points_y[i] = shp_poly.points[i].y;
            }
        }

        /**  create the Shape named tuple and put it in the list  **/
        PyObject* py_shp_poly = PyStructSequence_New(&Shape);
        PyStructSequence_SET_ITEM(py_shp_poly, 0, (PyObject*) py_bb);
        PyStructSequence_SET_ITEM(py_shp_poly, 1, py_nparts);
        PyStructSequence_SET_ITEM(py_shp_poly, 2, py_npoints);
        PyStructSequence_SET_ITEM(py_shp_poly, 3, (PyObject*) py_parts);
        PyStructSequence_SET_ITEM(py_shp_poly, 4, (PyObject*) py_points);

        PyList_SET_ITEM(py_shp_polygons, comp, py_shp_poly);
    }

    /***  clean up and return; all PyObject references have been passed  ***/
    delete mp_shp;

    return py_shp_polygons;
}

static const char* documentation = 
"shp_polygons = multilabel_potrace_shp(comp_assign, straight_line_tol = 1.0)\n"
"\n"
"Extract and simplifies contours delimiting homogeneous connected components\n"
"within a 2D grid structure (typically, pixels of an image). Resulting\n"
"polygons are stored following shapefile specifications.\n"
"\n"
"Simplifications is done by an adaptation of the potrace software by Peter\n"
"Selinger [1] to multilabel rasters (i.e. with more than two colors).\n"
"\n"
"NOTA: by default, components are identified using uint16 identifiers;\n"
"this can be changed in the sources if more than 65535 components are\n"
"expected, or if the number of components never exceeds 255 and memory is\n"
"critical (recompilation is necessary)\n"
"\n"
"INPUTS:\n"
"comp_assign - multilabel raster image, assigning a component identifier to\n"
"    each pixel, given as a numpy two-dimensional array of " COMP_T_STRING " elements.\n"
"\n"
"    Components are required to be connected (in the 8-neighbors\n"
"    connectivity sense); a nonconnected component would results in a\n"
"    polygon with several exterior rings (see OUTPUTS) and cause bugs.\n"
"\n"
"    Usually, the component identifiers start at 0, and are sequential up\n"
"    to the highest identifier, but this is not compulsory; each identifier\n"
"    between 0 and the highest which not present in the input raster results\n"
"    in an empty polygon at the corresponding index in the output list.\n"
"straight_line_tol - fidelity to the raster: how far (in l1 distance, pixel\n"
"    unit) from a raw border can a straight line approximate it; higher\n"
"    values favor coarse polygons with less line segments.\n"
"\n"
"OUTPUTS:\n"
"shp_polygons - a list indexed by the component identifiers, containing the\n"
"    polygons delimiting the corresponding component.\n"
"\n"
"    The data structure of the polygon is a python named tuple, inspired by\n"
"    the shapefile specifications [2], with the following entries:\n"
"    - 'bounding_box': a numpy array of float of length 4; store the\n"
"       bounding box of the polygon, in the order Xmin, Ymin, Xmax, Ymax\n"
"    - 'number_of_parts': an integer, the number of rings in the polygon\n"
"    - 'number_of_points': an integer, the total number of points for all\n"
"       rings\n"
"    - 'parts': numpy array of integers of length number_of_parts; store,\n"
"       for each ring, the index of its first point in the 'points' array\n"
"    - 'points': numpy array of float or shape 2-by-number_of_points;\n"
"       the points for each ring of the polygon are stored end to end;\n"
"       the first point of a ring is repeated at the end; the points for\n"
"       ring 2 follow the points for ring 1, and so on; the 'parts' array\n"
"       holds the array index of the starting point for each ring; there is\n"
"       no delimiter array between rings\n"
"\n"
"As usual in planar coordinate system but in contrast to matrix indexing,\n"
"the origin is put at the lower-left corner of the raster, the x-axis grows\n"
"left-to-right, and the y-axis grows bottom-to-top. Base unit sizes are the\n"
"pixels sides, so that the corners of the pixels have integer coordinates.\n"
"\n"
"Parallel implementation with OpenMP API.\n"
"\n"
"References:\n"
"\n"
"[1] P. Selinger, Potrace: a polygon-based tracing algorithm, 2003,\n"
"http://potrace.sourceforge.net/\n"
"\n"
"[2] ESRI Shapefile Technical Description, Environmental Systems Research\n"
"Institute, Inc., 1998, \n"
"https://www.esri.com/library/whitepapers/pdfs/shapefile.pdf\n"
"\n"
"Hugo Raguet 2020\n";



static PyMethodDef multilabel_potrace_shp_methods[] = {
    {"multilabel_potrace_shp", (PyCFunction) multilabel_potrace_shp,
        METH_VARARGS | METH_KEYWORDS, documentation},
    {NULL, NULL, 0, NULL}
};

/* module initialization */
#if PY_MAJOR_VERSION >= 3
/* Python version 3 */
static struct PyModuleDef multilabel_potrace_shp_module = {
    PyModuleDef_HEAD_INIT,
    "multilabel_potrace_shp", /* name of module */
    /* module documentation, may be null */
    "wrapper for Multilabel Potrace SHP, with special named tuple type\n"
    "\"Shape\" for the resulting polygons following shapefile specifications.",
    -1,   /* size of per-interpreter state of the module,
             or -1 if the module keeps state in global variables. */
    multilabel_potrace_shp_methods, /* actual methods in the module */
    NULL, /* multi-phase initialization, may be null */
    NULL, /* traversal function, may be null */
    NULL, /* clearing function, may be null */
    NULL  /* freeing function, may be null */
};

PyMODINIT_FUNC
PyInit_multilabel_potrace_shp(void)
{
    import_array() /* IMPORTANT: this must be called to use numpy array */

    PyObject* m;

    /* create the module */
    m = PyModule_Create(&multilabel_potrace_shp_module);
    if (!m){ return NULL; }

    /* add the Shape struct sequence to the module */
    PyStructSequence_InitType(&Shape, &Shape_desc);
    Py_INCREF(&Shape);
    if (PyModule_AddObject(m, "Shape", (PyObject*) &Shape) < 0) {
        Py_DECREF(&Shape);
        Py_DECREF(m);
        return NULL;
    }

    return m;
}

#else

/* module initialization */
/* Python version 2 */
PyMODINIT_FUNC
initmultilabel_potrace_shp(void)
{
    import_array() /* IMPORTANT: this must be called to use numpy array */

    PyObject* m;

    m = Py_InitModule("multilabel_potrace_shp",
            multilabel_potrace_shp_methods);
    if (!m){ return; }

    /* add the Shape struct sequence to the module */
    PyStructSequence_InitType(&Shape, &Shape_desc);
    Py_INCREF(&Shape);
    if (PyModule_AddObject(m, "Shape", (PyObject*) &Shape) < 0) {
        Py_DECREF(&Shape);
        Py_DECREF(m);
        return;
    }
}

#endif
