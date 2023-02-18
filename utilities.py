# pylint: disable=broad-except, unspecified-encoding
"""
 ╔╗ ┬┌┬┐┌─┐┬ ┬┌─┐┬─┐┌─┐┌─┐  ╔╦╗┌─┐─┐ ┬  ╦ ╦─┐ ┬
 ╠╩╗│ │ └─┐├─┤├─┤├┬┘├┤ └─┐   ║║├┤ ┌┴┬┘  ║ ║┌┴┬┘
 ╚═╝┴ ┴ └─┘┴ ┴┴ ┴┴└─└─┘└─┘  ═╩╝└─┘┴ └─  ╚═╝┴ └─
Bitshares Decentralized Exchange User Experience
"""
# STANDARD MODULES
import contextlib
import math
import os
import sys
import time
from datetime import datetime
from json import loads as json_loads
from threading import Thread
from traceback import format_exc

# GLOBAL CONSTANTS
ATTEMPTS = 3
PATH = f"{str(os.path.dirname(os.path.abspath(__file__)))}/"


class NonceSafe:
    """
    ╔═══════════════════════════════╗
    ║ ╔╗╔╔═╗╔╗╔╔═╗╔═╗  ╔═╗╔═╗╔═╗╔═╗ ║
    ║ ║║║║ ║║║║║  ║╣   ╚═╗╠═╣╠╣ ║╣  ║
    ║ ╝╚╝╚═╝╝╚╝╚═╝╚═╝  ╚═╝╩ ╩╚  ╚═╝ ║
    ╚═══════════════════════════════╝

    context manager for process-safe nonce generation and inter process communication
        nonce generation
        process safe read
        process safe write
        process safe atomic read/write
    wtfpl litepresence.com 2022
    """

    @staticmethod
    def __enter__(*_) -> None:
        """
        file lock: try until success to change name of nonce.vacant to nonce.occupied
        """
        if not os.path.exists(f"{PATH}nonce_safe/nonce.vacant") and not os.path.exists(
            f"{PATH}nonce_safe/nonce.occupied"
        ):
            NonceSafe.restart()
        while True:
            # fails when nonce.occupied
            try:
                os.rename("nonce_safe/nonce.vacant", "nonce_safe/nonce.occupied")
                break
            except Exception:
                time.sleep(0.01)

    @staticmethod
    def __exit__(*_) -> None:
        """
        file unlock : change name of nonce.occupied back to nonce.vacant
        """
        os.rename("nonce_safe/nonce.occupied", "nonce_safe/nonce.vacant")

    @staticmethod
    def restart() -> None:
        """
        new locker: on startup, delete directory and start fresh
        """
        os.system(
            f"rm -r {PATH}nonce_safe; "
            + f"mkdir {PATH}nonce_safe; "
            + f"touch {PATH}nonce_safe/nonce.vacant"
        )
        thread = Thread(target=NonceSafe.free)
        thread.start()

    @staticmethod
    def free() -> None:
        """
        the nonce locker should never be occupied for more than a few milliseconds
        plausible the locker could get stuck, e.g. a process terminates while occupied
        """
        while True:
            # check every three seconds if the nonce is vacant
            if os.path.exists(f"{PATH}nonce_safe/nonce.vacant"):
                time.sleep(3)
            else:
                # check repeatedly for 3 seconds for vacancy
                start = time.time()
                while True:
                    elapsed = time.time() - start
                    if os.path.exists(f"{PATH}nonce_safe/nonce.vacant"):
                        break
                    # liberate the nonce locker
                    if elapsed > 3:
                        os.rename(
                            "nonce_safe/nonce.occupied", "nonce_safe/nonce.vacant"
                        )


def get_nonce(precision: int = 1e9) -> int:
    """
    :param precision: int(10^n)
    :return nonce:
    """
    with NonceSafe():
        now = int(time.time() * precision)
        while True:
            nonce = int(time.time() * precision)
            if nonce > now:
                return nonce
            time.sleep(1 / (10 * precision))


def chunks(l, n):
    """Yield n number of striped chunks from l."""
    return [l[i::n] for i in range(n)]


def is_whitelisted(asset):
    """
    return the whitelisting status of the asset
    """
    grey = 3  # Not Rated
    if asset == "BTS":
        grey = 6
    elif "COMPUMATRIX" in asset:
        grey = 1  # Blacklisted
    elif asset == "CNY":
        grey = 2  # Not Recommended
    elif ("XBTSX" in asset) or ("GDEX" in asset):
        grey = 4  # Whitelisted
    elif "HONEST" in asset:
        grey = 6 if ("BTC" in asset) or ("USD" in asset) else 5
    return grey * (255 / 6)


def it(style, text):
    """
    Color printing in terminal
    """
    emphasis = {
        "red": 91,
        "green": 92,
        "yellow": 93,
        "blue": 94,
        "purple": 95,
        "cyan": 96,
        "orange": "38;5;202",
    }
    return f"\033[{emphasis[style]}m{str(text)}\033[0m"


# ~ def block_print():
# ~ """
# ~ temporarily disable printing
# ~ """
# ~ sys.stdout = open(os.devnull, "w")


# ~ def enable_print():
# ~ """
# ~ re-enable printing
# ~ """
# ~ sys.stdout = sys.__stdout__


