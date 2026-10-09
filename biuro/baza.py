"""Baza danych Biura (lokalnie, SQLite).

Jednostka rozliczeniowa to KOMPLEKS: sasiadujace dzialki traktowane jako calosc,
z jednym badaniem gleby i wspolna powierzchnia. Dawki i limity liczy Python.

Plik bazy: biuro/dane/biuro.db (poza gitem - dane osobowe wlascicieli).
Przy kazdym starcie aplikacji robiona jest kopia w biuro/dane/kopie/.
"""
import os
import shutil
import sqlite3
from datetime import date, datetime, timedelta

KATALOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dane")
SCIEZKA = os.environ.get("BIURO_DB") or os.path.join(KATALOG, "biuro.db")

# Limit dawki osadu (Mg suchej masy na hektar) w okresie 3 lat - praktyka firmy
# (cel nierolniczy, art. 96 ust. 1 ustawy o odpadach). Okres liczony wstecz od dzis.
LIMIT_SM_HA = 45.0
OKRES_DNI = 3 * 365

METALE = ["cd", "cr", "cu", "hg", "ni", "pb", "zn"]
NAZWY_METALI = {"cd": "Kadm", "cr": "Chrom", "cu": "Miedź", "hg": "Rtęć",
                "ni": "Nikiel", "pb": "Ołów", "zn": "Cynk"}

# Wartosci dopuszczalne dla gleby wg sprawozdan INTERLABO (rozporzadzenie w sprawie
# komunalnych osadow sciekowych, zal. 3). Wpisane tylko dla kategorii, ktora mamy
# potwierdzona w sprawozdaniu; dla innych aplikacja nie ocenia i odsyla do sprawozdania.
PROGI_GLEBY = {
    "grunt lekki": {"ph_min": 5.6, "cd": 3, "cr": 150, "cu": 50, "hg": 1, "ni": 30, "pb": 50, "zn": 150},
}
NIEPEWNOSC_PH = 0.2

