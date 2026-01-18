# monitor.py - automatyczny monitoring KPO z powiadomieniami

import time
import auth
import notifications

# Co ile minut sprawdzać
INTERVAL_MINUTES = 15

# Przechowujemy ID kart które już widzieliśmy
known_kpos = set()

def check_for_new_kpos():
    """Sprawdza czy są nowe karty do zatwierdzenia"""
    global known_kpos
    
    token = auth.get_token()
    if not token:
        print("Błąd: nie można uzyskać tokena")
        return
    
    result = auth.get_kpo_list(token)
    if not result or "items" not in result:
        print("Brak danych z BDO")
        return
    
    # Filtruj karty do zatwierdzenia
    pending = [k for k in result["items"] 
               if k.get("cardStatusCodeName") == "CONFIRMATION_GENERATED"]
    
    # Znajdź nowe karty
    new_kpos = []
    for kpo in pending:
        kpo_id = kpo.get("kpoId")
        if kpo_id not in known_kpos:
            known_kpos.add(kpo_id)
            new_kpos.append(kpo)
    
    if new_kpos:
        print(f"Znaleziono {len(new_kpos)} nowych KPO!")
        notifications.notify_new_kpo(new_kpos)
    else:
        print("Brak nowych KPO")

def main():
    print("=== Monitor KPO uruchomiony ===")
    print(f"Sprawdzanie co {INTERVAL_MINUTES} minut")
    print("Naciśnij Ctrl+C aby zatrzymać\n")
    
    # Pierwsze sprawdzenie - zapamiętaj istniejące karty
    token = auth.get_token()
    if token:
        result = auth.get_kpo_list(token)
        if result and "items" in result:
            for kpo in result["items"]:
                if kpo.get("cardStatusCodeName") == "CONFIRMATION_GENERATED":
                    known_kpos.add(kpo.get("kpoId"))
            print(f"Zapamiętano {len(known_kpos)} istniejących KPO\n")
    
    # Pętla sprawdzająca
    while True:
        time.sleep(INTERVAL_MINUTES * 60)
        print(f"\n[{time.strftime('%H:%M')}] Sprawdzam...")
        check_for_new_kpos()

if __name__ == "__main__":
    main()