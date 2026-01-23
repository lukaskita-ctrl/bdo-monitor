# auth.py - moduł autoryzacji i logiki BDO
import subprocess
import json
import config
import time

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
    """Wersja pancerna dla Windows - radzi sobie ze znakami & w adresie"""
    # Budujemy pełną komendę jako jeden tekst
    command = f'curl -s -g -X GET "{url}" -H "accept: application/json" -H "Authorization: Bearer {token}"'
    
    result = subprocess.run(command, capture_output=True, encoding='utf-8', errors='ignore', shell=True)
    
    if result.stdout:
        try:
            return json.loads(result.stdout)
        except Exception as e:
            print(f"BDO zwróciło tekst zamiast danych: {result.stdout[:100]}")
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

# --- LOGOWANIE I TOKENY ---

def get_token():
    url = f"{config.API_URL}/WasteRegister/v1/Auth/generateEupAccessToken"
    payload = {"ClientId": config.CLIENT_ID, "ClientSecret": config.CLIENT_SECRET, "EupId": config.EUP_ID}
    result = _curl_post(url, payload)
    if result and "AccessToken" in result:
        return result["AccessToken"]
    return None

# --- OPERACJE NA KPO ---

def get_kpo_details(token, kpo_id):
    """Pobiera pełne dane karty (masa, WtcId)"""
    url = f"{config.API_URL}/WasteRegister/WasteTransferCard/v1/Kpo/receiver/details/{kpo_id}"
    return _curl_get_auth(url, token)

def confirm_kpo(token, kpo_id, remarks=""):
    """Potwierdza przyjęcie KPO"""
    # Krok 1: Pobierz szczegóły karty żeby mieć wasteMass
    details_url = f"{config.API_URL}/WasteRegister/WasteTransferCard/v1/Kpo/confirmationgenerated/card?KpoId={kpo_id}&CompanyType=2"
    details = _curl_get_auth(details_url, token)
    
    if not details or not isinstance(details, dict):
        print(f"Nie można pobrać szczegółów karty: {details}")
        return None
    
    waste_mass = details.get('wasteMass')
    if not waste_mass:
        print(f"Brak wasteMass w szczegółach karty")
        return None
    
    # Krok 2: Potwierdź kartę z masą
    url = f"{config.API_URL}/WasteRegister/WasteTransferCard/v1/Kpo/assign/receiveconfirmation"
    payload = {
        "KpoId": kpo_id,
        "CorrectedWasteMass": waste_mass,
        "Remarks": remarks
    }
    
    return _curl_put_auth(url, payload, token)

def get_kpo_by_date(token, date_from, date_to, year=2026):
    """Pobiera karty potwierdzone z danego zakresu dat wraz z masami"""
    
    # Krok 1: Pobierz listę kart
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
    
    # Krok 2: Filtruj potwierdzone karty (OBA statusy!)
    karty_ze_szczegolami = []
    
    for kpo in result["items"]:
        status = kpo.get("cardStatusCodeName")
        
        # Akceptuj oba statusy
        if status not in ["RECEIVE_CONFIRMATION", "TRANSPORT_CONFIRMATION"]:
            continue
        
        # Sprawdź datę potwierdzenia
        conf_time = kpo.get("receiveConfirmationTime", "")
        if conf_time:
            conf_date = conf_time[:10]  # Wyciągnij YYYY-MM-DD
            if date_from <= conf_date <= date_to:
                # Pobierz szczegóły z masą
                kpo_id = kpo.get("kpoId")
                
                # Wybierz endpoint w zależności od statusu
                if status == "RECEIVE_CONFIRMATION":
                    details_url = f"{config.API_URL}/WasteRegister/WasteTransferCard/v1/Kpo/receiveconfirmed/card?KpoId={kpo_id}&CompanyType=2"
                else:  # TRANSPORT_CONFIRMATION
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