SCHEMAT = """
CREATE TABLE IF NOT EXISTS oczyszczalnie (
    id INTEGER PRIMARY KEY,
    nazwa TEXT NOT NULL UNIQUE,      -- krotka nazwa robocza, np. "Raszyn"
    nazwa_bdo TEXT,                  -- nazwa wytworcy w BDO (do dopasowania kart w etapie B2)
    uwagi TEXT
);
CREATE TABLE IF NOT EXISTS wlasciciele (
    id INTEGER PRIMARY KEY,
    nazwa TEXT NOT NULL,
    telefon TEXT,
    uwagi TEXT
);
CREATE TABLE IF NOT EXISTS kompleksy (
    id INTEGER PRIMARY KEY,
    nazwa TEXT NOT NULL,
    obreb TEXT,
    gmina TEXT,
    powierzchnia_ha REAL NOT NULL CHECK (powierzchnia_ha > 0),
    kategoria_gruntu TEXT,
    wlasciciel_id INTEGER REFERENCES wlasciciele(id),
    uwagi TEXT
);
-- Kompleks moze byc przypisany do jednej oczyszczalni (duze wywozy) albo do kilku
-- (male partie kontenerami z kilku oczyszczalni na te same dzialki).
CREATE TABLE IF NOT EXISTS kompleksy_oczyszczalnie (
    kompleks_id INTEGER NOT NULL REFERENCES kompleksy(id) ON DELETE CASCADE,
    oczyszczalnia_id INTEGER NOT NULL REFERENCES oczyszczalnie(id) ON DELETE CASCADE,
    PRIMARY KEY (kompleks_id, oczyszczalnia_id)
);
CREATE TABLE IF NOT EXISTS dzialki (
    id INTEGER PRIMARY KEY,
    kompleks_id INTEGER NOT NULL REFERENCES kompleksy(id) ON DELETE CASCADE,
    numer TEXT NOT NULL,
    UNIQUE (kompleks_id, numer)
);
CREATE TABLE IF NOT EXISTS badania_gleby (
    id INTEGER PRIMARY KEY,
    kompleks_id INTEGER NOT NULL REFERENCES kompleksy(id) ON DELETE CASCADE,
    nr_sprawozdania TEXT NOT NULL UNIQUE,
    laboratorium TEXT,
    data_pobrania TEXT NOT NULL,
    ph REAL,
    p2o5 REAL, p2o5_lt INTEGER DEFAULT 0,
    cd REAL, cd_lt INTEGER DEFAULT 0,
    cr REAL, cr_lt INTEGER DEFAULT 0,
    cu REAL, cu_lt INTEGER DEFAULT 0,
    hg REAL, hg_lt INTEGER DEFAULT 0,
    ni REAL, ni_lt INTEGER DEFAULT 0,
    pb REAL, pb_lt INTEGER DEFAULT 0,
    zn REAL, zn_lt INTEGER DEFAULT 0,
    ocena_laboratorium TEXT,
    plik TEXT
);
CREATE TABLE IF NOT EXISTS badania_osadu (
    id INTEGER PRIMARY KEY,
    oczyszczalnia_id INTEGER NOT NULL REFERENCES oczyszczalnie(id),
    nr_sprawozdania TEXT NOT NULL UNIQUE,
    laboratorium TEXT,
    data_pobrania TEXT NOT NULL,
    sucha_masa_proc REAL NOT NULL CHECK (sucha_masa_proc > 0 AND sucha_masa_proc <= 100),
    plik TEXT
);
CREATE TABLE IF NOT EXISTS dostawy (
    id INTEGER PRIMARY KEY,
    kompleks_id INTEGER NOT NULL REFERENCES kompleksy(id) ON DELETE CASCADE,
    data TEXT NOT NULL,
    masa_mg REAL NOT NULL CHECK (masa_mg > 0),
    sucha_masa_proc REAL NOT NULL CHECK (sucha_masa_proc > 0 AND sucha_masa_proc <= 100),
    oczyszczalnia_id INTEGER REFERENCES oczyszczalnie(id),
    badanie_osadu_id INTEGER REFERENCES badania_osadu(id),
    kpo_id TEXT UNIQUE,
    karta_nr TEXT,
    uwagi TEXT
);
"""


def polacz(sciezka=None):
    sciezka = sciezka or SCIEZKA
    os.makedirs(os.path.dirname(sciezka), exist_ok=True)
    conn = sqlite3.connect(sciezka)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMAT)
    return conn


def kopia_zapasowa(sciezka=None, zostaw=30):
    """Kopia pliku bazy do dane/kopie/ (najwyzej `zostaw` ostatnich)."""
    sciezka = sciezka or SCIEZKA
    if not os.path.exists(sciezka):
        return None
    katalog = os.path.join(os.path.dirname(sciezka), "kopie")
    os.makedirs(katalog, exist_ok=True)
    cel = os.path.join(katalog, f"biuro-{datetime.now():%Y-%m-%d_%H%M%S}.db")
    src = sqlite3.connect(sciezka)
    dst = sqlite3.connect(cel)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    kopie = sorted(f for f in os.listdir(katalog) if f.startswith("biuro-") and f.endswith(".db"))
    for stara in kopie[:-zostaw]:
        os.remove(os.path.join(katalog, stara))
    return cel


# ---------- zapis ----------

def oczyszczalnia_id(conn, nazwa):
    nazwa = (nazwa or "").strip()
    if not nazwa:
        return None
    wiersz = conn.execute("SELECT id FROM oczyszczalnie WHERE nazwa = ?", (nazwa,)).fetchone()
    if wiersz:
        return wiersz["id"]
    return conn.execute("INSERT INTO oczyszczalnie (nazwa, nazwa_bdo) VALUES (?, ?)", (nazwa, nazwa)).lastrowid


