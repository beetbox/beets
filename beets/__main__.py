"""The __main__ module lets you run the beets CLI interface by typing
`python -m beets`.
"""

import sys

from .ui import main

if __name__ == "__main__":
    main(sys.argv[1:])
