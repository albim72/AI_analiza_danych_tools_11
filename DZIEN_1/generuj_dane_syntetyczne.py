#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generator 5 000 000 syntetycznych pozycji elektroniki i AGD do CSV.

Wymagania: Python 3.10+ oraz biblioteka Faker:
    python -m pip install Faker

Uruchomienie (domyślnie 5 mln wierszy):
    python generuj_dane_syntetyczne.py
Próba na mniejszej liczbie wierszy:
    python generuj_dane_syntetyczne.py --n 10000 --output proba.csv
Inne opcje:
    python generuj_dane_syntetyczne.py --seed 123 --batch-size 50000

CSV: UTF-8 z BOM, separator średnik, przecinek dziesiętny, ceny w PLN.
Cena netto jest ceną jednej sztuki; wartość netto = ilość * cena netto.
Zakresy cen są założeniami edukacyjnymi, a nie aktualnym cennikiem rynkowym.
Kolory: czerwony 25%, zielony 25%, czarny 20%, żółty 10%, inne 20%.
„-25%” dla zielonego zinterpretowano jako omyłkowo zapisane 25%.
„inne” jest jedną zbiorczą etykietą. Kolory losujemy niezależnie od produktu.
Udziały są dokładne dla n podzielnego przez 20; dla innych n stosowane jest
zaokrąglenie metodą największych reszt (błąd poniżej jednego wiersza).

Faker('pl_PL').city() i administrative_unit() budują niewielką pulę nazw.
Jawna mapa miast przypisuje im właściwe województwa, bo niezależne wywołania
tych dwóch metod nie gwarantują zgodności geograficznej. Używamy 48 miast,
po 3 na województwo; nie jest to rozkład odpowiadający liczbie mieszkańców.
Pula lokalizacji jest używana wielokrotnie, aby przyspieszyć duży eksport.