def trace(error):
    """
    print and return stack trace upon exception
    """
    msg = str(type(error).__name__) + "\n"
    msg += str(error.args) + "\n"
    msg += str(format_exc()) + "\n"
    print(msg)
    return msg


def sigfig(number, n_figures=6):
    """
    Formats a number to have a specified number of significant figures.
    The number is rounded to the nearest significant figure. If the number is
    zero or close to zero, it is returned as 0.0. Positive and negative infinity
    and NaN are returned as-is.
    Parameters:
    number (float): The number to be formatted.
    n_figures (int, optional): The number of significant figures to be displayed (default is 6).
    Returns:
    float: The formatted number.
    """
    if number == 0 or number != number or math.isinf(number):
        return number
    elif number > 10**-15:
        return round(
            number, -int(math.floor(math.log10(abs(number)))) + (n_figures - 1)
        )
    else:
        return 0.0


# ~ def no_sci(flt, n_figures=6):
# ~ """
# ~ format floats without scientific notation
# ~ """
# ~ flt = str(sigfig(flt, n_figures))
# ~ was_neg = False
# ~ return_val = _extracted_from_no_sci_8(flt, was_neg) if "e" in flt else flt
# ~ return return_val.ljust(n_figures - len(return_val.lstrip(".0")), "0")

# ~ # TODO Rename this here and in `no_sci`
# ~ def _extracted_from_no_sci_8(flt, was_neg):
# ~ if flt.startswith("-"):
# ~ flt = flt[1:]
# ~ was_neg = True
# ~ str_vals = str(flt).split("e")
# ~ coef = float(str_vals[0])
# ~ exp = int(str_vals[1])
# ~ result = ""
# ~ if exp > 0:
# ~ result += str(coef).replace(".", "")
# ~ result += "".join(["0" for _ in range(abs(exp - len(str(coef).split(".")[1])))])
# ~ elif exp < 0:
# ~ result += "0."
# ~ result += "".join(["0" for _ in range(abs(exp) - 1)])
# ~ result += str(coef).replace(".", "")
# ~ if was_neg:
# ~ result = f"-{result}"
# ~ return result
def nbsp(count):
    """
    returns a string of multiple non breaking spaces
    """
    return "".join("&nbsp;" for _ in range(count))


def no_sci(flt, n_figures=6):
    """
    Formats a float to a specified number of figures, avoiding scientific notation.
    Parameters:
    flt (float): The float to be formatted.
    n_figures (int, optional): The number of figures to be displayed (default is 6).
    Returns:
    str: The formatted float.
    """
    flt = str(sigfig(float(flt), n_figures))
    was_neg = False
    if "e" in flt:
        if flt.startswith("-"):
            flt = flt[1:]
            was_neg = True
        str_vals = flt.split("e")
        coef = float(str_vals[0])
        exp = int(str_vals[1])
        result = ""
        if exp > 0:
            result += str(coef).replace(".", "")
            result += "".join(
                ["0" for _ in range(abs(exp - len(str(coef).split(".")[1])))]
            )
        elif exp < 0:
            result += "0."
            result += "".join(["0" for _ in range(abs(exp) - 1)])
            result += str(coef).replace(".", "")
        if was_neg:
            result = f"-{result}"
        flt = result
    return flt.ljust(n_figures - len(flt.lstrip(".0")), "0")


# ~ def race_write(doc="", text=""):
# ~ """
# ~ Concurrent Write to File Operation
# ~ """
# ~ text = str(text)
# ~ i = 0
# ~ doc = f"{PATH}pipe/{doc}"
# ~ while True:
# ~ try:
# ~ time.sleep(0.05 * i ** 2)
# ~ i += 1
# ~ with open(doc, "w+") as handle:
# ~ handle.write(text)
# ~ handle.close()
# ~ break
# ~ except Exception as error:
# ~ msg = str(type(error).__name__) + str(error.args)
# ~ msg += " race_write()"
# ~ print(msg)
# ~ with contextlib.suppress(Exception):
# ~ handle.close()
# ~ continue
# ~ finally:
# ~ with contextlib.suppress(Exception):
# ~ handle.close()


# ~ def race_read_json(doc=""):
# ~ """
# ~ Concurrent Read JSON from File Operation
# ~ """
# ~ doc = f"{PATH}pipe/{doc}"
# ~ i = 0
# ~ while True:
# ~ try:
# ~ time.sleep(0.05 * i ** 2)
# ~ i += 1
# ~ with open(doc, "r") as handle:
# ~ data = json_loads(handle.read())
# ~ handle.close()
# ~ return data
# ~ except Exception as error:
# ~ msg = str(type(error).__name__) + str(error.args)
# ~ msg += " race_read_json()"
# ~ print(msg)
# ~ with contextlib.suppress(Exception):
# ~ handle.close()
# ~ continue
# ~ finally:
# ~ with contextlib.suppress(Exception):
# ~ handle.close()
def to_iso_date(unix):
    """
    returns CONSTANTS.core.ISO8601 datetime given unix epoch
    """
    return datetime.utcfromtimestamp(int(unix / 1000)).isoformat()


def from_iso_date(date):
    """
    returns unix epoch given YYYY-MM-DD
    """
    return int(time.mktime(time.strptime(str(date), "%Y-%m-%d %H:%M:%S")))
