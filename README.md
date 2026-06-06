# Zarządcy Nieruchomości Wrocław – GitHub Pages

Strona wyświetla dane zarządców nieruchomości z Wrocławia pobrane z Google Maps API.

## Jak wdrożyć na GitHub Pages

### Krok 1 — Utwórz repozytorium
1. Wejdź na [github.com](https://github.com) i zaloguj się
2. Kliknij **New repository**
3. Nazwa np. `zarzadcy-wroclaw`
4. Ustaw jako **Public** (GitHub Pages działa bezpłatnie dla publicznych)
5. Kliknij **Create repository**

### Krok 2 — Wgraj pliki
Wgraj te 3 pliki do repozytorium:
- `index.html`
- `data.json`
- `README.md` (opcjonalnie)

Możesz to zrobić przez interfejs GitHub: **Add file → Upload files**

### Krok 3 — Włącz GitHub Pages
1. W repozytorium kliknij **Settings**
2. W lewym menu: **Pages**
3. Source: **Deploy from a branch**
4. Branch: `main`, folder: `/ (root)`
5. Kliknij **Save**

Po chwili (1–2 min) strona będzie dostępna pod adresem:
```
https://TWOJA-NAZWA.github.io/zarzadcy-wroclaw/
```

---

## Jak podmienić dane (266 firm zamiast 10)

Uruchom skrypt `generate_data.py` (czyta `dane/wroclaw/zarzadcy_wroclaw_full_details.json`), który tworzy pełny `data.json`:

```bash
python generate_data.py
```

Następnie wgraj nowy `data.json` do repozytorium — strona automatycznie pokaże wszystkie firmy.

Strona pobiera dane przez `fetch('data.json')` — nie ma żadnych danych wbitych w HTML.

---

## Struktura plików

```
github-pages/
├── index.html      # Strona (tabela + mapa, nie edytuj)
├── data.json       # BAZA DANYCH — tylko ten plik podmieniasz
└── README.md       # Ta instrukcja
```

## Struktura data.json

```json
{
  "generated_at": "2026-06-02 17:56:51",
  "total": 10,
  "results": [
    {
      "name": "Nazwa firmy",
      "address": "Adres",
      "phone": "500 000 000",
      "website": "https://...",
      "rating": 4.5,
      "reviews_count": 42,
      "maps_url": "https://maps.google.com/...",
      "status": "OPERATIONAL",
      "hours": ["poniedziałek: 9:00–17:00", ...],
      "lat": 51.107,
      "lng": 17.038,
      "reviews": [
        { "author": "Jan Kowalski", "rating": 5, "time": "rok temu", "text": "..." }
      ]
    }
  ]
}
```
