# Rei Toei Stage Cue Configuration and Genre Catalog

[Back to the customization guide](rei-toei-customization.md)

## Scope and Suno Caveat

This is the project's exhaustive reference catalog of **potential** arrangement
and performance cues, grouped by genre family. Any cue below can be copied into a
profile's `cues` or `optional_cues`. It is a curated vocabulary, not an official
Suno command list: Suno v6-mini does not document a deterministic bracket-tag
grammar, so a cue can be ignored, interpreted differently, or sung. Always
audition the result.

Rei's quality gates can guarantee the text layout, not the generated audio.
Put directions in `[square brackets]`, each on its own line. Reserve parentheses
for sung vocalizations such as `(Oh oh oh)`. Keep genre, instrumentation, mix,
and BPM descriptors primarily in the style tags; avoid cue overload.

## Selecting a Profile

Edit `lyrical_structure.stage_cues` in
[`rei_toei_domain_knowledge.json`](../data/avatar/rei_toei_domain_knowledge.json):

```json
{
  "active_profile": "cyberpunk",
  "profiles": {
    "...": "Keep the existing profile objects here."
  }
}
```

Change **only** `active_profile` to select an existing profile. The example above
illustrates the selector, not a complete replacement for the profiles object.
Selection is explicit; genre tags do not trigger automatic profile changes.
The default remains `cyberpop`.

| Profile | Required sections | Production/layout choices |
|---|---|---|
| `cyberpop` | Intro, Verse 1, Chorus, Verse 2, Bridge, Drop, Solo, Outro | `[Instrumental Build]`, `(Ahh ahh ahh)`, sung `[Intro Verse]`, `[Heavy Bass Drop]`; solo instrument remains a creative choice |
| `cyberpunk` | Same required sections as cyberpop | `[Dark Synth Pulse]`, `[Distorted Bass Drop]`, `[Distorted Synth Solo]`, `[Fade Out]`; optional instrumental `[Glitch Breakdown]` |
| `acoustic` | Verse 1, Chorus, Verse 2, Outro | Optional `[Intro]` with `[Fingerpicked Guitar]`; optional `[Acoustic Guitar Solo]`; no Drop or forced primer |
| `rock` | Verse 1, Chorus, Verse 2, Bridge, Solo, Outro | Optional `[Intro]` with `[Guitar Riff]`; mandatory `[Guitar Solo]`; no Drop or forced primer |
| `hip_hop` | Verse 1, Hook, Verse 2, Outro | The `chorus` JSON field renders as `[Hook]`; optional `[Beat Intro]`; no mandatory bridge, drop, or solo |
| `ambient` | Instrumental Intro, sung Verse 1, instrumental Interlude, instrumental Outro | `[Atmospheric Pads]`, `[Ambient Interlude]`, `[Fade Out]`; optional `[Refrain]`; no drop or primer |

These are editable starter arrangements, not rules defining an entire genre.
Stage profiles do not change the persona, style tags, language policy, or tempo
fitting settings; adjust those separately when changing musical direction.

## Profile Schema

Each profile is complete, not inherited from another profile. Copy a profile,
rename it, then edit its sections. This example defines a compact acoustic song:

```json
{
  "intro_verse_label": null,
  "intro_primer": null,
  "optional_cues": ["Soft Percussion", "Humming"],
  "sections": {
    "intro": {
      "label": "Intro",
      "required": false,
      "content": "instrumental",
      "cues": ["Fingerpicked Guitar"]
    },
    "verse_1": {
      "label": "Verse 1",
      "required": true,
      "content": "sung",
      "cues": []
    },
    "chorus": {
      "label": "Refrain",
      "required": true,
      "content": "sung",
      "cues": []
    },
    "outro": {
      "label": "Outro",
      "required": true,
      "content": "sung",
      "cues": ["Fade Out"]
    }
  }
}
```

- **`sections`**: Enabled JSON fields, in performance order. Removing a field
  disables it, including in fallback and final assembly. An optional field can
  appear when supplied, but is not synthesized just because it has cue settings.
- **Supported field names**: `intro`, `verse_1`, `pre_chorus`, `chorus`, `verse_2`,
  `bridge`, `drop`, `solo`, `breakdown`, `outro`. These are the fixed Lyrics data
  contract, not mandatory musical sections. New fields such as `verse_3` need
  code support; assigning `label: "Verse 3"` does not add another verse field.
