# Regler for assistenten (Claude Code / Codex)

Dette er verktøymanualen for den som skriver utkast og kjører `comic.py`
sammen med eieren av en serie. Den gjelder alle serier. Hver serie ligger
under `prosjekter/<navn>/` med sin egen `prosjekt.ini`, canon, kort,
utkast og sin egen `AGENTS.md`; **les den også**, den sier hva eieren av
akkurat den serien vil, og den vinner over denne fila når de er uenige.

Finnes `STATUS.md` og `TODONT.md` i rota, les dem: STATUS er hva som er
sant i dag, TODONT er det som er prøvd og ikke virket, med målinger. De
finnes bare i verktøyforfatterens eget repo; mangler de, er denne fila nok.

## Prosjekter og oppsett

- `comic.py` finner prosjektet fra utkastets sti, ellers `-P <navn>` (står
  FØR underkommandoen: `comic.py -P navn pick`), ellers `project=` under
  `[comic]` i keys.ini, ellers cwd.
- `keys.ini` har leverandører og eventuelle nøkler, felles for alle
  prosjekter. Alt om innhold står i prosjektets `prosjekt.ini`.
- Nytt prosjekt: kopier `prosjekter/eksempel/` til et nytt navn og fyll ut.
- Eieren godkjenner. Assistenten velger aldri selv.
- Alt som genereres beholdes i `generert/`. Ingenting slettes.

## Formatet: stående paneler

Med `format = paneler` i prosjekt.ini er en stripe et sett høye 2:3-bilder,
ett per panel, laget for mobil: et flerbildeinnlegg på Facebook, en
karusell på Instagram, en side på en blogg man ruller nedover. Den gamle
liggende stripa med alle panelene i ett bilde er unntaket (`new --strip`).

Løypa:

```
comic.py new <utkast>          # ett kall per panel, stiftet til én kjøring
comic.py -P <navn> pick        # nettside: velg kjøring, kommenter paneler
comic.py approve <utkast>      # kutter valgt kjøring til paneler/<slug>/N.jpg
```

`paneler/<slug>/1.jpg, 2.jpg ...` er det eieren legger ut, i den
rekkefølgen.

## Utkastet

- Fil `prosjekter/<navn>/utkast/NNN-slug.md` med frontmatter `tittel`,
  `karakterer`, `status`. Ett avsnitt per panel, `Panel N:` først.
- Beskriv det som skal synes, ikke det som skal føles. Replikker ordrett i
  anførselstegn. Si antallet paneler når det ikke er fire.
- **Panelene tegnes hver for seg.** Innledningen leses som kontekst, ikke
  som instruks. Alt som skal være med i et panel må stå i det panelets
  avsnitt: farge på rekvisitter, svart-hvitt, klær som skal være like,
  hvem som er i bildet. En lilla elefant som bare er lilla i ett avsnitt,
  blir grå i de neste.
- **Et kort er en invitasjon.** Kortet sendes for hver figur som er nevnt
  ved navn i avsnittet; et avsnitt som ikke nevner noen, får ingen kort.
  Nevner en replikk noen som ikke skal være i bildet, skriv `[uten: navn]`
  i avsnittet.
- **Ingen taleboble der en rekvisitt kan si det.** Et broderi, en kopp, et
  forkle eller en tekstboks bærer tekst bedre enn en boble.
- Bobler leses ovenfra og ned: den første replikken må stå høyest.
- Unngå positurer med mange synlige labber (hund på ryggen, hund sett
  rett forfra med alle fire); modellen teller feil. Proporsjoner og antall
  bein rettes i utkastet, ikke med korreksjoner.
- To figurer som tenker det samme: skriv "én felles tankeboble med en
  rekke små skyer ned til hver av dem", ellers tegnes boblen to ganger.
- Seriens AGENTS.md sier hva eieren vil bli spurt om før et utkast er
  ferdig. Spør i én samlet melding og skriv svarene inn ordrett.
- Fyll inn plassholdere med Python, ikke sed; en plassholder brutt over to
  linjer overlever sed og blir tegnet.

## Velge og kommentere: pick-siden

