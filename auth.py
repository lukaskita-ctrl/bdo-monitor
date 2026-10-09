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

STATUSY_POTWIERDZONE = ("RECEIVE_CONFIRMATION", "TRANSPORT_CONFIRMATION")
ROZMIAR_STRONY = 200
MAKS_STRON = 50


def _szukaj_kart(token, year):
    """Wszystkie karty z danego roku, gdzie firma jest przejmujacym - strona po stronie.
    Zwraca liste kart albo None, gdy BDO nie odpowiedzialo juz na pierwsza strone."""
    url = f"{config.API_URL}/WasteRegister/WasteTransferCard/v1/Kpo/receiver/search"
    karty, widziane = [], set()
    for strona in range(MAKS_STRON):
        payload = {
            "PaginationParameters": {
                "Order": {"IsAscending": False},
                "Page": {"Index": strona, "Size": ROZMIAR_STRONY}
            },
            "Year": year,
            "SearchInCarriers": True,
            "SearchInSenders": True,
            "TransportDateRange": True,
            "ReceiveConfirmationDateRange": True
        }
        wynik = _curl_post_auth(url, payload, token)
        if not isinstance(wynik, dict):
            return None if strona == 0 else karty
        pozycje = wynik.get("items") or wynik.get("Items") or []
        nowe = [k for k in pozycje if k.get("kpoId") not in widziane]
        for k in nowe:
            widziane.add(k.get("kpoId"))
        karty.extend(nowe)
        # koniec: niepelna strona albo BDO zwraca w kolko to samo
        if len(pozycje) < ROZMIAR_STRONY or not nowe:
            break
    return karty


def get_kpo_list(token, year=None):
    """Karty, gdzie firma jest przejmujacym: biezacy rok, a w styczniu takze poprzedni
    (karty z konca grudnia czekajace na potwierdzenie). Zwraca {"items": [...]} albo None."""
    from datetime import date
    dzis = date.today()
    lata = [year] if year else ([dzis.year - 1, dzis.year] if dzis.month == 1 else [dzis.year])
    wszystkie, udane = [], False
    for rok in lata:
        karty = _szukaj_kart(token, rok)
        if karty is not None:
            udane = True
            wszystkie.extend(karty)
    return {"items": wszystkie} if udane else None


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

def _szczegoly_karty(token, kpo):
    """Szczegoly potwierdzonej karty (masa, data potwierdzenia) albo None."""
    kpo_id = kpo.get("kpoId")
    if kpo.get("cardStatusCodeName") == "RECEIVE_CONFIRMATION":
        url = f"{config.API_URL}/WasteRegister/WasteTransferCard/v1/Kpo/receiveconfirmed/card?KpoId={kpo_id}&CompanyType=2"
    else:
        url = f"{config.API_URL}/WasteRegister/WasteTransferCard/v1/Kpo/transportconfirmation/card?KpoId={kpo_id}&CompanyType=2"
    szczegoly = _curl_get_auth(url, token)
    return szczegoly if isinstance(szczegoly, dict) else None


def _masa(*zrodla):
    """Masa przyjeta: najpierw skorygowana przez przejmujacego, potem z karty."""
    for zrodlo in zrodla:
        if not isinstance(zrodlo, dict):
            continue
        for pole in ("correctedWasteMass", "wasteMass"):
            try:
                wartosc = float(zrodlo.get(pole) or 0)
            except (TypeError, ValueError):
                continue
            if wartosc > 0:
                return wartosc
    return 0.0


def get_kpo_by_date(token, date_from, date_to, year=None):
    """Karty potwierdzone (przez przejmujacego lub juz takze przez transportujacego),
    ktorych data potwierdzenia przyjecia miesci sie w zakresie dat.
    Zwraca {"items": [...], "bez_daty": n, "bez_szczegolow": n} albo None przy bledzie BDO."""
    from concurrent.futures import ThreadPoolExecutor

    rok_od, rok_do = int(date_from[:4]), int(date_to[:4])
    if date_from[5:7] == "01":
        rok_od -= 1  # karty z grudnia potwierdzane w styczniu
    lata = [year] if year else list(range(rok_od, rok_do + 1))

    kandydaci, udane = [], False
    for rok in lata:
        karty = _szukaj_kart(token, rok)
        if karty is not None:
            udane = True
            kandydaci.extend(k for k in karty if k.get("cardStatusCodeName") in STATUSY_POTWIERDZONE)
    if not udane:
        return None

    # karty z data na liscie spoza zakresu odrzucamy od razu, bez pytania BDO o szczegoly
    do_sprawdzenia = []
    for kpo in kandydaci:
        data = (kpo.get("receiveConfirmationTime") or "")[:10]
        if data and not (date_from <= data <= date_to):
            continue
        do_sprawdzenia.append(kpo)

    with ThreadPoolExecutor(max_workers=6) as pula:
        szczegoly = list(pula.map(lambda k: _szczegoly_karty(token, k), do_sprawdzenia))

    wynik, bez_daty, bez_szczegolow = [], 0, 0
    for kpo, det in zip(do_sprawdzenia, szczegoly):
        if det is None:
            bez_szczegolow += 1
        det = det or {}
        data = (kpo.get("receiveConfirmationTime") or det.get("receiveConfirmationTime") or "")[:10]
        if not data:
            bez_daty += 1
            continue
        if not (date_from <= data <= date_to):
            continue
        wynik.append({
            "cardNumber": det.get("cardNumber") or kpo.get("cardNumber"),
            "senderName": kpo.get("senderName") or det.get("senderName"),
            "wasteMass": _masa(det, kpo),
            "receiveConfirmationTime": data,
            "wasteCode": kpo.get("wasteCode"),
            "status": kpo.get("cardStatusCodeName"),
        })
    return {"items": wynik, "bez_daty": bez_daty, "bez_szczegolow": bez_szczegolow}


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