- **`label`**: The output heading, without brackets. For example, `Hook`,
  `Middle Eight`, `Interlude`, or `Coda` can rename an existing field.
- **`required`**: Boolean. The draft gate checks that section's content. Missing
  sections cause bounded retries with feedback drawn from this profile.
- **`content`**: `sung` requires actual sung lines, not just tags or vocalizations.
  `instrumental` requires directions beyond the heading and brackets its body;
  it does not generate translations or Romaji for that section.
- **`cues`**: Mandatory directions whenever this section is present, in listed
  order, without brackets in JSON. Final formatting inserts them at the start
  of the body and removes duplicate occurrences, including inline copies.
  These cues are deterministic formatting repairs, not extra model retries.
- **`optional_cues`**: Optional direction vocabulary sent to the lyric model.
  These cues are not injected or enforced.
- **`intro_verse_label`**: Separate heading for sung opening lines, such as
  `Intro Verse`; `null` disables the split opening layout.
- **`intro_primer`**: Parenthesized vocalization, such as `(Ahh ahh ahh)` or
  `(Oh oh oh)`, immediately after the intro heading; `null` disables the forced
  primer. An opening vowel vocalization is replaced rather than duplicated.

At least one section must be both required and sung: this is a vocal-lyric
pipeline, not a configuration for fully instrumental Suno generation.

The final draft can backfill missing framing sections from the profile-aware
fallback (Intro, Pre-Chorus, Drop, Solo, Breakdown, Outro). Missing required
verses, Chorus, or Bridge after retries triggers the existing full-song fallback.
Disabling a section does not weaken Japanese-language or repetition checks on
the remaining content.

## Structural Cue Vocabulary

Use the profile's `label` setting to rename the corresponding field. The fixed
JSON fields still determine which text is a verse, chorus, or instrumental part.

| Purpose | Potential headings |
|---|---|
| Opening | `[Intro]`, `[Instrumental Intro]`, `[Instrumental Build]`, `[Opening]`, `[Prelude]`, `[Overture]`, `[Cold Open]`, `[Count In]`, `[Fade In]` |
| Sung opening | `[Intro Verse]`, `[Opening Verse]`, `[Intro Hook]`, `[A Cappella Intro]` |
| Narrative | `[Verse 1]`, `[Verse 2]`, `[Rap Verse]`, `[Spoken Verse]`, `[Spoken Word]`, `[Narration]`, `[Monologue]` |
| Lift into hook | `[Pre-Chorus]`, `[Pre-Hook]`, `[Build]`, `[Build Up]`, `[Rise]`, `[Lift]`, `[Riser]` |
| Main hook | `[Chorus]`, `[Hook]`, `[Refrain]`, `[Anthem]`, `[Post-Chorus]`, `[Tag]`, `[Final Chorus]` |
| Contrast | `[Bridge]`, `[Middle Eight]`, `[Breakdown]`, `[Interlude]`, `[Break]`, `[Turnaround]`, `[Vamp]` |
| Release | `[Drop]`, `[Dance Break]`, `[Beat Drop]`, `[Switch Up]`, `[Climax]` |
| Instrument feature | `[Solo]`, `[Instrumental Break]`, `[Improvisation]`, `[Cadenza]`, `[Jam]`, `[Riff]` |
| Closing | `[Outro]`, `[Coda]`, `[Finale]`, `[Postlude]`, `[Reprise]`, `[Outro Hook]`, `[Fade Out]`, `[End]` |

A label such as `[Spoken Verse]` remains sung-content text in the data model:
the system cannot guarantee a spoken rather than melodic Suno performance.

## Genre Cue Catalog

The following are candidate **directions** for `cues` or `optional_cues`.
Do not paste every cue into one profile. Choose a few that support its arc.
Only the six profiles listed above ship as selectable presets; the other rows
are vocabulary for building your own profiles.

Each family below lists genre-specific cues in three columns. **Opening** cues
set the texture, **Feature** cues mark builds, breaks and solos, and **Closing**
cues shape the ending. Combine them with the cross-genre palette that follows.

### Electronic: Cyber, Synth and Industrial

