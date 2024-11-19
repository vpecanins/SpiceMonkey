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

        self.fig = plt.figure(dpi=dpi, figsize=(3, 2))
        self.canvas = FigureCanvas(self, -1, self.fig)
        self.toolbar = NavigationToolbarMenu(self.canvas, self.root.menubar, self.root.statusbar)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.canvas, 1, wx.EXPAND)
        self.SetSizer(sizer)
        
        self.lock = threading.Lock()
        self.setup_done = False

        # Skip focus, otherwise it catches Ctrl+S which should be caught by the main menu
        self.canvas.Bind(wx.EVT_SET_FOCUS, self.on_set_focus, self.canvas)

        # Lines of plots
        self.line_original_mag = None
        self.line_original_ph = None
        self.line_target_mag = None
        self.line_target_ph = None
        self.line_optimized_mag = None
        self.line_optimized_ph = None

    def on_set_focus(self, event):
        # Workaround: Avoid getting the focus
        wx.CallAfter(self.Navigate)
        event.Skip()

    def setup(self):
        self.setup_done = True

        # Setup mag axes
        self.ax_mag = self.fig.add_subplot(211)
        # self.ax_mag.set_title('Magnitude')
        self.ax_mag.set(xlabel='Frequency [Hz]', ylabel='Magnitude [dB]')
        self.setup_xaxis(self.ax_mag)

        self.ax_mag.yaxis.set_major_locator(matplotlib.ticker.MultipleLocator(20.0))
        self.ax_mag.yaxis.set_minor_locator(matplotlib.ticker.MultipleLocator(10.0))

        # Setup ph axes
        self.ax_ph = self.fig.add_subplot(212)
        # self.ax_ph.set_title('Phase')
        self.ax_ph.set(xlabel='Frequency [Hz]', ylabel='Phase [deg]')
        self.setup_xaxis(self.ax_ph)

        self.ax_ph.yaxis.set_major_locator(matplotlib.ticker.MultipleLocator(45.0))
        self.ax_ph.yaxis.set_minor_locator(matplotlib.ticker.MultipleLocator(15.0))

        #self.fig.tight_layout()

    def clear_axis(self,ax):
        for line in ax.get_lines():
            line.remove()
        ax.set_prop_cycle(None)

    # def plot_original(self, f_vec: np.ndarray, original: np.ndarray):
    #     with self.lock:
    #         if self.line_original_mag is not None:
    #             self.line_original_mag.set_xdata(f_vec)
    #             self.line_original_mag.set_ydata(original[0, :])
    #         if self.line_original_ph is not None:
    #             self.line_original_ph.set_xdata(f_vec)
    #             self.line_original_ph.set_ydata(original[1, :])

    # def plot(self, f_vec: np.ndarray, original: np.ndarray or None, optimized: np.ndarray or None, target: np.ndarray or None):
    #     with self.lock:
    #         if not self.setup_done:
    #             self.setup()
    #
    #         self.clear_axis(self.ax_mag)
    #         self.clear_axis(self.ax_ph)
    #
    #         self.f_vec = f_vec
    #         self.ax_mag.set_xlim(left=self.f_vec[0], right=self.f_vec[-1])
    #         self.ax_ph.set_xlim(left=self.f_vec[0], right=self.f_vec[-1])
    #
    #         # Plot original
    #         if original is not None:
    #             self.line_original_mag = \
    #                 self.ax_mag.plot(self.f_vec, original[0, :], self.root.app_state.linestyle_original,
    #                              color=self.root.app_state.linecolor_original, label='Original')
    #             self.line_original_ph = \
    #                 self.ax_ph.plot(self.f_vec, original[1, :], self.root.app_state.linestyle_original,
    #                             color=self.root.app_state.linecolor_original, label='Original')
    #
    #         if target is not None:
    #             self.line_target_mag = \
    #                 self.ax_mag.plot(self.f_vec, target[0,:], self.root.app_state.linestyle_target,
    #                              color=self.root.app_state.linecolor_target, label='Target')
    #             self.line_target_ph = \
    #                 self.ax_ph.plot(self.f_vec, target[1,:], self.root.app_state.linestyle_target,
    #                             color=self.root.app_state.linecolor_target, label='Target')
    #
    #         if optimized is not None:
    #             self.line_optimized_mag = \
    #                 self.ax_mag.plot(self.f_vec, optimized[0,:], self.root.app_state.linestyle_optimized,
    #                              color=self.root.app_state.linecolor_optimized, label='Optimized')
    #             self.line_optimized_ph = \
    #                 self.ax_ph.plot(self.f_vec, optimized[1,:],  self.root.app_state.linestyle_optimized,
    #                             color=self.root.app_state.linecolor_optimized, label='Optimized')
    #
    #         # Comment this?
    #         #self.ax_mag.autoscale(enable=True, axis='y')
    #         #self.ax_ph.autoscale(enable=True, axis='y')
    #         self.finish_plot()

    def finish_plot(self):
        self.ax_mag.relim()
        self.ax_mag.autoscale_view(scalex=False, scaley=True)
        self.ax_ph.relim()
        self.ax_ph.autoscale_view(scalex=False, scaley=True)
        self.ax_mag.legend(loc="upper right")

        #self.fig.canvas.draw_idle() # this runs the plotter in another thread, doesnt work when you use a thread for the optimization
        self.fig.suptitle("Transfer function " + self.root.app_state.outexpr + "/" + self.root.app_state.inexpr)
        self.fig.tight_layout()
        self.fig.canvas.draw()  # draw must be used when calling from optimization, with the locks there
        self.Update()

    def plot_line(self, name: str, f_vec: np.ndarray, data: np.ndarray):
        assert not self.lock.locked()
        with self.lock:
            if not self.setup_done:
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

            # Rearranges axis limits, calls tight_layout and draws plot
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

