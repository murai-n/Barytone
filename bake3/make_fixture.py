"""Build the Capture One profile folder that t_browser.js scans.

    python3 bake3/make_fixture.py DIR        (then CO_TEST=DIR node bake3/t_browser.js)

DIR/Input gets 12 stand-in camera profiles named the way Capture One names
them: three Nikon Z5 ones (one neutral, two with a look baked in, which the
tool must mark as unsuitable), a hyphenated Sony model, and others."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../scripts"))
import test_profile
NAMES = ["NikonZ5-Nikon_-_Neutral", "NikonZ5-Nikon_-_Portrait", "NikonZ5-Nikon_-_Vivid",
         "SonyILCE-7M4-Generic", "SonyILCE-7RM4-Generic", "CanonEOSR5-Generic", "CanonEOSR6-Generic",
         "FujifilmX-T4-Generic", "LeicaQ2-Generic", "PanasonicS5-Generic", "OlympusE-M1MarkIII-Generic",
         "RicohGRIII-Generic"]
d = os.path.join(sys.argv[1], "Input"); os.makedirs(d, exist_ok=True)
for n in NAMES: open(os.path.join(d, n + ".icm"), "wb").write(test_profile.profile(n))
print(len(NAMES), "profiles in", d)