| Genre / style | Opening and development | Transition / feature | Closing |
|---|---|---|---|
| Cyberpop / Vocaloid pop | `[Bright Synth Arpeggio]`, `[Vocoder Layer]`, `[Synth Pulse]`, `[Sparkle Synth]`, `[Chiptune Lead]` | `[Heavy Bass Drop]`, `[Glitch Synth Solo]`, `[Chopped Vocals]`, `[Arpeggiated Synth Solo]`, `[Key Change]` | `[Digital Fade]`, `[Synth Sparkle Tail]` |
| Cyberpunk / dark electronic | `[Dark Synth Pulse]`, `[Static Burst]`, `[Dystopian Atmosphere]`, `[Rain And Neon Ambience]`, `[Radio Interference]` | `[Distorted Bass Drop]`, `[Distorted Synth Solo]`, `[Glitch Breakdown]`, `[System Failure]`, `[Data Corruption]` | `[Tape Stop]`, `[Power Down]`, `[Fade Out]` |
| Synthwave / retrowave / outrun | `[Analog Synth Intro]`, `[Arpeggiated Bass]`, `[Gated Reverb Drums]`, `[Night Drive Pads]` | `[Synth Solo]`, `[Gated Snare Fill]`, `[Saxophone Solo]`, `[Key Change]` | `[Neon Synth Fade]`, `[Chorus Pad Tail]` |
| Darksynth / horror synth | `[Ominous Bass Drone]`, `[Pulsing Arpeggio]`, `[Horror Strings]` | `[Aggressive Synth Lead]`, `[Distorted Kick Break]`, `[Detuned Brass Hit]` | `[Dark Drone Out]` |
| Vaporwave / future funk | `[Slowed Sample Intro]`, `[Chopped Disco Loop]`, `[Mall Ambience]` | `[Filter Chop]`, `[Pitch Down]`, `[Sidechain Pump]` | `[Slowed Fade]` |
| Industrial / EBM / aggrotech | `[Mechanical Pulse]`, `[Metallic Percussion]`, `[Factory Noise]`, `[Distorted Vocal Intro]` | `[Industrial Percussion Solo]`, `[Distortion Burst]`, `[Noise Break]`, `[Marching Kick]` | `[Machine Shutdown]`, `[Steam Release]` |
| Electro / electroclash | `[Robotic Vocoder]`, `[808 Cowbell]`, `[Electro Bassline]` | `[Robot Voice Break]`, `[Synth Stab Solo]` | `[Vocoder Sign Off]` |
| Chiptune / 8-bit | `[8 Bit Arpeggio]`, `[Square Wave Lead]`, `[Noise Channel Drums]` | `[Pulse Width Solo]`, `[Level Up Riff]` | `[Game Over Jingle]` |
| Hyperpop / glitch pop | `[Pitched Vocal Chop]`, `[Bubble Synth]`, `[Detuned Supersaw]` | `[Distorted Drop]`, `[Pitch Shift]`, `[Digital Stutter]`, `[Autotune Break]` | `[Bitcrushed Fade]`, `[Hard Cut]` |

### Electronic: Club and Bass Music

