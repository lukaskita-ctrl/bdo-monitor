# auth.py - moduł autoryzacji i logiki BDO
import subprocess
import json
import ustawienia as config

# --- FUNKCJE POMOCNICZE (KOMUNIKACJA) ---

def _curl_post(url, payload):
    result = subprocess.run([
        'curl', '-s', '-X', 'POST', url,
        '-H', 'accept: application/json',
        '-H', 'Content-Type: application/json',
        '-d', json.dumps(payload)
    ], capture_output=True, encoding='utf-8', errors='ignore')
    return json.loads(result.stdout) if result.stdout else None

def _curl_post_auth(url, payload, token):
    result = subprocess.run([
        'curl', '-s', '-X', 'POST', url,
        '-H', 'accept: application/json',
        '-H', f'Authorization: Bearer {token}',
        '-H', 'Content-Type: application/json',
        '-d', json.dumps(payload)
    ], capture_output=True, encoding='utf-8', errors='ignore')
    return json.loads(result.stdout) if result.stdout else None

def _curl_get_auth(url, token):
    result = subprocess.run([
        'curl', '-s', '-g', '-X', 'GET', url,
        '-H', 'accept: application/json',
        '-H', f'Authorization: Bearer {token}'
    ], capture_output=True, encoding='utf-8', errors='ignore')
    if result.stdout:
        try:
            return json.loads(result.stdout)
        except:
            return None
    return None

def _curl_put_auth(url, payload, token):
    result = subprocess.run([
        'curl', '-s', '-X', 'PUT', url,
        '-H', 'accept: application/json',
        '-H', f'Authorization: Bearer {token}',
        '-H', 'Content-Type: application/json',
        '-d', json.dumps(payload)
    ], capture_output=True, encoding='utf-8', errors='ignore')
    return json.loads(result.stdout) if result.stdout else None

def _curl_put_auth_status(url, payload, token):
    """PUT, ktory zwraca (kod_HTTP, tresc_odpowiedzi) - potrzebne, bo BDO
    przy udanym potwierdzeniu odsyla zwykle pusta odpowiedz."""
    result = subprocess.run([
        'curl', '-s', '-X', 'PUT', url,
        '--max-time', '60',
        '-w', '\n%{http_code}',
        '-H', 'accept: application/json',
        '-H', f'Authorization: Bearer {token}',
        '-H', 'Content-Type: application/json',
        '-d', json.dumps(payload)
    ], capture_output=True, encoding='utf-8', errors='ignore')
    tekst, _, kod = (result.stdout or '').rpartition('\n')
    try:
        return int(kod), tekst
    except ValueError:
        return 0, result.stdout or ''

# --- LOGOWANIE ---

def get_token():
    url = f"{config.API_URL}/WasteRegister/v1/Auth/generateEupAccessToken"
    payload = {"ClientId": config.CLIENT_ID, "ClientSecret": config.CLIENT_SECRET, "EupId": config.EUP_ID}
    result = _curl_post(url, payload)
    if result and "AccessToken" in result:
        return result["AccessToken"]
    return None

# --- OPERACJE NA KPO ---

def get_kpo_list(token, year=2026):
    """Pobiera listę KPO gdzie jesteś przejmującym"""
    url = f"{config.API_URL}/WasteRegister/WasteTransferCard/v1/Kpo/receiver/search"
    payload = {
        "PaginationParameters": {
            "Order": {"IsAscending": False},
            "Page": {"Index": 0, "Size": 50}
        },
        "Year": year,
        "SearchInCarriers": True,
        "SearchInSenders": True,
        "TransportDateRange": True,
        "ReceiveConfirmationDateRange": True
    }
    return _curl_post_auth(url, payload, token)

def confirm_kpo(token, kpo_id, remarks=""):
    """Potwierdza przyjęcie KPO.
    Zwraca slownik {"ok": bool, "komunikat": str} z informacja dla uzytkownika."""
    # Krok 1: Pobierz szczegóły karty żeby mieć wasteMass
    details_url = f"{config.API_URL}/WasteRegister/WasteTransferCard/v1/Kpo/confirmationgenerated/card?KpoId={kpo_id}&CompanyType=2"
    details = _curl_get_auth(details_url, token)
    
    if not details or not isinstance(details, dict):
        print(f"Nie można pobrać szczegółów karty: {details}")
        return {"ok": False, "komunikat": "Nie udało się pobrać szczegółów karty z BDO. Karta NIE została potwierdzona."}
    
    waste_mass = details.get('wasteMass')
    if not waste_mass:
        print(f"Brak wasteMass w szczegółach karty")
        return {"ok": False, "komunikat": "Karta nie ma podanej masy odpadu. Nie potwierdzono - sprawdź ją w BDO."}
    
    # Krok 2: Potwierdź kartę z masą
    url = f"{config.API_URL}/WasteRegister/WasteTransferCard/v1/Kpo/assign/receiveconfirmation"
    payload = {
        "KpoId": kpo_id,
        "CorrectedWasteMass": waste_mass,
        "Remarks": remarks
    }
    
    kod, tekst = _curl_put_auth_status(url, payload, token)
    if 200 <= kod < 300:
        return {"ok": True, "komunikat": "Karta potwierdzona w BDO (masa: " + str(waste_mass).replace(".", ",") + " Mg)."}
    print(f"BDO odrzuciło potwierdzenie: kod {kod}, odpowiedź: {tekst[:500]}")
    szczegoly = ""
    try:
        dane = json.loads(tekst)
        if isinstance(dane, dict):
            szczegoly = dane.get("message") or dane.get("Message") or dane.get("title") or ""
    except (ValueError, TypeError):
        pass
    komunikat = f"BDO odrzuciło potwierdzenie (kod {kod or 'brak połączenia'})."
    if szczegoly:
        komunikat += " " + str(szczegoly)[:200].rstrip(" .") + "."
    return {"ok": False, "komunikat": komunikat + " Karta NIE została potwierdzona."}

