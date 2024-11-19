![SpiceMonkey banana icon](banana-icon.png)
# SpiceMonkey
A self-contained Python tool to simulate and optimize AC electrical circuits.

It takes a SPICE-like description of a circuit, uses Modified Nodal Analysis (MNA) to find the transfer function in the Laplace domain using symbolic expressions (sympy) and it uses least-squares to optimize the elements until we get a desired frequency response

It has a GUI based on wxPython that is multiplatform.

This is meant to be a "table-top" tool running on lab PCs to help you understand your circuit better while you are building it on the protoboard.

For bug reporting use GitHub "Issues" feature

# Screenshot (Linux)

![SpiceMonkey screenshot](screenshot.png)

# Screenshot (MacOS)

![SpiceMonkey screenshot](screenshot_mac.png)

# Setup instructions 

In general:
1. Install at least Python 3.13 or newer
2. Install all the required Python libraries: `pip install -r requirements.txt`
3. Run `python main.py` in your terminal to launch the GUI

## MS Windows

## MacOS

## Linux

# License

Copyright 2024 Victor Pecanins

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

