#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wydajna analiza CSV z generatora elektroniki i AGD, Python 3.10+.

Instalacja:
    python -m pip install "numpy>=1.26" "pandas>=2.2" "scipy>=1.11"
Terminal:
    python analizuj_dane_syntetyczne.py dane_syntetyczne.csv
    python analizuj_dane_syntetyczne.py proba.csv --expected-rows 10000
    python analizuj_dane_syntetyczne.py dane_syntetyczne.csv --chunksize 100000
Colab/Jupyter, po przesłaniu tego pliku do katalogu notebooka:
    %pip install numpy pandas scipy
    from analizuj_dane_syntetyczne import analizuj
    wynik = analizuj("dane_syntetyczne.csv", chunksize=250_000)
Można też wkleić cały skrypt do komórki: zdefiniuje funkcje i pokaże instrukcję,
bez automatycznego czytania pliku i bez parsowania argumentów kernela.

Format: UTF-8 (BOM opcjonalny), średnik, przecinek lub kropka dziesiętna.
Jeden przebieg pliku. Pandas: odczyt partiami i agregacje. NumPy: walidacja,
histogram groszowy, dokładne kwantyle ceny i stabilna macierz kowariancji.
SciPy: diagnostyka chi-kwadrat kolorów. Dask nie jest wymagany.
Pamięć: O(chunksize + expected_rows + 3500001); bitmapa ID to ~5 MB dla
5 mln ID, histogram cen ~28 MB, ponadto ramki i tablice robocze jednej partii.
Nie ma konkatenacji całego wejścia ani pętli Pythona po wszystkich rekordach.

Raporty w nowym katalogu: podsumowanie.json, podsumowanie.txt, jakosc.csv,
produkty.csv, kategorie.csv, wojewodztwa.csv, miasta.csv, kolory.csv,
histogram_cen.csv, korelacje.csv, bledne_wiersze_probka.csv.
Nowy katalog z datą jest tworzony automatycznie; istniejący nie jest nadpisywany.
Jeśli zapis zostanie przerwany, katalog może być częściowy; plik
podsumowanie.json powstaje na końcu i oznacza ukończoną analizę.

Zasady jakości:
- Kontrola schematu, braków, typów, zakresów, katalogu produktów i geografii.
- expected_rows określa oczekiwaną liczbę rekordów i dopuszczalny zakres ID.
- Duplikaty ID są wykrywane także pomiędzy partiami. Zachowywane jest pierwsze
  wystąpienie ID w pliku, kolejne są wykluczane, nawet jeśli pierwsze było błędne.
- Nieciągła kolejność ID jest raportowana, ale sama nie wyklucza wiersza.
- Agregacje obejmują wyłącznie poprawne, pierwsze wystąpienia rekordów.
- Suma ilość * cena jest sprawdzana w groszach. Sumy kwot są int64 w groszach;
  pliki grupowań zawierają także dokładne kolumny *_grosze.
- Histogram i kwantyle cen obejmują wszystkie poprawne rekordy, nie próbkę.
- Korelacje Pearsona liczone są z momentów całego poprawnego zbioru.
- Chi-kwadrat dotyczy poprawnych wierszy; p-value jest wyłącznie ilustracyjne:
  generator narzuca liczebności kolorów, a nie losuje niezależnych obserwacji.
- Brakujące ID i udziały kolorów w całym wejściu są sprawdzane oddzielnie.
- Błędna struktura CSV przerywa analizę; wiersze nie są po cichu pomijane.
- Założenia cenowe i mapa 48 miast są kopią konfiguracji generatora. Przy
  zmianie katalogu zaktualizuj CATALOG i GEOGRAPHY w tym pliku.
- Rekord jest pozycją syntetyczną, nie zamówieniem ani unikalnym klientem.

