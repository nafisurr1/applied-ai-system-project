# 🎧 Model Card: Music Recommender Simulation

## 1. Model Name

**VibeMatch 1.0**, a small content-based music recommender built for a class simulation.

---

## 2. Intended Use

- **What it does:** given one listener's taste profile (favorite genre and mood, a target energy, and optional extras like acousticness, decade, mood tags and a clean-lyrics flag), it scores every song in a 20-song catalog and returns the top 5 with a plain-language reason for each point it gave.
- **Assumptions about the user:** their taste fits in a few labels and numbers, they want songs close to one target energy, and they want the same thing every time (no time of day, no listening history).
- **Who it is for:** classroom exploration of how recommenders turn data into rankings, and where that goes wrong.
- **Not intended for:** real users, real music catalogs, or any decision that matters. It knows nothing about the songs beyond 15 hand-entered attributes, the songs and artists are made up, and it has never been checked against what real people actually like (there is no ground truth).

---

## 3. How the Model Works

Think of it as a judge with a points sheet. For every song, the judge gives:

- **2 points** if the song's genre is the listener's favorite genre, and **1 point** if its mood is their favorite mood.
- **Up to 1.5 points for energy.** A song gets the full 1.5 when its energy equals the listener's target, and fewer points the further away it is. A listener who wants calm music gets the most points from calm songs, not from the loudest ones.
- **Up to 0.5 points each** for being close on any other number the listener cares about: acousticness, positivity (valence), tempo, danceability, popularity, decade and instrumentalness.
- **0.5 points for every mood tag** the song shares with the listener (for example "nostalgic" or "rainy").
- **Minus 3 points** for explicit lyrics, but only if the listener asked for clean songs.

Every time the judge gives points, it writes down why ("genre match: pop (+2.00)"). Then all 20 songs are sorted from most to fewest points, and the top 5 are the recommendations.

**Changes from the starter:** the starter had no logic, so all of this is new. Beyond the required genre/mood/energy recipe, I added closeness scoring for the other numeric features, five new song attributes, four switchable scoring modes (balanced, genre-first, mood-first, energy-focused) and an optional diversity rule. The diversity rule takes 1 point off a song for each song by the same artist already in the list, and 0.5 points for each song in the same genre, so one artist or genre can't fill the whole top 5.

---

## 4. Data

- **Size:** 20 songs in `data/songs.csv`: the 10 starter songs plus 10 I added to cover genres and moods the starter didn't have.
- **Genres (17):** lofi (3 songs), pop (2), and one song each of rock, ambient, jazz, synthwave, indie pop, hip-hop, edm, classical, country, r&b, metal, folk, reggae, latin and blues.
- **Moods (14):** chill (3), happy, intense, relaxed and sad (2 each), and one each of moody, focused, confident, euphoric, melancholic, nostalgic, romantic, angry and playful.
- **Attributes (15):** id, title, artist, genre, mood, energy, tempo_bpm, valence, danceability, acousticness, plus five I added: popularity (0–100), release_decade, mood_tags (2–3 descriptive tags), instrumentalness and explicit.
- **What's missing:** lyrics, language, region, artist popularity over time, and any listening behavior (plays, skips, likes). Nine songs have energy ≥ 0.7 and seven have energy ≤ 0.4, so the catalog leans slightly loud. Most genres have exactly one song, so a single row decides what a fan of that genre sees.

---

## 5. Strengths

- **Clear profiles get clear answers.** Chill Lofi gets three lofi songs and then other calm, acoustic songs (ambient, jazz). Nostalgic Road Trip gets Dusty Highway by a wide margin (6.42 vs 2.66) because genre, mood, decade and all three mood tags line up.
- **Closeness scoring behaves like intuition.** A calm-music fan isn't pushed toward loud songs, and songs that miss the genre but match the feel (Spacewalk Thoughts for Chill Lofi) still rank above unrelated ones.
- **Every score can be audited.** The listed reasons add up to the score (a test checks this for every mode), so it's always possible to see why a song is where it is.
- **It degrades gracefully.** An unknown genre ("k-pop") doesn't crash anything. It falls back to mood and energy and returns the two happy, upbeat pop-adjacent songs first.

