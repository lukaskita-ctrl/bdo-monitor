"""Biuro - lokalna aplikacja na komputerze Lukasza.

Uruchomienie (PowerShell, w katalogu projektu):
    python biuro\\app.py
i otworz w przegladarce: http://localhost:5001

Dziala tylko na tym komputerze (adres 127.0.0.1). Nie laczy sie z BDO
(to przyjdzie w etapie B2, wylacznie do odczytu).
"""
import hmac
import os
import re
import secrets
import sqlite3
import sys
from datetime import date, datetime

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import baza  # noqa: E402

KATALOG_PROJEKTU = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__, static_folder=os.path.join(KATALOG_PROJEKTU, "static"))
app.secret_key = os.environ.get("BIURO_SECRET_KEY") or secrets.token_bytes(32)

DATA_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ---------- baza na czas jednego zapytania ----------

def db():
    if "db" not in g:
        g.db = baza.polacz()
    return g.db


@app.teardown_appcontext
def zamknij(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


# ---------- ochrona formularzy (CSRF) ----------

def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def sprawdz_csrf():
    if request.method == "POST":
        przeslany = request.form.get("csrf_token", "")
        oczekiwany = session.get("csrf", "")
        if not oczekiwany or not hmac.compare_digest(przeslany.encode(), oczekiwany.encode()):
            flash("Formularz wygasł. Odśwież stronę i spróbuj ponownie.", "error")
            return redirect(request.referrer or url_for("kompleksy"))


# ---------- formatowanie po polsku ----------

@app.template_filter("pl")
def pl(x, miejsca=2):
    if x is None:
        return "–"
    tekst = f"{float(x):,.{miejsca}f}"
    if "." in tekst:  # zbedne zera tylko po przecinku (1000 musi zostac 1000)
        tekst = tekst.rstrip("0").rstrip(".")
    return tekst.replace(",", " ").replace(".", ",")


@app.template_filter("data_pl")
def data_pl(tekst):
    if not tekst:
        return "–"
    try:
        d = tekst if isinstance(tekst, date) else datetime.strptime(str(tekst)[:10], "%Y-%m-%d").date()
    except ValueError:
        return str(tekst)
    return f"{d.day}.{d.month:02d}.{d.year}"


@app.template_filter("wynik")
def wynik(badanie, pole):
    v = badanie[pole]
    if v is None:
        return "–"
    lt = badanie[pole + "_lt"] if (pole + "_lt") in badanie.keys() else 0
    return ("<" if lt else "") + pl(v, 3)


# ---------- pomocnicze ----------

def liczba(nazwa, wymagana=True, min_=None, max_=None):
    tekst = (request.form.get(nazwa) or "").strip().replace(" ", "").replace(",", ".")
    if not tekst:
        if wymagana:
            raise ValueError(f"Uzupełnij pole „{nazwa.replace('_', ' ')}”.")
        return None
    try:
        v = float(tekst)
    except ValueError:
        raise ValueError(f"Pole „{nazwa.replace('_', ' ')}” musi być liczbą.")
    if (min_ is not None and v < min_) or (max_ is not None and v > max_):
        raise ValueError(f"Pole „{nazwa.replace('_', ' ')}” poza zakresem {min_}–{max_}.")
    return v


def wynik_lab(nazwa):
    """'<0,5' -> (0.5, True); '5,9' -> (5.9, False); '' -> None"""
    tekst = (request.form.get(nazwa) or "").strip().replace(" ", "").replace(",", ".")
    if not tekst:
        return None
    lt = tekst.startswith("<")
    try:
        return float(tekst.lstrip("<")), lt
    except ValueError:
        raise ValueError(f"Wynik „{nazwa}” musi być liczbą (dopuszczalne „<” na początku).")


def data_z_formularza(nazwa):
    tekst = (request.form.get(nazwa) or "").strip()
    if not DATA_RE.match(tekst):
        raise ValueError("Podaj poprawną datę.")
    return tekst


# ---------- strony ----------

@app.route("/")
def kompleksy():
    sm = request.args.get("sm", "").replace(",", ".")
    try:
        sm = float(sm) if sm else None
    except ValueError:
        sm = None
    return render_template("kompleksy.html", grupy=baza.zestawienie_wg_oczyszczalni(db()),
                           limit=baza.LIMIT_SM_HA, sm=sm, ile=baza.ile_mokrej_masy)


@app.route("/oczyszczalnie", methods=["GET", "POST"])
def oczyszczalnie():
    if request.method == "POST":
        nazwa = (request.form.get("nazwa") or "").strip()
        if not nazwa:
            flash("Podaj nazwę oczyszczalni.", "error")
        else:
            baza.dodaj_oczyszczalnie(db(), nazwa, (request.form.get("nazwa_bdo") or "").strip() or None,
                                     (request.form.get("uwagi") or "").strip() or None)
            db().commit()
            flash(f"Zapisano oczyszczalnię „{nazwa}”.", "ok")
        return redirect(url_for("oczyszczalnie"))
    lista = db().execute(
        "SELECT o.*, COUNT(ko.kompleks_id) AS kompleksow FROM oczyszczalnie o "
        "LEFT JOIN kompleksy_oczyszczalnie ko ON ko.oczyszczalnia_id = o.id GROUP BY o.id ORDER BY o.nazwa").fetchall()
    return render_template("oczyszczalnie.html", lista=lista)


@app.route("/kompleks/<int:kid>/oczyszczalnie", methods=["POST"])
def zmien_przypisania(kid):
    baza.ustaw_przypisania(db(), kid, request.form.getlist("oczyszczalnie"))
    db().commit()
    flash("Zapisano przypisanie do oczyszczalni.", "ok")
    return redirect(url_for("kompleks", kid=kid))


@app.route("/kompleks/<int:kid>")
def kompleks(kid):
    stan = baza.stan_kompleksu(db(), kid)
    if stan is None:
        abort(404)
    badania = db().execute("SELECT * FROM badania_gleby WHERE kompleks_id = ? ORDER BY data_pobrania DESC",
                           (kid,)).fetchall()
    przypisane = [o["nazwa"] for o in stan["oczyszczalnie"]]
    oczyszczalnie = przypisane + [o["nazwa"] for o in baza.wszystkie_oczyszczalnie(db()) if o["nazwa"] not in przypisane]
    sm = request.args.get("sm", "").replace(",", ".")
    try:
        sm = float(sm) if sm else None
    except ValueError:
        sm = None
    return render_template("kompleks.html", s=stan, badania=badania, oczyszczalnie=oczyszczalnie,
                           wszystkie=baza.wszystkie_oczyszczalnie(db()),
                           przypisane_ids={o["id"] for o in stan["oczyszczalnie"]},
                           limit=baza.LIMIT_SM_HA, metale=baza.METALE, nazwy=baza.NAZWY_METALI,
                           sm=sm, zmiesci=baza.ile_mokrej_masy(stan["pozostalo_sm_mg"], sm) if sm else None,
                           dzis=date.today().isoformat())


@app.route("/kompleks/nowy", methods=["GET", "POST"])
def nowy_kompleks():
    if request.method == "POST":
        try:
            nazwa = (request.form.get("nazwa") or "").strip()
            if not nazwa:
                raise ValueError("Podaj nazwę kompleksu.")
            dzialki = [d for d in re.split(r"[,;\s]+", request.form.get("dzialki", "")) if d]
            if not dzialki:
                raise ValueError("Podaj co najmniej jeden numer działki.")
            kid = baza.dodaj_kompleks(
                db(), nazwa, liczba("powierzchnia_ha", min_=0.01, max_=10000), dzialki,
                obreb=request.form.get("obreb") or None, gmina=request.form.get("gmina") or None,
                kategoria_gruntu=request.form.get("kategoria_gruntu") or None,
                wlasciciel=request.form.get("wlasciciel"), uwagi=request.form.get("uwagi") or None,
                oczyszczalnie_ids=request.form.getlist("oczyszczalnie"))
            db().commit()
            flash(f"Dodano kompleks „{nazwa}”.", "ok")
            return redirect(url_for("kompleks", kid=kid))
        except ValueError as e:
            flash(str(e), "error")
    return render_template("nowy_kompleks.html", f=request.form, wszystkie=baza.wszystkie_oczyszczalnie(db()),
                           wybrane=set(request.form.getlist("oczyszczalnie")))


@app.route("/kompleks/<int:kid>/dostawa", methods=["POST"])
def dodaj_dostawe(kid):
    try:
        baza.dodaj_dostawe(db(), kid, data_z_formularza("data"), liczba("masa_mg", min_=0.001, max_=100),
                           liczba("sucha_masa_proc", min_=0.1, max_=100),
                           oczyszczalnia=request.form.get("oczyszczalnia"),
                           karta_nr=request.form.get("karta_nr") or None, uwagi=request.form.get("uwagi") or None)
        db().commit()
        stan = baza.stan_kompleksu(db(), kid)
        if stan["przekroczony"]:
            flash("Dostawa zapisana, ale LIMIT KOMPLEKSU JEST PRZEKROCZONY. Sprawdź wpisy.", "error")
        else:
            flash(f"Dostawa zapisana. Zostało {pl(stan['pozostalo_sm_ha'])} Mg s.m./ha.", "ok")
    except ValueError as e:
        flash(str(e), "error")
    except sqlite3.IntegrityError:
        flash("Nie zapisano – sprawdź wartości (masa i sucha masa muszą być dodatnie).", "error")
    return redirect(url_for("kompleks", kid=kid))


@app.route("/kompleks/<int:kid>/dostawa/<int:did>/usun", methods=["POST"])
def usun_dostawe(kid, did):
    db().execute("DELETE FROM dostawy WHERE id = ? AND kompleks_id = ?", (did, kid))
    db().commit()
    flash("Dostawa usunięta.", "ok")
    return redirect(url_for("kompleks", kid=kid))


@app.route("/kompleks/<int:kid>/badanie", methods=["POST"])
def dodaj_badanie(kid):
    try:
        nr = (request.form.get("nr_sprawozdania") or "").strip()
        if not nr:
            raise ValueError("Podaj numer sprawozdania.")
        wyniki = {"ph": liczba("ph", wymagana=False, min_=2, max_=12), "p2o5": wynik_lab("p2o5")}
        for m in baza.METALE:
            wyniki[m] = wynik_lab(m)
        baza.dodaj_badanie_gleby(db(), kid, nr, data_z_formularza("data_pobrania"), wyniki,
                                 laboratorium=request.form.get("laboratorium") or None,
                                 ocena_laboratorium=request.form.get("ocena_laboratorium") or None)
        db().commit()
        flash(f"Dodano badanie gleby {nr}.", "ok")
    except ValueError as e:
        flash(str(e), "error")
    except sqlite3.IntegrityError:
        flash("Sprawozdanie o tym numerze jest już w bazie.", "error")
    return redirect(url_for("kompleks", kid=kid))


if __name__ == "__main__":
    kopia = baza.kopia_zapasowa()
    if kopia:
        print("Kopia zapasowa bazy:", kopia)
    print("Biuro działa: http://localhost:5001  (zatrzymanie: Ctrl+C)")
    app.run(host="127.0.0.1", port=int(os.environ.get("BIURO_PORT", 5001)), debug=False)