Dokumentacja:
https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html
https://numpy.org/doc/stable/reference/generated/numpy.bincount.html
https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.chisquare.html
"""

import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import platform
import sys
import time

try:
    import numpy as np
    import pandas as pd
    import scipy
    from scipy import stats
except ImportError as exc:
    raise ImportError("Zainstaluj numpy pandas scipy (w notebooku: %pip install numpy pandas scipy)") from exc

COLS = ["id", "nazwa", "ilość sztuk", "cena netto", "kolor", "miasto",
        "województwo", "kategoria", "wartość netto"]
COLORS = ["czerwony", "zielony", "czarny", "żółty", "inne"]
PERCENT = np.array([25, 25, 20, 10, 20], dtype=np.int64)
CATALOG = {'Opaska kablowa pojedyncza': ('Akcesoria elektroniczne', 1, 5),
 'Rezystor pojedynczy': ('Podzespoły elektroniczne', 1, 8),
 'Przewód USB podstawowy': ('Akcesoria elektroniczne', 5, 35),
 'Przewód USB-C premium': ('Akcesoria elektroniczne', 40, 180),
 'Ładowarka USB-C 65 W': ('Akcesoria elektroniczne', 60, 250),
 'Powerbank 20000 mAh': ('Akcesoria elektroniczne', 80, 350),
 'Mysz przewodowa': ('Peryferia komputerowe', 15, 80),
 'Mysz gamingowa premium': ('Peryferia komputerowe', 180, 750),
 'Klawiatura biurowa': ('Peryferia komputerowe', 30, 180),
 'Klawiatura mechaniczna premium': ('Peryferia komputerowe', 250, 1100),
 'Dysk SSD 1 TB': ('Podzespoły komputerowe', 180, 550),
 'Karta graficzna premium': ('Podzespoły komputerowe', 3500, 13000),
 'Monitor biurowy 24 cale': ('Komputery i monitory', 300, 850),
 'Monitor profesjonalny 32 cale': ('Komputery i monitory', 2200, 11000),
 'Laptop podstawowy': ('Komputery i monitory', 1100, 2600),
 'Laptop biznesowy': ('Komputery i monitory', 2800, 7500),
 'Laptop gamingowy premium': ('Komputery i monitory', 6500, 22000),
 'Stacja robocza profesjonalna': ('Komputery i monitory', 12000, 35000),
 'Smartfon podstawowy': ('Urządzenia mobilne', 250, 850),
 'Smartfon klasy średniej': ('Urządzenia mobilne', 900, 2300),
 'Smartfon flagowy': ('Urządzenia mobilne', 2800, 7500),
 'Tablet podstawowy': ('Urządzenia mobilne', 350, 1300),
 'Tablet profesjonalny': ('Urządzenia mobilne', 2500, 8500),
 'Smartwatch': ('Urządzenia mobilne', 150, 2400),
 'Słuchawki przewodowe': ('Audio i RTV', 15, 200),
 'Słuchawki bezprzewodowe premium': ('Audio i RTV', 450, 1800),
 'Głośnik Bluetooth': ('Audio i RTV', 60, 1200),
 'Soundbar premium': ('Audio i RTV', 1500, 6500),
 'Telewizor LED 43 cale': ('Audio i RTV', 850, 2300),
 'Telewizor OLED 65 cali': ('Audio i RTV', 3800, 14000),
 'Projektor kina domowego premium': ('Audio i RTV', 7000, 30000),
 'Router Wi-Fi': ('Sieci komputerowe', 70, 650),
 'System Wi-Fi mesh premium': ('Sieci komputerowe', 800, 3500),
 'Czajnik elektryczny podstawowy': ('Małe AGD', 35, 150),
 'Czajnik elektryczny premium': ('Małe AGD', 180, 900),
 'Toster': ('Małe AGD', 50, 450),
 'Blender ręczny': ('Małe AGD', 60, 500),
 'Robot kuchenny planetarny': ('Małe AGD', 350, 4500),
 'Ekspres przelewowy': ('Małe AGD', 80, 650),
 'Ekspres automatyczny premium': ('Małe AGD', 2500, 12000),
 'Frytkownica beztłuszczowa': ('Małe AGD', 180, 1500),
 'Żelazko parowe': ('Małe AGD', 60, 500),
 'Odkurzacz tradycyjny': ('Małe AGD', 180, 1100),
 'Robot sprzątający premium': ('Małe AGD', 1800, 6500),
 'Pralka podstawowa': ('Duże AGD', 1000, 2000),
 'Pralka premium': ('Duże AGD', 2800, 7500),
 'Suszarka z pompą ciepła': ('Duże AGD', 1500, 5500),
 'Lodówka z zamrażarką': ('Duże AGD', 1100, 3500),
 'Lodówka side-by-side premium': ('Duże AGD', 4500, 16000),
 'Zmywarka podstawowa': ('Duże AGD', 950, 2200),
 'Zmywarka premium': ('Duże AGD', 2600, 6500),
 'Piekarnik do zabudowy': ('Duże AGD', 900, 4500),
 'Płyta indukcyjna premium': ('Duże AGD', 2200, 8500),
 'Kuchenka mikrofalowa': ('Małe AGD', 200, 1500)}
GEOGRAPHY = {'Wrocław': 'dolnośląskie',
 'Legnica': 'dolnośląskie',
 'Wałbrzych': 'dolnośląskie',
 'Bydgoszcz': 'kujawsko-pomorskie',
 'Toruń': 'kujawsko-pomorskie',
 'Włocławek': 'kujawsko-pomorskie',
 'Lublin': 'lubelskie',
 'Chełm': 'lubelskie',
 'Zamość': 'lubelskie',
 'Gorzów Wielkopolski': 'lubuskie',
 'Zielona Góra': 'lubuskie',
 'Nowa Sól': 'lubuskie',
 'Łódź': 'łódzkie',
 'Piotrków Trybunalski': 'łódzkie',
 'Pabianice': 'łódzkie',
 'Kraków': 'małopolskie',
 'Tarnów': 'małopolskie',
 'Nowy Sącz': 'małopolskie',
 'Warszawa': 'mazowieckie',
 'Radom': 'mazowieckie',
 'Płock': 'mazowieckie',
 'Opole': 'opolskie',
 'Nysa': 'opolskie',
 'Brzeg': 'opolskie',
 'Rzeszów': 'podkarpackie',
 'Przemyśl': 'podkarpackie',
 'Krosno': 'podkarpackie',
 'Białystok': 'podlaskie',
 'Łomża': 'podlaskie',
 'Suwałki': 'podlaskie',
 'Gdańsk': 'pomorskie',
 'Gdynia': 'pomorskie',
 'Słupsk': 'pomorskie',
 'Katowice': 'śląskie',
 'Gliwice': 'śląskie',
 'Częstochowa': 'śląskie',
 'Kielce': 'świętokrzyskie',
 'Ostrowiec Świętokrzyski': 'świętokrzyskie',
 'Starachowice': 'świętokrzyskie',
 'Olsztyn': 'warmińsko-mazurskie',
 'Elbląg': 'warmińsko-mazurskie',
 'Ełk': 'warmińsko-mazurskie',
 'Poznań': 'wielkopolskie',
 'Kalisz': 'wielkopolskie',
 'Konin': 'wielkopolskie',
 'Szczecin': 'zachodniopomorskie',
 'Koszalin': 'zachodniopomorskie',
 'Świnoujście': 'zachodniopomorskie'}
GROUPS = {"produkty": ["nazwa", "kategoria"], "kategorie": ["kategoria"],
          "wojewodztwa": ["województwo"], "miasta": ["miasto", "województwo"],
          "kolory": ["kolor"]}


def liczba(series):
    return pd.to_numeric(series.str.strip().str.replace(",", ".", regex=False), errors="coerce").to_numpy(dtype=np.float64)


def calkowite(x, low, high):
    return np.isfinite(x) & (x >= low) & (x <= high) & (x == np.floor(x))


def kwoty(series, maximum):
    x = liczba(series)
    # Limit dwóch miejsc po separatorze; nie akceptuj notacji naukowej kwot.
    format_ok = series.str.fullmatch(r"[0-9]+(?:[.,][0-9]{1,2})?").to_numpy(dtype=bool)
    ok = format_ok & np.isfinite(x) & (x >= 0) & (x <= maximum)
    cents = np.rint(np.where(ok, x, 0) * 100).astype(np.int64)
    return cents, ok


class Moments:
    """Łączenie centralnych momentów partii; stabilniejsze niż E[X²]-E[X]²."""
    def __init__(self):
        self.n = 0
        self.mean = np.zeros(3)
        self.m2 = np.zeros((3, 3))

    def add(self, x):
        m = len(x)
        if not m:
            return
        mean = x.mean(axis=0)
        centered = x - mean
        delta = mean - self.mean
        total = self.n + m
        self.m2 += centered.T @ centered + np.outer(delta, delta) * (self.n * m / total)
        self.mean += delta * (m / total)
        self.n = total

    def correlation(self):
        den = np.sqrt(np.outer(np.diag(self.m2), np.diag(self.m2)))
        out = np.full((3, 3), np.nan)
        np.divide(self.m2, den, out=out, where=den > 0)
        return np.clip(out, -1, 1)


def polacz_grupy(old, new, keys):
    if old is None:
        return new
    return pd.concat([old, new], ignore_index=True).groupby(
        keys, observed=True, sort=False, as_index=False).agg(
            rekordy=("rekordy", "sum"), sztuki=("sztuki", "sum"),
            wartosc_grosze=("wartosc_grosze", "sum"), suma_cen_grosze=("suma_cen_grosze", "sum"),
            min_cena_grosze=("min_cena_grosze", "min"), max_cena_grosze=("max_cena_grosze", "max"))


def zapisz_csv(df, path):
    df.to_csv(path, sep=";", decimal=",", encoding="utf-8-sig", index=False, float_format="%.6f")


def kwantyle(hist):
    n = int(hist.sum())
    if n == 0:
        return {}
    cumulative = np.cumsum(hist)
    out = {}
    for q in [0, .01, .05, .25, .5, .75, .95, .99, 1]:
        pos = (n - 1) * q
        lo, hi = int(np.floor(pos)), int(np.ceil(pos))
        a, b = np.searchsorted(cumulative, [lo, hi], side="right")
        out[f"p{q*100:g}"] = float((a + (b - a) * (pos - lo)) / 100)
    return out


def analizuj(plik="dane_syntetyczne.csv", output=None, chunksize=250_000,
             expected_rows=5_000_000, error_sample=1000):
    """Zwraca słownik podsumowania; wszystkie raporty zapisuje w output."""
    if not isinstance(chunksize, int) or chunksize < 1:
        raise ValueError("chunksize musi być dodatnią liczbą całkowitą")
    if not isinstance(expected_rows, int) or not 1 <= expected_rows <= 100_000_000:
        raise ValueError("expected_rows musi należeć do 1..100000000")
    if not isinstance(error_sample, int) or error_sample < 0:
        raise ValueError("error_sample musi być nieujemną liczbą całkowitą")
    source = Path(plik).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Nie znaleziono CSV: {source}")
    # Walidacja nagłówka zanim utworzymy katalog wyników.
    options = dict(sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False,
                   na_filter=False, on_bad_lines="error", skip_blank_lines=False)
    header = pd.read_csv(source, nrows=0, **options)
    if list(header.columns) != COLS:
        raise ValueError(f"Oczekiwane kolumny w tej kolejności: {COLS}; otrzymano {list(header.columns)}")
    folder = Path(output) if output else Path("analiza_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    folder = folder.expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    seen = np.zeros(expected_rows + 1, dtype=bool)
    hist = np.zeros(3_500_001, dtype=np.int64)
    moments = Moments()
    groups = {name: None for name in GROUPS}
    quality = Counter()
    colors_input = Counter()
    bad_examples = []
    sample_count = rows = valid_rows = units = total_cents = 0
    categories = {k: v[0] for k, v in CATALOG.items()}
    lows = {k: v[1] * 100 for k, v in CATALOG.items()}
    highs = {k: v[2] * 100 for k, v in CATALOG.items()}
    print(f"Analiza: {source.name}; partie po {chunksize:,} rekordów", flush=True)
    with pd.read_csv(source, chunksize=chunksize, **options) as reader:
        for number, raw in enumerate(reader, 1):
            size = len(raw)
            checks = {}
            for col in COLS:
                checks[f"brak: {col}"] = raw[col].str.strip().eq("").to_numpy()
            ids = liczba(raw["id"])
            q = liczba(raw["ilość sztuk"])
            price, price_ok = kwoty(raw["cena netto"], 35000)
            value, value_ok = kwoty(raw["wartość netto"], 35 * 35000)
            id_ok = calkowite(ids, 1, expected_rows)
            quantity_ok = calkowite(q, 1, 35)
            quantity = np.where(quantity_ok, q, 0).astype(np.int64)
            checks["niepoprawne ID"] = ~id_ok
            checks["niepoprawna ilość"] = ~quantity_ok
            checks["niepoprawna cena"] = ~price_ok | (price < 100)
            checks["niepoprawna wartość netto"] = ~value_ok
            checks["wartość różna od ilość razy cena"] = value_ok & price_ok & quantity_ok & (value != price * quantity)
            checks["produkt spoza katalogu"] = ~raw["nazwa"].isin(CATALOG).to_numpy()
            checks["kategoria niezgodna z produktem"] = raw["kategoria"].ne(raw["nazwa"].map(categories)).to_numpy()
            checks["cena poza klasą produktu"] = (price < raw["nazwa"].map(lows).to_numpy()) | (price > raw["nazwa"].map(highs).to_numpy())
            checks["nieznany kolor"] = ~raw["kolor"].isin(COLORS).to_numpy()
            checks["miasto lub województwo spoza mapy"] = raw["województwo"].ne(raw["miasto"].map(GEOGRAPHY)).to_numpy()
            # np.unique wykrywa powtórzenia w partii; bitmapa między partiami.
            positions = np.flatnonzero(id_ok)
            integer_ids = ids[id_ok].astype(np.int64)
            unique_ids, first = np.unique(integer_ids, return_index=True)
            duplicates = np.zeros(size, dtype=bool)
            duplicates[positions] = True
            duplicates[positions[first]] = seen[unique_ids]
            seen[unique_ids] = True
            checks["powtórzone ID po pierwszym wystąpieniu"] = duplicates
            quality["ID niezgodne z numerem rekordu (informacyjnie)"] += int(np.count_nonzero(
                ids != np.arange(rows + 1, rows + size + 1)))
            valid = np.ones(size, dtype=bool)
            for reason, mask in checks.items():
                quality[reason] += int(mask.sum())
                valid &= ~mask
            count_bad = int((~valid).sum())
            quality["wykluczone rekordy (unikalne wiersze)"] += count_bad
            if count_bad and sample_count < error_sample:
                pos = np.flatnonzero(~valid)[: error_sample - sample_count]
                example = raw.iloc[pos].copy()
                example.insert(0, "numer_rekordu", rows + pos + 1)
                example["przyczyny"] = [" | ".join(k for k, m in checks.items() if m[i]) for i in pos]
                bad_examples.append(example)
                sample_count += len(example)
            colors_input.update(raw["kolor"].value_counts().to_dict())
            rows += size
            if valid.any():
                frame = raw.loc[valid, ["nazwa", "kategoria", "miasto", "województwo", "kolor"]].copy()
                for col in frame.columns:
                    frame[col] = frame[col].astype("category")
                frame["sztuki"] = quantity[valid]
                frame["cena_grosze"] = price[valid]
                frame["wartosc_grosze"] = value[valid]
                valid_rows += len(frame)
                units += int(quantity[valid].sum())
                total_cents += int(value[valid].sum())
                hist += np.bincount(price[valid], minlength=len(hist))
                moments.add(np.column_stack((quantity[valid], price[valid] / 100, value[valid] / 100)))
                for name, keys in GROUPS.items():
                    batch = frame.groupby(keys, observed=True, sort=False, as_index=False).agg(
                        rekordy=("sztuki", "size"), sztuki=("sztuki", "sum"),
                        wartosc_grosze=("wartosc_grosze", "sum"), suma_cen_grosze=("cena_grosze", "sum"),
                        min_cena_grosze=("cena_grosze", "min"), max_cena_grosze=("cena_grosze", "max"))
                    # Wspólne kategorie między partiami nie są wymagane.
                    for key in keys:
                        batch[key] = batch[key].astype(str)
                    groups[name] = polacz_grupy(groups[name], batch, keys)
            if number == 1 or number % 4 == 0:
                seconds = time.perf_counter() - started
                print(f"Wczytano {rows:,}; poprawne {valid_rows:,}; {rows/max(seconds,.001):,.0f} rekordów/s", flush=True)
    quality["brakujące ID w oczekiwanym zakresie"] = expected_rows - int(seen.sum())
    quality["różnica liczby rekordów względem oczekiwanej (wartość bezwzględna)"] = abs(rows - expected_rows)
    summary_groups = {}
    color_valid = np.zeros(5, dtype=np.int64)
    for name, keys in GROUPS.items():
        table = groups[name]
        if table is None:
            table = pd.DataFrame(columns=keys + ["rekordy", "sztuki", "wartosc_grosze", "suma_cen_grosze", "min_cena_grosze", "max_cena_grosze"])
        if len(table):
            table = table.sort_values("wartosc_grosze", ascending=False, kind="stable").reset_index(drop=True)
            table["wartosc_netto_PLN"] = table["wartosc_grosze"] / 100
            table["srednia_cena_netto_PLN"] = table["suma_cen_grosze"] / table["rekordy"] / 100
            table["srednia_cena_wazona_sztukami_PLN"] = table["wartosc_grosze"] / table["sztuki"] / 100
            table["udzial_wartosci_proc"] = table["wartosc_grosze"] / total_cents * 100
            table["skumulowany_udzial_proc"] = table["udzial_wartosci_proc"].cumsum()
            if name == "kolory":
                color_valid = table.set_index("kolor")["rekordy"].reindex(COLORS, fill_value=0).to_numpy(dtype=np.int64)
            summary_groups[name + "_top5"] = table.head(5).to_dict(orient="records")
        zapisz_csv(table, folder / f"{name}.csv")
    # Kolory wejścia sprawdzamy względem dokładnych liczebności generatora.
    target = rows * PERCENT // 100
    remainder_order = np.argsort(-(rows * PERCENT % 100), kind="stable")
    target[remainder_order[: rows - int(target.sum())]] += 1
    observed = np.array([colors_input[c] for c in COLORS], dtype=np.int64)
    color_diagnostic = {
        "wejscie": dict(zip(COLORS, observed.tolist())),
        "cel_dla_liczby_wierszy_wejscia": dict(zip(COLORS, target.tolist())),
        "roznica": dict(zip(COLORS, (observed - target).tolist())),
        "dokladna_zgodnosc": bool(np.array_equal(observed, target)),
        "chi2_poprawne_wiersze": None, "p_value_ilustracyjne": None,
        "uwaga": "Generator narzuca liczebności; p-value nie dowodzi losowości. Dla małych liczebności oczekiwanych test jest pomijany.",
    }
    if valid_rows and np.min(valid_rows * PERCENT / 100) >= 5:
        chi = stats.chisquare(color_valid, f_exp=valid_rows * PERCENT / 100)
        color_diagnostic.update(chi2_poprawne_wiersze=float(chi.statistic), p_value_ilustracyjne=float(chi.pvalue))
    # Zagregowany histogram do raportu; dokładny histogram groszowy zostaje w RAM.
    edges = np.array([0, 100, 500, 1000, 2500, 5000, 10000, 20000, 35000.01])
    counts = [int(hist[int(round(a*100)):int(round(b*100))].sum()) for a, b in zip(edges[:-1], edges[1:])]
    zapisz_csv(pd.DataFrame({"od_PLN_wlacznie": edges[:-1], "do_PLN_wylacznie": edges[1:], "rekordy": counts}), folder / "histogram_cen.csv")
    corr_names = ["ilość sztuk", "cena netto", "wartość netto"]
    corr = pd.DataFrame(moments.correlation(), columns=corr_names)
    corr.insert(0, "zmienna", corr_names)
    zapisz_csv(corr, folder / "korelacje.csv")
    zapisz_csv(pd.DataFrame(quality.items(), columns=["kontrola", "liczba"]), folder / "jakosc.csv")
    errors = pd.concat(bad_examples, ignore_index=True) if bad_examples else pd.DataFrame(columns=["numer_rekordu"] + COLS + ["przyczyny"])
    zapisz_csv(errors, folder / "bledne_wiersze_probka.csv")
    result = {
        "plik": str(source), "katalog_wynikow": str(folder), "liczba_wierszy": rows,
        "oczekiwana_liczba_wierszy": expected_rows, "poprawne_wiersze": valid_rows,
        "wykluczone_wiersze": rows - valid_rows, "suma_sztuk": units,
        "wartosc_netto_grosze": total_cents, "wartosc_netto_PLN": total_cents / 100,
        "srednia_cena_netto_PLN": float(moments.mean[1]) if valid_rows else None,
        "odchylenie_standardowe_ceny_probkowe": float(np.sqrt(moments.m2[1, 1] / (valid_rows - 1))) if valid_rows > 1 else None,
        "srednia_cena_wazona_sztukami_PLN": total_cents / units / 100 if units else None,
        "kwantyle_ceny_PLN_dokladne": kwantyle(hist), "kolory": color_diagnostic,
        "jakosc": dict(quality), "liczba_przykladow_bledow": sample_count,
        "top5": summary_groups, "czas_sekundy": round(time.perf_counter() - started, 3),
        "wersje": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__, "scipy": scipy.__version__},
        "metoda": "Jeden przebieg; agregacje po poprawnych pierwszych wystąpieniach ID; dokładne kwoty w groszach; kwantyle z histogramu pełnego zbioru.",
        "uwaga": "Kontrole jakości mogą się nakładać. Brakujące ID liczone po wszystkich poprawnych numerycznie ID, także w błędnych wierszach. Pusta korelacja oznacza brak danych lub zerową wariancję.",
    }
    formatted_amount = f"{total_cents // 100:,}".replace(",", " ") + f",{total_cents % 100:02d}"
    text = (f"ANALIZA DANYCH SYNTETYCZNYCH\n\nWiersze: {rows:,}\nPoprawne: {valid_rows:,}\n"
            f"Wykluczone: {rows-valid_rows:,}\nSuma sztuk: {units:,}\n"
            f"Wartość netto: {formatted_amount} PLN\n"
            f"Dokładna zgodność kolorów: {color_diagnostic['dokladna_zgodnosc']}\n"
            f"Czas: {result['czas_sekundy']} s\n\n{result['metoda']}\n{result['uwaga']}\n"
            "Raporty obejmują dane syntetyczne, nie rzeczywistą sprzedaż.\n")
    (folder / "podsumowanie.txt").write_text(text, encoding="utf-8")
    (folder / "podsumowanie.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(text + f"\nWyniki: {folder}", flush=True)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Analiza 5 mln wierszy CSV partiami: NumPy, pandas, SciPy.")
    parser.add_argument("plik", nargs="?", default="dane_syntetyczne.csv")
    parser.add_argument("--output", help="Nowy katalog raportów")
    parser.add_argument("--chunksize", type=int, default=250_000)
    parser.add_argument("--expected-rows", type=int, default=5_000_000)
    parser.add_argument("--error-sample", type=int, default=1000)
    args = parser.parse_args([] if argv is None and "__file__" not in globals() else argv)
    try:
        analizuj(args.plik, args.output, args.chunksize, args.expected_rows, args.error_sample)
        return 0
    except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        print(f"Błąd: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Przerwano analizę; katalog wyników może być niekompletny.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    if "__file__" not in globals():
        print('Gotowe. Uruchom: wynik = analizuj("dane_syntetyczne.csv")')
    else:
        raise SystemExit(main())
