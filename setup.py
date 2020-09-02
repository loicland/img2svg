#----------------------------------------------------------------------#
#          distutils setup script for compiling python extensions      #
#----------------------------------------------------------------------#
""" 
Compilation command: python setup.py build_ext
Hugo Raguet, adapted by Loic Landrieu, 2020
"""

from distutils.core import setup, Extension
from distutils.command.build import build
from distutils.ccompiler import new_compiler
import numpy
import shutil # for rmtree, os.rmdir can only remove _empty_ directory
import os 
import re

###  targets and compile options  ###

include_dirs = [numpy.get_include(), # find the Numpy headers
                "../include"]
# compilation and linkage options
# MIN_OPS_PER_THREAD roughly controls parallelization, see doc in README.md
if os.name == 'nt': # windows
    extra_compile_args = ["/std:c++11", "/openmp",
                          "-DMIN_OPS_PER_THREAD=10000"]
    extra_link_args = ["/lgomp"]
elif os.name == 'posix': # linux
    extra_compile_args = ["-std=c++11", "-fopenmp",
                          "-DMIN_OPS_PER_THREAD=10000"]
    extra_link_args = ["-lgomp"]
else:
    raise NotImplementedError('OS not yet supported.')

###  auxiliary functions  ###
class build_class(build):
    def initialize_options(self):
        build.initialize_options(self)
        self.build_lib = "bin" 
    def run(self):
        build_path = self.build_lib

def purge(dir, pattern):
    for f in os.listdir(dir):
        if re.search(pattern, f):
            os.remove(os.path.join(dir, f))

### ============ GRID GRAPH ============  ###
# ensure right working directory
tmp_work_dir = os.path.realpath(os.curdir)
os.chdir(os.path.join(os.path.realpath(os.path.dirname(__file__)), './grid-graph/python'))
name = "grid_graph"

if not os.path.exists("bin"):
    os.mkdir("bin")

# remove previously compiled lib
purge("bin/", "grid_graph")

###  compilation  ###
mod = Extension(
        name,
        # list source files
        ["cpython/grid_graph_cpy.cpp",
         "../src/edge_list_to_forward_star.cpp",
         "../src/grid_to_graph.cpp"],
        include_dirs=include_dirs,
        extra_compile_args=extra_compile_args,
        extra_link_args=extra_link_args)

setup(name=name, ext_modules=[mod], cmdclass=dict(build=build_class))

###  postprocessing  ###
try:
    shutil.rmtree("build") # remove temporary compilation products
except FileNotFoundError:
    pass

### ============ MULTILABEL POTRACE ============  ###

os.chdir('../../multilabel-potrace/python')
name = "multilabel_potrace_shp"
include_dirs = [numpy.get_include(), # find the Numpy headers
                "../include", "../include/potrace"]

if not os.path.exists("bin"):
    os.mkdir("bin")

if not os.path.exists("build"):
    os.mkdir("build")

# remove previously compiled lib
purge("bin/", "multilabel_potrace_shp")

###  compilation  ###

# compile potrace sources with C compiler
compiler = new_compiler()
C_sources = ["../src/potrace/trace.c", "../src/potrace/curve.c"]
compiler.compile(C_sources, include_dirs=include_dirs)
extra_objects = []
object_extension = ".o" if  os.name == "posix" else ".obj"
for o in C_sources:
    obj = os.path.join("build", os.path.splitext(os.path.split(o)[1])[0]+object_extension)
    shutil.move(os.path.splitext(o)[0]+object_extension, obj)
    extra_objects.append(obj)


# compile multilabel potrace with C++ compiler and create module
mod = Extension(
        name,
        # list source files
        ["../src/multilabel_potrace_shp.cpp",
         "../src/multilabel_potrace.cpp",
         "./cpython/multilabel_potrace_shp_cpy.cpp"],
        include_dirs=include_dirs,
        extra_objects=extra_objects,
        extra_compile_args=extra_compile_args,
        extra_link_args=extra_link_args)

setup(name=name, ext_modules=[mod], cmdclass=dict(build=build_class))                

###  postprocessing  ###
try:
    shutil.rmtree("build") # remove temporary compilation products
except FileNotFoundError:
    pass

### ============ PARALLEL CUT PURSUIT ============  ###

os.chdir('../../parallel-cut-pursuit/python')
name = "cp_kmpp_d0_dist_cpy"
include_dirs = [numpy.get_include(), # find the Numpy headers
                "../include"]
###  preprocessing  ###
# ensure right working directory

if not os.path.exists("bin"):
    os.mkdir("bin")

# remove previously compiled lib
purge("bin/", "cp_kmpp_d0_dist_cpy")

###  compilation  ###

mod = Extension(
        name,
        # list source files
        ["cpython/cp_kmpp_d0_dist_cpy.cpp", "../src/cp_kmpp_d0_dist.cpp",
         "../src/cut_pursuit_d0.cpp", "../src/cut_pursuit.cpp",
         "../src/maxflow.cpp"], 
        include_dirs=include_dirs,
        extra_compile_args=extra_compile_args,
        extra_link_args=extra_link_args)
setup(name=name, ext_modules=[mod], cmdclass=dict(build=build_class))

###  postprocessing  ###
try:
    shutil.rmtree("build") # remove temporary compilation products
except FileNotFoundError:
    pass

os.chdir(tmp_work_dir) # get back to initial working directory
