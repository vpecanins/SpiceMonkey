from Engine import Engine
from AppState import AppState

import subprocess
import numpy as np
import os.path
import matplotlib.pyplot as plt
import matplotlib
import math


def run_ltspice(app_state: AppState, test_name: str, debug=False):

    # If test has a ngspice-specific netlist, copy it, otherwise use same netlist as used by Engine
    if hasattr(app_state, "netlist_ltspice"):
        netlist = app_state.netlist_ltspice + ""
    else:
        netlist = app_state.netlist + ""

    netlist_translate = netlist.replace("M", "Meg")
    netlist_translate = netlist_translate.replace("*", "")
    netlist_translate = netlist_translate.replace(";", "*")

    if debug:
        print(netlist_translate)

    cir_filename = "/home/peca/.wine/drive_c/Program Files/LTC/LTspiceXVII/" + test_name + ".cir"
    output_filename = "/home/peca/.wine/drive_c/Program Files/LTC/LTspiceXVII/" + test_name + ".raw"

    numdecades = np.log10(app_state.freqmax / app_state.freqmin)
    points_per_decade = int(np.round(app_state.npoints / numdecades))
    # print("Make npoints = " + str(points_per_decade * numdecades + 1))

    outexpr = app_state.outexpr

    txt = netlist_translate + "\n"
    txt = txt + ".ac dec " + str(points_per_decade) + " " + str(app_state.freqmin) + " " + \
          str(app_state.freqmax) + "\n.save I(R1)\n.backanno\n.end\n"

    f = open(cir_filename, "w")
    f.write(txt)
    f.close()

    cmd = ["wine-stable",
        "/home/peca/.wine/drive_c/Program Files/LTC/LTspiceXVII/XVIIx64.exe",  "-Run", "-b",
        "C:\\Program Files\\LTC\\LTspiceXVII\\"+test_name+".cir",  "-ascii"]

    my_env = os.environ.copy()
    my_env["WINEPREFIX"] = "/home/peca/.wine"

    if debug:
        subprocess.run(cmd, env=my_env)
    else:
        subprocess.run(cmd, env=my_env,
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.STDOUT)

    if os.path.isfile(output_filename):
        with open(output_filename, 'r') as file:
            data = file.read().split("Values:\n")[1].replace("\n\t", ",").replace("\t\t", ",")

        with open(output_filename, 'w') as file:
            file.write(data)

        M = np.loadtxt(output_filename, dtype=float, delimiter=",")

        os.remove(output_filename)
        os.remove(cir_filename)

        return M[:, (1,3,4)]
    else:
        print("File not found: " + output_filename)
        return None

def run_ngspice(app_state: AppState, test_name: str, debug=False):

    # If test has a ngspice-specific netlist, copy it, otherwise use same netlist as used by Engine
    if hasattr(app_state, "netlist_ngspice"):
        netlist = app_state.netlist_ngspice + ""
    else:
        netlist = app_state.netlist + ""

    netlist_translate = netlist.replace("M", "Meg")
    netlist_translate = netlist_translate.replace("*", "")
    netlist_translate = netlist_translate.replace(";", "*")

    if debug:
        print(netlist_translate)

    cir_filename = "test_netlists/" + test_name + ".cir"
    output_filename = "test_netlists/" + test_name + "output.txt"

    numdecades = np.log10(app_state.freqmax / app_state.freqmin)
    points_per_decade = int(np.round(app_state.npoints / numdecades))
    #print("Make npoints = " + str(points_per_decade * numdecades + 1))

    outexpr = app_state.outexpr

    txt = ".title " + test_name + "\n"
    txt = txt + netlist_translate + "\n"
    txt = txt + ".control\n" + \
        "ac dec " + str(points_per_decade) + " " + str(app_state.freqmin) + " " + str(app_state.freqmax) + "\n" + \
        "set wr_singlescale\n" + \
        "set wr_vecnames\n" + \
        "wrdata " + output_filename + " " + outexpr +"\n" + \
        "exit\n" + \
        ".endc\n\n" + \
        ".end\n"

    f = open(cir_filename, "w")
    f.write(txt)
    f.close()


    if debug:
        subprocess.run(["ngspice", "test_netlists/" + test_name + ".cir"])
    else:
        subprocess.run(["ngspice", "test_netlists/" + test_name + ".cir"],
                       stdout=subprocess.DEVNULL,
                        stderr=subprocess.STDOUT)

    if os.path.isfile(output_filename):
        M = np.loadtxt(output_filename, dtype=float, skiprows=1)
        os.remove(output_filename)
        os.remove(cir_filename)
        return M
    else:
        print("File not found: " + output_filename)
        return None

