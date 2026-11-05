# 5 zadań: analiza danych z Claude — LAB

Nov 5, 2026 · @Marcin

## Jak używać zestawu

Pięć zadań laboratoryjnych prowadzi uczestnika od profilowania surowych danych do raportu dla zarządu, z Claude jako asystentem analityka. Wszystkie działają na jednym zbiorze danych z celowo wbudowanymi błędami, więc odpowiedzi Claude da się sprawdzić z kluczem na końcu dokumentu.

**Dane: sklep internetowy „Ziarno” (kawa i akcesoria), styczeń 2024 – wrzesień 2026.** Trzy pliki CSV w układzie gwiazdy: `zamowienia.csv` (fakty), `klienci.csv` i `produkty.csv` (wymiary). Zbiór zawiera duplikaty, braki, niespójne nazwy województw, zwroty z ujemną ilością, błędy cenowe, sezonowość i dwutygodniową awarię sklepu.

**Wymagania:** konto Claude z włączonym tworzeniem i analizą plików (wykonywanie kodu), Power BI Desktop, SQL Server Developer lub SQLite, Python z pandas.

| Zadanie | Temat | Moduł programu | Czas |
| --- | --- | --- | --- |
| 1 | Profilowanie i EDA, weryfikacja halucynacji | 1, 2, 4 | 45 min |
| 2 | SQL z opisu struktury danych | 2, 5 | 45 min |
| 3 | Miary DAX i debugowanie kontekstu | 2, 5, 6 | 50 min |
| 4 | Python: statystyka, szereg czasowy, anomalie | 3, 4, 7 | 60 min |
| 5 | Projekt końcowy: segmentacja, prognoza, storytelling | 3, 7, 8 | 90 min |

**Zasada wspólna dla wszystkich zadań:** każdą liczbę podaną przez Claude uczestnik potwierdza drugą drogą (Power BI, SQL, własny kod lub poproszenie Claude o pokazanie wykonanego kodu). To ćwiczy moduł 1: halucynacje i ich zapobieganie.

## Zadanie 1. Profilowanie danych i EDA z weryfikacją halucynacji

**Cel:** uczestnik zleca Claude profil trzech plików, dostaje listę problemów z jakością danych i sprawdza, które liczby są policzone, a które zgadnięte.

**Funkcje Claude:** wgrywanie plików, wykonywanie kodu Python (analiza plików), porównanie odpowiedzi z włączonym i wyłączonym rozszerzonym myśleniem.

**Kroki**

1. **Prompt bez danych (test halucynacji).** Zanim wgrasz pliki, zapytaj: „Ile duplikatów jest w moim pliku zamowienia.csv?”. Zanotuj, czy Claude odmówi, czy poda liczbę.
2. **Prompt słaby.** Wgraj trzy pliki i napisz tylko: „przeanalizuj te dane”. Zapisz, co dostałeś.
3. **Prompt ustrukturyzowany.** Nowa rozmowa, te same pliki, prompt poniżej.
4. **Weryfikacja.** Poproś: „Pokaż kod, którym policzyłeś liczbę duplikatów i braków”. Uruchom ten kod lokalnie albo sprawdź wynik w Power Query (Profil kolumny).
5. **Porównaj** wyniki kroków 2 i 3 z kluczem trenera. Zapisz, które problemy Claude wykrył sam, a które przeoczył.

**Prompt startowy (krok 3)**

```text
<rola>Jesteś analitykiem danych przygotowującym dane do raportu sprzedaży w Power BI.</rola>

<dane>
Załączone pliki: zamowienia.csv (fakty, jedna linia = pozycja zamówienia),
klienci.csv i produkty.csv (wymiary). Okres: 2024-01 do 2026-09.
Wartość pozycji = ilosc * cena_jedn * (1 - rabat_proc/100).
</dane>

<zadanie>
1. Wczytaj pliki kodem i podaj profil każdej kolumny: typ, braki, wartości unikalne, min/max.
2. Sprawdź jakość: duplikaty, braki, wartości odstające, niespójne kategorie,
   spójność dat między tabelami, klucze bez dopasowania.
3. Dla każdego problemu zaproponuj regułę czyszczenia i oceń jej wpływ na przychód.
</zadanie>

<zasady>
- Każdą liczbę licz kodem; nie szacuj.
- Jeśli czegoś nie da się ustalić z danych, napisz „nie wiem”.
- Nie usuwaj danych, tylko je oznacz.
</zasady>

<format>Tabela problemów: problem | liczba wierszy | przykład | reguła | wpływ na przychód (PLN).</format>
```

**Kryteria sukcesu:** wykryte co najmniej 6 z 8 wbudowanych problemów (lista w kluczu), każda liczba ma pokazany kod, uczestnik umie wskazać różnicę między krokiem 2 a 3.

