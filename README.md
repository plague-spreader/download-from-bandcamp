# download-from-bandcamp

Download any album from bandcamp.

Usage: `download_from_bandcamp.py <Bandcamp URL> [... <Bandcamp URL>]`

If an URL ends with "/music" then it is an "album container" and the script
downloads all the albums inside.

In any case every album will be downloaded inside a separate directory.
