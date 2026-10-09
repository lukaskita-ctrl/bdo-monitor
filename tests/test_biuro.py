"""Testy Biura (baza i obliczenia dawek) na tymczasowej bazie, bez BDO.
Uruchom z katalogu projektu:  python tests/test_biuro.py"""
import os, sys, tempfile, re
from datetime import date
KAT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KAT, "biuro"))
tmp = tempfile.mkdtemp()
os.environ["BIURO_DB"] = os.path.join(tmp, "test.db")
import baza

conn = baza.polacz()
kid = baza.dodaj_kompleks(conn, "Test – dz. 1–3", 4.0, ["1", "2/1", "3"], obreb="Testowo",
                          kategoria_gruntu="grunt lekki", wlasciciel="Jan Testowy")
baza.dodaj_badanie_gleby(conn, kid, "1/2026", "2026-07-18",
                         {"ph": 5.7, "p2o5": (5.3, False), "cd": (0.01, True), "cr": (5.9, False),
                          "cu": (2.9, False), "hg": (0.5, True), "ni": (2.8, False), "pb": (9.6, False),
                          "zn": (15.3, False)}, laboratorium="INTERLABO", ocena_laboratorium="spełnia")
# 4 ha * 45 = 180 Mg s.m. limitu
baza.dodaj_dostawe(conn, kid, "2026-08-01", 25.0, 20.0, oczyszczalnia="Oczyszczalnia A")   # 5 Mg s.m.
baza.dodaj_dostawe(conn, kid, "2026-08-02", 24.0, 25.0, oczyszczalnia="Oczyszczalnia A")   # 6 Mg s.m.
baza.dodaj_dostawe(conn, kid, "2022-01-10", 500.0, 20.0)                                    # 100 Mg s.m., poza 3 latami
conn.commit()

s = baza.stan_kompleksu(conn, kid, dzis=date(2026, 10, 9))
print("suma s.m. w 3 latach:", s["suma_sm_mg"], "| dawka/ha:", s["dawka_sm_ha"], "| zostalo Mg s.m.:", s["pozostalo_sm_mg"])
assert abs(s["suma_sm_mg"] - 11.0) < 1e-9
assert abs(s["dawka_sm_ha"] - 2.75) < 1e-9
assert abs(s["pozostalo_sm_mg"] - 169.0) < 1e-9
assert s["dostaw_w_okresie"] == 2 and not s["przekroczony"]
print("uwagi gleby:", s["uwagi_gleby"])
assert len(s["uwagi_gleby"]) == 1 and "blisko progu" in s["uwagi_gleby"][0]
assert abs(baza.ile_mokrej_masy(169.0, 20.0) - 845.0) < 1e-9

# przekroczenie
baza.dodaj_dostawe(conn, kid, "2026-09-01", 900.0, 20.0)   # +180 Mg s.m.
conn.commit()
s = baza.stan_kompleksu(conn, kid, dzis=date(2026, 10, 9))
assert s["przekroczony"] and s["pozostalo_sm_mg"] == 0.0
print("przekroczenie wykryte:", s["dawka_sm_ha"], "Mg s.m./ha")

# metal ponad limit i nieznana kategoria
k2 = baza.dodaj_kompleks(conn, "Ciezki", 1.0, ["9"], kategoria_gruntu="grunt ciężki")
baza.dodaj_badanie_gleby(conn, k2, "2/2026", "2026-07-18", {"ph": 6.5, "cd": (4.0, False)})
s2 = baza.stan_kompleksu(conn, k2)
assert any("Brak progów" in u for u in s2["uwagi_gleby"])
k3 = baza.dodaj_kompleks(conn, "Lekki z kadmem", 1.0, ["10"], kategoria_gruntu="grunt lekki")
baza.dodaj_badanie_gleby(conn, k3, "3/2026", "2026-07-18", {"ph": 6.5, "cd": (4.0, False), "cr": (1, False),
                         "cu": (1, False), "hg": (0.5, True), "ni": (1, False), "pb": (1, False), "zn": (1, False)})
s3 = baza.stan_kompleksu(conn, k3)
assert any("Kadm" in u and "ponad limit" in u for u in s3["uwagi_gleby"]), s3["uwagi_gleby"]

conn.commit()

# zle dane odrzucone przez baze
import sqlite3
try:
    baza.dodaj_dostawe(conn, kid, "2026-09-02", -5, 20); raise SystemExit("ujemna masa przeszla!")
except sqlite3.IntegrityError:
    pass

