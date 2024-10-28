import math
import re

def eng2num(strng):
    if not strng:
        return float('nan')

    # SPICE compatibility
    strng = strng.replace("Meg", "M")
    strng = strng.replace("MEG", "M")
    strng = strng.replace("meg", "M")

    c = strng[-1]

    if c.isdigit():
        try:
            return float(strng)
        except ValueError:
            return float('nan')

    else:
        if c == 'k':
            c = 'K'

        try:
            p = 'afpnum.KMGTPE'.index(c)
            p = (p - 6) * 3
            try:
                return float(strng[0:-1]) * (10 ** p)
            except ValueError:
                return float('nan')
        except ValueError:
            return float('nan')

def eng2num_replace(strng):
    regex = r"(^|[^0-9a-zA-Z.])([0-9]*[\.]?[0-9]+[afpnumkKMGTPE]?)"
    #matches = re.findall(regex, strng, re.MULTILINE)
    #for m in matches:
    #    g = m[1]
    #    v = eng2num(g)
    #    if not math.isnan(v):
    #        strng = strng.replace(g, str(v))

    def fun(m: re.Match):
        g = m.group(0)
        v = eng2num(g)
        if math.isnan(v):
            return g
        else:
            return str(v)

    return re.sub(regex, fun, strng)


def num2eng(n, ndigits: int = 5):
    if math.isnan(n):
        return "NaN"

    if n == 0:
        return "0"

    L = math.floor(math.log10(abs(n)) / 3)

    if L==0:
        return str.format('{0:.' + str(ndigits) + 'g}', n)
    else:
        L = max(-6, min(6, L))
        c = 'afpnum.KMGTPE'[L+6]
        return str.format('{0:.' + str(ndigits) + 'g}', n / (1000 ** L)) + c
