from __future__ import annotations

import os
import textwrap
from typing import NamedTuple
from urllib.parse import urlparse

import pytest


def xfail_on_ci(msg: str) -> pytest.MarkDecorator:
    return pytest.mark.xfail(
        bool(os.environ.get("GITHUB_ACTIONS")),
        reason=msg,
        raises=AssertionError,
    )


class LyricsPage(NamedTuple):
    """Lyrics page representation for integrated tests."""

    url: str
    lyrics: str
    artist: str = "The Beatles"
    track_title: str = "Lady Madonna"
    url_title: str | None = None  # only relevant to the Google backend
    marks: list[str] = []  # markers for pytest.param  # noqa: RUF012

    def __str__(self) -> str:
        """Return name of this test case."""
        return f"{self.backend}-{self.source}"

    @classmethod
    def make(cls, url, lyrics, *args, **kwargs):
        return cls(url, textwrap.dedent(lyrics).strip(), *args, **kwargs)

    @property
    def root_url(self) -> str:
        return urlparse(self.url).netloc

    @property
    def source(self) -> str:
        return self.root_url.replace("www.", "").split(".")[0]

    @property
    def backend(self) -> str:
        if (source := self.source) in {"genius", "tekstowo", "lrclib"}:
            return source
        return "google"


lyrics_pages = [
    LyricsPage.make(
        "http://www.absolutelyrics.com/lyrics/view/the_beatles/lady_madonna",
        """
        The Beatles - Lady Madonna

        Lady Madonna, children at your feet.
        Wonder how you manage to make ends meet.
        Who finds the money? When you pay the rent?
        Did you think that money was heaven sent?
        Friday night arrives without a suitcase.
        Sunday morning creep in like a nun.
        Monday's child has learned to tie his bootlace.
        See how they run.
        Lady Madonna, baby at your breast.
        Wonder how you manage to feed the rest.
        See how they run.
        Lady Madonna, lying on the bed,
        Listen to the music playing in your head.
        Tuesday afternoon is never ending.
        Wednesday morning papers didn't come.
        Thursday night you stockings needed mending.
        See how they run.
        Lady Madonna, children at your feet.
        Wonder how you manage to make ends meet.
        """,
        url_title="Lady Madonna Lyrics :: The Beatles - Absolute Lyrics",
    ),
    LyricsPage.make(
        "https://www.azlyrics.com/lyrics/beatles/ladymadonna.html",
        """
        Lady Madonna, children at your feet
        Wonder how you manage to make ends meet
        Who finds the money when you pay the rent
        Did you think that money was Heaven sent?
        Friday night arrives without a suitcase
        Sunday morning creeping like a nun
        Monday's child has learned to tie his bootlace
        See how they run

        Lady Madonna, baby at your breast
        Wonders how you manage to feed the rest?

        See how they run

        Lady Madonna lying on the bed
        Listen to the music playing in your head

        Tuesday afternoon is never ending
        Wednesday morning papers didn't come
        Thursday night your stockings needed mending
        See how they run

        Lady Madonna, children at your feet
        Wonder how you manage to make ends meet
        """,
        url_title="The Beatles - Lady Madonna Lyrics | AZLyrics.com",
        marks=[xfail_on_ci("AZLyrics is blocked by Cloudflare")],
    ),
    LyricsPage.make(
        "https://www.dainuzodziai.lt/m/mergaites-nori-mylet-atlanta/",
        """
        Jos nesuspėja skriet paskui vėją
        Bangos į krantą grąžina jas vėl
        Jos karštą saulę paliesti norėjo
        Ant kranto palikę visas negandas

        Bet jos nori mylėt
        Jos nenori liūdėt
        Leisk mergaitėms mylėt
        Kaip jos moka mylėt
        Koks vakaras šiltas ir nieko nestinga
        Veidus apšviečia žaisminga šviesa
        Jos buvo laimingos prie jūros kur liko
        Tik vėjas išmokęs visas jų dainas
        """,
        artist="Atlanta",
        track_title="Mergaitės Nori Mylėt",
        url_title="Mergaitės nori mylėt – Atlanta | Dainų Žodžiai",
        marks=[xfail_on_ci("Expired SSL certificate")],
    ),
    LyricsPage.make(
        "https://genius.com/The-beatles-lady-madonna-lyrics",
        """
        [Intro: Instrumental]

        [Verse 1: Paul McCartney]
        Lady Madonna, children at your feet
        Wonder how you manage to make ends meet
        Who finds the money when you pay the rent?
        Did you think that money was heaven sent?

        [Bridge: Paul McCartney]
        Friday night arrives without a suitcase
        Sunday morning creeping like a nun
        Monday's child has learned to tie his bootlace
        See how they run

        [Verse 2: Paul McCartney]
        Lady Madonna, baby at your breast
        Wonders how you manage to feed the rest

        [Bridge: Paul McCartney, John Lennon & George Harrison]
        [Tenor Saxophone Solo: Ronnie Scott]
        See how they run

        [Verse 3: Paul McCartney]
        Lady Madonna, lying on the bed
        Listen to the music playing in your head

        [Bridge: Paul McCartney]
        Tuesday afternoon is never ending
        Wednesday morning papers didn't come
        Thursday night your stockings needed mending
        See how they run

        [Verse 4: Paul McCartney]
        Lady Madonna, children at your feet
        Wonder how you manage to make ends meet

        [Outro: Instrumental]
        """,
        marks=[xfail_on_ci("Genius returns 403 FORBIDDEN in CI")],
    ),
    LyricsPage.make(
        "https://www.lacoccinelle.net/259956-the-beatles-lady-madonna.html",
        """
        Lady Madonna
        Mademoiselle Madonna

        Lady Madonna, children at your feet.
        Mademoiselle Madonna, les enfants à vos pieds
        Wonder how you manage to make ends meet.
        Je me demande comment vous vous débrouillez pour joindre les deux bouts
        Who finds the money, when you pay the rent ?
        Qui trouve l'argent pour payer le loyer ?
        Did you think that money was heaven sent ?
        Pensiez-vous que ça allait être envoyé du ciel ?

        Friday night arrives without a suitcase.
        Le vendredi soir arrive sans bagages
        Sunday morning creeping like a nun.
        Le dimanche matin elle se traine comme une nonne
        Monday's child has learned to tie his bootlace.
        Lundi l'enfant a appris à lacer ses chaussures
        See how they run.
        Regardez comme ils courent

        Lady Madonna, baby at your breast.
        Mademoiselle Madonna, le bébé a votre sein
        Wonder how you manage to feed the rest.
        Je me demande comment vous faites pour nourrir le reste

        Lady Madonna, lying on the bed,
        Mademoiselle Madonna, couchée sur votre lit
        Listen to the music playing in your head.
        Vous écoutez la musique qui joue dans votre tête

        Tuesday afternoon is never ending.
        Le mardi après-midi n'en finit pas
        Wednesday morning papers didn't come.
        Le mercredi matin les journaux ne sont pas arrivés
        Thursday night you stockings needed mending.
        Jeudi soir, vos bas avaient besoin d'être réparés
        See how they run.
        Regardez comme ils filent

        Lady Madonna, children at your feet.
        Mademoiselle Madonna, les enfants à vos pieds
        Wonder how you manage to make ends meet.
        Je me demande comment vous vous débrouillez pour joindre les deux bouts
        """,
        url_title="Paroles et traduction The Beatles : Lady Madonna - paroles de chanson",  # noqa: E501
    ),
    LyricsPage.make(
        # note that this URL needs to be followed with a slash, otherwise it
        # redirects to the same URL with a slash
        "https://www.letras.mus.br/the-beatles/275/",
        """
        Lady Madonna
        Children at your feet
        Wonder how you manage
        To make ends meet

        Who finds the money
        When you pay the rent?
        Did you think that money
        Was Heaven sent?

        Friday night arrives without a suitcase
        Sunday morning creeping like a nun
        Monday's child has learned
        To tie his bootlace
        See how they run

        Lady Madonna
        Baby at your breast
        Wonders how you manage
        To feed the rest
        See how they run

        Lady Madonna
        Lying on the bed
        Listen to the music
        Playing in your head

        Tuesday afternoon is neverending
        Wednesday morning papers didn't come
        Thursday night your stockings
        Needed mending
        See how they run

        Lady Madonna
        Children at your feet
        Wonder how you manage
        To make ends meet
        """,
        url_title="Lady Madonna - The Beatles - LETRAS.MUS.BR",
    ),
    LyricsPage.make(
        "https://lrclib.net/api/get/14038",
        """
        [00:08.35] Lady Madonna, children at your feet
        [00:12.85] Wonder how you manage to make ends meet
        [00:17.56] Who finds the money when you pay the rent
        [00:21.78] Did you think that money was heaven sent
        [00:26.22] Friday night arrives without a suitcase
        [00:30.02] Sunday morning creeping like a nun
        [00:34.53] Monday's child has learned to tie his bootlace
        [00:39.18] See how they run
        [00:43.33] Lady Madonna, baby at your breast
        [00:48.50] Wonders how you manage to feed the rest
        [00:52.54]
        [01:01.32] Ba-ba, ba-ba, ba-ba, ba-ba-ba
        [01:05.03] Ba-ba, ba-ba, ba-ba, ba, ba-ba, ba-ba
        [01:09.58] Ba-ba, ba-ba, ba-ba, ba-ba-ba
        [01:14.27] See how they run
        [01:19.05] Lady Madonna, lying on the bed
        [01:22.99] Listen to the music playing in your head
        [01:27.92]
        [01:36.33] Tuesday afternoon is never ending
        [01:40.47] Wednesday morning papers didn't come
        [01:44.76] Thursday night your stockings needed mending
        [01:49.35] See how they run
        [01:53.73] Lady Madonna, children at your feet
        [01:58.65] Wonder how you manage to make ends meet
        [02:06.04]
        """,
    ),
    LyricsPage.make(
        "https://www.lyricsmania.com/lady_madonna_lyrics_the_beatles.html",
        """
        Lady Madonna, children at your feet.
        Wonder how you manage to make ends meet.
        Who finds the money? When you pay the rent?
        Did you think that money was heaven sent?

        Friday night arrives without a suitcase.
        Sunday morning creep in like a nun.
        Monday's child has learned to tie his bootlace.
        See how they run.

        Lady Madonna, baby at your breast.
        Wonder how you manage to feed the rest.

        See how they run.
        Lady Madonna, lying on the bed,
        Listen to the music playing in your head.

        Tuesday afternoon is never ending.
        Wednesday morning papers didn't come.
        Thursday night you stockings needed mending.
        See how they run.

        Lady Madonna, children at your feet.
        Wonder how you manage to make ends meet.
        """,
        url_title="The Beatles - Lady Madonna Lyrics",
    ),
    LyricsPage.make(
        "https://www.lyricsmode.com/lyrics/b/beatles/mother_natures_son.html",
        """
        Born a poor young country boy, Mother Nature's son
        All day long I'm sitting singing songs for everyone

        Sit beside a mountain stream, see her waters rise
        Listen to the pretty sound of music as she flies

        Doo doo doo doo doo doo doo doo doo doo doo
        Doo doo doo doo doo doo doo doo doo
        Doo doo doo

        Find me in my field of grass, Mother Nature's son
        Swaying daises sing a lazy song beneath the sun

        Doo doo doo doo doo doo doo doo doo doo doo
        Doo doo doo doo doo doo doo doo doo
        Doo doo doo doo doo doo
        Yeah yeah yeah

        Mm mm mm mm mm mm mm
        Mm mm mm, ooh ooh ooh
        Mm mm mm mm mm mm mm
        Mm mm mm mm, wah wah wah

        Wah, Mother Nature's son
        """,
        artist="The Beatles",
        track_title="Mother Nature's Son",
        url_title=(
            "Mother Nature's Son lyrics by The Beatles - original song full"
            " text. Official Mother Nature's Son lyrics, 2025 version"
            " | LyricsMode.com"
        ),
    ),
    LyricsPage.make(
        "https://www.lyricsontop.com/amy-winehouse-songs/jazz-n-blues-lyrics.html",
        """
        It's all gone within two days,
        Follow my father
        His extravagant ways
        So, if I got it out I'll spend it all.
        Heading In parkway, til I hit the wall.
        I cross my fingers at the cash machine,
        As I check my balance I kiss the screen,
        I love it when it says I got the main's
        To got o Miss Sixty and pick up my jeans.
        Money ever last long
        Had to fight what's wrong,
        Blow it all on bags and shoes,
        Jazz n' blues.
        Money ever last long,
        Had to fight what's wrong,
        Blow it all on bags and shoes,
        Jazz n' blues.

        Standing to the â€¦ bar today,
        Waiting impatient to throw my cash away,
        For that Russian JD and coke
        Had the drinks all night, and now I am bold
        But that's cool, cause I can buy more from you.
        And I didn't forgot about that 50 Compton,
        Tell you what? My fancy's coming through
        I'll take you at shopping, can you wait til next June?
        Yeah, Money ever last long
        Had to fight what's wrong,
        Blow it all on bags and shoes,
        Jazz n' blues.
        Money ever last long,
        Had to fight what's wrong,
        Blow it all on bags and shoes,
        Jazz n' blues.

        (Instrumental Break)

        Money ever last long
        Had to fight what's wrong,
        Blow it all on bags and shoes,
        Jazz n' blues.
        Money ever last long,
        Had to fight what's wrong,
        Blow it all on bags and shoes,
        Jazz n' blues.
        Money ever last long,
        Had to fight what's wrong,
        Blow it all on bags and shoes,
        Jazz n' blues.
        """,
        artist="Amy Winehouse",
        track_title="Jazz N' Blues",
        url_title="Amy Winehouse - Jazz N' Blues lyrics complete",
    ),
    LyricsPage.make(
        "https://www.musica.com/letras.asp?letra=59862",
        """
        Lady Madonna, baby at your breast
        Wonders how you manage to feed the rest

        See how they run

        Lady Madonna lying on the bed
        Listen to the music playing in your head

        Tuesday afternoon is never ending
        Wednesday morning papers didn't come
        Thursday night your stockings needed mending
        See how they run

        Lady Madonna, children at your feet
        Wonder how you manage to make ends meet
        """,
        url_title="Lady Madonna - Letra - The Beatles - Musica.com",
    ),
    LyricsPage.make(
        "https://www.paroles.net/the-beatles/paroles-lady-madonna",
        """
        Lady Madonna, children at your feet.
        Wonder how you manage to make ends meet.
        Who finds the money? When you pay the rent?
        Did you think that money was heaven sent?

        Friday night arrives without a suitcase.
        Sunday morning creep in like a nun.
        Monday's child has learned to tie his bootlace.
        See how they run.

        Lady Madonna, baby at your breast.
        Wonders how you manage to feed the rest.

        See how they run.
        Lady Madonna, lying on the bed,
        Listen to the music playing in your head.

        Tuesday afternoon is never ending.
        Wednesday morning papers didn't come.
        Thursday night your stockings needed mending.
        See how they run.

        Lady Madonna, children at your feet.
        Wonder how you manage to make ends meet.
        """,
        url_title="Paroles Lady Madonna par The Beatles - Lyrics - Paroles.net",
    ),
    LyricsPage.make(
        "https://www.songlyrics.com/the-beatles/lady-madonna-lyrics",
        """
        Lady Madonna, children at your feet
        Wonder how you manage to make ends meet
        Who finds the money? When you pay the rent?
        Did you think that money was Heaven sent?
        Friday night arrives without a suitcase
        Sunday morning creep in like a nun
        Monday's child has learned to tie his bootlace
        See how they run

        Lady Madonna, baby at your breast
        Wonder how you manage to feed the rest

        See how they run

        Lady Madonna, lying on the bed
        Listen to the music playing in your head

        Tuesday afternoon is never ending
        Wednesday morning papers didn't come
        Thursday night you stockings needed mending
        See how they run

        Lady Madonna, children at your feet
        Wonder how you manage to make ends meet
        """,
        url_title="THE BEATLES - LADY MADONNA LYRICS",
        marks=[xfail_on_ci("Songlyrics is blocked by Cloudflare")],
    ),
    LyricsPage.make(
        "https://sweetslyrics.com/the-beatles/lady-madonna-lyrics",
        """
        Lady Madonna, children at your feet.
        Wonder how you manage to make ends meet.
        Who finds the money when you pay the rent?
        Did you think that money was heaven sent?

        Friday night arrives without a suitcase.
        Sunday morning creeping like a nun.
        Monday's child has learned to tie his bootlace.
        See how they run...

        Lady Madonna, baby at your breast.
        Wonders how you manage to feed the rest.

        (Sax solo)

        See how they run...

        Lady Madonna, lying on the bed.
        Listen to the music playing in your head.

        Tuesday afternoon is never ending.
        Wednesday morning papers didn't come.
        Thursday night your stockings needed mending.
        See how they run...

        Lady Madonna, children at your feet.
        Wonder how you manage to make ends meet.
        """,
        url_title="The Beatles - Lady Madonna",
        marks=[xfail_on_ci("Sweetslyrics also fails with 403 FORBIDDEN in CI")],
    ),
    LyricsPage.make(
        "https://www.tekstowo.pl/piosenka,the_beatles,lady_madonna.html",
        """
        Lady Madonna,
        Children at your feet
        Wonder how you manage to make ends meet.

        Who find the money
        When you pay the rent?
        Did you think that money was Heaven sent?

        Friday night arrives without a suitcase
        Sunday morning creeping like a nun
        Monday's child has learned to tie his bootlace

        See how they run

        Lady Madonna
        Baby at your breast
        Wonders how you manage to feed the rest

        See how they run

        Lady Madonna
        Lying on the bed
        Listen to the music playing in your head

        Tuesday afternoon is neverending
        Wednesday morning papers didn't come
        Thursday night your stockings needed mending

        See how they run

        Lady Madonna,
        Children at your feet
        Wonder how you manage to make ends meet
        """,
        marks=[pytest.mark.xfail(reason="Tekstowo seems to be broken again")],
    ),
    LyricsPage.make(
        "https://genius.com/Caparezza-argenti-vive-lyrics",
        """
        Ciao Dante, ti ricordi di me? Sono Filippo Argenti
        Il vicino di casa che nella Commedia ponesti tra questi violenti
        Sono quello che annega nel fango, pestato dai demoni intorno
        Cos'è, vuoi provocarmi, sommo? Puoi solo provocarmi sonno!
        """,
        artist="Caparezza",
        track_title="Argenti vive",
        marks=[xfail_on_ci("Genius returns 403 FORBIDDEN in CI")],
    ),
    LyricsPage.make(
        "https://genius.com/Arctic-monkeys-r-u-mine-lyrics",
        """
        I go crazy 'cause here isn't where I wanna be
        And satisfaction feels like a distant memory
        And I can't help myself, all I
        Wanna hear her say is "Are you mine?"
        """,
        artist="Arctic Monkeys",
        track_title="R U Mine?",
        marks=[xfail_on_ci("Genius returns 403 FORBIDDEN in CI")],
    ),
    LyricsPage.make(
        "https://www.azlyrics.com/lyrics/derivakat/bountyhunter.html",
        """
        [Romanized:]

        Living legend made of myths and made of stories
        But I'm present, find the mark and I'll take the glory
        Hit the dead-end, cornered like an animal, it just
        Takes one second, I'm nothing if not practical
        But I don't really care if you're right or you're wrong
        Bùguǎn nǐ de wùhuì or you're just a disgrace
        Get in the zone when I put on my song
        Bìrán de xiànshí when I'm up in your face
        Zhēn tài kě qíng kùn zài lóng lǐ de nǐ
        But you'll find in the end that I'll leave you erased
        (If they call?) I'm the one
        (Got a job?) Get it done
        All alone, you and me, I'll be leaving no trace

        No place where I won't go to
        No limits I won't break through
        No godless deed I won't do
        If they got problems, then they know to

        Call the bounty hunter
        Yeah, they got my number
        I'm the problem solver
        Leave you six feet under
        You won't see another
        Winter, spring or summer
        Wǒ huì ràng nǐ xiāoshī
        No way to recover (Hey!)

        Run it up
        Night or day (Hey!)
        Hunt you down
        Run away

        No mercy from this mercenary
        Take away your sanctuary
        Shìlì jiù xiàng 20/20
        Way I see you'll end up buried
        Don't deviate
        Zhǎodào nǐ so I terminate
        Wúlùn, wǒ huì make you pay
        I'll double tap you like bang, bang

        (Dead lilac) A ghost you only heard in rumor
        (Dead lilac) But only if you heard me sooner
        (Dead lilac) Losing your chances and losing your time
        (Dead lilac) shìjiè wèilái méi nǐ de cúnzài (Yeah)

        No place where I won't go to (I won't go to)
        No limits I won't break through (I won't break through)
        No godless deed I won't do (That I won't do)
        If they got problems, then they know to

        Call the bounty hunter (Hey)
        Yeah, they got my number
        I'm the problem solver (Hey)
        Leave you six feet under
        You won't see another (Hey)
        Winter, spring or summer
        Wǒ huì ràng nǐ xiāoshī (Hey)
        No way to recover (Hey!)

        Run it up (Run it up)
        Night or day (Hey!) (Day)
        Hunt you down (Hunt you down)
        Run away

        [English/Chinese:]

        Living legend made of myths and made of stories
        But I'm present, find the mark and I'll take the glory
        Hit the dead-end, cornered like an animal, it just
        Takes one second, I'm nothing if not practical
        But I don't really care if you're right or you're wrong
        不管你的误会 or you're just a disgrace
        Get in the zone when I put on my song
        必然的现实 when I'm up in your face
        真太可情 困在笼里的你
        But you'll find in the end that I'll leave you erased
        (If they call?) I'm the one
        (Got a job?) Get it done
        All alone, you and me, I'll be leaving no trace

        No place where I won't go to
        No limits I won't break through
        No godless deed I won't do
        If they got problems, then they know to

        Call the bounty hunter
        Yeah, they got my number
        I'm the problem solver
        Leave you six feet under
        You won't see another
        Winter, spring or summer
        我会让你消失
        No way to recover (Hey!)

        Run it up
        Night or day (Hey!)
        Hunt you down
        Run away

        No mercy from this mercenary
        Take away your sanctuary
        视力就像 20/20
        Way I see you'll end up buried
        Don't deviate
        找到你 so I terminate
        无论, 我会 make you pay
        I'll double tap you like bang, bang

        (Dead lilac) A ghost you only heard in rumor
        (Dead lilac) But only if you heard me sooner
        (Dead lilac) Losing your chances and losing your time
        (Dead lilac) 世界未来没你的存在 (Yeah)

        No place where I won't go to (I won't go to)
        No limits I won't break through (I won't break through)
        No godless deed I won't do (That I won't do)
        If they got problems, then they know to

        Call the bounty hunter (Hey)
        Yeah, they got my number
        I'm the problem solver (Hey)
        Leave you six feet under
        You won't see another (Hey)
        Winter, spring or summer
        我会让你消失 (Hey)
        No way to recover (Hey!)

        Run it up (Run it up)
        Night or day (Hey!) (Day)
        Hunt you down (Hunt you down)
        Run away
        """,
        artist="Derivakat",
        track_title="Bounty Hunter",
        url_title="Derivakat - Bounty Hunter Lyrics | AZLyrics.com",
        marks=[xfail_on_ci("AZLyrics is blocked by Cloudflare")],
    ),
]
