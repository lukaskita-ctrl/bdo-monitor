from flask import Flask, render_template, request, redirect, url_for, Response, abort
import auth
import hmac
import os
import re
from datetime import datetime

app = Flask(__name__)

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

@app.route('/')
def index():
    """Strona główna z listą kart do potwierdzenia"""
    token = auth.get_token()
    if token:
        result = auth.get_kpo_list(token)
        kpos = []
        if result and isinstance(result, dict):
            all_kpos = result.get('Items') or result.get('items') or []
            # Filtruj tylko karty do potwierdzenia
            kpos = [k for k in all_kpos if k.get('cardStatusCodeName') == 'CONFIRMATION_GENERATED']
        return render_template('index.html', kpos=kpos)
    return "Błąd autoryzacji BDO. Sprawdź ClientID i ClientSecret."

@app.route('/stats', methods=['GET', 'POST'])
def stats_page():
    """Strona statystyk i sumowania ton"""
    token = auth.get_token()
    
    now = datetime.now()
    date_from = request.form.get('date_from', now.strftime('%Y-%m-01'))
    date_to = request.form.get('date_to', now.strftime('%Y-%m-%d'))

    if token:
        result = auth.get_kpo_by_date(token, date_from, date_to)
        
        kpo_items = []
        if result and isinstance(result, dict):
            kpo_items = result.get("items") or []
        
        podsumowanie = {}
        if kpo_items:
            podsumowanie = auth.get_detailed_stats(kpo_items)

        return render_template(
            'stats.html', 
            stats=podsumowanie, 
            date_from=date_from, 
            date_to=date_to
        )
        
    return "Nie udało się połączyć z BDO."

@app.route('/confirm/<kpo_id>')
def confirm_kpo_route(kpo_id):
    """Logika potwierdzania pojedynczej karty"""
    if not KPO_ID_RE.match(kpo_id):
        abort(400)
    token = auth.get_token()
    if token:
        result = auth.confirm_kpo(token, kpo_id)
        print("Wynik potwierdzenia:", result)
    return redirect(url_for('index'))

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
