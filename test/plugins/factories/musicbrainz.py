import factory


class AliasFactory(factory.DictFactory):
    class Params:
        suffix = ""

    begin: str | None = None
    end: str | None = None
    ended = factory.LazyAttribute(lambda obj: obj.end is not None)
    locale: str | None = None
    name = factory.LazyAttribute(lambda o: f"Alias {o.suffix}")
    primary = False
    sort_name = factory.LazyAttribute(lambda o: f"{o.name}, The")
    type = "Artist name"
    type_id = "894afba6-2816-3c24-8072-eadb66bd04bc"
