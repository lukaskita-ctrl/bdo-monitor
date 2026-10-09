# BDO Monitor — kontekst projektu

Ten plik czytasz na początku każdej sesji. Opisuje, czym jest aplikacja, jakie są twarde zasady, co już wiemy o kodzie i co jest do zrobienia.

## O projekcie

BDO Monitor to aplikacja Flask (Python) dla firmy Zielony Obieg, która zajmuje się transportem i odzyskiem (proces R10, rolnicze wykorzystanie) komunalnych osadów ściekowych (kod odpadu 19 08 05).

Aplikacja:
- pobiera karty przekazania odpadów (KPO) z rządowego systemu BDO przez API,
- pozwala potwierdzać przejęcie odpadu jednym kliknięciem,
- liczy statystyki tonażu według wytwórców (oczyszczalni),
- wysyła powiadomienia mailowe o nowych kartach,
- moduł Działki: ewidencja działek rolnych, dostaw osadu i limitów dawki.

Właściciel produktu: Łukasz. Nie jest programistą — czyta Pythona, ale decyzje techniczne trzeba mu krótko wyjaśniać po polsku. Zna świetnie domenę (BDO, R10, przepisy o osadach). Cel na teraz: **solidna wersja v1.0 dla własnej firmy**. Później: rozbudowa do SaaS dla innych firm, dlatego kod ma być od razu porządny i rozszerzalny.

## Zasady nadrzędne (nie łamać)

1. **Potwierdzenie karty w BDO to czynność prawna.** Nigdy nie potwierdzaj kart automatycznie ani w testach na prawdziwym API. Potwierdzenie zawsze jest świadomą akcją użytkownika (POST + CSRF + potwierdzenie w UI).
2. **Żadnych sekretów w kodzie, repo ani na czacie.** Klucze BDO (CLIENT_ID, CLIENT_SECRET, EUP_ID) i dane maila tylko w zmiennych środowiskowych (`.env` lokalnie, ustawienia na Renderze). Utrzymuj `config.example.py` / `.env.example` bez wartości.
3. **Nie pracuj na `main`.** Render wdraża z `main` automatycznie. Każde zadanie na osobnej gałęzi; merge do `main` tylko po akceptacji Łukasza.
4. **Testy bez prawdziwego API.** Logikę sprawdzaj na fixtures (zanonimizowane JSON-y odpowiedzi BDO w `tests/fixtures/`).
5. **Liczby liczy Python.** Masy, dawki na hektar, limity, daty i prognozy — zawsze w kodzie, nigdy przez model językowy (dotyczy przyszłych funkcji AI).
6. **Małe kroki.** Jedno zadanie = jedna gałąź = krótki opis zmian po polsku (co, dlaczego, jak sprawdzić).
7. **Nie dokładaj funkcji na zapas.** Złożoność dodajemy, gdy realne użycie pokaże potrzebę.

## Stack i środowisko

- Python, Flask (Blueprints), SQLite (moduł Działki)
- Hosting: Render.com (region Frankfurt), docelowo subdomena `bdo.zielonyobieg.pl`
- Repo: GitHub `lukaskita-ctrl/bdo-monitor`
- Mail: Mailgun / SMTP
- Łukasz pracuje na Windows (natywnie, PowerShell)
- Render (darmowy plan, usypia przy braku ruchu): Build `pip install -r requirements.txt`, Start `python app.py`, auto-deploy z `main` przy każdym commicie.
- `monitor.py` **nie jest nigdzie uruchamiany** (Start Command odpala tylko `app.py`) — powiadomienia mailowe obecnie nie działają.
- Konfiguracja: `ustawienia.py` czyta zmienne środowiskowe (na Renderze: Environment), awaryjnie stary `config.py`. Wzór zmiennych: `.env.example`.
- Lokalnie u Łukasza (`C:\Users\lukas\bdo-monitor`) leży `config.py` z **produkcyjnymi** kluczami BDO. Nie uruchamiaj niczego, co łączy się z prawdziwym API BDO, bez jego wyraźnej zgody.