**Pułapka do omówienia:** `id_zamowienia` nie jest kluczem, bo jedno zamówienie ma kilka linii. Jeśli Claude policzy duplikaty po samym `id_zamowienia`, dostanie ok. 22 tys. „duplikatów” zamiast 37. To dobry przykład błędu złego założenia, a nie halucynacji.

**Rozszerzenie:** poproś Claude o skrypt Power Query (M), który stosuje zaproponowane reguły, i wklej go do Power BI.

## Zadanie 2. SQL z opisu struktury danych

**Cel:** uczestnik przekazuje Claude wyłącznie schemat i słownik biznesowy (bez danych), dostaje zapytania T-SQL, a potem znajduje błędy w gotowym zapytaniu.

**Funkcje Claude:** Projekt z wiedzą projektu (schemat wgrany raz, używany w wielu rozmowach), objaśnianie i debugowanie kodu.

**Kroki**

1. Załaduj trzy pliki CSV do SQL Server (kreator importu) lub SQLite.
2. Utwórz w Claude Projekt „Ziarno – SQL” i wklej do instrukcji projektu blok `<schemat>` z promptu poniżej. Dzięki temu nie powtarzasz struktury w każdej rozmowie.
3. W nowej rozmowie w projekcie zamów kolejno cztery zapytania (lista w prompcie). Każde uruchom i porównaj z kluczem.
4. **Debugowanie.** Wklej zapytanie z błędami (niżej) i poproś: „Wyjaśnij krok po kroku, co liczy to zapytanie, i wskaż błędy, które zafałszują wynik”.
5. Sprawdź, ilu z czterech błędów Claude znalazł bez podpowiedzi.

**Prompt startowy**

```text
<schemat>
CREATE TABLE produkty (id_produktu VARCHAR(10) PRIMARY KEY, nazwa NVARCHAR(100),
  kategoria NVARCHAR(50), cena_katalogowa DECIMAL(10,2), koszt_jedn DECIMAL(10,2));
CREATE TABLE klienci (id_klienta VARCHAR(10) PRIMARY KEY, data_rejestracji DATE,
  wojewodztwo NVARCHAR(50), segment VARCHAR(3), wiek DECIMAL(4,1));
CREATE TABLE zamowienia (id_zamowienia VARCHAR(10), data DATE, id_klienta VARCHAR(10),
  id_produktu VARCHAR(10), ilosc INT, cena_jedn DECIMAL(10,2), rabat_proc DECIMAL(5,2),
  kanal VARCHAR(10));
</schemat>

<slownik>
- Jedna linia zamowienia = jeden produkt w zamówieniu; zamówienie ma 1-3 linie.
- Ujemna ilosc = zwrot. rabat_proc NULL oznacza brak rabatu (0%).
- Przychód netto = ilosc * cena_jedn * (1 - rabat_proc/100).
- Marża = przychód netto - ilosc * koszt_jedn.
- wojewodztwo ma niespójną pisownię (wielkość liter, spacje, brak polskich znaków).
- Dane zawierają duplikaty całych wierszy.
</slownik>

<zasady>Dialekt T-SQL. Używaj CTE. Komentarz nad każdym krokiem.
Nie zgaduj nazw kolumn spoza schematu.</zasady>

Zapytania:
1. Widok v_zamowienia_czyste: bez duplikatów, z ujednoliconym województwem
   i kolumną przychod_netto.
2. Przychód netto i liczba zamówień miesięcznie, z osobną kolumną zwrotów.
3. Top 5 produktów według marży w 2025 roku.
4. RFM dla każdego klienta na dzień 2026-10-01 (recency w dniach,
   liczba zamówień, wartość) z podziałem na kwintyle NTILE(5).
```

**Zapytanie z błędami (krok 4)**

```sql
SELECT k.wojewodztwo,
       COUNT(z.id_zamowienia) AS liczba_zamowien,
       SUM(z.ilosc * z.cena_jedn * (1 - z.rabat_proc / 100)) AS przychod
FROM zamowienia z
JOIN klienci k ON z.id_klienta = k.id_klienta
WHERE YEAR(z.data) = 2025
GROUP BY k.wojewodztwo
ORDER BY przychod DESC;
```

**Kryteria sukcesu:** cztery zapytania działają bez ręcznych poprawek albo uczestnik wie, dlaczego wymagały poprawki; w kroku 4 wskazane wszystkie cztery błędy.

**Pułapka do omówienia:** błąd z `NULL` w rabacie nie daje komunikatu. Zapytanie działa i zwraca wiarygodnie wyglądające liczby, tylko o 80 tys. PLN za niskie. Warto też zapytać grupę, co by się stało, gdyby `rabat_proc` było typu `INT` (dzielenie całkowite w T-SQL: 15/100 = 0).

