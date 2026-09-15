"""Short music-taste quiz. Each answer adds weight to one or more genres."""

GENRES = {
    "pop": {"label": "Pop", "emoji": "🎤", "deezer_id": 132, "blurb": "Big hooks, bigger choruses."},
    "rock": {"label": "Rock", "emoji": "🎸", "deezer_id": 152, "blurb": "Guitars up, volume up."},
    "hiphop": {"label": "Rap / Hip Hop", "emoji": "🔥", "deezer_id": 116, "blurb": "Bars, beats and bounce."},
    "dance": {"label": "Dance / Electro", "emoji": "💃", "deezer_id": 113, "blurb": "Built for the floor."},
    "rnb": {"label": "R&B / Soul", "emoji": "💜", "deezer_id": 165, "blurb": "Smooth, soulful, sultry."},
    "alternative": {"label": "Indie / Alternative", "emoji": "🌙", "deezer_id": 85, "blurb": "Left of the dial."},
    "country": {"label": "Country / Folk", "emoji": "🤠", "deezer_id": 84, "blurb": "Stories, steel and heart."},
    "latin": {"label": "Latin / Reggaeton", "emoji": "🌶️", "deezer_id": 197, "blurb": "Ritmo all night."},
    "metal": {"label": "Metal", "emoji": "🤘", "deezer_id": 464, "blurb": "Loud. Louder. Loudest."},
    "jazz": {"label": "Jazz / Blues", "emoji": "🎷", "deezer_id": 129, "blurb": "Late night, low light."},
    "classics": {"label": "Films / Musicals", "emoji": "🎬", "deezer_id": 173, "blurb": "Showtunes and soundtracks."},
}

QUIZ = [
    {
        "q": "It's your turn at karaoke. What are you grabbing the mic for?",
        "options": [
            {"text": "A massive sing-along chorus everyone knows", "w": {"pop": 3, "rock": 1}},
            {"text": "Something I can rap every word of", "w": {"hiphop": 3, "rnb": 1}},
            {"text": "A slow burner I can really belt", "w": {"rnb": 2, "pop": 1, "classics": 1}},
            {"text": "A wall of guitars and a scream at the end", "w": {"rock": 2, "metal": 2}},
            {"text": "A showtune with full choreography", "w": {"classics": 3, "pop": 1}},
        ],
    },
    {
        "q": "Pick a night out.",
        "options": [
            {"text": "A sweaty club until sunrise", "w": {"dance": 3, "latin": 1}},
            {"text": "A dive bar with a live band", "w": {"rock": 2, "alternative": 1, "country": 1}},
            {"text": "A rooftop with cocktails and a DJ", "w": {"rnb": 2, "hiphop": 1, "pop": 1}},
            {"text": "A salsa bar or street party", "w": {"latin": 3, "dance": 1}},
            {"text": "A dim jazz club or a musical", "w": {"jazz": 2, "classics": 2}},
        ],
    },
    {
        "q": "Which of these sounds most like your playlist?",
        "options": [
            {"text": "Taylor Swift, Dua Lipa, Harry Styles", "w": {"pop": 3}},
            {"text": "Kendrick, Drake, Nicki Minaj", "w": {"hiphop": 3}},
            {"text": "Arctic Monkeys, The Killers, Phoebe Bridgers", "w": {"alternative": 3, "rock": 1}},
            {"text": "Bad Bunny, Shakira, Karol G", "w": {"latin": 3}},
            {"text": "Metallica, Foo Fighters, Queen", "w": {"metal": 2, "rock": 2}},
            {"text": "Luke Combs, Kacey Musgraves, Johnny Cash", "w": {"country": 3}},
        ],
    },
    {
        "q": "Road trip. Who controls the aux?",
        "options": [
            {"text": "Me — 80s and 90s throwbacks only", "w": {"pop": 2, "rock": 1, "dance": 1}},
            {"text": "Whoever has the deepest cuts", "w": {"alternative": 2, "jazz": 1, "rnb": 1}},
            {"text": "Anything with a beat you can feel", "w": {"dance": 2, "hiphop": 1, "latin": 1}},
            {"text": "Windows down, singing our hearts out to ballads", "w": {"country": 1, "pop": 1, "classics": 1, "rnb": 1}},
            {"text": "Turn it up until the speakers hurt", "w": {"metal": 2, "rock": 2}},
        ],
    },
]


def score_quiz(answers: list[int]) -> dict:
    scores = {g: 0 for g in GENRES}
    for qi, ai in enumerate(answers[: len(QUIZ)]):
        options = QUIZ[qi]["options"]
        if 0 <= ai < len(options):
            for g, w in options[ai]["w"].items():
                scores[g] += w
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    primary = ranked[0][0] if ranked[0][1] > 0 else "pop"
    secondary = [g for g, s in ranked[1:3] if s > 0]
    return {"primary": primary, "secondary": secondary, "scores": scores}