| Genre / style | Opening and development | Transition / feature | Closing |
|---|---|---|---|
| Techno / minimal techno | `[Filtered Kick Intro]`, `[Rolling Bass]`, `[Hypnotic Loop]` | `[Filter Sweep]`, `[Percussion Break]`, `[Kick Return]`, `[Acid Line]` | `[DJ Outro]`, `[Kick Only Outro]` |
| Hard techno / warehouse | `[Saturated Kick Intro]`, `[Rumble Bass]`, `[Warehouse Reverb]` | `[Kick Drop]`, `[Industrial Break]`, `[Siren Rise]` | `[Kick Fade]` |
| Acid house / acid techno | `[303 Acid Line]`, `[Resonant Squelch]` | `[Acid Solo]`, `[Resonance Sweep]` | `[Acid Line Fade]` |
| House / deep house | `[Four On The Floor]`, `[Piano Stabs]`, `[Organ Bass]` | `[Piano Break]`, `[Bassline Return]`, `[Diva Vocal Break]` | `[Instrumental Fade]`, `[DJ Outro]` |
| Disco house / nu-disco | `[Filtered Disco Loop]`, `[String Swells]` | `[Filter Open]`, `[Clap Break]` | `[Filtered Fade]` |
| UK garage / 2-step | `[Shuffled Hats]`, `[Chopped Vocal Intro]` | `[Bass Wobble Break]`, `[Vocal Chop Solo]` | `[2 Step Outro]` |
| Trance / progressive trance | `[Atmospheric Intro]`, `[Arpeggio Build]`, `[Gated Pads]` | `[Snare Roll]`, `[Uplifting Drop]`, `[Supersaw Lead]`, `[Euphoric Breakdown]` | `[Reverb Tail]` |
| Psytrance | `[Rolling Psy Bass]`, `[Alien Fx]` | `[Psychedelic Lead]`, `[Acid Squelch Break]` | `[Psy Fade]` |
| Dubstep / riddim / bass music | `[Sub Bass Intro]`, `[Tension Build]`, `[Riser]` | `[Bass Drop]`, `[Wobble Bass]`, `[Half Time Break]`, `[Growl Bass]` | `[Sub Bass Fade]` |
| Future bass / melodic bass | `[Chord Swell]`, `[Vocal Chop Intro]` | `[Supersaw Drop]`, `[Sidechain Chords]` | `[Chord Fade]` |
| Drum and bass / liquid / neurofunk | `[Atmospheric Pads]`, `[Rolling Breakbeat]`, `[Liquid Piano]` | `[Drum Fill]`, `[Reese Bass Drop]`, `[Amen Break]`, `[Neuro Bass Solo]` | `[Breakbeat Outro]` |
| Jungle / breakbeat | `[Chopped Amen]`, `[Ragga Sample]`, `[Sub Bass]` | `[Break Edit]`, `[Time Stretch Fill]` | `[Rewind]` |
| Breakcore / glitch | `[Fragmented Breakbeats]`, `[Stutter Edit]` | `[Glitch Noise]`, `[Rapid Drum Chops]`, `[Chaos]` | `[Abrupt Stop]` |
| Hardstyle / hardcore / gabber | `[Reverse Bass Kick]`, `[Epic Lead Intro]` | `[Kick Drop]`, `[Screech Lead]`, `[Anti Climax]` | `[Kick Roll Ending]` |
| EDM / big room / festival | `[Festival Build]`, `[Crowd Chant]`, `[Snare Riser]` | `[Big Room Drop]`, `[Air Horn]`, `[Build Up]` | `[Festival Outro]` |
| Phonk / drift phonk | `[Cowbell Melody]`, `[Memphis Vocal Sample]` | `[Distorted 808 Drop]`, `[Cowbell Solo]` | `[Slowed Outro]` |

### Pop, R&B and Soul

| Genre / style | Opening and development | Transition / feature | Closing |
|---|---|---|---|
| Mainstream pop / dance-pop | `[Catchy Synth Hook]`, `[Finger Snaps]`, `[Vocal Ad Libs]` | `[Post-Chorus Hook]`, `[Key Change]`, `[Breakdown]` | `[Final Chorus]`, `[Cold Ending]` |
| J-pop / anime pop | `[Piano Intro]`, `[Bright Guitar Riff]`, `[String Hits]` | `[String Lift]`, `[Guitar Solo]`, `[Final Chorus Lift]`, `[Key Change]` | `[Full Band Ending]` |
| City pop | `[Slap Bass Groove]`, `[Electric Piano]`, `[Brass Hits]` | `[Saxophone Solo]`, `[Guitar Cutting]` | `[Fade Out]` |
| K-pop | `[Group Chant]`, `[Trap Hi Hats]`, `[Synth Hook]` | `[Dance Break]`, `[Rap Break]`, `[Beat Switch]` | `[Group Shout Ending]` |
| Electropop / synth-pop | `[Synth Bass Intro]`, `[Drum Machine]` | `[Synth Solo]`, `[Vocoder Break]` | `[Synth Fade]` |
| Indie pop / bedroom pop | `[Lo Fi Guitar]`, `[Soft Vocals]` | `[Dreamy Interlude]`, `[Tape Wobble]` | `[Soft Fade]` |
| Ballad / power ballad | `[Solo Piano]`, `[Soft Strings]` | `[Emotional Swell]`, `[Key Change]`, `[Guitar Solo]` | `[Piano Outro]`, `[Final Held Note]` |
| R&B / neo-soul | `[Electric Piano Intro]`, `[Warm Bass]` | `[Vocal Run]`, `[Guitar Fill]`, `[Harmony Stack]` | `[Vocal Fade]` |
| Soul / Motown | `[Horn Intro]`, `[Tambourine]`, `[Backing Vocals]` | `[Horn Break]`, `[Call And Response]` | `[Ad Lib Fade]` |
| Funk / disco | `[Slap Bass Intro]`, `[Muted Guitar]`, `[String Swells]` | `[Horn Stabs]`, `[Bass Solo]`, `[Drum Break]` | `[Extended Groove]` |
| Gospel / choral | `[Choir Entrance]`, `[Organ Intro]`, `[Hand Claps]` | `[Call And Response]`, `[Choir Swell]`, `[Vamp]` | `[Choir Sustain]`, `[Final Amen]` |