**Rozszerzenie:** zamów analizę kohortową (miesiąc pierwszego zakupu × retencja po 1, 3 i 6 miesiącach) i poproś Claude o wskazanie, które założenia przyjął.

## Zadanie 3. Miary DAX w Power BI i debugowanie kontekstu

**Cel:** uczestnik opisuje Claude model danych Power BI, dostaje tabelę kalendarza i zestaw miar, a następnie naprawia trzy miary dające błędne wyniki.

**Funkcje Claude:** rozszerzone myślenie (dla miar z analizą czasu), objaśnianie kodu, opis modelu przekazany jako tekst.

**Kroki**

1. Zaimportuj trzy pliki CSV do Power BI Desktop. **Przy imporcie ustaw ustawienia regionalne na angielski (USA).** W polskich ustawieniach kropka dziesiętna może zostać odczytana jako separator tysięcy i cena 49.0 zamieni się w 490.
2. Utwórz relacje: `zamowienia[id_klienta]` → `klienci`, `zamowienia[id_produktu]` → `produkty`.
3. Wyślij prompt poniżej. Wklej tabelę `Kalendarz`, oznacz ją jako tabelę dat i połącz z `zamowienia[data]`.
4. Dodaj miary i zbuduj macierz: kategoria × rok. Porównaj wartości z kluczem.
5. **Debugowanie.** Wklej trzy błędne definicje (niżej) wraz z opisem objawu i poproś o diagnozę oraz poprawkę.

**Prompt startowy**

```text
<model>
Tabele w Power BI:
- zamowienia: id_zamowienia, data, id_klienta, id_produktu, ilosc, cena_jedn,
  rabat_proc (puste = brak rabatu), kanal. Jedna linia = jeden produkt w zamówieniu.
  Ujemna ilosc = zwrot.
- klienci: id_klienta, data_rejestracji, wojewodztwo, segment (B2C/B2B), wiek
- produkty: id_produktu, nazwa, kategoria, cena_katalogowa, koszt_jedn
Relacje: wiele-do-jednego z zamowienia do klienci i produkty, filtr jednokierunkowy.
Zakres dat: 2024-01-01 do 2026-09-30.
</model>

<zadanie>
1. Tabela Kalendarz w DAX (rok, kwartał, miesiąc, nazwa miesiąca po polsku,
   numer tygodnia ISO).
2. Miary: Przychód netto, Marża, Liczba zamówień, Średnia wartość zamówienia,
   Przychód PY, Zmiana r/r %, Przychód YTD, Udział kategorii % w wybranym okresie,
   Ranking produktu w kategorii, Wskaźnik zwrotów %.
</zadanie>

<zasady>
- Przychód licz przez SUMX po wierszach, nie przez kolumnę obliczeniową.
- Dziel przez DIVIDE.
- Pod każdą miarą jedno zdanie: jaki kontekst filtra modyfikuje i dlaczego.
- Jeśli miara wymaga założenia, nazwij je wprost.
</zasady>
```

**Trzy błędne definicje (krok 5)**

```text
-- 1. Kolumna obliczeniowa w tabeli klienci. Objaw: każdy klient ma tę samą wartość.
Wartość klienta = SUMX(zamowienia, zamowienia[ilosc] * zamowienia[cena_jedn])

-- 2. Objaw: przy fragmentatorze Rok = 2025 udziały kategorii sumują się do ok. 37%, nie do 100%.
Udział % = DIVIDE([Przychód netto], CALCULATE([Przychód netto], ALL(zamowienia)))

-- 3. Objaw: średnia wartość zamówienia w 2025 wynosi ok. 211 zł, a dział sprzedaży podaje ok. 350 zł.
Średnia wartość zamówienia = AVERAGEX(zamowienia, zamowienia[ilosc] * zamowienia[cena_jedn] * (1 - zamowienia[rabat_proc] / 100))
```

**Kryteria sukcesu:** Przychód netto 2025 zgodny z kluczem (dane surowe), udziały kategorii w 2025 sumują się do 100%, uczestnik umie powiedzieć własnymi słowami, czym jest przejście kontekstu (błąd 1).

**Pułapka do omówienia:** w DAX `1 - BLANK()/100` daje 1, więc pusty rabat liczy się jak 0%. W SQL z zadania 2 ten sam wzór daje `NULL` i gubi wiersze. Ten sam słownik biznesowy wymaga różnego kodu w różnych językach, a Claude nie zawsze o tym wspomina bez pytania.

**Rozszerzenie:** poproś Copilota w Power BI o te same miary i porównaj odpowiedzi obu asystentów (jeśli grupa ma licencję Copilot).
