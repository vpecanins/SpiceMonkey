import time

from matplotlib.figure import Figure
import matplotlib
import threading
import numpy as np
import matplotlib as mpl
import pathlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_wxagg import (
    FigureCanvasWxAgg as FigureCanvas)
from matplotlib.backend_bases import NavigationToolbar2
import wx

class NavigationToolbarMenu(NavigationToolbar2):

    def __init__(self, canvas, menu, statusbar):

        menu.root.Bind(wx.EVT_MENU, self.home, menu.figureItem["home"])
        menu.root.Bind(wx.EVT_MENU, self.back, menu.figureItem["back"])
        menu.root.Bind(wx.EVT_MENU, self.forward, menu.figureItem["forward"])
        menu.root.Bind(wx.EVT_MENU, self.pan, menu.figureItem["pan"])
        menu.root.Bind(wx.EVT_MENU, self.zoom, menu.figureItem["zoom"])
        menu.root.Bind(wx.EVT_MENU, self.configure_subplots, menu.figureItem["subplots"])
        menu.root.Bind(wx.EVT_MENU, self.save_figure, menu.figureItem["save"])
        self.menu = menu
        self.statusbar = statusbar
        self._coordinates = True
        self.was_none = True
        self.old_status_text = ""
        NavigationToolbar2.__init__(self, canvas)

    # Copied from NavigationToolbar2Wx
    def save_figure(self, *args):
        # Fetch the required filename and file type.
        filetypes, exts, filter_index = self.canvas._get_imagesave_wildcards()
        default_file = self.canvas.get_default_filename()
        dialog = wx.FileDialog(
            self.canvas.GetParent(), "Save to file",
            mpl.rcParams["savefig.directory"], default_file, filetypes,
            wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        dialog.SetFilterIndex(filter_index)
        if dialog.ShowModal() == wx.ID_OK:
            path = pathlib.Path(dialog.GetPath())
            fmt = exts[dialog.GetFilterIndex()]
            ext = path.suffix[1:]
            if ext in self.canvas.get_supported_filetypes() and fmt != ext:
                # looks like they forgot to set the image type drop
                # down, going with the extension.
                fmt = ext
            # Save dir for next time, unless empty str (which means use cwd).
            if mpl.rcParams["savefig.directory"]:
                mpl.rcParams["savefig.directory"] = str(path.parent)
            try:
                self.canvas.figure.savefig(str(path), format=fmt)
            except Exception as e:
                dialog = wx.MessageDialog(
                    parent=self.canvas.GetParent(), message=str(e),
                    caption='Matplotlib error')
                dialog.ShowModal()
                dialog.Destroy()

    def _update_buttons_checked(self):
        self.menu.figureItem["pan"].Check(self.mode.name == "PAN")
        self.menu.figureItem["zoom"].Check(self.mode.name == "ZOOM")

    def zoom(self, *args):
        super().zoom(*args)
        self._update_buttons_checked()

    def pan(self, *args):
        super().pan(*args)
        self._update_buttons_checked()

    def draw_rubberband(self, event, x0, y0, x1, y1):
        height = self.canvas.figure.bbox.height
        self.canvas._rubberband_rect = (x0, height - y0, x1, height - y1)
        self.canvas.Refresh()

    def remove_rubberband(self):
        self.canvas._rubberband_rect = None
        self.canvas.Refresh()

    def set_message(self, s):
        if self._coordinates:
            # Track transitions to recover old statusbar text when cursor moves out of plot
            if s != "":
                if self.was_none:
                    self.old_status_text = self.statusbar.GetStatusText(1)
                    self.was_none = False
                self.statusbar.SetStatusText(s.replace("(x, y) = ", ""), 1)
            else:
                if not self.was_none:
                    self.statusbar.SetStatusText(self.old_status_text, 1)
                    self.was_none = True

    def set_history_buttons(self):
        can_backward = self._nav_stack._pos > 0
        can_forward = self._nav_stack._pos < len(self._nav_stack._elements) - 1

        self.menu.figureItem["forward"].Enable(can_forward)
        self.menu.figureItem["back"].Enable(can_backward)

#############################################################################################################

#############################################################################################################

#############################################################################################################

#############################################################################################################

class WxBodePlot(wx.Panel):
    def __init__(self, parent, root, id=-1, dpi=None, **kwargs):
        wx.Panel.__init__(self, parent, id=id, **kwargs)
        self.root = root

        self.f_vec = [self.root.app_state.freqmin, self.root.app_state.freqmax]  # Just for initialization
        self.ax_mag = None
        self.ax_ph = None

        self.fig = plt.figure(dpi=dpi, figsize=(3, 2))
        self.canvas = FigureCanvas(self, -1, self.fig)
        self.toolbar = NavigationToolbarMenu(self.canvas, self.root.menubar, self.root.statusbar)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.canvas, 1, wx.EXPAND)
        self.SetSizer(sizer)

        # Plotting functions can be called from at least two threads
        # (main thread and worker thread during optimization_step)
        # So we need a lock
        self.lock = threading.Lock()
        self.setup_done = False

        # Skip focus, otherwise it catches Ctrl+S which should be caught by the main menu
        self.canvas.Bind(wx.EVT_SET_FOCUS, self.on_set_focus, self.canvas)

    def on_set_focus(self, event):
        # Workaround: Avoid getting the focus
        wx.CallAfter(self.Navigate)
        event.Skip()

    def setup(self):
        self.fig.clear()

        # Setup mag axes
        self.ax_mag = self.fig.add_subplot(211)
        self.setup_xaxis(self.ax_mag)

        if self.root.app_state.magnitude_in_dB:
            self.ax_mag.set(xlabel='Frequency [Hz]', ylabel='Magnitude [dB]')
            self.ax_mag.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(nbins=10, steps=[2, 4, 6]))
            self.ax_mag.yaxis.set_minor_locator(matplotlib.ticker.MultipleLocator(10.0))
            self.ax_mag.yaxis.set_major_formatter(matplotlib.ticker.ScalarFormatter())
        else:
            self.ax_mag.set(xlabel='Frequency [Hz]', ylabel='Magnitude [linear]')
            self.ax_mag.yaxis.set_major_locator(matplotlib.ticker.AutoLocator())
            self.ax_mag.yaxis.set_major_formatter(matplotlib.ticker.EngFormatter(unit='', sep=''))

        # Setup ph axes
        self.ax_ph = self.fig.add_subplot(212)
        self.ax_ph.set(xlabel='Frequency [Hz]', ylabel='Phase [deg]')
        self.setup_xaxis(self.ax_ph)

        self.ax_ph.yaxis.set_major_locator(matplotlib.ticker.MultipleLocator(45.0))
        self.ax_ph.yaxis.set_minor_locator(matplotlib.ticker.MultipleLocator(15.0))

        self.fig.tight_layout()
        self.setup_done = True

    def clear(self):
        for line in self.ax_mag.get_lines():
            line.remove()
        self.ax_mag.set_prop_cycle(None)
        for line in self.ax_ph.get_lines():
            line.remove()
        self.ax_ph.set_prop_cycle(None)

    def clear_line(self, name: str):
        for line in self.ax_mag.get_lines():
            if line.get_label() == name:
                line.remove()
        for line in self.ax_ph.get_lines():
            if line.get_label() == name:
                line.remove()

    def finish_plot(self):
        self.fig.tight_layout()
        self.fig.canvas.draw_idle() # this runs the plotter in another thread, also works.
        #self.fig.canvas.draw()
        self.Update()

    def plot_line(self, name: str, f_vec: np.ndarray, data: np.ndarray, do_setup=False):
        assert not self.lock.locked()
        with self.lock:
            if do_setup or not self.setup_done:
                self.setup()

            # Find line with label matching 'name' and update the X and Y data
            line_found = False

            for line in self.ax_mag.get_lines():
                if line.get_label() == name:
                    line.set_xdata(f_vec)
                    line.set_ydata(data[0,:])
                    line_found = True

            for line in self.ax_ph.get_lines():
                if line.get_label() == name:
                    line.set_xdata(f_vec)
                    line.set_ydata(data[1,:])
                    line_found = True

            # If line is not found and name is valid, create new line
            if not line_found:
                if name.lower() in ["original", "target", "optimized"]:
                    self.ax_mag.plot(f_vec, data[0, :], self.root.app_state["linestyle_"+name.lower()],
                                     color=self.root.app_state["linecolor_"+name.lower()], label=name)
                    self.ax_ph.plot(f_vec, data[1, :], self.root.app_state["linestyle_"+name.lower()],
                                    color=self.root.app_state["linecolor_"+name.lower()], label=name)

            # Rearrange axes limits
            self.ax_mag.relim()
            self.ax_mag.autoscale_view(scalex=False, scaley=True)
            self.ax_ph.relim()
            self.ax_ph.autoscale_view(scalex=False, scaley=True)

            # Call tight_layout and draws plot
            self.ax_mag.legend(loc="upper right")

            tf_str = ""

            if self.root.app_state.outexpr and self.root.app_state.inexpr:
                if self.root.app_state.outexpr != "" and self.root.app_state.inexpr != "":
                    tf_str = self.root.app_state.outexpr + "/" + self.root.app_state.inexpr

            self.fig.suptitle("Transfer function " + tf_str)
            self.finish_plot()

    def setup_xaxis(self, ax):
        # Logarithmic axes
        ax.set_yscale('linear')
        ax.set_xscale('log')

        # Enable a major and minor grid.
        ax.grid(visible=True, which='major', linestyle='-', color='gray')
        ax.grid(visible=True, which='minor', linestyle='--', color='silver')
        ax.minorticks_on()

        locmin = matplotlib.ticker.LogLocator(base=10.0, subs=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9),
                                              numticks=12)
        ax.xaxis.set_minor_locator(locmin)
        ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())

        ax.xaxis.set_major_locator(matplotlib.ticker.LogLocator(base=10.0, numticks=12))
        ax.xaxis.set_major_formatter(matplotlib.ticker.EngFormatter(unit='', sep='', places=0))

