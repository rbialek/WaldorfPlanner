# Zasady planowania lekcji - Rok szkolny 2026/27

## Ogolne

- Rok szkolny: 2026/2027
- Klasy: 9, 10, 11, 12
- Laczna liczba uczniow: 62 (kl9: 17, kl10: 17, kl11: 18, kl12: 10)

## Rozszerzenia

- Kazdy uczen wybiera od 1 do 3 przedmiotow rozszerzonych
- Dostepne rozszerzenia: matematyka, biologia, chemia, fizyka, informatyka, historia, j_polski, geografia, wos, historia_sztuki
- Grupy rozszerzeniowe moga laczyc uczniow z roznych klas

## Jezyki obce

- Kazdy uczen wybiera 1 jezyk obcy (oprocz j_angielskiego, ktory jest obowiazkowy)
- Dostepne jezyki: j_hiszpanski, j_niemiecki, j_rosyjski, j_francuski
- ZW = uczen zwolniony z jezyka obcego

## Przedmioty

- Przedmioty caloroczne: j_polski, matematyka, fizyka, angielski1, angielski2, wf, filozofia, etyka, artystyczne, wychowawcza
- Przedmioty caloroczne tylko kl12: matura_mat, matura_pol
- Przedmioty epokowe (kl9-11): historia, biologia, chemia, informatyka, geografia, edukacja_obyw, edb, biz
- 10 przedmiotow rozszerzonych (do wyboru 1-3)
- 4 jezyki obce (do wyboru 1)
- Przedmioty z wieloma nauczycielami: j_polski (n2, n12), matematyka (n1, n11)

## Nauczyciele

- Laczna liczba nauczycieli: 12
- Niektórzy nauczyciele ucza wiecej niz jednego przedmiotu (np. n1 - matematyka + matematyka_roz)

## Siatka godzin lekcyjnych

| Nr lekcji | Godziny |
|-----------|---------|
| 0 | 7:25 - 8:10 |
| 1 | 8:15 - 9:00 |
| 2 | 9:10 - 9:55 |
| 3 | 10:10 - 10:55 |
| 4 | 11:05 - 11:50 |
| 5 | 12:10 - 12:55 |
| 6 | 13:05 - 13:50 |
| 7 | 14:00 - 14:45 |
| 8 | 14:55 - 15:40 |
| 9 | 15:45 - 16:30 |

## System epok (kl9-11)

Przedmioty epokowe sa nauczane w 4-tygodniowych blokach. W danej epoce klasa ma tylko jeden przedmiot epokowy. 
Przedmiot epokowy jest uczony przez tego samego nauczyciela w tym samym bloku.
Najlepiej jesli przedmiot epokowy odbywa sie o tej samej porze. 
Klasa 12 nie uczestniczy w systemie epok.

| Okres | kl9 | kl10 | kl11 |
|-------|-----|------|------|
| 2.09 - 23.09 | informatyka | biologia | historia |
| 24.09 - 23.10 | biologia | historia | matematyka |
| 27.10 - 20.11 | chemia | geografia | biologia |
| 24.11 - 11.12 | geografia | edukacja_obyw | informatyka |
| 15.12 - 22.01 | historia | chemia | geografia |
| 26.01 - 9.03 | biologia | geografia | chemia |
| 10.03 - 9.04 | chemia | edukacja_obyw | geografia |
| 13.04 - 14.05 | edb | historia | biz |
| 18.05 - 15.06 | historia | biz | historia |

## Ograniczenia planowania (twarde - musza byc spelnione)

- Uczen nie moze miec dwoch lekcji w tym samym czasie
- Nauczyciel nie moze prowadzic dwoch lekcji w tym samym czasie
- Maksymalnie 8 lekcji dziennie na klase
- Dni nauki: poniedzialek - piatek
- Uwzglednic ograniczenia dostepnosci nauczycieli (patrz nauczyciele.md)

## Optymalizacja (miekkie - wczytywane przez solver)

Solver wczytuje ponizsze reguly i ich wagi. Waga okresla priorytet (wyzsza = wazniejsza).
Waga 0 = regula wylaczona. Mozna dodawac nowe reguly jesli solver je wspiera.

| ID | Opis | Waga |
|----|------|------|
| unikaj_slot0 | Lekcje zaczynaja sie od lekcji 1 (8:15). Lekcja 0 (7:25) tylko wyjatkowo. | 100 |
| brak_okienek_uczniow | Lekcje uczniow w jednym ciagu bez przerw. Jesli uczen ma 6 lekcji to np. 1-6, nie 1-3 i 5-7. | 50 |
| wczesne_konczenie | Uczniowie koncza lekcje jak najwczesniej. | 30 |
| trudne_wczesniej | Przedmioty wymagajace (matematyka, fizyka, informatyka, chemia, biologia) we wczesnych godzinach. Po nich lzejsze (wf, sztuka). | 25 |
| min_okienek_nauczycieli | Lekcje nauczyciela danego dnia w spojnym bloku, bez pustych godzin miedzy lekcjami. | 20 |
| kompaktowy_plan | Nauczyciele w najmniejszej liczbie dni. Jesli malo godzin, lepiej 2-3 dni niz 5. | 10 |
| unikaj_pojedynczych | Unikaj sytuacji gdy nauczyciel przychodzi na 1 lekcje w dniu. | 5 |