# przypisania do oczyszczalni: duza oczyszczalnia ma swoje kompleksy, male dziela wspolne
conn.rollback()
rasz = baza.dodaj_oczyszczalnie(conn, "Raszyn", "GMINNE PRZEDSIEBIORSTWO KOMUNALNE EKO-RASZYN")
zar = baza.dodaj_oczyszczalnie(conn, "Żarnów"); fal = baza.dodaj_oczyszczalnie(conn, "Fałków"); oro = baza.dodaj_oczyszczalnie(conn, "Orońsko")
k_rasz = baza.dodaj_kompleks(conn, "Błonie – dz. 7", 10.0, ["7"], kategoria_gruntu="grunt lekki", oczyszczalnie_ids=[rasz])
k_mal = baza.dodaj_kompleks(conn, "Wspólny – dz. 8", 2.0, ["8"], kategoria_gruntu="grunt lekki", oczyszczalnie_ids=[zar, fal, oro])
baza.dodaj_dostawe(conn, k_mal, "2026-09-10", 10.0, 20.0, oczyszczalnia="Żarnów")   # 2 Mg s.m.
baza.dodaj_dostawe(conn, k_mal, "2026-09-11", 10.0, 20.0, oczyszczalnia="Fałków")   # 2 Mg s.m.
conn.commit()
st = baza.stan_kompleksu(conn, k_mal, dzis=date(2026, 10, 9))
assert abs(st["suma_sm_mg"] - 4.0) < 1e-9, "wspolny limit liczy dostawy ze wszystkich oczyszczalni"
assert [o["nazwa"] for o in st["oczyszczalnie"]] == ["Fałków", "Orońsko", "Żarnów"]
grupy = {(g["oczyszczalnia"]["nazwa"] if g["oczyszczalnia"] else None): g for g in baza.zestawienie_wg_oczyszczalni(conn, dzis=date(2026, 10, 9))}
assert [s_["kompleks"]["nazwa"] for s_ in grupy["Raszyn"]["kompleksy"]] == ["Błonie – dz. 7"]
assert grupy["Żarnów"]["wspolne_z"][k_mal] == ["Fałków", "Orońsko"]
assert abs(grupy["Orońsko"]["wolne_sm_mg"] - (90.0 - 4.0)) < 1e-9
assert None in grupy and any(s_["kompleks"]["id"] == kid for s_ in grupy[None]["kompleksy"])
baza.ustaw_przypisania(conn, k_mal, [zar]); conn.commit()
assert [o["nazwa"] for o in baza.przypisane_oczyszczalnie(conn, k_mal)] == ["Żarnów"]
baza.ustaw_przypisania(conn, k_mal, [zar, fal, oro]); conn.commit()
print("przypisania: OK (wspólny kompleks, zestawienie, bez przypisania)")

conn.rollback(); conn.close()

# kopia zapasowa
kopia = baza.kopia_zapasowa()
assert kopia and os.path.exists(kopia)

# strony aplikacji
import app as biuro_app
c = biuro_app.app.test_client()
h = c.get("/").get_data(as_text=True)
assert "Test – dz. 1–3" in h and "przekroczony" in h
h = c.get(f"/kompleks/{kid}?sm=20").get_data(as_text=True)
assert "Dostawy osadu" in h and "blisko progu" in h
tok = re.search(r'name="csrf_token" value="([^"]+)"', h).group(1)
r = c.post(f"/kompleks/{k3}/dostawa", data={"csrf_token": tok, "data": "2026-10-01", "masa_mg": "25,1",
                                            "sucha_masa_proc": "18,5", "oczyszczalnia": "Oczyszczalnia B"},
           follow_redirects=True).get_data(as_text=True)
assert "Dostawa zapisana" in r, r[:500]
r = c.post(f"/kompleks/{k3}/dostawa", data={"csrf_token": "zly", "data": "2026-10-01", "masa_mg": "25",
                                            "sucha_masa_proc": "18"}, follow_redirects=True).get_data(as_text=True)
assert "Formularz wygasł" in r
r = c.post("/kompleks/nowy", data={"csrf_token": tok, "nazwa": "Nowy", "dzialki": "5, 6/2",
                                   "powierzchnia_ha": "2,5", "kategoria_gruntu": "grunt lekki"},
           follow_redirects=True).get_data(as_text=True)
assert "Dodano kompleks" in r
h = c.get("/").get_data(as_text=True)
assert "Raszyn" in h and "wspólny z: Fałków, Orońsko" in h and "Bez przypisanej oczyszczalni" in h
h = c.get("/?sm=20").get_data(as_text=True)
assert "Mg osadu przy 20%" in h
r = c.post("/oczyszczalnie", data={"csrf_token": tok, "nazwa": "Pionki", "nazwa_bdo": "PWKiC Pionki"}, follow_redirects=True).get_data(as_text=True)
assert "Zapisano oczyszczalnię" in r and "PWKiC Pionki" in r
r = c.post(f"/kompleks/{kid}/oczyszczalnie", data={"csrf_token": tok, "oczyszczalnie": [str(rasz)]}, follow_redirects=True).get_data(as_text=True)
assert "Zapisano przypisanie" in r
pl = biuro_app.pl
assert pl(1000, 0) == "1\u202f000" and pl(0, 0) == "0" and pl(3527.4, 0) == "3\u202f527"
assert pl(24.50) == "24,5" and pl(1000.0) == "1\u202f000" and pl(0.25, 3) == "0,25" and pl(None) == "–"
print("OK - wszystkie sprawdzenia Biura przeszly")
