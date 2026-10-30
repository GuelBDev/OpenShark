"""Model-specific HID feature reports based on public captures and local app resources."""

from .dpi_3311 import DPI_3311
from .profiles import BUTTON_ACTIONS


R1_DPI_TEMPLATE = bytes.fromhex(
    "04 38 01 00 00 3f 00 00 02 02 02 02 02 02 00 00 "
    "00 00 00 00 00 00 00 00 01 ff 00 00 00 ff 00 00 "
    "00 ff ff ff 00 00 ff ff ff 00 ff ff 40 00 ff ff "
    "ff 02 0d 75 00 00 00 00"
)
X6_DPI_TEMPLATE = bytes(56)
X11_DPI_TEMPLATE = bytes.fromhex(
    "04 38 01 00 01 3f 20 20 12 25 38 4b 75 81 00 00 "
    "00 00 00 00 00 01 00 00 02 ff 00 00 00 ff 00 00 "
    "00 ff ff ff 00 00 ff ff ff 00 ff ff 40 00 ff ff "
    "ff 02 0f 68 00 00 00 00"
)
BUTTON_TEMPLATE = bytes.fromhex(
    "08 3b 01 02 00 00 03 00 00 04 00 00 0d 00 00 "
    "0e 00 00 0f 00 00 06 00 00 05 00 00 3c 00 00 "
    "01 00 00 01 00 00 01 00 00 01 00 00 01 00 00 "
    "01 00 00 01 00 00 0a 00 00 09 00 00 00 94"
)


def checksum(buf, start, end, high):
    value = sum(buf[start:end]) & 0xffff
    buf[high] = value >> 8
    buf[high + 1] = value & 0xff
    return bytes(buf)


def r1_dpi_code(dpi):
    index = dpi // 100 - 1
    code = (2, 4, 6, 9, 11, 14)[index] if index < 6 else 14 + ((index - 6 + 1) // 3) + (index - 6 + 1) * 2
    return code & 0xff


def x11_dpi_code(dpi):
    if dpi == 20100:
        return 0xeb, 1, True
    doubled = dpi > 10000
    base = round(dpi / 2) if doubled else dpi
    if base > 10000:
        code = 199 + (base - 10100) // 100
        return code & 0xff, code >> 8, doubled
    if base > 5000 and base % 100 == 0:
        return DPI_3311[base // 100 - 1], 1, doubled
    return DPI_3311[(base - 50) // 50], 0, doubled


def build_dpi(profile):
    model = profile["model"]
    buf = bytearray({"R1": R1_DPI_TEMPLATE, "X6": X6_DPI_TEMPLATE,
                     "X11": X11_DPI_TEMPLATE}[model])
    if model == "R1":
        high = 0
        for i, dpi in enumerate(profile["dpi"]):
            buf[8 + i] = r1_dpi_code(dpi)
            buf[16 + i] = int(10100 <= dpi <= 12000)
            if dpi > 12000:
                high |= 1 << i
        buf[6] = buf[7] = high
    elif model == "X6":
        buf[0:3] = b"\x04\x38\x01"
        buf[5], buf[7], buf[49] = 0x3f, 1, 1
        colors = ((255, 0, 0), (0, 255, 0), (0, 0, 255),
                  (255, 255, 0), (0, 255, 255), (255, 0, 255),
                  (255, 64, 0), (255, 255, 255))
        for i, color in enumerate(colors):
            buf[25 + i * 3:28 + i * 3] = bytes(color)
        for i, dpi in enumerate(profile["dpi"]):
            encoded = dpi // 50 - 1
            buf[8 + i] = encoded & 0xff
            buf[16 + i] = encoded >> 8
        buf[6] = int(profile["angle_snap"])
    else:
        buf[6] = buf[7] = 0
        for i, dpi in enumerate(profile["dpi"]):
            x, y, doubled = x11_dpi_code(dpi)
            buf[8 + i], buf[16 + i] = x, y
            if doubled:
                buf[6] |= 1 << i
    buf[3] = int(profile["angle_snap"])
    buf[4] = int(profile["ripple"])
    buf[24] = profile["active_stage"]
    return checksum(buf, 3, 50, 50)


def build_polling(profile):
    code = {125: 8, 250: 4, 500: 2, 1000: 1}[profile["polling"]]
    return bytes((6, 9, 1, code, 0xff - code, 0, 0, 0, 0))


def build_power(profile):
    model = profile["model"]
    if model == "R1":
        buf = bytearray.fromhex("05 0f 01 00 03 18 00 00 ff 04 02 01 20 00 00")
        buf[4] = 0x03 | (profile["deep_sleep"] & 0xf0)
        buf[5] = 0x08 | ((profile["deep_sleep"] & 0x0f) << 4)
        buf[10] = profile["response"] // 2
    elif model == "X6":
        buf = bytearray.fromhex("05 0f 01 00 03 a8 00 ff 00 01 08 01 b3")
        buf[4] = (profile["deep_sleep"] & 0xf0) | 3
        buf[5] = ((profile["deep_sleep"] << 4) & 0xff) | 8
        buf[10] = profile["response"]
    else:
        buf = bytearray.fromhex("05 0f 01 00 03 a8 00 ff 00 01 04 01 af 00 00")
        buf[4] = (profile["deep_sleep"] & 0xf0) | 3
        buf[5] = ((profile["deep_sleep"] << 4) & 0xff) | 8
        buf[10] = profile["response"] // 2
    buf[9] = int(profile["sleep"] * 2)
    return checksum(buf, 3, 11, 11)


def build_buttons(profile):
    buf = bytearray(BUTTON_TEMPLATE)
    # UI order: left, right, middle, forward, back, DPI.
    for button, slot in enumerate((1, 2, 3, 7, 8, 4)):
        buf[3 + (slot - 1) * 3] = BUTTON_ACTIONS[profile["buttons"][button]]
    return checksum(buf, 3, 57, 57)


def reports_for(profile, section="all"):
    report = {"dpi": build_dpi, "polling": build_polling,
              "power": build_power, "buttons": build_buttons}
    if section == "all":
        sections = ("polling", "dpi", "power", "buttons")
    else:
        sections = (section,)
    return [report[key](profile) for key in sections]
