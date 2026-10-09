from flask import Flask, render_template, request, redirect, url_for, Response, abort, session, flash
import auth
import hmac
import os
import re
import secrets
from datetime import datetime

app = Flask(__name__)
# Klucz do podpisywania sesji (komunikaty po potwierdzeniu, ochrona CSRF).
# Opcjonalnie zmienna SECRET_KEY; bez niej losowy przy kazdym starcie.
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_bytes(32)

# --- Logowanie do aplikacji (HTTP Basic) ---
# Login i haslo ustawiane w zmiennych srodowiskowych APP_USER i APP_PASSWORD
# (na Renderze: Environment -> Environment Variables). Bez nich aplikacja
# jest zablokowana dla wszystkich, zeby nigdy nie dzialala bez hasla.
APP_USER = os.environ.get('APP_USER')
APP_PASSWORD = os.environ.get('APP_PASSWORD')

# Identyfikator karty KPO: tylko litery, cyfry i myslniki (format GUID)
KPO_ID_RE = re.compile(r'^[A-Za-z0-9-]{1,64}$')


@app.before_request
def wymagaj_logowania():
    if not APP_USER or not APP_PASSWORD:
        return Response(
            'Aplikacja zablokowana: brak ustawionych APP_USER i APP_PASSWORD.',
            503, {'Content-Type': 'text/plain; charset=utf-8'})
    dane = request.authorization
    ok = (
        dane is not None
        and hmac.compare_digest((dane.username or '').encode(), APP_USER.encode())
        and hmac.compare_digest((dane.password or '').encode(), APP_PASSWORD.encode())
    )
    if not ok:
        return Response(
            'Wymagane logowanie.', 401,
            {'WWW-Authenticate': 'Basic realm="BDO Monitor", charset="UTF-8"',
             'Content-Type': 'text/plain; charset=utf-8'})

def csrf_token():
    """Jednorazowo losowany token sesji, wstawiany do formularzy."""
    if 'csrf' not in session:
        session['csrf'] = secrets.token_urlsafe(32)
    return session['csrf']


app.jinja_env.globals['csrf_token'] = csrf_token

DATA_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


@app.template_filter('data_pl')
def data_pl(wartosc):
    """'2026-10-08T07:30:00' -> '8.10.2026, 07:30'; '2026-10-08' -> '8.10.2026'."""
    if not wartosc:
        return '–'
    tekst = str(wartosc).replace('Z', '')
    for wzor, wynik in (('%Y-%m-%dT%H:%M:%S.%f', 'czas'), ('%Y-%m-%dT%H:%M:%S', 'czas'),
                        ('%Y-%m-%dT%H:%M', 'czas'), ('%Y-%m-%d', 'data')):
        try:
            d = datetime.strptime(tekst[:26], wzor)
        except ValueError:
            continue
        dzien = f"{d.day}.{d.month:02d}.{d.year}"
        return f"{dzien}, {d:%H:%M}" if wynik == 'czas' else dzien
    return str(wartosc)


@app.template_filter('mg')
def mg(wartosc):
    """Masa po polsku: 1234.56 -> '1 234,56 Mg' (do 4 miejsc, bez zbednych zer)."""
    try:
        liczba = float(wartosc)
    except (TypeError, ValueError):
        return '–'
    tekst = f"{liczba:,.4f}".rstrip('0').rstrip('.')
    return tekst.replace(',', '\u202f').replace('.', ',') + ' Mg'


@app.template_filter('karty')
def karty(n):
    """Polska odmiana: 1 karta, 2-4 karty, 5+ kart (12-14 kart)."""
    if n == 1:
        return 'karta'
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return 'karty'
    return 'kart'


@app.route('/')
def index():
    """Strona główna z listą kart do potwierdzenia"""
    token = auth.get_token()
    if token:
        result = auth.get_kpo_list(token)
        if result is None:
            return render_template('index.html', kpos=[],
                                   blad='BDO nie zwróciło listy kart. Spróbuj ponownie za chwilę.')
        kpos = []
        if isinstance(result, dict):
            all_kpos = result.get('Items') or result.get('items') or []
            # Filtruj tylko karty do potwierdzenia
            kpos = [k for k in all_kpos if k.get('cardStatusCodeName') == 'CONFIRMATION_GENERATED']
        return render_template('index.html', kpos=kpos)
    return render_template('index.html', kpos=[],
                           blad='Nie udało się zalogować do BDO. Sprawdź klucze CLIENT_ID, CLIENT_SECRET i EUP_ID na Renderze.')

