# img2svg

Approximates images in svg format. Now supports Bezier curves!

|      input image           |      output svg (polygonal)|
| -------------------------- | -------------------------- |
|<img src="https://i.imgur.com/LKEPvRb.jpg" width="300"> |<img src="https://user-images.githubusercontent.com/1902679/92108251-59eaa680-ede7-11ea-8206-a553209782f8.png" width="300">|

## 1. Cloning

Use the recursive submodule option to clone the necessary submodules. 
```
git clone --recurse-submodules https://github.com/loicland/img2svg
```
Otherwise, clone the following repo in the root:
- https://gitlab.com/1a7r0ch3/parallel-cut-pursuit
- https://gitlab.com/1a7r0ch3/multilabel-potrace
- https://gitlab.com/1a7r0ch3/grid-graph

## 2. Requirement

You need `numpy`, `matplotlib`
```
pip install numpy matplotlib
```

## 3. Installation

In a command prompt run:
```
python setup.py build_ext
```
Test with
```
python img2svg.py
```
## 4. Usage

```
python img2svg -f filename -r reg_strength -c contour_color -s stroke_width -o out_size -p output_path
```
With
- -f --file: path to image
- -r --reg_strength : how much simplification to do. Default = 1.0
- -c --contour_color: color of the contour, if any. Default = \'\' (no contour). Exemple : \'red\'
- -s --stroke_width: width of the contour (only if contour_color != \'\'). Default = 2.0 (thick)
- -o --out_size: size of the largest side of the image. Default = 500
- -p --output_path: output path. Default = replace the image extension by \`svg\`
- -a --apply: Function to apply before partition: sqrt, log, none (default)
- -s --smooth: Smoothing term. 0  = polygonal, >0 cubic Bezier curves. Default = 1.0
- -lt --line_tolerance: How far are lines allowed to deviate from the borders. Default = 1.0
- -ct --curve_tolerance: max difference area ratio diff between original and simplified polygons. Default=0.2

