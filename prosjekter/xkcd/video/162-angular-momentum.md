---
tittel: Angular Momentum
karakterer: cueball, megan
format: video
status: film v3 2026-10-07; shot 3 clip is the xAI API (grok-imagine-video-1.5-lite) take, all other clips and all key frames via agentry on SuperGrok
nr: 162
kilde: xkcd 162 "Angular Momentum", https://xkcd.com/162/, CC BY-NC 2.5
tillegg_megan: tonight she wears a long, oversized light-grey T-shirt as a nightshirt, bare legs, barefoot; no burgundy top, no jeans
tillegg_cueball: tonight he is in bed in a plain dark T-shirt, duvet over his legs; no jeans
---
Video, vertical 9:16, nine shots, about 32 seconds plus intro and outro.
The original is one panel: a dark bedroom, Cueball sitting up in bed, Megan
spinning in the middle of the floor, and her lines cascading down the
image. Here the monologue is cut into shots. No speech bubbles; the lines
are a soundtrack later, subtitles until then. Dialogue word for word from
the original.

Fixed details:

- Night. The only light is cold moonlight through one window on the left
  wall and a faint warm glow from a bedside lamp. Blue and grey palette.
- Megan wears a long T-shirt as a nightshirt, barefoot. Cueball sits up in
  bed under the duvet, bare-chested or in a T-shirt, hair flattened by the
  pillow.
- Megan always spins counterclockwise seen from above, the Earth's own
  direction, so the physics of the joke holds: she turns toward her own
  left, right shoulder swinging toward the camera. Say it that way in
  every movement line; "counterclockwise" alone was read both ways
  (agentry clip wrong, API lite clip right, 2026-10-07). Arms slightly
  out, hair lifting with the turn.
- Room template `rom_soverom` in `assets/video/`: a bedroom at night with
  a bed on the right, a window on the left, nobody in it.

Format per shot (read by `video.py`): the first paragraph is the
description for people. Then the fields `Personer`, `Rom`, `Replikk`,
`Tekst`, `Varighet` (seconds in the film), `Bilde` (English prompt for the
key frame) and `Bevegelse` (English prompt for the clip). A shot without
`Bevegelse` becomes a still with a slow zoom. Character descriptions and
the room template are added automatically from `prosjekt.ini`.

Skudd 1: Establishing shot, the whole bedroom. Cueball sits up in bed,
Megan spins in the middle of the floor, a soft blur around her.
Personer: cueball, megan
Rom: soverom
Varighet: 3
Bilde: Wide shot of a dark bedroom at night, cold moonlight from a window on the left, a bed on the right. Cueball sits up in the bed under the duvet, just woken, looking at the middle of the room. Megan stands in the middle of the floor in a long T-shirt, barefoot, mid-spin, arms slightly out, hair lifting, a faint motion blur around her. Quiet, intimate, slightly surreal.
Bevegelse: The woman turns slowly on the spot, counterclockwise as seen from above, which means she turns toward her own LEFT: her right shoulder swings forward toward the camera and her left shoulder swings back, the same direction every time, hair and T-shirt hem lifting gently with each turn. The man in the bed does not move. Moonlight stays steady. Nobody else enters the frame.

Skudd 2: Close on Cueball in bed, sleepy, puzzled.
Personer: cueball
Rom: soverom
Replikk: Cueball: "What are you doing?"
Varighet: 3
Bilde: Close-up of Cueball sitting up in bed, framed from the chest up, duvet at his waist, hair flattened on one side, eyes half open, a puzzled frown, looking toward the camera-left. Moonlight on one side of his face. No one else in frame.
Bevegelse: The man blinks slowly and tilts his head a little, puzzled. He does not speak. Nobody else enters the frame.

