"""ITF extension, stage I4: which Sackmann player a Flashscore player (or a TennisExplorer ranking row) is.

Names are compared as sets of name tokens, accents removed, so word order does not matter: Flashscore's slug
"dlimi-yassine", TennisExplorer's "Dlimi Yassine" and Sackmann's "Yassine Dlimi" are one key. A number in a slug
("rodrigues-pedro-2006", Flashscore's way of telling namesakes apart) is not part of the name.

A Flashscore player resolves, within a tour, as:

    verified          exactly one Sackmann player with that name key among players active since 2015 (or born
                      since 1990), and no country disagreement
    verified_country  several namesakes, exactly one from the player's country
    ambiguous         several namesakes and the country does not settle it: not forecast, listed for review
    conflict          one namesake, but from a different country: not forecast, listed for review
    new_player        no Sackmann player of that name: a new player, with a stable id of their own

Country names (Flashscore and TennisExplorer write them in English, alike) are mapped to Sackmann's IOC codes from
the data, not by hand: every player matched by a unique name votes for (country, IOC), and a country takes the IOC
code with at least 3 votes and 80% of them. "World" (Flashscore's label for neutral athletes, Russian and Belarusian
alike) carries no country information: it neither votes nor decides.

A new player's id is negative, derived from the Flashscore player id (the convention the main-tour system uses for
players without a Sackmann id), so it never collides with a Sackmann id and stays the same across runs.
"""
import hashlib
import re
import unicodedata
from collections import Counter, defaultdict

COUNTRY_VOTES, COUNTRY_SHARE = 3, 0.8
NO_COUNTRY = {"", "World", "Neutral"}     # Flashscore's label for neutral athletes (Russia and Belarus alike)
ACTIVE_DOB = 19900101
RESOLVED = ("verified", "verified_country", "new_player")


def tokens(text):
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii").lower()
    return [t for t in re.split(r"[^a-z0-9]+", text) if t and not t.isdigit()]


def name_key(text):
    return frozenset(tokens(text))


def provider_id(provider, value):
    """A stable negative id for a player known only to a provider."""
    return -int(hashlib.sha256(f"{provider}:{value}".encode()).hexdigest()[:12], 16)


class Identities:
    def __init__(self, players, active=None):
        """`players`: {(tour, id): {"name", "ioc", "dob"}} (load.load_players); `active`: set of (tour, id) seen in
        matches since 2015 (namesakes who retired long ago are not candidates)."""
        self.players = players
        self.by_key = defaultdict(list)
        for (tour, pid), p in players.items():
            if active is None or (tour, pid) in active or (p.get("dob") or 0) >= ACTIVE_DOB:
                self.by_key[(tour, name_key(p["name"]))].append(pid)
        self.countries = {}
        self.cache = {}

    def candidates(self, tour, text):
        return self.by_key.get((tour, name_key(text)), [])

    def learn_countries(self, people):
        """`people`: [(tour, name text, country)]. Fills self.countries {country: IOC} from unique-name matches."""
        votes = defaultdict(Counter)
        for tour, text, country in people:
            found = self.candidates(tour, text)
            if len(found) == 1 and country and country not in NO_COUNTRY:
                votes[country][self.players[(tour, found[0])]["ioc"]] += 1
        for country, counts in votes.items():
            ioc, n = counts.most_common(1)[0]
            if n >= COUNTRY_VOTES and n / sum(counts.values()) >= COUNTRY_SHARE:
                self.countries[country] = ioc
        return self.countries

    def resolve(self, tour, provider, provider_player_id, text, country):
        """(status, player id or None)."""
        key = (tour, provider, provider_player_id)
        if key in self.cache:
            return self.cache[key]
        found = self.candidates(tour, text)
        ioc = None if country in NO_COUNTRY else self.countries.get(country)
        if len(found) == 1:
            own = self.players[(tour, found[0])]["ioc"]
            result = ("conflict", None) if ioc and own and own != ioc else ("verified", found[0])
        elif len(found) > 1:
            same = [pid for pid in found if ioc and self.players[(tour, pid)]["ioc"] == ioc]
            result = ("verified_country", same[0]) if len(same) == 1 else ("ambiguous", None)
        else:
            result = ("new_player", provider_id(provider, provider_player_id))
        self.cache[key] = result
        return result
