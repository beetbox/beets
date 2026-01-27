import factory
from factory.fuzzy import FuzzyChoice

from beetsplug._utils.musicbrainz import ArtistRelationType


class _SortNameFactory(factory.DictFactory):
    name: str
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
        suffix = ""

    locale: str | None = None
    name = factory.LazyAttribute(lambda o: f"Alias {o.suffix}")
    primary = False
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
        [factory.SubFactory(AliasFactory, type="Release group name")]
    )
    artist_credit = factory.List([factory.SubFactory(ArtistCreditFactory)])
    disambiguation = factory.LazyAttribute(
        lambda o: f"{o.title} Disambiguation"
    )
    first_release_date = factory.Faker("date")
    genres = factory.List([])
    primary_type = "Album"
    primary_type_id = "f529b476-6e62-324f-b0aa-1f3e33d313fc"
    secondary_type_ids = factory.List([])
    secondary_types = factory.List([])
    tags = factory.List([])
    title = "Release Group"
