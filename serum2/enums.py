"""Factory-verified enum values for Serum 2 parameters."""

WARP_MODES = [
    "kSync", "kBendPos", "kBendNeg", "kBendPosNeg",
    "kFM_OSC", "kFM_OSC2", "kRM_OSC", "kPWM",
    "kASYMPos", "kASYMNeg", "kSelfPD",
    "kDistSoftSat", "kDistLinFold", "kDistTube",
    "kFilterLPF", "kPD_OSC",
]

VOICE_FILTER_TYPES = [
    "L12", "L24", "L18", "MgL18", "MgL24",
    "LadderMg", "LadderAcid", "LadderEMS", "DirtyMg", "Scream3LP",
    "B12", "B24", "BN12", "LN12", "LNH12", "LNH24",
    "Combs", "CombL6N", "CombHL6P", "DistComb2LP",
    "Exp", "ExpBPF", "PZ_SVF", "Phase48P",
    "FlangeP", "FlangePhase12HL6P", "Diffuser", "Reverb1",
    "FormantONE", "FormantTWO", "Wsp", "RM",
]

BASIC_VOICE_FILTER_TYPES = {
    "L12", "L24", "L18", "L6", "H12", "H24", "B12", "B24", "N12", "LN12", "BN12",
}

FX_FILTER_TYPES = [
    "L12", "L24", "L18", "N12", "LN12", "B24", "BN12",
    "H12", "DJMixer", "LadderMg", "LadderAcid",
    "Scream3LP", "Scream3BP", "Combs", "PZ_SVF",
]

DISTORTION_MODES = [
    "kSoftClip", "kHardClip", "kSoftSat", "kTapeSat",
    "kDiode1", "kDiode2", "kLinFold", "kSinFold",
    "kOverdrive", "kStompBox", "kAsym", "kDownsample",
    "kRectify", "kSineShaper", "kXShaper", "kZeroSquare",
]

LFO_TYPES = ["Path", "Lorenz", "Rossler", "RandomSH"]

LFO_MODES = ["Free", "Envelope", "Trigger"]

# Static fallback list — prefer paths.find_wavetables() when Serum 2 is installed.
WAVETABLES = [
    "S2 Tables/Default Shapes.wav",
    "Analog/Basic Shapes.wav", "Analog/Basic Mg.wav", "Analog/Basic Mini.wav",
    "Analog/BS2 - Acid.wav", "Analog/BS2 - Filthy.wav", "Analog/BS2 - Subby Saw.wav",
    "Analog/MB Saw.wav", "Analog/SawRounded.wav", "Analog/SawRoundedToSquare.wav",
    "Analog/PWM Juno.wav", "Analog/PWM Mini.wav", "Analog/PWM Inception.wav",
    "Analog/Jno.wav", "Analog/MsAw.wav", "Analog/MiniBass.wav", "Analog/Acid.wav",
    "Analog/4088.wav", "Analog/BSOD_Square.wav", "Analog/MATRIXY C64.wav",
    "S2 Tables/Analog/Saw Drift.wav", "S2 Tables/Analog/Saw Drift 303.wav",
    "S2 Tables/Analog/Saw Square.wav", "S2 Tables/Analog/Saw to Square.wav",
    "S2 Tables/Analog/Saw Ripple.wav", "S2 Tables/Analog/Saw Phasey.wav",
    "S2 Tables/Analog/PolySaw II.wav", "S2 Tables/Analog/Sub - Driven Saws.wav",
    "S2 Tables/Analog/Subby Roller.wav", "S2 Tables/Analog/Warm Sub.wav",
    "S2 Tables/Analog/MWoog.wav", "S2 Tables/Analog/Modular18.wav",
    "S2 Tables/Analog/Triangle Sub Morph.wav", "S2 Tables/Analog/No Fund Tri Saw Sq.wav",
    "S2 Tables/Analog/Zero Feels.wav",
    "Digital/Reese.wav", "Digital/Evol Longreece.wav", "Digital/Gritty.wav",
    "Digital/Kream.wav", "Digital/Sludgecrank.wav", "Digital/DirtySaw.wav",
    "Digital/CrushWub.wav", "Digital/SubBass_1.wav", "Digital/Dist Bass Dropper.wav",
    "Digital/Dist C2.wav", "Digital/Dist Fwapper SQ.wav", "Digital/Wraith.wav",
    "Digital/Razor.wav", "Digital/Scream.wav", "Digital/FM_Splat.wav",
    "Digital/FM_Freak.wav", "Digital/FMFM.wav", "Digital/bipole_harmonic.wav",
]

FX_TYPE_IDS = {
    "FXDistortion": 0,
    "FXFilter": 1,
    "FXDelay": 2,
    "FXReverb": 3,
    "FXChorus": 4,
    "FXFlanger": 5,
    "FXPhaser": 7,
    "FXComp": 10,
    "FXEQ": 11,
    "FXUtils": 12,
    "FXHyperD": 13,
    "FXBode": 14,
}

ENUM_REGISTRY = {
    "kParamWarpMenu": WARP_MODES,
    "VoiceFilter.kParamType": VOICE_FILTER_TYPES,
    "FXFilter.kParamType": FX_FILTER_TYPES,
    "kParamMode": DISTORTION_MODES,
    "kParamType": LFO_TYPES,
}
