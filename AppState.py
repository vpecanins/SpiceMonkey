import _io
import json

# This class acts like a general app state storage
# It acts like a dict, storing key/value pairs
#
# It includes functions to load and save the state
# from JSON files
#
# It has a built-in functionality that detects when
# any parameter has been changed (via __setattr__) and
# marks the state as "unsaved", calling a callback function
# (To change the title of the window when we have unsaved
# data). This only detects changes on the first hierarchy
# level of AppState (if an element of AppState is itelf another
# dict, and an element of that dict is changed, you dont call
# __setitem__ on the AppState)
# So, when changing stuff on minval and maxval, one must call
# mark_unsaved manually
#

class AppState(dict):

    def __init__(self):
        super().__init__()

        self["freqmin"] = 1
        self["freqmax"] = 1e9
        self["npoints"] = 60
        self["magnitude"] = 1e3
        self["phase"] = 0
        self["log_transform"] = True
        self["subs_before_solve"] = True
        self["ftol"] = 1e-19
        self["xtol"] = 1e-19
        self["gtol"] = 1e-8
        self["diff_step"] = 1e-3
        self["max_nfev"] = 1000
        self["weight_mag"] = 0.01
        self["weight_amp"] = 0.01
        self["weight_phase"] = 0.01
        self["weight_reg"] = 0.01

        self["linestyle_initial"] = "o"
        self["linecolor_initial"] = "green"
        self["linestyle_target"] = "o"
        self["linecolor_target"] = "blue"
        self["linestyle_optimized"] = ".-"
        self["linecolor_optimized"] = "orange"
        self["parser_case_sensitive"] = False

        self["optimize_mag"] = True
        self["optimize_phase"] = False
        self["makeup_gain"] = True
        self["makeup_gain_min"] = 0.01
        self["makeup_gain_max"] = 100
        self["optimize_reg"] = True
        self["optim_method"] = "trf"
        self["pztable"] = []
        self["inexpr"] = ""
        self["outexpr"] = ""
        self["netlist"] = ""
        self["minval"] = {"R": 1e-9, "L": 1e-9, "C": 10e-15, "E": 1e-6, "F": 1e-6, "G": 1e-6, "H": 1e-6, "K": 0}
        self["maxval"] = {"R": 1e9,  "L": 1,    "C": 1,      "E": 1e6,  "F": 1e6,  "G": 1e6,  "H": 1e6, "K": 1}
        self["parse_while_typing"] = True
        self["solve_while_typing"] = True

        # These attributes are not dumped into the JSON file
        # This is handled manually in the save_state function
        self._unsaved = False
        self._json_file = "state.json"
        self._modified_callback = None

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as e:
            raise AttributeError(name) from e

    def __setattr__(self, k, v):
        # Whenever we change or delete an attribute that doesn not begin with _,
        # we set the _unsaved flag, if it was not set before, we call _modified_callback
        # This is used to change the title of the main window when we have unsaved changes
        if not k[0] == "_":
            if not dict.__getitem__(self, "_unsaved"):
                dict.__setitem__(self, "_unsaved", True)
                if callable(self._modified_callback):
                    self._modified_callback()

        return dict.__setitem__(self, k, v)

    def mark_unsaved(self):
        if not dict.__getitem__(self, "_unsaved"):
            dict.__setitem__(self, "_unsaved", True)
            if callable(self._modified_callback):
                self._modified_callback()

    def __delattr__(self, v):
        # Whenever we change or delete an attribute that doesn not begin with _,
        # we set the _unsaved flag, if it was not set before, we call _modified_callback
        # This is used to change the title of the main window when we have unsaved changes
        if not v[0] == "_":
            if not dict.__getitem__(self, "_unsaved"):
                dict.__setitem__(self, "_unsaved", True)
                if callable(self._modified_callback):
                    self._modified_callback()

        return dict.__delitem__(self, v)

    def __repr__(self):
        # String representation
        if self.keys():
            m = max(map(len, list(self.keys()))) + 1
            return '\n'.join([k.rjust(m) + ': ' + repr(v)
                              for k, v in sorted(self.items())])
        else:
            return self.__class__.__name__ + "()"

    #def __dir__(self):
        # TODO is this needed?
        #return list(self.keys()).remove("_unsaved").remove("_json_file").remove("_modified_callback")

    def load(self, filename: str):
        with open(filename, "r") as file:
            jstr = file.read()
            tempobj = json.loads(jstr)
            for k in tempobj.keys():
                self[k] = tempobj[k]
        self._json_file = filename
        self._unsaved = False
        if callable(self._modified_callback):
            self._modified_callback()


    def save(self, filename: str):
        # Manually remove fields that we don't want in the JSON file
        self.pop("_unsaved")
        self.pop("_json_file")
        callback_bak = self.pop("_modified_callback")
        with open(filename, "w") as file:
            json.dump(self, fp=file, indent=4, skipkeys=True)
            file.flush()
        # Manually recover fields that we removed before
        self._unsaved = False
        self._json_file = filename
        self._modified_callback = callback_bak
        if callable(self._modified_callback):
            self._modified_callback()
