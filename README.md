# 🔔 Freelance Job Monitor

Automatische monitor voor Scrum Master / Agile Coach opdrachten op Nederlandse freelance platforms.  
Draait via **GitHub Actions** (gratis) en stuurt een e-mail zodra er nieuwe opdrachten verschijnen.

---

## Gemonitorde platforms

| Platform | URL |
|---|---|
| Freelance.nl | freelance.nl |
| Malt.nl | malt.nl |
| Freep.nl | freep.nl |
| Striive | striive.com |
| Quest4 | quest4.nl |
| HeadFirst | headfirst.group |
| Between | between.nl |
| Yacht | yacht.nl |
| Brunel | brunel.net |
| Flextender | flextender.nl |
| TenderNed | tenderned.nl |

---

## Setup — Stap voor stap

### 1. Maak een Gmail App Password aan

> GitHub kan niet inloggen met je gewone Gmail-wachtwoord. Je hebt een "App Password" nodig.

1. Ga naar [myaccount.google.com/security](https://myaccount.google.com/security)
2. Zorg dat **2-staps verificatie** aan staat
3. Ga naar [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
4. Maak een nieuw app-wachtwoord aan (kies "Overig" → noem het "Job Monitor")
5. Kopieer het 16-teken wachtwoord (bijv. `abcd efgh ijkl mnop`)

### 2. Maak een nieuwe GitHub repository

1. Ga naar [github.com/new](https://github.com/new)
2. Naam: `job-monitor` (of iets anders)
3. Zet op **Private** (je wilt niet dat iedereen je config ziet)
4. Klik "Create repository"

### 3. Upload alle bestanden

De makkelijkste manier:

1. Klik in je nieuwe repo op **"uploading an existing file"**
2. Sleep ALLE bestanden en mappen uit het gedownloade ZIP-bestand naar het upload-venster:
   - `monitor.py`
   - `config.yaml`
   - `requirements.txt`
   - `seen_jobs.json`
   - `.github/workflows/monitor.yml` ← **let op:** de `.github` map is een verborgen map!
3. Commit de bestanden

> **Tip voor de `.github` map:** Als je OS verborgen bestanden niet toont, zet dit dan aan in je bestandsverkenner, of gebruik de GitHub web-editor om het workflow-bestand handmatig aan te maken.

### 4. Voeg Secrets toe

1. Ga naar je repo → **Settings** → **Secrets and variables** → **Actions**
2. Klik **"New repository secret"** en voeg toe:

| Naam | Waarde |
|---|---|
| `EMAIL_SENDER` | `bjorngrob1980@gmail.com` |
| `EMAIL_PASSWORD` | Je Gmail App Password (16 tekens) |

### 5. Test het!

1. Ga naar **Actions** tab in je repo
2. Klik links op **"Freelance Job Monitor"**
3. Klik **"Run workflow"** → **"Run workflow"**
4. Wacht ~2 minuten en check je e-mail

---

## Configuratie aanpassen

Bewerk `config.yaml` om:

- **Zoekwoorden** te wijzigen of toe te voegen
- **Sites** aan/uit te zetten (comment uit met `#`)
- **E-mail ontvanger** te wijzigen

```yaml
keywords:
  - scrum master
  - scrummaster
  - agile coach
  - product owner       # ← voorbeeld: extra zoekwoord

sites:
  - freelance_nl
  - yacht
  # - brunel            # ← uitgeschakeld
```

---

## Schema aanpassen

Het standaard schema is **elk uur van 7:00-22:00 CET**.  
Wijzig in `.github/workflows/monitor.yml`:

```yaml
schedule:
  # Elk uur, 7:00-22:00 CET (= 5:00-20:00 UTC)
  - cron: '0 5-20 * * *'

  # Alleen werkdagen, elke 2 uur:
  # - cron: '0 6-18/2 * * 1-5'

  # 3x per dag (8:00, 13:00, 18:00 CET):
  # - cron: '0 6,11,16 * * *'
```

---

## Veelgestelde vragen

**Q: Kost dit geld?**  
Nee. GitHub Actions biedt 2000 gratis minuten per maand voor private repos. Elk scan duurt ~1-2 minuten. Bij 16 scans/dag ≈ 480 min/maand — ruim binnen de limiet.

**Q: Een site werkt niet / geeft geen resultaten?**  
Sommige sites laden hun vacatures via JavaScript (niet zichtbaar voor een simpele HTTP-request). Als een site structureel 0 resultaten geeft, laat het me weten — dan pas ik de scraper aan (bijv. met een API-endpoint als dat beschikbaar is).

**Q: Kan ik meer zoekwoorden toevoegen?**  
Ja! Voeg ze toe in `config.yaml` onder `keywords`.

**Q: Ik krijg te veel / te weinig resultaten?**  
Verfijn de zoekwoorden. Hoe specifieker, hoe minder ruis.
