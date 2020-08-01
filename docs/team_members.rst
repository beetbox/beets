############
Team Members
############

.. _worthy of joining the team:

Becoming a team member
======================

At beets, our goal is to be as inclusive as possible to allow the organization to grow full of people that are willing to help out!

With that said, in order to become part of the beets team, all you have to do is follow a pull request through to the end without one of the current team members having to step in and finish it off. Once that's done, one of our team members should ask if you'd like to join the team. If we forget, please kindly ask us.

So, I just joined the team, now what?
=====================================

First of all, welcome! If you haven't already introduced yourself in our zulip chat, please do so the rest of the team can meet you. Besides getting to know the other team members, we like to use this chat to talk logistics about beets, or to house any informal discussion that wouldn't be better served in discourse or github.

Once you're on the team, you now have write access to the repository, and with great power comes great responsibility! Generally, we prefer any non-trivial changes to go through a pull-request process so other team members can give you the green light to merge it in.

As far as other maintenance actions go, feel free to start triaging any issues or reviewing/merging any pull requests. A couple of notes on those...

Issues
------

For triage, check out the `labels`_ we use. We try to keep things simple, and most should be self-explanatory, but there are a few that are worth pointing out.

* :code:`first timers only` : This is a label reserved for those that are new to open source. This idea was first introduced by Kent Dodds, who `explains the purpose of the label in his blog`_. We encourage anyone that chooses to apply this label to any issue, to follow the spirit of it and be willing to do a bit more hand holding than normal to help someone brand new achieve their first contribution to open source!

* :code:`bug`, :code:`feature`, and :code:`needinfo` : Basically, we like to limit the :code:`bug` and :code:`feature` labels to anything that is currently actionable so anyone can filter through the issues and start working on any one of them right away. In this sense, you can think of the :code:`needinfo` label as any bug or feature that is in a pre-actionable state. This could be anything to needing more info from the original poster, to needing more investigation by the team to figuring out the cause of a bug or whether or not we'd like to actually implement a proposed feature.

.. _explains the purpose of the label in his blog: https://kentcdodds.com/blog/first-timers-only

Pull Requests
-------------

Once you're a part of the team, please feel free to do any code reviews or merge any pull requests. For merging specifically, if the pull request is fairly large/significant, or perhaps you aren't confident in its implications, it's probably best to err on the side of caution and ask in our chat if you can get a second opinion before hitting the big green button.

Also, if the original author is `worthy of joining the team`_, then please send them an invitation to the chat and ping `@sampsyo`_ so he can add them to the team on GitHub.

.. _labels: https://github.com/beetbox/beets/labels
.. _@sampsyo: https://github.com/sampsyo

Miscellaneous
-------------

Stale-bot
^^^^^^^^^

Often, people will submit incomplete issues or pull requests and then disappear. To deal with this, we have a stale-bot that will run through old pull requests and issues with the :code:`needinfo` label. For more specifics on how it works, you can have a look at our `stale-bot configuration`_.

.. _stale-bot configuration: https://github.com/beetbox/beets/blob/master/.github/stale.yml