def dodaj_oczyszczalnie(conn, nazwa, nazwa_bdo=None, uwagi=None):
    nazwa = nazwa.strip()
    istnieje = conn.execute("SELECT id FROM oczyszczalnie WHERE nazwa = ?", (nazwa,)).fetchone()
    if istnieje:
        conn.execute("UPDATE oczyszczalnie SET nazwa_bdo = COALESCE(?, nazwa_bdo), uwagi = COALESCE(?, uwagi) "
                     "WHERE id = ?", (nazwa_bdo, uwagi, istnieje["id"]))
        return istnieje["id"]
    return conn.execute("INSERT INTO oczyszczalnie (nazwa, nazwa_bdo, uwagi) VALUES (?, ?, ?)",
                        (nazwa, nazwa_bdo, uwagi)).lastrowid


def ustaw_przypisania(conn, kompleks_id, oczyszczalnie_ids):
    """Zastepuje liste oczyszczalni przypisanych do kompleksu."""
    conn.execute("DELETE FROM kompleksy_oczyszczalnie WHERE kompleks_id = ?", (kompleks_id,))
    for oid in set(int(o) for o in oczyszczalnie_ids):
        conn.execute("INSERT INTO kompleksy_oczyszczalnie (kompleks_id, oczyszczalnia_id) VALUES (?, ?)",
                     (kompleks_id, oid))


def przypisane_oczyszczalnie(conn, kompleks_id):
    return conn.execute(
        "SELECT o.* FROM oczyszczalnie o JOIN kompleksy_oczyszczalnie ko ON ko.oczyszczalnia_id = o.id "
        "WHERE ko.kompleks_id = ? ORDER BY o.nazwa", (kompleks_id,)).fetchall()


def wszystkie_oczyszczalnie(conn):
    return conn.execute("SELECT * FROM oczyszczalnie ORDER BY nazwa").fetchall()


def wlasciciel_id(conn, nazwa):
    nazwa = (nazwa or "").strip()
    if not nazwa:
        return None
    wiersz = conn.execute("SELECT id FROM wlasciciele WHERE nazwa = ?", (nazwa,)).fetchone()
    if wiersz:
        return wiersz["id"]
    return conn.execute("INSERT INTO wlasciciele (nazwa) VALUES (?)", (nazwa,)).lastrowid


def dodaj_kompleks(conn, nazwa, powierzchnia_ha, dzialki, obreb=None, gmina=None,
                   kategoria_gruntu=None, wlasciciel=None, uwagi=None, oczyszczalnie_ids=()):
    kid = conn.execute(
        "INSERT INTO kompleksy (nazwa, obreb, gmina, powierzchnia_ha, kategoria_gruntu, wlasciciel_id, uwagi) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (nazwa.strip(), obreb, gmina, float(powierzchnia_ha), kategoria_gruntu,
         wlasciciel_id(conn, wlasciciel), uwagi)).lastrowid
    for numer in dzialki:
        numer = numer.strip()
        if numer:
            conn.execute("INSERT OR IGNORE INTO dzialki (kompleks_id, numer) VALUES (?, ?)", (kid, numer))
    if oczyszczalnie_ids:
        ustaw_przypisania(conn, kid, oczyszczalnie_ids)
    return kid


def dodaj_badanie_gleby(conn, kompleks_id, nr_sprawozdania, data_pobrania, wyniki,
                        laboratorium=None, ocena_laboratorium=None, plik=None):
    """`wyniki`: {"ph": 5.9, "p2o5": (5.3, False), "cd": (0.01, True), ...}
    dla metali i P2O5 krotka (wartosc, czy_ponizej_granicy_oznaczalnosci)."""
    kolumny = ["kompleks_id", "nr_sprawozdania", "laboratorium", "data_pobrania", "ph",
               "ocena_laboratorium", "plik"]
    wartosci = [kompleks_id, nr_sprawozdania, laboratorium, data_pobrania, wyniki.get("ph"),
                ocena_laboratorium, plik]
    for pole in ["p2o5"] + METALE:
        if wyniki.get(pole) is not None:
            v, lt = wyniki[pole]
            kolumny += [pole, pole + "_lt"]
            wartosci += [float(v), 1 if lt else 0]
    sql = f"INSERT INTO badania_gleby ({', '.join(kolumny)}) VALUES ({', '.join('?' * len(kolumny))})"
    return conn.execute(sql, wartosci).lastrowid


