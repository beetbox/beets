.. image:: https://img.shields.io/pypi/v/beets.svg
    :target: https://pypi.python.org/pypi/beets

.. image:: https://img.shields.io/codecov/c/github/beetbox/beets.svg
    :target: https://codecov.io/github/beetbox/beets

.. image:: https://travis-ci.org/beetbox/beets.svg?branch=master
    :target: https://travis-ci.org/beetbox/beets


beets
=====

Beets는 강박적인 음악을 듣는 사람들을 위한 미디어 라이브러리 관리 시스템이다.

Beets의 목적은 음악들을 한번에 다 받는 것이다.
음악들을 카탈로그화 하고, 자동으로 메타 데이터를 개선한다.
그리고 음악에 접근하고 조작할 수 있는 도구들을 제공한다.

다음은 Beets의 brainy tag corrector가 한 일의 예시이다.

  $ beet import ~/music/ladytron
  Tagging:
      Ladytron - Witching Hour
  (Similarity: 98.4%)
   * Last One Standing      -> The Last One Standing
   * Beauty                 -> Beauty*2
   * White Light Generation -> Whitelightgenerator
   * All the Way            -> All the Way...

Beets는 라이브러리로 디자인 되었기 때문에, 당신이 음악들에 대해 상상하는 모든 것을 할 수 있다.
`plugins`_ 을 통해서 모든 것을 할 수 있는 것이다!

- 필요하는 메타 데이터를 계산하거나 패치 할 때: `album art`_,
  `lyrics`_, `genres`_, `tempos`_, `ReplayGain`_ levels, or `acoustic
  fingerprints`_.
- `MusicBrainz`_, `Discogs`_,`Beatport`_로부터 메타데이터를 가져오거나,
  노래 제목이나 음향 특징으로 메타데이터를 추측한다
- `Transcode audio`_ 당신이 좋아하는 어떤 포맷으로든 변경한다.
- 당신의 라이브러리에서 `duplicate tracks and albums`_ 이나 `albums that are missing tracks`_ 를 검사한다.
- 남이 남기거나, 좋지 않은 도구로 남긴 잡다한 태그들을 지운다.
- 파일의 메타데이터에서 앨범 아트를 삽입이나 추출한다.
- 당신의 음악들을 `HTML5 Audio`_ 를 지원하는 어떤 브라우저든 재생할 수 있고,
  웹 브라우저에 표시 할 수 있다.
- 명령어로부터 음악 파일의 메타데이터를 분석할 수 있다.
- `MPD`_ 프로토콜을 사용하여 음악 플레이어로 음악을 들으면, 엄청나게 다양한 인터페이스로 작동한다.

만약 Beets에 당신이 원하는게 아직 없다면,
당신이 python을 안다면 `writing your own plugin`_ _은 놀라울정도로 간단하다.

.. _plugins: https://beets.readthedocs.org/page/plugins/
.. _MPD: https://www.musicpd.org/
.. _MusicBrainz music collection: https://musicbrainz.org/doc/Collections/
.. _writing your own plugin:
    https://beets.readthedocs.org/page/dev/plugins.html
.. _HTML5 Audio:
    http://www.w3.org/TR/html-markup/audio.html
.. _albums that are missing tracks:
    https://beets.readthedocs.org/page/plugins/missing.html
.. _duplicate tracks and albums:
    https://beets.readthedocs.org/page/plugins/duplicates.html
.. _Transcode audio:
    https://beets.readthedocs.org/page/plugins/convert.html
.. _Discogs: https://www.discogs.com/
.. _acoustic fingerprints:
    https://beets.readthedocs.org/page/plugins/chroma.html
.. _ReplayGain: https://beets.readthedocs.org/page/plugins/replaygain.html
.. _tempos: https://beets.readthedocs.org/page/plugins/acousticbrainz.html
.. _genres: https://beets.readthedocs.org/page/plugins/lastgenre.html
.. _album art: https://beets.readthedocs.org/page/plugins/fetchart.html
.. _lyrics: https://beets.readthedocs.org/page/plugins/lyrics.html
.. _MusicBrainz: https://musicbrainz.org/
.. _Beatport: https://www.beatport.com

설치
-------

당신은 ``pip install beets`` 을 사용해서 Beets를 설치할 수 있다.
그리고 `Getting Started`_ 가이드를 확인할 수 있다.

.. _Getting Started: https://beets.readthedocs.org/page/guides/main.html

컨트리뷰션
----------

어떻게 도우려는지 알고싶다면 `Hacking`_ 위키페이지를 확인하라.
당신은 docs 안에 `For Developers`_ 에도 관심이 있을수 있다.

.. _Hacking: https://github.com/beetbox/beets/wiki/Hacking
.. _For Developers: https://beets.readthedocs.io/en/stable/dev/

Read More
---------

`its Web site`_ 에서 Beets에 대해 조금 더 알아볼 수 있다.
트위터에서 `@b33ts`_ 를 팔로우하면 새 소식을 볼 수 있다.

.. _its Web site: https://beets.io/
.. _@b33ts: https://twitter.com/b33ts/

저자들
-------

`Adrian Sampson`_ 와 많은 사람들의 지지를 받아 Beets를 만들었다.
돕고 싶다면 `forum`_.를 방문하면 된다.

.. _forum: https://discourse.beets.io
.. _Adrian Sampson: https://www.cs.cornell.edu/~asampson/
