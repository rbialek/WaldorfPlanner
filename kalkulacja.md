# Kalkulacja planu lekcji - Instrukcja generowania

## Cel

Wygeneruj optymalny tygodniowy plan lekcji dla szkoly na rok 2026/27.
Plan musi spelniac wszystkie twarde ograniczenia i maksymalnie optymalizowac miekkie kryteria.

## Dane wejsciowe

Przeczytaj WSZYSTKIE ponizsze pliki przed rozpoczeciem kalkulacji:

1. `dane/2026-27/klasy.md` - lista uczniow, ich rozszerzenia, jezyki obce, grupy angielskiego
2. `dane/2026-27/nauczyciele.md` - lista nauczycieli, przedmioty, ograniczenia dostepnosci
3. `dane/2026-27/przedmioty.md` - przedmioty caloroczne, epokowe, rozszerzone, jezyki
4. `dane/2026-27/matryca.md` - ile godzin kazdego przedmiotu w kazdej klasie
5. `dane/2026-27/zasady.md` - siatka godzin, system epok, ograniczenia, kryteria optymalizacji

## Algorytm generowania

### Krok 1: Zbuduj model danych

Na podstawie plikow wejsciowych zbuduj pelny model:

- **Sloty**: 5 dni (pn-pt) x 10 lekcji (0-9) = 50 slotow na tydzien
- **Klasy**: kl9 (17 ucz.), kl10 (17 ucz.), kl11 (18 ucz.), kl12 (10 ucz.)
- **Nauczyciele**: n1-n12 z ich ograniczeniami czasowymi
- **Przedmioty**: caloroczne, epokowe (zmienne wg okresu), rozszerzone, jezyki

### Krok 2: Zidentyfikuj grupy uczniow

Dla kazdego przedmiotu rozszerzonego i jezyka obcego wypisz liste uczniow z klasy.md:

- **Grupy rozszerzeniowe** - uczniowie z tym samym rozszerzeniem moga byc laczeni miedzyklasowo
- **Grupy jezykowe** - uczniowie tego samego jezyka obcego moga byc laczeni miedzyklasowo
- **Grupy angielskiego** - angielski1 i angielski2 w kazdej klasie (nie laczyc miedzyklasowo)

### Krok 3: Zastosuj ograniczenia twarde

Sprawdz KAZDE przypisanie pod katem:

1. **Brak konfliktow uczniow** - zaden uczen nie ma 2 lekcji w tym samym slocie
2. **Brak konfliktow nauczycieli** - zaden nauczyciel nie ma 2 lekcji w tym samym slocie
3. **Dostepnosc nauczycieli** - nie przypisuj lekcji gdy nauczyciel jest niedostepny:
   - n2: niedostepna poniedzialki 8-10 (lekcje 1-2)
   - n3: niedostepny piatki (caly dzien)
   - n4: niedostepna wtorki 12-15 (lekcje 5-8)
   - n5: niedostepny srody 10-15 (lekcje 3-8), czwartki 7-11 (lekcje 0-4)
   - n7: niedostepny piatki 13-15 (lekcje 6-8)
   - n8: niedostepna poniedzialki 7-9 (lekcje 0-1), srody 13-15 (lekcje 6-8)
   - n10: niedostepna czwartki (caly dzien)
   - n11: niedostepny wtorki 7-10 (lekcje 0-2)
4. **Max 8 lekcji dziennie** na klase
5. **System epok** - w danym okresie epokowym klasa ma przypisany konkretny przedmiot (patrz zasady.md)

### Krok 4: Optymalizuj (priorytet malejacy)

1. **Start od lekcji 1** - lekcja 0 tylko jesli konieczna
2. **Brak okienek uczniow** - lekcje kazdego ucznia musza byc w ciagu (bez przerw)
3. **Minimalne okienka nauczycieli** - lekcje nauczyciela w danym dniu w spojnym bloku
4. **Kompaktowy plan nauczycieli** - koncentruj lekcje w najmniejszej liczbie dni, unikaj pojedynczych lekcji w dniu

### Krok 5: Uwzglednij angielski

- angielski1 i angielski2 tej samej klasy MUSZA byc w tym samym slocie (lekcje rownolegle)
- n8 prowadzi jedna grupe, druga grupa potrzebuje drugiego prowadzacego LUB obie grupy sa w roznych slotach
- UWAGA: n8 nie moze prowadzic obu grup jednoczesnie! Jesli obie sa rownolegle, jedna musi miec innego nauczyciela. Alternatywnie: angielski1 i angielski2 tej samej klasy moga byc w roznych slotach.

## Pliki wyjsciowe

Zapisz wyniki w katalogu `plany/`:

### Plany klas: `plany/klasa{N}.md`

Generuj: `plany/klasa9.md`, `plany/klasa10.md`, `plany/klasa11.md`, `plany/klasa12.md`

Format:

