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
    "01 00 00 01 00 00 09 00 00 0a 00 00 00 94"
)


def checksum(buf, start, end, high):
    value = sum(buf[start:end]) & 0xffff
    buf[high] = value >> 8
    buf[high + 1] = value & 0xff
    return bytes(buf)


# Exact PAW3311 R1 values from xb-bx/attack-shark-r1-driver/dpi.odin.
R1_DPI_CODES = bytes.fromhex(
    "02 04 06 09 0b 0e 10 12 15 17 19 1c 1e 20 23 25 "
    "27 2a 2c 2f 31 33 36 38 3a 3d 3f 41 44 46 48 4b "
    "4d 4f 52 54 57 59 5b 5e 60 62 65 67 69 6c 6e 70 "
    "73 75 77 7a 7c 7f 81 83 86 88 8a 8d 8f 91 94 96 "
    "98 9b 9d 9f a2 a4 a7 a9 ab ae b0 b2 b5 b7 b9 bc "
    "be c0 c3 c5 c7 ca cc cf d1 d3 d6 d8 da dd df e1 "
    "e4 e6 e8 eb 76 77 79 7a 7b 7c 7d 7f 80 81 82 83 "
    "84 86 87 88 89 8a 8b 8d 8e 8f 90 91 93 94 95 96 "
    "97 98 9a 9b 9c 9d 9e 9f a1 a2 a3 a4 a5 a7 a8 a9 "
    "aa ab ac ae af b0 b1 b2 b3 b5 b6 b7 b8 b9 bb bc "
    "bd be bf c0 c2 c3 c4 c5 c6 c7 c9 ca cb cc cd cf "
    "d0 d1 d2 d3"
)


def r1_dpi_code(dpi):
    if not 100 <= dpi <= 18000 or dpi % 100:
        raise ValueError("DPI R1 fora do intervalo ou passo de 100")
    return R1_DPI_CODES[dpi // 100 - 1]


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
        buf[3] = int(profile["angle_snap"])
        buf[4] = int(profile["ripple"])
        buf[24] = profile["active_stage"]
        return checksum(buf, 3, 50, 50)
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
    buf[0] = 0x04
    buf[1] = 0x38
    buf[2] = profile.get("active_stage", 1)
    buf[5] = 0x3F

    # Polling rate code at byte 24: 0 = 125Hz, 1 = 250Hz, 2 = 500Hz, 3 = 1000Hz
    poll_rate = profile.get("polling", 1000)
    buf[24] = {125: 0, 250: 1, 500: 2, 1000: 3}.get(poll_rate, 3)

    # LOD in byte 46 (1 or 2 mm)
    buf[46] = profile.get("lod_mm", 1)

    # Flags in byte 48 (Motion Sync bit 0, Ripple bit 1, Angle Snap bit 2)
    flags = 0x01 if profile.get("motion_sync", True) else 0x00
    if profile.get("ripple", False):
        flags |= 0x02
    if profile.get("angle_snap", False):
        flags |= 0x04
    buf[48] = flags

    # Debounce delay in byte 49
    debounce = profile.get("response", 8)
    if not (1 <= debounce <= 20):
        debounce = 8
    buf[49] = debounce

    return checksum(buf, 3, 50, 50)


def build_polling(profile):
    if profile["model"] == "R1":
        codes = {125: (0x08, 0xF7), 250: (0x04, 0xFB),
                 500: (0x02, 0xFD), 1000: (0x01, 0xFE)}
        return bytes((0x06, 0x09, 0x01, *codes[profile["polling"]], 0, 0, 0, 0))
    return build_dpi(profile)


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
        sections = ("dpi", "polling", "power", "buttons") if profile["model"] == "R1" else ("dpi", "power", "buttons")
    else:
        sections = (section,)
    return [report[key](profile) for key in sections]
