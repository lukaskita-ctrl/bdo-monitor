# 🗑️ BDO Monitor - Zielony Obieg

**Automatyczne monitorowanie i zarządzanie kartami przekazania odpadów (KPO) z systemu BDO**

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-Web_Framework-green.svg)](https://flask.palletsprojects.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 📋 O projekcie

BDO Monitor to aplikacja webowa stworzona dla firmy **Zielony Obieg** do automatyzacji procesów związanych z zarządzaniem odpadami w Polsce. Aplikacja integruje się z oficjalnym API systemu BDO (Baza Danych Odpadowych) i zastępuje ręczne sprawdzanie portalu rządowego.

### Problem który rozwiązuje

- ❌ Codzienne ręczne logowanie do portalu BDO
- ❌ Przeszukiwanie listy kart wymagających potwierdzenia
- ❌ Brak powiadomień o nowych kartach
- ❌ Czasochłonne generowanie raportów i statystyk

### Rozwiązanie

- ✅ Automatyczne pobieranie kart KPO wymagających potwierdzenia
- ✅ Jedno-klikowe potwierdzanie kart
- ✅ Powiadomienia email o nowych kartach
- ✅ Statystyki tonaży wg wytwórców odpadów
- ✅ Responsywny interfejs dostępny z telefonu

## 🖼️ Screenshots

### Dashboard główny
Lista kart KPO oczekujących na potwierdzenie z przyciskami akcji.

### Statystyki
Zestawienie tonaży odpadów według wytwórców z filtrowaniem po datach.

## 🚀 Funkcjonalności

| Funkcja | Opis |
|---------|------|
| **Dashboard KPO** | Lista kart do potwierdzenia ze statusami |
| **Potwierdzanie kart** | Jednym kliknięciem z automatycznym pobieraniem masy |
| **Statystyki** | Sumowanie tonaży wg wytwórców z filtrami dat |
| **Powiadomienia** | Email przez Mailgun o nowych kartach |
| **Mobile-friendly** | Responsywny design do pracy w terenie |

## 🛠️ Stack technologiczny

- **Backend:** Python 3.9+, Flask
- **Frontend:** HTML5, CSS3 (inline styles)
- **API:** BDO API (OAuth 2.0 Client Credentials)
- **Email:** Mailgun SMTP
- **Hosting:** PythonAnywhere / Render.com

## 📦 Instalacja

### Wymagania

- Python 3.9 lub nowszy
- Konto w systemie BDO z dostępem do API
- (Opcjonalnie) Konto Mailgun dla powiadomień

### Krok 1: Klonowanie repozytorium

```bash
git clone https://github.com/lukaskita-ctrl/bdo-monitor.git
cd bdo-monitor
```

### Krok 2: Instalacja zależności

```bash
pip install -r requirements.txt
```

### Krok 3: Konfiguracja

Utwórz plik `config.py` z danymi dostępowymi:

```python
# BDO API Configuration
CLIENT_ID = "twoj_client_id"
CLIENT_SECRET = "twoj_client_secret"
EUP_ID = "twoj_eup_id"
API_URL = "https://api.bdo.mos.gov.pl"

# Email Configuration (Mailgun)
EMAIL_SENDER = "bdo@twoja-domena.pl"
EMAIL_RECEIVER = "twoj@email.pl"
EMAIL_PASSWORD = "mailgun_password"
```

### Krok 4: Uruchomienie

```bash
python app.py
```

Aplikacja będzie dostępna pod adresem `http://localhost:5000`

## 📁 Struktura projektu

```
bdo-monitor/
├── app.py              # Główna aplikacja Flask (routes)
├── auth.py             # Moduł autoryzacji i logiki BDO API
├── config.py           # Konfiguracja (nie commitować!)
├── monitor.py          # Moduł monitorowania (scheduled tasks)
├── notifications.py    # Wysyłanie powiadomień email
├── requirements.txt    # Zależności Python
├── templates/
│   ├── index.html      # Dashboard główny
│   └── stats.html      # Strona statystyk
└── static/
    └── icon.png        # Ikona aplikacji (PWA)
```

## 🔌 Endpoints API

| Endpoint | Metoda | Opis |
|----------|--------|------|
| `/` | GET | Dashboard z listą KPO do potwierdzenia |
| `/stats` | GET, POST | Statystyki tonaży z filtrami dat |
| `/confirm/<kpo_id>` | GET | Potwierdzenie pojedynczej karty KPO |

## 🔒 Bezpieczeństwo

- Dane dostępowe przechowywane w osobnym `config.py` (nie commitowany)
- Autoryzacja OAuth 2.0 z tokenami Bearer
- Komunikacja z API BDO przez HTTPS

## 🚧 Planowane funkcjonalności

- [ ] Eksport danych do Excel/PDF
- [ ] Archiwum historycznych KPO z wyszukiwaniem
- [ ] Powiadomienia push (PWA)
- [ ] Integracja z AI do analizy trendów
- [ ] Dashboard analityczny z wykresami
- [ ] Automatyczne raporty miesięczne

## 🤝 Wkład w projekt

Projekt jest rozwijany na potrzeby firmy Zielony Obieg, ale sugestie i pull requesty są mile widziane!

1. Fork repozytorium
2. Utwórz branch (`git checkout -b feature/nowa-funkcja`)
3. Commit zmian (`git commit -m 'Dodaj nową funkcję'`)
4. Push do brancha (`git push origin feature/nowa-funkcja`)
5. Otwórz Pull Request

## 📄 Licencja

Ten projekt jest dostępny na licencji MIT - szczegóły w pliku [LICENSE](LICENSE).

## 👤 Autor

**Łukasz** - [lukaskita-ctrl](https://github.com/lukaskita-ctrl)

Firma: **Zielony Obieg** - Gospodarka odpadami, Polska

---

*Zbudowane z ❤️ dla branży gospodarki odpadami*

