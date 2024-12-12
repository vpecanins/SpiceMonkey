import wx
from WxDialogOptimSettings import WxDialogOptimSettings
from WxDialogOptimRanges import WxDialogOptimRanges
from Examples import examples
import os
from AppState import AppState

class WxMainMenu(wx.MenuBar):

    # Helper function to add menu elements with less writing
    def menu_item(self, m: wx.Menu, d: dict, key: str, label: str, status_label: str,
                     wxid=None, callback=None, enable=True):
        if wxid is None:
            wxid = wx.NewIdRef(1)
        d[key] = m.Append(wxid, label, status_label)

        if not enable:
            d[key].Enable(False)

        if callback is not None:
            self.root.Bind(wx.EVT_MENU, callback, d[key])

    def menu_checkitem(self, m: wx.Menu, d: dict, key: str, label: str, status_label: str,
                  wxid=None, enable=True, extra_callback=None):
        if wxid is None:
            wxid = wx.NewIdRef(1)
        d[key] = m.Append(wxid, label, status_label, kind=wx.ITEM_CHECK)
        self.check_items[key] = d[key]

        if not enable:
            d[key].Enable(False)

        # Use the menu key as name for the parameter in app_state
        def callback(e):
            self.root.app_state.__setattr__(key, d[key].IsChecked())
            if callable(extra_callback):
                extra_callback()
            e.Skip()

        self.root.Bind(wx.EVT_MENU, callback, d[key])

    def menu_examples_item(self, m: wx.Menu, d: dict, key: str, label: str, status_label: str,
                     wxid=None, enable=True):
        if wxid is None:
            wxid = wx.NewIdRef(1)
        d[key] = m.Append(wxid, label, status_label)

        if not enable:
            d[key].Enable(False)

        def callback(e):
            for k, val in examples[key].items():
                self.root.app_state[k] = val
            self.root.app_state["netlist_optimized"] = ""
            self.root.load_all_states()
            e.Skip()

        if callback is not None:
            self.root.Bind(wx.EVT_MENU, callback, d[key])

    def __init__(self, root):
        super().__init__()

        self.root = root

        self.dialog_settings = WxDialogOptimSettings(self.root, self.root.app_state)
        self.dialog_ranges = WxDialogOptimRanges(self.root, self.root.app_state)

        self.file_cir = None

        self.check_items = {}

        fileMenu = wx.Menu()
        fileItem = {}
        self.menu_item(fileMenu, fileItem, "new", "New", "New session", wx.ID_NEW, self.file_new)
        self.menu_item(fileMenu, fileItem, "open", "Open", "Open JSON state file", wx.ID_OPEN, self.file_open)
        self.menu_item(fileMenu, fileItem, "save", "Save", "Save JSON state file", wx.ID_SAVE, self.file_save)
        self.menu_item(fileMenu, fileItem, "saveas", "Save as\tCtrl+Shift+S", "Save JSON state file as", wx.ID_SAVEAS, self.file_saveas)
        fileMenu.AppendSeparator()
        self.menu_item(fileMenu, fileItem, "quit", "Quit", "Quit application", wx.ID_EXIT, self.file_quit)
        self.Append(fileMenu, '&File')

        figureMenu = wx.Menu()
        figureItem = {}
        figureItem["home"] = (figureMenu.Append(wx.ID_HOME, 'Home', 'Home position'))
        figureItem["back"] = (figureMenu.Append(wx.ID_BACKWARD, 'Back', 'Back position'))
        figureItem["forward"] = (figureMenu.Append(wx.ID_FORWARD, 'Forward', 'Forward position'))
        figureMenu.AppendSeparator()
        figureItem["pan"] = (figureMenu.Append(wx.ID_MOVE_FRAME, 'Pan', 'Pan', kind=wx.ITEM_CHECK))
        figureItem["zoom"] = (figureMenu.Append(wx.ID_ZOOM_IN, 'Zoom', 'Zoom section', kind=wx.ITEM_CHECK))
        figureMenu.AppendSeparator()
        figureItem["subplots"] = (figureMenu.Append(wx.ID_SETUP, 'Configure subplots...', 'Configure subplots'))
        figureItem["save"] = (figureMenu.Append(wx.NewIdRef(1), 'Save figure as...\tCtrl+F', 'Save figure as image'))
        self.Append(figureMenu, 'Fi&gure')
        self.figureItem = figureItem

        netlistMenu = wx.Menu()
        self.netlistItem = {}
        self.menu_item(netlistMenu, self.netlistItem, "parse", 'Parse && Solve\tF4', 'Parse SPICE netlist & solve circuit',
                       wx.ID_CONVERT,
                       self.optim_parse)
        fileMenu.AppendSeparator()
        self.menu_item(netlistMenu, self.netlistItem, "import", "Import SPICE\tCtrl+I", "Import SPICE netlist", None, self.file_import)
        self.menu_item(netlistMenu, self.netlistItem, "export", "Export SPICE\tCtrl+E", "Export SPICE netlist", None, self.file_export)
        netlistMenu.AppendSeparator()
        self.menu_checkitem(netlistMenu, self.netlistItem, "parse_while_typing",
                            'Parse while typing', 'Parse while typing', None)
        self.menu_checkitem(netlistMenu, self.netlistItem, "solve_while_typing",
                            'Solve while typing', 'Solve while typing', None)
        self.menu_checkitem(netlistMenu, self.netlistItem, "parser_case_sensitive",
                            'Case-sensitive', 'Case-sensitive', None, enable=False)
        self.menu_checkitem(netlistMenu, self.netlistItem, "subs_before_solve", 'Substitute before solve',
                                              'Substitute fixed before solve (not necessarily faster)', None)

        self.Append(netlistMenu, '&Netlist')

        def cb_parse_while_typing(e):
            # Disable checkbox "Solve while typing" if "Parse while typing" is not enabled
            self.netlistItem["solve_while_typing"].Enable(self.netlistItem["parse_while_typing"].IsChecked())
            e.Skip()

        self.root.Bind(wx.EVT_MENU, cb_parse_while_typing, self.netlistItem["parse_while_typing"])

        optimMenu = wx.Menu()
        self.optimItem = {}
        self.menu_item(optimMenu, self.optimItem, "run", 'Run\tF5', 'Launch optimization', wx.ID_EXECUTE,
                       self.optim_run)
        self.menu_item(optimMenu, self.optimItem, "stop", 'Stop\tEsc', 'Stop optimization', wx.ID_STOP,
                       self.optim_run, enable=False)
        optimMenu.AppendSeparator()
        self.menu_checkitem(optimMenu, self.optimItem, "log_transform", 'Log search',
                       'Enable or disable logarithmic search of the parameters', None)
        self.menu_checkitem(optimMenu, self.optimItem, "magnitude_in_dB", 'Magnitude in dB',
                            'Use dB or linear scale for magnitude', None, extra_callback=self.optim_magnitude_in_dB)
        self.menu_checkitem(optimMenu, self.optimItem, "optimize_mag", 'Optimize magnitude',
                       'Enable or disable magnitude response optimization', None)
        self.menu_checkitem(optimMenu, self.optimItem, "optimize_phase", 'Optimize phase',
                            'Enable or disable phase response optimization', None)
        self.menu_checkitem(optimMenu, self.optimItem, "optimize_reg", 'Regularization',
                            'Keep optimized values close to initial values', None)
        self.menu_checkitem(optimMenu, self.optimItem, "makeup_gain", 'Make-up gain',
                            'Add constant make-up gain to help optimization', None)
        optimMenu.AppendSeparator()

        self.menu_item(optimMenu, self.optimItem, "ranges", 'Element ranges...',
                       'Set minimum and maximum values for optimized elements', wx.ID_ANY, self.element_ranges)

        self.menu_item(optimMenu, self.optimItem, "settings", 'Optimization settings...\tF6',
                       'Tune the settings of the optimization algorithm', wx.ID_PROPERTIES, self.optim_settings)

        self.Append(optimMenu, '&Optimization')

        helpMenu = wx.Menu()
        self.helpItem = {}

        # Examples submenu
        examplesMenu = wx.Menu()
        self.examplesItem = {}
        for k in examples.keys():
            self.menu_examples_item(examplesMenu, self.examplesItem, k, k, k, wx.ID_ANY)

        helpMenu.Append(wx.ID_ANY, "Examples", examplesMenu)

        # Other help menus
        self.menu_checkitem(helpMenu, self.helpItem, "_debug", 'Print debug messages', 'Print debug messages', None)
        self.menu_item(helpMenu, self.helpItem, "about", "About...", "About SpiceMonkey", wx.ID_ABOUT, self.about)

        self.Append(helpMenu, '&Help')

        entries = [wx.AcceleratorEntry() for i in range(3)]

        entries[0].Set(wx.ACCEL_CTRL, ord('I'), self.netlistItem["import"].GetId(), self.netlistItem["import"])
        entries[1].Set(wx.ACCEL_CTRL, ord('E'), self.netlistItem["export"].GetId(), self.netlistItem["export"])

        accel_tbl = wx.AcceleratorTable(entries)

        root.SetAcceleratorTable(accel_tbl)
        root.SetMenuBar(self)

    def file_new(self, e):

        # Check for unsaved changes
        if self.root.app_state._unsaved:
            ret = wx.MessageBox(self.root.app_state._json_file + " has unsaved changes.\nWould you like to save them?",
                                "Unsaved changes",
                                wx.ICON_QUESTION | wx.YES_NO | wx.CANCEL | wx.YES_DEFAULT)
            if ret == wx.YES:
                self.file_save(None)
            elif ret == wx.NO:
                pass
            else:
                return

        self.root.app_state.__init__()
        self.root.engine.__init__(self.root.app_state, self.root.engine.callback)
        self.root.app_state._json_file = "new file"
        self.root.h_original = None
        self.root.h_optimized = None
        self.set_window_title()
        self.root.load_all_states()


    def set_window_title(self):
        if self.root.app_state._json_file == "":
            self.root.SetTitle("*new file - SpiceMonkey")
        else:
            if os.path.commonpath([os.path.abspath(self.root.app_state._json_file), os.path.abspath(os.curdir)]) == \
                    os.path.abspath(os.curdir):
                rpath = os.path.relpath(self.root.app_state._json_file)
            else:
                rpath = self.root.app_state._json_file
            if self.root.app_state._unsaved:
                self.root.SetTitle("*" + rpath + " - SpiceMonkey")
            else:
                self.root.SetTitle(rpath + " - SpiceMonkey")

    def optim_magnitude_in_dB(self):
        self.root.update_plots(do_setup=True)

    def optim_settings(self, e):
        self.dialog_settings.load_state()
        self.dialog_settings.Show()

    def element_ranges(self, e):
        self.dialog_ranges.load_state()
        self.dialog_ranges.Show()

    def load_state(self):
        for key, el in self.check_items.items():
            el.Check(self.root.app_state[key])
        self.dialog_settings.load_state()

    def file_open(self, e):

        # Check for unsaved changes
        if self.root.app_state._unsaved:
            ret = wx.MessageBox(self.root.app_state._json_file + " has unsaved changes.\nWould you like to save them?",
                                "Unsaved changes",
                                wx.ICON_QUESTION | wx.YES_NO | wx.CANCEL | wx.YES_DEFAULT)
            if ret == wx.YES:
                self.file_save(None)
            elif ret == wx.NO:
                pass
            else:
                return

        # Ask the user what new file to open
        with wx.FileDialog(self, "Open JSON state file", wildcard="JSON state files (*.json)|*.json|All files (*.*)|*.*",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:

            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return  # the user changed their mind

            # Proceed loading the file chosen by the user
            self.root.app_state._json_file = fileDialog.GetPath()
            try:
                self.root.app_state.load(self.root.app_state._json_file)
                self.root.load_all_states()
                self.set_window_title()
            except IOError:
                wx.LogError("Cannot open file '%s'." % self.root.app_state._json_file)

    def file_save(self, e):
        if self.root.app_state._json_file == "":
            self.file_saveas(e)
        else:
            try:
                self.root.app_state.save(self.root.app_state._json_file)
            except IOError:
                wx.LogError("Cannot save current data in file '%s'." % self.file_json)

    def file_saveas(self, e):
        with wx.FileDialog(self, "Save JSON state file as", wildcard="JSON state files (*.json)|*.json|All files (*.*)|*.*",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fileDialog:

            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return  # the user changed their mind

            # save the current contents in the file
            pathname = fileDialog.GetPath()

            if fileDialog.GetFilterIndex() == 0:
                if ".json" not in pathname:
                    pathname = pathname + ".json"

            try:
                self.root.app_state._json_file = pathname
                self.root.app_state.save(self.root.app_state._json_file)
                self.set_window_title()
            except IOError:
                wx.LogError("Cannot save current data in file '%s'." % pathname)

    def file_import(self, e):
        with wx.FileDialog(self, "Import SPICE netlist",
                           wildcard="SPICE netlist (*.cir)|*.cir|All files (*.*)|*.*",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:

            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return  # the user changed their mind

            # Proceed loading the file chosen by the user
            self.file_cir = fileDialog.GetPath()
            try:
                with open(self.file_cir, 'r') as file:
                    self.root.app_state["netlist"] = file.read()
                    self.root.load_all_states()

            except IOError:
                wx.LogError("Cannot open file '%s'." % self.file_cir)

    def file_export(self, e):
        with wx.FileDialog(self, "Export SPICE netlist", wildcard="SPICE netlist (*.cir)|*.cir|All files (*.*)|*.*",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fileDialog:

            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return  # the user changed their mind

            # save the current contents in the file
            self.file_cir = fileDialog.GetPath()
            try:
                with open(self.file_cir, 'w') as file:
                    if self.root.panel_netlist.notebook.GetSelection() == 0:
                        # Export original netlist
                        file.write(self.root.app_state.netlist)
                    else:
                        # Export optimized netlist
                        file.write(self.root.app_state.netlist_optimized)

                    file.close()

            except IOError:
                wx.LogError("Cannot save current data in file '%s'." % self.file_cir)

    def file_quit(self, e):
        self.root.Close()

    def optim_run(self, e):
        self.root.panel_netlist.event_handler_btn_optimize(None)

    def optim_parse(self, e):
        self.root.panel_netlist.event_handler_btn_parse_solve(None)

    def optim_stop(self, e):
        self.root.panel_netlist.event_handler_btn_optimize(None)

    def about(self, e):
        ret = wx.MessageBox("SpiceMonkey, A self-contained Python tool to simulate and optimize AC electrical circuits.",
                            "About",
                            wx.ICON_INFORMATION | wx.OK)
