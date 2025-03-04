from NumEng import *
import re
import numpy as np
import sympy as sp
from sympy.utilities.lambdify import lambdify
import time
from typing import Callable
from sympy.parsing.sympy_parser import parse_expr
from AppState import AppState

import sys, os
#sys.path.insert(0, "/home/peca/Repos/scipy-leastsquares-callback-new/build-install/lib/python3/dist-packages")
#from scipy.optimize import least_squares

from vpm_least_squares.least_squares import least_squares
from scipy.optimize import OptimizeResult, differential_evolution, Bounds

# The circuit solving engine is based on MNA (Modified Nodal Analysis)
# References:
# - Farid N. Najm - Circuit Simulation-Wiley-IEEE Press (2010)
#   Errata for the book: https://www.eecg.utoronto.ca/~najm/simbook/errata.pdf
# - Video tutorials about MNA, Prof. Shanthi Pavan (IIT Madras):
#   https://www.youtube.com/watch?v=43eM-axd1mU
# - Implementation in MATLAB:
#   https://lpsa.swarthmore.edu/Systems/Electrical/mna/MNA6.html
# - SLICAP from TUDelft: Similar idea but requires Maxima CAS
#   https://analog-electronics.tudelft.nl/slicap/SLiCAP_python/slicap_python.html
#
#  The design matrix:
#
#                  Coefficients to    Coefficients to    Vector of       Vector of
#                  Node voltages      Branch currents    Unknowns        Knowns
#                --------------------------------       ----------      ----------
#               |                      |         |      |         |     |         |
#   Equations   |       N*N            |  N*B    |      |  N*1    |     |  N*1    |   Independent isources
#   nodes       |                      |         |      | Node    |     |         |
#               |                      |         |   x  | voltages|  =  |         |
#               |                      |         |      |         |     |         |
#               | ---------------------| --------|      | --------|     | --------|
#   Equations   |       B*N            |  B*B    |      |  B*1 Br.|     |  B*1    |   Independent vsources
#   branches    |                      |         |      | Currents|     |         |
#                --------------------------------       ----------      ----------
#

# TODO: Organize data as items in CircuitElement
# This data type is meant to be communication between parser & solver & optimizer
# from typing import NamedTuple
#
# class CircuitElement(NamedTuple):
#     val: str
#     initial: float
#     sym: sp.Symbol  # Problem: this we want as a list because is used in expression based components
#     line: int
#     fixed: bool
#     minval: float
#     maxval: float

# TODO: Divide this class into 4:
# - Engine: Main encapsulation
# - Engine_parser: Spice netlist parser & design matrix generator
# - Engine_optimizer: Least squares optimization
# - Engine_freqresp: Target frequency response generator