def run_test(test_name: str, enable_plot=True, debug=False):
    file_json = "test_netlists/"+test_name+".json"
    if debug:
        print("\n[DEBUG] Loading app_state from file: " + file_json)

    app_state = AppState()
    app_state.load(file_json)

    if hasattr(app_state, "skip_ltspice"):
        skip_ltspice = app_state.skip_ltspice
    else:
        skip_ltspice = False

    if hasattr(app_state, "skip_ngspice"):
        skip_ngspice = app_state.skip_ngspice
    else:
        skip_ngspice = False

    if not skip_ngspice:
        M_ngspice = run_ngspice(app_state, test_name, debug)

        if M_ngspice is None:
            print("[DEBUG] Error running ngspice")
            return -1

        # NGSpice produces results in real imag format, convert to dB and degrees
        re = M_ngspice[:, 1]
        im = M_ngspice[:, 2]
        mag = np.sqrt(np.power(re, 2) + np.power(im, 2))
        ph  = np.unwrap(np.angle(re + 1j * im))  # Unwrap phase

        M_ngspice[:, 1] = 20*np.log10(mag)  # Magnitude in dB
        M_ngspice[:, 2] = ph*180 / math.pi  # Convert radians into degrees for phase

    if not skip_ltspice:
        M_ltspice = run_ngspice(app_state, test_name, debug)

        if M_ltspice is None:
            print("[DEBUG] Error running LTspice")
            return -1

        # LTSpice produces results in real imag format, convert to dB and degrees
        re = M_ltspice[:, 1]
        im = M_ltspice[:, 2]
        mag = np.sqrt(np.power(re, 2) + np.power(im, 2))
        ph = np.unwrap(np.angle(re + 1j * im))  # Unwrap phase

        M_ltspice[:, 1] = 20 * np.log10(mag)  # Magnitude in dB
        M_ltspice[:, 2] = ph * 180 / math.pi  # Convert radians into degrees for phase

    def cb_step(engine: Engine, s: str):
        pass

    engine = Engine(app_state, cb_step)
    engine.enable_print_debug = debug

    if not engine.parse(app_state.netlist):
        print("[DEBUG] Error running spicemonkey parser")
        return -1

    if not engine.solve():
        print("[DEBUG] Error running spicemonkey solver")
        return -1

    # The solved circuit frequency response is in h_initial
    f_vec = engine.get_f_axis()
    b_initial = engine.get_freqresponse(engine.h_initial)

    M_spicemonkey = np.transpose(np.vstack((f_vec, b_initial)))

    if not skip_ngspice:
        error = np.power(np.sum(np.power(M_spicemonkey - M_ngspice, 2)), 0.5) / np.sqrt(M_spicemonkey.size-1)
    else:
        error = 0

    if enable_plot:
        if not skip_ngspice:
            ax_mag = plt.subplot(2, 1, 1)
            ax_mag.semilogx(M_ngspice[:, 0], M_ngspice[:, 1], "o", label="ngspice")
            ax_ph = plt.subplot(2, 1, 2)
            ax_ph.semilogx(M_ngspice[:, 0], M_ngspice[:, 2], "o", label="ngspice")

        if not skip_ltspice:
            ax_mag = plt.subplot(2, 1, 1)
            ax_mag.semilogx(M_ltspice[:, 0], M_ltspice[:, 1], "x", label="ltspice")
            ax_ph = plt.subplot(2, 1, 2)
            ax_ph.semilogx(M_ltspice[:, 0], M_ltspice[:, 2], "x", label="ltspice")

        ax_mag = plt.subplot(2, 1, 1)
        ax_mag.semilogx(M_spicemonkey[:, 0], M_spicemonkey[:, 1], "-", label="spicemonkey")
        ax_ph = plt.subplot(2, 1, 2)
        ax_ph.semilogx(M_spicemonkey[:, 0], M_spicemonkey[:, 2], "-", label="spicemonkey")

        ax_mag.set(xlabel='Frequency [Hz]', ylabel='Magnitude [dB]')
        ax_mag.xaxis.set_major_locator(matplotlib.ticker.LogLocator(base=10.0, numticks=12))
        ax_mag.xaxis.set_major_formatter(matplotlib.ticker.EngFormatter(unit='', sep=''))
        ax_ph.set(xlabel='Frequency [Hz]', ylabel='Phase [deg]')
        ax_ph.yaxis.set_major_locator(matplotlib.ticker.MultipleLocator(45.0))
        ax_ph.yaxis.set_minor_locator(matplotlib.ticker.MultipleLocator(15.0))
        ax_ph.xaxis.set_major_locator(matplotlib.ticker.LogLocator(base=10.0, numticks=12))
        ax_ph.xaxis.set_major_formatter(matplotlib.ticker.EngFormatter(unit='', sep=''))
        plt.suptitle(test_name + " Error = " + str(error) + "\n in=" + app_state.inexpr + ", out=" + app_state.outexpr)
        ax_mag.grid()
        ax_mag.legend()
        ax_ph.grid()
        ax_ph.legend()

        plt.show()

    return error
