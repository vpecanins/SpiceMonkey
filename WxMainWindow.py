import wx
from WxBodePlot import WxBodePlot
from WxPanelPoleZero import WxPanelPoleZero
from WxMainMenu import WxMainMenu
from WxPanelNetlist import WxPanelNetlist
from AppState import AppState
from Engine import Engine
from ResultEvent import EVT_RESULT_ID, ResultEvent

class WxMainWindow(wx.Frame):
    def __init__(self, parent: wx.App, app_state: AppState):
        wx.Frame.__init__(self, None, -1, title="SpiceMonkey", size=(960, 540))
        self.parent = parent

        icon = wx.Icon()
        icon.CopyFromBitmap(wx.Bitmap("banana-icon.png", wx.BITMAP_TYPE_ANY))
        self.SetIcon(icon)

        self.app_state = app_state
        self.engine = Engine(self.app_state, callback=self.callback_engine)

        # Hold the symbolic expressions for the original and optimized netlists
        self.h_original = None
        self.h_optimized = None

        # Create menu bar
        self.menubar = WxMainMenu(self)

        # Menu bar contains currently open file, sets the title of the window
        self.menubar.set_window_title()

        # When app_state is modified, it calls back set_window_title to add an
        # asterisk to window title if unsaved data
        self.app_state._modified_callback = self.menubar.set_window_title

        # Cool status bar with two fields
        self.statusbar = wx.Frame.CreateStatusBar(self, number=2, style=wx.STB_DEFAULT_STYLE,
                                                  id=0, name="StatusBarNameStr")

        # First field take as much width as possible, second field fixed with 240px
        self.statusbar.SetStatusWidths([-1, 240])
        self.statusbar.SetStatusStyles([wx.SB_SUNKEN, wx.SB_SUNKEN])

        # Split window in three horizontal resizable panes (needs to be done with two nested splitters)
        splitter = wx.SplitterWindow(self, -1, style=wx.SP_LIVE_UPDATE)
        splitter.SetMinimumPaneSize(240)
        splitter2 = wx.SplitterWindow(splitter, -1, style=wx.SP_LIVE_UPDATE)
        splitter2.SetMinimumPaneSize(240)
        splitter2.SetSashGravity(1.0)  # Keep sash to the right when resizing window

        # Register event handler
        self.Connect(-1, -1, EVT_RESULT_ID, self.callback_engine_thread_event)

        # Three panels
        self.panel_netlist =  WxPanelNetlist(splitter, self)
        self.panel_bodeplot = WxBodePlot(splitter2, self)
        self.panel_polezero = WxPanelPoleZero(splitter2, self)

        # Split window in three horizontal resizable panes
        splitter.SplitVertically(self.panel_netlist, splitter2)
        splitter2.SplitVertically(self.panel_bodeplot, self.panel_polezero)
        splitter.SetSashPosition(10)
        splitter2.SetSashPosition(-10)

        # Set minimum size and current size of thw window
        self.SetMinSize((960, 540))
        self.SetSize((960, 540))

        self.Bind(wx.EVT_CLOSE, self.on_close)

        # CallAfter solves GtkCritical scrollbar notice
        wx.CallAfter(self.load_all_states)

    def on_close(self, event):

        if event.CanVeto() and self.app_state._unsaved:
            ret = wx.MessageBox(self.app_state._json_file + " has unsaved changes.\nWould you like to save them?",
                             "Unsaved changes",
                             wx.ICON_QUESTION | wx.YES_NO | wx.CANCEL | wx.YES_DEFAULT)
            if ret == wx.YES:
                # Needed workaround related to app not closing with Matplotlib
                self.menubar.file_save(None)
                self.parent.ExitMainLoop()
            elif ret == wx.NO:
                # Needed workaround related to app not closing with Matplotlib
                self.parent.ExitMainLoop()
            else:
                event.Veto()
                return

        self.parent.ExitMainLoop()
        self.Destroy()

    def update_plots(self, do_setup=False):
        # Updates the bode plots if the corresponding symbolic expression is not None.
        # If the symbolic expression is not None, but it cannot compute the frequency response,
        # because get_freqresponse returns None, update_plots returns False.

        self.engine.compute_target_freqresponse()
        if self.engine.b_target is None:
            self.panel_bodeplot.clear_line("Target")
        else:
            self.panel_bodeplot.plot_line("Target", self.engine.f_vec, self.engine.b_target, do_setup)
            do_setup = False

        if self.h_original is None:
            self.panel_bodeplot.clear_line("Original")
        else:
            b_original = self.engine.get_freqresponse(self.h_original)
            if b_original is None:
                return False
            else:
                self.panel_bodeplot.plot_line("Original", self.engine.f_vec, b_original, do_setup)
                do_setup = False

        if self.h_optimized is None:
            self.panel_bodeplot.clear_line("Optimized")
        else:
            b_optimized = self.engine.get_freqresponse(self.h_optimized)
            if b_optimized is None:
                return False
            else:
                self.panel_bodeplot.plot_line("Optimized", self.engine.f_vec, b_optimized, do_setup)

        return True


    def load_all_states(self):
        # Called by menu when opening state file
        self.panel_polezero.load_state()
        self.engine.__init__(self.app_state, self.callback_engine)
        self.update_plots(do_setup=True)
        self.menubar.load_state()
        self.panel_netlist.load_state()

    def callback_engine(self, engine: Engine, s: str):
        # This callback is called by engine thread
        # It muse use ResultEvent to communicate with the main GUI thread
        # This is handled by callback_engine_thread_event
        revt = ResultEvent(s, engine)
        wx.PostEvent(self, revt)

    def callback_engine_thread_event(self, event):

        # Print all status messages in status bar
        # If the status_msg has multiple lines, only print the first one in the status bar
        if hasattr(event, "status_msg"):
            if event.status_msg != "":
                self.statusbar.SetStatusText(event.status_msg.split('\n')[0])

        # For certain status messages, change things in the GUI
        if hasattr(event, "event_type"):
            if event.event_type == "parser_ok":
                self.panel_netlist.fill_combos()
                self.enable_parse_solve(True, True)
                self.enable_optimize(False, settings=True, stop=False)

            elif event.event_type == "parser_error":
                self.enable_parse_solve(True, False)
                self.enable_optimize(False, settings=True, stop=False)

            elif event.event_type == "parser_ok_solving":
                # Do not update combos here, as user might be typing some in/out expression not valid yet
                # This is needed to update input expression combo box in case input sources in the netlist have changed
                # Error: This calls build output expression before self.X is created (because we havent solved yet)
                # TODO: Need to separate between output expression validation and expression building
                self.panel_netlist.fill_combos()
                #self.enable_parse_solve(False, False)
                #self.enable_optimize(False, settings=True, stop=False)
                pass

            elif event.event_type == "solver_ok":
                # Is this needed?
                # self.panel_netlist.fill_combos()

                if self.panel_netlist.parsed_tab == 0:
                    self.h_original = self.engine.h_initial
                else:
                    self.h_optimized = self.engine.h_initial

                plot_ok = self.update_plots()
                self.enable_parse_solve(True, True)
                self.enable_optimize(plot_ok, settings=True, stop=False)

            elif event.event_type == "solver_error":
                if self.panel_netlist.parsed_tab == 0:
                    self.h_original = None
                else:
                    self.h_optimized = None

                self.update_plots()
                self.enable_parse_solve(True, True)
                self.enable_optimize(False, settings=True, stop=False)

            elif event.event_type == "optim_step":
                self.panel_bodeplot.plot_line("Optimized", self.engine.f_vec, self.engine.b_step)
                self.app_state.netlist_optimized = self.engine.generate(self.engine.optimized_vals)
                self.panel_netlist.txt_spice_optimized.ChangeValue(self.app_state.netlist_optimized)

            elif event.event_type == "optim_ok":
                self.enable_parse_solve(True, True)
                self.enable_optimize(True, settings=True, stop=False)
                self.panel_netlist.parsed_tab = 1

                self.h_optimized = self.engine.h_final  # .copy() removed
                b_optimized = self.engine.get_freqresponse(self.h_optimized)
                self.panel_bodeplot.plot_line("Optimized", self.engine.f_vec, b_optimized)
                #self.engine.get_final_freqresponse()
                #self.panel_bodeplot.plot_line("Optimized", self.engine.f_vec, self.engine.b_step)

            elif event.event_type == "optim_cancelled":
                self.enable_parse_solve(True, True)
                self.enable_optimize(True, settings=True, stop=False)
                self.panel_netlist.parsed_tab = 1

            elif event.event_type == "optim_error":
                self.enable_parse_solve(True, True)
                self.enable_optimize(True, settings=True, stop=False)
                self.panel_netlist.parsed_tab = 1

    def enable_parse_solve(self, enable=False, combos=False):
        # Called whenever we need to enable or disable gui elements for parse/solve
        self.panel_netlist.btn_parse_solve.Enable(enable)
        self.panel_netlist.combobox_out.Enable(combos)
        self.panel_netlist.combobox_in.Enable(combos)
        self.panel_netlist.root.menubar.netlistItem["parse"].Enable(enable)
        self.menubar.netlistItem["subs_before_solve"].Enable(enable)

    def enable_optimize(self, enable=False, settings=False, stop=False):
        if stop:
            self.panel_netlist.btn_optimize.SetLabel("Stop")
            self.menubar.optimItem["stop"].Enable(True)
        else:
            self.panel_netlist.btn_optimize.SetLabel("Optimize")
            self.menubar.optimItem["stop"].Enable(False)
        self.panel_netlist.btn_optimize.Enable(enable or stop)
        self.panel_netlist.btn_copy_optimized.Enable(enable)
        self.menubar.optimItem["run"].Enable(enable)
        self.menubar.optimItem["log_transform"].Enable(settings)
        self.menubar.optimItem["magnitude_in_dB"].Enable(settings)
        self.menubar.optimItem["optimize_mag"].Enable(settings)
        self.menubar.optimItem["optimize_phase"].Enable(settings)
        self.menubar.optimItem["optimize_reg"].Enable(settings)
        self.menubar.optimItem["makeup_gain"].Enable(settings)
        self.menubar.optimItem["ranges"].Enable(settings)
        self.menubar.optimItem["settings"].Enable(settings)
        self.panel_polezero.enable(settings)