```markdown
# Plan lekcji - Klasa {N} - Rok szkolny 2026/27

## Tygodniowy plan (caloroczny)

Uwaga: przedmioty epokowe zmieniaja sie wg planu epok (patrz zasady.md).
W tabeli oznaczone jako [EPOKA] - w danym okresie zastap aktualnym przedmiotem.

|  | Poniedzialek | Wtorek | Sroda | Czwartek | Piatek |
|--|-------------|--------|-------|----------|--------|
| 0 (7:25-8:10) | - | - | - | - | - |
| 1 (8:15-9:00) | j_polski (n2) | matematyka (n1) | ... | ... | ... |
| 2 (9:10-9:55) | ... | ... | ... | ... | ... |
| ... | ... | ... | ... | ... | ... |

## Lekcje epokowe (zmienne wg okresu)

| Slot | Nauczyciel | Aktualny przedmiot wg epoki |
|------|------------|----------------------------|
| wt/3 | n3 | [EPOKA] - patrz zasady.md |

## Grupy rozszerzeniowe

| Rozszerzenie | Slot | Nauczyciel | Uczniowie z tej klasy |
|-------------|------|------------|----------------------|
| matematyka_roz | sr/5 | n1 | Bokun, Dudziak, Fabianczyk, Hankus, ... |
| biologia_roz | cz/5 | n4 | Beyga, Bilek, Jurasz, ... |

## Grupy jezykowe

| Jezyk | Slot | Nauczyciel | Uczniowie |
|-------|------|------------|-----------|
| j_hiszpanski | pt/4 | n8 | (wszyscy z klasy 9) |

## Grupy angielskiego

| Grupa | Slot | Nauczyciel | Uczniowie |
|-------|------|------------|-----------|
| angielski1 | pn/3 | n8 | Beyga, Bilek, Bokun, Dudziak, Hankus, Jakubiec, Jurasz, Kawa, Pytlarz, Sznabel |
| angielski2 | pn/3 | n8 | Cader, Fabianczyk, Polanska, Stefanowska, Wlodarski, Zietek, Borowska |
```

### Plany nauczycieli: `plany/{nID}_{Imie}_{Nazwisko}.md`

Generuj dla kazdego nauczyciela, np:
- `plany/n1_Jan_Kowalski.md`
- `plany/n2_Anna_Nowak.md`
- `plany/n3_Piotr_Wisniewski.md`
- `plany/n4_Maria_Kaminska.md`
- `plany/n5_Tomasz_Zielinski.md`
- `plany/n6_Ewa_Szymanska.md`
- `plany/n7_Krzysztof_Wojcik.md`
- `plany/n8_Agnieszka_Kozlowska.md`
- `plany/n9_Robert_Jankowski.md`
- `plany/n10_Magdalena_Mazur.md`
- `plany/n11_Andrzej_Krawczyk.md`
- `plany/n12_Katarzyna_Piotrowska.md`

Format:

```markdown
# Plan lekcji - {Imie} {Nazwisko} ({nID}) - Rok szkolny 2026/27

## Przedmioty: {lista przedmiotow}
## Ograniczenia: {ograniczenia lub "brak"}
## Laczna liczba godzin: {X}h/tydzien

## Tygodniowy plan

|  | Poniedzialek | Wtorek | Sroda | Czwartek | Piatek |
|--|-------------|--------|-------|----------|--------|
| 0 (7:25-8:10) | - | - | - | - | - |
| 1 (8:15-9:00) | matematyka kl9 | - | matematyka kl12 | ... | ... |
| 2 (9:10-9:55) | matematyka kl9 | ... | ... | ... | ... |
| ... | ... | ... | ... | ... | ... |

## Szczegoly lekcji

| Dzien | Lekcja | Przedmiot | Klasa/Grupa | Uczniowie |
|-------|--------|-----------|-------------|-----------|
| pn | 1 | matematyka | kl9 (cala klasa) | Beyga, Bilek, Bokun, ... (17 ucz.) |
| pn | 2 | matematyka | kl9 (cala klasa) | Beyga, Bilek, Bokun, ... (17 ucz.) |
| pn | 5 | matematyka_roz | grupa roz. mat kl9+kl10 | Bokun, Dudziak, ... (12 ucz.) |

## Podsumowanie

- Dni pracy: {lista dni}
- Godziny: {min}-{max} (lekcje {od}-{do})
- Okienka: {liczba} ({opis gdzie})
- Bloki: {opis spojnych blokow}
```

## Walidacja koncowa

Po wygenerowaniu WSZYSTKICH planow, sprawdz:

1. **Spojnosc miedzy planami** - lekcja w planie klasy musi odpowiadac lekcji w planie nauczyciela
2. **Brak konfliktow** - zaden nauczyciel nie ma 2 lekcji w tym samym slocie
3. **Brak konfliktow uczniow** - szczegolnie uczniowie w grupach miedzyklasowych
4. **Pokrycie matrycy** - kazdy przedmiot ma tyle godzin ile w matryca.md
5. **Listy uczniow** - przy kazdym przedmiocie sa poprawni uczniowie z klasy.md
6. **Ograniczenia nauczycieli** - zadna lekcja nie jest w niedostepnym slocie

Jesli walidacja wykryje bledy, popraw plan i ponownie zwaliduj.

## Raport

Na koniec wygeneruj `plany/raport.md` z podsumowaniem:

- Statystyki okienek (uczniowie i nauczyciele)
- Uzycie lekcji 0
- Rozklad godzin nauczycieli na dni
- Ewentualne kompromisy i dlaczego byly konieczne
