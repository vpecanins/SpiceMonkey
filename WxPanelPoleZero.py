import wx
import wx.grid
from NumEng import *
import math

from typing import Callable

import WxMainWindow

class WxPanelPoleZero(wx.Panel):
    def __init__(self, parent, root: WxMainWindow):
        super().__init__(parent)
        
        # Main window can be accessed from here
        self.app_state = root.app_state
        self.root = root

        # Grid
        ############################################################
        my_grid = wx.grid.Grid(self, -1)
        my_grid.EnableDragRowMove(False)
        my_grid.EnableDragRowSize(False)
        my_grid.SetRowLabelSize(0)

        self.my_grid = my_grid
        N = 0
        my_grid.CreateGrid(N, 3)
        my_grid.SetColLabelValue(0, "Type")
        my_grid.SetColLabelValue(1, "Freq")
        my_grid.SetColLabelValue(2, "Q")

        self.my_grid.Bind(wx.grid.EVT_GRID_CELL_CHANGING, self.cell_validate)
        self.my_grid.Bind(wx.grid.EVT_GRID_CELL_CHANGED, self.cell_changed)
        self.my_grid.Bind(wx.grid.EVT_GRID_EDITOR_CREATED, self.editor_create)
        self.my_grid.Bind(wx.grid.EVT_GRID_SELECT_CELL, self.select_cell)

        self.row_types = ["Pole real", "Pole pair", "Zero real", "Zero pair"]

        my_grid.SetSelectionMode(wx.grid.Grid.GridSelectRows)
        my_grid.SetDefaultCellAlignment(wx.ALIGN_CENTRE, wx.ALIGN_CENTRE)

        btn_sizer = [wx.BoxSizer(wx.HORIZONTAL),  # Freq Min
                     wx.BoxSizer(wx.HORIZONTAL),  # Freq Max
                     wx.BoxSizer(wx.HORIZONTAL),  # N points
                     wx.BoxSizer(wx.HORIZONTAL),  # Magnitude
                     wx.BoxSizer(wx.HORIZONTAL),  # Phase
                     wx.BoxSizer(wx.HORIZONTAL)]  # Bottom buttons

        self.labels = []

        # Top fields
        ############################################################
        self.labels.append(wx.StaticText(self, -1, "Freq min:", style=wx.ALIGN_CENTER))
        btn_sizer[0].Add(self.labels[-1], 1, wx.EXPAND | wx.ALL, 1)
        self.txt_fmin = wx.TextCtrl(self, -1, style=wx.TE_CENTER | wx.TE_PROCESS_ENTER)
        self.txt_fmin.Bind(wx.EVT_TEXT_ENTER, lambda e: self.internal_update_callback())
        btn_sizer[0].Add(self.txt_fmin, 1, wx.EXPAND | wx.ALL, 1)

        self.labels.append(wx.StaticText(self, -1, "Freq max:", style=wx.ALIGN_CENTER))
        btn_sizer[1].Add(self.labels[-1], 1, wx.EXPAND | wx.ALL, 1)
        self.txt_fmax = wx.TextCtrl(self, -1, style=wx.TE_CENTER | wx.TE_PROCESS_ENTER)
        self.txt_fmax.Bind(wx.EVT_TEXT_ENTER, lambda e: self.internal_update_callback())
        btn_sizer[1].Add(self.txt_fmax, 1, wx.EXPAND | wx.ALL, 1)

        self.labels.append(wx.StaticText(self, -1, "N points:", style=wx.ALIGN_CENTER))
        btn_sizer[2].Add(self.labels[-1], 1, wx.EXPAND | wx.ALL, 1)
        self.txt_npoints = wx.TextCtrl(self, -1, style=wx.TE_CENTER | wx.TE_PROCESS_ENTER)
        self.txt_npoints.Bind(wx.EVT_TEXT_ENTER, lambda e: self.internal_update_callback())
        btn_sizer[2].Add(self.txt_npoints, 1, wx.EXPAND | wx.ALL, 1)

        self.labels.append(wx.StaticText(self, -1, "Magnitude:", style=wx.ALIGN_CENTER))
        btn_sizer[3].Add(self.labels[-1], 1, wx.EXPAND | wx.ALL, 1)
        self.txt_magnitude = wx.TextCtrl(self, -1, style=wx.TE_CENTER | wx.TE_PROCESS_ENTER)
        self.txt_magnitude.Bind(wx.EVT_TEXT_ENTER, lambda e: self.internal_update_callback())
        btn_sizer[3].Add(self.txt_magnitude, 1, wx.EXPAND | wx.ALL, 1)

        self.labels.append(wx.StaticText(self, -1, "Phase:", style=wx.ALIGN_CENTER))
        btn_sizer[4].Add(self.labels[-1], 1, wx.EXPAND | wx.ALL, 1)
        self.txt_phase = wx.TextCtrl(self, -1, style=wx.TE_CENTER | wx.TE_PROCESS_ENTER)
        self.txt_phase.Bind(wx.EVT_TEXT_ENTER, lambda e: self.internal_update_callback())
        btn_sizer[4].Add(self.txt_phase, 1, wx.EXPAND | wx.ALL, 1)

        # Bottom buttons
        ############################################################
        self.btn_add = wx.Button(self, label="Add")
        btn_sizer[-1].Add(self.btn_add, 1, wx.CENTER | wx.ALL, 1)
        self.btn_add.SetBitmapLabel(wx.ArtProvider.GetBitmap(wx.ART_PLUS, wx.ART_MENU))
        self.btn_add.Bind(wx.EVT_BUTTON, self.callback_add)

        self.btn_remove = wx.Button(self, label="Remove")
        btn_sizer[-1].Add(self.btn_remove, 1, wx.CENTER | wx.ALL, 1)
        self.btn_remove.SetBitmapLabel(wx.ArtProvider.GetBitmap(wx.ART_MINUS, wx.ART_MENU))
        self.btn_remove.Bind(wx.EVT_BUTTON, self.callback_remove)

        # Slider
        ############################################################
        self.sign = 1
        self.decade = 1
        self.sel_row = None
        self.sel_col = None
        self.nticks = 500
        self.roundpos = 100

        slider_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.slider = wx.Slider(self, value=0, minValue=-self.nticks, maxValue=self.nticks,
                                style=wx.SL_HORIZONTAL)
        self.slider.Bind(wx.EVT_SLIDER, self.evt_slider)
        self.slider.Bind(wx.EVT_SCROLL_THUMBRELEASE, self.evt_release_slider)
        self.slider.Bind(wx.EVT_KEY_UP, self.evt_release_slider)

        self.label_slider_min = wx.StaticText(self, -1, "   ", style=wx.ALIGN_CENTER)
        self.label_slider_max = wx.StaticText(self, -1, "   ", style=wx.ALIGN_CENTER)

        slider_sizer.Add(self.label_slider_min, 0, wx.CENTER | wx.LEFT | wx.RIGHT, 2)
        slider_sizer.Add(self.slider, 1, wx.EXPAND)
        slider_sizer.Add(self.label_slider_max, 0, wx.CENTER | wx.LEFT | wx.RIGHT, 2)
        self.slider_sizer = slider_sizer

        self.slider.Enable(0)

        # Layout
        ############################################################
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(btn_sizer[0], 0, flag=wx.EXPAND)
        sizer.Add(btn_sizer[1], 0, flag=wx.EXPAND)
        sizer.Add(btn_sizer[2], 0, flag=wx.EXPAND)
        sizer.Add(btn_sizer[3], 0, flag=wx.EXPAND)
        sizer.Add(btn_sizer[4], 0, flag=wx.EXPAND)
        sizer.Add(self.my_grid, 1, flag=wx.EXPAND)
        sizer.Add(slider_sizer, 0, flag=wx.EXPAND)
        sizer.Add(btn_sizer[-1], 0, flag=wx.EXPAND)

        self.SetSizer(sizer)

        # TODO apply order automatically based on frequency

    def enable(self, enable):
        self.my_grid.Enable(enable)
        self.txt_phase.Enable(enable)
        self.txt_magnitude.Enable(enable)
        self.txt_fmax.Enable(enable)
        self.txt_fmin.Enable(enable)
        self.txt_npoints.Enable(enable)
        self.slider.Enable(enable)
        self.btn_add.Enable(enable)
        self.btn_remove.Enable(enable)
        for el in self.labels:
            el.Enable(enable)
        self.label_slider_min.Enable(enable)
        self.label_slider_max.Enable(enable)

    def internal_update_callback(self):
        self.app_state.freqmin = eng2num(self.txt_fmin.GetLineText(0))
        self.app_state.freqmax = eng2num(self.txt_fmax.GetLineText(0))
        self.app_state.npoints = eng2num(self.txt_npoints.GetLineText(0))
        self.app_state.magnitude = eng2num(self.txt_magnitude.GetLineText(0))
        self.app_state.phase = eng2num(self.txt_phase.GetLineText(0))

        if math.isnan(self.app_state.freqmin):
            return

        if math.isnan(self.app_state.freqmax):
            return

        if math.isnan(self.app_state.npoints):
            return

        if math.isnan(self.app_state.magnitude):
            return

        if math.isnan(self.app_state.phase):
            return

        nrows = self.my_grid.GetNumberRows()

        self.app_state.pztable = []
        for n in range(0, nrows):
            rt = self.my_grid.GetCellValue(n, 0)
            w0 = eng2num(self.my_grid.GetCellValue(n, 1))
            if "pair" in rt:
                q = eng2num(self.my_grid.GetCellValue(n, 2))
            else:
                q = 1
            self.app_state.pztable.append([rt, w0, q])

        # Call update_callback from parent window to update all UI
        self.root.update_callback()

    def load_state(self):
        self.txt_fmin.SetValue(num2eng(self.app_state.freqmin))
        self.txt_fmax.SetValue(num2eng(self.app_state.freqmax))
        self.txt_npoints.SetValue(num2eng(self.app_state.npoints))
        self.txt_magnitude.SetValue(num2eng(self.app_state.magnitude))
        self.txt_phase.SetValue(num2eng(self.app_state.phase))

        nrows = self.my_grid.GetNumberRows()
        if nrows != 0:
            self.my_grid.DeleteRows(0, nrows)

        for p in self.app_state.pztable:
            if p[0] in self.row_types:
                self.add_row(p[0], p[1], p[2])

        self.my_grid.SelectRow(self.sel_row)
        self.my_grid.SelectCol(self.sel_col)

        # Call update_callback from parent window to update all UI
        self.root.update_callback()

    def add_row(self, row_type: str, freq: float, q: float):
        self.my_grid.AppendRows(1)
        n = self.my_grid.GetNumberRows() - 1

        t1 = wx.grid.GridCellTextEditor()
        t2 = wx.grid.GridCellTextEditor()

        self.my_grid.SetCellEditor(n, 1, t1)
        self.my_grid.SetCellEditor(n, 2, t2)

        g = wx.grid.GridCellChoiceEditor(choices=self.row_types, allowOthers=False)
        self.my_grid.SetCellEditor(n, 0, g)

        self.my_grid.SetCellValue(n, 0, row_type)
        self.my_grid.SetCellValue(n, 1, num2eng(freq))
        self.my_grid.SetCellValue(n, 2, num2eng(q))

        self.sel_row = n
        self.sel_col = 1
        self.enable_disable_q(n)
        self.set_slider()

        return n

    # When Add button is clicked
    def callback_add(self, event):
        sel = self.my_grid.GetSelectedRows()
        if sel:
            sel = sel[-1]
        else:
            if self.sel_row is not None:
                sel = self.sel_row
            else:
                sel = self.my_grid.GetNumberRows() - 1

        if sel > 0:
            rt = self.my_grid.GetCellValue(sel, 0)  # Previous row selected
            f0 = eng2num(self.my_grid.GetCellValue(sel, 1))
            q0 = eng2num(self.my_grid.GetCellValue(sel, 2))
        else:
            rt = self.row_types[0]  # Pole real
            f0 = math.sqrt(self.app_state.freqmin * self.app_state.freqmax)
            q0 = 1

        n = self.add_row(rt, f0, q0)
        self.my_grid.SetGridCursor(n, 1)
        self.my_grid.SelectRow(n)
        self.my_grid.EnableCellEditControl(True)
        self.internal_update_callback()

    # When Remove button is clicked
    def callback_remove(self, event):
        n = self.my_grid.GetSelectedRows()

        if n:
            firstrow = n[0]
        while n:
            self.my_grid.DeleteRows(n[0])
            n = self.my_grid.GetSelectedRows()

        n2 = self.my_grid.GetNumberRows()
        if n2:
            self.my_grid.SelectRow(n2 - 1)
        else:
            self.slider.Enable(0)
            self.label_slider_max.SetLabel("   ")
            self.label_slider_min.SetLabel("   ")

        self.internal_update_callback()

    # Only known working way to validate the user input in a WxPython GridCellTextEditor
    # Because wx.Validator doesn't seem to work and there's no examples
    def cell_validate(self, event):
        row = event.GetRow()
        col = event.GetCol()
        if col != 0:
            val = event.GetString()
            if math.isnan(eng2num(val)):
                event.Veto()
            else:
                event.Skip()
        else:
            event.Skip()

    # Only known way to center the text in a WxPython GridCellTextEditor
    def editor_create(self, event):
        row = event.GetRow()
        col = event.GetCol()
        if col != 0:
            event.GetControl().SetWindowStyle(wx.TE_CENTER)

    def select_cell(self, event):
        self.sel_row = event.GetRow()
        self.sel_col = event.GetCol()
        self.slider.Enable(1)

        if self.sel_col == 0:
            self.sel_col = 1

        self.set_slider()

    def set_slider(self):
        s = self.my_grid.GetCellValue(self.sel_row, self.sel_col)
        n = eng2num(s)
        if not math.isnan(n) and not n == 0.0:
            self.sign = math.copysign(1, n)
            mag = math.fabs(n)
            self.decade = round(math.log10(mag))
            self.label_slider_min.SetLabel(num2eng(math.pow(10, self.decade - 1)))
            self.label_slider_min.SetWindowStyle(wx.TEXT_ALIGNMENT_CENTER)
            self.label_slider_max.SetLabel(num2eng(math.pow(10, self.decade + 1)))
            self.slider.SetValue(int(self.nticks * (math.log10(mag) - self.decade)))
            self.slider_sizer.Layout()

    def evt_slider(self, event):
        if self.sel_col != 0:
            rp = self.roundpos / math.pow(10, self.decade)
            self.my_grid.SetCellValue(self.sel_row, self.sel_col, num2eng(
                round(rp * self.sign * math.pow(10,
                                                self.decade + self.slider.GetValue() / self.nticks)) / rp))

    def evt_release_slider(self, event):
        self.set_slider()
        self.internal_update_callback()

    def enable_disable_q(self, row):
        if "pair" in self.my_grid.GetCellValue(row, 0):
            self.my_grid.SetCellValue(row, 2, num2eng(self.app_state.pztable[row][2]))
            self.my_grid.SetReadOnly(row, 2, False)
        else:
            self.my_grid.SetCellValue(row, 2, "")
            self.my_grid.SetReadOnly(row, 2, True)

    def cell_changed(self, event):
        self.sel_row = event.GetRow()
        self.sel_col = event.GetCol()

        if self.sel_col == 0:
            self.sel_col = 1
            self.enable_disable_q(self.sel_row)

        self.set_slider()

        self.internal_update_callback()

