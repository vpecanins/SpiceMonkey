import time
import wx

import threading
import WxMainWindow
from ResultEvent import ResultEvent

class WxPanelNetlist(wx.Panel):
    def __init__(self, parent, root: WxMainWindow):
        super().__init__(parent)
        self.parser_solver_called_while_typing = False
        self.root = root
        self.parent = parent
        self.engine = root.engine

        self.worker_thread = None
        self.worker_lock = threading.Lock()
        self.changed_flag = []
        self.enable_print_debug = True
        self.selected_tab = 0

        # In/out combo boxes
        self.combobox_in = wx.Choice(self)
        self.combobox_out = wx.ComboBox(self, style=wx.TE_PROCESS_ENTER)
        self.combobox_in.Bind(wx.EVT_CHOICE, self.event_handler_combobox)
        self.combobox_out.Bind(wx.EVT_TEXT, self.event_handler_combobox)
        cb_in_sizer = wx.BoxSizer()
        cb_in_sizer.Add(wx.StaticText(self, -1, "In:", style=wx.ALIGN_CENTER), 0, wx.EXPAND | wx.ALL, 5)
        cb_in_sizer.Add(self.combobox_in, 1, wx.EXPAND | wx.ALL, 1)
        cb_out_sizer = wx.BoxSizer()
        cb_out_sizer.Add(wx.StaticText(self, -1, "Out:", style=wx.ALIGN_CENTER), 0, wx.EXPAND | wx.ALL, 5)
        cb_out_sizer.Add(self.combobox_out, 1, wx.EXPAND | wx.ALL, 1)

        # Notebook
        self.notebook = wx.Notebook(self)

        # ORIGINAL SPICE TEXT VIEW
        ############################################################
        self.panel1 = wx.Panel(self.notebook)
        self.sizer1 = wx.BoxSizer(wx.VERTICAL)
        self.txt_spice = wx.TextCtrl(self.panel1, style=wx.TE_MULTILINE)
        tcFont = self.txt_spice.GetFont()
        tcFont.SetFamily(wx.FONTFAMILY_TELETYPE)
        self.txt_spice.SetFont(tcFont)
        self.txt_spice.SetMinSize(wx.Size(30 * tcFont.PixelSize.Width, 30 * tcFont.PixelSize.Height))

        self.sizer1.Add(self.txt_spice, 1, wx.EXPAND | wx.ALL, 1)
        self.panel1.SetSizer(self.sizer1)

        self.txt_spice.Bind(wx.EVT_TEXT, self.event_handler_text)  # Text changed
        self.txt_spice.Bind(wx.EVT_KEY_UP, self.update_line_col)   # Keyboard btn up
        self.txt_spice.Bind(wx.EVT_LEFT_UP, self.update_line_col)  # Mouse btn up

        # Optimized SPICE TEXT VIEW
        ############################################################
        self.panel2 = wx.Panel(self.notebook)
        self.sizer2 = wx.BoxSizer(wx.VERTICAL)
        self.txt_spice_optimized = wx.TextCtrl(self.panel2, style=wx.TE_MULTILINE)
        self.txt_spice_optimized.SetFont(tcFont)
        self.txt_spice_optimized.SetMinSize(wx.Size(30 * tcFont.PixelSize.Width, 30 * tcFont.PixelSize.Height))
        self.btn_copy_optimized = wx.Button(self.panel2, label="Copy to original")
        self.btn_copy_optimized.Enable(False)
        self.btn_copy_optimized.Bind(wx.EVT_BUTTON, self.event_handler_copy_optimized)
        self.sizer2.Add(self.txt_spice_optimized, 1, wx.EXPAND | wx.ALL, 1)
        self.sizer2.Add(self.btn_copy_optimized, 0, wx.EXPAND | wx.ALL, 1)
        self.panel2.SetSizer(self.sizer2)

        self.txt_spice_optimized.Bind(wx.EVT_TEXT, self.event_handler_text)  # Text changed
        self.txt_spice_optimized.Bind(wx.EVT_KEY_UP, self.update_line_col)  # Keyboard btn up
        self.txt_spice_optimized.Bind(wx.EVT_LEFT_UP, self.update_line_col)  # Mouse btn up

        # Bottom buttons
        ############################################################
        self.btn_parse_solve = wx.Button(self, label="Parse && Solve")
        self.btn_parse_solve.Bind(wx.EVT_BUTTON, self.event_handler_btn_parse_solve)

        self.btn_optimize = wx.Button(self, label="Optimize")
        self.btn_optimize.Bind(wx.EVT_BUTTON, self.event_handler_btn_optimize)

        # Layout
        ############################################################
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(cb_in_sizer, 0, wx.EXPAND | wx.ALL, 1)
        sizer.Add(cb_out_sizer, 0, wx.EXPAND | wx.ALL, 1)
        self.notebook.AddPage(self.panel1, "Original", True)
        self.notebook.AddPage(self.panel2, "Optimized", False)
        sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 1)

        sizer.Add(self.btn_parse_solve, 0, wx.EXPAND | wx.ALL, 1)
        sizer.Add(self.btn_optimize, 0, wx.EXPAND | wx.ALL, 1)
        self.SetSizer(sizer)

    def debug_print(self, o, end=None):
        if self.enable_print_debug:
                print("[GUI DEBUG] " + str(o).replace("\n", "\n[GUI DEBUG] "), end=end)

    def load_state(self):
        self.txt_spice.ChangeValue(self.root.app_state.netlist) # do not trigger EVT_TEXT
        self.txt_spice_optimized.ChangeValue(self.root.app_state.netlist_optimized)  # do not trigger EVT_TEXT
        self.combobox_in.SetSelection(self.combobox_in.FindString(self.root.app_state.inexpr))
        self.combobox_out.ChangeValue(self.root.app_state.outexpr)
        wx.CallAfter(self.event_handler_btn_parse_solve, None)

    def event_handler_text(self, event):
        self.changed_flag.append(1)
        self.debug_print("Changed flag set: " + str(len(self.changed_flag)))

        # Depending on which tab is selected, update netlist or netlist_optimized
        self.selected_tab = self.notebook.GetSelection()
        if self.notebook.GetSelection() == 0:
            self.root.app_state.netlist = self.txt_spice.GetValue()
        else:
            self.root.app_state.netlist_optimized = self.txt_spice_optimized.GetValue()

        # Start parse & solve thread if enabled while typing
        if self.root.app_state.parse_while_typing:
            if not self.worker_lock.locked():
                self.enable_parse_solve(False)
                self.parser_solver_called_while_typing = True
                self.worker_thread = threading.Thread(target=self.parser_solver_thread_fun)
                self.worker_thread.start()

    def event_handler_copy_optimized(self, event):
        v = self.txt_spice_optimized.GetValue()
        if v != "":
            self.txt_spice.SetValue(v)
            self.notebook.SetSelection(0)
            self.event_handler_text(event)

    def update_line_col(self, event):
        x, lx, cx = self.txt_spice.PositionToXY(self.txt_spice.GetInsertionPoint())
        stat = "Line:%s Col:%s" % (cx+1, lx+1)
        self.root.statusbar.SetStatusText(stat, 1)
        event.Skip()

    def event_handler_combobox(self, event):
        if self.worker_lock.locked():
            assert(0)  # ComboBoxes are disabled while solving so should never be called

        self.root.app_state.inexpr = self.combobox_in.GetString(self.combobox_in.GetSelection())
        self.root.app_state.outexpr = self.combobox_out.GetValue()

        # Input & output expressions only affect solver, not parser
        # So we only need to call parse&solver if solve_while typing is enabled
        if self.parser_solver_called_while_typing and not self.root.app_state.solve_while_typing:
            pass
        else:
            outexpr_valid, _, _ = self.engine.validate_output_expr()
            if outexpr_valid is not None:
                self.enable_parse_solve(False)
                self.enable_optimize(False)
                self.worker_thread = threading.Thread(target=self.parser_solver_thread_fun)
                self.worker_thread.start()

        event.Skip()

    def enable_parse_solve(self, enable=False):
        # Called whenever we need to enable or disable gui elements for parse/solve
        self.btn_parse_solve.Enable(enable)
        self.combobox_out.Enable(enable)
        self.combobox_in.Enable(enable)
        self.root.menubar.netlistItem["parse"].Enable(enable)
        self.root.menubar.netlistItem["subs_before_solve"].Enable(enable)

    def enable_optimize(self, enable=False, settings=False, stop=False):
        if stop:
            self.btn_optimize.SetLabel("Stop")
            self.root.menubar.optimItem["stop"].Enable(True)
        else:
            self.btn_optimize.SetLabel("Optimize")
            self.root.menubar.optimItem["stop"].Enable(False)
        self.btn_optimize.Enable(enable or stop)
        self.btn_copy_optimized.Enable(enable)
        self.root.menubar.optimItem["run"].Enable(enable)
        self.root.menubar.optimItem["log_transform"].Enable(settings)
        self.root.menubar.optimItem["optimize_mag"].Enable(settings)
        self.root.menubar.optimItem["optimize_phase"].Enable(settings)
        self.root.menubar.optimItem["optimize_reg"].Enable(settings)
        self.root.menubar.optimItem["makeup_gain"].Enable(settings)
        self.root.menubar.optimItem["ranges"].Enable(settings)
        self.root.menubar.optimItem["settings"].Enable(settings)
        self.root.panel_polezero.enable(settings)

    def event_handler_btn_parse_solve(self, event):
        assert (not self.worker_lock.locked())  # Buttons are disabled while solving so should never be called

        self.enable_parse_solve(False)  # TODO: Move this to callback_worker_thread_event, create event parse_solve_start
        self.enable_optimize(False, settings=True)  # TODO: Move this to callback_worker_thread_event, create event parse_solve_start
        self.parser_solver_called_while_typing = False
        self.worker_thread = threading.Thread(target=self.parser_solver_thread_fun)
        self.worker_thread.start()

    def event_handler_btn_optimize(self, event):
        if self.btn_optimize.GetLabelText() == "Stop":
            # The worker thread will catch this flag and stop after finishing current iteration
            self.root.engine.stop_flag = True  # Supposed to be atomic operation
            self.btn_optimize.Enable(False)
            self.root.statusbar.SetStatusText("Stopping optimization...")  # NO move this to callback, optimizer has delay before handling flag
        else:
            self.enable_optimize(False, settings=False, stop=True)
            self.enable_parse_solve(False)
            self.root.statusbar.SetStatusText("Starting optimization...")   # TODO: Move this to callback_worker_thread_event, create event optimize_start
            self.notebook.SetSelection(1)

            # Launch least squares optimization in a separate thread
            self.worker_thread = threading.Thread(target=self.optimizer_thread_fun)
            self.worker_thread.start()

    def optimizer_thread_fun(self):
        with self.worker_lock:
            self.engine.optimize()

    def parser_solver_thread_fun(self):

        # Do-while loop to repeat Parse & Solve if netlist has been changed after Solve
        while True:

            # Do-while loop to repeat Parse if netlist has been changed after Parse
            while True:

                # The lock must be inside the loop.
                # Otherwise, events are released to the GUI while the thread has the lock.
                with self.worker_lock:
                    self.changed_flag.clear()

                    # Depending on which tab is selected, use netlist or netlist_optimized
                    self.selected_tab = self.notebook.GetSelection()
                    if self.notebook.GetSelection() == 0:
                        parser_status = self.engine.parse(self.root.app_state.netlist)
                    else:
                        parser_status = self.engine.parse(self.root.app_state.netlist_optimized)

                    if self.parser_solver_called_while_typing:
                        # Delay to not call parser too often
                        time.sleep(0.5)

                if len(self.changed_flag) == 0:
                    # Not changed during parser, exit the parser Do-while loop, and proceed to solve
                    break
                else:
                    # Netlist text changed during parser. Must parse again.
                    # Depending on which tab is selected, update netlist or netlist_optimized
                    if self.notebook.GetSelection() == 0:
                        self.root.app_state.netlist = self.txt_spice.GetValue()
                    else:
                        self.root.app_state.netlist_optimized = self.txt_spice_optimized.GetValue()
                    self.debug_print("Changed before starting solving")

            if parser_status:
                # Parser completed correctly
                if self.parser_solver_called_while_typing and not self.root.app_state.solve_while_typing:
                    # Parser was called while typing and solve while typing is disabled
                    wx.PostEvent(self.root, ResultEvent("parser_ok", self.engine))
                else:
                    # Parser was not called while typing, call solver.
                    wx.PostEvent(self.root, ResultEvent("parser_ok_solving", self.engine))
                    with self.worker_lock:
                        solver_status = self.engine.solve()

                        if self.parser_solver_called_while_typing:
                            # Delay to not call parser & solver too often TODO maybe this should go after ResultEvent
                            time.sleep(0.5)

                    wx.PostEvent(self.root, ResultEvent("solver_ok" if solver_status else "solver_error", self.engine))

            else:
                if self.parser_solver_called_while_typing:
                    # Delay to not call parser & solver too often TODO maybe this should go after ResultEvent
                    time.sleep(0.1)

                r = ResultEvent("parser_error", self.engine)
                wx.PostEvent(self.root, r)  # Event handled by callback_engine_thread_event

            if len(self.changed_flag) == 0:
                # Not changed during solve, exit the parser & solve Do-while loop
                break
            else:
                # Changed while solving, must parse & solve again
                # Depending on which tab is selected, update netlist or netlist_optimized
                self.selected_tab = self.notebook.GetSelection()
                if self.notebook.GetSelection() == 0:
                    self.root.app_state.netlist = self.txt_spice.GetValue()
                else:
                    self.root.app_state.netlist_optimized = self.txt_spice_optimized.GetValue()
                self.debug_print("Changed after starting solving")

    def fill_combos(self):
        inexpr_bak = self.root.app_state.inexpr
        outexpr_bak = self.root.app_state.outexpr

        # Workaround: Need to unbind before .Clear() because .Clear() activates the event
        self.combobox_in.Unbind(wx.EVT_CHOICE)
        self.combobox_out.Unbind(wx.EVT_TEXT)

        self.combobox_out.Clear()
        self.combobox_in.Clear()

        # Fill up the combo boxes with an incomplete list of valid expressions
        input_exprs, output_exprs = self.engine.get_list_input_output_expressions()

        for el in output_exprs:
            self.combobox_out.Append(el)

        for el in input_exprs:
            self.combobox_in.Append(el)

        # Check if current output expression is valid
        outexpr_valid, _, _ = self.engine.validate_output_expr()

        if outexpr_valid is not None:
            # The output expression is valid
            # self.root.app_state.outexpr = outexpr_bak
            pass

        else:
            # The output expression is not valid
            if len(output_exprs) != 0 and len(outexpr_bak) == 0:
                self.root.app_state.outexpr = output_exprs[0]

        self.combobox_out.ChangeValue(self.root.app_state.outexpr)

        if inexpr_bak in input_exprs:
            # The input expression is valid
            # self.root.app_state.inexpr = inexpr_bak
            pass

        else:
            # The input expression is not valid
            if len(input_exprs) != 0 and len(inexpr_bak) == 0:
                self.root.app_state.inexpr = input_exprs[0]

        self.combobox_in.SetSelection(self.combobox_in.FindString(self.root.app_state.inexpr))

        self.combobox_in.Bind(wx.EVT_CHOICE, self.event_handler_combobox)
        self.combobox_out.Bind(wx.EVT_TEXT, self.event_handler_combobox)
