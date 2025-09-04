Extend MediaFile
================

MediaFile_ is the file tag abstraction layer that beets uses to make
cross-format metadata manipulation simple. Plugins can add fields to MediaFile
to extend the kinds of metadata that they can easily manage.

The ``MediaFile`` class uses ``MediaField`` descriptors to provide access to
file tags. If you have created a descriptor you can add it through your plugins
:py:meth:`beets.plugins.BeetsPlugin.add_media_field` method.

.. _mediafile: https://mediafile.readthedocs.io/en/latest/

Here's an example plugin that provides a meaningless new field "foo":

.. code-block:: python

    class FooPlugin(BeetsPlugin):
        def __init__(self):
            field = mediafile.MediaField(
                mediafile.MP3DescStorageStyle("foo"), mediafile.StorageStyle("foo")
            )
            self.add_media_field("foo", field)


    FooPlugin()
    item = Item.from_path("/path/to/foo/tag.mp3")
    assert item["foo"] == "spam"

    item["foo"] == "ham"
    item.write()
    # The "foo" tag of the file is now "ham"
