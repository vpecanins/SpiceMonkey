import wx
from NumEng import *


class WxDialogOptimSettings(wx.Dialog):
    def __init__(self, parent, app_state):
        super(WxDialogOptimSettings, self).__init__(parent, title="Optimization settings")

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

        self.setting_arr = [("xtol", "Independent variable tolerance"),
                            ("ftol", "Cost function tolerance"),
                            ("gtol", "Norm of the gradient tolerance"),
                            ("max_nfev", "Max number of evaluations"),
                            ("diff_step", "Step for Jacobian computation"),
                            ("weight_mag", "Weight applied to magnitude error"),
                            ("weight_phase", "Weight applied to phase error"),
                            ("weight_amp", "Weight applied to makeup gain"),
                            ("weight_reg", "Weight applied to regularization")]

        self.texts = {}
        gsizer = wx.FlexGridSizer(0, 2, 1, 1)
        gsizer.AddGrowableCol(1, 0)
        gsizer.AddGrowableCol(0, 0)

        # Optimization algorithm combo box
        gsizer.Add(wx.StaticText(self, -1, "Optimization algorithm: ", style=wx.ALIGN_LEFT), proportion=1,
                       flag=wx.EXPAND | wx.ALL, border=5)

        self.combo = wx.ComboBox(self, id=wx.ID_ANY, value="",
                               choices=["trf", "dogbox", "differential_evolution"],
                               style=wx.CB_READONLY)

        gsizer.Add(self.combo, proportion=2, flag=wx.ALIGN_LEFT)

        # The rest of the boxes
        for el in self.setting_arr:
            gsizer.Add(wx.StaticText(self, -1, el[1] + " (" + el[0] + "): ", style=wx.ALIGN_LEFT), 1,
                       wx.EXPAND | wx.ALL, 5)
            t = wx.TextCtrl(self, -1, style=wx.TE_CENTER)
            gsizer.Add(t, 1, flag=wx.EXPAND | wx.ALL)
            self.texts[el[0]] = t



        szr.Add(gsizer, 0, wx.ALL, 1)
        szr.Add(self.btn_bar, 0, wx.ALL, 1)

        self.load_state()
        szr.Fit(self)
        self.SetSizer(szr)
        self.SetAutoLayout(True)

    def load_state(self):
        self.combo.ChangeValue(self.app_state.optim_method)
        for el in self.texts.keys():
            self.texts[el].SetValue(str(self.app_state[el]))

    def callback_evt_button(self, event):
        if event.GetId() == wx.ID_OK or event.GetId() == wx.ID_APPLY:
            self.app_state.optim_method = self.combo.GetValue()
            for key, el in self.texts.items():
                self.app_state[key] = eng2num(el.GetValue())
        event.Skip()
