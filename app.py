from flask import Flask, render_template, request, redirect, url_for
import auth
import config
from datetime import datetime

import google.generativeai as genai

# Konfiguracja Gemini
genai.configure(api_key=config.GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

app = Flask(__name__)

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

@app.route('/confirm/<kpo_id>')
def confirm_kpo_route(kpo_id):
    """Logika potwierdzania pojedynczej karty"""
    token = auth.get_token()
    if token:
        result = auth.confirm_kpo(token, kpo_id)
        print("Wynik potwierdzenia:", result)
    return redirect(url_for('index'))

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

@app.route('/ask_ai', methods=['POST'])
def ask_ai():
    token = auth.get_token()
    data = request.json
    question = data.get('question')
    
    # Pobieramy aktualne statystyki, żeby AI miało o czym rozmawiać
    # Używamy zakresu dat przekazanego z frontendu lub domyślnego
    date_from = data.get('date_from', '2026-01-01')
    date_to = data.get('date_to', '2026-01-31')
    
    result = auth.get_kpo_by_date(token, date_from, date_to)
    
    # Tworzymy kontekst dla AI (widzi tylko podsumowanie, żeby było szybciej)
    summary = auth.get_detailed_stats(result.get('Items', []))
    
    prompt = f"""
    Jesteś asystentem firmy Zielony Obieg. Twoim właścicielem jest Łukasz.
    Oto aktualne statystyki odpadów z BDO od {date_from} do {date_to}:
    {str(summary)}
    
    Odpowiedz krótko i konkretnie na pytanie użytkownika. 
    Jeśli pytanie dotyczy ton, podaj liczby. Pytanie: {question}
    """
    
    response = model.generate_content(prompt)
    return {"answer": response.text}    
