import factory
from factory.fuzzy import FuzzyChoice

from beetsplug._utils.musicbrainz import ArtistRelationType


class _SortNameFactory(factory.DictFactory):
    name: str | factory.LazyAttribute
    sort_name = factory.LazyAttribute(lambda o: f"{o.name}, The")


class _PeriodFactory(factory.DictFactory):
    begin: str | None = None
    end: str | None = None
    ended = factory.LazyAttribute(lambda obj: obj.end is not None)


class _IdFactory(factory.DictFactory):
    class Params:
        id_base = 0
        index = 1

    id = factory.LazyAttribute(
        lambda o: f"00000000-0000-0000-0000-{o.id_base + o.index:012d}"
    )


class AliasFactory(_SortNameFactory, _PeriodFactory):
    class Params:
        prefix = ""
        suffix = ""

    locale = "en"
    name = factory.LazyAttribute(
        lambda o: (
            f"{o.prefix + ' ' if o.prefix else ''}Alias {o.suffix or o.locale}"
        )
    )
    primary = True
    type = "Artist name"
    type_id = factory.LazyAttribute(
        lambda o: {
            "Artist name": "894afba6-2816-3c24-8072-eadb66bd04bc",
            "Label name": "3a1a0c48-d885-3b89-87b2-9e8a483c5675",
            "Legal name": "d4dcd0c0-b341-3612-a332-c0ce797b25cf",
            "Recording name": "5d564c8f-97de-3572-94bb-7f40ad661499",
            "Release group name": "156e24ca-8746-3cfc-99ae-0a867c765c67",
            "Release name": "df187855-059b-3514-9d5e-d240de0b4228",
            "Search hint": "abc2db8a-7386-354d-82f4-252c0213cbe4",
        }[o.type]
    )


class ArtistFactory(_SortNameFactory, _IdFactory):
    class Params:
        id_base = 0

    country: str | None = None
    disambiguation = ""
    name = "Artist"
    type = "Person"
    type_id = "b6e035f4-3ce9-331c-97df-83397230b0df"
    aliases = factory.List(
        [
            factory.SubFactory(
                AliasFactory,
                type="Artist name",
                prefix=factory.SelfAttribute("...name"),
            )
        ]
    )


class ArtistCreditFactory(factory.DictFactory):
    artist = factory.SubFactory(ArtistFactory)
    joinphrase = ""
    name = factory.LazyAttribute(lambda o: f"{o.artist['name']} Credit")


class ArtistRelationFactory(_PeriodFactory):
    artist = factory.SubFactory(
        ArtistFactory,
        name=factory.LazyAttribute(
            lambda o: f"{o.factory_parent.type.capitalize()} Artist"
        ),
    )
    attribute_ids = factory.Dict({})
    attribute_credits = factory.Dict({})
    attributes = factory.List([])
    direction = "backward"
    source_credit = ""
    target_credit = ""
    type = FuzzyChoice(ArtistRelationType.__args__)  # type: ignore[attr-defined]
    type_id = factory.Faker("uuid4")


class AreaFactory(factory.DictFactory):
    disambiguation = ""
    id = factory.Faker("uuid4")
    iso_3166_1_codes = factory.List([])
    iso_3166_2_codes = factory.List([])
    name = "Area"
    sort_name = "Area, The"
    type: None = None
    type_id: None = None


class ReleaseEventFactory(factory.DictFactory):
    area = factory.SubFactory(AreaFactory)
    date = factory.Faker("date")


class ReleaseGroupFactory(_IdFactory):
    class Params:
        id_base = 100

    aliases = factory.List(
        [
            factory.SubFactory(
                AliasFactory,
                type="Release group name",
                prefix=factory.SelfAttribute("...title"),
            )
        ]
    )
    artist_credit = factory.List([factory.SubFactory(ArtistCreditFactory)])
    disambiguation = factory.LazyAttribute(
        lambda o: f"{o.title} Disambiguation"
    )
    first_release_date = "2001-02-03"
    genres = factory.List([])
    primary_type = "Album"
    primary_type_id = "f529b476-6e62-324f-b0aa-1f3e33d313fc"
    secondary_type_ids = factory.List([])
    secondary_types = factory.List([])
    tags = factory.List([])
    title = "Release Group"