Skudd 3: Medium shot of Megan spinning, calm face. Cueball in the bed
behind her.
Personer: megan, cueball
Rom: soverom
Replikk: Megan: "Spinning counterclockwise."
Varighet: 3
Bilde: Medium shot of Megan from the knees up, in the middle of the dark bedroom, spinning slowly, arms slightly out, hair lifting, eyes calm and half closed, a small serene smile. The window with moonlight behind her to the left. Behind her on the right, smaller and softly out of focus, Cueball sits up in the bed under the duvet and watches her. Nobody else.
Bevegelse: The woman keeps turning slowly on the spot, counterclockwise as seen from above, which means she turns toward her own LEFT: her right shoulder swings forward toward the camera and her left shoulder swings back, the same direction every time, her hair and the hem of her T-shirt lifting gently. Her whole body turns as one piece, head included: her face turns away from the camera and comes back around with each turn, never staying fixed on the camera while the body rotates. Her face stays calm. The man in the bed behind her stays still. Nobody else enters the frame.

Skudd 4: Low angle, Megan spinning against the window and the moon,
Cueball in the bed at the edge of the frame.
Personer: megan, cueball
Rom: soverom
Replikk: Megan: "Each turn robs the planet of angular momentum."
Varighet: 4
Bilde: Low camera angle from the floor looking up at Megan spinning, her figure dark against the moonlit window behind her, the full moon visible in the window pane, arms out, hair fanned by the turn. Dramatic but gentle. At the right edge of the frame, in the background, Cueball sits up in the bed under the duvet, watching. Nobody else.
Bevegelse: Slow spin counterclockwise as seen from above, which means she turns toward her own LEFT: her right shoulder swings forward toward the camera and her left shoulder swings back, the same direction every time, hair fanning out; the moon stays fixed in the window. The man in the bed stays still. Nobody else enters the frame.

Skudd 5: Insert: the Earth from space, the night side facing us, turning
very slowly.
Varighet: 4
Replikk: Megan: "Slowing its spin the tiniest bit."
Bilde: The planet Earth seen from space, filling most of the frame, the night side toward the camera with faint city lights, a thin bright crescent of dawn on the right edge, stars behind. Same clean webtoon style as the rest, flat colours, not photoreal. No people.
Bevegelse: The Earth rotates very slowly; the thin crescent of daylight at the right edge does not grow. Stars stay still.

Skudd 6: The window from inside, the horizon beyond it, a faint grey
pre-dawn glow that is not getting any brighter.
Rom: soverom
Replikk: Megan: "Lengthening the night, pushing back the dawn."
Varighet: 4
Bilde: TIGHT framing on the bedroom window only: the window and its thin white curtains fill the whole frame edge to edge, no bed, no floor, no furniture visible. The same window as in the room reference, seen from inside: the white frame, the full moon high in the pane, and through the glass a far horizon where the faintest grey-blue hint of dawn lies along the skyline under a sky still full of stars. Nobody in frame. Still and quiet.

Skudd 7: Close on Megan, she has stopped, a little dizzy, smiling at him;
Cueball soft in the background in the bed.
Personer: megan, cueball
Rom: soverom
Replikk: Megan: "Giving me a little more time here."
Varighet: 4
Bilde: Close-up of Megan from the chest up, she has stopped spinning, a little unsteady, hair settling, a soft smile, eyes on Cueball. Moonlight on her face. Behind her, out of focus on the right, Cueball sits up in the bed under the duvet looking back at her. Nobody else.
Bevegelse: Her hair settles slowly after the spin, she sways very slightly, her smile widens a little. She does not speak. The man in the background stays still. Nobody else enters the frame.

Skudd 8: Two-shot. Megan sits down on the edge of the bed, Cueball reaches
for her hand.
Personer: cueball, megan
Rom: soverom
Replikk: Megan: "With you."
Varighet: 4
Bilde: Medium two-shot in the dark bedroom. Megan sits down on the edge of the bed, turned toward Cueball, who sits up under the duvet and reaches out to take her hand. Both faces soft, looking at each other. Moonlight from the window on the left. Nobody else in frame.
Bevegelse: The woman settles on the edge of the bed and the man takes her hand; they look at each other and stay still. Nobody else enters the frame.

Skudd 9: Wide shot again, the room at rest, both in bed, the window still
dark.
Personer: cueball, megan
Rom: soverom
Tekst: after xkcd #162 by Randall Munroe, CC BY-NC 2.5
Varighet: 3
Bilde: Wide shot of the dark bedroom, same framing as the opening shot. Cueball and Megan lie in the bed under the duvet, close together, eyes closed. The middle of the floor is empty. Moonlight from the window on the left, the sky outside still night. Quiet.
