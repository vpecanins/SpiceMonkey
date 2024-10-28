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

    def update_callback(self):
        #print("Update callback")
        self.engine.get_target_freqresponse()
        if self.engine.output_expr_initial is not None:
            self.engine.get_initial_freqresponse()
            self.panel_bodeplot.plot(self.engine.f_vec, self.engine.b_initial, None, self.engine.b_target)
        else:
            self.panel_bodeplot.plot(self.engine.f_vec, None, None, self.engine.b_target)

    def load_all_states(self):
        # Called by menu when opening state file
        self.panel_netlist.load_state()
        self.panel_polezero.load_state()
        self.menubar.load_state()

    def callback_engine(self, engine: Engine, s: str):
        # This callback is called by engine thread
        # It muse use ResultEvent to communicate with the main GUI thread
        # This is handled by callback_engine_thread_event
        revt = ResultEvent(s, engine)
        wx.PostEvent(self, revt)

    def callback_engine_thread_event(self, event):

        # Print all status messages in status bar
        if hasattr(event, "status_msg"):
            if event.status_msg != "":
                self.statusbar.SetStatusText(event.status_msg)

        # For certain status messages, change things in the GUI
        if hasattr(event, "event_type"):
            if event.event_type == "parser_ok":
                self.panel_netlist.fill_combos()
                self.panel_netlist.enable_parse_solve(True)
                self.panel_netlist.enable_optimize(False, settings=True, stop=False)

            elif event.event_type == "parser_error":
                self.panel_netlist.fill_combos()
                self.panel_netlist.enable_parse_solve(True)
                self.panel_netlist.enable_optimize(False, settings=True, stop=False)

            elif event.event_type == "parser_ok_solving":
                # Do not update combos here, as user might be typing some in/out expression not valid yet
                self.panel_netlist.enable_parse_solve(False)
                self.panel_netlist.enable_optimize(False, settings=True, stop=False)

            elif event.event_type == "solver_ok":
                self.panel_netlist.fill_combos()
                self.update_callback()
                self.panel_netlist.enable_parse_solve(True)
                self.panel_netlist.enable_optimize(True, settings=True, stop=False)

            elif event.event_type == "solver_error":
                self.update_callback()
                self.panel_netlist.enable_parse_solve(True)
                self.panel_netlist.enable_optimize(False, settings=True, stop=False)

            elif event.event_type == "optim_step":
                self.panel_bodeplot.plot(self.engine.f_vec, self.engine.b_initial,
                                              event.b_optimized, self.engine.b_target)
                self.panel_netlist.txt_spice_optimized.ChangeValue(self.engine.generate(event.optimized_vals))

            elif event.event_type == "optim_ok":
                self.panel_netlist.enable_parse_solve(True)
                self.panel_netlist.enable_optimize(True, settings=True, stop=False)
                self.engine.get_optimized_freqresponse()
                self.panel_bodeplot.plot(self.engine.f_vec, self.engine.b_initial,
                                              self.engine.b_optimized, self.engine.b_target)

            elif event.event_type == "optim_cancelled":
                self.panel_netlist.enable_parse_solve(True)
                self.panel_netlist.enable_optimize(True, settings=True, stop=False)

            elif event.event_type == "optim_error":
                self.panel_netlist.enable_parse_solve(True)
                self.panel_netlist.enable_optimize(True, settings=True, stop=False)