# Veiviser: ny stripe

For assistenten (codex, Claude Code). Følg denne når eieren vil lage en ny
stripe, sier "ny stripe", forteller en vits eller en historie, eller
starter deg med `ny-stripe.bat`. Eieren skriver lite. Du gjør jobben og
spør bare om det du ikke kan finne ut selv.

## Slik snakker du

- Ett spørsmål per melding. Kort. Vent på svaret.
- Gi nummererte valg når det går: "1 ja, 2 nei, 3 noe annet". "1", "ja"
  og "ok" er fullgode svar.
- Aldri be eieren skrive en prompt, et utkast, en fil eller en kommando.
  Det gjør du.
- Ikke vis kommandoer eller filstier om eieren ikke spør. Si hva som skjer:
  "Jeg tegner presten nå, det tar et minutt."
- Går noe galt: én setning om hva, én om hva du gjør nå.
- Eieren godkjenner. Du godkjenner aldri selv.

## Før første spørsmål, uten å spørre

1. Finn prosjektet: `project =` under `[comic]` i keys.ini. Les
   prosjektets AGENTS.md, CANON.md og prosjekt.ini.
2. Se hvilke kort som finnes i `karakterer/` og hvilke rom (`rom_...`) som
   står i prosjekt.ini.
3. Finn neste nummer i `utkast/`.
4. Python er `.venv\Scripts\python.exe` i rota, ikke `python`. Kjør alt
   fra rota: `.venv\Scripts\python.exe comic.py ...`.

## 1. Historien

Spør: "Hva skal stripa handle om? Fortell vitsen sånn du husker den, det
trenger ikke være pent."

Gjenfortell den i to eller tre setninger: oppsettet, så poenget. Spør:
"Er det sånn den går? 1 ja, 2 nei (fortell meg hva som er feil)."

Poenget skal stå med eierens ord om eieren har sagt det ordrett. Ikke
pynt på punchlinen.

## 2. Figurene

Skriv opp hvem som er med. For hver figur:

- Finnes et kort som passer: foreslå det. "Presten kan spilles av Gubben.
  1 ja, 2 lag en egen prest."
- Ellers: foreslå et utseende i én setning (alder, kropp, hår, ansikt,
  klær med én fast farge) og spør "1 ok, 2 endre". Så
  `comic.py kort <navn> "<beskrivelse>" --stil karakterer\<kort>.jpg`,
  der `<kort>` er et eksisterende kort av samme slag: en person for en
  person, et dyr for et dyr. Det nye kortet får oppsett og tegnestil
  derfra.
- Se på kortet selv før du viser det, side om side med `--stil`-kortet:
  samme oppsett (navn, helfigur, nærbilde, profil, rygg, uttrykk) og samme
  strek? Ser det ut som et foto, eller er det bare én figur: tegn på nytt
  (`<navn>2`) uten å spørre eieren.
- Vis kortet: skriv hele stien alene på en linje, så eieren kan
  Ctrl+klikke den. Ikke stol på `Invoke-Item` eller `Start-Process`: i
  Tommys test 2026-11-01 gikk kommandoen gjennom uten at noe åpnet seg
  for eieren. Spør "1 bra,
  2 prøv igjen, 3 endre noe". Prøv igjen = nytt navn (`presten2`),
  ingenting overskrives. Bruk det nye navnet i utkastet.
- Navnet er ett ord uten æøå, og det er ordet du bruker i panelteksten:
  `presten`, `johansen`. Legg et `### Presten`-avsnitt med beskrivelsen i
  CANON.md og IMAGE_CANON.md.

Folkemengder og barn som løper får ikke kort. Beskriv dem i teksten med et
tall: "fem gutter i kortbukser", ikke "masse unger". Maks tre figurer med
kort i ett panel; de deler plassen med rommet og panel 1.

## 3. Stedene

Skriv opp stedene. Hvert sted som er med i to paneler eller flere, får et
romkort:

- Foreslå hvordan stedet ser ut i én setning med farger: vegger,
  gardiner, møbler, lampe, duk. Spør "1 ok, 2 endre".
- `comic.py rom <navn> "<beskrivelse>"`, vis bildet som et kort (over),
  spør "1 bra, 2 prøv igjen, 3 endre noe".
- Legg `rom_<navn> = assets/rom-<navn>.jpg` under `[prosjekt]` i
  prosjekt.ini.

Et sted som bare er med i ett panel, trenger ikke kort.

## 4. Panelene

Foreslå tre til fem paneler, én linje hver, med replikkene. Poenget i
siste panel, siste replikk alene. Spør: "1 tegn den, 2 endre noe".

## 5. Spørsmålene fra prosjektet

Prosjektets AGENTS.md kan ha spørsmål som skal stilles før et utkast er
ferdig. Still dem én om gangen. Skriv svarene inn ordrett.

## 6. Utkastet

Skriv `utkast/NNN-slug.md` etter reglene i AGENTS.md i rota. Det som
oftest glipper:

- Hvert panelavsnitt står alene. Navn, klær med farger, hvem som står til
  venstre og høyre, og `[rom: <navn>]` først i hvert avsnitt som foregår
  der.
- Replikkene ordrett i anførselstegn. Den som snakker først, står høyest.
- Tekst på ting heller enn bobler der det går.
- `status: utkast` i frontmatter.

Kjør `new <utkast> --dry-run` og les det selv. Står en figur uten kort, et
rom uten kort, eller feil antall paneler: rett det før du går videre.

## 7. Tegn og vis

Si: "Jeg tegner nå. Det tar noen minutter." Kjør `new <utkast>`.

Start velgeren i bakgrunnen (`comic.py pick`) og gi eieren adressen
alene på en linje, `http://127.0.0.1:8780/<nr>/`; eieren åpner den selv.
Svarer det alt på porten fra en tidligere økt, bruk den. Si:
"Klikk på et panel for å si hva som er galt. Trykk 'Velg denne' når du er
fornøyd. Si fra her når du er ferdig."

## 8. Rett og godkjenn

Når eieren sier fra, les `generert/<slug>/picks.json`.

- Kommentarer på paneler: skriv rettingen inn i panelavsnittet i
  utkastet, og tegn bare de panelene på nytt (`new <utkast> --only 3`).
  Si hva du endret i én setning. Tilbake til steg 7.
- Valgt uten kommentarer, eller eieren sier "godkjenn": `approve`, sett
  `status: godkjent <dato>` i utkastet, og skriv hele stien til mappa
  `prosjekter\<prosjekt>\paneler\<slug>` alene på en linje. Si: "Bildene er
  nummerert. Legg dem ut i den rekkefølgen." Står `samlet = ja` i
  prosjekt.ini, finnes også `paneler\<slug>-samlet.jpg` med alle panelene
  i ett høyt bilde; skriv den stien også.

Feil i et rom (nye gardiner, ny lampe) rettes med romkortet, ikke ved å
beskrive rommet i avsnittet. Har to rettinger feilet på samme panel, tegn
panelet på nytt fra utkastet.