class Engine:

    def __init__(self, app_state: AppState, callback: Callable):

        self.app_state = app_state

        # Status (Information or Error) message as string
        # This is meant to be shown in the StatusBar of the GUI
        # So status_msg has to be only one line
        self.status_msg = ""

        # Debug message (Internal algorithm data) as string
        # Printed in the console only if app_state._debug is True
        # debug_msg can be multiple lines
        self.debug_msg = ""

        self.nodes = ["0"]  # Node names, starting by GND node. So we have len(self.nodes)-1 nodes to be solved
        self.branches = None  # Branch currents to be solved

        self.netlist_fields = None  # All fields of the parsed circuit elements
        self.elems_val = None  # Value field of all parsed circuit elements

        self.sources_ac = None  # AC and DC values of fixed I and V sources
        self.sources_dc = None

        self.elems_fixed = None  # Values of the circuit elements with fixed value (not changed)
        self.elems_expr = None  # Expressions of the circuit elements with expression-based values
        self.elems_initial = None  # Initial values of the circuit elements to be optimized

        self.elems_line = None  # Line numbers of all circuit elements (for netlist generation)
        self.expr_lines = None  # Line numbers of expression-based circuit elements (for netlist generation)

        self.minval = None
        self.maxval = None
        self.prefix = ""  # Might be needed to avoid name clash with SymPy default variables (not needed)
        self.sym = None  # Array of symbols with prefix: self.sym["Vin"] = Symbol(xVin)
        self.optimized_lines = None
        self.lines = None

        # Problem matrices.
        # Each one a Hybrid matrix:
        # - Node voltages for all nodes of the circuits except GND
        # - Branch currents for VEHLKT elements (Vsources, VCVS, CCVS, inductors & transformers)
        # - Incidence matrices (for controlled sources, according to MNA stamps)
        #
        # The problem formulation is:
        #
        #   (G + jwC) * X = M
        #
        #  Number of equations of the problem = len(nodes) - 1 + len(branches)

        self.G = None       # (NxN) Conductances, incidence matrices and transconductances
        self.C = None       # (NxN) Capacitors, inductors, and mutual inductances
        self.M = None       # (Nx1) Independent sources (voltage & current) and zeros for GHKL elements
        self.X = None       # (Nx1) Vector of unknowns (Node voltages & Branch currents)

        # The 's' variable from Laplace transform
        self.s = sp.Symbol('s')

        # Optimization related stuff
        self.f_vec = None
        self.b_target = None
        self.b_initial = None
        self.b_step = None
        self.last_A_solved = None   # Last circuit matrix that was inverted, to skip inversion if we can
        self.last_M_solved = None
        self.stop_flag = False
        self.callback = callback
        self.x_initial = None
        self.x_min = None
        self.x_max = None
        self.names = None
        self.optimized_vals = None
        self.makeup_gain = None
        self.iteration = None
        self.n = None
        self.resnorm = None
        self.h_compiled = None
        self.h_final = None
        self.output_expr = None
        self.h_initial = None

        self.syntax_strings = {
            "R": "Rnnn <node+> <node-> <val>",
            "L": "Lnnn <node+> <node-> <val>",
            "C": "Cnnn <node+> <node-> <val>",
            "V": "Vnnn <node+> <node-> <val> [AC] <val>",
            "I": "Innn <node+> <node-> <val> [AC] <val>",
            "E": "Ennn <nodeout+> <nodeout-> <nodectl+> <nodectl-> <val>",
            "F": "Fnnn <node+> <node-> <elemctl> <val>",
            "G": "Gnnn <nodeout+> <nodeout-> <nodectl+> <nodectl-> <val>",
            "H": "Hnnn <node+> <node-> <elemctl> <val>",
            "O": "Onnn <nodein+> <nodein-> <nodeout>",
            "K": "Knnn <inductor1> <inductor2> <val>",
            "T": "Tnnn <node1+> <node1-> <node2+> <node2-> <val>"
        }

    def debug_print(self, s: str, end=None):
        self.error_msg = s
        if self.app_state._debug:
            print("[DEBUG] " + s.replace("\n", "\n[DEBUG] "), end=end)

    def info_print(self, s: str, event_type = "", end=None):
        self.status_msg = s
        print("[INFO] " + s.replace("\n", "\n[INFO] "), end=end)
        self.callback(self, event_type)

    def error_print(self, s: str, event_type = "", end=None):
        self.status_msg = "error: " + s
        print("[ERROR] " + s.replace("\n", "\n[ERROR] "), end=end)
        self.callback(self, event_type)

    def get_node(self, s: str):
        if s[0] == '-':  # In case node has minus sign, keep only node name
            s = s[1:]
        if s in self.nodes:
            return self.nodes.index(s)
        else:
            self.error_print("parse: invalid argument to get_node: " + s)
            assert 0

    # Some local helper functions
    def add_get_node(self, s: str):
        if s[0] == '-':  # In case node has minus sign, keep only node name
            s = s[1:]
        if s not in self.nodes:
            self.nodes.append(s)
        return self.get_node(s)

    def add_get_branch(self, s: str):
        if s.upper() not in self.branches:
            self.branches.append(s.upper())
        return self.branches.index(s.upper())

    def parse(self, netlist: str):
        """
        Parse SPICE netlist and build problem matrices.

        Arguments:
            netlist (str): A SPICE-like netlist to be parsed.

        Returns:
            True, if parsing was successful.
            False, if the netlist contains any errors.
            The location and type of error is printed using self.error_print.
        """

        self.nodes = ["0"]
        self.branches = []
        self.netlist_fields = {}
        self.elems_val = {}
        self.elems_line = {}  # For error printing and netlist generation purposes
        self.elems_fixed = {}
        self.elems_expr = {}
        self.elems_initial = {}
        self.minval = {}
        self.maxval = {}
        self.optimized_lines = {}
        self.expr_lines={}
        self.sym = {}
        self.sources_ac = {}  # AC and DC values of fixed I and V sources
        self.sources_dc = {}

        self.lines = netlist.splitlines()

        # Strip spaces
        for idx, l in enumerate(self.lines):
            self.lines[idx] = l.strip()

        # First pass:
        # Traverse entire netlist once to find out:
        # - Number of nodes and their label (number of V's to solve)
        # - Number of Vsources (number of I's to solve)
        # - Create SymPy symbols for all elements
        # - Save independent vsources and isources
        for idx, l in enumerate(self.lines):
            # Ignore empty lines
            if len(l) == 0: continue

            c = l[0].upper()

            # Ignore comments
            if c == ';' or c == "*" or c == "#" or c == "/": continue

            # Split into fields
            f = l.split()

            if len(f[0]) < 2:
                self.error_print("parse: line " + str(idx+1)
                                 + ": expected " + self.syntax_strings[c])
                return False

            if c in "RLCVIEFGHOKT":
                if len(f) < 4:
                    self.error_print("parse: line " + str(idx+1)
                                     + ": expected " + self.syntax_strings[c])
                    return False

                if c == 'K':
                    #  Coupling coefficient: f[1] and f[2] are names of inductors, no nodes to add here
                    self.add_get_branch(f[1])
                    self.add_get_branch(f[2])
                else:
                    # Regular circuit elements, add nodes
                    self.add_get_node(f[1])
                    self.add_get_node(f[2])

                # Create SymPy symbols.
                self.sym[f[0].upper()] = sp.Symbol(self.prefix + f[0], real=True)
            else:
                self.error_print("parse: line " + str(idx+1)
                                 + ": unknown circuit element " + str(c))
                return False

            if c in "EGT":  # VCVS and VCCS have (nodep, noden, nc1, nc2), ideal transformer has (n1+, n1-, n2+, n2-)
                if len(f) < 6:
                    self.error_print("parse: line " + str(idx+1)
                                     + ": expected " + self.syntax_strings[c])
                    return False

                self.add_get_node(f[3])
                self.add_get_node(f[4])

            if c in "FH":  # CCVS, CCCS have a current-sensing circuit element in f[3]
                if len(f) < 5:
                    self.error_print("parse: line " + str(idx+1)
                                     + ": expected " + self.syntax_strings[c])
                    return False

                # Append current-sensing branch
                self.add_get_branch(f[3])

            if c in "VEHLO":  # V, VCVS, CCVS, L, Opamps increment number of I's to solve
                self.add_get_branch(f[0])

            if c in "O":  # Opamp f[3] field is the output node
                self.add_get_node(f[3])

            if c in "T":  # Ideal transformer needs the current of the primary and secondary sides
                self.add_get_branch(f[0] + "_1")  # Branch current primary side
                self.add_get_branch(f[0] + "_2")  # Branch current secondary side

            # Extract val from netlist
            if c in "RLCK":
                self.elems_val[f[0].upper()] = f[3]
            elif c in "FH":
                self.elems_val[f[0].upper()] = f[4]
            elif c in "EGT":
                self.elems_val[f[0].upper()] = f[5]
            elif c in "VI":
                i = 3
                firstset = False
                while True:
                    u = f[i].upper()
                    if u == "AC":
                        if (len(f)-1) >= i + 1:
                            i = i + 1
                            self.sources_ac[f[0].upper()] = f[i]
                        else:
                            self.sources_ac[f[0].upper()] = 0
                    elif u == "DC":
                        if (len(f)-1) >= i + 1:
                            i = i + 1
                            self.sources_dc[f[0].upper()] = f[i]
                        else:
                            self.sources_dc[f[0].upper()] = 0
                    else:
                        if not firstset:
                            self.sources_dc[f[0].upper()] = f[i]
                            firstset = True
                        else:
                            pass

                    if (len(f) - 1) >= i + 1:
                        i = i + 1
                    else:
                        break

            self.elems_line[f[0].upper()] = idx
            self.netlist_fields[f[0].upper()] = f

        if len(self.sym) == 0:
            self.error_print("parse: netlist contains no elements")
            return False

        if len(self.nodes) < 2:
            self.error_print("parse: netlist contains no nodes")
            return False

        # Interpret val as fixed, initial or expression-based
        for key, val in self.elems_val.items():
            c = key[0].upper()

            if "{" in val:
                # Element value is an expression
                if "}" not in val:
                    self.error_print("parse: line " + str(self.elems_line[key]+1)
                                     + ": invalid expression: " + val)
                    return False

                ee = val.replace("{", "").replace("}", "").upper()
                ee = eng2num_replace(ee)
                expr = sp.parse_expr(ee, local_dict=self.sym)
                for el in expr.free_symbols:
                    if el not in self.sym.values():
                        self.error_print("parse: line "+ str(self.elems_line[key]+1)
                                         + ": unknown variable in expression: " + str(el))
                        return False
                self.elems_expr[key] = expr
                self.expr_lines[self.elems_line[key]] = self.netlist_fields[key]
            elif "*" in val:
                # Element value is fixed
                valf = eng2num(val.replace("*", ""))
                if math.isnan(valf):
                    self.error_print("parse: line " + str(self.elems_line[key]+1)
                                     + ": invalid value: " + val)
                    return False

                if c in "RLCEFGHKT":
                    self.elems_fixed[key] = valf
            else:
                # Element value is not fixed
                valf = eng2num(val)
                if math.isnan(valf):
                    self.error_print("parse: line " + str(self.elems_line[key]+1)
                                     + ": invalid value: " + val)
                    return False

                self.optimized_lines[self.elems_line[key]] = self.netlist_fields[key]
                if c in "RLCEFGHKT":
                    self.elems_initial[key] = valf

            # Setup min and max vals
            if c in "RLCEFGHKT":
                # Default min and max values from app_state
                minval = self.app_state.minval[c]
                maxval = self.app_state.maxval[c]

                # If element has min= or max= argument, that overrides the default
                for el in self.netlist_fields[key]:
                    if el.startswith("min="):
                        valf = eng2num(el.replace("min=", ""))
                        if math.isnan(valf):
                            self.error_print("parse: line " + str(self.elems_line[key]+1)
                                             + ": invalid value: " + val)
                            return False
                        else:
                            minval = valf
                    elif el.startswith("max="):
                        valf = eng2num(el.replace("max=", ""))
                        if math.isnan(valf):
                            self.error_print("parse: line " + str(self.elems_line[key]+1)
                                             + ": invalid value: " + val)
                            return False
                        else:
                            maxval = valf

                self.minval[key] = minval
                self.maxval[key] = maxval

        # These form the A matrix
        N = len(self.nodes) - 1
        B = len(self.branches)

        self.G = sp.zeros(N+B,N+B)
        self.C = sp.zeros(N+B,N+B)

        # These form the vector of knowns
        self.M = sp.zeros(N+B, 1)

        # Second pass:
        # Fill up design matrix
        for key, f in self.netlist_fields.items():
            c = f[0][0].upper()

            if c == 'R':  # Resistors
                nodep = self.add_get_node(f[1])  # Node already added but we use same logic
                noden = self.add_get_node(f[2])

                if key in self.branches:
                    # Group 2, for which we need to save current because is used in a F or H source
                    index = self.add_get_branch(f[0])  # Source is added in previous step

                    inv = 1  # Is any of the nodes inverted? TODO Check this, formulas seem correct
                    if f[1][0] == '-': inv = -inv
                    if f[2][0] == '-': inv = -inv

                    if nodep != 0:
                        self.G[nodep - 1, N + index] += 1
                        self.G[N + index, nodep - 1] += 1
                    if noden != 0:
                        self.G[noden - 1, N + index] -= inv
                        self.G[N + index, noden - 1] -= inv

                    self.G[N + index, N + index] -= self.sym[key]

                else:
                    # Group 1, we don't need to save current
                    g = self.sym[key] ** -1  # Conductance
                    if nodep == 0:  # First terminal is ground
                        self.G[noden - 1, noden - 1] += g
                    elif noden == 0:  # Second terminal is ground
                        self.G[nodep - 1, nodep - 1] += g
                    else:  # No terminal is ground
                        self.G[nodep - 1, nodep - 1] += g
                        self.G[noden - 1, noden - 1] += g

                        inv = 1  # Is any of the nodes inverted?
                        if f[1][0] == '-': inv = -inv
                        if f[2][0] == '-': inv = -inv

                        self.G[nodep - 1, noden - 1] -= inv * g  # Matrix stays symmetric
                        self.G[noden - 1, nodep - 1] -= inv * g

            elif c == 'C': # Capacitors
                nodep = self.add_get_node(f[1])  # Node already added but we use same logic
                noden = self.add_get_node(f[2])

                if key in self.branches:
                    # Group 2, for which we need to save current because is used in a F or H source
                    index = self.add_get_branch(f[0])  # Source is added in previous step

                    inv = 1  # Is any of the nodes inverted? TODO Check this, formulas seem correct
                    if f[1][0] == '-': inv = -inv
                    if f[2][0] == '-': inv = -inv

                    if nodep != 0:
                        self.G[nodep - 1, N + index] += 1
                        self.C[N + index, nodep - 1] -= 1*self.sym[key]

                    if noden != 0:
                        self.G[noden - 1, N + index] -= inv
                        self.C[N + index, noden - 1] += inv*self.sym[key]

                    self.G[N + index, N + index] += -1

                else:
                    # Group 1, we don't need to save current
                    g = self.sym[key]  # Capacitance
                    if nodep == 0:  # First terminal is ground
                        self.C[noden - 1, noden - 1] += g
                    elif noden == 0:  # Second terminal is ground
                        self.C[nodep - 1, nodep - 1] += g
                    else:  # No terminal is ground
                        self.C[nodep - 1, nodep - 1] += g
                        self.C[noden - 1, noden - 1] += g

                        inv = 1  # Is any of the nodes inverted?
                        if f[1][0] == '-': inv = -inv
                        if f[2][0] == '-': inv = -inv

                        self.C[nodep - 1, noden - 1] -= inv * g  # Matrix stays symmetric
                        self.C[noden - 1, nodep - 1] -= inv * g

            elif c == 'L':  # Inductors
                index = self.add_get_branch(f[0]) # Source is added in previous step
                nodep = self.add_get_node(f[1])
                noden = self.add_get_node(f[2])

                inv = 1  # Is any of the nodes inverted? TODO Check this, formulas seem correct
                if f[1][0] == '-': inv = -inv
                if f[2][0] == '-': inv = -inv

                if nodep != 0:
                    self.G[nodep - 1, N + index] += 1
                    self.G[N + index, nodep - 1] += 1
                if noden != 0:
                    self.G[noden - 1, N + index] -= inv
                    self.G[N + index, noden - 1] -= inv

                self.C[N + index, N + index] -= self.sym[key]

            elif c == 'V':  # Fixed V sources: V<int> <node.+> <node.-> <value>
                index = self.add_get_branch(f[0])  # Source is added in previous step
                nodep = self.add_get_node(f[1])
                noden = self.add_get_node(f[2])

                inv = -1  # TODO implement inversion for balanced circuits

                # Figure 2.22 from book Farid Najm
                # Correct V(out) & I(Vin) in simplerc
                if nodep != 0:
                    self.G[nodep - 1, N + index] += 1
                    self.G[N + index, nodep - 1] += 1
                if noden != 0:
                    self.G[noden - 1, N + index] -= 1
                    self.G[N + index, noden - 1] -= 1

                self.M[N + index, 0] += self.sym[key]

            elif c == 'I':  # Fixed I sources
                nodep = self.add_get_node(f[1])
                noden = self.add_get_node(f[2])
                if nodep != 0:
                    self.M[nodep - 1, 0] += self.sym[key]
                if noden != 0:
                    self.M[noden - 1, 0] -= self.sym[key]

            elif c == 'G':  # VCCS
                nodep = self.add_get_node(f[1])
                noden = self.add_get_node(f[2])
                nc1 = self.add_get_node(f[3])
                nc2 = self.add_get_node(f[4])
                if nodep != 0 and nc1 != 0:
                    self.G[nodep - 1, nc1 - 1] += self.sym[key]
                if nodep != 0 and nc2 != 0:
                    self.G[nodep - 1, nc2 - 1] -= self.sym[key]
                if noden != 0 and nc1 != 0:
                    self.G[noden - 1, nc1 - 1] -= self.sym[key]
                if noden != 0 and nc2 != 0:
                    self.G[noden - 1, nc2 - 1] += self.sym[key]

            elif c == 'E':  # VCVS
                nodep = self.add_get_node(f[1])
                noden = self.add_get_node(f[2])
                nc1 = self.add_get_node(f[3])
                nc2 = self.add_get_node(f[4])
                index = self.add_get_branch(f[0])
                if nodep != 0:
                    self.G[nodep - 1, N + index] += 1
                    self.G[N + index, nodep - 1] += 1
                if noden != 0:
                    self.G[noden - 1, N + index] -= 1
                    self.G[N + index, noden - 1] -= 1
                if nc1 != 0:
                    self.G[N + index, nc1 - 1] -= self.sym[key]  # This makes the matrix asymmetric!
                if nc2 != 0:
                    self.G[N + index, nc2 - 1] += self.sym[key]

            elif c == 'F':  # CCCS
                nodep = self.add_get_node(f[1])
                noden = self.add_get_node(f[2])
                index_ctl = self.add_get_branch(f[3])  # Branch current used as current sensor

                if nodep != 0:
                    self.G[nodep - 1, N + index_ctl] -= self.sym[key]
                    #self.G[nodep - 1, N + index] -= 1

                if noden != 0:
                    self.G[noden - 1, N + index_ctl] += self.sym[key]
                    #self.G[noden - 1, N + index] += 1

            elif c == 'H':  # CCVS
                nodep = self.add_get_node(f[1])
                noden = self.add_get_node(f[2])
                index = self.add_get_branch(f[0])   # Current through output vsource
                index_ctl = self.add_get_branch(f[3])  # Branch used as current sensor

                if nodep != 0:
                    self.G[nodep - 1, N + index] += 1
                    self.G[N + index, nodep - 1] += 1
                if noden != 0:
                    self.G[noden - 1, N + index] -= 1
                    self.G[N + index, noden - 1] -= 1

                self.G[N + index, N + index_ctl] -= self.sym[key]

            elif c == 'O':  # Ideal Opamp
                nodep = self.add_get_node(f[1])
                noden = self.add_get_node(f[2])
                n3 = self.add_get_node(f[3])
                index = self.add_get_branch(f[0])

                self.G[n3 - 1, N + index] += 1  # Current through the opamp

                if nodep != 0:
                    self.G[N + index, nodep - 1] += 1
                if noden != 0:
                    self.G[N + index, noden - 1] -= 1

            elif c == 'K':  # Coupling coefficient between two inductors
                index1 = self.add_get_branch(f[1])  # First coupled inductor
                index2 = self.add_get_branch(f[2])  # Second coupled inductor

                # Check if the two coupled inductors exist (must have been parsed before this)
                if f[1].upper() not in self.sym.keys() or f[2].upper() not in self.sym.keys():
                    self.error_print("parse: line " + str(self.elems_line[f[0].upper()])
                                     + ": inductor not found")
                    return False

                # Calculate mutual inductance = K * sqrt(L1 * L2)
                mutual_l = self.sym[f[0].upper()] * sp.sqrt(self.sym[f[1].upper()] * self.sym[f[2].upper()])

                self.C[N + index1, N + index2] -= mutual_l
                self.C[N + index2, N + index1] -= mutual_l

            elif c == 'T':  # Ideal transformer
                # Source: Circuit Oriented Electromagnetic Modeling Using the PEEC Techniques, First Edition.
                # Albert E. Ruehli, Giulio Antonini, and Lijun Jiang
                # https://onlinelibrary.wiley.com/doi/pdf/10.1002/9781119078388.app2

                node1p = self.add_get_node(f[1])  # Positive node primary side
                node1n = self.add_get_node(f[2])  # Negative node primary side
                node2p = self.add_get_node(f[3])  # Positive node secondary side
                node2n = self.add_get_node(f[4])  # Negative node secondary side

                index1 = self.add_get_branch(f[0] + "_1")  # Branch current primary side
                index2 = self.add_get_branch(f[0] + "_2")  # Branch current secondary side

                # Primary/secondary current ratio
                self.G[N + index1, N + index1] += 1
                self.G[N + index1, N + index2] -= self.sym[key]

                if node1p != 0:
                    self.G[node1p-1, N + index1] += 1
                    self.G[N + index2, node1p-1] -= self.sym[key]  # Primary/secondary voltage ratio
                if node1n != 0:
                    self.G[node1n-1, N + index1] -= 1
                    self.G[N + index2, node1n-1] += self.sym[key]  # Primary/secondary voltage ratio
                if node2p != 0:
                    self.G[node2p-1, N + index2] += 1
                    self.G[N + index2, node2p-1] += 1  # Primary/secondary voltage ratio
                if node2n != 0:
                    self.G[node2n-1, N + index2] -= 1
                    self.G[N + index2, node2n-1] -= 1  # Primary/secondary voltage ratio

            else:
                self.error_print("parse: unknown component in filling up matrix")
                return False

        self.debug_print("Nodes = " + str(self.nodes))
        self.debug_print("Branches = " + str(self.branches))

        self.debug_print("DC sources = " + str(self.sources_dc))
        self.debug_print("AC sources = " + str(self.sources_ac))

        self.debug_print("Circuit matrix G + sC =")
        self.debug_print(sp.pretty(self.G + self.C*self.s, wrap_line=False, num_columns=2000))

        self.debug_print("\n\n")

        self.debug_print("Vector of knowns M = ")
        self.debug_print(sp.pretty(self.M, wrap_line=False, num_columns=2000))
        self.debug_print("\n\n")

        return True

    def generate(self, new_elems: dict):
        lines_new = self.lines  # self.lines.copy()

        # Substitute lines of optimized components with optimized values
        for idx, f in self.optimized_lines.items():
            key = f[0].upper()
            if key in new_elems.keys():
                val = num2eng(new_elems[key])
                c = key[0].upper()
                if c in "RLC":
                    f[3] = val
                elif c in "FH":
                    f[4] = val
                elif c in "EG":
                    f[5] = val
                lines_new[idx] = " ".join(f)

        # Add comment with optimized value on lines with expressions
        for idx, f in self.expr_lines.items():
            key = f[0].upper()
            if key in self.elems_expr.keys():

                # Remove any prior comments on that line
                for idx2, field2 in enumerate(f):
                    if ';' in field2:
                        f = f[0:idx2]
                        break
                ee = self.elems_expr[key] # The expression

                for key, el in self.elems_fixed.items():
                    ee = ee.subs(self.sym[key], el)

                for key, el in new_elems.items():
                    ee = ee.subs(self.sym[key], el)

                val = sp.simplify(ee)
                f.append("; " + num2eng(val))
                lines_new[idx] = " ".join(f)

        # Merge lines into one text
        txt = ""
        for l in lines_new:
            txt = txt + l + "\n"
        return txt

    def solve(self):

        # Validate input expression
        if self.app_state.inexpr.upper() not in self.sources_dc.keys():
            if self.app_state.inexpr.upper() not in self.sources_ac.keys():
                self.error_print("solve: invalid input expression")
                return False

        # Superposition principle, substitute by 0 all sources that are not the input
        subs_zero = []
        for key in self.sources_dc.keys():
            c = key[0][0]
            if c in "VI":
                if not key == self.app_state.inexpr.upper():
                    subs_zero.append(key)

        for key in self.sources_ac.keys():
            c = key[0][0]
            if c in "VI":
                if not key == self.app_state.inexpr.upper():
                    subs_zero.append(key)

        # TODO: Maybe use copy here?
        A = self.G + self.C*self.s  # Circuit matrix in complex
        M = self.M  # Vector of knowns

        # Subtitute before solve is active
        # Substitute:
        # - Fixed elements by its value
        # - Independent V and I sources that are not selected as input expression
        # - Expressions in elements value by its value
        if self.app_state.subs_before_solve:
            for el in subs_zero:
                M = M.subs(self.sym[el], 0)

            # Substitute expressions in element values
            for key, el in self.elems_expr.items():
                A = A.subs(self.sym[key], el)

            for key, el in self.elems_fixed.items():
                A = A.subs(self.sym[key], el)

            M = sp.simplify(M)
            A = sp.simplify(A)

        # self.debug_print("Circuit matrix G + sC = ")
        # self.debug_print("\n" + sp.pretty(A, wrap_line=False, num_columns=2000))
        #
        # self.debug_print("\n")
        #
        # self.debug_print("Vector of knowns M = ")
        # self.debug_print("\n" + sp.pretty(M, wrap_line=False, num_columns=2000))
        # self.debug_print("\n")

        # Heart of the algorithm: Solution of the system of equations
        ################################################
        if (self.last_A_solved is not None and self.last_A_solved == A) and \
            (self.last_M_solved is not None and self.last_M_solved == M):  # Needed if sources change but matrix stay
            self.info_print("solve: solving matrix not needed")
        else:
            self.info_print("solve: solving matrix, this may take some time... ")
            start_time = time.time()
            system = A, M
            solutions = sp.linsolve(system)

            X = None

            for solution in solutions:
                if X is None:
                    X = solution  # Pick only first solution
                else:
                    self.error_print("solve: system has not an unique solution")
                    return False

            if X is None:
                self.error_print("solve: unsolvable system")
                return False

            self.info_print("solve: solving matrix finished ({:.2f}s)".format(time.time() - start_time))

            # Simplify solution if enabled (can take more time than solving!)
            if self.app_state.simplify_after_solve:
                self.info_print("solve: simplification, this may take some time... ")
                start_time = time.time()
                self.X = sp.simplify(sp.Matrix(X))
                self.info_print("solve: simplification finished ({:.2f}s)".format(time.time() - start_time))
            else:
                self.X = sp.Matrix(X)

            # Save last one solved to see if we need to solve it again on the future
            self.last_A_solved = A
            self.last_M_solved = M

            self.debug_print("Solution vector X =")
            self.debug_print(sp.pretty(self.X, wrap_line=False, num_columns=2000))
            self.debug_print("\n")

        # Handle output expression
        self.output_expr = self.build_output_expr()

        if self.output_expr is None:
            # Handle output expression already prints error if needed
            return False

        self.debug_print("Input expression:")
        self.debug_print(sp.pretty(self.sym[self.app_state.inexpr.upper()], wrap_line=False, num_columns=2000))
        self.debug_print("")

        self.debug_print("Output expression (before substitution):")
        self.debug_print(sp.pretty(self.output_expr, wrap_line=False, num_columns=2000))
        self.debug_print("")

        # Substitute expressions in element values
        for key, el in self.elems_expr.items():
            self.output_expr = self.output_expr.subs(self.sym[key], el)

        # Substitute everything in case "substitute before solving" or current output was not selected
        # Substitute variables that are zero
        for key in subs_zero:
            self.output_expr = sp.simplify(self.output_expr.subs(self.sym[key], 0))

        # Substitute fixed component values
        for key, el in self.elems_fixed.items():
            self.output_expr = self.output_expr.subs(self.sym[key], el)

        # Collect terms together as coefficients of s variable.
        self.output_expr = sp.collect(self.output_expr, self.s)

        # Create symbolic expression for initial transfer function
        self.h_initial = self.output_expr

        # Substitute initial component values
        for key, el in self.elems_initial.items():
            self.h_initial = self.h_initial.subs(self.sym[key], el)

        self.debug_print("Output expression (after substitution):")
        self.debug_print(sp.pretty(self.output_expr, wrap_line=False, num_columns=2000))
        self.debug_print("")

        self.debug_print("Initial transfer function:")
        self.debug_print(sp.pretty(self.h_initial, wrap_line=False, num_columns=2000))
        self.debug_print("")

        for sym in list(self.h_initial.free_symbols):
            if sym != self.s:
                self.error_print("solve: incomplete substitution")
                return False

        return True

    def validate_input_expr(self):
        # Validate input expression
        if self.app_state.inexpr.upper() not in self.sources_dc.keys():
            if self.app_state.inexpr.upper() not in self.sources_ac.keys():
                self.error_print("input_expression: source not found: " + self.app_state.inexpr)
                return False
        return True

    def validate_output_expr(self):
        # Validate output expression
        regex = r"([VIZYLC])\(([^,]*)(,?.*)\)"
        matches = re.findall(regex, self.app_state.outexpr, re.IGNORECASE)

        if len(matches) == 0:
            return None

        grp = matches[0]
        if grp[0].upper() == 'V':
            # Output is a voltage
            out_p = 0
            out_n = 0
            if grp[1] in self.nodes:
                # Expression has V(node) or V(node+, node-) syntax
                out_p = self.nodes.index(grp[1])

                if len(grp[2]) == 0:
                    # User entered: V(,x)
                    pass
                elif len(grp[2]) == 1:
                    # User entered: V(1,)
                    return None
                else:
                    n2 = grp[2][1:]  # Remove initial comma from regex capture group
                    if n2 in self.nodes:  # V(node+, node-) syntax
                        out_n = self.nodes.index(n2)
                    else:
                        self.debug_print("output_expression: V(out_n) node not valid")
                        return None

            else:
                # Expression has V(component) syntax
                if grp[1].upper() in self.netlist_fields:
                    f = self.netlist_fields[grp[1].upper()]
                    if f[0][0].upper() in "RLCVIEFGH":
                        out_p = self.get_node(f[1])
                        out_n = self.get_node(f[2])
                    else:
                        self.debug_print("output_expression: V(element) not found")
                        return None
                else:
                    self.debug_print("output_expression: V(out_p) or V(element) not valid")
                    return None

            if out_p == out_n:
                self.debug_print("output_expression: V(node,node) selected, output is zero")
                return None

            # This can be re-used to build_output_expression
            return ("V", out_p, out_n)

        elif grp[0].upper() == 'I':
            # Output is a current
            if grp[1].upper() in self.branches:
                # Current is available in vector X directly
                return ("Ibranch", grp[1].upper(), "")

            elif grp[1].upper() in self.netlist_fields:
                # Current through RC element calculated from differential voltage and conductance
                f = self.netlist_fields[grp[1].upper()]
                c = f[0][0].upper()
                if c in "RC":
                    return ("Ielem", grp[1].upper(), "")

            else:
                self.debug_print("output_expression: I() branch or element not found")
                return None

        elif grp[0].upper() in 'ZYLC':
            # Output is an impedance or admittance seen by a V or I source
            input_type = self.app_state.inexpr[0].upper()
            output_type = grp[1][0].upper()

            if input_type != output_type:
                self.debug_print("output_expression: input and output sources must be the same type")
                return None

            if input_type == "V":
                if grp[1].upper() not in self.netlist_fields.keys():
                    self.debug_print("output_expression: source not found: " + grp[1])
                    return None
                else:
                    return (grp[0].upper(), "V", grp[1].upper())
            elif input_type == "I":
                if grp[1].upper() not in self.netlist_fields.keys():
                    self.debug_print("output_expression: source not found: " + grp[1])
                    return None
                else:
                    return (grp[0].upper(), "I", grp[1].upper())
            else:
                self.debug_print("output_expression: input and output must be V or I source")
                return None

        else:
            # Should never reach here
            return None



    def build_output_expr(self):
        """ Check if self.app_state.outexpr is valid and return symbolic expression

        Returns:
            None, if self.app_state.outexpr is not valid
            Symbolic expression, if self.app_state.outexpr is valid

        """

        if not self.validate_input_expr():
            return None

        valid = self.validate_output_expr()

        self.debug_print("build_output_expr: valid output expression: {}".format(valid))

        if valid is None:
            return None

        # Build output expression
        if valid[0] == 'V':
            out_n = valid[1]
            out_p = valid[2]

            # Return symbolic expression
            if out_n == 0:
                # Cancel input expression from output expression
                return sp.cancel(self.X[out_p-1]/self.sym[self.app_state.inexpr.upper()])
            elif out_p == 0:
                # Negative sign
                return -sp.cancel(self.X[out_n-1]/self.sym[self.app_state.inexpr.upper()])
            else:
                # Differential
                return sp.cancel((self.X[out_p-1]-self.X[out_n-1])/self.sym[self.app_state.inexpr.upper()])

        elif valid[0] == 'Ibranch':
            idx = len(self.nodes) - 1 + self.branches.index(valid[1])

            # Return symbolic expression
            return sp.cancel(self.X[idx] / self.sym[self.app_state.inexpr.upper()])

        elif valid[0] == 'Ielem':
            # Current through RC element calculated from differential voltage and conductance
            f = self.netlist_fields[valid[1]]
            c = f[0][0].upper()

            out_p = self.get_node(f[1])
            out_n = self.get_node(f[2])

            if c == 'R': gg = 1 / self.sym[valid[1].upper()]  # R
            else: gg = self.s * self.sym[valid[1].upper()]  # C

            # Return symbolic expression
            if out_n == 0:
                # Cancel input expression from output expression
                return sp.cancel(self.X[out_p-1] / self.sym[self.app_state.inexpr.upper()] * gg)
            elif out_p == 0:
                # Negative sign
                return -sp.cancel(self.X[out_n-1] / self.sym[self.app_state.inexpr.upper()] * gg)
            else:
                # Differential
                return sp.cancel((self.X[out_p-1] - self.X[out_n-1]) / self.sym[self.app_state.inexpr.upper()] * gg)

        elif valid[0] in 'ZYLC':
            # Output is an impedance or admittance seen by a V or I source
            input_type = valid[1]

            if input_type == "V":
                # Input is a voltage source, output must be current through a voltage source
                voltage = self.sym[self.app_state.inexpr.upper()]

                # Current is available in vector X directly
                idx = len(self.nodes) - 1 + self.branches.index(valid[2].upper())
                current = self.X[idx]

            elif input_type == "I":
                # Input is a current source, output must be voltage across a current source
                in_source = self.app_state.inexpr.upper()
                current = self.sym[in_source]

                f = self.netlist_fields[valid[2]]

                # Get nodes connected to the current source
                out_p = self.add_get_node(f[1].upper())
                out_n = self.add_get_node(f[2].upper())

                if out_n == 0:
                    voltage = self.X[out_p-1]
                elif out_p == 0:
                    voltage = -self.X[out_n-1]
                else:
                    voltage = self.X[out_p-1] - self.X[out_n-1]
            else:
                assert 0

            if valid[0].upper() == "Z":
                return sp.cancel(-voltage / current)
            elif valid[0].upper() == "Y":
                return sp.cancel(-current / voltage)
            elif valid[0].upper() == "L":
                return sp.cancel(-voltage / current / self.s)
            elif valid[0].upper() == "C":
                return sp.cancel(-current / voltage / self.s)

        return None

    def get_list_input_output_expressions(self):
        # Get a (non-complete) list of input/output expressions
        # to fill the UI combo boxes

        input_exprs = []
        output_exprs = []

        # Node Voltages as output expressions
        for el in self.nodes:
            if not el == "0":
                output_exprs.append("V(" + el + ")")

        # Element voltages and currents as output expressions
        for key, f in self.netlist_fields.items():
            c = f[0][0].upper()
            if c in "RLCEFGH":
                output_exprs.append("V(" + f[0] + ")")
                output_exprs.append("I(" + f[0] + ")")

        # Fixed Vsource: V as input expression, I as output expression
        # Fixed Isource: I as input expresssion, V as output expression
        for key, f in self.netlist_fields.items():
            c = f[0][0].upper()
            if c == 'V':
                input_exprs.append(f[0])
                output_exprs.append("I(" + f[0] + ")")
            elif c == 'I':
                input_exprs.append(f[0])
                output_exprs.append("V(" + f[0] + ")")

        return input_exprs, output_exprs


        ################################################################################################################

        ################################################################################################################

        ################################################################################################################

        ################################################################################################################

    def unpack_x(self, x):
        # Undo log-transform if enabled
        if self.app_state.log_transform:
            xt = np.exp(x)
        else:
            xt = x

        # Unpack makeup gain if enabled
        makeup_gain = 1
        if self.app_state.makeup_gain:
            makeup_gain = xt[-1]
            xt = xt[0:-1]

        optimized_vals = {}
        for idx, key in enumerate(self.names):
            optimized_vals[key] = xt[idx]

        return optimized_vals, makeup_gain

    def optimize(self):

        # Added for batch mode, redundant in GUI mode
        self.f_vec = self.get_f_axis()
        self.b_target  = self.get_freqresponse(self.get_h_target())

        def resfun(xin):
            """
            Called by optimization on each iteration to calculate the residues.

            Also called by outfun to calculate the frequency response at each step (b_step)

            When called by the least squares algorithm, we use lambda to keep only first return variable.

            Shape of the residue vector can change depending on which features are enabled:
                mag_residue[npoints], ph_residue[npoints], regularization[residues_reg], makeup_gain[1]
            """

            if self.app_state.makeup_gain:
                x = xin[0:-1]
                if self.app_state.log_transform:
                    makeup_gain_db = 20*np.log10(np.exp(xin[-1]))
                else:
                    makeup_gain_db = 20*np.log10(xin[-1])
            else:
                x = xin
                makeup_gain_db = 0

            # asterisk=unpack elements of list and pass them as separate parameters
            h_vec = self.h_compiled(*x)

            # Calculate frequency response (b_step)
            if self.app_state.magnitude_in_dB:
                b_step = np.vstack((20 * np.log10(np.abs(h_vec)),
                                         np.unwrap(np.angle(h_vec)) * 180 / np.pi))
            else:
                b_step = np.vstack((np.abs(h_vec),
                                         np.unwrap(np.angle(h_vec)) * 180 / np.pi))

            residues = []

            # Magnitude optimization
            if self.app_state.optimize_mag:
                residues_mag = b_step[0, :] - self.b_target[0, :] + makeup_gain_db
                residues = np.concatenate((residues, self.app_state.weight_mag * residues_mag))

            # Phase optimization
            if self.app_state.optimize_phase:
                residues_phase = b_step[1, :] - self.b_target[1, :]
                residues = np.concatenate((residues, self.app_state.weight_phase * residues_phase))

            # Regularization: Minimize difference between optimized and initial value
            npoints = float(len(b_step[0, :]))
            if self.app_state.optimize_reg:
                if self.app_state.makeup_gain:
                    x_initial_nogain = self.x_initial[0:-1]
                else:
                    x_initial_nogain = self.x_initial

                residues_reg = np.array(x - x_initial_nogain)
                residues = np.concatenate((residues, self.app_state.weight_reg * residues_reg
                                           * np.sqrt(npoints / float(len(residues_reg)))))

            # The residue corresponding to the make up gain
            if self.app_state.makeup_gain:
                residues = np.concatenate((residues, [self.app_state.weight_amp * makeup_gain_db * np.sqrt(npoints)]))

            # Optimization algorithms from SciPy only need the residues,
            # so you need to wrap this function as lambda(x): outfun(x)[0] when passing it to the optimization algorithm
            # We can use returned b_step for plotting so we do not have to repeat the code elsewhere
            return residues, b_step

        def outfun(intermediate_result: OptimizeResult):
            """
            Called on each iteration of the optimizaton to plot the intermediate results
            """

            self.iteration = intermediate_result.nit
            if hasattr(intermediate_result, "cost"):
                self.resnorm = intermediate_result.cost
            else:
                self.resnorm = np.sqrt(np.sum(np.power(intermediate_result.fun, 2)))

            self.optimized_vals, self.makeup_gain = self.unpack_x(intermediate_result.x)
            self.n, self.b_step = resfun(intermediate_result.x)

            # Print make-up gain if enabled
            str_makeup = " makeup_gain: {:.2f}".format(self.makeup_gain) if self.app_state.makeup_gain else ""

            self.info_print("optimize: step " + str(self.iteration) +
                            ": resnorm={:.2f}".format(self.resnorm) + str_makeup,
                            event_type="optim_step")

            # Print values on each iteration
            if self.app_state._debug:
                s = ""
                for key, val in self.optimized_vals.items():
                    s = s + key + "=" + num2eng(val, ndigits=3) + ", "
                s = s[0:-2]  # Remove last comma
                self.debug_print(s)

            # Check if the stop flag is set to cancel ongoing optimization
            if self.stop_flag:
                self.stop_flag = False
                #raise StopIteration
                return True
            else:
                # This is to avoid the UI becoming unresponsive
                if not self.app_state._batch_mode:
                    time.sleep(0.5)
                return False

        # Prepare initial vectors to call optimization function
        self.x_initial = []
        self.x_min = []
        self.x_max = []
        self.names = []
        h_compiled_syms = []

        for key, el in self.elems_initial.items():
            h_compiled_syms.append(self.sym[key])
            self.x_initial.append(el)
            self.x_min.append(self.minval[key])
            self.x_max.append(self.maxval[key])
            self.names.append(key)

        # Do logarithmic transform
        h_compiled_expr = self.output_expr  # .copy() removed
        if self.app_state.log_transform:
            for el in h_compiled_syms:
                h_compiled_expr = h_compiled_expr.subs(el, sp.exp(el))
            for i, x in enumerate(self.x_initial):
                self.x_initial[i] = math.log(x)
            for i, x in enumerate(self.x_min):
                self.x_min[i] = math.log(x)
            for i, x in enumerate(self.x_max):
                self.x_max[i] = math.log(x)

        # Get a big vector that depends on component values
        h_compiled_vec = []
        for f in self.f_vec:
            h_compiled_vec.append(h_compiled_expr.subs(self.s, 2 * sp.pi * 1j * f))

        # Compile sympy function for fast evaluation
        self.h_compiled = lambdify(h_compiled_syms, h_compiled_vec, 'numpy')

        # If make up gain is enabled, add initial, max and min to the vectors
        if self.app_state.makeup_gain:
            self.x_initial.append(1)  # Initial makeup gain = 1
            self.x_min.append(self.app_state.makeup_gain_min)
            self.x_max.append(self.app_state.makeup_gain_max)
            if self.app_state.log_transform:  # Convert to log in case we need it
                self.x_initial[-1] = math.log(self.x_initial[-1])
                self.x_min[-1] = math.log(self.x_min[-1])
                self.x_max[-1] = math.log(self.x_max[-1])

        # Run optimization algorithm
        try:
            if self.app_state.optim_method == 'trf' or self.app_state.optim_method == 'dogbox':
                res = least_squares(fun=lambda x: resfun(x)[0],
                                    x0=self.x_initial,
                                    bounds=(self.x_min, self.x_max),
                                    method=self.app_state.optim_method,
                                    loss='soft_l1',
                                    args=(),  # Needed variables accessed via self.xxx
                                    xtol=self.app_state.xtol, ftol=self.app_state.ftol, gtol=self.app_state.gtol,
                                    x_scale='jac',
                                    max_nfev=self.app_state.max_nfev, diff_step=self.app_state.diff_step,
                                    callback=outfun)
            elif self.app_state.optim_method == "differential_evolution":
                res = differential_evolution(func=lambda x: np.sum(np.power(resfun(x)[0], 2)),
                                             x0 = self.x_initial,
                                             bounds=Bounds(lb=self.x_min, ub=self.x_max),
                                             callback=outfun)
            else:
                self.error_print("optimize: unknown method", event_type="optim_error")
                return

            self.optimized_vals, self.makeup_gain = self.unpack_x(res.x)

            self.h_final = self.output_expr  # .copy() removed

            for key, val in self.optimized_vals.items():
                self.h_final = self.h_final.subs(self.sym[key], val)

            self.h_final = sp.simplify(self.h_final)

            if res.success:
                str_makeup = " makeup_gain: {:.2f}".format(self.makeup_gain) if self.app_state.makeup_gain else ""
                self.info_print("optimize: " + res.message + str_makeup, event_type="optim_ok")
                self.debug_print("Optimized transfer function:")
                self.debug_print(sp.pretty(self.h_final, wrap_line=False, num_columns=2000))
                return True
            else:
                self.info_print("optimize: stopped", event_type="optim_cancelled")
                return True

        except Exception as error:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
            self.error_print("optimize: " + str(error), event_type="optim_error")
            return False

        #######################################################################################

        #######################################################################################

        #######################################################################################

        #######################################################################################

    def get_f_axis(self):
        return np.logspace(np.log10(self.app_state.freqmin),
                           np.log10(self.app_state.freqmax),
                           int(self.app_state.npoints))

    def get_h_target(self):
        """Build and return symbolic expression for the target transfer function"""

        if self.app_state.phase == 0:
            s = str(self.app_state.magnitude)
        elif self.app_state.phase == 180:
            s = str(-self.app_state.magnitude)
        elif self.app_state.phase == -180:
            s = str(-self.app_state.magnitude)
        else:
            s = str(self.app_state.magnitude) + "* exp(1j*" + str(self.app_state.phase/180.0*np.pi) + ")"

        for p in self.app_state.pztable:
            w0 = 2 * math.pi * p[1]
            if not math.isnan(w0):
                if p[0] == 'Pole real':
                    if w0 == 0.0:
                        s = s + '/s'
                    else:
                        s = s + '/(1+s/' + str(w0) + ')'
                elif p[0] == 'Zero real':
                    if w0 == 0.0:
                        s = s + '*s'
                    else:
                        s = s + '*(1+s/' + str(w0) + ')'
                elif p[0] == 'Pole pair':
                    if w0 == 0.0:
                        s = s + '/s**2'
                    else:
                        q0 = p[2]
                        if not math.isnan(q0):
                            s = s + '/(1+s/' + str(w0) + '/' + str(q0) + '+s**2/' + str(w0) + '**2)'
                elif p[0] == 'Zero pair':
                    if w0 == 0.0:
                        s = s + '*s**2'
                    else:
                        q0 = p[2]
                        if not math.isnan(q0):
                            s = s + '*(1+s/' + str(w0) + '/' + str(q0) + '+s**2/' + str(w0) + '**2)'

        return parse_expr(s)

    def compute_target_freqresponse(self):  # Only used in update_plots
        self.f_vec = self.get_f_axis()
        self.b_target = self.get_freqresponse(self.get_h_target())


    def get_freqresponse(self, h_sym):
        """
        Evaluate a symbolic expression over a frequency range.

        Returns:
            A matrix with two rows. First row is the magnitude (in dB or linear)
            and second row the unwrapped phase in degrees.
        """

        f_vec = self.get_f_axis()

        if h_sym is None:
            self.error_print("get_freqresponse: h_sym is None")
            return None

        if h_sym == 1:
            h_vec = np.ones_like(f_vec)
        elif isinstance(h_sym, sp.Float):
            if float(h_sym) == 0:
                if self.app_state.magnitude_in_dB:
                    self.error_print("get_freqresponse: transfer function is zero and magnitude is in dB")
                    return None
            h_vec = np.ones_like(f_vec) * float(h_sym)
        elif isinstance(h_sym, sp.Expr):
            if len(h_sym.free_symbols) == 0:
                if complex(h_sym) == 0:
                    if self.app_state.magnitude_in_dB:
                        self.error_print("get_freqresponse: transfer function is zero and magnitude is in dB")
                        return None
                h_vec = complex(h_sym) * np.ones_like(f_vec)
            else:
                h_lambd = lambdify(self.s, h_sym, 'numpy')
                h_vec = h_lambd(2 * np.pi * 1j * f_vec)

                if isinstance(h_vec, np.ndarray):
                    if h_vec.dtype != np.complex128:
                        self.error_print("get_freqresponse: incomplete substitution")
                        self.debug_print("H_sym = ")
                        self.debug_print(str(h_sym))
                        return None
                else:
                    self.error_print("get_freqresponse: h_vec not an array")
                    self.debug_print("H_sym = ")
                    self.debug_print(str(h_sym))
                    return None
        else:
            self.error_print("get_freqresponse: cannot deal with h_sym type")
            self.debug_print("H_sym = ")
            self.debug_print(str(h_sym))
            return None

        # Handle case with no poles and no zeros (just gain)
        #if type(h_vec) != list:
        #    h_vec = h_vec * np.ones_like(f_vec)

        if self.app_state.magnitude_in_dB:
            return np.vstack((20 * np.log10(np.abs(h_vec)), np.unwrap(np.angle(h_vec)) * 180 / np.pi))
        else:
            return np.vstack((np.abs(h_vec), np.unwrap(np.angle(h_vec)) * 180 / np.pi))