class GenreFactory(factory.DictFactory):
    id = factory.Faker("uuid4")
    count = 1
    disambiguation = ""
    name = "Genre"


class TagFactory(GenreFactory):
    name = "Tag"


class LabelFactory(_SortNameFactory, _IdFactory):
    aliases = factory.List([])
    disambiguation = ""
    genres = factory.List([])
    label_code: str | None = None
    name = "Label"
    tags = factory.List([])
    type = "Imprint"
    type_id = "b6285b2a-3514-3d43-80df-fcf528824ded"


class LabelInfoFactory(factory.DictFactory):
    catalog_number = "LAB123"
    label = factory.SubFactory(LabelFactory)


class TextRepresentationFactory(factory.DictFactory):
    language = "eng"
    script = "Latn"


class RecordingFactory(_IdFactory):
    class Params:
        id_base = 1000

    aliases = factory.List(
        [
            factory.SubFactory(
                AliasFactory,
                type="Recording name",
                prefix=factory.SelfAttribute("...title"),
            )
        ]
    )
    artist_credit = factory.List(
        [
            factory.SubFactory(
                ArtistCreditFactory, artist__name="Recording Artist"
            )
        ]
    )
    disambiguation = ""
    isrcs = factory.List([])
    length = 360
    title = "Recording"
    video = False
    genres = factory.List([])
    tags = factory.List([])


class TrackFactory(_IdFactory):
    class Params:
        id_base = 10000

    artist_credit = factory.List([])
    length = factory.LazyAttribute(lambda o: o.recording["length"])
    number = "A1"
    position = 1
    recording = factory.SubFactory(RecordingFactory)
    title = factory.LazyAttribute(
        lambda o: (
            f"{'Video: ' if o.recording['video'] else ''}{o.recording['title']}"
        )
    )


class MediumFactory(_IdFactory):
    class Params:
        id_base = 100000

    format = "Digital Media"
    format_id = "907a28d9-b3b2-3ef6-89a8-7b18d91d4794"
    position = 1
    title = "Medium"
    data_tracks = factory.List([])
    track_offset: int | None = None
    tracks = factory.List([factory.SubFactory(TrackFactory)])
    track_count = factory.LazyAttribute(lambda o: len(o.tracks))


class UrlFactory(factory.DictFactory):
    id = factory.Faker("uuid4")
    resource = "https://example.com"


class UrlRelationFactory(factory.DictFactory):
    type = "purchase for download"
    url = factory.SubFactory(UrlFactory)


class ReleaseFactory(_IdFactory):
    class Params:
        id_base = 1000000

    aliases = factory.List(
        [
            factory.SubFactory(
                AliasFactory,
                type="Release name",
                prefix=factory.SelfAttribute("...title"),
            )
        ]
    )
    artist_credit = factory.List(
        [factory.SubFactory(ArtistCreditFactory, artist__id_base=10)]
    )
    asin = factory.LazyAttribute(lambda o: f"{o.title} Asin")
    barcode = "0000000000000"
    cover_art_archive = factory.Dict(
        {
            "artwork": False,
            "back": False,
            "count": 0,
            "darkened": False,
            "front": False,
        }
    )
    disambiguation = factory.LazyAttribute(
        lambda o: f"{o.title} Disambiguation"
    )
    genres = factory.List([factory.SubFactory(GenreFactory)])
    label_info = factory.List([factory.SubFactory(LabelInfoFactory)])
    media = factory.List([factory.SubFactory(MediumFactory)])
    packaging: str | None = None
    packaging_id: str | None = None
    quality = "normal"
    release_events = factory.List(
        [
            factory.SubFactory(
                ReleaseEventFactory, area=None, date="2021-03-26"
            ),
            factory.SubFactory(
                ReleaseEventFactory,
                area__iso_3166_1_codes=["US"],
                date="2020-01-01",
            ),
        ]
    )
    release_group = factory.SubFactory(ReleaseGroupFactory)
    status = "Official"
    status_id = "4e304316-386d-3409-af2e-78857eec5cfe"
    tags = factory.List([factory.SubFactory(TagFactory)])
    text_representation = factory.SubFactory(TextRepresentationFactory)
    title = "Album"
