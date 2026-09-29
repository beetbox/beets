import factory


class AudioTrackFactory(factory.DictFactory):
    type_ = "track"
    position = "1"
    title = "Track"
    duration = ""


class IndexTrackFactory(factory.DictFactory):
    type_ = "index"
    title = "Index Track"
    position = ""
    duration = ""
    sub_tracks = factory.List([factory.SubFactory(AudioTrackFactory)])


class HeadingTrackFactory(factory.DictFactory):
    type_ = "heading"
    title = "Heading Track"
    position = ""
    duration = ""
