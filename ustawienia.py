# ustawienia.py - konfiguracja aplikacji
# Wartosci czytane sa ze zmiennych srodowiskowych (na Renderze:
# Environment -> Environment Variables). Jesli zmiennej nie ma, a lokalnie
# istnieje stary plik config.py, brana jest wartosc z niego.
# Dzieki temu aplikacja nie wywraca sie przy starcie, gdy config.py brakuje.
import os

try:
    import config as _plik
except ImportError:
    _plik = None


def _wartosc(nazwa, domyslna=None):
    v = os.environ.get(nazwa)
    if v:
        return v
    if _plik is not None and getattr(_plik, nazwa, None):
        return getattr(_plik, nazwa)
    return domyslna


# Standardowy adres produkcyjnego API BDO; mozna nadpisac zmienna API_URL.
API_URL = _wartosc('API_URL', 'https://rejestr-bdo.mos.gov.pl/api')
CLIENT_ID = _wartosc('CLIENT_ID')
CLIENT_SECRET = _wartosc('CLIENT_SECRET')
EUP_ID = _wartosc('EUP_ID')

EMAIL_SENDER = _wartosc('EMAIL_SENDER')
EMAIL_RECEIVER = _wartosc('EMAIL_RECEIVER')
EMAIL_PASSWORD = _wartosc('EMAIL_PASSWORD')