---

## 6. Limitations and Bias

**The main weakness I found is that the genre label outweighs the feel of the song, and the match is all-or-nothing.** A "pop / happy" listener gets **Gym Hero** (pop, *intense*, explicit) as their #2 song, above **Rooftop Lights**, which is *happy* and only 0.04 away from their target energy. Rooftop Lights is labeled "indie pop", and "indie pop" isn't the string "pop", so it gets zero genre points. The genre point is worth twice a mood match, so the label wins over the feeling. The same thing happens to the "sad but hyped" listener: Paper Boats (folk, sad, energy 0.30) ranks first even though they asked for energy 0.9, because a genre plus mood match (3.0 points) is worth more than the most energy can ever give (1.5). In plain terms, the system trusts the label more than the music.

Other patterns I saw:

- **A high-energy filter bubble.** Across my 8 test profiles, Gym Hero and Sunrise City each show up in 5 of the 8 top-5 lists, and Laser Bloom and Storm Runner in 4. Part of that is my test set (5 of the 8 profiles ask for energy ≥ 0.8), but it also shows that once the genre and mood points are used up, the rest of the list is filled purely by energy, and the same loud songs fill it every time. The quiet classical track (Moonlit Sonata Redux) never appears in any list.
- **Small genres get one song and then filler.** There is one rock song, so the Deep Intense Rock listener gets Storm Runner and then pop, EDM, metal and even happy pop (Sunrise City at #5) picked only for being loud. Lofi has 3 songs, so lofi fans get the most on-target lists. That's a dataset imbalance, not a choice anyone made.
- **The clean-lyrics option is a penalty, not a filter.** For the clean-workout profile, explicit Gym Hero still ranks #3, because −3 points only pushes it below a few songs in a thin catalog. A parent who asks for clean songs would reasonably expect it to be gone.
- **No sense of "I don't know."** For the unknown-genre profile, the best score is only 2.41 out of a possible 4.5 or more, but the output looks just as confident as for a perfect match.

---

## 7. Evaluation

**What I tested:** 8 profiles, made of 4 normal listeners (the starter pop/happy, High-Energy Pop, Chill Lofi and Deep Intense Rock), one that uses the advanced attributes (Nostalgic Road Trip), and 3 adversarial ones meant to trick the scoring: "sad but hyped" (sad folk at energy 0.9, a combination the catalog barely has), an unknown genre (k-pop), and a "clean workout" (intense pop but no explicit lyrics, where the obvious pick is explicit). I checked whether the top 5 matched my own sense of each listener, read the reasons for anything surprising, and ran two weight experiments plus the diversity rule. 22 pytest tests cover the scoring math, sorting, modes, diversity and the fact that the reasons add up to each score.

**Output for each profile** (`python -m src.main`, balanced mode):

*Starter: pop / happy*

```
=== Starter: pop / happy ===
Profile: genre=pop, mood=happy, energy=0.8
Mode: balanced (default recipe: genre 2.0, mood 1.0, energy up to 1.5)
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| #  | Song                               | Genre / mood         | Score | Why                                                        |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 1  | Sunrise City — Neon Echo           | pop / happy          | 4.47  | genre match: pop (+2.00)                                   |
|    |                                    |                      |       | mood match: happy (+1.00)                                  |
|    |                                    |                      |       | energy 0.82 vs target 0.8 (+1.47)                          |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 2  | Gym Hero — Max Pulse               | pop / intense        | 3.30  | genre match: pop (+2.00)                                   |
|    |                                    |                      |       | energy 0.93 vs target 0.8 (+1.30)                          |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 3  | Rooftop Lights — Indigo Parade     | indie pop / happy    | 2.44  | mood match: happy (+1.00)                                  |
|    |                                    |                      |       | energy 0.76 vs target 0.8 (+1.44)                          |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 4  | Fuego Lento — La Marea             | latin / playful      | 1.50  | energy 0.8 vs target 0.8 (+1.50)                           |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 5  | Concrete Crown — Kilo Verse        | hip-hop / confident  | 1.47  | energy 0.78 vs target 0.8 (+1.47)                          |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
```

*High-Energy Pop*

```
=== High-Energy Pop ===
Profile: genre=pop, mood=happy, energy=0.9, danceability=0.85
Mode: balanced (default recipe: genre 2.0, mood 1.0, energy up to 1.5)
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| #  | Song                               | Genre / mood         | Score | Why                                                        |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 1  | Sunrise City — Neon Echo           | pop / happy          | 4.85  | genre match: pop (+2.00)                                   |
|    |                                    |                      |       | mood match: happy (+1.00)                                  |
|    |                                    |                      |       | energy 0.82 vs target 0.9 (+1.38)                          |
|    |                                    |                      |       | danceability 0.79 vs target 0.85 (+0.47)                   |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 2  | Gym Hero — Max Pulse               | pop / intense        | 3.94  | genre match: pop (+2.00)                                   |
|    |                                    |                      |       | energy 0.93 vs target 0.9 (+1.46)                          |
|    |                                    |                      |       | danceability 0.88 vs target 0.85 (+0.48)                   |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 3  | Rooftop Lights — Indigo Parade     | indie pop / happy    | 2.77  | mood match: happy (+1.00)                                  |
|    |                                    |                      |       | energy 0.76 vs target 0.9 (+1.29)                          |
|    |                                    |                      |       | danceability 0.82 vs target 0.85 (+0.48)                   |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 4  | Laser Bloom — Pulse Theory         | edm / euphoric       | 1.89  | energy 0.95 vs target 0.9 (+1.43)                          |
|    |                                    |                      |       | danceability 0.92 vs target 0.85 (+0.46)                   |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 5  | Storm Runner — Voltline            | rock / intense       | 1.89  | energy 0.91 vs target 0.9 (+1.48)                          |
|    |                                    |                      |       | danceability 0.66 vs target 0.85 (+0.41)                   |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
```

*Chill Lofi*

```
=== Chill Lofi ===
Profile: genre=lofi, mood=chill, energy=0.35, likes_acoustic=True
Mode: balanced (default recipe: genre 2.0, mood 1.0, energy up to 1.5)
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| #  | Song                               | Genre / mood         | Score | Why                                                        |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 1  | Library Rain — Paper Lanterns      | lofi / chill         | 4.97  | genre match: lofi (+2.00)                                  |
|    |                                    |                      |       | mood match: chill (+1.00)                                  |
|    |                                    |                      |       | energy 0.35 vs target 0.35 (+1.50)                         |
|    |                                    |                      |       | acousticness 0.86 vs target 0.8 (+0.47)                    |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 2  | Midnight Coding — LoRoom           | lofi / chill         | 4.85  | genre match: lofi (+2.00)                                  |
|    |                                    |                      |       | mood match: chill (+1.00)                                  |
|    |                                    |                      |       | energy 0.42 vs target 0.35 (+1.40)                         |
|    |                                    |                      |       | acousticness 0.71 vs target 0.8 (+0.45)                    |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 3  | Focus Flow — LoRoom                | lofi / focused       | 3.92  | genre match: lofi (+2.00)                                  |
|    |                                    |                      |       | energy 0.4 vs target 0.35 (+1.42)                          |
|    |                                    |                      |       | acousticness 0.78 vs target 0.8 (+0.49)                    |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 4  | Spacewalk Thoughts — Orbit Bloom   | ambient / chill      | 2.83  | mood match: chill (+1.00)                                  |
|    |                                    |                      |       | energy 0.28 vs target 0.35 (+1.40)                         |
|    |                                    |                      |       | acousticness 0.92 vs target 0.8 (+0.44)                    |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 5  | Coffee Shop Stories — Slow Stereo  | jazz / relaxed       | 1.93  | energy 0.37 vs target 0.35 (+1.47)                         |
|    |                                    |                      |       | acousticness 0.89 vs target 0.8 (+0.46)                    |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
```

*Deep Intense Rock*

```
=== Deep Intense Rock ===
Profile: genre=rock, mood=intense, energy=0.92, likes_acoustic=False
Mode: balanced (default recipe: genre 2.0, mood 1.0, energy up to 1.5)
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| #  | Song                               | Genre / mood         | Score | Why                                                        |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 1  | Storm Runner — Voltline            | rock / intense       | 4.93  | genre match: rock (+2.00)                                  |
|    |                                    |                      |       | mood match: intense (+1.00)                                |
|    |                                    |                      |       | energy 0.91 vs target 0.92 (+1.48)                         |
|    |                                    |                      |       | acousticness 0.1 vs target 0.2 (+0.45)                     |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 2  | Gym Hero — Max Pulse               | pop / intense        | 2.91  | mood match: intense (+1.00)                                |
|    |                                    |                      |       | energy 0.93 vs target 0.92 (+1.48)                         |
|    |                                    |                      |       | acousticness 0.05 vs target 0.2 (+0.42)                    |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 3  | Laser Bloom — Pulse Theory         | edm / euphoric       | 1.87  | energy 0.95 vs target 0.92 (+1.46)                         |
|    |                                    |                      |       | acousticness 0.03 vs target 0.2 (+0.41)                    |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 4  | Iron Verdict — Grave Signal        | metal / angry        | 1.84  | energy 0.97 vs target 0.92 (+1.43)                         |
|    |                                    |                      |       | acousticness 0.04 vs target 0.2 (+0.42)                    |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 5  | Sunrise City — Neon Echo           | pop / happy          | 1.84  | energy 0.82 vs target 0.92 (+1.35)                         |
|    |                                    |                      |       | acousticness 0.18 vs target 0.2 (+0.49)                    |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
```

*Nostalgic Road Trip*

```
=== Nostalgic Road Trip ===
Profile: genre=country, mood=nostalgic, energy=0.6, release_decade=1990, mood_tags=['nostalgic', 'warm', 'open-road'], allow_explicit=False
Mode: balanced (default recipe: genre 2.0, mood 1.0, energy up to 1.5)
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| #  | Song                               | Genre / mood         | Score | Why                                                        |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 1  | Dusty Highway — Cal Turner         | country / nostalgic  | 6.42  | genre match: country (+2.00)                               |
|    |                                    |                      |       | mood match: nostalgic (+1.00)                              |
|    |                                    |                      |       | energy 0.55 vs target 0.6 (+1.43)                          |
|    |                                    |                      |       | release_decade 1990 vs target 1990 (+0.50)                 |
|    |                                    |                      |       | mood tags nostalgic, open-road, warm (+1.50)               |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 2  | Coffee Shop Stories — Slow Stereo  | jazz / relaxed       | 2.66  | energy 0.37 vs target 0.6 (+1.16)                          |
|    |                                    |                      |       | release_decade 1990 vs target 1990 (+0.50)                 |
|    |                                    |                      |       | mood tags nostalgic, warm (+1.00)                          |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 3  | Velvet Hours — Nia Rose            | r&b / romantic       | 2.22  | energy 0.48 vs target 0.6 (+1.32)                          |
|    |                                    |                      |       | release_decade 2000 vs target 1990 (+0.40)                 |
|    |                                    |                      |       | mood tags warm (+0.50)                                     |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 4  | Night Drive Loop — Neon Echo       | synthwave / moody    | 2.17  | energy 0.75 vs target 0.6 (+1.27)                          |
|    |                                    |                      |       | release_decade 1980 vs target 1990 (+0.40)                 |
|    |                                    |                      |       | mood tags nostalgic (+0.50)                                |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 5  | Island Time — Sunny Dub            | reggae / relaxed     | 2.15  | energy 0.5 vs target 0.6 (+1.35)                           |
|    |                                    |                      |       | release_decade 1970 vs target 1990 (+0.30)                 |
|    |                                    |                      |       | mood tags warm (+0.50)                                     |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
```

*Edge case: sad but hyped*

```
=== Edge case: sad but hyped ===
Profile: genre=folk, mood=sad, energy=0.9
Mode: balanced (default recipe: genre 2.0, mood 1.0, energy up to 1.5)
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| #  | Song                               | Genre / mood         | Score | Why                                                        |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 1  | Paper Boats — Willow & Pine        | folk / sad           | 3.60  | genre match: folk (+2.00)                                  |
|    |                                    |                      |       | mood match: sad (+1.00)                                    |
|    |                                    |                      |       | energy 0.3 vs target 0.9 (+0.60)                           |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 2  | Rainy Day Blues — Hollow Creek     | blues / sad          | 1.72  | mood match: sad (+1.00)                                    |
|    |                                    |                      |       | energy 0.38 vs target 0.9 (+0.72)                          |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 3  | Storm Runner — Voltline            | rock / intense       | 1.48  | energy 0.91 vs target 0.9 (+1.48)                          |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 4  | Gym Hero — Max Pulse               | pop / intense        | 1.46  | energy 0.93 vs target 0.9 (+1.46)                          |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 5  | Laser Bloom — Pulse Theory         | edm / euphoric       | 1.43  | energy 0.95 vs target 0.9 (+1.43)                          |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
```

*Edge case: unknown genre*

```
=== Edge case: unknown genre ===
Profile: genre=k-pop, mood=happy, energy=0.7
Mode: balanced (default recipe: genre 2.0, mood 1.0, energy up to 1.5)
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| #  | Song                               | Genre / mood         | Score | Why                                                        |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 1  | Rooftop Lights — Indigo Parade     | indie pop / happy    | 2.41  | mood match: happy (+1.00)                                  |
|    |                                    |                      |       | energy 0.76 vs target 0.7 (+1.41)                          |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 2  | Sunrise City — Neon Echo           | pop / happy          | 2.32  | mood match: happy (+1.00)                                  |
|    |                                    |                      |       | energy 0.82 vs target 0.7 (+1.32)                          |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 3  | Night Drive Loop — Neon Echo       | synthwave / moody    | 1.42  | energy 0.75 vs target 0.7 (+1.42)                          |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 4  | Concrete Crown — Kilo Verse        | hip-hop / confident  | 1.38  | energy 0.78 vs target 0.7 (+1.38)                          |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 5  | Fuego Lento — La Marea             | latin / playful      | 1.35  | energy 0.8 vs target 0.7 (+1.35)                           |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
```

*Edge case: clean workout*

```
=== Edge case: clean workout ===
Profile: genre=pop, mood=intense, energy=0.9, allow_explicit=False
Mode: balanced (default recipe: genre 2.0, mood 1.0, energy up to 1.5)
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| #  | Song                               | Genre / mood         | Score | Why                                                        |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 1  | Sunrise City — Neon Echo           | pop / happy          | 3.38  | genre match: pop (+2.00)                                   |
|    |                                    |                      |       | energy 0.82 vs target 0.9 (+1.38)                          |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 2  | Storm Runner — Voltline            | rock / intense       | 2.48  | mood match: intense (+1.00)                                |
|    |                                    |                      |       | energy 0.91 vs target 0.9 (+1.48)                          |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 3  | Gym Hero — Max Pulse               | pop / intense        | 1.46  | genre match: pop (+2.00)                                   |
|    |                                    |                      |       | mood match: intense (+1.00)                                |
|    |                                    |                      |       | energy 0.93 vs target 0.9 (+1.46)                          |
|    |                                    |                      |       | explicit lyrics (-3.00)                                    |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 4  | Laser Bloom — Pulse Theory         | edm / euphoric       | 1.43  | energy 0.95 vs target 0.9 (+1.43)                          |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 5  | Fuego Lento — La Marea             | latin / playful      | 1.35  | energy 0.8 vs target 0.9 (+1.35)                           |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
```

**Comparing profiles (what changed, and does it make sense?):**

| Profiles compared | What changed | Why it makes sense |
|-------------------|--------------|--------------------|
| Starter pop/happy vs High-Energy Pop | Same top 3 (Sunrise City, Gym Hero, Rooftop Lights), but #4 and #5 swap from Fuego Lento and Concrete Crown (energy ~0.8) to Laser Bloom and Storm Runner (energy ~0.9+). | Raising the energy target to 0.9 and adding danceability 0.85 rewards the loudest, most danceable songs once the pop/happy matches run out. |
| High-Energy Pop vs Chill Lofi | No overlap at all. Lofi gets low-energy, acoustic songs (Library Rain, Midnight Coding, Spacewalk Thoughts) instead of energetic pop. | The energy target goes from 0.9 to 0.35 and `likes_acoustic` adds points for acoustic songs, so the whole list moves to the quiet end of the catalog. |
| Chill Lofi vs Deep Intense Rock | Opposite ends: everything in Rock's top 5 has energy above 0.8 and low acousticness; everything in Lofi's is below 0.45 energy with acousticness 0.7+. | Both energy and acousticness targets flip. This pair shows the numeric features doing real work, not just the labels. |
| Starter pop/happy vs Deep Intense Rock | Gym Hero shows up in both: #2 for pop because it is pop, #2 for rock because it is intense. | Gym Hero is the only song that is both high-energy and matches one label for each profile. This is the clearest example of one song gaming the point system from two directions. |
| Deep Intense Rock vs Edge case: clean workout | Both want intense, loud music, but the clean profile drops Gym Hero from #2 (for rock) to #3 with a −3.00 explicit note, and Sunrise City (clean, pop) takes #1. | The explicit penalty works as designed, but because it's a penalty rather than a filter, the explicit song still makes the list. |
| Chill Lofi vs Nostalgic Road Trip | Both are mid-to-low energy, but Road Trip pulls in Coffee Shop Stories and Velvet Hours through decade (1990s) and the "warm" and "nostalgic" tags instead of lofi labels. | The advanced attributes let two calm listeners get different lists based on era and vibe, which the original three features couldn't tell apart. |
| Starter pop/happy vs Edge case: unknown genre | With "k-pop" (not in the catalog) the genre points vanish, so Rooftop Lights (indie pop, happy) moves up from #3 to #1, and every score is lower (best 2.41 vs 4.47). | Without a genre match the ranking is decided by mood and energy alone, which happens to fix the indie-pop problem but also shows that the system can't tell the user when nothing really fits. |
| High-Energy Pop vs Edge case: sad but hyped | Both want energy ~0.9 and share Gym Hero, Laser Bloom and Storm Runner, but the sad profile's #1 is quiet Paper Boats (energy 0.30). | The genre + mood match (3.0 points) beats the 0.9 points of energy that Paper Boats loses. The labels win when the preferences conflict. |

**Why does "Gym Hero" keep showing up for people who just want happy pop?** In plain language: the recommender gives 2 points just for being labeled pop, and Gym Hero is labeled pop. It is also very energetic, and the starter listener wants energy 0.8, so it collects nearly all of the energy points too. The song that actually sounds like what they want, Rooftop Lights, is labeled "indie pop". The recommender doesn't know that's basically pop, so Rooftop Lights only gets the happy-mood point. Gym Hero is happy-pop-adjacent on paper, not in feel.

**Experiments** (`python -m src.experiments`):

```
=== Starter: pop / happy ===
  baseline      Sunrise City | Gym Hero | Rooftop Lights | Fuego Lento | Concrete Crown
  weight shift  Sunrise City | Rooftop Lights | Gym Hero | Fuego Lento | Concrete Crown   <- changed
  no mood       Sunrise City | Gym Hero | Fuego Lento | Concrete Crown | Rooftop Lights   <- changed

=== High-Energy Pop ===
  baseline      Sunrise City | Gym Hero | Rooftop Lights | Laser Bloom | Storm Runner
  weight shift  Sunrise City | Gym Hero | Rooftop Lights | Storm Runner | Laser Bloom   <- changed
  no mood       Gym Hero | Sunrise City | Laser Bloom | Storm Runner | Fuego Lento   <- changed

=== Chill Lofi ===
  baseline      Library Rain | Midnight Coding | Focus Flow | Spacewalk Thoughts | Coffee Shop Stories
  weight shift  Library Rain | Midnight Coding | Focus Flow | Spacewalk Thoughts | Coffee Shop Stories
  no mood       Library Rain | Focus Flow | Midnight Coding | Coffee Shop Stories | Rainy Day Blues   <- changed

=== Deep Intense Rock ===
  baseline      Storm Runner | Gym Hero | Laser Bloom | Iron Verdict | Sunrise City
  weight shift  Storm Runner | Gym Hero | Laser Bloom | Iron Verdict | Sunrise City
  no mood       Storm Runner | Gym Hero | Laser Bloom | Iron Verdict | Sunrise City

=== Nostalgic Road Trip ===
  baseline      Dusty Highway | Coffee Shop Stories | Velvet Hours | Night Drive Loop | Island Time
  weight shift  Dusty Highway | Coffee Shop Stories | Velvet Hours | Island Time | Night Drive Loop   <- changed
  no mood       Dusty Highway | Coffee Shop Stories | Velvet Hours | Night Drive Loop | Island Time

=== Edge case: sad but hyped ===
  baseline      Paper Boats | Rainy Day Blues | Storm Runner | Gym Hero | Laser Bloom
  weight shift  Paper Boats | Storm Runner | Gym Hero | Laser Bloom | Iron Verdict   <- changed
  no mood       Paper Boats | Storm Runner | Gym Hero | Laser Bloom | Iron Verdict   <- changed

=== Edge case: unknown genre ===
  baseline      Rooftop Lights | Sunrise City | Night Drive Loop | Concrete Crown | Fuego Lento
  weight shift  Rooftop Lights | Sunrise City | Night Drive Loop | Concrete Crown | Fuego Lento
  no mood       Night Drive Loop | Rooftop Lights | Concrete Crown | Fuego Lento | Sunrise City   <- changed

=== Edge case: clean workout ===
  baseline      Sunrise City | Storm Runner | Gym Hero | Laser Bloom | Fuego Lento
  weight shift  Storm Runner | Sunrise City | Laser Bloom | Fuego Lento | Rooftop Lights   <- changed
  no mood       Sunrise City | Storm Runner | Laser Bloom | Fuego Lento | Rooftop Lights   <- changed
```

- **Weight shift (energy doubled to 3.0, genre halved to 1.0).** For the starter pop/happy profile, Rooftop Lights moves above Gym Hero (scores below), which matches my intuition better. For "sad but hyped", Rainy Day Blues drops out and loud songs fill #2–#5, leaving Paper Boats as the only sad song. That is more *accurate* to the energy request, but the "sad" half of the request now barely counts. So the shift made some lists more accurate and others just different. It trades one kind of dominance (labels) for another (energy).
- **Feature removal (mood check off).** Six of the eight profiles change. For Chill Lofi, Rainy Day Blues (sad blues) sneaks in at #5 because it's quiet and acoustic. For High-Energy Pop, Gym Hero takes #1 from Sunrise City. Mood is doing useful work: it's the only thing separating "calm and happy" from "calm and sad".
- **Diversity rule.** For Chill Lofi, the second LoRoom song (Focus Flow) drops from #3 to #5, and Spacewalk Thoughts (ambient) and Coffee Shop Stories (jazz) move up. The list is more varied but slightly less "lofi". That trade-off seems right for a discovery playlist and wrong for a "just give me lofi" listener, which is why it's an option and not the default.

Weight shift, starter profile, top 3 (`python -m src.main --profile "Starter: pop / happy" --mode energy-focused --k 3`):

```
Loaded songs: 20

=== Starter: pop / happy ===
Profile: genre=pop, mood=happy, energy=0.8
Mode: energy-focused (weight-shift experiment: energy doubled, genre halved)
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| #  | Song                               | Genre / mood         | Score | Why                                                        |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 1  | Sunrise City — Neon Echo           | pop / happy          | 4.94  | genre match: pop (+1.00)                                   |
|    |                                    |                      |       | mood match: happy (+1.00)                                  |
|    |                                    |                      |       | energy 0.82 vs target 0.8 (+2.94)                          |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 2  | Rooftop Lights — Indigo Parade     | indie pop / happy    | 3.88  | mood match: happy (+1.00)                                  |
|    |                                    |                      |       | energy 0.76 vs target 0.8 (+2.88)                          |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 3  | Gym Hero — Max Pulse               | pop / intense        | 3.61  | genre match: pop (+1.00)                                   |
|    |                                    |                      |       | energy 0.93 vs target 0.8 (+2.61)                          |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
```

**What surprised me:** how often one or two songs carried several unrelated profiles, and how convincing the explanations look even when the ranking is wrong for the listener. "genre match: pop (+2.00)" reads like a good reason until you notice the song is the wrong mood.

---

## 8. Future Work

1. **Partial genre matches.** Treat related genres ("indie pop" and "pop", "metal" and "rock") as partly matching, for example 1.0 point instead of 0 or 2, using a small genre-similarity table. This targets the biggest weakness above.
2. **Make clean lyrics a hard filter**, and show a confidence note when the best score is low ("no strong matches for k-pop; here's what's closest by mood and energy").
3. **Use behavior, not just labels.** Even a fake listening history (likes and skips) would allow a simple collaborative-filtering signal, which would catch "people who like Rooftop Lights also like Sunrise City" without relying on genre strings.
4. **Turn diversity on for longer lists**, and cap any single song's appearances across a user's daily mixes so the high-energy bubble doesn't form.

---

## 9. Personal Reflection

**Biggest learning moment.** The "Gym Hero for happy pop" result. The math was doing exactly what I told it to, and every reason it printed was true, but the recommendation was still wrong for the listener. A recommender can be correct and explainable and still not be good. "Good" depends on whether the features capture what people actually care about, and an exact-match genre string doesn't.

**How AI helped, and when I double-checked.** I used one AI coding assistant in agent mode. It explained collaborative vs. content-based filtering, suggested the closeness formula (`1 − |difference|`) so energy rewards being near the target instead of being higher, wrote the scoring and ranking code, expanded the catalog, and suggested adversarial profiles like "sad but hyped". I double-checked it in three places. First, the starter's `main.py` imported `recommender` directly, which crashes under the required `python -m src.main`, so the import had to change to `src.recommender`. Second, I wrote a test that adds up the points in every explanation and compares them to the score, so the explanations can't drift from the math, including after diversity penalties. Third, I planted small bugs (closeness rewarding bigger values, sorting ascending, ignoring the diversity penalty, inverting `likes_acoustic`) to confirm the tests actually fail when the logic is wrong. All eight planted bugs were caught.

**What surprised me about simple algorithms.** A points sheet with five rules already *feels* like a recommendation. The Chill Lofi and Road Trip lists are genuinely what I'd pick. That's also what makes it misleading: the confident ranked list and tidy reasons look the same whether the system has a great match or is just filling slots with whatever is loud.

**What I'd try next.** Partial genre matching and a "no strong match" warning first, since they fix the two failures I could actually see, then a fake listening history to try a collaborative signal and compare the two approaches on the same profiles.