### Rock and Metal

| Genre / style | Opening and development | Transition / feature | Closing |
|---|---|---|---|
| Classic rock | `[Guitar Riff]`, `[Hammond Organ]`, `[Drum Count In]` | `[Guitar Solo]`, `[Organ Solo]`, `[Drum Break]` | `[Big Rock Ending]` |
| Indie / alternative rock | `[Clean Guitar Intro]`, `[Guitar Riff]`, `[Jangly Guitar]` | `[Guitar Solo]`, `[Drum Break]`, `[Full Band Return]` | `[Feedback Fade]` |
| Grunge | `[Quiet Clean Verse]`, `[Sludgy Riff]` | `[Loud Chorus Burst]`, `[Noisy Guitar Solo]` | `[Feedback Ending]` |
| Shoegaze / dream pop | `[Wall Of Guitars]`, `[Reverse Reverb]`, `[Hazy Vocals]` | `[Noise Swell]`, `[Tremolo Guitar]` | `[Wash Of Feedback]` |
| Post-rock | `[Delay Guitar Intro]`, `[Slow Build]` | `[Crescendo]`, `[Tremolo Picking]`, `[Explosive Climax]` | `[Decaying Echoes]` |
| Punk / pop-punk | `[Palm Muted Guitar]`, `[Fast Drum Intro]` | `[Gang Vocal Layer]`, `[Drum Break]`, `[Breakdown]` | `[Abrupt Band Stop]` |
| Emo / post-hardcore | `[Twinkly Guitar]`, `[Screamed Intro]` | `[Screamed Vocals]`, `[Breakdown]`, `[Clean Bridge]` | `[Feedback Ending]` |
| Hard rock / heavy metal | `[Distorted Guitar Riff]`, `[Double Kick Build]` | `[Guitar Solo]`, `[Half Time Breakdown]`, `[Drum Fill]`, `[Dual Guitar Harmony]` | `[Final Power Chord]` |
| Thrash / speed metal | `[Fast Tremolo Riff]`, `[Thrash Beat]` | `[Shred Solo]`, `[Gang Shout]` | `[Machine Gun Ending]` |
| Metalcore / djent | `[Chugging Riff]`, `[Polyrhythmic Groove]` | `[Breakdown]`, `[Clean Chorus]`, `[Screamed Vocals]` | `[Final Breakdown]` |
| Symphonic / power metal | `[Orchestral Intro]`, `[Choir Chant]` | `[Neoclassical Solo]`, `[Keyboard Solo]`, `[Choir Swell]` | `[Orchestral Finale]` |
| Doom / sludge / stoner | `[Slow Heavy Riff]`, `[Fuzz Bass]` | `[Fuzz Guitar Solo]`, `[Crushing Breakdown]` | `[Feedback Drone]` |
| Black metal | `[Blast Beat]`, `[Tremolo Riff]`, `[Atmospheric Keys]` | `[Ambient Break]`, `[Shrieked Vocals]` | `[Cold Wind Fade]` |
| Nu-metal / rap rock | `[Downtuned Riff]`, `[DJ Scratch]` | `[Rap Verse]`, `[Turntable Solo]`, `[Breakdown]` | `[Hard Stop]` |

### Hip-Hop and Urban

