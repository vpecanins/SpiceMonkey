import wx
import sys

from WxMainWindow import WxMainWindow
from Engine import Engine
from AppState import AppState
from RunTests import run_test

import argparse

# Press the green button in the gutter to run the script.
if __name__ == '__main__':

    arg_parser = argparse.ArgumentParser(
        description="A self-contained circuit analysis and optimization toolbox.")
    arg_parser.add_argument('-b', '--batch', help='Run in batch mode without GUI', action='store_true')
    arg_parser.add_argument('-t', '--test', help='Run tests', action='store_true')
    arg_parser.add_argument('-v', '--verbose', help='Print all debug messages', action='store_true')
    arg_parser.add_argument('statefile', nargs="?", default="", help='Load state from JSON file (default: ./state.json)')
    args = arg_parser.parse_args()

    if args.test:
        print("Running tests...")
        if args.statefile == "":
            tests = ["simplerc1", "simplerc2", "group2", "transformer", "pdsm1", "pdsm2", "pdsm3", "pdsm4",
                     "inductor", "esource", "gsource", "fsource", "hsource", "opamp"]
        else:
            tests = [args.statefile]
        for test in tests:
            print("Running test: " + test + "... ", end="")
            error = run_test(test, enable_plot=args.verbose, debug=args.verbose)
            # error = run_test(test, enable_plot=True, debug=True)
            if error > 0 and error < 10:
                print("PASSED (Error: {:.2f})".format(error))
            else:
                print("FAILED (Error: {:.2f})".format(error))
                exit()
    else:
        app_state = AppState()
        app_state._debug = args.verbose
        app_state._batch_mode = args.batch

        if args.batch:
            if args.statefile == "":
                print("State file required for batch mode")
                exit()
            else:
                try:
                    app_state.load(args.statefile)

                    print("Loaded statefile '%s'." % args.statefile)

                    def engine_callback(s, event_type):
                        pass

                    # Create engine and launch steps in batch mode
                    engine = Engine(app_state, engine_callback)

                    # Parse netlist
                    parser_status = engine.parse(app_state.netlist)

                    if parser_status:
                        # Parser completed successfully, call solver
                        solver_status = engine.solve()

                        if solver_status:
                            # Solver completed successfully
                            # Call optimizer
                            optimize_status = engine.optimize()

                            if optimize_status:
                                print("Optimization finished")
                                print()
                                print("Original netlist:")
                                print(app_state.netlist)
                                print()
                                print("Optimized netlist:")
                                print(app_state.netlist_optimized)
                                print()
                                sys.exit(0)
                            else:
                                print("Optimization error.")
                                sys.exit(3)

                        else:
                            # Solver error
                            print("Solver error: " + engine.error_msg)
                            sys.exit(2)
                    else:
                        # Parser error
                        print("Parser error: " + engine.error_msg)
                        sys.exit(1)

                except IOError:
                    print("Cannot open file '%s'." % args.statefile)
                    sys.exit(1)
        else:
            print("Starting WxWidgets version: " + str(wx.version()))

            if args.statefile == "":
                print("State file not specified, trying to load state.json")
                file_path = "state.json"
            else:
                file_path = args.statefile

            try:
                app_state.load(file_path)

                print("Loaded statefile '%s'." % file_path)

            except IOError:
                print("Cannot open file '%s'." % file_path)

                # Exit if user specified file is not found
                if args.statefile == "":
                    print("Using built-in defaults")
                else:
                    exit()

            app = wx.App(redirect=False)
            frm = WxMainWindow(app, app_state)
            app.SetTopWindow(frm)
            frm.Show(True)
            app.MainLoop()