## Wiedza o API BDO

- Uwierzytelnianie: client credentials, token Bearer, identyfikator miejsca prowadzenia działalności (EUP_ID).
- Potwierdzenie KPO to dwa kroki: najpierw GET szczegółów karty, potem PUT potwierdzenia z pobraną masą.
- API wymaga wartości liczbowych (nie `None`) w polach typu `correctedWasteMass`.
- Odpowiedzi bywają z kluczem `items` albo `Items` — obsługuj oba w jednym miejscu.
- Pola kart mogą być nieobecne (np. `wasteCodeDescription`, `wasteMass`) — kod nie może się przez to wywracać.

## Stan obecny kodu (z przeglądu, październik 2026)

Krytyczne:
- `auth.py`: zapytania nadal przez `curl` w `subprocess` (bez `shell=True` od PR #1); token widoczny w argumentach procesu → docelowo `requests`.
- Logowanie HTTP Basic (`APP_USER`/`APP_PASSWORD`) działa od PR #1 — docelowo można zamienić na formularz logowania z sesją.
- `/confirm/<id>` to GET (link) → podatne na CSRF i prefetch.
- Brak paginacji: lista 50 kart, statystyki 200 → statystyki po cichu zaniżone.
- `monitor.py`: karta dodawana do `known_kpos` przed wysłaniem maila, wynik wysyłki ignorowany; stan tylko w pamięci (ginie po restarcie).
- Rok `2026` wpisany na sztywno w `get_kpo_list` i `get_kpo_by_date`.

Funkcjonalność i dług:
- Nowy token przy każdym żądaniu, statystyki robią 1 + N wywołań sekwencyjnie → wolno, ryzyko timeoutu.
- Brak timeoutów na wywołaniach sieciowych i SMTP.
- Filtr dat robiony lokalnie po `receiveConfirmationTime`; karty o statusie `TRANSPORT_CONFIRMATION` mieszają się w statystykach. (Łukasz zgłaszał też, że karty „znikają ze statystyk” po potwierdzeniu — prawdopodobnie ten sam problem ze statusami/paginacją.)
- Błędy zwracane jako gołe stringi z kodem 200; brak komunikatów (flash) po potwierdzeniu.
- Duplikaty `index.html` i `stats.html` w katalogu głównym (Flask używa `templates/`); `templates/stats.html` ma zdublowane `<meta charset>` i `<title>`.
- Cztery prawie identyczne funkcje `_curl_*`, gołe `except:`.
- `requests` w requirements, ale nieużywany; brak przypiętych wersji i `gunicorn`.
- `print` zamiast `logging`; brak testów i CI.
- README obiecuje rzeczy, których nie ma (LICENSE, PWA, push, mobile-first).

**Moduł Działki — jeszcze nie istnieje w kodzie.** Repo zawiera tylko monitor kart i statystyki (bez SQLite i Blueprintów). Moduł był wcześniej projektowany w rozmowie z Claude (tabele `oczyszczalnie`, `wlasciciele`, `dzialki`, `dostawy`, `historia_sm`; dashboard działek, formularz dostawy z kalkulatorem, zarządzanie oczyszczalniami, generator rocznego sprawozdania dla oczyszczalni), ale nie został wdrożony. Traktuj ten opis jako punkt wyjścia do Etapu 5, nie jako istniejący kod. Strukturę aplikacji (Blueprints, SQLite) przygotuj w Etapach 1–3 tak, żeby moduł dało się później dołożyć.

## Plan prac

### Etap 0 — przygotowanie
- [x] Ustalone, jak działa `monitor.py` na Renderze (nie działa — patrz wyżej).
- [ ] Zanonimizowane fixtures z odpowiedzi BDO w `tests/fixtures/`.

### Etap 1 — bezpieczeństwo i klient API
- [ ] Jeden klient API na `requests`: bez shella, timeouty, cache tokena do wygaśnięcia, obsługa `items`/`Items`. (Pilna łatka: `shell=True` usunięte w PR #1.)
- [x] Konfiguracja ze zmiennych środowiskowych + `.env.example` (PR #2).
- [x] Logowanie do aplikacji: HTTP Basic z env (PR #1).
- [ ] Potwierdzanie przez POST + CSRF + komunikat o wyniku.

### Etap 2 — kompletne i poprawne dane
- [ ] Paginacja we wszystkich zapytaniach.
- [ ] Rok wyliczany z zakresu dat (także zakres przez dwa lata).
- [ ] Jasna logika statusów kart w statystykach.
- [ ] Odporność na brakujące pola.

### Etap 3 — monitor
- [ ] Karta oznaczana jako znana dopiero po udanej wysyłce maila.
- [ ] Trwały stan (tabela w SQLite).
- [ ] Jeden sposób uruchamiania zgodny z Renderem.

### Etap 4 — porządki
- [ ] Usunąć duplikaty HTML, naprawić `stats.html`.
- [ ] `logging`, przypięte wersje, `gunicorn`, LICENSE.
- [ ] Testy (statystyki, filtr dat, paginacja) i proste CI.
- [ ] README zgodne z rzeczywistością.

### Etap 5 — funkcje v1.0 (z notatek Łukasza)
- [ ] Widok nowych kart z akcją zatwierdź / odrzuć, odświeżany na bieżąco.
- [ ] Przypisanie potwierdzonej karty do działki (sposób powiązania do ustalenia z Łukaszem — wcześniej dostawy na działki wpisywano osobno w zakładce Działki).
- [ ] Baza działek z powierzchnią do zagospodarowania.
- [ ] Powiązanie karty z badaniem osadu (sucha masa) → dawka w Mg s.m./ha i pilnowanie limitów.
- [ ] Eksport do Excela.

### Etap 6 — prognoza stanu osadu na oczyszczalni
Cel: szacować, ile osadu leży na placu oczyszczalni i kiedy osiągnie zadaną ilość (planowanie kampanii).
- Dane: odbiory (data ostatniego kursu, masa) z kart KPO.
- Model: oczyszczalnie opróżniane kampaniami do zera → tempo = masa kampanii / dni od końca poprzedniej kampanii; stan dziś = tempo × dni od ostatniego opróżnienia; data osiągnięcia X Mg = X / tempo. Pokazywać przedział (min–max z historycznych temp), z korektą sezonową, gdy będzie więcej danych.
- Możliwość wpisania ręcznego odczytu z oczyszczalni („dziś ok. N Mg”) jako punktu kalibracji.
- Walidacja: na jednej z oczyszczalni prognoza ok. 220 Mg zgodziła się z odczytem z placu (7.10.2026), tempo ok. 17–18 Mg/dobę.

### Etap 7 — AI (dopiero po v1.0)
- Warstwa pośrednia `llm.py` (jedna funkcja), żeby przełączać dostawcę konfiguracją.
- Kandydaci: Mistral przez API (hosting w UE; ekstrakcja danych z PDF-ów z badań osadu i gleby, asystent z function calling po danych z SQLite), Bielik lokalnie (dokumenty po polsku), basal (klasyfikacja maili/uwag z progiem pewności — wymaga GPU NVIDIA, Render jej nie ma).
- AI tylko podpowiada; nigdy nie potwierdza kart. Decyzje AI logowane.

## Jak raportować pracę

Po każdym zadaniu krótko po polsku:
1. Co zmieniłeś i dlaczego (bez żargonu, gdzie się da).
2. Jak Łukasz może to sprawdzić u siebie (konkretne kroki w PowerShell / w przeglądarce).
3. Czy coś wymaga jego decyzji.