@app.route('/stats', methods=['GET', 'POST'])
def stats_page():
    """Strona statystyk i sumowania ton"""
    token = auth.get_token()
    
    now = datetime.now()
    date_from = request.form.get('date_from', '')
    date_to = request.form.get('date_to', '')
    if not DATA_RE.match(date_from):
        date_from = now.strftime('%Y-%m-01')
    if not DATA_RE.match(date_to):
        date_to = now.strftime('%Y-%m-%d')

    if token:
        if date_from > date_to:
            date_from, date_to = date_to, date_from
        result = auth.get_kpo_by_date(token, date_from, date_to)
        if result is None:
            return render_template('stats.html', stats=[], date_from=date_from, date_to=date_to,
                                   blad='BDO nie zwróciło listy kart. Spróbuj ponownie za chwilę.')
        kpo_items = result.get("items") or []
        
        podsumowanie = {}
        if kpo_items:
            podsumowanie = auth.get_detailed_stats(kpo_items)

        # od najwiekszej masy
        wiersze = sorted(podsumowanie.items(), key=lambda x: x[1]['total_mass'], reverse=True)
        return render_template(
            'stats.html',
            stats=wiersze,
            suma_kursow=sum(d['count'] for _, d in wiersze),
            suma_masy=sum(d['total_mass'] for _, d in wiersze),
            bez_daty=result.get("bez_daty", 0),
            bez_szczegolow=result.get("bez_szczegolow", 0),
            date_from=date_from,
            date_to=date_to
        )

    return render_template('stats.html', stats=[], date_from=date_from, date_to=date_to,
                           blad='Nie udało się połączyć z BDO. Spróbuj ponownie za chwilę.')

@app.route('/diagnostyka')
def diagnostyka_page():
    """Tylko odczyt: liczby pokazujace, co BDO zwraca dla statystyk (bez nazw firm)."""
    now = datetime.now()
    date_from = request.args.get('od', '')
    date_to = request.args.get('do', '')
    if not DATA_RE.match(date_from):
        date_from = now.strftime('%Y-%m-01')
    if not DATA_RE.match(date_to):
        date_to = now.strftime('%Y-%m-%d')
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    token = auth.get_token()
    if not token:
        return render_template('diagnostyka.html', d=None, date_from=date_from, date_to=date_to,
                               blad='Nie udało się zalogować do BDO.')
    return render_template('diagnostyka.html', d=auth.diagnostyka(token, date_from, date_to),
                           date_from=date_from, date_to=date_to)


def _sprawdz_csrf():
    przeslany = request.form.get('csrf_token', '')
    oczekiwany = session.get('csrf', '')
    return bool(oczekiwany) and hmac.compare_digest(przeslany.encode(), oczekiwany.encode())


@app.route('/reject/<kpo_id>', methods=['POST'])
def reject_kpo_route(kpo_id):
    """Odrzucenie karty z powodem - tylko swiadome klikniecie w formularzu."""
    if not KPO_ID_RE.match(kpo_id):
        abort(400)
    if not _sprawdz_csrf():
        flash('Odśwież stronę i spróbuj ponownie (wygasła sesja). Karta NIE została odrzucona.', 'error')
        return redirect(url_for('index'))
    powod = ' '.join(request.form.get('powod', '').split())
    if len(powod) < 3:
        flash('Podaj powód odrzucenia. Karta NIE została odrzucona.', 'error')
        return redirect(url_for('index'))
    powod = powod[:500]
    token = auth.get_token()
    if not token:
        flash('Błąd autoryzacji BDO. Karta NIE została odrzucona.', 'error')
        return redirect(url_for('index'))
    wynik = auth.reject_kpo(token, kpo_id, powod) or {"ok": False, "komunikat": "Nieznany błąd. Karta NIE została odrzucona."}
    print("Wynik odrzucenia:", kpo_id, wynik)
    flash(wynik["komunikat"], 'ok' if wynik["ok"] else 'error')
    return redirect(url_for('index'))


@app.route('/confirm/<kpo_id>', methods=['POST'])
def confirm_kpo_route(kpo_id):
    """Potwierdzenie pojedynczej karty - tylko swiadome klikniecie w formularzu."""
    if not KPO_ID_RE.match(kpo_id):
        abort(400)
    if not _sprawdz_csrf():
        flash('Odśwież stronę i spróbuj ponownie (wygasła sesja). Karta NIE została potwierdzona.', 'error')
        return redirect(url_for('index'))
    token = auth.get_token()
    if not token:
        flash('Błąd autoryzacji BDO. Karta NIE została potwierdzona.', 'error')
        return redirect(url_for('index'))
    wynik = auth.confirm_kpo(token, kpo_id) or {"ok": False, "komunikat": "Nieznany błąd. Karta NIE została potwierdzona."}
    print("Wynik potwierdzenia:", kpo_id, wynik)
    flash(wynik["komunikat"], 'ok' if wynik["ok"] else 'error')
    return redirect(url_for('index'))

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
