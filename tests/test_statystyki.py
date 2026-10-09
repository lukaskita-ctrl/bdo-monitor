"""Test statystyk na falszywym serwerze BDO (bez prawdziwego API).
Uruchom z katalogu projektu:  python tests/test_statystyki.py
Sprawdza: karty po potwierdzeniu transportu (bez daty na liscie), kilka stron wynikow,
zakresy przez dwa lata, korekte masy, karty bez daty i bledy szczegolow."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import os, re, json, base64, threading, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
# --- fałszywe BDO ---
KARTY = {}   # rok -> lista
def dodaj(rok, i, status, data_listy, data_szczeg, masa, korekta=None, oczyszczalnia="A"):
    kid=f"{rok}-{i:05d}"
    KARTY.setdefault(rok,[]).append({"kpoId":kid,"cardNumber":f"KPO/{i}/{rok}","senderName":f"Oczyszczalnia {oczyszczalnia}",
        "cardStatusCodeName":status, **({"receiveConfirmationTime":data_listy} if data_listy else {}),
        "_szcz":{"cardNumber":f"KPO/{i}/{rok}","wasteMass":masa, **({"correctedWasteMass":korekta} if korekta else {}),
                 **({"receiveConfirmationTime":data_szczeg} if data_szczeg else {})}})
n=0
# 2026: 420 kart przyjetych w pazdzierniku: polowa juz potwierdzona przez transportujacego (bez daty na liscie!)
for i in range(420):
    n+=1
    if i%2: dodaj(2026,n,"TRANSPORT_CONFIRMATION",None,"2026-10-0%dT10:00:00"%(1+i%8),25.0,oczyszczalnia="A")
    else:   dodaj(2026,n,"RECEIVE_CONFIRMATION","2026-10-0%dT10:00:00"%(1+i%8),None,25.0,oczyszczalnia="B")
n+=1; dodaj(2026,n,"RECEIVE_CONFIRMATION","2026-10-05T10:00:00",None,25.0,korekta=24.1,oczyszczalnia="B")   # korekta masy
n+=1; dodaj(2026,n,"TRANSPORT_CONFIRMATION",None,None,25.0)                                                # brak daty nigdzie
n+=1; dodaj(2026,n,"RECEIVE_CONFIRMATION","2026-09-15T10:00:00",None,25.0)                                 # poza zakresem
n+=1; dodaj(2026,n,"CONFIRMATION_GENERATED",None,None,25.0)                                                # czeka - nie liczyc
n+=1; dodaj(2026,n,"REJECTED",None,None,25.0)                                                              # odrzucona
n+=1; dodaj(2026,n,"RECEIVE_CONFIRMATION","2026-10-06T10:00:00",None,"BLAD_SZCZEGOLOW",oczyszczalnia="B")  # szczegoly padna
SZCZEG={k["kpoId"]:k["_szcz"] for r in KARTY.values() for k in r}
TRYB={"limit":10**6,"baza":0}
ZAPYTANIA=[]
class Fake(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def _send(self,c,o): b=json.dumps(o).encode(); self.send_response(c); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        p=json.loads(self.rfile.read(int(self.headers.get("Content-Length",0))))
        rok=p["Year"]; idx=p["PaginationParameters"]["Page"]["Index"]; size=p["PaginationParameters"]["Page"]["Size"]
        ZAPYTANIA.append((rok,idx))
        size=min(size, TRYB["limit"])                  # BDO moze obcinac rozmiar strony
        idx=max(idx - TRYB["baza"], 0)                 # BDO moze numerowac strony od 1
        lista=[{k:v for k,v in c.items() if k!="_szcz"} for c in KARTY.get(rok,[])]
        self._send(200,{"items":lista[idx*size:(idx+1)*size]})
    def do_GET(self):
        q=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query); d=SZCZEG[q["KpoId"][0]]
        if d.get("wasteMass")=="BLAD_SZCZEGOLOW": self.send_response(500); self.send_header("Content-Length","0"); self.end_headers(); return
        self._send(200,d)
srv=ThreadingHTTPServer(("127.0.0.1",5097),Fake); threading.Thread(target=srv.serve_forever,daemon=True).start()
os.environ.update(API_URL="http://127.0.0.1:5097",CLIENT_ID="x",CLIENT_SECRET="x",EUP_ID="x",APP_USER="l",APP_PASSWORD="p")
import auth; auth.get_token=lambda:"T"
r=auth.get_kpo_by_date("T","2026-10-01","2026-10-31")
print("strony pobrane z BDO:", sorted(set(ZAPYTANIA)))
print("kart w statystykach:", len(r["items"]), "| bez daty:", r["bez_daty"], "| bez szczegolow:", r["bez_szczegolow"])
assert len(r["items"]) == 422 and r["bez_daty"] == 1 and r["bez_szczegolow"] == 1
assert sum(1 for k in r["items"] if k["status"] == "TRANSPORT_CONFIRMATION") == 210
st=auth.get_detailed_stats(r["items"])
for k,v in sorted(st.items()): print(" ", k, v["count"], "kursow,", round(v["total_mass"],3), "Mg")
print("  w tym po potwierdzeniu transportu:", sum(1 for k in r["items"] if k["status"]=="TRANSPORT_CONFIRMATION"))
# rozne zachowania stronicowania BDO
for opis,tryb in [("BDO obcina strone do 100 kart",{"limit":100,"baza":0}),("BDO numeruje strony od 1",{"limit":10**6,"baza":1}),("oba naraz",{"limit":50,"baza":1})]:
    TRYB.update(tryb); ZAPYTANIA.clear()
    r2=auth.get_kpo_by_date("T","2026-10-01","2026-10-31")
    print(opis, "-> kart:", len(r2["items"]), "| zapytan o strony:", len(ZAPYTANIA))
    assert len(r2["items"]) == 422, opis
TRYB.update({"limit":10**6,"baza":0})
# strona diagnostyczna
import app as A0
cd=A0.app.test_client(); Hd={"Authorization":"Basic "+base64.b64encode(b"l:p").decode()}
hd=cd.get("/diagnostyka?od=2026-10-01&do=2026-10-31",headers=Hd).get_data(as_text=True)
print("diagnostyka: policzone", re.search(r"Policzone w statystykach</strong></td><td[^>]*><strong>(\d+)",hd).group(1),
      "| bez daty na liscie:", "z datą potwierdzenia przyjęcia na liście" in hd, "| nazwy firm na stronie:", "Oczyszczalnia A" in hd)
assert "Oczyszczalnia A" not in hd
# styczen -> pyta tez o poprzedni rok
ZAPYTANIA.clear(); auth.get_kpo_by_date("T","2027-01-01","2027-01-31"); print("zakres styczen 2027 pyta o lata:", sorted({z[0] for z in ZAPYTANIA}))
ZAPYTANIA.clear(); auth.get_kpo_by_date("T","2026-11-15","2027-02-10"); print("zakres XI 2026-II 2027 pyta o lata:", sorted({z[0] for z in ZAPYTANIA}))
# lista do potwierdzenia
print("lista oczekujacych (bez limitu 50):", len(auth.get_kpo_list("T")["items"]), "kart z roku", __import__("datetime").date.today().year)
# strona statystyk
import app as A
c=A.app.test_client(); H={"Authorization":"Basic "+base64.b64encode(b"l:p").decode()}
html=c.post("/stats",headers=H,data={"date_from":"2026-10-01","date_to":"2026-10-31"}).get_data(as_text=True)
print("strona: Razem:", re.search(r"<td>Razem</td><td[^>]*>(\d+)</td><td[^>]*>([^<]+)<",html).groups())
print("strona: uwaga:", " ".join(re.search(r'komunikat-error"[^>]*>(.*?)</div>',html,re.S).group(1).split()))
# BDO nie odpowiada
srv.shutdown(); srv.server_close()
print("OK - wszystkie sprawdzenia przeszly")
print("BDO wylaczone ->", re.search(r'komunikat-error">([^<]+)',c.post("/stats",headers=H,data={"date_from":"2026-10-01","date_to":"2026-10-31"}).get_data(as_text=True)).group(1))