Zapis partiami nie przechowuje całego zbioru w RAM. Plik może zajmować
kilkaset MB. Excel nie pomieści 5 mln wierszy w pojedynczym arkuszu;
do pełnej analizy użyj np. Power BI, bazy danych lub Pythona.
Istniejący plik nie zostanie nadpisany. Przerwany zapis pozostawia częściowy
plik do ręcznego usunięcia. Ten sam seed odtwarza wynik przy tej samej
wersji Pythona, Faker i skryptu.
Dokumentacja Faker: https://faker.readthedocs.io/en/stable/locales/pl_PL.html
"""

import argparse
import csv
import random
import sys
import time
from pathlib import Path

try:
    from faker import Faker
except ImportError:
    raise SystemExit("Brak Faker. Zainstaluj: python -m pip install Faker")


N = 5_000_000
KOLUMNY = (
    "id", "nazwa", "ilość sztuk", "cena netto", "kolor", "miasto",
    "województwo", "kategoria", "wartość netto",
)
KOLORY = ("czerwony", "zielony", "czarny", "żółty", "inne")
PROCENTY = (25, 25, 20, 10, 20)

# Nazwa, kategoria, dolna i górna granica ceny jednostkowej netto w PLN.
# Klasa produktu jest zawarta w nazwie. Losujemy równomiernie po katalogu.
PRODUKTY = (
    ("Opaska kablowa pojedyncza", "Akcesoria elektroniczne", 1, 5),
    ("Rezystor pojedynczy", "Podzespoły elektroniczne", 1, 8),
    ("Przewód USB podstawowy", "Akcesoria elektroniczne", 5, 35),
    ("Przewód USB-C premium", "Akcesoria elektroniczne", 40, 180),
    ("Ładowarka USB-C 65 W", "Akcesoria elektroniczne", 60, 250),
    ("Powerbank 20000 mAh", "Akcesoria elektroniczne", 80, 350),
    ("Mysz przewodowa", "Peryferia komputerowe", 15, 80),
    ("Mysz gamingowa premium", "Peryferia komputerowe", 180, 750),
    ("Klawiatura biurowa", "Peryferia komputerowe", 30, 180),
    ("Klawiatura mechaniczna premium", "Peryferia komputerowe", 250, 1100),
    ("Dysk SSD 1 TB", "Podzespoły komputerowe", 180, 550),
    ("Karta graficzna premium", "Podzespoły komputerowe", 3500, 13000),
    ("Monitor biurowy 24 cale", "Komputery i monitory", 300, 850),
    ("Monitor profesjonalny 32 cale", "Komputery i monitory", 2200, 11000),
    ("Laptop podstawowy", "Komputery i monitory", 1100, 2600),
    ("Laptop biznesowy", "Komputery i monitory", 2800, 7500),
    ("Laptop gamingowy premium", "Komputery i monitory", 6500, 22000),
    ("Stacja robocza profesjonalna", "Komputery i monitory", 12000, 35000),
    ("Smartfon podstawowy", "Urządzenia mobilne", 250, 850),
    ("Smartfon klasy średniej", "Urządzenia mobilne", 900, 2300),
    ("Smartfon flagowy", "Urządzenia mobilne", 2800, 7500),
    ("Tablet podstawowy", "Urządzenia mobilne", 350, 1300),
    ("Tablet profesjonalny", "Urządzenia mobilne", 2500, 8500),
    ("Smartwatch", "Urządzenia mobilne", 150, 2400),
    ("Słuchawki przewodowe", "Audio i RTV", 15, 200),
    ("Słuchawki bezprzewodowe premium", "Audio i RTV", 450, 1800),
    ("Głośnik Bluetooth", "Audio i RTV", 60, 1200),
    ("Soundbar premium", "Audio i RTV", 1500, 6500),
    ("Telewizor LED 43 cale", "Audio i RTV", 850, 2300),
    ("Telewizor OLED 65 cali", "Audio i RTV", 3800, 14000),
    ("Projektor kina domowego premium", "Audio i RTV", 7000, 30000),
    ("Router Wi-Fi", "Sieci komputerowe", 70, 650),
    ("System Wi-Fi mesh premium", "Sieci komputerowe", 800, 3500),
    ("Czajnik elektryczny podstawowy", "Małe AGD", 35, 150),
    ("Czajnik elektryczny premium", "Małe AGD", 180, 900),
    ("Toster", "Małe AGD", 50, 450),
    ("Blender ręczny", "Małe AGD", 60, 500),
    ("Robot kuchenny planetarny", "Małe AGD", 350, 4500),
    ("Ekspres przelewowy", "Małe AGD", 80, 650),
    ("Ekspres automatyczny premium", "Małe AGD", 2500, 12000),
    ("Frytkownica beztłuszczowa", "Małe AGD", 180, 1500),
    ("Żelazko parowe", "Małe AGD", 60, 500),
    ("Odkurzacz tradycyjny", "Małe AGD", 180, 1100),
    ("Robot sprzątający premium", "Małe AGD", 1800, 6500),
    ("Pralka podstawowa", "Duże AGD", 1000, 2000),
    ("Pralka premium", "Duże AGD", 2800, 7500),
    ("Suszarka z pompą ciepła", "Duże AGD", 1500, 5500),
    ("Lodówka z zamrażarką", "Duże AGD", 1100, 3500),
    ("Lodówka side-by-side premium", "Duże AGD", 4500, 16000),
    ("Zmywarka podstawowa", "Duże AGD", 950, 2200),
    ("Zmywarka premium", "Duże AGD", 2600, 6500),
    ("Piekarnik do zabudowy", "Duże AGD", 900, 4500),
    ("Płyta indukcyjna premium", "Duże AGD", 2200, 8500),
    ("Kuchenka mikrofalowa", "Małe AGD", 200, 1500),
)

MIASTA_REGIONY = {
    "dolnośląskie": ("Wrocław", "Legnica", "Wałbrzych"),
    "kujawsko-pomorskie": ("Bydgoszcz", "Toruń", "Włocławek"),
    "lubelskie": ("Lublin", "Chełm", "Zamość"),
    "lubuskie": ("Gorzów Wielkopolski", "Zielona Góra", "Nowa Sól"),
    "łódzkie": ("Łódź", "Piotrków Trybunalski", "Pabianice"),
    "małopolskie": ("Kraków", "Tarnów", "Nowy Sącz"),
    "mazowieckie": ("Warszawa", "Radom", "Płock"),
    "opolskie": ("Opole", "Nysa", "Brzeg"),
    "podkarpackie": ("Rzeszów", "Przemyśl", "Krosno"),
    "podlaskie": ("Białystok", "Łomża", "Suwałki"),
    "pomorskie": ("Gdańsk", "Gdynia", "Słupsk"),
    "śląskie": ("Katowice", "Gliwice", "Częstochowa"),
    "świętokrzyskie": ("Kielce", "Ostrowiec Świętokrzyski", "Starachowice"),
    "warmińsko-mazurskie": ("Olsztyn", "Elbląg", "Ełk"),
    "wielkopolskie": ("Poznań", "Kalisz", "Konin"),
    "zachodniopomorskie": ("Szczecin", "Koszalin", "Świnoujście"),
}


def pula_lokalizacji(fake):
    """Pobierz nazwy z Faker i połącz je zgodnie z mapą geograficzną."""
    mapa = {miasto: woj for woj, miasta in MIASTA_REGIONY.items() for miasto in miasta}
    miasta = set()
    regiony = set()
    for _ in range(50_000):
        miasto = fake.city()
        woj = "".join(fake.administrative_unit().lower().split())
        if miasto in mapa:
            miasta.add(miasto)
        if woj in MIASTA_REGIONY:
            regiony.add(woj)
        if len(miasta) == len(mapa) and len(regiony) == len(MIASTA_REGIONY):
            break
    brakujace = sorted(set(mapa) - miasta)
    if brakujace or len(regiony) != 16:
        raise RuntimeError(
            "Faker nie dostarczył wszystkich nazw z mapy. "
            f"Brakujące miasta: {brakujace}; regiony: {sorted(set(MIASTA_REGIONY) - regiony)}. "
            "Sprawdź wersję Faker lub dostosuj mapę miast."
        )
    return tuple((miasto, mapa[miasto]) for miasto in sorted(miasta))


def liczebnosci_kolorow(n):
    liczby = [n * procent // 100 for procent in PROCENTY]
    kolejnosc = sorted(range(len(PROCENTY)), key=lambda i: -(n * PROCENTY[i] % 100))
    for indeks in kolejnosc[: n - sum(liczby)]:
        liczby[indeks] += 1
    return liczby


def kwota(grosze):
    """Dokładny zapis do dwóch miejsc, bez błędów arytmetyki float."""
    return f"{grosze // 100},{grosze % 100:02d}"


def generuj(n=N, output=Path("dane_syntetyczne.csv"), seed=42, batch_size=50_000):
    if n < 1 or batch_size < 1:
        raise ValueError("n i batch_size muszą być dodatnie")
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"Plik już istnieje: {output}. Wybierz inną nazwę.")
    fake = Faker("pl_PL")
    fake.seed_instance(seed)
    lokalizacje = pula_lokalizacji(fake)
    rng = random.Random(seed)
    docelowe = liczebnosci_kolorow(n)
    pozostale = docelowe.copy()
    katalog = tuple((nazwa, kategoria, dol * 100, gora * 100)
                    for nazwa, kategoria, dol, gora in PRODUKTY)
    start = time.perf_counter()
    output.parent.mkdir(parents=True, exist_ok=True)
    print(f"Zapis {n:,} wierszy do: {output.resolve()}", flush=True)
    # Tryb x dodatkowo chroni przed nadpisaniem pliku utworzonego w międzyczasie.
    with output.open("x", encoding="utf-8-sig", newline="", buffering=1024 * 1024) as plik:
        writer = csv.writer(plik, delimiter=";", lineterminator="\n")
        writer.writerow(KOLUMNY)
        for poczatek in range(1, n + 1, batch_size):
            koniec = min(poczatek + batch_size, n + 1)
            partia = []
            for identyfikator in range(poczatek, koniec):
                nazwa, kategoria, minimum, maksimum = rng.choice(katalog)
                ilosc = rng.randint(1, 35)
                cena = rng.randint(minimum, maksimum)
                miasto, woj = rng.choice(lokalizacje)
                # Losowanie bez zwracania z puli liczników: dokładne udziały
                # i losowa kolejność, bez tablicy 5 mln kolorów w pamięci.
                los = rng.randrange(n - identyfikator + 1)
                for indeks, liczba in enumerate(pozostale):
                    if los < liczba:
                        pozostale[indeks] -= 1
                        kolor = KOLORY[indeks]
                        break
                    los -= liczba
                partia.append((identyfikator, nazwa, ilosc, kwota(cena), kolor,
                               miasto, woj, kategoria, kwota(ilosc * cena)))
            writer.writerows(partia)
            zapisano = koniec - 1
            if zapisano == n or (poczatek - 1) // 500_000 < zapisano // 500_000:
                czas = time.perf_counter() - start
                print(f"{zapisano:,}/{n:,} ({100 * zapisano / n:.1f}%) | "
                      f"{zapisano / max(czas, 0.001):,.0f} wierszy/s", flush=True)
    print(f"Gotowe. Rozmiar: {output.stat().st_size / 1024**2:.1f} MiB")
    print("Liczebności kolorów: " + ", ".join(
        f"{kolor}: {liczba:,}" for kolor, liczba in zip(KOLORY, docelowe)))
    return output


def dodatnia(text):
    wartosc = int(text)
    if wartosc < 1:
        raise argparse.ArgumentTypeError("Wartość musi być większa od zera")
    return wartosc


def main():
    parser = argparse.ArgumentParser(description="Generator syntetycznych danych elektroniki i AGD.")
    parser.add_argument("--n", type=dodatnia, default=N, help="Liczba wierszy (domyślnie 5000000)")
    parser.add_argument("--output", type=Path, default=Path("dane_syntetyczne.csv"), help="Plik wyjściowy")
    parser.add_argument("--seed", type=int, default=42, help="Ziarno generatora (domyślnie 42)")
    parser.add_argument("--batch-size", type=dodatnia, default=50_000, help="Liczba wierszy w partii")
    args = parser.parse_args()
    try:
        generuj(args.n, args.output, args.seed, args.batch_size)
    except (OSError, ValueError, RuntimeError) as blad:
        print(f"Błąd: {blad}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nPrzerwano. Plik może zawierać tylko część danych.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
