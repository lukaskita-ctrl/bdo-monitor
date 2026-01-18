from flask import Flask, render_template, request, redirect, url_for
import auth
import config
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def index():
    """Strona główna z listą kart do potwierdzenia"""
    token = auth.get_token()
    if token:
        # Pobieramy karty "aktywne" dla Twojego miejsca działalności
        result = auth.get_kpo_list(token)
        kpos = []
        if result and isinstance(result, dict):
            kpos = result.get('Items') or result.get('items') or []
        return render_template('index.html', kpos=kpos)
    return "Błąd autoryzacji BDO. Sprawdź ClientID i ClientSecret."

@app.route('/stats', methods=['GET', 'POST'])
def stats_page():
    """Strona statystyk i sumowania ton"""
    token = auth.get_token()
    
    # Domyślny zakres dat: od początku miesiąca do dzisiaj
    now = datetime.now()
    date_from = request.form.get('date_from', now.strftime('%Y-%m-01'))
    date_to = request.form.get('date_to', now.strftime('%Y-%m-%d'))

    if token:
        # Pobieramy dane z BDO przy użyciu Twojej nowej funkcji z EUP_ID
        result = auth.get_kpo_by_date(token, date_from, date_to)
        
        # BEZPIECZNE WYCIĄGANIE KART (Zapobiega AttributeError)
        kpo_items = []
        if result and isinstance(result, dict):
            kpo_items = result.get("Items") or result.get("items") or []
        
        # Przeliczanie statystyk (sumowanie ton wg wytwórcy)
        podsumowanie = {}
        if kpo_items:
            podsumowanie = auth.get_detailed_stats(kpo_items)
            print(f"DEBUG: Przetworzono {len(kpo_items)} kart dla statystyk.")
        else:
            print("DEBUG: Lista kart z BDO jest pusta dla podanego zakresu.")

        return render_template(
            'stats.html', 
            stats=podsumowanie, 
            date_from=date_from, 
            date_to=date_to
        )
        
    return "Nie udało się połączyć z BDO."

@app.route('/confirm/<kpo_id>', methods=['POST'])
def confirm_kpo(kpo_id):
    """Logika potwierdzania pojedynczej karty"""
    token = auth.get_token()
    if token:
        # Pobieramy szczegóły, żeby znać wagę i wersję
        details = auth.get_kpo_details(token, kpo_id)
        if details:
            # Potwierdzamy kartę w BDO
            auth.confirm_kpo_planned(token, details)
    return redirect(url_for('index'))

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)