examples = {
    "1st order RC lowpass filter": {
        "freqmin": 10.0,
        "freqmax": 10000000000.0,
        "npoints": 28.0,
        "magnitude": 1,
        "phase": 0,
        "pztable": [
            [
                "Pole real",
                4000.0,
                1
            ]
        ],
        "inexpr": "Vin",
        "outexpr": "V(out)",
        "netlist": "; Simple 1st-order RC lowpass filter\nVin 1 0 1 AC 1\nR1 out 1 5M\nC1 out 0 10p",
    },
    "2nd order RC lowpass filter": {
        "freqmin": 10.0,
        "freqmax": 10000000000.0,
        "npoints": 28.0,
        "magnitude": 1,
        "phase": 0,
        "pztable": [
            [
                "Pole real",
                4000.0,
                1
            ],
            [
                "Pole real",
                4000.0,
                1
            ]
        ],
        "inexpr": "Vin",
        "outexpr": "V(out)",
        "netlist": "; Simple 2nd-order RC lowpass filter\nVin 1 0 1 AC 1\nR1 2 1 5M\nC1 2 0 10p\nR2 2 out 5M\nC2 out 0 10p\n",
    },
    "Fixed components": {
        "freqmin": 10.0,
        "freqmax": 10000000000.0,
        "npoints": 28.0,
        "magnitude": 1,
        "phase": 0,
        "pztable": [
            [
                "Pole real",
                4000.0,
                1
            ],
            [
                "Pole real",
                100000.0,
                1
            ]
        ],
        "inexpr": "Vin",
        "outexpr": "V(out)",
        "netlist": "; Example with fixed components\nVin 1 0 1 AC 1\nR1 2 1 5M\nC1 2 0 10p*\nR2 2 out 5M\nC2 out 0 10p*\n",
    },
    "Expression-based components": {
        "freqmin": 10.0,
        "freqmax": 10000000000.0,
        "npoints": 28.0,
        "magnitude": 1,
        "phase": 0,
        "pztable": [
            [
                "Pole real",
                4000.0,
                1
            ],
            [
                "Pole real",
                100000.0,
                1
            ]
        ],
        "inexpr": "Vin",
        "outexpr": "V(out)",
        "netlist": "; Example with expression-based components\nVin 1 0 1 AC 1\nR1 2 1 5M\nC1 2 0 10p*\nR2 2 out 5M\nC2 out 0 {10*C1}\n",
    },
    "Per-component bounds": {
        "freqmin": 10.0,
        "freqmax": 10000000000.0,
        "npoints": 28.0,
        "magnitude": 1,
        "phase": 0,
        "pztable": [
            [
                "Pole real",
                4000.0,
                1
            ],
            [
                "Pole real",
                100000.0,
                1
            ]
        ],
        "inexpr": "Vin",
        "outexpr": "V(out)",
        "netlist": "; Example with per-component bounds\nVin 1 0 1 AC 1\nR1 2 1 5M\nC1 2 0 10p*\nR2 2 out 5M max=10M\nC2 out 0 10p min=1p max=100p\n",
    }
}
