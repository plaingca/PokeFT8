"""Deterministic, versioned grid habitats and display-level conversions."""

import hashlib
import re

SPECIES = """BULBASAUR IVYSAUR VENUSAUR CHARMANDER CHARMELEON CHARIZARD SQUIRTLE
WARTORTLE BLASTOISE CATERPIE METAPOD BUTTERFREE WEEDLE KAKUNA BEEDRILL PIDGEY
PIDGEOTTO PIDGEOT RATTATA RATICATE SPEAROW FEAROW EKANS ARBOK PIKACHU RAICHU
SANDSHREW SANDSLASH NIDORAN_F NIDORINA NIDOQUEEN NIDORAN_M NIDORINO NIDOKING
CLEFAIRY CLEFABLE VULPIX NINETALES JIGGLYPUFF WIGGLYTUFF ZUBAT GOLBAT ODDISH
GLOOM VILEPLUME PARAS PARASECT VENONAT VENOMOTH DIGLETT DUGTRIO MEOWTH PERSIAN
PSYDUCK GOLDUCK MANKEY PRIMEAPE GROWLITHE ARCANINE POLIWAG POLIWHIRL POLIWRATH
ABRA KADABRA ALAKAZAM MACHOP MACHOKE MACHAMP BELLSPROUT WEEPINBELL VICTREEBEL
TENTACOOL TENTACRUEL GEODUDE GRAVELER GOLEM PONYTA RAPIDASH SLOWPOKE SLOWBRO
MAGNEMITE MAGNETON FARFETCHD DODUO DODRIO SEEL DEWGONG GRIMER MUK SHELLDER
CLOYSTER GASTLY HAUNTER GENGAR ONIX DROWZEE HYPNO KRABBY KINGLER VOLTORB
ELECTRODE EXEGGCUTE EXEGGUTOR CUBONE MAROWAK HITMONLEE HITMONCHAN LICKITUNG
KOFFING WEEZING RHYHORN RHYDON CHANSEY TANGELA KANGASKHAN HORSEA SEADRA GOLDEEN
SEAKING STARYU STARMIE MR_MIME SCYTHER JYNX ELECTABUZZ MAGMAR PINSIR TAUROS
MAGIKARP GYARADOS LAPRAS DITTO EEVEE VAPOREON JOLTEON FLAREON PORYGON OMANYTE
OMASTAR KABUTO KABUTOPS AERODACTYL SNORLAX ARTICUNO ZAPDOS MOLTRES DRATINI
DRAGONAIR DRAGONITE MEWTWO MEW""".split()
LEGENDARY = ["ARTICUNO", "ZAPDOS", "MOLTRES", "MEWTWO", "MEW"]
RARE = [
    "CHANSEY",
    "KANGASKHAN",
    "SCYTHER",
    "PINSIR",
    "TAUROS",
    "LAPRAS",
    "DITTO",
    "EEVEE",
    "VAPOREON",
    "JOLTEON",
    "FLAREON",
    "PORYGON",
    "OMANYTE",
    "OMASTAR",
    "KABUTO",
    "KABUTOPS",
    "AERODACTYL",
    "SNORLAX",
    "DRATINI",
    "DRAGONAIR",
    "DRAGONITE",
]
COMMON = [name for name in SPECIES if name not in LEGENDARY + RARE]


def grid4(value):
    value = (value or "").strip().upper()
    return value[:4] if re.fullmatch(r"[A-R]{2}[0-9]{2}(?:[A-X]{2})?", value) else ""


def choose_species(grid, prior_contacts=0, call=""):
    """Novel-to-this-log grids get rarer pools; assignments are saved by Dex."""
    square = grid4(grid)
    seed = square or ("CALL:" + call.upper())
    digest = hashlib.sha256(("PokeFT8-grid-v1:" + seed).encode()).digest()
    roll = int.from_bytes(digest[:4], "big") % 1000
    if square and roll < (10 if prior_contacts == 0 else 1):
        pool, rarity = LEGENDARY, "legendary"
    elif square and roll < (150 if prior_contacts == 0 else 20):
        pool, rarity = RARE, "rare"
    else:
        pool, rarity = COMMON, "common"
    return pool[int.from_bytes(digest[4:8], "big") % len(pool)], rarity


def snr_level(snr):
    # Offset signed dB into Red's positive level range; raw SNR stays in the UI.
    return 50 if snr is None else max(1, min(100, 50 - round(snr)))


def watts_level(watts):
    return max(1, min(100, round(watts)))
