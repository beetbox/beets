import factory


class _SortNameFactory(factory.DictFactory):
    name: str
    sort_name = factory.LazyAttribute(lambda o: f"{o.name}, The")


class AliasFactory(_SortNameFactory):
    class Params:
        suffix = ""

    begin: str | None = None
    end: str | None = None
    ended = factory.LazyAttribute(lambda obj: obj.end is not None)
    locale: str | None = None
    name = factory.LazyAttribute(lambda o: f"Alias {o.suffix}")
    primary = False
    type = "Artist name"
    type_id = "894afba6-2816-3c24-8072-eadb66bd04bc"


class ArtistFactory(_SortNameFactory):
    class Params:
        id_base = 0
        index = 1

    country: str | None = None
    disambiguation = ""
    id = factory.LazyAttribute(
        lambda o: f"00000000-0000-0000-0000-{o.id_base + o.index:012d}"
    )
    name = "Artist"
    type = "Person"
    type_id = "b6e035f4-3ce9-331c-97df-83397230b0df"


class ArtistCreditFactory(factory.DictFactory):
    artist = factory.SubFactory(ArtistFactory)
    joinphrase = ""
    name = factory.LazyAttribute(lambda o: f"{o.artist['name']} Credit")