| Genre / style | Opening and development | Transition / feature | Closing |
|---|---|---|---|
| Hip-hop / boom bap | `[Beat Intro]`, `[Vinyl Crackle]`, `[Dusty Drums]` | `[Beat Switch]`, `[Drum Break]`, `[Record Scratch]` | `[Beat Outro]` |
| Trap | `[808 Intro]`, `[Hi Hat Roll]`, `[Dark Bells]` | `[808 Drop]`, `[Beat Switch]`, `[Ad Libs]` | `[808 Fade]` |
| Drill (UK / NY) | `[Sliding 808]`, `[Drill Hi Hats]`, `[Choir Sample]` | `[Beat Switch]`, `[Bass Slide]` | `[Beat Cut]` |
| Lo-fi hip-hop / chillhop | `[Vinyl Crackle]`, `[Dusty Piano]`, `[Rain Ambience]` | `[Muted Drum Break]`, `[Jazz Guitar Fill]` | `[Tape Fade]` |
| G-funk / West Coast | `[Talk Box]`, `[Synth Whine Lead]` | `[Talk Box Solo]`, `[Funk Bass Break]` | `[Groove Fade]` |
| Grime | `[Square Wave Bass]`, `[Eski Click]` | `[Reload]`, `[MC Hype]` | `[Rewind]` |
| Spoken word / slam | `[Sparse Piano]`, `[Spoken Word]` | `[Pause]`, `[Rising Intensity]` | `[Silence]` |

### Acoustic, Folk and Roots

| Genre / style | Opening and development | Transition / feature | Closing |
|---|---|---|---|
| Acoustic folk / singer-songwriter | `[Fingerpicked Guitar]`, `[Soft Percussion]`, `[Humming]` | `[Acoustic Guitar Solo]`, `[Harmonica Solo]` | `[Natural Decay]` |
| Indie folk / folk rock | `[Strummed Acoustic]`, `[Stomp And Clap]`, `[Mandolin]` | `[Group Vocals]`, `[Banjo Break]` | `[Gang Vocal Ending]` |
| Celtic / traditional | `[Tin Whistle Intro]`, `[Bodhran]`, `[Fiddle Reel]` | `[Fiddle Solo]`, `[Uilleann Pipes]` | `[Final Reel Flourish]` |
| Country | `[Acoustic Strum]`, `[Telecaster Twang]` | `[Pedal Steel Solo]`, `[Fiddle Solo]`, `[Key Change]` | `[Acoustic Tag Ending]` |
| Bluegrass / Americana | `[Banjo Intro]`, `[Upright Bass]` | `[Banjo Solo]`, `[Dobro Solo]`, `[Mandolin Break]` | `[Shave And A Haircut Ending]` |
| Blues | `[Slide Guitar Intro]`, `[Shuffle Groove]` | `[Blues Guitar Solo]`, `[Harmonica Solo]` | `[Turnaround Ending]` |
| Delta / acoustic blues | `[Bottleneck Slide]`, `[Foot Stomp]` | `[Slide Solo]`, `[Hummed Verse]` | `[Final Slide]` |

### Jazz and Classical

| Genre / style | Opening and development | Transition / feature | Closing |
|---|---|---|---|
| Jazz / swing / big band | `[Piano Intro]`, `[Walking Bass]`, `[Brushed Drums]`, `[Horn Section]` | `[Saxophone Solo]`, `[Piano Solo]`, `[Trading Fours]`, `[Shout Chorus]` | `[Final Ensemble Chord]` |
| Bebop / hard bop | `[Fast Head]`, `[Ride Cymbal]` | `[Trumpet Solo]`, `[Drum Solo]` | `[Head Out]` |
| Smooth jazz / fusion | `[Fretless Bass]`, `[Electric Piano]` | `[Synth Solo]`, `[Guitar Solo]`, `[Odd Meter Break]` | `[Saxophone Fade]` |
| Bossa nova | `[Nylon Guitar]`, `[Soft Brush Percussion]` | `[Flute Solo]`, `[Whispered Vocal]` | `[Gentle Fade]` |
| Cinematic / orchestral / epic | `[String Ostinato]`, `[Low Brass Intro]`, `[Taiko Drums]` | `[Orchestral Swell]`, `[Timpani Roll]`, `[Full Orchestra]`, `[Choir Swell]` | `[Orchestral Decay]` |
| Classical / chamber | `[String Quartet]`, `[Solo Cello]`, `[Harpsichord]` | `[Cadenza]`, `[Pizzicato Section]` | `[Final Cadence]` |
| Opera / musical theatre | `[Overture]`, `[Recitative]` | `[Aria]`, `[Duet]`, `[Ensemble Number]` | `[Curtain Call]` |
| Neoclassical / minimal piano | `[Solo Piano]`, `[Repeating Motif]` | `[Strings Enter]`, `[Gentle Crescendo]` | `[Single Held Note]` |