def dodaj_dostawe(conn, kompleks_id, data, masa_mg, sucha_masa_proc, oczyszczalnia=None,
                  kpo_id=None, karta_nr=None, uwagi=None, badanie_osadu_id=None):
    return conn.execute(
        "INSERT INTO dostawy (kompleks_id, data, masa_mg, sucha_masa_proc, oczyszczalnia_id, "
        "badanie_osadu_id, kpo_id, karta_nr, uwagi) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (kompleks_id, data, float(masa_mg), float(sucha_masa_proc), oczyszczalnia_id(conn, oczyszczalnia),
         badanie_osadu_id, kpo_id, karta_nr, uwagi)).lastrowid


# ---------- obliczenia (zawsze w Pythonie) ----------

def _data(tekst):
    return datetime.strptime(tekst[:10], "%Y-%m-%d").date()


def ocena_gleby(badanie, kategoria):
    """Lista uwag do badania gleby: przekroczenia i wartosci blisko progu."""
    if badanie is None:
        return ["Brak badania gleby."]
    progi = PROGI_GLEBY.get((kategoria or "").strip().lower())
    if not progi:
        return [f"Brak progów w aplikacji dla kategorii „{kategoria or 'nieznana'}” – sprawdź ocenę w sprawozdaniu."]
    uwagi = []
    ph = badanie["ph"]
    if ph is not None:
        if ph <= progi["ph_min"]:
            uwagi.append(f"pH {pl(ph)} nie przekracza progu {pl(progi['ph_min'])} – osadu nie stosować.")
        elif ph - NIEPEWNOSC_PH <= progi["ph_min"]:
            uwagi.append(f"pH {pl(ph)} blisko progu {pl(progi['ph_min'])} (niepewność ±{pl(NIEPEWNOSC_PH)}).")
    for m in METALE:
        v = badanie[m]
        if v is None:
            uwagi.append(f"Brak wyniku: {NAZWY_METALI[m]}.")
        elif not badanie[m + "_lt"] and v > progi[m]:
            uwagi.append(f"{NAZWY_METALI[m]} {pl(v)} mg/kg ponad limit {pl(progi[m])}.")
    return uwagi


def pl(x):
    """Liczba po polsku: 5.9 -> '5,9'."""
    return f"{x:g}".replace(".", ",")


def stan_kompleksu(conn, kompleks_id, dzis=None):
    """Wykorzystanie limitu i ocena gleby dla kompleksu."""
    dzis = dzis or date.today()
    k = conn.execute("SELECT * FROM kompleksy WHERE id = ?", (kompleks_id,)).fetchone()
    if k is None:
        return None
    od = dzis - timedelta(days=OKRES_DNI)
    dostawy = conn.execute(
        "SELECT d.*, o.nazwa AS oczyszczalnia FROM dostawy d "
        "LEFT JOIN oczyszczalnie o ON o.id = d.oczyszczalnia_id "
        "WHERE d.kompleks_id = ? ORDER BY d.data DESC, d.id DESC", (kompleks_id,)).fetchall()
    w_okresie = [d for d in dostawy if _data(d["data"]) > od]
    suma_sm = sum(d["masa_mg"] * d["sucha_masa_proc"] / 100 for d in w_okresie)
    suma_mokra = sum(d["masa_mg"] for d in w_okresie)
    pow_ha = k["powierzchnia_ha"]
    limit_sm = LIMIT_SM_HA * pow_ha
    badanie = conn.execute("SELECT * FROM badania_gleby WHERE kompleks_id = ? ORDER BY data_pobrania DESC LIMIT 1",
                           (kompleks_id,)).fetchone()
    dzialki = [r["numer"] for r in conn.execute(
        "SELECT numer FROM dzialki WHERE kompleks_id = ? ORDER BY id", (kompleks_id,))]
    return {
        "kompleks": k,
        "oczyszczalnie": przypisane_oczyszczalnie(conn, kompleks_id),
        "dzialki": dzialki,
        "dostawy": dostawy,
        "dostaw_w_okresie": len(w_okresie),
        "okres_od": od,
        "suma_sm_mg": suma_sm,
        "suma_mokra_mg": suma_mokra,
        "dawka_sm_ha": suma_sm / pow_ha,
        "limit_sm_mg": limit_sm,
        "pozostalo_sm_mg": max(limit_sm - suma_sm, 0.0),
        "pozostalo_sm_ha": max(LIMIT_SM_HA - suma_sm / pow_ha, 0.0),
        "procent": min(suma_sm / limit_sm * 100, 999) if limit_sm else 0,
        "przekroczony": suma_sm > limit_sm + 1e-9,
        "badanie": badanie,
        "uwagi_gleby": ocena_gleby(badanie, k["kategoria_gruntu"]),
    }


