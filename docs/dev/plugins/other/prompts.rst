.. _append_prompt_choices:

Append Prompt Choices
---------------------

Plugins can also append choices to the prompt presented to the user during an
import session.

To do so, add a listener for the ``before_choose_candidate`` event, and return a
list of ``PromptChoices`` that represent the additional choices that your plugin
shall expose to the user:

.. code-block:: python

    from beets.plugins import BeetsPlugin
    from beets.ui.commands import PromptChoice


    class ExamplePlugin(BeetsPlugin):
        def __init__(self):
            super().__init__()
            self.register_listener(
                "before_choose_candidate", self.before_choose_candidate_event
            )

        def before_choose_candidate_event(self, session, task):
            return [
                PromptChoice("p", "Print foo", self.foo),
                PromptChoice("d", "Do bar", self.bar),
            ]

        def foo(self, session, task):
            print('User has chosen "Print foo"!')

        def bar(self, session, task):
            print('User has chosen "Do bar"!')

The previous example modifies the standard prompt:

.. code-block:: shell

    # selection (default 1), Skip, Use as-is, as Tracks, Group albums,
    Enter search, enter Id, aBort?

by appending two additional options (``Print foo`` and ``Do bar``):

.. code-block:: shell

    # selection (default 1), Skip, Use as-is, as Tracks, Group albums,
    Enter search, enter Id, aBort, Print foo, Do bar?

If the user selects a choice, the ``callback`` attribute of the corresponding
``PromptChoice`` will be called. It is the responsibility of the plugin to check
for the status of the import session and decide the choices to be appended: for
example, if a particular choice should only be presented if the album has no
candidates, the relevant checks against ``task.candidates`` should be performed
inside the plugin's ``before_choose_candidate_event`` accordingly.

Please make sure that the short letter for each of the choices provided by the
plugin is not already in use: the importer will emit a warning and discard all
but one of the choices using the same letter, giving priority to the core
importer prompt choices. As a reference, the following characters are used by
the choices on the core importer prompt, and hence should not be used: ``a``,
``s``, ``u``, ``t``, ``g``, ``e``, ``i``, ``b``.

Additionally, the callback function can optionally specify the next action to be
performed by returning a ``importer.Action`` value. It may also return a
``autotag.Proposal`` value to update the set of current proposals to be
considered.
