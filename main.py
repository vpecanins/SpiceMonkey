import wx

from WxMainWindow import WxMainWindow
from Engine import Engine
from AppState import AppState
from RunTests import run_test

import argparse

# Press the green button in the gutter to run the script.
if __name__ == '__main__':

    arg_parser = argparse.ArgumentParser(
        description="A self-contained Python tool to simulate and optimize AC electrical circuits.")
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

        if args.batch:
            if args.statefile == "":
                print("State file required for batch mode")
                exit()
            else:
                try:
                    app_state.load(args.statefile)

                    print("Loaded statefile '%s'." % args.statefile)

                    # TODO create engine here and process data in batch mode

                except IOError:
                    print("Cannot open file '%s'." % args.statefile)
                    exit()
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