def reject_kpo(token, kpo_id, remarks):
    """Odrzuca KPO (odmowa przyjecia) z podanym powodem.
    UWAGA: adres endpointu przyjety wg znanych integracji API BDO - przy
    pierwszym uzyciu sprawdzic w BDO, czy karta ma status "Odrzucona".
    Zwraca slownik {"ok": bool, "komunikat": str}."""
    url = f"{config.API_URL}/WasteRegister/WasteTransferCard/v1/Kpo/reject"
    payload = {"KpoId": kpo_id, "Remarks": remarks}
    kod, tekst = _curl_put_auth_status(url, payload, token)
    if 200 <= kod < 300:
        return {"ok": True, "komunikat": "Karta odrzucona w BDO. Powód: " + remarks}
    print(f"BDO odrzuciło żądanie odrzucenia: kod {kod}, odpowiedź: {tekst[:500]}")
    szczegoly = ""
    try:
        dane = json.loads(tekst)
        if isinstance(dane, dict):
            szczegoly = dane.get("message") or dane.get("Message") or dane.get("title") or ""
    except (ValueError, TypeError):
        pass
    komunikat = f"Nie udało się odrzucić karty (kod {kod or 'brak połączenia'})."
    if szczegoly:
        komunikat += " " + str(szczegoly)[:200].rstrip(" .") + "."
    return {"ok": False, "komunikat": komunikat + " Karta NIE została odrzucona."}

def get_kpo_by_date(token, date_from, date_to, year=2026):
    """Pobiera karty potwierdzone z danego zakresu dat wraz z masami"""
    
    url = f"{config.API_URL}/WasteRegister/WasteTransferCard/v1/Kpo/receiver/search"
    payload = {
        "PaginationParameters": {"Order": {"IsAscending": False}, "Page": {"Index": 0, "Size": 200}},
        "Year": year,
        "SearchInCarriers": True,
        "SearchInSenders": True,
        "TransportDateRange": True,
        "ReceiveConfirmationDateRange": True
    }
    
    result = _curl_post_auth(url, payload, token)
    
    if not result or "items" not in result:
        return {"items": []}
    
    karty_ze_szczegolami = []
    
    for kpo in result["items"]:
        status = kpo.get("cardStatusCodeName")
        
        if status not in ["RECEIVE_CONFIRMATION", "TRANSPORT_CONFIRMATION"]:
            continue
        
        conf_time = kpo.get("receiveConfirmationTime", "")
        if conf_time:
            conf_date = conf_time[:10]
            if date_from <= conf_date <= date_to:
                kpo_id = kpo.get("kpoId")
                
                if status == "RECEIVE_CONFIRMATION":
                    details_url = f"{config.API_URL}/WasteRegister/WasteTransferCard/v1/Kpo/receiveconfirmed/card?KpoId={kpo_id}&CompanyType=2"
                else:
                    details_url = f"{config.API_URL}/WasteRegister/WasteTransferCard/v1/Kpo/transportconfirmation/card?KpoId={kpo_id}&CompanyType=2"
                
                details = _curl_get_auth(details_url, token)
                
                if details and isinstance(details, dict):
                    karty_ze_szczegolami.append({
                        "cardNumber": details.get("cardNumber"),
                        "senderName": kpo.get("senderName"),
                        "wasteMass": details.get("wasteMass", 0),
                        "receiveConfirmationTime": details.get("receiveConfirmationTime"),
                        "wasteCode": kpo.get("wasteCode"),
                        "status": status
                    })
    
    return {"items": karty_ze_szczegolami}

def get_detailed_stats(kpo_list):
    """Sumuje masy dla poszczególnych wytwórców"""
    stats = {}
    for kpo in kpo_list:
        sender = kpo.get('senderName', 'Nieznany Wytwórca')
        try:
            mass = float(kpo.get('wasteMass', 0))
        except:
            mass = 0.0
        
        if sender not in stats:
            stats[sender] = {'total_mass': 0.0, 'count': 0}
        
        stats[sender]['total_mass'] += mass
        stats[sender]['count'] += 1
    return stats