def ile_mokrej_masy(pozostalo_sm_mg, sucha_masa_proc):
    """Ile Mg osadu (masy mokrej) zmiesci sie jeszcze przy danej suchej masie."""
    if not sucha_masa_proc:
        return None
    return pozostalo_sm_mg / (sucha_masa_proc / 100)


def lista_kompleksow(conn, dzis=None, oczyszczalnia_id=None):
    if oczyszczalnia_id:
        ids = [r["id"] for r in conn.execute(
            "SELECT k.id FROM kompleksy k JOIN kompleksy_oczyszczalnie ko ON ko.kompleks_id = k.id "
            "WHERE ko.oczyszczalnia_id = ? ORDER BY k.obreb, k.nazwa", (oczyszczalnia_id,))]
    else:
        ids = [r["id"] for r in conn.execute("SELECT id FROM kompleksy ORDER BY obreb, nazwa")]
    return [stan_kompleksu(conn, i, dzis) for i in ids]


def zestawienie_wg_oczyszczalni(conn, dzis=None):
    """Grupy: kazda oczyszczalnia z przypisanymi kompleksami i suma wolnego limitu.
    Kompleks wspolny dla kilku oczyszczalni pojawia sie w kazdej z nich (to ten sam limit)."""
    grupy = []
    for o in wszystkie_oczyszczalnie(conn):
        lista = lista_kompleksow(conn, dzis, oczyszczalnia_id=o["id"])
        wspoldzielone = {r["kompleks_id"] for r in conn.execute(
            "SELECT kompleks_id FROM kompleksy_oczyszczalnie GROUP BY kompleks_id HAVING COUNT(*) > 1")}
        inne = {}
        for s in lista:
            if s["kompleks"]["id"] in wspoldzielone:
                inne[s["kompleks"]["id"]] = [x["nazwa"] for x in s["oczyszczalnie"] if x["id"] != o["id"]]
        grupy.append({
            "oczyszczalnia": o,
            "kompleksy": lista,
            "wspolne_z": inne,
            "ha": sum(s["kompleks"]["powierzchnia_ha"] for s in lista),
            "wolne_sm_mg": sum(s["pozostalo_sm_mg"] for s in lista),
        })
    grupy.sort(key=lambda g: (len(g["kompleksy"]) == 0, g["oczyszczalnia"]["nazwa"]))
    bez = [s for s in lista_kompleksow(conn, dzis) if not s["oczyszczalnie"]]
    if bez:
        grupy.append({"oczyszczalnia": None, "kompleksy": bez, "wspolne_z": {},
                      "ha": sum(s["kompleks"]["powierzchnia_ha"] for s in bez),
                      "wolne_sm_mg": sum(s["pozostalo_sm_mg"] for s in bez)})
    return grupy
