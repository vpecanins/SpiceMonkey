import wx
from NumEng import *


class WxDialogOptimRanges(wx.Dialog):
    def __init__(self, parent, app_state):
        super(WxDialogOptimRanges, self).__init__(parent, title="Optimization ranges")

        szr = wx.BoxSizer(wx.VERTICAL)
        self.app_state = app_state

        self.btn_ok = wx.Button(self, wx.ID_OK, label="OK")
        self.btn_apply = wx.Button(self, wx.ID_APPLY, label="Apply")
        self.btn_cancel = wx.Button(self, wx.ID_CANCEL, label="Cancel")

        self.btn_ok.SetDefault()

        self.Bind(wx.EVT_BUTTON, self.callback_evt_button)

        self.btn_bar = wx.StdDialogButtonSizer()

        self.btn_bar.SetCancelButton(self.btn_cancel)
        self.btn_bar.SetAffirmativeButton(self.btn_ok)
        self.btn_bar.AddButton(self.btn_apply)

        self.btn_bar.Realize()

        element_texts = {
            "R": "Resistor",
            "C": "Capacitor",
            "L": "Inductor",
            "K": "Coupling coefficient",
            "E": "Voltage controlled voltage source (VCVS)",
            "F": "Current controlled current source (CCCS)",
            "G": "Voltage controlled current source (VCCS)",
            "H": "Current controlled voltage source (CCVS)",
        }

        self.texts_min = {}
        self.texts_max = {}

        gsizer = wx.FlexGridSizer(0, 3, 1, 1)
        gsizer.AddGrowableCol(2, 0)
        gsizer.AddGrowableCol(1, 0)
        gsizer.AddGrowableCol(0, 0)

        # First row with titles
        gsizer.Add(wx.StaticText(self, -1, "Variable type: ", style=wx.ALIGN_LEFT), proportion=1,
                       flag=wx.EXPAND | wx.ALL, border=5)

        gsizer.Add(wx.StaticText(self, -1, "Min. ", style=wx.ALIGN_LEFT), proportion=1,
                   flag=wx.EXPAND | wx.ALL, border=5)

        gsizer.Add(wx.StaticText(self, -1, "Max. ", style=wx.ALIGN_LEFT), proportion=1,
                   flag=wx.EXPAND | wx.ALL, border=5)

        # The circuit elements
        for el in self.app_state.minval.keys():
            gsizer.Add(wx.StaticText(self, -1, el + ": " + element_texts[el], style=wx.ALIGN_LEFT), 1,
                       wx.EXPAND | wx.ALL, 5)
            t = wx.TextCtrl(self, -1, style=wx.TE_CENTER)
            gsizer.Add(t, 1, flag=wx.EXPAND | wx.ALL)
            self.texts_min[el] = t

            t = wx.TextCtrl(self, -1, style=wx.TE_CENTER)
            gsizer.Add(t, 1, flag=wx.EXPAND | wx.ALL)
            self.texts_max[el] = t

        # The makeup gain
        gsizer.Add(wx.StaticText(self, -1, "Make-up gain (if enabled)", style=wx.ALIGN_LEFT), 1,
                   wx.EXPAND | wx.ALL, 5)

        self.txt_makeupgain_min = wx.TextCtrl(self, -1, style=wx.TE_CENTER)
        gsizer.Add(self.txt_makeupgain_min, 1, flag=wx.EXPAND | wx.ALL)
        self.txt_makeupgain_max = wx.TextCtrl(self, -1, style=wx.TE_CENTER)
        gsizer.Add(self.txt_makeupgain_max, 1, flag=wx.EXPAND | wx.ALL)

        # Add the grid sizer to main sizer
        szr.Add(gsizer, 0, wx.ALL, 1)
        szr.Add(self.btn_bar, 0, wx.ALL, 1)

        self.load_state()
        szr.Fit(self)
        self.SetSizer(szr)
        self.SetAutoLayout(True)

    def load_state(self):
        for el in self.app_state.minval.keys():
            self.texts_min[el].SetValue(num2eng(self.app_state.minval[el]))
            self.texts_max[el].SetValue(num2eng(self.app_state.maxval[el]))
        self.txt_makeupgain_min.SetValue(num2eng(self.app_state.makeup_gain_min))
        self.txt_makeupgain_max.SetValue(num2eng(self.app_state.makeup_gain_max))

    def callback_evt_button(self, event):
        if event.GetId() == wx.ID_OK or event.GetId() == wx.ID_APPLY:
            for el in self.app_state.minval.keys():
                if self.app_state.minval[el] != eng2num(self.texts_min[el].GetValue()):
                    self.app_state.minval[el] = eng2num(self.texts_min[el].GetValue())
                    self.app_state.mark_unsaved()

                if self.app_state.maxval[el] != eng2num(self.texts_max[el].GetValue()):
                    self.app_state.maxval[el] = eng2num(self.texts_max[el].GetValue())
                    self.app_state.mark_unsaved()

        self.app_state.makeup_gain_min = eng2num(self.txt_makeupgain_min.GetValue())
        self.app_state.makeup_gain_max = eng2num(self.txt_makeupgain_max.GetValue())

        event.Skip()