### Global and Regional

| Genre / style | Opening and development | Transition / feature | Closing |
|---|---|---|---|
| Reggae / dub / ska | `[Offbeat Guitar]`, `[Bass Intro]`, `[Skank Guitar]` | `[Dub Echo]`, `[Horn Break]`, `[Drum And Bass Break]` | `[Tape Echo Fade]` |
| Dancehall | `[Riddim Intro]`, `[Air Horn]` | `[Toasting]`, `[Riddim Switch]` | `[Pull Up]` |
| Reggaeton / Latin pop | `[Dembow Intro]`, `[Latin Percussion]` | `[Percussion Break]`, `[Brass Lift]` | `[Rhythmic Fade]` |
| Salsa / Afro-Cuban | `[Piano Montuno]`, `[Clave Pattern]` | `[Timbale Solo]`, `[Conga Solo]`, `[Horn Response]` | `[Ensemble Hit]` |
| Cumbia / bachata / tango | `[Guiro Groove]`, `[Bachata Guitar]`, `[Bandoneon Intro]` | `[Accordion Solo]`, `[Guitar Requinto]` | `[Final Accent]` |
| Flamenco | `[Flamenco Guitar]`, `[Palmas]` | `[Rasgueado]`, `[Zapateado]`, `[Cante]` | `[Remate]` |
| Afrobeats / amapiano | `[Shaker Groove]`, `[Log Drum Intro]` | `[Percussion Break]`, `[Log Drum Fill]` | `[Groove Fade]` |
| Afrobeat / highlife | `[Horn Riff]`, `[Highlife Guitar]` | `[Saxophone Solo]`, `[Call And Response]` | `[Extended Jam]` |
| Bollywood / Indian fusion | `[Tabla Intro]`, `[Sitar Drone]`, `[Dhol Groove]` | `[Bansuri Solo]`, `[Dhol Break]` | `[Tabla Tihai]` |
| Middle Eastern / Arabic pop | `[Oud Intro]`, `[Darbuka Groove]` | `[Oud Solo]`, `[Ney Flute]` | `[Darbuka Roll Ending]` |
| Traditional Japanese / wa-pop | `[Koto Intro]`, `[Shakuhachi]`, `[Taiko Drums]` | `[Shamisen Solo]`, `[Taiko Break]` | `[Koto Glissando]` |
| C-pop / Chinese traditional fusion | `[Guzheng Intro]`, `[Erhu Melody]` | `[Pipa Solo]`, `[Dizi Flute]` | `[Guzheng Glissando]` |
| Celtic punk / polka | `[Accordion Intro]`, `[Oom Pah Bass]` | `[Accordion Solo]`, `[Gang Shout]` | `[Accelerando Ending]` |

### Ambient, Downtempo and Experimental

| Genre / style | Opening and development | Transition / feature | Closing |
|---|---|---|---|
| Ambient / drone / meditation | `[Atmospheric Pads]`, `[Field Recording]`, `[Singing Bowls]` | `[Ambient Interlude]`, `[Evolving Drone]`, `[Silence]` | `[Long Reverb Tail]`, `[Fade Out]` |
| Downtempo / trip-hop | `[Slow Breakbeat]`, `[Dusty Strings]`, `[Turntable Scratch]` | `[Dub Bass Break]`, `[Moody Interlude]` | `[Vinyl Run Out]` |
| Chillout / lounge | `[Mellow Rhodes]`, `[Soft Percussion]` | `[Flute Solo]`, `[Lounge Break]` | `[Sunset Fade]` |
| New age / spa | `[Harp Glissando]`, `[Ocean Waves]` | `[Soft Choir]`, `[Wind Chimes]` | `[Gentle Release]` |
| Dark ambient / horror | `[Low Rumble]`, `[Distant Screams]`, `[Creaking Textures]` | `[Sudden Stinger]`, `[Dissonant Strings]` | `[Abrupt Silence]` |
| Experimental / noise | `[Room Tone]`, `[Feedback Texture]` | `[Noise Burst]`, `[Granular Cloud]`, `[Silence]` | `[Hard Cut]` |
| IDM / glitch | `[Micro Edits]`, `[Complex Breakbeat]` | `[Granular Break]`, `[Bit Reduction]` | `[Glitch Out]` |
| Video game / soundtrack | `[Title Screen Theme]`, `[Adventure Motif]` | `[Boss Battle]`, `[Victory Fanfare]` | `[Credits Roll]` |

