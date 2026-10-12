from dataclasses import dataclass
from typing import Dict, List

@dataclass(frozen=True)
class Theme:
    name: str
    bg_top: str
    bg_bottom: str
    card: str
    card2: str
    text: str
    subtext: str
    accent: str
    stroke: str
    shadow: str
    grain_opacity: float

THEMES: List[Theme] = [
    Theme("Midnight Acrylic", "#07162E", "#040A14", "rgba(14,27,52,0.62)", "rgba(10,20,40,0.46)", "#EAF2FF", "rgba(234,242,255,0.70)", "#5AA6FF", "rgba(140,190,255,0.18)", "rgba(0,0,0,0.45)", 0.10),
    Theme("Deep Navy Glass", "#061B34", "#02060D", "rgba(9,26,54,0.62)", "rgba(8,18,38,0.44)", "#EAF2FF", "rgba(234,242,255,0.70)", "#7DC0FF", "rgba(160,210,255,0.18)", "rgba(0,0,0,0.48)", 0.11),
    Theme("Cobalt Night", "#071A3E", "#040813", "rgba(12,34,84,0.58)", "rgba(10,22,50,0.44)", "#EAF2FF", "rgba(234,242,255,0.70)", "#6B7CFF", "rgba(170,176,255,0.18)", "rgba(0,0,0,0.46)", 0.10),
    Theme("Indigo Aurora", "#081A33", "#040611", "rgba(18,30,78,0.58)", "rgba(10,18,42,0.44)", "#EAF2FF", "rgba(234,242,255,0.70)", "#A27CFF", "rgba(200,170,255,0.18)", "rgba(0,0,0,0.46)", 0.10),
    Theme("Polar Blue", "#061F2A", "#02070A", "rgba(12,36,44,0.58)", "rgba(10,22,28,0.44)", "#EAF2FF", "rgba(234,242,255,0.70)", "#67E3FF", "rgba(170,245,255,0.18)", "rgba(0,0,0,0.44)", 0.10),
    Theme("Steel Ocean", "#071B2A", "#03060B", "rgba(18,40,55,0.58)", "rgba(12,26,34,0.44)", "#EAF2FF", "rgba(234,242,255,0.70)", "#4DD7B5", "rgba(140,255,230,0.18)", "rgba(0,0,0,0.44)", 0.10),
    Theme("Night Sapphire", "#07193B", "#03050E", "rgba(14,29,75,0.60)", "rgba(10,18,44,0.44)", "#EAF2FF", "rgba(234,242,255,0.70)", "#4FA3FF", "rgba(150,200,255,0.18)", "rgba(0,0,0,0.47)", 0.10),
    Theme("Blueberry Ink", "#0A1530", "#040510", "rgba(20,26,62,0.58)", "rgba(12,16,40,0.44)", "#EAF2FF", "rgba(234,242,255,0.70)", "#FF6BCB", "rgba(255,170,220,0.18)", "rgba(0,0,0,0.46)", 0.10),
    Theme("Graphite Navy", "#0C1522", "#05070C", "rgba(22,28,40,0.62)", "rgba(14,18,26,0.46)", "#EAF2FF", "rgba(234,242,255,0.70)", "#8AA0B8", "rgba(200,210,220,0.18)", "rgba(0,0,0,0.50)", 0.09),
    Theme("Nebula Blue", "#071A2A", "#030712", "rgba(16,33,55,0.58)", "rgba(10,18,32,0.44)", "#EAF2FF", "rgba(234,242,255,0.70)", "#B6FF6B", "rgba(220,255,170,0.18)", "rgba(0,0,0,0.44)", 0.09),
    Theme("Royal Prism", "#0A1332", "#03040D", "rgba(22,28,90,0.58)", "rgba(14,16,44,0.44)", "#EAF2FF", "rgba(234,242,255,0.70)", "#FFD36B", "rgba(255,215,150,0.18)", "rgba(0,0,0,0.46)", 0.09)
]

def themes_map() -> Dict[str, Theme]:
    return {t.name: t for t in THEMES}