`comic.py -P <navn> pick` starter én server for prosjektet: `/` er lista
over utkast med kjøringer, `/<nr>/` er siden for én stripe (nummeret før
første bindestrek). Hver kjøring vises som et rutenett av paneler med ett
kommentarfelt per panel og en "Velg denne"-knapp. Sidene bygges per
oppslag, så nye kjøringer kommer uten omstart. Standard port 8780.
`--bind 0.0.0.0` for å nå den fra mobilen.

Sløyfen:

1. Start serveren i bakgrunnen og gi eieren adressen.
2. Vent til eieren sier fra, les `generert/<slug>/picks.json`: `picked`,
   `panels[bilde][n]` (kommentar per panel) og `note` (fritekst).
3. Skriv kommentaren inn i utkastet først, så tegn bare de panelene på
   nytt: `new <utkast> --only 3 5`. Siden viser den nye kjøringen.
4. Eieren velger uten kommentar: `approve`.

## Korreksjoner, i denne rekkefølgen

1. **Rett avsnittet og tegn panelet på nytt**: `new --only N`. Førstevalget
   for alt som handler om hva som er i bildet. `--chain` tegner flere
   paneler etter hverandre med panelet foran som referanse, for to paneler
   som må ha samme biler eller samme rom. `--only N --insert N` når panel N
   er nytt i utkastet og de gamle skal ett hakk ned.
2. **`fix --panel N "..."`** for én lokal ting: en hånd, en labb, en
   boble som skal bli tankeboble, en tekstboks som skal inn. Bare panelet
   sendes og limes tilbake i eksakt størrelse.
3. **Pillow** for å flytte, klippe eller bytte paneler mellom kjøringer,
   uten bildemodell.
4. `fix --mask` bare for én kroppsdel i et liggende bilde; ikke på en
   stiftet panelkjøring.

Slik skrives en korreksjon:

- Én eller to endringer per kall.
- Beskriv feilen visuelt, ikke med fagord. "En liten hvit trekant som
  henger fra nedre kant av bobla" virker; "fjern den ekstra halen" ikke.
- Si hva området skal fylles med.
- Avslutt med hva som ikke skal røres (ansikter, tekst, resten).
- Sjekk resultatet i full oppløsning: klipp ut området med Pillow.
- Har to korreksjoner feilet på samme panel: tegn panelet på nytt.
- Tekst i en boks byttes ikke pålitelig; tegn panelet på nytt fra
  avsnittet med den nye teksten.

## Leverandører

Satt opp i keys.ini, valgt med `-p`, standard i prosjekt.ini.

| Leverandør | Hva | Per panel | Bruk |
|---|---|---|---|
| `openai-images` | OpenAI Images API, nøkkel | 15 til 20 s, ca. 3 cent | når noen venter på resultatet |
| `agentry` | codex via agentry, ChatGPT-abonnement | 70 til 170 s, gratis | batcher ingen venter på |
| `grok-agentry` | Grok Build via agentry, SuperGrok | 30 til 60 s, gratis | paneler og film; stilen driver mot foto |
| `openai` | Responses-veien, en LLM skriver prompten | | bare liggende striper |

- `fallback = openai-images` under `[agentry]` gjør at et panel som feiler
  på codex (kvote, tidsavbrudd) tas på API-et automatisk.
- comic.py starter sin egen agentry på porten i keys.ini om ingen svarer,
  med logg i `generert/agentry-<port>.log`.
- Maks fem referansebilder på codex, tre på Grok. Kombinerte kort
  (`karakterer/a-b.jpg`) velges automatisk når alle på kortet er med og
  teller som ett.
- `--dry-run` på `new` og `fix` viser nøyaktig hva som sendes.

## Andre kommandoer

- `comic.py portrait <utkast>`: tegner en godkjent liggende stripe om til
  stående paneler, ett kall per panel med panelet som referanse.
- `comic.py fix <utkast> "..."`: korrigerer siste bilde; `--run N` for et
  eldre, `--panel N` for ett panel.
- `comic.py approve <utkast>`: med `format = paneler` kuttes den valgte
  kjøringen (eller en nyere) til `paneler/`; ellers header og kant på
  stripa i `striper/`. Er `credit =` satt i prosjekt.ini, tegnes en
  kreditteringslinje under bildet.
- `comic.py providers`: hva som er satt opp.
- `video.py`: film fra et skuddmanus, se prosjektets `video/`.
