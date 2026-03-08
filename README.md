# 🗑️ BDO Monitor — Automated Waste Transfer Card Management

> A web application that automates monitoring and management of waste transfer cards (KPO) through Poland's national BDO (Waste Database) API — replacing tedious daily manual checks with a mobile-friendly dashboard.

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-Web_Framework-000000?logo=flask)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 🎯 Why This Exists

In Poland, every company that transports or processes waste is legally required to use **BDO** (*Baza Danych o Produktach i Opakowaniach oraz o Gospodarce Odpadami*) — a government-run waste tracking database. Every waste transfer generates a **KPO** (Karta Przekazania Odpadów / Waste Transfer Card) that must be manually reviewed and confirmed through a clunky government web portal.

For a company like mine that handles **thousands of tons of sewage sludge per year** across multiple agricultural partners, this means:

- ❌ Logging into the BDO portal daily
- ❌ Manually searching through lists of cards awaiting confirmation
- ❌ No notifications when new cards arrive
- ❌ No easy way to generate tonnage reports or statistics

**BDO Monitor** solves all of this:

- ✅ Automatic retrieval of KPO cards awaiting confirmation
- ✅ One-click card confirmation directly from the app
- ✅ Email notifications for new cards (via Mailgun)
- ✅ Tonnage statistics by waste producer with date filtering
- ✅ Responsive UI — works from a phone in the field

---

## 📱 Features

| Feature | Description |
|---------|-------------|
| **KPO Dashboard** | Live list of waste transfer cards pending confirmation |
| **One-Click Confirm** | Confirm cards instantly with automatic mass/weight retrieval |
| **Statistics** | Tonnage summaries by waste producer with date range filters |
| **Email Alerts** | Mailgun-powered notifications when new cards appear |
| **Mobile-Friendly** | Responsive design built for field use on a phone |

---

## 🛠️ Tech Stack

- **Backend:** Python 3.9+, Flask
- **Frontend:** HTML5, CSS3 (inline styles, no framework)
- **API Integration:** BDO API (OAuth 2.0 Client Credentials flow)
- **Email:** Mailgun SMTP
- **Hosting:** PythonAnywhere / Render.com

---

## 📁 Project Structure

```
bdo-monitor/
├── app.py              # Main Flask app (routes & views)
├── auth.py             # BDO API authorization & core logic
├── config.py           # Configuration (not committed — see setup)
├── monitor.py          # Scheduled monitoring tasks
├── notifications.py    # Email notification module
├── requirements.txt    # Python dependencies
├── templates/
│   ├── index.html      # Main dashboard
│   └── stats.html      # Statistics page
└── static/
    └── icon.png        # App icon (PWA)
```

---

## 🚀 Setup

### Prerequisites

- Python 3.9+
- BDO account with API access ([api.bdo.mos.gov.pl](https://api.bdo.mos.gov.pl))
- (Optional) Mailgun account for email notifications

### Installation

```bash
git clone https://github.com/lukaskita-ctrl/bdo-monitor.git
cd bdo-monitor
pip install -r requirements.txt
```

### Configuration

Create a `config.py` file with your credentials:

```python
# BDO API Configuration
CLIENT_ID = "your_client_id"
CLIENT_SECRET = "your_client_secret"
EUP_ID = "your_eup_id"
API_URL = "https://api.bdo.mos.gov.pl"

# Email Configuration (Mailgun)
EMAIL_SENDER = "bdo@your-domain.com"
EMAIL_RECEIVER = "your@email.com"
EMAIL_PASSWORD = "mailgun_password"
```

### Run

```bash
python app.py
```

The app will be available at `http://localhost:5000`

---

## 🔌 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard — list of KPO cards pending confirmation |
| `/stats` | GET, POST | Tonnage statistics with date filters |
| `/confirm/<kpo_id>` | GET | Confirm a single KPO card |

---

## 🔒 Security

- Credentials stored in a separate `config.py` (excluded from version control)
- OAuth 2.0 Bearer token authentication with BDO API
- All API communication over HTTPS

---

## 🗺️ Roadmap

- [ ] Export data to Excel / PDF
- [ ] Historical KPO archive with search
- [ ] Push notifications (PWA)
- [ ] AI-powered trend analysis
- [ ] Analytics dashboard with charts
- [ ] Automated monthly reports

---

## 🧑‍💻 About

Built by **Łukasz Kita** ([@lukaskita-ctrl](https://github.com/lukaskita-ctrl)) — founder of [Zielony Obieg](https://zielonyobieg.pl), a waste management company in Poland specializing in sewage sludge transport and agricultural disposal.

This project was born out of a real daily pain point: spending too much time on the BDO government portal doing repetitive manual work. Instead of accepting it, I learned Python and built a tool to automate it.

---

## 📄 License

MIT — see [LICENSE](LICENSE) for details.

---

<details>
<summary>🇵🇱 README po polsku</summary>

## BDO Monitor — Zielony Obieg

Automatyczne monitorowanie i zarządzanie kartami przekazania odpadów (KPO) z systemu BDO.

Aplikacja webowa stworzona dla firmy Zielony Obieg do automatyzacji procesów związanych z zarządzaniem odpadami w Polsce. Integruje się z oficjalnym API systemu BDO i zastępuje ręczne sprawdzanie portalu rządowego.

### Funkcjonalności

- Automatyczne pobieranie kart KPO wymagających potwierdzenia
- Jedno-klikowe potwierdzanie kart
- Powiadomienia email o nowych kartach (Mailgun)
- Statystyki tonaży wg wytwórców odpadów z filtrami dat
- Responsywny interfejs dostępny z telefonu

### Stack

Python 3.9+ · Flask · BDO API (OAuth 2.0) · Mailgun · HTML5/CSS3

### Instalacja

```bash
git clone https://github.com/lukaskita-ctrl/bdo-monitor.git
cd bdo-monitor
pip install -r requirements.txt
# Utwórz config.py z danymi dostępowymi (patrz sekcja angielska)
python app.py
```

</details>
