mStream
=======

``mstream`` is a music streaming server that can be used alongside beets

Demo
----

`See The Demo
<https://darncoyotes.mstream.io/>`_

Install & Run
-------------

You need to have Node & NPM installed to use mStream.  After that you can install 
mStream by running the following commands ::

    git clone https://github.com/IrosTheBeggar/mStream.git
    cd mStream
    # Install without dev dependencies
    npm install --only=production
    sudo npm link

Then just type ``mstream`` to run the server and go to
http://localhost:3000/.

`A full guide on how to install mStream on a fresh Ubuntu install can be found here
<https://irosthebeggar.github.io/mStream/docs/install.html>`_

Configure with CLI flags
------------------------

The quickest way to setup mStream is to use command line flags.
`A full list of command line settings can be seen here.
<https://irosthebeggar.github.io/mStream/docs/cli_arguments.html>`_ 
More advanced configurations can be made by using a JSON config file ::

    # change port (defaults to 3000)
    mstream -p 4999

    # setup user
    # the login system will be disabled if these values are not set
    mstream -u username -x password

    # set music directory
    # defaults to the current working directory if not set
    mstream -m /path/to/music

    ## lastFM Scrobbling
    mstream -l username -z password

Configure with JSON file
------------------------

mStream can also be booted using a JSON file using the `-j` flag.  
Using a JSON config file allows for more advanced configuration options,
such as multiple users and folders.

When booting with a JSON config file, all other flags will be ignored. ::

    mstream -j /path/to/config.json

An example config is shown below.  
`You can see the full set of config options here
<https://irosthebeggar.github.io/mStream/docs/json_config.html>`_ ::

    {
      "port": 3030,
      "database_plugin": {
        "dbPath":"/path/to/mstream.db"
      },
      "folders": {
        "blues": "/path/to/blues",
        "metal": "/path/to/metal"
      },
      "users": {
        "dan": {
          "password": "qwerty",
          "vpaths": ["blues", "metal"]
        },
        "james": {
          "password": "password",
          "vpaths": ["blues"],
          "lastfm-user": "username",
          "lastfm-password": "password"
        }
      }
    }