### Cross-Genre Direction Palette

- **Dynamics**: `[Soft Entrance]`, `[Gradual Crescendo]`, `[Sudden Silence]`,
  `[Full Band]`, `[Sparse Arrangement]`, `[Decrescendo]`, `[Stop Time]`,
  `[Swell]`, `[Pause]`, `[Build Up]`, `[Explosive Climax]`.
- **Rhythm**: `[Half Time]`, `[Double Time]`, `[Syncopated Break]`, `[Drum Fill]`,
  `[Percussion Only]`, `[Beat Switch]`, `[Tempo Change]`, `[Snare Roll]`,
  `[Kick Drop Out]`, `[Hand Claps]`, `[Breakbeat]`.
- **Harmony and key**: `[Key Change]`, `[Modulation]`, `[Minor Shift]`,
  `[Chord Swell]`, `[Pedal Tone]`, `[Drone]`.
- **Voice**: `[Whispered Vocal]`, `[Spoken Word]`, `[Harmony Stack]`,
  `[Call And Response]`, `[Choir]`, `[Vocoder]`, `[Vocal Chop]`, `[Ad Libs]`,
  `[Falsetto]`, `[Belted Vocal]`, `[Screamed Vocals]`, `[Rap Verse]`,
  `[Duet]`, `[Male Vocal]`, `[Female Vocal]`, `[A Cappella]`, `[Humming]`.
- **Texture and effects**: `[Filter Sweep]`, `[Tape Echo]`, `[Glitch Noise]`,
  `[Reverb Swell]`, `[Bitcrushed Texture]`, `[Static Burst]`, `[Riser]`,
  `[Reverse Cymbal]`, `[Sidechain Pump]`, `[Pitch Shift]`, `[Tape Stop]`,
  `[Vinyl Crackle]`, `[Radio Filter]`, `[Phone Filter]`.
- **Ambience and sound effects**: `[Rain]`, `[Crowd Cheering]`, `[City Ambience]`,
  `[Thunder]`, `[Heartbeat]`, `[Clock Ticking]`, `[Applause]`.
- **Ending**: `[Fade Out]`, `[Abrupt Stop]`, `[Final Chord]`, `[Reverb Tail]`,
  `[Instrumental Fade]`, `[Silence]`, `[Cold Ending]`, `[Ritardando]`,
  `[Final Held Note]`, `[End]`.

Production/vocal directions are not pronunciation cues. A bracketed Hepburn line
belongs immediately below the corresponding Japanese lyric, not in `cues`.

## Validation and Troubleshooting

- Labels and cues must be nonempty single-line names, without `[]` or `()`.
  The primer is the exception: it must include its surrounding parentheses.
- Profile names, section fields, content types, required booleans, cue arrays,
  and heading collisions are checked when the knowledge loads. Invalid settings
  raise `ValueError`; the app does not silently select a different profile.
- A cue cannot also be a section heading. For example, use the `drop` field's
  heading for `[Drop]`; do not also place `"Drop"` in its `cues` array.
- Old knowledge objects lacking `stage_cues` use the shipped JSON policy for
  compatibility. There is no separate hardcoded mandatory-section list.
- Changing JSON during a console session requires `/reload`. New CLI generation
  runs load it afresh. Metadata records `stage_cue_profile`.
- Edit existing `suno_best_practices.prompt_rules` if custom prose guidance
  contradicts the selected profile.
- Preview before submission:

```bash
bash run.sh --profile core run --rm app \
  python main.py --rei-generate --rei-preview

source .venv/bin/activate && python -m pytest -q \
  tests/test_rei_stage_policy.py tests/test_rei_required_sections.py \
  tests/test_rei_suno_quality.py
```
